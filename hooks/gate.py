"""mycelium-extra plan-approval gate for Claude Code and Codex hooks.

Usage (from hooks/hooks.json): gate.py stop | prompt | tool | post
Reads the hook JSON on stdin. Stdlib-only; runs on Python 3.6+.

Active only in a repository with .mycelium-extra/gate.json. It never emits
"allow": a command passes by the hook staying silent, so the user's own
permission prompts still apply. It catches mistakes; it is not security.

The Stop hook also pins the files on a plan's `Inputs:` line; the tool hook
blocks a launch whose pinned inputs changed; the post hook appends one run
receipt per gated run to .mycelium-extra/receipts.jsonl.

After `hints on`, the prompt and Stop hooks also suggest the command to run next.
"""

import ast
import collections
import fnmatch
import functools
import json
import os
import re
import sys
import time

STATE_DIR = ".mycelium-extra"
DEFAULTS = {
    "gated_paths": ["analysis/**", "nbs/**"],
    "gated_commands": ["sbatch", "snakemake", "nextflow"],
    "approval_hours": 24,
    "pin_hash_mb": 200,
    "pin_seconds": 5,
    "pin_scripts": True,
}
SCAN_SECONDS = 5  # reading approvals; the PreToolUse hook is killed at 10 s
EXPLORE_VAR = "MYCELIUM_EXTRA_EXPLORE"
APPROVE = re.compile(r"^\s*approve plan(?: ([0-9a-f]{8}))?\s*[.!]?\s*$", re.IGNORECASE)
EXPLORE_GRANT = re.compile(r"^\s*(allow|stop) explore\s*[.!]?\s*$", re.IGNORECASE)
HINTS_TOGGLE = re.compile(r"^\s*hints (on|off)\s*[.!]?\s*$", re.IGNORECASE)
HANDOFF_TOKENS = 120000  # context size at which the Stop hint suggests a handoff
# (pattern, command, condition); first match wins. "living": only where .living/ exists;
# "unplanned": only with no active approval. Specific rules go before the broad analysis one.
PROMPT_HINTS = [(re.compile(pattern, re.IGNORECASE), command, condition) for pattern, command, condition in (
    (r"\b(wrap up|hand ?off|new session|fresh session|continue later)\b", "/mycelium-extra:handoff", None),
    (r"\bnew analysis\b|\bscaffold", "/mycelium-extra:new-analysis", None),
    (r"\bwhich decisions?\b|\bconflicting decisions?\b|\bdecisions? (still )?binds?\b",
     "/mycelium-extra:decision-status", None),
    (r"\bsample (table|sheet)\b|\bcohort counts?\b", "/mycelium-extra:data-contract-check", None),
    (r"\b(brainstorm|ideas|what are we missing)\b", "/mycelium:ideas", "living"),
    (r"\bingest\b|\bregister (the |a )?data(set)?\b|\bnew data\b", "/mycelium:ingest", "living"),
    (r"\b(write[- ]?up|report)\b", "/mycelium:report", "living"),
    (r"\b(review|audit|sanity[- ]check)\b", "/mycelium:review", "living"),
    (r"\b(analy[sz]e|analysis|differential|pseudobulk|clustering|regression|enrichment|re-?run)\b",
     "/mycelium-extra:grill", "unplanned"),
)]
PLAN_STATUS = re.compile(
    r"^[\s>*_`]*plan status[\s*_`]*:[\s*_`]*(READY_WITH_ASSUMPTIONS|READY|DECISION_REQUIRED)[\s*_`.]*$",
    re.IGNORECASE | re.MULTILINE)
RUNNERS = re.compile(
    r"^(python[\d.]*|Rscript|R|bash|sh|zsh|jupyter|papermill|quarto|julia|perl|node|source|\.)$")
SHELLS = {"bash", "sh", "zsh"}
MYCELIUM_SEES = re.compile(r"^(python[\d.]*|Rscript|R|jupyter)$")  # Mycelium 0.7.2's run detector
SCRIPT_EXT = re.compile(r"(\.(py|R|r|sh|ipynb|qmd|Rmd|rmd|jl|smk|pl)$|(^|/)Snakefile$)")
WRAPPERS = {"env", "time", "nohup", "nice", "command", "exec", "stdbuf", "timeout", "srun",
            "conda", "mamba", "micromamba", "pixi", "uv", "run", "xvfb-run"}
VALUE_FLAGS = {"-n", "-p", "--name", "--prefix", "-e", "--environment", "--env",
               "-J", "--job-name", "-t", "--time", "-A", "--account", "--partition"}
WRITE_ALL = {"rm", "rmdir", "mv", "tee", "touch", "truncate", "mkdir", "chmod", "chown", "shred",
             "unlink"}  # every path argument is written
WRITE_LAST = {"cp", "ln", "install", "rsync", "scp"}  # only the destination is written
HEAD_SKIP = {"sudo", "do", "then", "else", "elif", "!", "{"}
WRITE_CODE = re.compile(
    r"""open\s*\([^)]*,\s*(mode\s*=\s*)?['"][^'"]*[wax+]|\.write(_text|_bytes|lines)?\s*\("""
    r"|\b(json|pickle)\.dump\s*\(|\bshutil\.\w+\s*\(|\bsubprocess\.|\bos\.system\s*\("
    r"|\bos\.(remove|unlink|rename|renames|replace|makedirs|mkdir|rmdir|removedirs|truncate|symlink"
    r"|link|chmod)\s*\(|\.(unlink|touch|mkdir|rmdir|rename|replace|symlink_to|chmod)\s*\("
    r"|\b(writeLines|saveRDS|save|write\.(csv|table|delim)|write_(csv|tsv|delim|lines|json|rds)"
    r"|file\.(remove|rename|create|copy|append)|unlink|dir\.create|sink|system2?)\s*\("
    r"|\bcat\s*\([^)]*\bfile\s*=")
PATHLIKE = re.compile(r"[\w./~-]+")
LOADS_FOLDER = re.compile(r"\bsys\.path\b|\b(os\.)?chdir\s*\(|\bsetwd\s*\(|\.libPaths\s*\(")
TABLE_ROW = re.compile(r"^\s*\|(.*)\|\s*$")
TABLE_RULE = re.compile(r"^\s*\|?[\s|:]*-[\s|:-]*$")
SOURCE_CITATION = re.compile(r"`?\brepo:\s*`?[^\s`|;,]+`?")
INPUTS_LINE = re.compile(r"^[\s>*_`-]*inputs[\s*_`]*:(.*)$", re.IGNORECASE | re.MULTILINE)
OUTPUTS_LINE = re.compile(r"^[\s>*_`-]*outputs[\s*_`]*:(.*)$", re.IGNORECASE | re.MULTILINE)
MAX_FOLDER_FILES = 5000
MAX_SNAPSHOT = 256 * 1024  # bytes; a larger script is pinned, but a change shows hashes only
MAX_SCRIPT_PINS = 500
DIFF_LINES = 30  # lines of diff on one approval card
LOCKFILES = ("renv.lock", "pixi.lock", "uv.lock", "poetry.lock", "Pipfile.lock", "conda-lock.yml",
             "environment.yml", "environment.yaml", "requirements.txt", "Manifest.toml")
ENV_LINE = re.compile(
    r"^\s*(module\s+(load|add|purge|use|restore)\b|(conda|mamba|micromamba)\s+activate\b"
    r"|(source|\.)\s+\S*activate\b|pixi\s+(run|shell)\b|(apptainer|singularity)\s+(exec|run|shell)\b"
    r"|export\s+(PATH|PYTHONPATH|R_LIBS\w*|CONDA_\w+)=)")
HOOK_ENV = ("CONDA_DEFAULT_ENV", "CONDA_PREFIX", "VIRTUAL_ENV", "PIXI_ENVIRONMENT_NAME")
JOB_ID = re.compile(r"Submitted batch job (\d+)")
PARSABLE_ID = re.compile(r"^\s*(\d+)(?:;[\w.-]+)?\s*$", re.MULTILINE)
NF_RUN_NAME = re.compile(r"Launching .*?\[([a-z]+_[a-z]+)\]")
GIT_TIMEOUT = 3


# ---------------------------------------------------------------- setup

def find_root(cwd):
    path = os.path.abspath(cwd or ".")
    while True:
        if os.path.isfile(os.path.join(path, STATE_DIR, "gate.json")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def load_config(root):
    with open(os.path.join(root, STATE_DIR, "gate.json"), encoding="utf-8") as handle:
        config = dict(DEFAULTS)
        config.update(json.load(handle))
    return config


def state_path(root, *parts):
    return os.path.join(root, STATE_DIR, *parts)


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1)
    os.replace(tmp, path)


def emit(payload):
    if payload:
        json.dump(payload, sys.stdout)
        sys.stdout.write("\n")


def safe_session(session_id):
    return re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "unknown")


def append_line(path, record):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def hash_budget(config):
    """Bytes this hook call may still read to hash files, and when it must stop.
    Hooks time out at 10-20 s, and data often sits on a network filesystem."""
    return {"bytes": float(config["pin_hash_mb"]) * 1024 * 1024,
            "deadline": time.time() + float(config["pin_seconds"])}


def listing(items, limit=10):
    items = list(items)
    return ", ".join(items[:limit]) + (" ..." if len(items) > limit else "")


# ---------------------------------------------------------------- fingerprints

def sha256(data=b""):
    import hashlib  # here, not at the top: most hook calls never hash
    return hashlib.sha256(data)


def sha256_file(path, deadline=None):
    """The file's sha256, or None if the deadline passes first."""
    digest = sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            if deadline is not None and time.time() >= deadline:
                return None
            digest.update(block)
    return digest.hexdigest()


def fingerprint(path, budget, pin=None):
    """Fingerprint a file or folder. A file gets a sha256 while the byte and time
    budget last, else size and mtime; given the pin it is compared with, it is
    hashed only if the pin was and the sizes still match."""
    try:
        info = os.stat(path)
    except OSError:
        return {"missing": True}
    if os.path.isdir(path):
        return folder_fingerprint(path, budget)
    if path.endswith(".ipynb") and info.st_size <= budget["bytes"]:
        text = notebook_code(path)  # executing a notebook rewrites its outputs, not its code
        if text is not None:
            return {"size": len(text), "mtime": int(info.st_mtime), "sha256": sha256(text).hexdigest()}
    record = {"size": info.st_size, "mtime": int(info.st_mtime)}
    wanted = pin is None or ("sha256" in pin and pin.get("size") == info.st_size)
    if wanted and info.st_size <= budget["bytes"] and time.time() < budget["deadline"]:
        digest = sha256_file(path, budget["deadline"])
        if digest:
            record["sha256"] = digest
            budget["bytes"] -= info.st_size
    return record


def notebook_code(path):
    """A notebook's code-cell sources as bytes, or None if it cannot be read as one."""
    try:
        with open(path, encoding="utf-8") as handle:
            cells = json.load(handle)["cells"]
        sources = ["".join(c["source"]) if isinstance(c["source"], list) else c["source"]
                   for c in cells if c.get("cell_type") == "code"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return "\n# ---- cell ----\n".join(sources).encode("utf-8")


def script_text(path):
    """What a script is pinned by: its bytes, or a notebook's code cells. None if unreadable."""
    if path.endswith(".ipynb"):
        text = notebook_code(path)
        if text is not None:
            return text
    try:
        with open(path, "rb") as handle:
            return handle.read(MAX_SNAPSHOT + 1)
    except OSError:
        return None


def folder_fingerprint(path, budget):
    """Names, sizes, and mtimes of the files under a folder; contents are not read.
    Past the deadline the folder is skipped, since a partial listing proves nothing."""
    skipped = {"folder": True, "skipped": "time limit"}
    lines = []
    for folder, dirs, files in os.walk(path):
        dirs.sort()
        for name in sorted(files):
            if time.time() >= budget["deadline"]:
                return skipped
            full = os.path.join(folder, name)
            try:
                info = os.stat(full)
            except OSError:
                continue
            lines.append("{}\t{}\t{}".format(os.path.relpath(full, path), info.st_size, int(info.st_mtime)))
            if len(lines) >= MAX_FOLDER_FILES:
                break
        if len(lines) >= MAX_FOLDER_FILES:
            break
    text = "\n".join(lines).encode("utf-8", "surrogateescape")
    record = {"folder": True, "files": len(lines), "listing_sha256": sha256(text).hexdigest()}
    if len(lines) >= MAX_FOLDER_FILES:
        record["truncated"] = True
    return record


def method(record):
    if record.get("missing"):
        return "missing"
    if record.get("skipped"):
        return "not pinned: " + record["skipped"]
    if record.get("folder"):
        return "folder listing"
    return "sha256" if "sha256" in record else "size+mtime"


def describe(record):
    if record.get("missing"):
        return "missing"
    if record.get("skipped"):
        return "not fingerprinted (" + record["skipped"] + ")"
    if record.get("folder"):
        return "{} files, listing {}".format(record["files"], record["listing_sha256"][:12])
    if "sha256" in record:
        return "sha256 {}".format(record["sha256"][:12])
    return "size {}, mtime {}".format(record["size"], record["mtime"])


def unchanged(pin, now):
    """Whether two fingerprints agree. A skipped one cannot disagree; callers
    that must say so check `skipped` first."""
    if pin.get("skipped") or now.get("skipped"):
        return True
    if pin.get("missing") or now.get("missing"):
        return bool(pin.get("missing")) == bool(now.get("missing"))
    if pin.get("folder") or now.get("folder"):
        return pin.get("listing_sha256") == now.get("listing_sha256")
    if pin.get("size") != now.get("size"):
        return False
    if "sha256" in pin and "sha256" in now:
        return pin["sha256"] == now["sha256"]
    return pin.get("mtime") == now.get("mtime")


# ---------------------------------------------------------------- command parsing

def tokenize(command, bodies=None):
    """Split a shell command into words and operator tokens.

    Quote-aware; `$(...)` stays inside its word; heredoc bodies are dropped,
    since they are stdin data, not commands. Newlines become ";". If given,
    `bodies` gets one entry per `<<` token, in order: its heredoc text, or "".
    """
    bodies = [] if bodies is None else bodies
    tokens, word, i, n = [], [], 0, len(command)
    heredocs = []
    in_word = False

    def flush():
        if in_word:
            tokens.append("".join(word))
        del word[:]
        return False

    while i < n:
        c = command[i]
        if c == "\\" and i + 1 < n:
            word.append(command[i + 1])
            in_word = True
            i += 2
        elif c in "'\"":
            end = command.find(c, i + 1)
            end = n if end < 0 else end
            word.append(command[i + 1:end])
            in_word = True
            i = end + 1
        elif c == "$" and command.startswith("$(", i):
            depth, j = 0, i
            while j < n:
                if command[j] == "(":
                    depth += 1
                elif command[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            word.append(command[i:j + 1])
            in_word = True
            i = j + 1
        elif c in " \t\r":
            in_word = flush()
            i += 1
        elif c == "\n":
            in_word = flush()
            tokens.append(";")
            i += 1
            for delimiter, slot in heredocs:
                lines = []
                while i < n:
                    end = command.find("\n", i)
                    end = n if end < 0 else end
                    line = command[i:end]
                    i = end + 1
                    if line.strip() == delimiter:
                        break
                    lines.append(line)
                bodies[slot] = "\n".join(lines)
            heredocs = []
        elif c in ";&|()<>":
            in_word = flush()
            j = i
            while j < n and command[j] == c and j - i < 2:
                j += 1
            op = command[i:j]
            if op in ("<<",) and command.startswith("-", j):
                j += 1
            if c in "<>" and command.startswith("&", j):
                j += 1
                while j < n and (command[j].isdigit() or command[j] == "-"):
                    j += 1
            tokens.append(command[i:j])
            i = j
            if op == "<<":
                bodies.append("")
                rest = command[i:].lstrip(" \t-")
                m = re.match(r"""['"]?([A-Za-z_][A-Za-z0-9_]*)['"]?""", rest)
                if m:
                    heredocs.append((m.group(1), len(bodies) - 1))
        else:
            word.append(c)
            in_word = True
            i += 1
    flush()
    return tokens


def is_separator(token):
    return token in (";", ";;", "&", "&&", "|", "||", "(", ")", "|&")


def segments(command):
    current = []
    for token in tokenize(command):
        if is_separator(token):
            if current:
                yield current
            current = []
        else:
            current.append(token)
    if current:
        yield current


def is_assignment(token):
    return re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", token) is not None


def repo_relative(root, cwd, token):
    token = os.path.expanduser(token)
    path = os.path.normpath(os.path.join(cwd, token))
    rel = os.path.relpath(os.path.realpath(path), os.path.realpath(root))
    if rel.startswith(".."):
        rel = os.path.relpath(path, root)
    if rel.startswith("..") or rel == ".":
        return None
    return rel.replace(os.sep, "/")


def gated_rel(root, cwd, token, config):
    rel = repo_relative(root, cwd, token)
    if rel is None:
        return None
    for pattern in config["gated_paths"]:
        glob = pattern.replace("**", "*")
        if fnmatch.fnmatch(rel, glob) or fnmatch.fnmatch(rel + "/", glob):
            return rel
    return None


def paths_in_text(root, cwd, text, config):
    """Gated scripts named in inline code; any gated path if the code imports from or moves into a folder."""
    loads = LOADS_FOLDER.search(text) is not None
    found = []
    for word in PATHLIKE.findall(text):
        rel = gated_rel(root, cwd, word, config) if "/" in word or "." in word else None
        if rel and (loads or SCRIPT_EXT.search(rel)):
            found.append(rel)
    return found


def classify(tokens, root, cwd, config):
    """Return (explore, gated_label or None, [gated repo paths]) for one segment."""
    explore = False
    i = 0
    while i < len(tokens) and is_assignment(tokens[i]):
        if tokens[i] == EXPLORE_VAR + "=1":
            explore = True
        i += 1
    previous = ""
    while i < len(tokens):
        word = os.path.basename(tokens[i])
        if word == "command" and tokens[i + 1:i + 2] in (["-v"], ["-V"]):
            return explore, None, []  # looks the name up, runs nothing
        if RUNNERS.match(word) or word in config["gated_commands"] or "/" in tokens[i]:
            break
        if (word in WRAPPERS or tokens[i].startswith("-") or previous in VALUE_FLAGS
                or tokens[i].isdigit() or re.match(r"^\d+[smhd]?$", tokens[i])
                or is_assignment(tokens[i])):
            if tokens[i] == EXPLORE_VAR + "=1":
                explore = True
            previous = tokens[i]
            i += 1
            continue
        return explore, None, []
    if i >= len(tokens):
        return explore, None, []
    head, rest = tokens[i], tokens[i + 1:]
    word = os.path.basename(head)
    paths = []
    for j, token in enumerate(rest):
        if token == "<" and j + 1 < len(rest):
            rel = gated_rel(root, cwd, rest[j + 1], config)
            if rel:
                paths.append(rel)
    if word in config["gated_commands"]:
        wraps = [t.split("=", 1)[1] for t in rest if t.startswith("--wrap=")]
        wraps += [rest[j + 1] for j, t in enumerate(rest) if t == "--wrap" and j + 1 < len(rest)]
        # sbatch's job folder (`-D DIR`, `--chdir DIR`) is where the job runs, not code it runs.
        folder = [j + 1 for j, t in enumerate(rest) if word == "sbatch" and t in ("-D", "--chdir")]
        paths += [p for p in (gated_rel(root, cwd, t, config) for j, t in enumerate(rest)
                              if not t.startswith("-") and j not in folder) if p]
        return explore, word, paths + ["wrap:" + w for w in wraps]
    if RUNNERS.match(word):
        positional = None
        skip = False
        for j, token in enumerate(rest):
            if skip:
                skip = False
                continue
            if token in ("<", ">", ">>", "<<", "<<-") or re.match(r"^\d?>&?\d*$", token):
                skip = token in ("<", ">", ">>", "<<", "<<-") or token.endswith(">")
                continue
            if word in SHELLS and re.match(r"^-[A-Za-z]*c[A-Za-z]*$", token) and j + 1 < len(rest):
                return explore, "recurse", [rest[j + 1]]
            if token in ("-c", "-e", "--eval") and j + 1 < len(rest):
                paths += paths_in_text(root, cwd, rest[j + 1], config)
                skip = True
                continue
            if token == "-m" and j + 1 < len(rest):
                module = rest[j + 1].replace(".", "/")
                rel = gated_rel(root, cwd, module + ".py", config) or gated_rel(root, cwd, module, config)
                if rel:
                    paths.append(rel)
                skip = True
                continue
            value = token.split("=", 1)[1] if token.startswith("-") and "=" in token else token
            if token.startswith("-") and value == token:
                continue
            rel = gated_rel(root, cwd, value, config)
            first = positional is None and not token.startswith("-")
            if first:
                positional = token
            if rel and (first or SCRIPT_EXT.search(rel) or word in ("jupyter", "papermill", "quarto")):
                paths.append(rel)
        return explore, (word if paths else None), paths
    rel = gated_rel(root, cwd, head, config)
    return explore, (head if rel else None), ([rel] if rel else [])


def job_cwd(tokens, cwd):
    """Where an sbatch job runs: its `-D`/`--chdir` folder, relative to where sbatch ran."""
    args = after_word(tokens, "sbatch")
    folders = flag_values(args, ("-D", "--chdir")) + [t[2:] for t in args if t.startswith("-D") and len(t) > 2]
    return os.path.normpath(os.path.join(cwd, os.path.expanduser(folders[-1]))) if folders else cwd


def cd_target(cwd, tokens):
    target = tokens[1] if len(tokens) > 1 else os.path.expanduser("~")
    return os.path.normpath(os.path.join(cwd, os.path.expanduser(target)))


def analyse_command(command, root, cwd, config):
    """Yield (explore, label, paths, segment, tokens, cwd) for each gated segment."""
    virtual_cwd = cwd
    for tokens in segments(command):
        if tokens[0] == "cd":
            virtual_cwd = cd_target(virtual_cwd, tokens)
            continue
        explore, label, paths = classify(tokens, root, virtual_cwd, config)
        if label == "recurse":
            for inner in analyse_command(paths[0], root, virtual_cwd, config):
                yield (inner[0] or explore,) + inner[1:]
            continue
        wraps = [p[5:] for p in paths if p.startswith("wrap:")]
        paths = [p for p in paths if not p.startswith("wrap:")]
        for payload in wraps:  # an sbatch --wrap payload runs in the job's folder
            inner_cwd = job_cwd(tokens, virtual_cwd) if label == "sbatch" else virtual_cwd
            for inner in analyse_command(payload, root, inner_cwd, config):
                yield (inner[0] or explore,) + inner[1:]
        if label:
            yield explore, label, paths, " ".join(tokens), tokens, virtual_cwd


def writes_state(command, root, cwd):
    """True if the command visibly writes into the gate's state folder.

    Redirect and file-command targets are resolved against the folder, so a
    command that only mentions it (reading it, or writing text about it
    elsewhere) passes. A runner's code cannot be traced: it counts when it
    gets a path in the folder, or when its code mentions the folder and writes.
    """
    if STATE_DIR not in command:
        return False
    state = os.path.realpath(state_path(root))
    bodies = []
    all_tokens = tokenize(command, bodies)
    bound = binds_state(all_tokens)
    values = literal_values(all_tokens)
    virtual_cwd, used, written = cwd, 0, {}
    for tokens in segments(command):
        heredocs = sum(1 for t in tokens if t in ("<<", "<<-"))
        own, used = bodies[used:used + heredocs], used + heredocs
        for j, token in enumerate(tokens[:-1]):
            if own and token in (">", ">>"):  # cat > run.py <<EOF: run.py's code is that heredoc
                written[tokens[j + 1]] = "\n".join(own)
        own += [written[t] for t in tokens if t in written]
        if tokens[0] == "cd":
            virtual_cwd = cd_target(virtual_cwd, tokens)
            continue

        def inside(token):
            if "`" not in token and "$(" not in token:
                token = re.sub(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?",
                               lambda m: values.get(m.group(1), m.group(0)), token)
            if "$" in token or "`" in token:  # unresolvable: may hold a path into the folder
                return STATE_DIR in token or bound
            path = os.path.realpath(os.path.join(virtual_cwd, os.path.expanduser(token)))
            return path == state or path.startswith(state + os.sep)

        if segment_writes(tokens, own, command, inside, root, virtual_cwd):
            return True
    return False


def literal_values(tokens):
    """Variables the command sets, each exactly once, to a literal value."""
    values, seen = {}, set()
    for token in tokens:
        if is_assignment(token):
            name, value = token.split("=", 1)
            if name in seen or "$" in value or "`" in value:
                values.pop(name, None)
            else:
                values[name] = value
            seen.add(name)
    return values


WRITE_CONTENT = {"write", "writelines", "write_text", "write_bytes"}
PURE_CALLS = {"join", "getcwd", "abspath", "realpath", "normpath", "relpath", "dirname", "basename",
              "expanduser", "str", "repr", "format"}


def names_state(code, root, cwd, python=False):
    """Whether code names the state folder as a target, not as text it writes elsewhere.

    For Python, a string literal counts when it is a path (no whitespace) or a
    shell command that writes the folder; prose and multi-line strings are text
    (a file's new content), and a comment is not code. A literal that only reaches
    a `.write()` call's content, through path-building calls such as `os.path.join`,
    is text too. Python that this interpreter cannot parse (3.8+ syntax on 3.6) is
    scanned token by token for the same literals; other code (R, perl) counts on
    any mention.
    """
    # ponytail: a state path split across pieces or hidden in a multi-line string passes;
    # data-flow tracking if that ever shows up in real use
    def target(value):
        return isinstance(value, str) and STATE_DIR in value and (
            not value.split(None, 1)[1:] or "\n" not in value and writes_state(value, root, cwd))
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        values = string_literals(code) if python else None
        return STATE_DIR in code if values is None else any(target(value) for value in values)
    text = written_text(tree)
    for node in ast.walk(tree):
        kind = type(node).__name__
        value = node.value if kind == "Constant" else node.s if kind == "Str" else None
        if id(node) not in text and target(value):
            return True
    return False


def written_text(tree):
    """ids of the string literals that are only content handed to a `.write()` call."""
    found = set()

    def descend(node):
        kind = type(node).__name__
        if kind == "Call":
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if name not in PURE_CALLS:
                return  # its result is not plain text: open(...).read(), a write, a delete
            children = list(node.args) + [keyword.value for keyword in node.keywords]
            children += [node.func.value] if type(node.func).__name__ == "Attribute" else []
        else:
            if kind in ("Constant", "Str"):
                found.add(id(node))
            children = ast.iter_child_nodes(node)
        for child in children:
            descend(child)

    for node in ast.walk(tree):
        if type(node).__name__ == "Call" and getattr(node.func, "attr", None) in WRITE_CONTENT:
            for arg in node.args:
                descend(arg)
    return found


def string_literals(code):
    """The string literals of Python source, read by its tokens; None if it does not tokenize."""
    import io
    import tokenize as pytokenize  # local: this module has its own tokenize()
    values = []
    try:
        for token in pytokenize.generate_tokens(io.StringIO(code).readline):
            if pytokenize.tok_name.get(token[0]) in ("STRING", "FSTRING_MIDDLE"):
                try:
                    values.append(ast.literal_eval(token[1]))
                except (SyntaxError, ValueError):
                    values.append(token[1])  # an f-string: its raw text
    except (pytokenize.TokenError, SyntaxError):
        return None
    return values


def binds_state(tokens):
    """Whether a variable in the command may hold a path into the state folder."""
    for j, token in enumerate(tokens):
        if is_assignment(token) and STATE_DIR in token:
            return True
        if token == "in" and j >= 2 and tokens[j - 2] == "for":
            for item in tokens[j + 1:]:
                if is_separator(item):
                    break
                if STATE_DIR in item:
                    return True
    return False


def segment_writes(tokens, bodies, command, inside, root, cwd):
    for j, token in enumerate(tokens[:-1]):
        if token in (">", ">>") and inside(tokens[j + 1]):
            return True
    i, previous = 0, ""
    while i < len(tokens) and (tokens[i] in WRAPPERS or tokens[i] in HEAD_SKIP or is_assignment(tokens[i])
                               or tokens[i].startswith("-") or previous in VALUE_FLAGS
                               or re.match(r"^\d+[smhd]?$", tokens[i])):
        previous = tokens[i]
        i += 1
    if i >= len(tokens):
        return False
    head, args = os.path.basename(tokens[i]), tokens[i + 1:]
    code = [args[j + 1] for j, t in enumerate(args[:-1]) if t in ("-c", "-e", "--eval")]
    stdin = [args[j + 1] for j, t in enumerate(args[:-1]) if t == "<"]
    positional, skip = [], False
    for token in args:
        if skip or token in code:
            skip = False
            continue
        skip = token in (">", ">>", "<", "<<", "<<-")
        if not skip and not token.startswith("-") and not token.startswith(">"):
            positional.append(token)
    if head in SHELLS:
        if any(writes_state(payload, root, cwd) for payload in code + bodies):
            return True
        if code:
            return False
    if head == "eval":
        return writes_state(" ".join(args), root, cwd)
    if head == "xargs":  # its targets arrive on stdin
        return any(os.path.basename(t) in WRITE_ALL | WRITE_LAST for t in args)
    if head in WRITE_ALL:
        return any(inside(t) for t in positional)
    if head in WRITE_LAST:
        targets = positional[-1:] + [t.split("=", 1)[1] for t in args if t.startswith("--target-directory=")]
        targets += [args[j + 1] for j, t in enumerate(args[:-1]) if t == "-t"]
        return any(inside(t) for t in targets)
    if head == "dd":
        return any(t.startswith("of=") and inside(t[3:]) for t in args)
    if head in ("sed", "perl") and any(re.match(r"^-\w*i", t) for t in args):
        if head == "sed" and not any(t in ("-f", "--expression", "--file") or t.startswith(
                ("--expression=", "--file=")) for t in args + code):
            positional = positional[1:] if not code else positional  # the first word is the script
        return any(inside(t) for t in positional)
    if head == "find" and any(t in ("-delete", "-exec", "-execdir", "-ok", "-okdir") for t in args):
        return any(inside(t) for t in positional)
    if RUNNERS.match(head):
        if any(inside(t) for t in positional + stdin):
            return True
        if not (code or bodies or positional or stdin):  # code piped in from another segment
            return WRITE_CODE.search(command) is not None
        return any(names_state(text, root, cwd, head.startswith("python")) and WRITE_CODE.search(text)
                   for text in code + bodies)
    return False


# ---------------------------------------------------------------- approvals

def active_approvals(root, config):
    """Approvals from the last `approval_hours`, or None if reading them ran out of time.
    Approval files are kept (verify reads old ones), so the folder only grows."""
    folder = state_path(root, "approvals")
    horizon = time.time() - float(config["approval_hours"]) * 3600
    deadline = time.time() + SCAN_SECONDS
    approvals = []
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            if time.time() >= deadline:
                return None
            record = read_json(os.path.join(folder, name), None)
            if record and record.get("approved_at", 0) >= horizon:
                approvals.append(record)
    return approvals


def covering(root, label, paths, approvals):
    """The approvals whose plan table covers a run, oldest first."""
    found = []
    for record in approvals:
        table = plan_table(record.get("plan", ""))
        if paths:
            if all(path_in_plan(root, path, table) for path in paths):
                found.append(record)
        elif names_command(label, table):
            found.append(record)
    return sorted(found, key=lambda record: record.get("approved_at", 0))


@functools.lru_cache(maxsize=None)
def plan_table(plan):
    """The text of the plan's table cells, minus Source cells and `repo:` citations.

    Only the table approves runs: a path or command word in prose, Evidence,
    or a source citation approves nothing. "" when the plan has no table.
    """
    lines = plan.splitlines()
    cells, dropped = [], set()
    for i, line in enumerate(lines):
        if not TABLE_ROW.match(line):
            dropped = set()
            continue
        if TABLE_RULE.match(line):
            continue
        parts = [cell.replace("\0", "|").strip()
                 for cell in TABLE_ROW.match(line).group(1).replace("\\|", "\0").split("|")]
        following = lines[i + 1] if i + 1 < len(lines) else ""
        if TABLE_ROW.match(following) and TABLE_RULE.match(following):  # a header row
            dropped = {j for j, cell in enumerate(parts) if "source" in cell.lower()}
            continue
        cells += [cell for j, cell in enumerate(parts) if j not in dropped]
    return SOURCE_CITATION.sub(" ", "\n".join(cells))


def names_command(command, table):
    return re.search(r"\b{}\b".format(re.escape(command)), table) is not None


@functools.lru_cache(maxsize=None)
def plan_paths(table):
    tokens = set()
    for word in PATHLIKE.findall(table):
        word = word.rstrip(".,;:").rstrip("/")
        if word.startswith("./"):
            word = word[2:]
        if "/" in word:
            tokens.add(word)
    return frozenset(tokens)  # cached, so callers must not mutate it


def plan_paths_in(root, table):
    """plan_paths with each path inside the project root made root-relative, the one form the
    gate and verify compare; a path outside the root stays as written."""
    return frozenset((repo_relative(root, root, p) or p) if os.path.isabs(p) else p for p in plan_paths(table))


def path_in_plan(root, path, table):
    named = plan_paths_in(root, table)
    parts = path.split("/")
    return any("/".join(parts[:depth]) in named for depth in range(len(parts), 1, -1))


def bullets(items, limit=10):
    items = list(items)
    return ["    \u2022 " + item for item in items[:limit]] + (
        ["    \u2026 and {} more".format(len(items) - limit)] if len(items) > limit else [])


def plan_grants(root, plan, config):
    """(gated paths, gated commands) the plan table lets through: a path covers itself and
    everything gated below it, a command covers every invocation."""
    table = plan_table(plan)
    paths = sorted(set(gated_rel(root, root, p, config) for p in plan_paths_in(root, table)) - set([None]))
    return paths, [c for c in config["gated_commands"] if names_command(c, table)]


def scope_lines(root, plan, config):
    """Which gated runs approving this plan would let through."""
    if not plan_table(plan).strip():
        return ["  Runs allowed: none (the plan has no plan table; only its paths and commands count)"]
    paths, commands = plan_grants(root, plan, config)
    runs = paths + commands
    if not runs:
        return ["  Runs allowed: none (the plan table names no gated script, folder, or command)"]
    return ["  Runs allowed"] + bullets(runs)


def output_words(text):
    """The paths on the plan's `Outputs:` lines, or None when it has none."""
    lines = OUTPUTS_LINE.findall(text)
    if not lines:
        return None
    words = []
    for line in lines:
        for word in PATHLIKE.findall(line):
            word = word.rstrip(".,;:")
            if ("/" in word or re.search(r"\.\w+$", word)) and word not in words:
                words.append(word)
    return words


def output_lines(text):
    """The paths on the plan's `Outputs:` lines, which verify checks after the runs."""
    words = output_words(text)
    if words is None:
        return ["  Outputs: none named (no `Outputs:` line)"]
    return ["  Outputs"] + bullets(words) if words else ["  Outputs: none"]


def approval_card(root, text, config, digest, pins, outside, previous, scripts=None):
    card = procedure_card(root, text, config, digest, pins, outside, previous, scripts or {})
    if card:
        return card
    return "\n".join(["mycelium-extra \u00b7 plan ready for approval",
                      "  \u25b6 approve plan {}".format(digest), ""]
                     + scope_lines(root, text, config) + pin_lines(pins, outside, previous)
                     + script_lines(root, scripts, config) + output_lines(text))


# ---------------------------------------------------------------- the procedure card
# What the user reads to check a plan: its question, goal, steps with their choices and checks,
# and everything the gate would let run. Display only: the gate still approves from plan_table,
# and nothing quoted here is read back as a path or a command.

CARD_COMPACT = 6   # up to this many steps take three lines each; more take two
CARD_STEPS = 15    # steps shown at all; the plan above lists the rest
CARD_CELL = 200   # a choice or a check is quoted up to this many characters
CARD_PREFIX = 12   # a shared path prefix is stripped when it is at least this long
CONTROL = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|[\x00-\x1f\x7f]")
APPROVE_WORDS = re.compile(r"approve\s+plan", re.IGNORECASE)
DONE_MARK = re.compile(r"\s*\(done\)", re.IGNORECASE)
FLAG_WORDS = re.compile(r"\b(fail\w*|flag\w*|warn\w*|error\w*|diverg\w*|mismatch\w*|unverified)\b",
                        re.IGNORECASE)
QUESTION_LINE = re.compile(r"^>\s*Question[^:]*:\s*(.*)$", re.MULTILINE)
OBJECTIVE_LINE = re.compile(r"^[\s>*_`-]*objective[\s*_`]*[.:]?[\s*_`]*(.*)$", re.IGNORECASE)
EVIDENCE_HEAD = re.compile(r"^[\s>*_`-]*evidence\b", re.IGNORECASE)
FACTS_LINE = re.compile(r"^Facts:.*$", re.MULTILINE)
EVIDENCE_TAG = re.compile(r"\s*\[(agent-derived|agent-asserted|human-stated)[^\]]*\]\s*$")
TAG_WORD = {"agent-derived": "derived", "agent-asserted": "asserted", "human-stated": "stated"}


def clean(text, limit=CARD_CELL):
    """Plan text made safe to quote: no control or ANSI characters, no markup, no `approve plan`
    phrase (only the card's last line may offer one), one line, shortened."""
    text = " ".join(CONTROL.sub(" ", text).replace("`", "").replace("**", "").split())
    text = APPROVE_WORDS.sub("approve-plan", text)
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "\u2026"


def table_cells(line):
    return [cell.replace("\0", "|").strip() for cell in TABLE_ROW.match(line).group(1).replace("\\|", "\0").split("|")]


def plan_rows(text):
    """The first plan table with a Step column and a Choice or Validation column, as a list of
    {num, step, choice, source, check}; None when there is no such table."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        following = lines[i + 1] if i + 1 < len(lines) else ""
        if not TABLE_ROW.match(line) or TABLE_RULE.match(line) or not (
                TABLE_ROW.match(following) and TABLE_RULE.match(following)):
            continue
        column = {}
        for j, cell in enumerate(c.lower() for c in table_cells(line)):
            for key, words in (("step", ("step",)), ("choice", ("choice",)), ("source", ("source",)),
                               ("check", ("validation", "check"))):
                if key not in column and any(word in cell for word in words):
                    column[key] = j
            if cell in ("#", "no", "no.") and "num" not in column:
                column["num"] = j
        if "step" not in column or not ("choice" in column or "check" in column):
            continue
        rows = []
        for row in lines[i + 2:]:
            if not TABLE_ROW.match(row):
                break
            if TABLE_RULE.match(row):
                continue
            cells = table_cells(row)
            cell = lambda key: cells[column[key]] if key in column and column[key] < len(cells) else ""
            rows.append({"num": cell("num") or str(len(rows) + 1), "step": cell("step"),
                         "choice": cell("choice"), "source": cell("source"), "check": cell("check")})
        return rows
    return None


def source_tag(cell):
    cell = " ".join(CONTROL.sub(" ", cell).replace("`", "").split())
    low = cell.lower()
    if low.startswith("user"):
        return "you"
    if low.startswith(("default", "repo")):
        return clean(cell.split(";")[0], 48)
    return clean(cell, 24)


def card_question(text):
    found = QUESTION_LINE.search(text)
    return clean(found.group(1), 200) if found and found.group(1).strip() else "none in the plan"


def card_goal(text):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        found = OBJECTIVE_LINE.match(line)
        if found:
            rest = found.group(1).strip() or next((l.strip() for l in lines[i + 1:] if l.strip()), "")
            return clean(rest, 240)
    return "none in the plan"


def evidence_flags(text):
    """The Evidence bullets that name a failure or a flag, tagged by how the fact was established."""
    found, inside = [], False
    for line in text.splitlines():
        if EVIDENCE_HEAD.match(line):
            inside = True
            continue
        if not inside:
            continue
        bullet = re.match(r"^\s*[-*]\s+(.*)$", line)
        if not bullet:
            if line.strip() and not line.startswith(" "):
                break
            continue
        body = bullet.group(1)
        if FLAG_WORDS.search(body):
            tag = EVIDENCE_TAG.search(body)
            found.append(clean(EVIDENCE_TAG.sub("", body), 150) + (" [{}]".format(TAG_WORD[tag.group(1)]) if tag else ""))
    return found


def shared_prefix(paths):
    paths = sorted(set(p for p in paths if p and not os.path.isabs(p)))
    if len(paths) < 2:
        return ""
    prefix = os.path.commonpath(paths)
    return prefix if len(prefix) >= CARD_PREFIX else ""


def prose_only(root, text, config, listed):
    """Scripts the plan mentions outside its table (and outside Inputs and Outputs), which approve nothing."""
    table, found = plan_table(text), []
    for word in PATHLIKE.findall(text):
        word = word.rstrip(".,;:").rstrip("/")
        if word.startswith("./"):
            word = word[2:]
        if "/" not in word or not SCRIPT_EXT.search(word) or word in listed:
            continue
        rel = gated_rel(root, root, word, config)
        if rel and rel not in found and not path_in_plan(root, rel, table):
            found.append(rel)
    return found


def names(items, short):
    """The first three paths; with more than one, the folder they share is named once."""
    items = sorted(items)
    base = os.path.commonpath(items) if len(items) > 1 and not any(os.path.isabs(i) for i in items) else ""
    shown = [i[len(base) + 1:] if base and i.startswith(base + "/") else short(i) for i in items[:3]]
    more = ", \u2026 and {} more".format(len(items) - 3) if len(items) > 3 else ""
    lead = " under {}/: ".format(short(base)) if base and all(i.startswith(base + "/") for i in items) else ": "
    return lead + ", ".join(shown) + more


def procedure_card(root, text, config, digest, pins, outside, previous, scripts):
    """The card for a plan whose table has Step and Choice or Validation columns, else None."""
    rows = plan_rows(text)
    if not rows:
        return None
    paths, commands = plan_grants(root, text, config)
    outputs = output_words(text)
    reads = sorted(pins) if pins else []
    words = set(plan_inputs(text) or []) | set(outputs or [])
    outside_prose = prose_only(root, text, config, words)
    prefix = shared_prefix(paths + (outputs or []) + reads + outside_prose)

    def short(path):
        if prefix and path == prefix:
            return "P"
        return "P/" + path[len(prefix) + 1:] if prefix and path.startswith(prefix + "/") else path

    def quote(cell, limit=CARD_CELL):
        return clean(prefix and cell.replace(prefix + "/", "P/") or cell, limit)

    pinned_lines, script_changes = script_state(root, scripts, config)
    changes = pin_changes(pins, previous) + script_changes
    defaults = [row["num"] for row in rows if row["source"].lower().startswith("default")]
    lines = ["mycelium-extra \u00b7 plan {} ready for approval".format(digest)]
    lines += changes
    lines += ["Question   " + card_question(text), "Goal       " + card_goal(text),
              "Defaults to confirm: " + ("step " + ", ".join(defaults) if defaults else "none")]
    facts = FACTS_LINE.search(text)
    if facts:
        lines.append(clean(facts.group(0), 160))
    lines += ["", "Procedure (choice [who decided], then the check)"]
    for row in rows[:CARD_STEPS]:
        cells = " ".join((row["step"], row["choice"], row["check"]))
        done = "  (agent says: done)" if DONE_MARK.search(cells) else ""
        step, choice, check = (quote(DONE_MARK.sub("", row[key]), 110 if key == "step" else CARD_CELL)
                               for key in ("step", "choice", "check"))
        source = "  [{}]".format(source_tag(row["source"])) if row["source"].strip() else ""
        if len(rows) > CARD_COMPACT:
            lines.append("{:>2}  {}{}  |  {}{}".format(row["num"], step, done, choice, source))
        else:
            lines += ["{:>2}  {}{}".format(row["num"], step, done), "    choice  " + choice + source]
        if check:
            lines.append("    check   " + check)
    if len(rows) > CARD_STEPS:
        lines.append("\u2026 and {} more steps in the plan above".format(len(rows) - CARD_STEPS))
    flags = evidence_flags(text)
    if flags:
        lines += ["", "From Evidence (flagged)"] + ["  - " + flag for flag in flags[:3]]
        if len(flags) > 3:
            lines.append("  (+{} more flagged in Evidence)".format(len(flags) - 3))
    lines += ["", "CAN RUN (in full)"]
    for path in paths:
        if os.path.isfile(os.path.join(root, path)) or SCRIPT_EXT.search(path):
            kind, note = ("script" if SCRIPT_EXT.search(path) else "file"), ("  pinned" if path in scripts else "")
        else:
            kind, note = "folder", "  (every gated file below it)"
        lines.append("  {:<9}{}{}".format(kind, short(path), note))
    lines += ["  {:<9}{}  (any invocation)".format("command", command) for command in commands]
    if not paths and not commands:
        lines.append("  nothing: the plan table names no gated script, folder, or command")
    lines.append("Reads " + ("{} pinned{}".format(len(reads), names(reads, short)) if reads else
                             ("none (no `Inputs:` line)" if pins is None else "none (the `Inputs:` line names no files)")))
    lines.append("Writes " + ("{}{}".format(len(outputs), names(outputs, short)) if outputs else
                              "none named (no `Outputs:` line)"))
    if outside:
        lines.append("Outside the repository, not pinned" + names(outside, str))
    if prefix:
        lines.append("P = " + prefix)
    if outside_prose:
        lines.append("In prose only, not authorised" + names(outside_prose, short))
    lines.append("\u25b6 approve plan {}".format(digest))
    return "\n".join(lines)


# ---------------------------------------------------------------- pinned inputs

def plan_inputs(text):
    """The words on a plan's `Inputs:` lines, or None when it has none."""
    lines = INPUTS_LINE.findall(text)
    if not lines:
        return None
    words = []
    for line in lines:
        for word in PATHLIKE.findall(line):
            word = word.rstrip(".,;:")
            if word.startswith("./"):
                word = word[2:]
            if word and word not in words:
                words.append(word)
    return words


def pin_inputs(root, text, config):
    """Return (pins, outside). pins maps repo paths to fingerprints; it is None
    when the plan has no `Inputs:` line. A word without a slash counts only if
    it names an existing file, so prose on the line is skipped."""
    words = plan_inputs(text)
    if words is None:
        return None, []
    budget = hash_budget(config)
    pins, outside = {}, []
    for word in words:
        rel = repo_relative(root, root, word)
        if rel is None:
            if "/" in word:
                outside.append(word)
            continue
        path = os.path.join(root, rel)
        if "/" not in word and not os.path.exists(path):
            continue
        pins[rel] = fingerprint(path, budget)
    return pins, outside


def pin_lines(pins, outside, previous):
    if pins is None:
        return ["  Inputs pinned: none (no `Inputs:` line)"]
    if pins:
        lines = ["  Inputs pinned"] + bullets("{} ({})".format(rel, method(pin)) for rel, pin in pins.items())
    else:
        lines = ["  Inputs pinned: none (the `Inputs:` line names no files)"]
    if outside:
        lines += ["  Outside the repository, not pinned"] + bullets(outside)
    return lines + pin_changes(pins, previous)


def pin_changes(pins, previous):
    old = (previous or {}).get("pins") or {}
    changed = [rel for rel, pin in (pins or {}).items() if rel in old and not unchanged(old[rel], pin)]
    return ["  Changed since this plan was last shown"] + bullets(changed) if changed else []


def changed_pins(root, pins, budget, cache):
    """Return (changes, unchecked) for one approval's pins."""
    changes, unchecked = [], []
    for rel, pin in pins.items():
        key = (rel, "sha256" in pin, pin.get("size"))
        if key not in cache:
            cache[key] = fingerprint(os.path.join(root, rel), budget, pin)
        now = cache[key]
        if pin.get("skipped") or now.get("skipped"):
            unchecked.append(rel)
        elif not unchanged(pin, now):
            changes.append("{}: {} -> {}".format(rel, describe(pin), describe(now)))
    return changes, unchecked


# ---------------------------------------------------------------- pinned scripts

def script_pinning(config):
    """(on, notice). Scripts are pinned unless gate.json sets `pin_scripts` to false;
    any other non-boolean value is ignored, with a notice."""
    value = config.get("pin_scripts", True)
    if isinstance(value, bool):
        return value, None
    return True, ('mycelium-extra gate: "pin_scripts" in gate.json must be true or false; '
                  "pinning scripts.")


def covered_scripts(root, text, config):
    """Existing script files the plan table names. A script under a folder it names, or
    one that does not exist yet, is pinned at its first run instead."""
    found = []
    for named in sorted(plan_paths_in(root, plan_table(text))):
        rel = gated_rel(root, root, named, config)
        if rel and SCRIPT_EXT.search(rel) and os.path.isfile(os.path.join(root, rel)):
            found.append(rel)
    return sorted(set(found))[:MAX_SCRIPT_PINS]


def keep_snapshot(root, rel, pin):
    """Copy a pinned script under its sha256, so a later change can be shown as a diff."""
    digest = pin.get("sha256")
    target = state_path(root, "scripts", digest or "-")
    if not digest or pin.get("size", 0) > MAX_SNAPSHOT or os.path.exists(target):
        return
    data = script_text(os.path.join(root, rel))
    if data is not None and len(data) <= MAX_SNAPSHOT and sha256(data).hexdigest() == digest:
        # (the file may have changed since it was hashed)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target + ".tmp", "wb") as handle:
            handle.write(data)
        os.replace(target + ".tmp", target)


def pin_scripts(root, text, config):
    """Fingerprint (and snapshot) each existing script the plan covers."""
    budget = hash_budget(config)
    pins = {}
    for rel in covered_scripts(root, text, config):
        pins[rel] = fingerprint(os.path.join(root, rel), budget)
        keep_snapshot(root, rel, pins[rel])
    return pins


def script_diff(root, rel, pin):
    """The diff from a pinned script to the file now, as a list of lines; None when
    the pinned version was not kept (over the size limit, or only size and mtime were pinned)."""
    try:
        with open(state_path(root, "scripts", pin.get("sha256") or "-"), "rb") as handle:
            old = handle.read()
    except OSError:
        return None
    new = script_text(os.path.join(root, rel))
    if new is None or len(new) > MAX_SNAPSHOT:
        return None
    import difflib  # here, not at the top: most hook calls never diff
    return list(difflib.unified_diff(old.decode("utf-8", "replace").splitlines(),
                                     new.decode("utf-8", "replace").splitlines(),
                                     "pinned", "now", lineterm="", n=0))


def diff_counts(diff):
    return (sum(1 for line in diff if line.startswith("+") and not line.startswith("+++")),
            sum(1 for line in diff if line.startswith("-") and not line.startswith("---")))


def script_change(root, rel, pin, budget, cache):
    """Return (change, skipped): how a pinned script differs now, as text with its diff size."""
    changes, skipped = changed_pins(root, {rel: pin}, budget, cache)
    if not changes:
        return None, bool(skipped)
    diff = script_diff(root, rel, pin)
    return changes[0] + (" (+{} -{} lines)".format(*diff_counts(diff)) if diff is not None else ""), False


def approved_script(root, approvals, rel):
    """The pin of a script in the newest active approval that has one."""
    for record in sorted(approvals or [], key=lambda r: r.get("approved_at", 0), reverse=True):
        pin = (record.get("scripts") or {}).get(rel) or read_json(
            state_path(root, "script-pins", record.get("hash", "-") + ".json"), {}).get(rel)
        if pin:
            return pin
    return None


def script_lines(root, scripts, config):
    """The approval card's script section: what is pinned and what changed since a plan approved it."""
    pinned, changed = script_state(root, scripts, config)
    return pinned + changed


def script_state(root, scripts, config):
    """(pinned lines, changed lines) of the scripts section."""
    approvals = active_approvals(root, config)
    now_all = dict(scripts or {})
    for record in approvals or []:  # scripts pinned at a first run, still on disk
        for rel in read_json(state_path(root, "script-pins", record.get("hash", "-") + ".json"), {}):
            if rel not in now_all and os.path.isfile(os.path.join(root, rel)):
                now_all[rel] = fingerprint(os.path.join(root, rel), hash_budget(config))
    if not now_all:
        return [], []
    lines = (["  Scripts pinned"] + bullets("{} ({})".format(rel, method(pin))
                                           for rel, pin in scripts.items())) if scripts else []
    changed, diff_text = [], []
    for rel, now in now_all.items():
        old = approved_script(root, approvals, rel)
        if old and not unchanged(old, now):
            diff = script_diff(root, rel, old)
            counts = " (+{} -{} lines)".format(*diff_counts(diff)) if diff is not None else ""
            changed.append("{}: {} -> {}{}".format(rel, describe(old), describe(now), counts))
            diff_text += ["      " + line for line in (diff or []) if not line.startswith(("---", "+++"))]
    after = []
    if changed:
        after += ["  Scripts changed since last approved"] + bullets(changed)
        after += diff_text[:DIFF_LINES]
        if len(diff_text) > DIFF_LINES:
            after.append("      \u2026 and {} more diff lines".format(len(diff_text) - DIFF_LINES))
    return lines, after


def note_first_runs(root, firsts, budget):
    """Pin scripts that did not exist when their plan was shown, at the run that first uses them."""
    ledgers = {}
    for digest, rel in firsts:
        ledger = ledgers.setdefault(digest, read_json(state_path(root, "script-pins", digest + ".json"), {}))
        if rel not in ledger:
            ledger[rel] = fingerprint(os.path.join(root, rel), budget)
            keep_snapshot(root, rel, ledger[rel])
    for digest, ledger in ledgers.items():
        write_json(state_path(root, "script-pins", digest + ".json"), ledger)


# ---------------------------------------------------------------- events

def on_tool(event, root, config):
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    state = os.path.realpath(state_path(root))
    if tool == "apply_patch":
        targets = re.findall(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$",
                             tool_input.get("command", ""), re.M)
        for target in targets:
            target = os.path.realpath(os.path.join(event.get("cwd") or root, target.strip()))
            if target == state or target.startswith(state + os.sep):
                return deny("mycelium-extra: {} is gate state. Only the user's approval "
                            "and the gate's hooks write there.".format(os.path.relpath(target, root)))
        return None
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        target = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        target = os.path.realpath(os.path.join(event.get("cwd") or root, target))
        if target == state or target.startswith(state + os.sep):
            return deny("mycelium-extra: {} is gate state. Only the user's approval "
                        "(typing `approve plan <hash>`) and the gate's hooks write there.".format(
                            os.path.relpath(target, root)))
        return None
    if tool != "Bash":
        return None
    command = tool_input.get("command", "")
    if writes_state(command, root, event.get("cwd") or root):
        return deny("mycelium-extra: this command appears to modify {}/, which holds gate state. "
                    "Reading it is fine; changing it is the user's call.".format(STATE_DIR))
    approvals = None
    blocked, stale, unchecked = [], [], []
    stale_scripts, firsts = [], []
    scripts_on, notice = script_pinning(config)
    budget, cache = hash_budget(config), {}
    granted = explore_granted(root, event.get("session_id"))
    for explore, label, paths, segment, _, _ in analyse_command(command, root, event.get("cwd") or root,
                                                                 config):
        if explore and granted:
            log_explore(root, event, segment, paths)
            continue
        if explore:
            return deny("mycelium-extra gate: the exploratory-run prefix works only after the user "
                        "types `allow explore` in this session, and they have not. Do not work "
                        "around this block; ask the user.")
        if approvals is None:
            approvals = active_approvals(root, config)
            if approvals is None:
                return deny(SCAN_TIMEOUT)
        records = covering(root, label, paths, approvals)
        if not records:
            blocked.append((label, paths))
            continue
        # The newest covering plan is the current intent: an older approval that pinned
        # less (or nothing) must not let a run through after the newer plan's pins changed.
        newest = records[-1]
        changes, skipped = changed_pins(root, newest.get("pins") or {}, budget, cache)
        if changes:
            stale.append((newest["hash"], changes))
        else:
            unchecked += [rel for rel in skipped if rel not in unchecked]
        changed_scripts = []
        for rel in paths if scripts_on else []:
            if not os.path.isfile(os.path.join(root, rel)):
                continue
            pin = (newest.get("scripts") or {}).get(rel) or read_json(
                state_path(root, "script-pins", newest["hash"] + ".json"), {}).get(rel)
            if not pin:
                firsts.append((newest["hash"], rel))
                continue
            change, skipped_script = script_change(root, rel, pin, budget, cache)
            if change:
                changed_scripts.append(change)
            elif skipped_script and rel not in unchecked:
                unchecked.append(rel)
        if changed_scripts:
            stale_scripts.append((newest["hash"], changed_scripts))
    if (stale or stale_scripts) and not blocked:
        lines = []
        for digest, changes in stale:
            lines.append("mycelium-extra gate: blocked because inputs pinned by plan {} changed after "
                         "the plan was written:".format(digest))
            lines.extend("  - " + change for change in changes)
        if stale:
            lines.append("Re-check these inputs (for example, re-run the plan's data-contract check) and "
                         "present the plan again; the user approves the new pins with `approve plan <hash>`. "
                         "Do not work around this block.")
        for digest, changes in stale_scripts:
            lines.append("mycelium-extra gate: blocked because scripts pinned under plan {} changed "
                         "since it was approved or first run:".format(digest))
            lines.extend("  - " + change for change in changes)
        if stale_scripts:
            lines.append("The user reviews the change and re-approves: present the plan again, and they "
                         "approve it with `approve plan <hash>`. Do not work around this block.")
        return deny("\n".join(lines))
    if not blocked:
        note_first_runs(root, firsts, budget)
        messages = []
        if unchecked:  # fail open, but say so
            messages.append("mycelium-extra gate: pinned inputs not re-checked before this run "
                            "(time limit, `pin_seconds`): {}.".format(listing(unchecked)))
        if notice and approvals is not None:  # a gated run was checked
            messages.append(notice)
        return {"systemMessage": "\n".join(messages)} if messages else None
    hashes = ", ".join(r["hash"] for r in approvals) or "none"
    lines = ["mycelium-extra gate: blocked because no active approved plan covers this run."]
    for label, paths in blocked:
        lines.append("  - {}{}".format(label, (" " + ", ".join(paths)) if paths else ""))
    lines.append("Active approved plans (last {} h): {}.".format(config["approval_hours"], hashes))
    lines.append("Present a plan whose plan table names these paths (prose, Evidence, and Source "
                 "citations do not count) and that ends with the grill status line; "
                 "the user approves it by typing `approve plan <hash>`. Do not work around this "
                 "block; if the user wants an exploratory run instead, they will say so.")
    return deny("\n".join(lines))


SCAN_TIMEOUT = (
    "mycelium-extra gate: blocked because reading {}/approvals/ took longer than {} s, so the gate "
    "cannot tell whether an approved plan covers this run. This happens when that folder holds very "
    "many files or sits on a slow filesystem. The user can move approvals they no longer need to "
    "verify out of it. Do not work around this block.".format(STATE_DIR, SCAN_SECONDS))


def deny(reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def grant_path(root, session_id):
    return state_path(root, "explore-grants", safe_session(session_id) + ".json")


def explore_granted(root, session_id):
    return os.path.isfile(grant_path(root, session_id))


def log_explore(root, event, segment, paths):
    append_line(state_path(root, "explore.log"), {"ts": time.time(), "session_id": event.get("session_id"),
                                                  "command": segment, "paths": paths})


def hints_on(root):
    return os.path.isfile(state_path(root, "hints.json"))


def prompt_hint(prompt, root, config):
    if not hints_on(root) or prompt.lstrip().startswith("/") or "mycelium" in prompt.lower():
        return None
    for pattern, command, condition in PROMPT_HINTS:
        if not pattern.search(prompt):
            continue
        if condition == "living" and not os.path.isdir(os.path.join(root, ".living")):
            continue
        if condition == "unplanned" and active_approvals(root, config) != []:
            continue
        return {"systemMessage": "mycelium-extra hint: this fits {}".format(command),
                "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": (
                    "mycelium-extra hint: this request fits `{}`. Name it to the user in one line and ask "
                    "before switching to it; do not invoke it unasked.".format(command))}}
    return None


def context_tokens(transcript):
    """Context size from the last main-thread usage record in the transcript, or 0."""
    try:
        with open(transcript, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            handle.seek(max(0, handle.tell() - 262144))
            lines = handle.read().decode("utf-8", "replace").splitlines()
    except (OSError, TypeError):
        return 0
    for line in reversed(lines):
        if '"usage"' not in line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        usage = (record.get("message") or {}).get("usage") if isinstance(record, dict) else None
        if usage and not record.get("isSidechain"):
            total = sum(usage.get(key) or 0 for key in (
                "input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            if total:  # some records carry all-zero usage
                return total
    return 0


def stop_hints(root, event):
    """Next-command hints at turn end, each shown once per session; user-only."""
    session_id = event.get("session_id")
    marker = state_path(root, "pending", safe_session(session_id) + ".hints.json")
    shown = read_json(marker, {"verify": [], "handoff": False})
    hints = []
    log = state_path(root, "receipts.jsonl")
    needle = json.dumps(session_id)[1:-1] if isinstance(session_id, str) else ""
    plans = []
    if os.path.isfile(log):
        with open(log, encoding="utf-8") as handle:
            for line in handle:
                if needle not in line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if record.get("session_id") == session_id and not record.get("explore"):
                    plans += [p for p in record.get("plans", []) if p not in plans]
    for digest in plans:
        if digest not in shown["verify"]:
            shown["verify"].append(digest)
            hints.append("mycelium-extra hint: next, `/mycelium-extra:verify {}`".format(digest))
    if not shown["handoff"] and context_tokens(event.get("transcript_path")) >= HANDOFF_TOKENS:
        shown["handoff"] = True
        hints.append("mycelium-extra hint: context is large; next, `/mycelium-extra:handoff`, then /clear")
    if hints:
        write_json(marker, shown)
    return hints


def on_prompt(event, root, config):
    prompt = event.get("prompt") or ""
    toggle = HINTS_TOGGLE.match(prompt)
    if toggle:
        path = state_path(root, "hints.json")
        if toggle.group(1).lower() == "on":
            write_json(path, {"on_at": time.time()})
            message = ("mycelium-extra: command hints on for this repository. "
                       "`hints off` turns them off.")
        else:
            if os.path.isfile(path):
                os.remove(path)
            message = "mycelium-extra: command hints off for this repository."
        return {"systemMessage": message,
                "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": message}}
    grant = EXPLORE_GRANT.match(prompt)
    if grant:
        path = grant_path(root, event.get("session_id"))
        if grant.group(1).lower() == "allow":
            write_json(path, {"granted_at": time.time(), "session_id": event.get("session_id")})
            message = ("mycelium-extra: exploratory runs allowed for this session. Prefix a gated run "
                       "with {}=1; each one is logged and listed as not reportable. "
                       "`stop explore` ends this.".format(EXPLORE_VAR))
        else:
            if os.path.isfile(path):
                os.remove(path)
            message = "mycelium-extra: exploratory runs are no longer allowed in this session."
        return {"systemMessage": message,
                "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": message}}
    match = APPROVE.match(prompt)
    session = safe_session(event.get("session_id"))
    pending = read_json(state_path(root, "pending", session + ".json"), [])
    known = ", ".join(p["hash"] for p in pending) or "none"
    if not match:
        if re.search(r"\bapprove plan\b", prompt, re.IGNORECASE) and len(prompt) < 200:
            message = ("mycelium-extra: nothing approved. To approve, send only `approve plan <hash>` "
                       "(pending in this session: {}).".format(known))
            return {"systemMessage": message}
        return prompt_hint(prompt, root, config)
    if match.group(1) is None:
        message = "mycelium-extra: pending plans in this session: {}. Nothing was approved.".format(known)
        return {"systemMessage": message,
                "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": message}}
    wanted = match.group(1).lower()
    plan = next((p for p in pending if p["hash"] == wanted), None)
    if plan is None:
        message = ("mycelium-extra: no pending plan {} in this session (pending: {}). "
                   "Nothing was approved.".format(wanted, known))
    else:
        pins = plan.get("pins") or {}
        scripts = plan.get("scripts") or {}
        record = {"hash": wanted, "approved_at": time.time(), "session_id": event.get("session_id"),
                  "plan": plan["text"], "pins": pins, "scripts": scripts}
        write_json(state_path(root, "approvals", wanted + ".json"), record)
        ledger = state_path(root, "script-pins", wanted + ".json")  # approving again re-baselines
        if os.path.isfile(ledger):
            os.remove(ledger)
        message = ("mycelium-extra: plan {} approved. Gated runs whose paths appear in that plan "
                   "may run for {} h. {}{}".format(
                       wanted, config["approval_hours"],
                       "Pinned inputs: {}.".format(listing(pins)) if pins else "No inputs pinned.",
                       " Pinned scripts: {}.".format(listing(scripts)) if scripts else ""))
    return {"systemMessage": message,
            "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": message}}


def on_stop(event, root, config):
    notices = []
    text = (event.get("last_assistant_message") or "").strip()
    status = PLAN_STATUS.search(text)
    if status and status.group(1).upper() != "DECISION_REQUIRED":
        digest = sha256(text.encode("utf-8")).hexdigest()[:8]
        session = safe_session(event.get("session_id"))
        path = state_path(root, "pending", session + ".json")
        pending = read_json(path, [])
        previous = next((p for p in pending if p["hash"] == digest), None)
        pending = [p for p in pending if p["hash"] != digest]
        entry = {"hash": digest, "ts": time.time(), "text": text, "pins": {}}
        pending.append(entry)
        write_json(path, pending[-10:])  # a timeout while pinning still leaves the plan approvable
        pins, outside = pin_inputs(root, text, config)
        entry["pins"] = pins or {}
        scripts_on, notice = script_pinning(config)
        entry["scripts"] = pin_scripts(root, text, config) if scripts_on else {}
        write_json(path, pending[-10:])
        notices.append(approval_card(root, text, config, digest, pins, outside, previous, entry["scripts"]))
        if notice:
            notices.append(notice)
    fresh = new_explore_runs(root, event.get("session_id"))
    if fresh:
        counts = collections.OrderedDict()
        for command in fresh:
            counts[command] = counts.get(command, 0) + 1
        listed = [c + (" ({} runs)".format(n) if n > 1 else "") for c, n in counts.items()]
        notices.append("mycelium-extra: {} exploratory run(s) this session are not reportable: {}. "
                       "Say \"promote explore runs\" to plan a reportable re-run.".format(
                           len(fresh), "; ".join(listed[:5]) + (" ..." if len(listed) > 5 else "")))
    if hints_on(root):
        notices += stop_hints(root, event)
    return {"systemMessage": "\n\n".join(notices)} if notices else None


def new_explore_runs(root, session_id):
    log = state_path(root, "explore.log")
    if not os.path.isfile(log):
        return []
    marker = state_path(root, "pending", safe_session(session_id) + ".explore-seen")
    seen = read_json(marker, 0)
    runs = []
    # Skip other sessions' lines unparsed; the id is matched as JSON writes it.
    needle = json.dumps(session_id)[1:-1] if isinstance(session_id, str) else ""
    with open(log, encoding="utf-8") as handle:
        for line in handle:
            if needle not in line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if record.get("session_id") == session_id:
                runs.append(record["command"])
    if len(runs) > seen:
        write_json(marker, len(runs))
    return runs[seen:]


# ---------------------------------------------------------------- run receipts

def on_post(event, root, config):
    if event.get("tool_name") != "Bash":
        return None
    command = (event.get("tool_input") or {}).get("command", "")
    runs = list(analyse_command(command, root, event.get("cwd") or root, config))
    if not runs:
        return None
    wrapped = set()  # an `sbatch --wrap` payload was submitted, not run here
    for run in runs:
        if run[1] == "sbatch":
            for payload in flag_values(after_word(run[4], "sbatch"), ("--wrap",)):
                wrapped.update(" ".join(tokens) for tokens in segments(payload))
    runs = [run for run in runs if run[1] == "sbatch" or run[3] not in wrapped]
    response = event.get("tool_response")
    output = response_text(response)
    status, source, extra = exit_status(event)
    approvals = active_approvals(root, config)
    budget = hash_budget(config)
    git = git_state(root)
    unread = approvals is None
    notes = ["approvals not read (time limit), so no plan is credited"] if unread else []
    approvals = approvals or []
    planned = []
    for explore, label, paths, segment, tokens, cwd in runs:
        records = covering(root, label, paths, approvals)
        wrapped_paths = []  # the gated scripts an `sbatch --wrap` payload runs, from the job's folder
        if label == "sbatch":
            for payload in flag_values(after_word(tokens, "sbatch"), ("--wrap",)):
                for inner in analyse_command(payload, root, job_cwd(tokens, cwd), config):
                    wrapped_paths += [p for p in inner[2] if p not in paths + wrapped_paths]
        if wrapped_paths:  # a plan is credited with the job only if it also names what the job runs
            records = [r for r in records
                       if all(path_in_plan(root, p, plan_table(r.get("plan", ""))) for p in wrapped_paths)]
        paths = paths + wrapped_paths
        if records and not explore and records[-1]["hash"] not in planned:
            planned.append(records[-1]["hash"])
        receipt = {
            "schema": "mycelium-extra.receipt.v1",
            "ts": time.time(),
            "session_id": event.get("session_id"),
            "cwd": repo_relative(root, root, cwd) or ".",
            "command": segment,
            "kind": label,
            "paths": paths,
            "explore": explore,
            "plans": [record["hash"] for record in records],
            "pins": (records[-1].get("pins") or {}) if records else {},
            "pins_checked": bool(records) and not explore,
            "git": git,
            "hook_env": {key: os.environ[key] for key in HOOK_ENV if os.environ.get(key)},
            "command_env": command_env(tokens),
            "exit_status": status,
            "exit_source": source,
            "response_keys": sorted(response) if isinstance(response, dict) else type(response).__name__,
        }
        receipt.update(extra)
        if event.get("host"):
            receipt["host"] = event["host"]
        if unread:
            receipt["approvals_unread"] = True
        receipt.update(launch_details(root, cwd, label, paths, tokens, output, budget))
        add_git_states(root, receipt, git is not None)
        append_line(state_path(root, "receipts.jsonl"), receipt)
        what = "{} job {}".format(label, receipt["job_id"]) if receipt.get("job_id") else label
        notes.append("{} ({})".format(what, "plan " + receipt["plans"][-1] if records
                                      else "explore run" if explore else "no approved plan"))
    result = {"systemMessage": "mycelium-extra: run receipt recorded: {}.".format("; ".join(notes))}
    context = []
    unseen = sorted({run[1] for run in runs if not MYCELIUM_SEES.match(run[1])})
    if unseen and os.path.isdir(os.path.join(root, ".living")):
        # Mycelium's own hooks detect only python, R and jupyter runs, so they stay silent here.
        context.append(
            "mycelium-extra: Mycelium's post-action protocol did not fire for this {} run (its hooks "
            "detect only python, R, and jupyter). Once the run has finished (check its log or job "
            "status), follow that protocol: learnings, decisions, findings, the manifest, and the "
            "analysis doc.".format(", ".join(unseen)))
    if any(run[0] for run in runs):
        # Mycelium's post-action protocol asks for findings after any run; keep this one out of results.
        context.append(
            "mycelium-extra: that was an exploratory run, not reportable. If you record a learning or "
            "finding from it (for example under Mycelium's post-action protocol), label it "
            "`Exploratory run (not reportable)`, and do not cite its outputs as results.")
    if planned and os.path.isdir(os.path.join(root, ".living")):
        # Mycelium parses only the ledger's date cell, so the Run/Session and Result cells can carry
        # the plan and the provenance tag (D7).
        context.append(
            "mycelium-extra: if you record a finding from this run, write its Evidence Ledger "
            "Run/Session cell as {}, so `verify stale` can link the finding to its plan, and end its "
            "Result cell with `[agent-derived: <output path>]`.".format(
                " or ".join("`{}; plan {}`".format(event.get("session_id"), digest) for digest in planned)))
    if context:
        result["hookSpecificOutput"] = {"hookEventName": event.get("hook_event_name") or "PostToolUse",
                                        "additionalContext": "\n\n".join(context)}
    return result


def response_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(response_text(v) for v in value.values())
    if isinstance(value, list):
        return "\n".join(response_text(v) for v in value)
    return ""


EXIT_LINE = re.compile(r"Exit code (-?[0-9]+)\s*$")
FAILED_LINE_MAX = 200  # the receipt keeps the error's first line only, cut to this length


def exit_status(event):
    """(status, source, extra receipt fields) for a Bash hook event. A missing status is never
    read as success.

    An integer exit code in the tool response wins (source "response"). Otherwise the event
    decides: PostToolUse runs only after a tool completes successfully, so a foreground run
    gets 0 (source "event"), but a run started with run_in_background has only started, and an
    interrupted result was cut off. PostToolUseFailure's `error` starts with `Exit code N` when
    the command ran and exited (source "error"); with no such line the shell did not start or
    Claude Code stopped it ("failed"), and is_interrupt marks an abort ("interrupted"). Only
    the error's first line is kept, never its output. Any other payload (no hook_event_name,
    an older Claude Code or another host) is "unknown"."""
    response = event.get("tool_response")
    found = exit_code_in(response)
    if found is not None:
        return found, "response", {}
    if event.get("host") == "codex":
        # Codex posts completed shell results, including failures. No code is a gap.
        return "unknown", None, {}
    name = event.get("hook_event_name")
    if name == "PostToolUse":
        tool_input = event.get("tool_input") or {}
        if tool_input.get("run_in_background") is True or (
                isinstance(response, dict) and response.get("backgroundTaskId")):
            return "unknown", None, {"background": True}
        if isinstance(response, dict) and response.get("interrupted") is True:
            return "interrupted", "event", {}
        return 0, "event", {}
    if name == "PostToolUseFailure":
        error = event.get("error")
        first = error.strip().split("\n", 1)[0].strip() if isinstance(error, str) else ""
        extra = {"error_line": first[:FAILED_LINE_MAX]} if first else {}
        if event.get("is_interrupt") is True:
            return "interrupted", "event", extra
        match = EXIT_LINE.match(first)
        if match and int(match.group(1)) != 0:  # a failure event is never read as success
            return int(match.group(1)), "error", extra
        return "failed", "event", extra
    return "unknown", None, {}


def exit_code_in(response):
    """Best effort: Claude Code's Bash result shape is not documented."""
    if isinstance(response, dict):
        for key in ("exit_code", "exitCode", "return_code", "returncode"):
            if isinstance(response.get(key), int) and not isinstance(response.get(key), bool):
                return response[key]
        for value in response.values():
            found = exit_code_in(value) if isinstance(value, dict) else None
            if found is not None:
                return found
    return None


def git(root, *args):
    import subprocess  # here, not at the top (~20 ms); outside the try, which names it
    try:
        proc = subprocess.run(("git", "-C", root) + args, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT,
                              env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"))
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def git_state(root):
    head = git(root, "rev-parse", "HEAD")
    if head is None:
        return None
    status = git(root, "status", "--porcelain", "--untracked-files=no")
    return {"head": head.strip(), "dirty": None if status is None else bool(status.strip())}


def add_git_states(root, receipt, in_git):
    """Mark each file record inside the repository committed, modified, untracked, or ignored."""
    records = [receipt.get("script")] + receipt.get("lockfiles", [])
    records += (receipt.get("engine") or {}).get("files", [])
    records = [r for r in records if r and r.get("in_repo") and not r.get("missing")]
    if not in_git or not records:
        return
    out = git(root, "status", "--porcelain", "--ignored", "--", *[r["path"] for r in records])
    if out is None:
        return
    states = []
    for line in out.splitlines():
        name = line[3:].strip('"').split(" -> ")[-1]
        states.append((name, {"??": "untracked", "!!": "ignored"}.get(line[:2], "modified")))
    for record in records:
        record["git"] = "committed"
        for name, state in states:
            if record["path"] == name.rstrip("/") or (name.endswith("/") and record["path"].startswith(name)):
                record["git"] = state


def file_record(root, cwd, token, budget):
    path = os.path.normpath(os.path.join(cwd, os.path.expanduser(token)))
    rel = repo_relative(root, cwd, token)
    record = {"path": rel or path, "in_repo": rel is not None}
    record.update(fingerprint(path, budget))
    return record


def flag_values(args, flags, many=False):
    values = []
    for j, token in enumerate(args):
        if token in flags and j + 1 < len(args) and not args[j + 1].startswith("-"):
            values.append(args[j + 1])
            k = j + 2
            while many and k < len(args) and not args[k].startswith("-"):
                values.append(args[k])
                k += 1
        elif "=" in token and token.split("=", 1)[0] in flags:
            values.append(token.split("=", 1)[1])
    return values


def optional_flag(args, flag):
    """A flag with an optional value: its value, True if bare, or None if absent."""
    if flag not in args:
        return None
    j = args.index(flag)
    return args[j + 1] if j + 1 < len(args) and not args[j + 1].startswith("-") else True


def after_word(tokens, word):
    for j, token in enumerate(tokens):
        if os.path.basename(token) == word:
            return tokens[j + 1:]
    return []


def command_env(tokens):
    for j, token in enumerate(tokens[:-1]):
        manager = os.path.basename(token)
        if manager in ("conda", "mamba", "micromamba", "pixi") and tokens[j + 1] == "run":
            names = flag_values(tokens[j + 2:], ("-n", "--name", "-p", "--prefix", "-e", "--environment"))
            return {"manager": manager, "env": names[0] if names else None}
    return None


def job_lines(text):
    env, sbatch = [], []
    for line in text.replace(";", "\n").splitlines():
        if line.startswith("#SBATCH") and len(sbatch) < 20:
            sbatch.append(line.strip()[:200])
        elif ENV_LINE.match(line) and len(env) < 20:
            env.append(line.strip()[:200])
    return env, sbatch


def launch_details(root, cwd, label, paths, tokens, output, budget):
    """The script, declared environment, lockfiles, and engine record of one run."""
    args = after_word(tokens, label) if label in ("sbatch", "snakemake", "nextflow") else tokens
    details, script, base, job_text = {}, None, cwd, ""
    if label == "sbatch":
        wraps = flag_values(args, ("--wrap",))
        if wraps:
            job_text = wraps[0]
            details["wrap_sha256"] = sha256(job_text.encode("utf-8")).hexdigest()
        if job_cwd(tokens, cwd) != cwd:
            details["job_cwd"] = repo_relative(root, root, job_cwd(tokens, cwd)) or job_cwd(tokens, cwd)
        else:
            takes_path = ("-o", "-e", "-i", "--output", "--error", "--input", "-D", "--chdir")
            for j, token in enumerate(args):
                if not token.startswith("-") and (j == 0 or args[j - 1] not in takes_path) \
                        and os.path.isfile(os.path.join(cwd, os.path.expanduser(token))):
                    script = token
                    break
        match = JOB_ID.search(output) or ("--parsable" in args and PARSABLE_ID.search(output)) or None
        details["job_id"] = match.group(1) if match else None
    elif label == "snakemake":
        given = flag_values(args, ("-s", "--snakefile"))
        workdir = (flag_values(args, ("-d", "--directory")) or ["."])[0]
        defaults = [p for p in ("Snakefile", "workflow/Snakefile")
                    if os.path.isfile(os.path.join(cwd, workdir, p))]
        script = given[0] if given else (os.path.join(workdir, defaults[0]) if defaults else None)
        files = [file_record(root, cwd, value, budget)
                 for value in flag_values(args, ("--configfile", "--configfiles"), many=True)]
        details["engine"] = {"configfiles": [f["path"] for f in files], "files": files,
                             "report": (flag_values(args, ("--report",)) or [None])[0],
                             "profile": (flag_values(args, ("--profile",)) or [None])[0],
                             "record": os.path.normpath(os.path.join(workdir, ".snakemake", "metadata"))}
    elif label == "nextflow":
        run_args = after_word(args, "run")
        pipeline = next((t for t in run_args if not t.startswith("-")), None)
        if pipeline and os.path.isfile(os.path.join(cwd, pipeline)):
            script = pipeline
        files = [file_record(root, cwd, value, budget)
                 for value in flag_values(args, ("-params-file", "-c", "-config"))]
        named = NF_RUN_NAME.search(output)
        details["engine"] = {"pipeline": pipeline, "files": files,
                             "revision": (flag_values(args, ("-r", "-revision")) or [None])[0],
                             "profile": (flag_values(args, ("-profile",)) or [None])[0],
                             "resume": "-resume" in args,
                             "run_name": named.group(1) if named else (flag_values(args, ("-name",)) or [None])[0],
                             "trace": optional_flag(args, "-with-trace"),
                             "report": optional_flag(args, "-with-report"),
                             "record": ".nextflow/history"}
    elif paths:
        script, base = paths[0], root
    if script:
        record = details["script"] = file_record(root, base, script, budget)
        full = os.path.join(root, record["path"]) if record["in_repo"] else record["path"]
        try:
            if os.path.isfile(full) and os.path.getsize(full) <= 1 << 20:
                with open(full, encoding="utf-8", errors="replace") as handle:
                    job_text = handle.read()
        except OSError:
            pass
    details["env_lines"], details["sbatch_lines"] = job_lines(job_text)
    folders = [root, cwd]
    if details.get("script", {}).get("in_repo"):
        folders.append(os.path.dirname(os.path.join(root, details["script"]["path"])))
    seen, lockfiles = set(), []
    for folder in folders:
        for name in LOCKFILES:
            full = os.path.realpath(os.path.join(folder, name))
            if full not in seen and os.path.isfile(full):
                seen.add(full)
                lockfiles.append(file_record(root, root, os.path.join(folder, name), budget))
    details["lockfiles"] = lockfiles
    return details


HANDLERS = {"tool": on_tool, "prompt": on_prompt, "stop": on_stop, "post": on_post}


def main(argv, text=None):
    """`text` is the event when gate_run.py has already read stdin."""
    if len(argv) != 2 or argv[1] not in HANDLERS:
        print("usage: gate.py stop|prompt|tool|post", file=sys.stderr)
        return 0
    try:
        event = json.loads(text if text is not None else sys.stdin.buffer.read().decode("utf-8", "replace"))
        root = find_root(event.get("cwd") or os.getcwd())
        if root is None:
            return 0
        emit(HANDLERS[argv[1]](event, root, load_config(root)))
    except Exception as error:  # fail open, but tell the user the gate broke
        emit({"systemMessage": "mycelium-extra gate error ({}): {}; the gate did not run.".format(
            argv[1], error)})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
