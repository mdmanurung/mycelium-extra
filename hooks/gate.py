"""mycelium-extra plan-approval gate for Claude Code, Codex, and OpenCode hooks.

Usage (from hooks/hooks.json): gate.py stop | prompt | tool | post
Reads the hook JSON on stdin. Stdlib-only; runs on Python 3.9+.

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
import contextlib
import fnmatch
import functools
import glob
import importlib.util
import json
import math
import os
import posixpath
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
    "lint_before_run": False,
    "lint_before_stop": False,
}
SCAN_SECONDS = 5  # reading approvals; the PreToolUse hook is killed at 10 s
LAUNCH_SECONDS = 24 * 3600  # a launch record older than this belongs to a call that never reported back
EXPLORE_VAR = "MYCELIUM_EXTRA_EXPLORE"
APPROVE = re.compile(r"^\s*approve plan(?: ([0-9a-f]{8})(?: +(\d{1,4}))?)?\s*[.!]?\s*$", re.IGNORECASE)
EXPLORE_GRANT = re.compile(r"^\s*(allow|stop) explore(?: ([0-9a-f]{8}))?\s*[.!]?\s*$", re.IGNORECASE)
SEND_PACKET = re.compile(r"send packet ([0-9a-f]{12,64})")  # no looser than review_packet.py's consent check
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
# Value options of the wrappers that precede a command, and the ones that move the command's
# folder; `classify` skips an option's value instead of mistaking it for the command.
_CONDA_OPTIONS = ({"-n", "--name", "-p", "--prefix", "-r", "--root-prefix", "-a", "--attach", "--label",
                   "-e", "--environment", "--manifest-path", "--config", "--cwd"}, {"--cwd"})
WRAPPER_OPTIONS = {
    "env": ({"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}, {"-C", "--chdir"}),
    "srun": (VALUE_FLAGS | {"-D", "--chdir"}, {"-D", "--chdir"}),
    "conda": _CONDA_OPTIONS, "mamba": _CONDA_OPTIONS, "micromamba": _CONDA_OPTIONS, "pixi": _CONDA_OPTIONS,
    "uv": ({"--extra", "--no-extra", "--group", "--no-group", "--only-group", "--env-file", "-w", "--with",
            "--with-editable", "--with-requirements", "--package", "--python-platform", "--index",
            "--default-index", "-i", "--index-url", "--extra-index-url", "-f", "--find-links",
            "--index-strategy", "--keyring-provider", "-P", "--upgrade-package", "--upgrade-group",
            "--resolution", "--prerelease", "--fork-strategy", "--exclude-newer", "--exclude-newer-package",
            "--no-sources-package", "--reinstall-package", "--link-mode", "-C", "--config-setting",
            "--config-settings-package", "--no-build-isolation-package", "--no-build-package",
            "--no-binary-package", "--cache-dir", "--refresh-package", "-p", "--python", "--color",
            "--allow-insecure-host", "--directory", "--project", "--config-file"}, {"--directory"}),
}
# Flags of the wrappers that take no value, so the word after one is the command, not its value.
_CONDA_FLAGS = {"-v", "--verbose", "--dev", "--debug-wrapper-scripts", "--no-capture-output",
                "--live-stream", "-h", "--help"}
WRAPPER_FLAGS = {
    "env": {"-i", "--ignore-environment", "-0", "--null", "-v", "--debug", "-h", "--help"},
    "srun": {"-v", "-q", "--quiet", "-O", "--overcommit", "-s", "--oversubscribe", "-u", "--unbuffered",
             "-k", "--no-kill", "-l", "--label", "-Q", "--exact", "--exclusive", "--overlap", "--pty",
             "--contiguous", "--help", "--usage", "--verbose"},
    "conda": _CONDA_FLAGS, "mamba": _CONDA_FLAGS, "micromamba": _CONDA_FLAGS, "pixi": _CONDA_FLAGS,
    "uv": {"--all-extras", "--no-dev", "--no-default-groups", "--all-groups", "--dev", "-m", "--module",
           "--only-dev", "--no-editable", "--exact", "--inexact", "--no-env-file", "--isolated", "--active",
           "--no-sync", "--locked", "--frozen", "-s", "--script", "--gui-script", "--all-packages",
           "--no-project", "--no-index", "-U", "--upgrade", "--no-sources", "--reinstall",
           "--compile-bytecode", "--no-build-isolation", "--no-build", "--no-binary", "-n", "--no-cache",
           "--refresh", "--managed-python", "--no-managed-python", "--no-python-downloads", "-q", "--quiet",
           "-v", "--verbose", "--system-certs", "--offline", "--no-progress", "--no-config", "-h", "--help"},
}
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
OUTPUT_WORD = re.compile(r"[\w./~*?\[\]-]+")
OUTPUT_SHORTHAND = re.compile(r"(?<![^\s`(,])(?:\u2026|\.\.\.)[^\s`,;()]*")  # `…_x.csv`: a prefix left out
OUTPUT_BRACES = re.compile(r"[^\s`,;()]*\{[^\s`;()]*")
MAX_OUTPUT_WORDS = 200
MAX_FOLDER_FILES = 5000
MAX_OBSERVED_OUTPUTS = 200  # declared output files watched around one launch; more and the observation is skipped
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


def lint_tools(root):
    """(scilintr, rscript): the paths `gate_init.py --tools` recorded in .mycelium-extra/tools.json,
    else the bare names, looked up on PATH."""
    tools = read_json(state_path(root, "tools.json"), {})
    tools = tools if isinstance(tools, dict) else {}
    return tools.get("scilintr") or "scilintr", tools.get("rscript") or "Rscript"


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "{}.{}.tmp".format(path, os.getpid())  # parallel hooks never share a temp file
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

def tokenize(command, bodies=None, operators=None):
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
            if operators is not None:
                operators.append(command[i:j])
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


def split_option(token, flags):
    """(option, attached value or None) if token is one of flags, as `-C DIR`, `-CDIR` or `--chdir=DIR`."""
    if token in flags:
        return token, None
    if token.startswith("--"):
        name, equals, value = token.partition("=")
        return (name, value) if equals and name in flags else (None, None)
    if token.startswith("-") and token[:2] in flags and len(token) > 2:
        return token[:2], token[2:]
    return None, None


class UnknownFolder(str):
    """The outer folder, standing in for a command's real one when a wrapper's folder option held an
    expansion that cannot be resolved (`env -C "$X/a"`). `raw` is that option's text; `readings` are the other
    (label, paths) readings of the run, for a plan to cover instead of the one returned."""
    def __new__(cls, path, raw, readings=()):
        folder = str.__new__(cls, path)
        folder.raw, folder.readings = raw, list(readings)
        return folder


def move_folder(cwd, value):
    """The folder after a wrapper's folder option: `$PWD`/`${PWD}` and `$HOME`/`${HOME}` are resolved; a value
    that still holds `$` or a backtick, or a relative move from an unknown folder, gives an UnknownFolder."""
    unknown = isinstance(cwd, UnknownFolder)
    if not unknown:
        value = re.sub(r"\$(?:\{(PWD|HOME)\}|(PWD|HOME)(?![A-Za-z0-9_]))",
                       lambda m: cwd if "PWD" in m.group(0) else os.path.expanduser("~"), value)
    if re.search(r"[$`]", value):
        return cwd if unknown else UnknownFolder(cwd, value)
    path = os.path.normpath(os.path.join(cwd, os.path.expanduser(value)))
    return UnknownFolder(path, cwd.raw, cwd.readings) if unknown and not os.path.isabs(
        os.path.expanduser(value)) else path


def classify(tokens, root, cwd, config):
    """Return (explore, gated_label or None, [gated repo paths], cwd) for one segment; cwd is the folder the
    command runs in, after any folder option of a wrapper (`env -C DIR`). If that folder cannot be resolved it
    is an UnknownFolder, and a script or gated command in it is read twice (relative to the outer folder and
    to the repo root): `.readings` of the returned folder lists the second reading."""
    result = _classify(tokens, root, cwd, config)
    folder = result[3]
    if not isinstance(folder, UnknownFolder) or result[1] == "recurse":
        return result
    other = _classify(tokens, root, UnknownFolder(root, folder.raw), config)
    found = [(r[1], r[2]) for r in (result, other) if r[1]]
    if not found:
        return result
    if len(found) == 2 and found[0] == found[1]:
        found.pop()
    return (result[0] or other[0], found[0][0], found[0][1], UnknownFolder(folder, folder.raw, found[1:]))


def _classify(tokens, root, cwd, config, info=None):
    """`info`, if given, gets "head": the index of the program in `tokens` once wrappers and assignments are skipped."""
    explore = False
    i = 0
    while i < len(tokens) and is_assignment(tokens[i]):
        if tokens[i] == EXPLORE_VAR + "=1":
            explore = True
        i += 1
    previous, wrapper, unknown = "", None, False
    while i < len(tokens):
        word = os.path.basename(tokens[i])
        if word == "command" and tokens[i + 1:i + 2] in (["-v"], ["-V"]):
            return explore, None, [], cwd  # looks the name up, runs nothing
        flag, inline = split_option(tokens[i], WRAPPER_OPTIONS.get(wrapper, ((), ()))[0])
        if flag:  # a known option of the wrapper: its value is not the command
            step = 1 if inline is not None else 2
            value = inline if inline is not None else (tokens[i + 1] if i + 1 < len(tokens) else None)
            if wrapper == "env" and flag in ("-S", "--split-string") and value:
                return explore, "recurse", [" ".join([value] + tokens[i + step:])], cwd
            if value and flag in WRAPPER_OPTIONS[wrapper][1]:
                cwd = move_folder(cwd, value)
            previous, unknown, i = "", False, i + step
            continue
        if RUNNERS.match(word) or word in config["gated_commands"]:
            break
        if "/" in tokens[i] and not (word in WRAPPERS and gated_rel(root, cwd, tokens[i], config) is None):
            break  # a path, unless it names a wrapper (`/usr/bin/env`) rather than a gated script
        if (word in WRAPPERS or tokens[i].startswith("-") or previous in VALUE_FLAGS
                or tokens[i].isdigit() or re.match(r"^\d+[smhd]?$", tokens[i])
                or is_assignment(tokens[i])):
            if tokens[i] == EXPLORE_VAR + "=1":
                explore = True
            if word in WRAPPERS and word != "run":
                wrapper = word
            # an option may take the next word as its value; `-oL` carries its own, and `--x=v` too
            unknown = (wrapper is not None and tokens[i].startswith("-") and "=" not in tokens[i]
                       and tokens[i] not in WRAPPER_FLAGS.get(wrapper, ())
                       and (tokens[i].startswith("--") or len(tokens[i]) == 2))
            previous = tokens[i]
            i += 1
            continue
        # a word after an option this reader does not know may be that option's value: skip it
        # when a runner or gated command follows with no other option between (`grep -rn python x/`
        # is a grep, not a hidden python), rather than call the segment ungated
        if unknown:
            later = []
            for t in tokens[i + 1:]:
                if t.startswith("-"):
                    break
                later.append(os.path.basename(t))
            if any(RUNNERS.match(t) or t in config["gated_commands"] for t in later):
                unknown, i = False, i + 1
                continue
        return explore, None, [], cwd
    if i >= len(tokens):
        return explore, None, [], cwd
    head, rest = tokens[i], tokens[i + 1:]
    if info is not None:
        info["head"] = i
    word = os.path.basename(head)
    paths = []
    def script_rel(token, direct=False):
        if not isinstance(cwd, UnknownFolder):
            return gated_rel(root, cwd, token, config)
        # in an unknown folder any script counts, not only one under a gated path: the folder may be one
        return repo_relative(root, cwd, token) if direct or SCRIPT_EXT.search(token) else None
    # the plugin's launcher (`sh <plugin>/hooks/py.sh [--hook] ARGS`) runs `python3 ARGS`; a gated py.sh stays a script
    if word in SHELLS and rest and os.path.basename(rest[0]) == "py.sh" and not script_rel(rest[0], True):
        word, rest = "python3", rest[2:] if rest[1:2] == ["--hook"] else rest[1:]
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
        return explore, word, paths + ["wrap:" + w for w in wraps], cwd
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
                return explore, "recurse", [rest[j + 1]], cwd
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
            rel = script_rel(value)
            first = positional is None and not token.startswith("-")
            if first:
                positional = token
            if rel and (first or SCRIPT_EXT.search(rel) or word in ("jupyter", "papermill", "quarto")):
                paths.append(rel)
        return explore, (word if paths else None), paths, cwd
    rel = script_rel(head, "/" in head)
    return explore, (head if rel else None), ([rel] if rel else []), cwd


def job_cwd(tokens, cwd):
    """Where an sbatch job runs: its `-D`/`--chdir` folder, relative to where sbatch ran."""
    args = after_word(tokens, "sbatch")
    folders = flag_values(args, ("-D", "--chdir")) + [t[2:] for t in args if t.startswith("-D") and len(t) > 2]
    return move_folder(cwd, folders[-1]) if folders else cwd


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
        explore, label, paths, run_cwd = classify(tokens, root, virtual_cwd, config)
        if label == "recurse":
            for inner in analyse_command(paths[0], root, run_cwd, config):
                yield (inner[0] or explore,) + inner[1:]
            continue
        wraps = [p[5:] for p in paths if p.startswith("wrap:")]
        paths = [p for p in paths if not p.startswith("wrap:")]
        for payload in wraps:  # an sbatch --wrap payload runs in the job's folder
            inner_cwd = job_cwd(tokens, run_cwd) if label == "sbatch" else run_cwd
            for inner in analyse_command(payload, root, inner_cwd, config):
                yield (inner[0] or explore,) + inner[1:]
        if label:
            yield explore, label, paths, " ".join(tokens), tokens, run_cwd


def single_shell_command(command, root, cwd, config):
    """Whether the shell's status and output belong to one command, including shell wrappers."""
    while True:
        operators = []
        tokenize(command, operators=operators)
        parts = list(segments(command))
        if len(parts) != 1 or "&" in operators:
            return False
        _, label, paths, _ = classify(parts[0], root, cwd, config)
        if label != "recurse":
            return True
        command = paths[0]


def writes_state(command, root, cwd):
    """True if the command visibly writes into the gate's state folder.

    Redirect and file-command targets are resolved against the folder, so a
    command that only mentions it (reading it, or writing text about it
    elsewhere) passes. A runner's code cannot be traced: it counts when it
    gets a path in the folder, or when its code mentions the folder and writes.
    """
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
        return (any(os.path.basename(t) in WRITE_ALL | WRITE_LAST for t in args)
                and any(inside(t) for part in segments(command) for t in part))
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
            return STATE_DIR in command and WRITE_CODE.search(command) is not None
        return any(names_state(text, root, cwd, head.startswith("python")) and WRITE_CODE.search(text)
                   for text in code + bodies)
    return False


# ---------------------------------------------------------------- approvals

class InvalidApproval(ValueError):
    pass


def valid_fingerprint(pin):
    if not isinstance(pin, dict):
        return False
    if pin.get("missing") is True or isinstance(pin.get("skipped"), str):
        return True
    if pin.get("folder") is True:
        return (isinstance(pin.get("files"), int) and pin["files"] >= 0
                and isinstance(pin.get("listing_sha256"), str)
                and re.fullmatch(r"[0-9a-f]{64}", pin["listing_sha256"]) is not None)
    return (isinstance(pin.get("size"), int) and pin["size"] >= 0
            and isinstance(pin.get("mtime"), (int, float))
            and (not isinstance(pin["mtime"], float) or math.isfinite(pin["mtime"]))
            and ("sha256" not in pin or isinstance(pin["sha256"], str)
                 and re.fullmatch(r"[0-9a-f]{64}", pin["sha256"]) is not None))


def valid_pins(pins):
    return isinstance(pins, dict) and all(valid_fingerprint(pin) for pin in pins.values())


def read_approval(path):
    record = read_json(path, None)
    if (not isinstance(record, dict) or not isinstance(record.get("hash"), str)
            or not re.fullmatch(r"[0-9a-f]{8}", record["hash"])
            or not isinstance(record.get("plan"), str)
            or not isinstance(record.get("approved_at"), (int, float))
            or isinstance(record.get("approved_at"), bool)
            or record["approved_at"] < 0
            or isinstance(record["approved_at"], float) and not math.isfinite(record["approved_at"])
            or any(record.get(key) is not None and not valid_pins(record[key]) for key in ("pins", "scripts"))):
        raise InvalidApproval("mycelium-extra gate: invalid approval state in {}. Restore the record "
                              "or move it aside before running; do not work around this block.".format(path))
    try:
        if not 1 <= time.localtime(record["approved_at"]).tm_year <= 9999:
            raise ValueError("year outside the supported calendar")
    except (OverflowError, OSError, ValueError):
        raise InvalidApproval("mycelium-extra gate: invalid approval state in {}: timestamp outside the "
                              "supported calendar. Restore the record before running.".format(path))
    return record


def read_script_pins(root, digest):
    path = state_path(root, "script-pins", digest + ".json")
    pins = read_json(path, None) if os.path.isfile(path) else {}
    if not valid_pins(pins):
        raise InvalidApproval("mycelium-extra gate: invalid approval state in {}. Restore the script pins "
                              "before running; do not work around this block.".format(path))
    return pins


def active_approvals(root, config, session_id=None):
    """Approvals from the last `approval_hours`, or None if reading them ran out of time.
    Approval files are kept (verify reads old ones), so the folder only grows."""
    folder = state_path(root, "approvals")
    horizon = time.time() - float(config["approval_hours"]) * 3600
    deadline = time.time() + SCAN_SECONDS
    approvals = []
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".json"):
                continue
            if time.time() >= deadline:
                return None
            record = read_approval(os.path.join(folder, name))
            if (record and record.get("approved_at", 0) >= horizon
                    and (session_id is None or bool(session_id) and record.get("session_id") == session_id)):
                approvals.append(record)
    return approvals


def call_id(event):
    """The host's id for this tool call, or None (older hosts, synthetic callers)."""
    return event.get("tool_use_id") or event.get("tool_call_id") or event.get("call_id") or None


def launch_path(root, event):
    """Where one tool call's launch record lives: keyed by the host's call id, else by session and command."""
    call = call_id(event) or (event.get("tool_input") or {}).get("command", "")
    key = sha256(json.dumps([event.get("session_id"), call]).encode("utf-8")).hexdigest()[:16]
    return state_path(root, "launches", key + ".json")


def abandon_launch(folder, name, stamp):
    """Move a launch record that never reported back to launches/abandoned/: an incomplete attempt, kept."""
    kept = os.path.join(folder, "abandoned")
    os.makedirs(kept, exist_ok=True)
    os.replace(os.path.join(folder, name), os.path.join(kept, "{}-{}".format(int(stamp), name)))


def create_exclusive(path, data):
    """Write `data` at `path` only if nothing is there yet; False when a record already is."""
    tmp = "{}.{}.{}.tmp".format(path, os.getpid(), os.urandom(4).hex())
    write_json(tmp, data)
    try:
        os.link(tmp, path)
        return True
    except FileExistsError:
        return False
    except OSError:  # no hard links on this filesystem: fall back to a plain (racy) check
        if os.path.exists(path):
            return False
        os.replace(tmp, path)
        return True
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def write_launch(root, event, runs, attempt_id=None):
    """Save this call's attempt: the approvals that let it launch and the pins checked, so its receipt keeps them
    after expiry. Without a call id, a second identical launch while the first record exists makes the key
    ambiguous: both attempts are stored and no Post is matched to either."""
    folder = state_path(root, "launches")
    if os.path.isdir(folder):  # records of calls that never reported back
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            try:
                if name.endswith(".json") and os.path.getmtime(path) < time.time() - LAUNCH_SECONDS:
                    abandon_launch(folder, name, os.path.getmtime(path))
            except OSError:  # a parallel call's hook got there first
                pass
    now = time.time()
    attempt = {"ts": now, "started": now, "attempt_id": attempt_id or os.urandom(8).hex(), "call_id": call_id(event),
               "cwd": repo_relative(root, root, event.get("cwd") or root) or ".", "runs": runs}
    path = launch_path(root, event)
    # ponytail: three simultaneous identical launches can lose one attempt from the ambiguous list
    if call_id(event) is None and not create_exclusive(path, attempt):
        existing = read_json(path, {})
        attempts = existing.get("attempts") if existing.get("ambiguous") else [existing]
        write_json(path, {"ts": now, "ambiguous": True, "attempts": (attempts or []) + [attempt]})
    elif call_id(event) is not None:
        write_json(path, attempt)


def pins_of(launch, record):
    """The pins a launch checked for this plan, else the approval's own."""
    checked = (launch or {}).get("pins") or {}
    return (checked[record["hash"]] if record["hash"] in checked else record.get("pins")) or {}


def reported_call(root, event):
    """Whether a receipt of this session already names this call id (a duplicate Post callback)."""
    call = call_id(event)
    if not call:
        return False
    try:
        with open(state_path(root, "receipts.jsonl"), "rb") as handle:
            handle.seek(0, os.SEEK_END)
            handle.seek(max(0, handle.tell() - (1 << 20)))
            tail = handle.read().decode("utf-8", "replace")
    except OSError:
        return False
    return any('"call_id": ' + json.dumps(call) in line and json.dumps(event.get("session_id")) in line
               for line in tail.splitlines())


def take_attempt(root, event):
    """This call's launch record, removed once read: {"match": matched | unmatched | ambiguous, "attempt": the
    record or None, "note": why not matched, "candidates": attempt ids when ambiguous}. Taking is one atomic
    rename, so two callbacks for one record cannot both match it."""
    path = launch_path(root, event)
    claim = "{}.{}.{}.taken".format(path, os.getpid(), os.urandom(4).hex())
    try:
        os.rename(path, claim)
    except OSError:
        note = ("duplicate callback: this call id already reported" if reported_call(root, event)
                else "no launch record for this call")
        return {"match": "unmatched", "attempt": None, "note": note, "candidates": []}
    record = read_json(claim, {})
    record = record if isinstance(record, dict) else {}
    try:
        os.remove(claim)
    except OSError:
        pass
    if record.get("ts", 0) < time.time() - LAUNCH_SECONDS:  # a very late report: the attempt stays incomplete
        folder = os.path.dirname(path)
        os.makedirs(os.path.join(folder, "abandoned"), exist_ok=True)
        write_json(os.path.join(folder, "abandoned", "{}-{}".format(int(record.get("ts", 0)), os.path.basename(path))),
                   record)
        return {"match": "unmatched", "attempt": None, "candidates": [],
                "note": "launch record older than {} h".format(LAUNCH_SECONDS // 3600)}
    if record.get("ambiguous"):
        attempts = [a for a in record.get("attempts") or [] if isinstance(a, dict)]
        ids = record.get("candidates") or [a.get("attempt_id") for a in attempts]
        if len(attempts) > 1:  # which attempt this Post belongs to is not known: one is consumed, never named
            create_exclusive(path, dict(record, attempts=attempts[1:], candidates=ids))
        return {"match": "ambiguous", "attempt": None, "candidates": ids,
                "note": "{} identical launches without a call id".format(len(ids))}
    if not record.get("attempt_id"):
        return {"match": "unmatched", "attempt": record, "candidates": [],
                "note": "launch record predates attempt ids"}
    return {"match": "matched", "attempt": record, "note": None, "candidates": []}


def take_launch(root, event):
    """This call's launch record, removed once read: {segment: [{paths, plans, pins}]}, or {} if there is none."""
    return (take_attempt(root, event)["attempt"] or {}).get("runs") or {}


def stat_pair(path):
    """[size, mtime_ns] of a path, or None when it does not exist."""
    try:
        info = os.stat(path)
    except OSError:
        return None
    return [info.st_size, info.st_mtime_ns]


def folder_files(folder, room, deadline):
    """(files under `folder`, recursively, None), or (None, reason) when there are more than `room` or time ran out."""
    files = []
    for here, dirs, names in os.walk(folder):
        dirs.sort()
        files += [os.path.join(here, name) for name in sorted(names)]
        if len(files) > room:
            return None, "cap reached ({} files)".format(MAX_OBSERVED_OUTPUTS)
        if time.time() >= deadline:
            return None, "time limit"
    return files, None


def expand_outputs(root, words, deadline):
    """(paths, None) for the declared output paths of a plan, repo-relative where they are inside it, or
    (None, reason) when they cannot be watched: a `**` pattern, more than MAX_OBSERVED_OUTPUTS files, or time
    ran out. Literal paths and one-level globs; a declared folder (or a glob hit that is one) stands for the
    files inside it, recursively, within the same cap, so nothing is ever listed partially."""
    paths = []
    for word in words:
        word = os.path.expanduser(word)
        full = word if os.path.isabs(word) else os.path.join(root, word)
        hits = [full]
        if re.search(r"[*?\[]", word):
            if "**" in word:
                return None, "pattern with ** not expanded: " + word
            hits = []
            # ponytail: glob lists a whole folder before matching; a folder of millions of files is slow here
            for hit in glob.iglob(full):
                hits.append(hit)
                if len(paths) + len(hits) > MAX_OBSERVED_OUTPUTS:
                    break
                if time.time() >= deadline:
                    return None, "time limit"
        for hit in hits:
            found = [hit]
            if os.path.isdir(hit):
                found, reason = folder_files(hit, MAX_OBSERVED_OUTPUTS - len(paths), deadline)
                if reason:
                    return None, reason
            for item in found:
                rel = os.path.relpath(item, root)
                rel = item if rel == ".." or rel.startswith(".." + os.sep) else rel
                if rel not in paths:
                    paths.append(rel)
        if len(paths) > MAX_OBSERVED_OUTPUTS:
            return None, "cap reached ({} files)".format(MAX_OBSERVED_OUTPUTS)
    return paths, None


def snapshot_outputs(root, plan, budget):
    """The launch-entry fields that record the plan's declared outputs before the run."""
    words = (output_words(plan) or [])[:MAX_OUTPUT_WORDS]
    if not words:
        return {"outputs_skipped": "no declared outputs"}
    paths, reason = expand_outputs(root, words, budget["deadline"])
    if reason:
        return {"outputs_skipped": reason}
    return {"outputs_declared": words, "outputs_before": dict((p, stat_pair(os.path.join(root, p))) for p in paths)}


def observe_outputs(root, launch, budget):
    """(outputs_changed, outputs_observation) for one matched launch entry, compared with its snapshot."""
    if launch.get("outputs_skipped"):
        return None, "skipped: " + launch["outputs_skipped"]
    before = launch.get("outputs_before")
    if not isinstance(before, dict):
        return None, "skipped: no output snapshot in the launch record"
    paths, reason = expand_outputs(root, launch.get("outputs_declared") or [], budget["deadline"])
    if reason:
        return None, "skipped: {} when the run ended".format(reason)
    now = dict((p, stat_pair(os.path.join(root, p))) for p in set(paths) | set(before)
               if not os.path.isdir(os.path.join(root, p)))  # a folder stands for its files
    return {"created": sorted(p for p in now if before.get(p) is None and now[p] is not None),
            "changed": sorted(p for p in before if before[p] is not None and now.get(p) is not None
                              and list(before[p]) != now[p]),
            "deleted": sorted(p for p in before if before[p] is not None and now.get(p) is None)}, "observed"


def pin_limitations(pins, what):
    """Why a pin identifies its file less strongly than a content hash, one string per weak pin."""
    found = []
    for rel in sorted(pins or {}):
        pin = pins[rel]
        if isinstance(pin.get("skipped"), str):
            found.append("{} {}: not fingerprinted ({})".format(what, rel, pin["skipped"]))
        elif pin.get("missing") is True:
            found.append("{} {}: did not exist when approved".format(what, rel))
        elif pin.get("folder") is True:
            found.append("{} {}: folder pinned by its file listing, not by content".format(what, rel))
        elif "sha256" not in pin:
            found.append("{} {}: pinned by size and modification time only".format(what, rel))
    return found


def write_instance(root, record, complete):
    """Write the approval instance (the frozen contract of this approval) under approval-instances/<hash>/ unless
    that exact freeze is already there, and return its id. The id covers the frozen content (plan, pins, scripts,
    preparation, limitations) but not the approval time or session, so approving the same freeze again reuses the
    instance; different pins under the same prose make a second one. Instances are never rewritten."""
    limitations = []
    if not complete:
        limitations.append("prepared before readiness was recorded (legacy entry without `ready`): that pinning "
                           "and the card finished is not established")
    limitations += pin_limitations(record.get("pins"), "input") + pin_limitations(record.get("scripts"), "script")
    body = {"schema": "mycelium-extra.approval-instance.v1", "hash": record["hash"],
            "plan_sha256": sha256(record["plan"].encode("utf-8")).hexdigest(),
            "pins": record.get("pins") or {}, "scripts": record.get("scripts") or {},
            "limitations": limitations, "prepared": "complete" if complete else "legacy-no-ready"}
    for key in ("validation", "execution"):  # only when declared, so a plan without the blocks keeps its id
        if record.get(key):
            body[key] = record[key]
    instance_id = sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
    path = state_path(root, "approval-instances", record["hash"], instance_id + ".json")
    if not os.path.isfile(path):
        write_json(path, dict(body, instance_id=instance_id, approved_at=record["approved_at"],
                              session_id=record.get("session_id")))
    return instance_id


def blocks_module():
    """hooks/validation.py (the plan's two optional comment blocks), imported only when a plan has one."""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import validation
    return validation


BLOCK_START = re.compile(r"<!--\s*(validation-bindings|exact-execution)\b")


def prepare_blocks(root, text):
    """({"validation": ..., "execution": ...}, errors) for a plan: only the blocks it has, each checked and, for
    bindings, with its test files pinned. Without a block: ({}, [])."""
    if not BLOCK_START.search(text):
        return {}, []
    module = blocks_module()
    rows = [row["num"] for row in plan_rows(text) or []]
    found, errors = {}, []
    for key, read in (("validation", module.read_bindings), ("execution", module.read_exact)):
        value, problems = read(text, rows, root)
        errors += problems
        if value:
            found[key] = value
    return ({}, errors) if errors else (found, [])


def invalid_card(digest, errors):
    """The card of a plan whose blocks are invalid: the problems, and no offer to approve."""
    lines = ["mycelium-extra \u00b7 plan {} cannot be approved: its validation-bindings or exact-execution "
             "block is invalid".format(digest)]
    lines += ["  - " + clean(error, 300) for error in errors[:12]]
    lines += ["  \u2026 and {} more".format(len(errors) - 12)] * (len(errors) > 12)
    lines.append("Fix the block and show the plan again; nothing here can be approved as written.")
    return "\n".join(lines)


def cwd_rel(root, cwd):
    """The folder a run starts in, repo-relative ("." for the root); outside the repository it stays absolute."""
    rel = os.path.relpath(os.path.realpath(cwd), os.path.realpath(root))
    return "." if rel == "." else str(cwd) if rel.startswith("..") else rel.replace(os.sep, "/")


def launch_argv(tokens, root, cwd, config):
    """(argv, inline variables) of one run: the words from the program on (wrappers such as `conda run`, `srun`
    or `timeout` and leading `VAR=value` words are not part of it) and the `VAR=value` words before it."""
    info = {}
    _classify(tokens, root, cwd, config, info)
    head = info.get("head")
    if head is None:
        return None, {}
    inline = dict(t.split("=", 1) for t in tokens[:head] if is_assignment(t) and not t.startswith(EXPLORE_VAR + "="))
    return tokens[head:], inline


def step_names_run(step, label, paths):
    """Whether an exact-execution step is about this run: its argv names one of the run's gated scripts (a
    path as written in the step's folder, or `-m` module), else, for a command with no script, its program."""
    argv = step["argv"]
    named = set()
    for j, word in enumerate(argv):
        if j and word.startswith("-"):
            continue
        for candidate in [word] + ([word.replace(".", "/") + ".py"] if j and argv[j - 1] == "-m" else []):
            named.add(posixpath.normpath(posixpath.join(step["cwd"], candidate)))
    if paths:
        return any(path in named for path in paths)
    return os.path.basename(argv[0]) == label


def exact_step_check(root, config, record, label, paths, tokens, cwd):
    """(launch-entry fields, deny lines) for one covered run against its plan's exact-execution steps. A plan
    without the block: ({}, []), a broad grant. A run no step is about: exact_match False. A run a step is
    about must equal one declared argv, in its folder, but for the operational flags."""
    execution = record.get("execution")
    if not execution:
        return {}, []
    steps = [step for step in execution["steps"] if step_names_run(step, label, paths)]
    if not steps:
        return {"exact_match": False}, []
    head = "mycelium-extra gate: blocked because plan {} froze the command of row {} (exact-execution) and this run ".format(
        record["hash"], steps[0]["row"])
    if isinstance(cwd, UnknownFolder):
        return {}, [head + "starts in an unresolved folder (`{}`, a shell expansion the gate cannot resolve), which "
                    "cannot satisfy an exact step. Write the folder literally (`env -C analysis/x ...`) or `cd` there first.".format(cwd.raw)]
    argv, inline = launch_argv(tokens, root, cwd, config)
    module, where, reasons = blocks_module(), cwd_rel(root, cwd), []
    for step in steps:
        ok, why = module.argv_matches(step["argv"], argv, where, step["cwd"], step["operational"], step["env"], inline)
        if ok:
            return {"exact_match": True, "exact_step": step["row"]}, []
        reasons.append((step, why))
    lines = [head + "differs: {}.".format(reasons[0][1])]
    for step, _ in reasons[:3]:
        env = "".join(" {}={}".format(k, v) for k, v in sorted(step["env"].items()))
        lines.append("  declared: {}   (folder {}{})".format(" ".join(step["argv"]), step["cwd"],
                                                              ", env" + env if env else ""))
    lines.append("  actual:   {}   (folder {}{})".format(
        " ".join(argv or tokens), where, ", inline" + "".join(" {}={}".format(k, v) for k, v in sorted(inline.items()))
        if inline else ""))
    flags = sorted(set(f for step, _ in reasons for f in step["operational"]))
    lines.append("An operational retry may differ only in the flags the plan lists as operational ({}). A changed "
                 "analytical argument (model, contrast, threshold, input, seed) changes the approved computation: "
                 "go back to the researcher, who approves a revised plan with `approve plan {}`. Do not work "
                 "around this block.".format(", ".join(flags) or "none", record["hash"]))
    return {}, lines


def invocation_note(root, config, check, plan):
    """Whether a check's invocation would be seen by the gate, and covered by this plan's table."""
    import shlex
    command = " ".join(shlex.quote(word) for word in check["invocation"])
    runs = list(analyse_command(command, root, root, config))
    if not runs:
        return ("not gated, so its runs are not recorded: put the test under a gated path or add its folder to "
                "`gated_paths` in gate.json")
    if all(covering(root, run[1], run[2], [{"plan": plan}]) for run in runs):
        return "gated, named in the plan table"
    return "gated but not named in the plan table, so a run would be denied"


def validation_lines(root, config, plan, validation):
    """The card's lines for a plan's validation bindings: one per check."""
    if not validation:
        return []
    lines = ["Validation bindings (the gate pins the files; `declared by` is the plan's own claim, not verified)"]
    for check in validation["checks"]:
        lines.append("  " + clean("{} \u00b7 row {} \u00b7 {} \u00b7 declared by {} \u00b7 {} test file{} pinned \u00b7 runs "
                           "`{}`: {}".format(
                               check["id"], check["plan_row"], "required" if check["required"] else "optional",
                               check["defined_by"], len(check["files"]), "" if len(check["files"]) == 1 else "s",
                               " ".join(check["invocation"]), invocation_note(root, config, check, plan)), CARD_WIDTH - 2))
    return lines


def validation_denial(stale):
    """The deny text for pinned validation files that changed: [(plan hash, [(check id, path, state)])]."""
    lines = []
    for digest, changes in stale:
        lines.append("mycelium-extra gate: blocked because a validation file pinned by plan {} is no longer as "
                     "approved:".format(digest))
        lines.extend("  - check {}: {} {}".format(check, path, state) for check, path, state in changes)
        lines.append("An approved acceptance expectation is frozen with the plan, and a changed expectation does "
                     "not carry the old acceptance evidence. The plan must be shown and approved again: present "
                     "it, and the user approves the new files with `approve plan {}`. Do not work around this "
                     "block.".format(digest))
    return lines


def covering_any(root, label, paths, cwd, approvals):
    """(approvals covering a run, the paths they cover). Run in an unknown folder, the run counts as covered
    if a plan covers any one of its readings."""
    records = covering(root, label, paths, approvals)
    for other_label, other_paths in getattr(cwd, "readings", ()):
        if records:
            break
        records, paths = covering(root, other_label, other_paths, approvals), other_paths
    return records, paths


def wrapped_gated_paths(root, config, tokens, cwd, paths):
    """The gated paths an `sbatch --wrap` payload runs, from the job's folder (first reading only)."""
    found = []
    for payload in flag_values(after_word(tokens, "sbatch"), ("--wrap",)):
        for inner in analyse_command(payload, root, job_cwd(tokens, cwd), config):
            found += [p for p in inner[2] if p not in paths + found]
    return found


def names_all(root, record, paths):
    table = plan_table(record.get("plan", ""))
    return all(path_in_plan(root, p, table) for p in paths)


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
def plan_table(plan, every_cell=False):
    """The text of the cells that grant runs: under a header with a Step column, the Step cells
    only; otherwise every cell but Source. `repo:` citations are dropped.

    Only the table approves runs: a path or command word in prose, Evidence, a Choice or
    Validation cell, or a source citation approves nothing. `every_cell` keeps every cell but
    Source, as before 0.9.57, for verify's record of what a plan named. "" with no table.
    """
    lines = plan.splitlines()
    cells, keep = [], None  # keep: a test for the column index of a cell that counts
    for i, line in enumerate(lines):
        if not TABLE_ROW.match(line):
            keep = None
            continue
        if TABLE_RULE.match(line):
            continue
        parts = [cell.replace("\0", "|").strip()
                 for cell in TABLE_ROW.match(line).group(1).replace("\\|", "\0").split("|")]
        following = lines[i + 1] if i + 1 < len(lines) else ""
        if TABLE_ROW.match(following) and TABLE_RULE.match(following):  # a header row
            heads = [cell.lower() for cell in parts]
            step = set([j for j, cell in enumerate(heads) if "step" in cell][:1])  # as plan_rows reads it
            source = set(j for j, cell in enumerate(heads) if "source" in cell)
            keep = (lambda j, step=step: j in step) if step and not every_cell else (
                lambda j, source=source: j not in source)
            continue
        cells += [cell for j, cell in enumerate(parts) if keep is None or keep(j)]
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
    literals = []

    def quoted(match):
        path = match.group(2)
        if any(c.isspace() for c in path) and os.path.exists(os.path.join(root, os.path.expanduser(path))):
            literals.append(path)
            return ""  # Its fragments must not accidentally grant a parent folder.
        return match.group(0)

    table = re.sub(r"([`\"'])([^`\"'\n]+)\1", quoted, table)
    return frozenset((repo_relative(root, root, p) or p) if os.path.isabs(p) else p
                     for p in list(plan_paths(table)) + literals)


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
    return ["  Runs allowed \u00b7 broad grant: any arguments"] + bullets(runs)


def expand_braces(word, limit=MAX_OUTPUT_WORDS):
    """`a_{x,y}.csv` -> `a_x.csv`, `a_y.csv`, every group in turn; `{sample}` (no comma) -> `*`.
    At most `limit` words: a longer expansion is cut, so ask for one more than you accept."""
    match = re.search(r"\{([^{}]*)\}", word)
    if not match:
        return [word]
    head, tail = word[:match.start()], word[match.end():]
    parts = match.group(1).split(",") if "," in match.group(1) else ["*"]
    return [w for part in parts for w in expand_braces(head + part + tail, limit)][:limit]


# What an `Inputs:` or `Outputs:` line names, read as literal paths. Nothing is evaluated: a shell
# expression, a pattern an Inputs line cannot use, a quote left open, or an expansion cut short is
# reported in `notes` and its text is never read as paths, so a fragment cannot stand for the file.
MAX_PATH_LINE = 4000   # characters of one line that are read
MAX_PATHS = 500        # paths read from one kind of line
EXPRESSION = re.compile(r"\S*\$(?:\([^)]*\)|[\w({])\S*")   # $VAR, ${VAR}, $(command ...)
PATTERN = re.compile(r"[{}*]|\?(?=[\w./])")           # a glob or brace pattern
LISTED = re.compile(r",\s+\S")                         # `a.tsv, b.tsv` inside one pair of quotes
QUOTE_END = " \t,;:)].`"                                # what may follow a closing single quote


def path_note(item, reason):
    return "`{}` {}".format(clean(item, 60), reason)


def closing_quote(line, start):
    """Index of the quote that closes the one at `start`, or -1. A single quote closes only before
    a space or punctuation, so `'data/o'brien.tsv'` is one path."""
    if line[start] != "'":
        return line.find(line[start], start + 1)
    for k in range(start + 1, len(line)):
        if line[k] == "'" and (k + 1 == len(line) or line[k + 1] in QUOTE_END):
            return k
    return -1


def split_quoted(line):
    """(pieces, notes): `line` as ("text", unquoted run) and ("quoted", literal) pieces. A backtick
    or a double quote opens anywhere; a single quote only after a space or an opening mark, so an
    apostrophe in prose is not one. Nothing after a quote left open is read."""
    pieces, notes, start, i = [], [], 0, 0
    while i < len(line):
        mark = line[i]
        if mark == "`" or (mark in "'\"" and (i == 0 or line[i - 1] in " \t(,;:=[")):
            end = closing_quote(line, i)
            if end < 0:
                notes.append(path_note(line[i:], "opens a quote that is never closed; nothing after it is read"))
                return pieces + [("text", line[start:i])], notes
            pieces += [("text", line[start:i]), ("quoted", line[i + 1:end])]
            start = i = end + 1
        else:
            i += 1
    return pieces + [("text", line[start:])], notes


def quoted_problem(item, root=None, pattern=True):
    """Why the text between quotes is not one literal path, or None. A name that exists is always
    taken as written (`root` known); a pattern is an error only where `pattern` is true."""
    if not item.strip():
        return "an empty quotation names no path"
    if re.search(r"\$(?:\(|[\w{])", item):
        return "is a shell expression; it is not evaluated, so name the literal path"
    if root is not None and os.path.exists(os.path.join(root, os.path.expanduser(item.strip()))):
        return None
    if pattern and PATTERN.search(item):
        return "is a pattern, not a path; name each file"
    if LISTED.search(re.sub(r"\{[^{}]*\}", "", item)):
        return "holds more than one path; put each in its own quotes"
    return None


def read_inputs(text, root=None):
    """(words, notes) for the plan's `Inputs:` lines; words is None without one. Quoted paths are
    kept whole (a quoted name that exists as written is taken even when it looks like a pattern,
    which needs `root`); unquoted words are the simple paths read since 0.9.x."""
    lines = INPUTS_LINE.findall(text)
    if not lines:
        return None, []
    words, notes = [], []

    def add(word):
        if word and word not in words and len(words) < MAX_PATHS:
            words.append(word)
        elif len(words) == MAX_PATHS and word not in words:
            notes.append("more than {} paths on the `Inputs:` lines; the rest are not read".format(MAX_PATHS))

    for line in lines:
        if len(line) > MAX_PATH_LINE:
            notes.append(path_note(line[:30], "starts a line longer than {} characters; the rest is not read".format(MAX_PATH_LINE)))
        pieces, found = split_quoted(line[:MAX_PATH_LINE])
        notes += found
        for kind, piece in pieces:
            if kind == "quoted":
                problem = quoted_problem(piece, root)
                if problem:
                    notes.append(path_note(piece, problem) if piece.strip() else problem)
                else:
                    add(piece.strip()[2:] if piece.strip().startswith("./") else piece.strip())
                continue
            piece = EXPRESSION.sub(lambda m: notes.append(path_note(
                m.group(0), "is a shell expression; it is not evaluated, so name the literal path")) or " ", piece)
            tokens, skip = piece.split(), False
            for token in tokens:
                core = re.sub(r"^(\*+|_+)(.+?)\1$", r"\2", token)
                if skip:
                    skip = False
                elif core.endswith("\\"):
                    notes.append(path_note(core, "ends in a backslash; quote a path that has a space"))
                    skip = True  # the rest of the name is the next word
                elif PATTERN.search(core) and ("/" in core or re.search(r"\.\w", core)):
                    folder = core[:PATTERN.search(core).start()].rpartition("/")[0]
                    notes.append(path_note(core, "is a pattern, not a path; name each file" + (
                        " (its folder `{}` is pinned instead)".format(folder) if folder else "")))
                    add(folder[2:] if folder.startswith("./") else folder)
                else:
                    for word in PATHLIKE.findall(token):
                        word = word.rstrip(".,;:")
                        add(word[2:] if word.startswith("./") else word)
    return words, notes


def read_outputs_notes(text):
    """(words, shorthand, notes) on the plan's `Outputs:` lines, or (None, [], []) without one. A
    `{a,b}` list is expanded and a `<name>` placeholder read as `*`; a word starting with `…` or
    `...` names no path, so it is set aside as shorthand for the card and verify to flag. A quoted
    path is kept whole, spaces and all."""
    lines = OUTPUTS_LINE.findall(text)
    if not lines:
        return None, [], []
    words, shorthand, notes = [], [], []

    def expand(item):
        found = expand_braces(item, MAX_OUTPUT_WORDS + 1)
        if len(found) > MAX_OUTPUT_WORDS:
            notes.append(path_note(item, "expands to more than {} paths; name them".format(MAX_OUTPUT_WORDS)))
        elif any("{" in w or "}" in w for w in found):
            notes.append(path_note(item, "has unbalanced braces"))
        else:
            return found
        return []

    for line in lines:
        if len(line) > MAX_PATH_LINE:
            notes.append(path_note(line[:30], "starts a line longer than {} characters; the rest is not read".format(MAX_PATH_LINE)))
        pieces, found = split_quoted(line[:MAX_PATH_LINE])
        notes += found
        for kind, piece in pieces:
            if kind == "quoted":
                problem = quoted_problem(piece, pattern=False)
                if problem:
                    notes.append(path_note(piece, problem) if piece.strip() else problem)
                elif piece.strip().startswith(("\u2026", "...")):
                    shorthand += [piece.strip()] * (piece.strip() not in shorthand)
                else:
                    words += expand(re.sub(r"<[\w-]+>", "*", piece.strip()))
                continue
            piece = EXPRESSION.sub(lambda m: notes.append(path_note(
                m.group(0), "is a shell expression; it is not evaluated, so name the literal path")) or " ", piece)
            shorthand += [w for w in OUTPUT_SHORTHAND.findall(piece) if w not in shorthand]
            piece = re.sub(r"<[\w-]+>", "*", OUTPUT_SHORTHAND.sub(" ", piece))
            piece = OUTPUT_BRACES.sub(lambda m: " ".join(expand(m.group(0))) or " ", piece)
            words += OUTPUT_WORD.findall(piece)
    return words, shorthand, notes


def read_outputs(text):
    """(words, shorthand) on the plan's `Outputs:` lines, or (None, []) without one; see read_outputs_notes."""
    return read_outputs_notes(text)[:2]


def output_words(text):
    """The paths on the plan's `Outputs:` lines, or None when it has none."""
    found = read_outputs(text)[0]
    if found is None:
        return None
    words = []
    for word in found:
        word = word.rstrip(".,;:")
        if ("/" in word or re.search(r"\.\w+$", word)) and word not in words:
            words.append(word)
    return words


def shorthand_line(text):
    shorthand = read_outputs(text)[1]
    return ["Shorthand, not read: {}; name the full path".format(", ".join(shorthand))] if shorthand else []


def output_lines(text):
    """The paths on the plan's `Outputs:` lines, which verify checks after the runs."""
    words = output_words(text)
    if words is None:
        return ["  Outputs: none named (no `Outputs:` line)"]
    return (["  Outputs"] + bullets(words) if words else ["  Outputs: none"]) + [
        "  " + line for line in shorthand_line(text)]


UNIGNORED = ("Warning: `{0}/` is not in .gitignore, so Mycelium's stop check counts the gate's receipts "
             "as session changes. Fix: add `{0}/` to .gitignore (mycelium-extra init does this).").format(STATE_DIR)


def state_unignored(root):
    """True when Mycelium (`.living/`) shares this git repository and the state folder is not ignored."""
    if not os.path.isdir(os.path.join(root, ".living")) or not git(root, "rev-parse", "--is-inside-work-tree"):
        return False
    return git(root, "check-ignore", "-q", STATE_DIR + "/gate.json") is None


def approval_card(root, text, config, digest, pins, outside, previous, scripts=None, blocks=None):
    """(the card to show, the parts `card <hash> checks|diff|full` shows on request)."""
    card, details = procedure_card(root, text, config, digest, pins, outside, previous, scripts or {}, blocks or {})
    if not card:
        card = "\n".join(["mycelium-extra \u00b7 plan ready for approval",
                          "  \u25b6 approve plan {}".format(digest), ""]
                         + scope_lines(root, text, config) + pin_lines(pins, outside, previous)
                         + script_lines(root, scripts, config) + output_lines(text)
                         + ["  " + line for line in unread_lines(root, text)])
    if state_unignored(root):
        def warn(text):
            head, _, rest = text.partition("\n")
            return "\n".join([head, UNIGNORED, rest])
        card = warn(card)
        if details:
            details["full"] = warn(details["full"])
    return card, details


# ---------------------------------------------------------------- the procedure card
# What the user reads to check a plan: its question, goal, steps with their choices and checks,
# and everything the gate would let run. Display only: the gate still approves from plan_table,
# and nothing quoted here is read back as a path or a command.

CARD_STEPS = 15    # steps shown at all; the plan above lists the rest
CARD_CELL = 200   # a choice or a check is quoted up to this many characters
CARD_PREFIX = 12   # a shared path prefix is stripped when it is at least this long
LINT_EXT = (".py", ".R", ".r", ".ipynb", ".qmd", ".Rmd", ".rmd")  # what verify's lint reads
LINT_SECONDS = 8   # each language's linter gets this long on the card; verify's own check gets longer
CARD_WIDTH = 250   # no line of the card, except a grant or a diff line, is longer
CARD_LINES = 35    # a longer card is shown as a digest; `card <hash> checks|diff|full` shows the rest
CARD_ASK = re.compile(r"^\s*card ([0-9a-f]{8})(?:\s+(checks|diff|full))?\s*[.!]?\s*$", re.IGNORECASE)
ABS_PATH = re.compile(r"(?<![\w./~-])/[^\s`|'\"]+")
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


def comparison_text(text):
    """Plan text as it is compared between plans: control and ANSI characters become spaces and
    whitespace is collapsed; nothing else is changed and nothing is shortened. clean() is for display."""
    return " ".join(CONTROL.sub(" ", text).split())


def table_cells(line):
    return [cell.replace("\0", "|").strip() for cell in TABLE_ROW.match(line).group(1).replace("\\|", "\0").split("|")]


def plan_rows(text):
    """The first plan table with a Step column and a Choice or Validation column, as a list of
    {num, step, choice, source, check, id, cells, head}; None when there is no such table. `id` is
    the cell of a `#`, `no`, `no.` or `ID` column (None without one; `num` then counts the rows);
    `cells` and `head` are every cell of the row and of the header, for comparing plans."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        following = lines[i + 1] if i + 1 < len(lines) else ""
        if not TABLE_ROW.match(line) or TABLE_RULE.match(line) or not (
                TABLE_ROW.match(following) and TABLE_RULE.match(following)):
            continue
        column, head = {}, tuple(table_cells(line))
        for j, cell in enumerate(c.lower() for c in head):
            for key, words in (("step", ("step",)), ("choice", ("choice",)), ("source", ("source",)),
                               ("check", ("validation", "check"))):
                if key not in column and any(word in cell for word in words):
                    column[key] = j
            if cell in ("#", "no", "no.", "id") and "num" not in column:
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
                         "choice": cell("choice"), "source": cell("source"), "check": cell("check"),
                         "id": cell("num") if "num" in column else None, "cells": tuple(cells), "head": head})
        return rows
    return None


def short_runs(root, cell):
    """Absolute paths in a step cell: inside the project, root-relative; outside, the program's name."""
    def fix(match):
        path = match.group(0)
        return path[len(root) + 1:] if path.startswith(root + "/") else os.path.basename(path) or path
    return ABS_PATH.sub(fix, cell)


def first_sentence(text):
    return re.split(r"(?<=[.;])\s", text, 1)[0]


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


def objective_text(text):
    """The plan's objective as written, or None without one."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        found = OBJECTIVE_LINE.match(line)
        if found:
            return found.group(1).strip() or next((l.strip() for l in lines[i + 1:] if l.strip()), "")
    return None


def card_goal(text):
    goal = objective_text(text)
    return "none in the plan" if goal is None else clean(goal, 240)


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
    """Scripts the plan mentions outside its Step cells (and outside Inputs and Outputs), which approve nothing."""
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


def all_approvals(root):
    """Every approval on record, newest first, or None when reading them ran out of time."""
    folder = state_path(root, "approvals")
    deadline = time.time() + SCAN_SECONDS
    found = []
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not name.endswith(".json"):
            continue
        if time.time() >= deadline:
            return None
        record = read_approval(os.path.join(folder, name))
        if record and record.get("plan"):
            found.append(record)
    return sorted(found, key=lambda record: record.get("approved_at", 0), reverse=True)


def read_receipts(root):
    receipts = []
    try:
        with open(state_path(root, "receipts.jsonl"), encoding="utf-8") as handle:
            for line in handle:
                try:
                    receipts.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return receipts


def baseline_plan(root, config, digest, text, paths, outputs):
    """(the newest earlier approval whose plan covers a path this one covers or writes, why not).
    Any age: this is the frozen plan history, not the last 24 hours."""
    approvals = all_approvals(root)
    if approvals is None:
        return None, "time limit"
    table = plan_table(text)
    mine = set(paths) | set(outputs or [])
    for record in approvals:  # an approval of this very text counts: the plan is being shown again
        theirs_table = plan_table(record["plan"])
        theirs = set(plan_grants(root, record["plan"], config)[0]) | set(output_words(record["plan"]) or [])
        if any(path_in_plan(root, p, theirs_table) for p in mine) or any(path_in_plan(root, q, table) for q in theirs):
            return record, ""
    return None, "no earlier approval names these paths"


def row_key(row):
    """What names a plan row across plans: its ID, else its step text."""
    return ("ID", comparison_text(row["id"])) if row["id"] else ("step", comparison_text(row["step"]))


def compare_rows(old, new):
    """How the plan table `new` differs from `old`, by whole cells (nothing shortened): a dict of
    same, changed, added, removed (the old rows' numbers), reordered, columns (the headers differ)
    and cannot (rows whose ID, else step text, is repeated in either table; they are not compared)."""
    def index(rows):
        found, repeated = collections.OrderedDict(), set()
        for row in rows:
            repeated.update([row_key(row)] * (row_key(row) in found))
            found[row_key(row)] = row
        return found, repeated

    before, twice_before = index(old)
    after, twice_after = index(new)
    repeated = twice_before | twice_after
    cells = lambda row: tuple(comparison_text(cell) for cell in row["cells"])
    found = {"same": 0, "changed": 0, "added": 0, "removed": [], "cannot": 0, "kind": "step",
             "columns": [comparison_text(c) for c in old[0]["head"]] != [comparison_text(c) for c in new[0]["head"]]
             if old and new else False}
    for row in new:
        key = row_key(row)
        if key in repeated:
            found["cannot"] += 1
        elif key not in before:
            found["added"] += 1
        else:
            found["same" if cells(row) == cells(before[key]) else "changed"] += 1
    for row in old:
        key = row_key(row)
        if key in repeated:
            found["cannot"] += key not in after  # a repeated row that is gone cannot be matched either
        elif key not in after:
            found["removed"].append(row["num"])
    found["kind"] = "ID" if any(key[0] == "ID" for key in repeated) else "step"
    shared = [key for key in before if key in after and key not in repeated]
    found["reordered"] = shared != [key for key in after if key in before and key not in repeated]
    return found


def plan_blocks(text):
    """The text of each `<!-- validation-bindings ... -->` and `<!-- exact-execution ... -->` block, compared
    as text (the blocks are parsed elsewhere)."""
    return collections.OrderedDict((name, [comparison_text(block) for block in re.findall(
        r"<!--\s*{}\b(.*?)-->".format(name), text, re.DOTALL)]) for name in ("validation-bindings", "exact-execution"))


def baseline_lines(root, config, digest, text, paths, outputs, pins, scripts, rows, short):
    """What is new since the baseline plan, measured by the hook: scripts and inputs by fingerprint,
    the plan by its objective and table rows. Says "no baseline" rather than imply nothing changed."""
    record, why = baseline_plan(root, config, digest, text, paths, outputs)
    if record is None:
        return ["Since earlier plans: no baseline ({})".format(why)]
    receipts = []

    def recorded(rel):
        pin = (record.get("scripts") or {}).get(rel) or read_json(
            state_path(root, "script-pins", record["hash"] + ".json"), {}).get(rel)
        if pin:
            return pin
        if not receipts:
            receipts.extend(read_receipts(root))
        for r in reversed(receipts):
            seen = r.get("script") or {}
            if (seen.get("path") == rel and record["hash"] in (r.get("plans") or []) and not r.get("explore")
                    and not seen.get("missing")):
                return seen
        return None

    states = collections.OrderedDict((name, []) for name in ("CHANGED", "NEW", "SAME"))
    for rel, now in sorted(scripts.items()):
        before = recorded(rel)
        states["NEW" if before is None else "SAME" if unchanged(before, now) else "CHANGED"].append(rel)
    lines = ["Since {} (approved {})".format(record["hash"], time.strftime("%Y-%m-%d %H:%M",
                                                                           time.localtime(record.get("approved_at", 0))))]
    lines.append("  scripts  " + (" \u00b7 ".join("{}: {}".format(name, ", ".join(short(r) for r in rels))
                                                  for name, rels in states.items() if rels) or "none pinned"))
    old_pins = record.get("pins") or {}
    pinned = collections.OrderedDict((name, []) for name in ("CHANGED", "NEW"))
    same = 0
    for rel, now in sorted((pins or {}).items()):
        if rel not in old_pins:
            pinned["NEW"].append(rel)
        elif unchanged(old_pins[rel], now):
            same += 1
        else:
            pinned["CHANGED"].append(rel)
    parts = ["{}: {}".format(name, names_plain(rels, short)) for name, rels in pinned.items() if rels]
    gone = sorted(rel for rel in old_pins if rel not in (pins or {}))
    parts += ["REMOVED: " + names_plain(gone, short)] * bool(gone)
    lines.append("  inputs   " + (", ".join(["{} SAME".format(same)] * bool(same) + parts) if same or parts
                                  else "none pinned"))
    before_rows = plan_rows(record["plan"])
    if before_rows is None:
        lines.append("  plan     the earlier plan has no step table")
    else:
        diff = compare_rows(before_rows, rows)
        gone = diff["removed"]
        goals = [None if goal is None else comparison_text(goal) for goal in map(objective_text, (record["plan"], text))]
        lines.append("  plan     objective {} \u00b7 steps: {} same, {} new or changed{}{}{}{}".format(
            "SAME" if goals[0] == goals[1] else "CHANGED",
            diff["same"], diff["added"] + diff["changed"],
            ", {} removed ({})".format(len(gone), ", ".join(gone[:5]) + (", \u2026" if len(gone) > 5 else "")) if gone else "",
            ", order changed" if diff["reordered"] else "", ", columns changed" if diff["columns"] else "",
            "; cannot compare: {} rows with a repeated {}".format(diff["cannot"], diff["kind"]) if diff["cannot"] else ""))
    was, now = output_words(record["plan"]) or [], outputs or []
    moved = ["{}: {}".format(name, names_plain(items, short)) for name, items in
             (("NEW", [w for w in now if w not in was]), ("REMOVED", [w for w in was if w not in now])) if items]
    if moved:
        lines.append("  outputs  " + " \u00b7 ".join(moved))
    was, now = (set(a + b) for a, b in (plan_grants(root, record["plan"], config), plan_grants(root, text, config)))
    moved = ["{}: {}".format(name, names_plain(sorted(items), short)) for name, items in
             (("NEW", now - was), ("REMOVED", was - now)) if items]
    if moved:
        lines.append("  scope    " + " \u00b7 ".join(moved))
    blocks, earlier = plan_blocks(text), plan_blocks(record["plan"])
    states = ["{} {}".format(name, "SAME" if earlier[name] == blocks[name] else "ADDED" if not earlier[name]
                             else "REMOVED" if not blocks[name] else "CHANGED")
              for name in blocks if earlier[name] or blocks[name]]
    if states:
        lines.append("  blocks   " + " \u00b7 ".join(states))
    return lines


def names_plain(items, short):
    shown = [short(item) for item in items[:3]]
    return ", ".join(shown) + (", \u2026 and {} more".format(len(items) - 3) if len(items) > 3 else "")


def fit(line):
    return line if len(line) <= CARD_WIDTH else line[:CARD_WIDTH - 1].rstrip() + "\u2026"


def load_verify():
    """skills/verify/scripts/verify.py as a module, wired to this gate (it is otherwise run from stdin)."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills", "verify", "scripts",
                        "verify.py")
    spec = importlib.util.spec_from_file_location("mycelium_extra_verify", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.gate = sys.modules[__name__]
    return module


def lint_gap_applies(gap, names):
    """A gap tagged `scilintr (R)` or `(Python)` concerns only steps whose code is that language; a step that
    names notebooks or documents (either language), or a gap with no tag, takes it."""
    match = re.match(r"scilintr \((\w+)\)", gap)
    kinds = set("Python" if n.endswith(".py") else "R" if n.endswith((".R", ".r")) else None for n in names)
    return not match or None in kinds or match.group(1) in kinds


def lint_bullets(root, rows, config):
    """{step number: one-line scilintr verdict} for the planned code each step names, by running verify's
    lint once on all of it: `clean`, `2 open (R002 2)`, or `not checked (...)`. Show only, never blocks;
    {} when the plan names no code, `card_lint` is false in gate.json, or the linter cannot be run."""
    if config.get("card_lint", True) is False:
        return {}
    files = {row["num"]: sorted(p for p in plan_paths_in(root, DONE_MARK.sub("", row["step"]))
                                if p.endswith(LINT_EXT) and os.path.isfile(os.path.join(root, p))) for row in rows}
    every = sorted(set(p for names in files.values() for p in names))
    if not every:
        return {}
    try:
        verify = load_verify()
        report = verify.Report()
        found = verify.lint(root, every, report, *lint_tools(root), seconds=LINT_SECONDS)["findings"]
    except Exception:  # ANALYSIS_OK[card-best-effort]: the card still shows the plan; verify lints in full later
        return {}
    gaps = [text for level, text in report.findings if level == "gap"]
    out = {}
    for num, names in files.items():
        if not names:
            continue
        mine = collections.Counter(f[3] for f in found if re.sub(r"\[code cell \d+\]$", "", f[0]) in names)
        unchecked = [g for g in gaps if any("`{}`".format(n) in g or "`{}:".format(n) in g for n in names)
                     or (not re.search(r"`[^`]*\.\w+[:`]", g) and lint_gap_applies(g, names))]  # no file named: the language's
        if mine:
            out[num] = "{} open ({})".format(sum(mine.values()), ", ".join(
                "{} {}".format(r, n) if n > 1 else r for r, n in mine.most_common(3)))
        elif unchecked:
            out[num] = "not checked ({})".format(re.sub(r"^scilintr(?: \(\w+\))? (?:not checked:? ?)?", "", unchecked[0])[:90])
        else:
            out[num] = "clean"
    return out


def procedure_card(root, text, config, digest, pins, outside, previous, scripts, blocks=None):
    """The card for a plan whose table has Step and Choice or Validation columns, else None."""
    rows = plan_rows(text)
    if not rows:
        return None, None
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

    pinned_lines, script_changes, script_diff_lines = script_state(root, scripts, config)
    changes = pin_changes(pins, previous) + script_changes
    defaults = [row["num"] for row in rows if row["source"].lower().startswith("default")]
    lines = ["mycelium-extra \u00b7 plan {} ready for approval".format(digest)]
    lines += baseline_lines(root, config, digest, text, paths, outputs, pins, scripts, rows, short)
    lines += changes
    lines += ["Question   " + card_question(text), "Goal       " + card_goal(text),
              "Defaults to confirm: " + ("step " + ", ".join(defaults) if defaults else "none")]
    facts = FACTS_LINE.search(text)
    if facts:
        lines.append(clean(facts.group(0), 160))
    procedure_at = len(lines)
    lint = lint_bullets(root, rows[:CARD_STEPS], config)
    legend = "   (* = a default decided; confirm it)" if defaults else ""
    lines += ["", "Sequence" + legend]
    brief = list(lines[-2:])
    for row in rows[:CARD_STEPS]:
        cells = " ".join((row["step"], row["choice"], row["check"]))
        done = "  (agent says: done)" if DONE_MARK.search(cells) else ""
        is_default = row["source"].lower().startswith("default")
        name = quote(re.sub(r"/?(?:[^\s/]+/)+(?=[\w.-])", "", re.sub(r"^run\s+", "", short_runs(root, DONE_MARK.sub(
            "", row["step"])).replace("`", ""), flags=re.IGNORECASE)), 70)
        head = "{} {} {}{}{}".format("  \u2193" if len(lines) > procedure_at + 2 else "   ", row["num"], name,
                                    "*" if is_default else "", done)
        why = "assumed: " + quote(re.sub(r"^default\s*:?\s*", "", row["source"], flags=re.IGNORECASE)) if is_default else ""
        who = "  [{}]".format(source_tag(row["source"])) if row["source"].strip() and not is_default else ""
        choice, check = (quote(DONE_MARK.sub("", row[key])) for key in ("choice", "check"))
        short_choice = quote(first_sentence(clean(DONE_MARK.sub("", row["choice"]), 1000)), 120)
        lines.append(head)
        brief.append(head)
        for bucket, text_ in ((lines, choice), (brief, short_choice)):
            if text_:
                bucket.append("        - choice: " + text_ + who)
            if why:
                bucket.append("        - " + why)
        if check:
            lines.append("        - check: " + check)
            if is_default:
                brief.append("        - check: " + quote(DONE_MARK.sub("", row["check"]), 120))
        if row["num"] in lint:
            lines.append("        - lint: " + lint[row["num"]])
            if lint[row["num"]] != "clean":
                brief.append(lines[-1])
    if len(rows) > CARD_STEPS:
        lines.append("\u2026 and {} more steps in the plan above".format(len(rows) - CARD_STEPS))
        brief.append(lines[-1])
    steps_end = len(lines)
    flags = evidence_flags(text)
    if flags:
        lines += ["", "From Evidence (flagged)"] + ["  - " + flag for flag in flags[:3]]
        if len(flags) > 3:
            lines.append("  (+{} more flagged in Evidence)".format(len(flags) - 3))
    can_run_at = len(lines) + 1
    execution = (blocks or {}).get("execution")
    lines += ["", "CAN RUN (in full)" + (" \u00b7 " + ("exact where listed below, otherwise broad grant: any arguments"
                                                  if execution else "broad grant: any arguments")
                                         if paths or commands else "")]
    for path in paths:
        if os.path.isfile(os.path.join(root, path)) or SCRIPT_EXT.search(path):
            kind, note = ("script" if SCRIPT_EXT.search(path) else "file"), ("  pinned" if path in scripts else "")
        else:
            kind, note = "folder", "  (every gated file below it)"
        lines.append("  {:<9}{}{}".format(kind, short(path), note))
    lines += ["  {:<9}{}  (any invocation)".format("command", command) for command in commands]
    if not paths and not commands:
        lines.append("  nothing: the plan table names no gated script, folder, or command")
    for step in (execution or {}).get("steps") or []:
        lines.append("  " + clean("exact: row {}: {}   (folder {}{}{})".format(
            step["row"], " ".join(step["argv"]), step["cwd"],
            ", free flags: " + " ".join(step["operational"]) if step["operational"] else "",
            "; env " + " ".join("{}={}".format(k, v) for k, v in sorted(step["env"].items())) if step["env"] else ""),
            1000))
    reads_at = len(lines)
    lines.append("Reads " + ("{} pinned{}".format(len(reads), names(reads, short)) if reads else
                             ("none (no `Inputs:` line)" if pins is None else "none (the `Inputs:` line names no files)")))
    lines.append("Writes " + ("{}{}".format(len(outputs), names(outputs, short)) if outputs else
                              "none named (no `Outputs:` line)"))
    lines += shorthand_line(text)
    lines += unread_lines(root, text)
    if outside:
        lines.append("Outside the repository, not pinned" + names(outside, str))
    if prefix:
        lines.append("P = " + prefix)
    if outside_prose:
        lines.append("Outside the Step column, not authorised" + names(outside_prose, short))
    lines += validation_lines(root, config, text, (blocks or {}).get("validation"))
    diff_at = len(lines)
    if script_diff_lines:
        lines += ["Diff of changed scripts"] + script_diff_lines
    lines.append("\u25b6 approve plan {}".format(digest))
    # A grant line and a diff line are never cut: what the gate allows and what changed are shown whole.
    lines = [line if can_run_at <= i < reads_at or i >= diff_at else fit(line) for i, line in enumerate(lines)]
    brief = [fit(line) for line in brief]
    full = "\n".join(lines)
    if len(lines) <= CARD_LINES:
        return full, None
    # The digest: the science of each step on one line, checks only where a default decided, Reads and
    # Writes counted, no diff. Baseline, changed scripts, flagged Evidence and grants stay in full.
    counts = "Reads {} pinned \u00b7 Writes {}".format(len(reads), len(outputs or []))
    more = "More: type `card {0} checks`{1} or `card {0} full`".format(
        digest, ", `card {} diff` ({} lines)".format(digest, len(script_diff_lines)) if script_diff_lines else "")
    shown = (lines[:procedure_at] + brief + lines[steps_end:reads_at] + [counts] + lines[reads_at + 2:diff_at]
             + [more, "\u25b6 approve plan {}".format(digest)])
    checks = ["Checks of plan {}".format(digest)] + ["{:>2}  {}".format(row["num"], quote(DONE_MARK.sub(
        "", row["check"]))) for row in rows if row["check"].strip()]
    return "\n".join(shown), {"full": full, "checks": "\n".join(checks), "diff": "\n".join(
        ["Diff of changed scripts"] + script_diff_lines) if script_diff_lines else "No script diff on this card."}


# ---------------------------------------------------------------- pinned inputs

def plan_inputs(text):
    """The words on a plan's `Inputs:` lines, or None when it has none; read_inputs says what it could not read."""
    return read_inputs(text)[0]


def unread_lines(root, text):
    """One line for each `Inputs:` or `Outputs:` entry that could not be read as a literal path (at most
    five of each kind), so the card never lets a fragment stand for the intended file."""
    lines = []
    for label, notes in (("Inputs", read_inputs(text, root)[1]), ("Outputs", read_outputs_notes(text)[2])):
        lines += ["{} not read: {}".format(label, note) for note in notes[:5]]
        lines += ["{} not read: \u2026 and {} more".format(label, len(notes) - 5)] * (len(notes) > 5)
    return lines


def pin_inputs(root, text, config):
    """Return (pins, outside). pins maps repo paths to fingerprints; it is None
    when the plan has no `Inputs:` line. A word without a slash counts only if
    it names an existing file, so prose on the line is skipped. What read_inputs
    could not read as a literal path is pinned as nothing; the card lists it."""
    words = read_inputs(text, root)[0]
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

def run_limit(config):
    """(limit, notice) from `max_runs_per_approval` in gate.json: a whole number of 1 or more. Unset means no
    limit; any other value is ignored, with a notice."""
    value = config.get("max_runs_per_approval")
    if value is None:
        return None, None
    if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
        return value, None
    return None, ('mycelium-extra gate: "max_runs_per_approval" in gate.json must be a whole number of 1 or '
                  "more; no limit applies.")


def checkpoint_steps(config):
    """(steps, notice) from `checkpoint_steps` in gate.json: a whole number of 1 or more. Unset or 0 is off;
    any other value is ignored, with a notice."""
    value = config.get("checkpoint_steps")
    whole = isinstance(value, int) and not isinstance(value, bool)
    if value is None or (whole and value == 0):
        return None, None
    if whole and value >= 1:
        return value, None
    return None, ('mycelium-extra gate: "checkpoint_steps" in gate.json must be a whole number of 1 or '
                  "more; no comprehension checkpoint applies.")


def checkpoint_question(rows, digest):
    """(row, right, question) for the one comprehension question about a plan table: which step number makes a
    Choice (the row picked from the hash, so asking twice gives the same question); with no Choice cell, which
    step number names the first script or path. `right` is the set of step numbers that answer it. None when
    neither is possible."""
    numbered = [(int(re.sub(r"\D", "", row["num"])), row) for row in rows if re.sub(r"\D", "", row["num"])]
    choice = lambda row: "" if clean(row["choice"], 120).lower() in ("-", "\u2014", "n/a", "none") else clean(
        row["choice"], 120)
    with_choice = [(n, row) for n, row in numbered if choice(row)]
    if with_choice:
        text = choice(with_choice[int(digest, 16) % len(with_choice)][1])
        row = next(row for n, row in with_choice if choice(row) == text)
        right = set(n for n, other in with_choice if choice(other) == text)
        return row, right, 'which step number makes this Choice: "{}"?'.format(text)
    for _, row in numbered:
        word = next((w.rstrip(".,;:") for w in clean(row["step"], 200).split()
                     if SCRIPT_EXT.search(w.rstrip(".,;:"))
                     or (re.search(r"\w/\w|^\.{0,2}/|/$", w) and not re.match(r"^[A-Za-z]+/[A-Za-z]+$", w))), None)
        if word:
            right = set(n for n, other in numbered if word in clean(other["step"], 200))
            return row, right, 'which step number names "{}"?'.format(word)
    return None


def log_approval(root, event, plan, approved_ts, checkpoint):
    """One line per approval in approvals.jsonl: when the plan was shown, when it was approved, its size, and
    the checkpoint result when one ran. Only logged: never shown, and never allowed to fail the approval."""
    shown = plan.get("ts")
    record = {"hash": plan["hash"], "session_id": event.get("session_id"), "shown_ts": shown,
              "approved_ts": approved_ts,
              "latency_s": round(max(approved_ts - shown, 0), 1) if isinstance(shown, (int, float)) else None,
              "plan_rows": len(plan_rows(plan["text"]) or []), "plan_chars": len(plan["text"])}
    if checkpoint:
        record["checkpoint"] = checkpoint
    try:
        append_line(state_path(root, "approvals.jsonl"), record)
    except OSError:
        pass


def checkpoint_reply(root, session, plan, steps, answer):
    """(reply, checkpoint): a reply asking the question (again) when the checkpoint holds back this
    `approve plan`; otherwise None and the checkpoint's result for the log (None when none ran). Wrong attempts
    are counted in a side file, so the pending plan itself never changes."""
    rows = plan_rows(plan["text"]) if steps else None
    asked = checkpoint_question(rows, plan["hash"]) if rows and len(rows) > steps else None
    if asked is None:
        return None, None
    row, right, question = asked
    path = state_path(root, "pending", session + ".checkpoint")
    state = read_json(path, {})
    state = state if isinstance(state, dict) else {}
    wrong = state.get(plan["hash"], 0)
    wrong = wrong if isinstance(wrong, int) else 0
    passed = answer is not None and int(answer) in right
    shown = ""
    if passed:
        state.pop(plan["hash"], None)
    else:
        state[plan["hash"]] = wrong + (answer is not None)
        if answer is not None:
            shown = "Not step {}. Step {}: {} | Choice: {} | Source: {}. ".format(
                answer, clean(row["num"], 10), clean(row["step"], 160), clean(row["choice"], 120) or "none",
                clean(row["source"], 60) or "none")
    try:
        write_json(path, state)
    except OSError:
        pass
    if passed:
        return None, {"asked": True, "passed": True, "wrong_attempts": wrong}
    return ("mycelium-extra: plan {h} is not approved yet. {shown}One question first: {q} Answer with "
            "`approve plan {h} <number>`.".format(h=plan["hash"], shown=shown, q=question)), None


def limit_changes(root, runs, budget, cache):
    """What differs now from the first run counted under an approval: the commit, and each script's content
    (shown even with `pin_scripts` off). The approval's inputs and pinned scripts already block when they change."""
    first, lines = runs[0], []
    now, before = git_state(root), first.get("git")
    if before and now and before.get("head") != now["head"]:
        lines.append("HEAD {} -> {}".format(before["head"][:12], now["head"][:12]))
    elif before and now and not before.get("dirty") and now.get("dirty"):
        lines.append("uncommitted changes now; the first run was on a clean tree")
    seen = {}
    for receipt in runs:
        record = receipt.get("script") or {}
        if record.get("in_repo") and record.get("path") and record["path"] not in seen:
            seen[record["path"]] = record
    for rel, record in sorted(seen.items()):
        change, _ = script_change(root, rel, record, budget, cache)
        if change:
            lines.append(change)
    return lines or ["nothing recorded differs: the same commit and scripts"]


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
        tmp = "{}.{}.{}.tmp".format(target, os.getpid(), os.urandom(4).hex())  # parallel hooks never share one
        with open(tmp, "wb") as handle:
            handle.write(data)
        os.replace(tmp, target)


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
        pin = (record.get("scripts") or {}).get(rel) or read_script_pins(root, record["hash"]).get(rel)
        if pin:
            return pin
    return None


def script_lines(root, scripts, config):
    """The approval card's script section: what is pinned and what changed since a plan approved it."""
    pinned, changed, diff = script_state(root, scripts, config)
    return pinned + changed + diff


def script_state(root, scripts, config):
    """(pinned lines, changed summary, diff lines) of the scripts section."""
    approvals = active_approvals(root, config)
    now_all = dict(scripts or {})
    for record in approvals or []:  # scripts pinned at a first run, still on disk
        for rel in read_script_pins(root, record["hash"]):
            if rel not in now_all and os.path.isfile(os.path.join(root, rel)):
                now_all[rel] = fingerprint(os.path.join(root, rel), hash_budget(config))
    if not now_all:
        return [], [], []
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
    after = ["  Scripts changed since last approved"] + bullets(changed) if changed else []
    diff = diff_text[:DIFF_LINES]
    if len(diff_text) > DIFF_LINES:
        diff.append("      \u2026 and {} more diff lines".format(len(diff_text) - DIFF_LINES))
    return lines, after, diff


@contextlib.contextmanager
def state_lock(root, name):
    """Serialize a read-modify-write of one state file across parallel hooks, with the repository's existing
    flock helper (stateio.locked). Best effort: where it cannot lock (no fcntl, a symlinked path, 2 s busy) the
    update goes ahead unlocked, as it always did. Never hold it while hashing or running a tool."""
    guard = None
    try:
        import stateio
        guard = stateio.locked(state_path(root, "locks", name + ".lock"))
        guard.__enter__()
    except Exception:
        guard = None
    try:
        yield
    finally:
        if guard is not None:
            guard.__exit__(None, None, None)


def note_first_runs(root, firsts, budget):
    """Pin scripts that did not exist when their plan was shown, at the run that first uses them."""
    found = collections.OrderedDict()
    for digest, rel in firsts:  # hashing happens before the lock is taken
        if rel not in read_script_pins(root, digest) and (digest, rel) not in found:
            found[(digest, rel)] = fingerprint(os.path.join(root, rel), budget)
            keep_snapshot(root, rel, found[(digest, rel)])
    if not found:
        return
    with state_lock(root, "script-pins"):  # a parallel hook may have added its own pin since
        ledgers = {}
        for (digest, rel), pin in found.items():
            ledgers.setdefault(digest, read_script_pins(root, digest)).setdefault(rel, pin)
        for digest, ledger in ledgers.items():
            write_json(state_path(root, "script-pins", digest + ".json"), ledger)


# ---------------------------------------------------------------- events

def on_tool(event, root, config):
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    state = os.path.realpath(state_path(root))
    if tool == "apply_patch":
        for _, target in PATCH_TARGET.findall(tool_input.get("command", "")):
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
        return protected_write_notice(root, event, target)
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
    limit, limit_notice = run_limit(config)
    capped = []
    granted = explore_granted(root, event.get("session_id"))
    scope = explore_scope_of(root, event.get("session_id")) if granted else None
    attempt_id, scope_notes = os.urandom(8).hex(), []
    run_scripts, launched = [], {}
    unresolved, wrap_blocked = [], []
    stale_validation, exact_refused = [], []
    for explore, label, paths, segment, tokens, run_cwd in analyse_command(command, root,
                                                                            event.get("cwd") or root, config):
        run_scripts += [p for p in paths if p.endswith(LINT_EXT) and p not in run_scripts]
        if explore and granted:
            extra = {}
            if scope:  # bounded exploration: the plan's analysis paths, and its declared protected files
                reason, notes = scoped_explore(root, config, scope, label, paths, tokens, run_cwd)
                if reason:
                    return deny(reason)
                scope_notes += [n for n in notes if n not in scope_notes]
                extra = {"explore_scope": scope.get("instance_id") or scope["hash"], "attempt_id": attempt_id}
                pins = dict((rel, fingerprint(os.path.join(root, rel), budget)) for rel in paths
                            if not rel.startswith("wrap:") and os.path.isfile(os.path.join(root, rel)))
                extra["explore_script_pins"] = pins
                # one launch entry, so the receipt names the attempt; no plan pins are checked, no output snapshot
                launched.setdefault(segment, []).append(dict(
                    extra, paths=paths, plans=[scope["hash"]], pins={}, outputs_skipped="exploratory run"))
            log_explore(root, event, segment, paths, extra)
            continue
        if explore:
            return deny("mycelium-extra gate: the exploratory-run prefix works only after the user "
                        "types `allow explore` in this session, and they have not. Do not work "
                        "around this block; ask the user.")
        if approvals is None:
            approvals = active_approvals(root, config, event.get("session_id") or "")
            if approvals is None:
                return deny(SCAN_TIMEOUT)
        records, used = covering_any(root, label, paths, run_cwd, approvals)
        wrapped = wrapped_gated_paths(root, config, tokens, run_cwd, paths) if label == "sbatch" else []
        if wrapped:  # one plan must name sbatch and what its --wrap payload runs, as the receipt requires
            records = [r for r in records if names_all(root, r, wrapped)]
        if not records:
            blocked.append((label, paths))
            if wrapped:
                wrap_blocked.append(wrapped)
            if isinstance(run_cwd, UnknownFolder) and run_cwd.raw not in unresolved:
                unresolved.append(run_cwd.raw)
            continue
        # The newest covering plan is the current intent: an older approval that pinned
        # less (or nothing) must not let a run through after the newer plan's pins changed.
        newest = records[-1]
        # one entry per (segment, paths): the same text in two folders is two runs with their own plans
        entry = {"paths": paths, "plans": [r["hash"] for r in records],
                 "pins": dict((r["hash"], r.get("pins") or {}) for r in records)}
        instances = dict((r["hash"], r["instance_id"]) for r in records if r.get("instance_id"))
        if instances:
            entry["instance_ids"] = instances
        if isinstance(run_cwd, UnknownFolder):  # allowed by one of its readings, not by a resolved folder
            entry["limitations"] = ["cwd unresolved: " + run_cwd.raw]
        fields, refused = exact_step_check(root, config, newest, label, paths, tokens, run_cwd)
        if refused:
            exact_refused += refused
            continue
        entry.update(fields)
        if newest.get("validation"):
            changed = blocks_module().changes(root, newest["validation"])
            if changed and all(newest["hash"] != h for h, _ in stale_validation):
                stale_validation.append((newest["hash"], changed))
            argv, inline = launch_argv(tokens, root, run_cwd, config) if not isinstance(run_cwd, UnknownFolder) else (None, {})
            for check in newest["validation"]["checks"]:  # the check this very command is, by exact argv
                if argv and blocks_module().argv_matches(check["invocation"], argv, cwd_rel(root, run_cwd), ".",
                                                         actual_env=inline)[0]:
                    entry["validation_check"] = check["id"]
        if not any(all(e.get(key) == value for key, value in entry.items()) for e in launched.setdefault(segment, [])):
            entry.update(snapshot_outputs(root, newest.get("plan", ""), budget))
            launched[segment].append(entry)
        changes, skipped = changed_pins(root, newest.get("pins") or {}, budget, cache)
        if changes:
            stale.append((newest["hash"], changes))
        else:
            unchecked += [rel for rel in skipped if rel not in unchecked]
        changed_scripts = []
        for rel in used if scripts_on else []:
            if not os.path.isfile(os.path.join(root, rel)):
                continue
            pin = (newest.get("scripts") or {}).get(rel) or read_script_pins(root, newest["hash"]).get(rel)
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
        if limit and all(newest["hash"] != h for h, _, _ in capped):
            try:
                runs = load_verify().approval_runs(root, config, newest["hash"], newest.get("approved_at", 0),
                                                   read_receipts(root))
            except Exception as error:  # fail open on the limit alone, and say so
                limit_notice = ("mycelium-extra gate: max_runs_per_approval not checked ({}: {})."
                                .format(type(error).__name__, error))
                limit = None
            else:
                if len(runs) >= limit:
                    capped.append((newest["hash"], len(runs), limit_changes(root, runs, budget, cache)))
    if exact_refused:
        return deny("\n".join(exact_refused))
    if stale_validation and not blocked:  # a pinned test or expectation file changed: checked before the pins below
        return deny("\n".join(validation_denial(stale_validation)))
    if (stale or stale_scripts or capped) and not blocked:
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
        for digest, used, changes in capped:
            lines.append("mycelium-extra gate: blocked because plan {} has been used for {} run(s), its limit "
                         "(`max_runs_per_approval` in gate.json). Changes since its first run:".format(digest, used))
            lines.extend("  - " + change for change in changes)
            lines.append("The user reviews this and re-approves: present the plan again, and they approve it "
                         "with `approve plan {}`, which restarts the count. Do not work around this "
                         "block.".format(digest))
        return deny("\n".join(lines))
    if not blocked:
        note_first_runs(root, firsts, budget)
        messages = []
        if unchecked:  # fail open, but say so
            messages.append("mycelium-extra gate: pinned inputs not re-checked before this run "
                            "(time limit, `pin_seconds`): {}.".format(listing(unchecked)))
        if notice and approvals is not None:  # a gated run was checked
            messages.append(notice)
        if limit_notice and approvals is not None:
            messages.append(limit_notice)
        denied, user_note, agent_note = lint_before_run(root, run_scripts, config)
        if denied:
            return denied
        if user_note:
            messages.append(user_note)
        if scope_notes:
            messages += scope_notes
            agent_note = "\n".join([agent_note] * bool(agent_note) + scope_notes)
        if launched:
            write_launch(root, event, launched, attempt_id)
        result = {"systemMessage": "\n".join(messages)} if messages else None
        if agent_note:
            result = result or {}
            result["hookSpecificOutput"] = {"hookEventName": "PreToolUse", "additionalContext": agent_note}
        return result
    hashes = ", ".join(r["hash"] for r in approvals) or "none"
    lines = ["mycelium-extra gate: blocked because no active approved plan covers this run."]
    for label, paths in blocked:
        lines.append("  - {}{}".format(label, (" " + ", ".join(paths)) if paths else ""))
    for wrapped in wrap_blocked:
        lines.append("An `sbatch --wrap` payload is covered only when one approved plan names both sbatch and "
                     "what the payload runs ({}); plans that cover them separately do not count.".format(
                         ", ".join(wrapped)))
    for raw in unresolved:
        lines.append("The folder `{}` given to a wrapper's folder option is a shell expansion the gate cannot "
                     "resolve, so it read the run relative to the repo root and to the current folder, and "
                     "no approved plan covers either. Write a literal path (`env -C analysis/demo ...`) or "
                     "`cd` there first.".format(raw))
    lines.append("Active approved plans (last {} h): {}.".format(config["approval_hours"], hashes))
    lines.append("Present a plan whose plan table names these paths (prose, Evidence, and Source "
                 "citations do not count) and that ends with the grill status line; "
                 "the user approves it by typing `approve plan <hash>`. Do not work around this "
                 "block; if the user wants an exploratory run instead, they will say so.")
    return deny("\n".join(lines))


LINT_RUN_MODES = ("warn", "block")


def open_findings_before_run(root, rels):
    """{script: [finding lines]} for the scripts a run uses that lint-on-write recorded with open findings and
    that have not been edited since, from any session's record. A script never linted by the hook, or edited
    since, is unknown and not listed; `verify` still checks it."""
    found = {}
    for rel in rels:
        try:
            mtime = os.path.getmtime(os.path.join(root, rel))
        except OSError:
            continue
        name = sha256(rel.encode("utf-8")).hexdigest()[:16] + ".json"
        for path in sorted(glob.glob(state_path(root, "pending", "*.lint", name))):
            entry = read_json(path, {})
            if entry.get("file") == rel and entry.get("mtime") == mtime and entry.get("rows"):
                found[rel] = entry["rows"]
                break
    return found


def lint_before_run(root, rels, config):
    """(deny or None, message for the user, message for the agent) from `lint_before_run` in gate.json: false
    (default) does nothing, "warn" tells both, "block" denies the run. Other values are ignored with a notice."""
    mode = config.get("lint_before_run", False)
    if mode is False:
        return None, None, None
    if mode not in LINT_RUN_MODES:
        return None, 'mycelium-extra gate: "lint_before_run" in gate.json must be "warn" or "block"; it is off.', None
    open_ = open_findings_before_run(root, rels)
    if not open_:
        return None, None, None
    lines = ["mycelium-extra: scilintr findings recorded at write time are still open in a script this run uses:"]
    for rel, rows in sorted(open_.items()):
        lines.append("  {}:".format(rel))
        lines += ["    " + row for row in rows[:5]] + (["    ..."] if len(rows) > 5 else [])
    if mode == "block":
        lines.append("Blocked because gate.json sets lint_before_run to block. Fix each finding, or waive it with "
                     "`ANALYSIS_OK[rule]: <what is done, why it is valid, where it is checked>` where the choice is "
                     "deliberate, then run again. The user can set it to warn. Do not work around this block.")
        return deny("\n".join(lines)), None, None
    lines.append("Running anyway (lint_before_run is warn). `verify` blocks on any finding left.")
    return None, "\n".join(lines), "\n".join(lines)


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


def log_explore(root, event, segment, paths, extra=None):
    append_line(state_path(root, "explore.log"), dict(extra or {}, ts=time.time(), session_id=event.get("session_id"),
                                                      command=segment, paths=paths))


def explore_scope_of(root, session_id):
    """The scope of this session's grant (`allow explore <hash>`), or None for a plain session grant."""
    scope = (read_json(grant_path(root, session_id), {}) or {}).get("scope")
    return scope if isinstance(scope, dict) and scope.get("hash") else None


def make_explore_scope(root, config, session_id, digest):
    """(scope, None) from an active approval of this session, else (None, why not). The scope keeps that approval's
    instance, the analysis paths and commands its plan grants, and its declared protected files and steps."""
    approvals = active_approvals(root, config, session_id or "")
    if approvals is None:
        return None, SCAN_TIMEOUT
    record = next((r for r in approvals if r["hash"] == digest), None)
    if record is None:
        return None, ("mycelium-extra: no active approved plan {} in this session (active: {}), so no scoped "
                      "exploration was allowed. Approve it first (`approve plan {}`), or type `allow explore` "
                      "alone for the broader session-wide development grant.".format(
                          digest, ", ".join(r["hash"] for r in approvals) or "none", digest))
    paths, commands = plan_grants(root, record.get("plan", ""), config)
    scope = {"hash": digest, "instance_id": record.get("instance_id"), "analysis_paths": paths,
             "commands": commands}
    scope.update((key, record[key]) for key in ("validation", "execution") if record.get(key))
    return scope, None


def scoped_explore(root, config, scope, label, paths, tokens, cwd):
    """(deny reason or None, notices) for one explore-prefixed run under a scoped grant. Denied only for a gated
    path (or command) outside the scope's analysis paths. A protected test or expectation file that changed, a run of
    a protected check's invocation, or a run that differs from a frozen exact step is surfaced, not denied. This
    is path-and-declared-file based; nothing here judges the science of a change."""
    def outside(label, paths):
        paths = [p for p in paths if not p.startswith("wrap:")]
        if label == "sbatch":
            paths += wrapped_gated_paths(root, config, tokens, cwd, paths)
        if not paths:
            return [] if label in scope.get("commands", []) else [label]
        return [p for p in paths if not any(p == g or p.startswith(g.rstrip("/") + "/")
                                            for g in scope.get("analysis_paths", []))]
    found = outside(label, paths)
    for other_label, other_paths in getattr(cwd, "readings", ()) if found else ():
        found = found and outside(other_label, other_paths)  # an unresolved folder counts if any reading is in scope
    if found:
        return ("mycelium-extra gate: blocked because exploration is scoped to approved plan {} and this run touches "
                "{}, outside the analysis paths that plan grants ({}). The user decides: they can approve a plan "
                "that names it (widening the scope), or type `allow explore` for the broader session-wide grant. Do "
                "not work around this block.".format(scope["hash"], ", ".join(found),
                                                     ", ".join(scope.get("analysis_paths") or []) or "none"), [])
    notes, blocks = [], blocks_module() if scope.get("validation") or scope.get("execution") else None
    if scope.get("validation"):
        notes += ["protected file {} ({}, check {}) is not as approved".format(path, state, check)
                  for check, path, state in blocks.changes(root, scope["validation"])]
        argv, inline = launch_argv(tokens, root, cwd, config) if not isinstance(cwd, UnknownFolder) else (None, {})
        notes += ["this run is the declared invocation of protected check {}; run under explore it is not validation "
                  "evidence".format(check["id"]) for check in scope["validation"]["checks"]
                  if argv and blocks.argv_matches(check["invocation"], argv, cwd_rel(root, cwd), ".", actual_env=inline)[0]]
    if scope.get("execution"):
        steps = [step for step in scope["execution"]["steps"] if step_names_run(step, label, paths)]
        refused = exact_step_check(root, config, {"hash": scope["hash"], "execution": scope["execution"]},
                                           label, paths, tokens, cwd)[1]
        if refused and steps:
            notes.append("this run differs from the frozen exact-execution command of row {}".format(steps[0]["row"]))
    if not notes:
        return None, []
    return None, ["mycelium-extra: exploration under plan {} (scoped): {}. Exploration continues, but reportable "
                  "runs will need re-approval: the plan is shown and approved again with `approve plan {}`, then "
                  "re-run with fresh outputs. Exploratory runs never count as validation or as a reportable run; "
                  "this check is path-and-declared-file based, advisory beyond that.".format(
                      scope["hash"], "; ".join(notes), scope["hash"])]


def protected_write_notice(root, event, target):
    """A PreToolUse notice when a scoped grant is active and `target` is a protected test or expectation file."""
    scope = explore_scope_of(root, event.get("session_id"))
    rel = os.path.relpath(target, os.path.realpath(root)).replace(os.sep, "/")
    files = [path for check in ((scope or {}).get("validation") or {}).get("checks") or []
             for path in check.get("files") or {}]
    if rel not in files:
        return None
    message = ("mycelium-extra: {} is a protected test or expectation file of plan {} (the scoped exploration "
               "grant). Editing it changes the approved contract: reportable runs will need re-approval "
               "(`approve plan {}`).".format(rel, scope["hash"], scope["hash"]))
    return {"systemMessage": message,
            "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": message}}


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


SCRIPTS_PINNED_FROM = 1791289996  # 2026-10-06 12:33 UTC: 0.9.44 first wrote `scripts` to a pending entry


def plan_ready(entry):
    """Whether a pending plan was fully prepared. Entries from 0.9.44 to 0.9.70 have no `ready` field, but
    wrote `scripts` only after pinning finished (the first save held hash, ts, text and pins), so an entry
    without `ready` counts as ready only with `scripts`. Before 0.9.44 nothing marked completion: those
    entries (older than that release) stay approvable."""
    if "ready" in entry:
        return bool(entry["ready"])
    return "scripts" in entry or entry.get("ts", 0) < SCRIPTS_PINNED_FROM


def packet_consent(event, root, prefix):
    """Record the user's consent to send one prepared review packet (`review-consent/<digest>.json`), the only
    place consent is written. The prefix must name exactly one prepared packet folder that has its manifest."""
    folder = state_path(root, "review-packets")
    digests = [name for name in (os.listdir(folder) if os.path.isdir(folder) else [])
               if re.fullmatch(r"[0-9a-f]{64}", name) and name.startswith(prefix)
               and os.path.isfile(os.path.join(folder, name, "manifest.json"))]
    if not digests:
        return ("mycelium-extra: no consent recorded: no prepared review packet matches `{}`. Prepare it with "
                "`review_packet.py prepare` and type the exact line `review_packet.py preview` prints.".format(prefix))
    if len(digests) > 1:
        return ("mycelium-extra: no consent recorded: {} prepared packets match `{}`, so nothing was recorded; "
                "type a longer prefix.".format(len(digests), prefix))
    digest = digests[0]
    write_json(state_path(root, "review-consent", digest + ".json"),
               {"schema": "mycelium-extra.review-consent.v1", "digest": digest,
                "session_id": event.get("session_id") or "unknown", "ts": time.time(), "prompt": event.get("prompt")})
    return ("mycelium-extra: consent recorded for review packet {}. Next: run `review_packet.py verify --digest {}` "
            "immediately before sending, and send exactly the files it lists.".format(digest, digest[:12]))


def on_prompt(event, root, config):
    prompt = event.get("prompt") or ""
    consent = SEND_PACKET.fullmatch(prompt.strip().lower())
    if consent:
        message = packet_consent(event, root, consent.group(1))
        return {"systemMessage": message,
                "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": message}}
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
            scope, problem = (None, None) if not grant.group(2) else make_explore_scope(
                root, config, event.get("session_id"), grant.group(2).lower())
            record = {"granted_at": time.time(), "session_id": event.get("session_id")}
            if problem:
                message = problem
            elif scope:
                write_json(path, dict(record, scope=scope))
                message = ("mycelium-extra: exploratory runs allowed for this session, scoped to approved plan {} "
                           "(approval instance {}). Prefix a gated run with {}=1; runs on {} need no further "
                           "approval, a run outside them is denied, and a change to the plan's protected test or "
                           "exact-execution files is reported (reportable runs then need re-approval). Scope "
                           "checks are path and declared-file based, advisory beyond that. Each run is logged and "
                           "never counts as validation. `stop explore` ends this.".format(
                               scope["hash"], scope.get("instance_id") or "unknown", EXPLORE_VAR,
                               ", ".join(scope["analysis_paths"]) or "no gated path"))
            else:
                write_json(path, record)
                message = ("mycelium-extra: exploratory runs allowed for this session. Prefix a gated run "
                           "with {}=1; each one is logged and listed as not reportable. This is the broader, "
                           "session-wide development grant (any gated path); `allow explore <plan hash>` "
                           "limits it to an approved plan. `stop explore` ends this.".format(EXPLORE_VAR))
        else:
            if os.path.isfile(path):
                os.remove(path)
            message = "mycelium-extra: exploratory runs are no longer allowed in this session."
        return {"systemMessage": message,
                "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": message}}
    match = APPROVE.match(prompt)
    steps, steps_notice = checkpoint_steps(config)
    if match and match.group(2) and not steps:  # a step number answers a checkpoint question; none is open
        match = None
    session = safe_session(event.get("session_id"))
    pending = read_json(state_path(root, "pending", session + ".json"), [])
    ask = CARD_ASK.match(prompt)
    if ask:  # answered here, so the agent never sees it
        plan = next((p for p in pending if p["hash"] == ask.group(1).lower()), None)
        part = (ask.group(2) or "full").lower()
        if plan is None:
            shown = "mycelium-extra: no pending plan {} in this session.".format(ask.group(1))
        else:
            shown = (plan.get("card") or {}).get(part) or "mycelium-extra: plan {} showed its full card.".format(
                plan["hash"])
        return {"decision": "block", "reason": shown}
    known = ", ".join(p["hash"] + ("" if plan_ready(p) else " (invalid block)" if p.get("invalid") else " (preparing)")
                      for p in pending) or "none"
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
    elif plan.get("invalid"):  # its validation-bindings or exact-execution block did not pass
        message = ("mycelium-extra: plan {} has an invalid validation-bindings or exact-execution block ({}). "
                   "Nothing was approved. Fix the block and show the plan again.".format(
                       wanted, clean(plan["invalid"][0], 160)))
    elif not plan_ready(plan):  # preparation was interrupted; approving would drop the pins
        message = ("mycelium-extra: plan {} was not fully prepared (inputs, scripts or card). Nothing was "
                   "approved. Show the plan again so it is prepared, then approve its hash.".format(wanted))
    else:
        reply, checkpoint = checkpoint_reply(root, session, plan, steps, match.group(2))
        if reply:
            return {"systemMessage": reply,
                    "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": reply}}
        pins = plan.get("pins") or {}
        scripts = plan.get("scripts") or {}
        record = {"hash": wanted, "approved_at": time.time(), "session_id": event.get("session_id"),
                  "plan": plan["text"], "pins": pins, "scripts": scripts}
        record.update((key, plan[key]) for key in ("validation", "execution") if plan.get(key))
        record["instance_id"] = write_instance(root, record, bool(plan.get("ready")))
        write_json(state_path(root, "approvals", wanted + ".json"), record)
        log_approval(root, event, plan, record["approved_at"], checkpoint)
        ledger = state_path(root, "script-pins", wanted + ".json")  # approving again re-baselines
        if os.path.isfile(ledger):
            os.remove(ledger)
        message = ("mycelium-extra: plan {} approved. Gated runs whose paths appear in that plan "
                   "may run for {} h. {}{}".format(
                       wanted, config["approval_hours"],
                       "Pinned inputs: {}.".format(listing(pins)) if pins else "No inputs pinned.",
                       " Pinned scripts: {}.".format(listing(scripts)) if scripts else ""))
        if steps_notice:
            message += " " + steps_notice
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
        previous = next((p for p in pending if p["hash"] == digest and plan_ready(p)), None)
        pending = [p for p in pending if p["hash"] != digest]
        entry = {"hash": digest, "ts": time.time(), "text": text, "pins": {}, "ready": False}
        pending.append(entry)
        write_json(path, pending[-10:])  # a timeout while pinning keeps the text, but it is not approvable yet
        pins, outside = pin_inputs(root, text, config)
        entry["pins"] = pins or {}
        scripts_on, notice = script_pinning(config)
        entry["scripts"] = pin_scripts(root, text, config) if scripts_on else {}
        blocks, errors = prepare_blocks(root, text)
        if errors:  # an invalid block is shown, never offered for approval; `ready` stays False
            entry["invalid"] = errors
            card, details = invalid_card(digest, errors), None
        else:
            entry.update(blocks)
            card, details = approval_card(root, text, config, digest, pins, outside, previous, entry["scripts"], blocks)
        if details:
            entry["card"] = details
        entry["ready"] = not errors  # pins, scripts and card are done: now the hash can be approved
        write_json(path, pending[-10:])
        notices.append(card)
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
    open_lint = open_lint_notice(root, event, config)
    if open_lint:
        notices.append(open_lint)
    if hints_on(root):
        notices += stop_hints(root, event)
    result = {"systemMessage": "\n\n".join(notices)} if notices else {}
    block = lint_stop_block(root, event, config)
    if block:
        result.update(decision="block", reason=block)
    return result or None


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

WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit", "apply_patch")
WRITE_LINT_SECONDS = 8  # per subprocess; all passes share 16 s, leaving room for the 20 s hook limit
WRITE_LINT_FILES = 5    # files of one apply_patch that are linted
LINT_ROW = 240          # characters of a finding shown to the agent: scilintr echoes the code it flags
PATCH_TARGET = re.compile(r"^\*\*\* (Add File|Update File|Delete File|Move to): (.+)$", re.M)


def lint_dir(root, session_id):
    """One state file per linted script, so parallel writes in one turn never overwrite each other:
    {"file", "rows": [finding lines], "mtime"}. The session's `.lint-shown` holds what the
    user was already told; separate `.lint-note-*` markers deduplicate gaps for the agent."""
    return state_path(root, "pending", safe_session(session_id) + ".lint")


def lint_entry_path(root, session_id, rel):
    return os.path.join(lint_dir(root, session_id), sha256(rel.encode("utf-8")).hexdigest()[:16] + ".json")


def written_scripts(event, root, config):
    """Gated code files this write touched, as repository paths (a deleted file is not one)."""
    tool_input = event.get("tool_input") or {}
    if event.get("tool_name") == "apply_patch":
        names = [name.strip() for kind, name in PATCH_TARGET.findall(tool_input.get("command", "")) if kind != "Delete File"]
    else:
        names = [tool_input.get("file_path") or tool_input.get("notebook_path") or ""]
    found = []
    for name in names:
        rel = gated_rel(root, event.get("cwd") or root, name, config) if name else None
        if rel and rel.endswith(LINT_EXT) and rel not in found and os.path.isfile(os.path.join(root, rel)):
            found.append(rel)
    return found


def lint_on_write(event, root, config):
    """After a script is written or edited, hand the agent scilintr's open findings on the touched files, once
    per change. Advisory: never blocks. The files go through one `verify.lint` call, so at most two passes per
    language. R may check cross-file rules among those files; `verify` checks the wider analysis.
    What scilintr could not check is said once per session, never shown as clean, and leaves that file's
    recorded findings as they were. Stop later tells the user what is still open."""
    if config.get("lint_on_write", True) is False:
        return None
    rels = written_scripts(event, root, config)
    if not rels:
        return None
    session = event.get("session_id")
    skipped, rels = rels[WRITE_LINT_FILES:], rels[:WRITE_LINT_FILES]
    mtimes = {rel: os.path.getmtime(os.path.join(root, rel)) for rel in rels}
    try:
        verify = load_verify()
        report = verify.Report()
        linted = verify.lint(root, rels, report, *lint_tools(root), seconds=WRITE_LINT_SECONDS,
                             deadline=time.monotonic() + 16)
        found = linted["findings"]
        findings = report.findings + [("gap", "scilintr not checked: `{}` has no readable code for a supported language.".format(rel))
                                      for rel in linted.get("notebooks", [])]
    except Exception as error:  # ANALYSIS_OK[lint-best-effort]: advisory hook; verify checks in full later
        found, findings = [], [("gap", "scilintr not checked: lint hook failed ({}).".format(type(error).__name__))]
    findings += [("gap", "scilintr not checked: `{}` exceeds the five-file write limit.".format(rel)) for rel in skipped]
    clean = lambda text: re.sub(r"[\x00-\x1f\x7f]", " ", text)[:LINT_ROW]
    gaps = [text for level, text in findings if level == "gap"]
    names_file = lambda gap, rel: "`{}`".format(rel) in gap or "`{}:".format(rel) in gap
    whole = any(not any(names_file(g, rel) for rel in rels + skipped) for g in gaps)
    unknown = set(rels) if whole else set(
        rel for rel in rels if any(names_file(g, rel) for g in gaps))
    lines = []
    for rel in rels:
        if rel in unknown:
            continue
        rows = ["{}:{}: [{}] {}".format(f[0], f[1], f[3], clean(f[4]))
                for f in sorted(found, key=lambda f: (f[0], int(f[1])))
                if re.sub(r"\[code cell \d+\]$", "", f[0]) == rel]
        rows += ["[waiver-reason] " + clean(text) for level, text in findings
                 if level == "block" and "`{}:".format(rel) in text]
        path = lint_entry_path(root, session, rel)
        previous = read_json(path, {}).get("rows", [])
        if rows:
            write_json(path, {"file": rel, "rows": rows, "mtime": mtimes[rel]})
        elif os.path.isfile(path):
            os.remove(path)
        shown = state_path(root, "pending", safe_session(session) + ".lint-shown")
        if rows != previous:
            try:
                os.remove(shown)
            except FileNotFoundError:
                pass
        if rows and rows != previous:
            lines.append("{} open finding(s) in `{}`:\n{}".format(
                len(rows), rel, "\n".join("  " + r for r in rows[:8]) + ("\n  ..." if len(rows) > 8 else "")))
    notes = []
    for gap in dict.fromkeys(gaps):
        marker = state_path(root, "pending", safe_session(session) + ".lint-note-" +
                            sha256(gap.encode("utf-8")).hexdigest()[:16])
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        try:
            with open(marker, "x"):
                pass
        except FileExistsError:
            continue
        notes.append(clean(gap))
    if not lines and not notes:
        return None
    text = ""
    if lines:
        text += ("mycelium-extra: scilintr reports after this write:\n{}\nFix each one, or waive it with "
                 "`ANALYSIS_OK[rule]: <what is done, why it is valid, where it is checked>` where the choice is "
                 "deliberate. `verify` blocks on any finding left.".format("\n".join(lines)))
    if notes:
        text += ("\n" if text else "mycelium-extra: ") + (
            "scilintr could not check everything just written, so this is not a clean result:\n{}\n`verify` "
            "reports it as a gap until it can be checked.".format("\n".join("  " + n for n in notes[:4])))
    return {"hookSpecificOutput": {"hookEventName": event.get("hook_event_name") or "PostToolUse",
                                   "additionalContext": text}}


def open_lint_scripts(root, session_id):
    """{script: [finding lines]} for scripts written this session whose findings are still open. A script edited
    since its lint (say by `sed` through Bash) is skipped: nothing is known."""
    folder = lint_dir(root, session_id)
    still = {}
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        entry = read_json(os.path.join(folder, name), {})
        try:
            if os.path.getmtime(os.path.join(root, entry["file"])) == entry["mtime"]:
                still[entry["file"]] = list(entry["rows"])
        except (OSError, KeyError, AttributeError, TypeError):
            continue
    return still


def open_lint_notice(root, event, config):
    """User-only Stop line for scripts written this session that still have open scilintr findings, shown once
    per change."""
    if config.get("lint_on_write", True) is False:
        return None
    still = open_lint_scripts(root, event.get("session_id"))
    marker = state_path(root, "pending", safe_session(event.get("session_id")) + ".lint-shown")
    if not still:
        if os.path.isfile(marker):
            os.remove(marker)
        return None
    counts = {rel: collections.Counter(re.search(r"\[([\w-]+)\]", r).group(1) for r in rows if "[" in r)
              for rel, rows in still.items()}
    message = ("mycelium-extra: scilintr findings are still open in script(s) written this session: {}. "
               "`verify` blocks on them unless they are fixed or waived with `ANALYSIS_OK[rule]: reason`.".format(
                   listing(("{} ({})".format(os.path.basename(rel), ", ".join(
                       "{} {}".format(r, n) if n > 1 else r for r, n in rules.most_common(3)))
                       for rel, rules in sorted(counts.items())), 5)))
    if read_json(marker, "") == message:
        return None
    write_json(marker, message)
    return message


def lint_stop_block(root, event, config):
    """With `lint_before_stop`, the reason that sends the agent back to fix or waive open findings, once per
    change. Never twice in a row: the host sets `stop_hook_active` when it is already continuing because
    of a Stop hook. Off by default; the user-only Stop line is the default backstop."""
    if config.get("lint_before_stop") is not True or config.get("lint_on_write", True) is False:
        return None
    if event.get("stop_hook_active"):
        return None
    still = open_lint_scripts(root, event.get("session_id"))
    if not still:
        return None
    lines = []
    for rel, rows in sorted(still.items())[:5]:
        lines.append("  {}:".format(rel))
        lines += ["    " + row for row in rows[:5]] + (["    ..."] if len(rows) > 5 else [])
    reason = ("mycelium-extra: scilintr findings are still open in script(s) you wrote this session:\n{}\n"
              "Fix each one, or waive it with `ANALYSIS_OK[rule]: <what is done, why it is valid, where it is "
              "checked>` where the choice is deliberate, then finish. `verify` blocks on any finding left. "
              "This stop is blocked once per change (gate.json `lint_before_stop`).".format("\n".join(lines)))
    marker = state_path(root, "pending", safe_session(event.get("session_id")) + ".lint-stop-blocked")
    if read_json(marker, "") == reason:
        return None
    write_json(marker, reason)
    return reason


def on_post(event, root, config):
    if event.get("tool_name") in WRITE_TOOLS:
        return lint_on_write(event, root, config)
    if event.get("tool_name") != "Bash":
        return None
    command = (event.get("tool_input") or {}).get("command", "")
    runs = list(analyse_command(command, root, event.get("cwd") or root, config))
    if not runs:
        return None
    taken = take_attempt(root, event)  # the approvals this launch was checked against, not today's
    attempt = taken["attempt"]
    launched = (attempt or {}).get("runs") or {}
    wrapped = set()  # an `sbatch --wrap` payload was submitted, not run here
    for run in runs:
        if run[1] == "sbatch":
            for payload in flag_values(after_word(run[4], "sbatch"), ("--wrap",)):
                wrapped.update(" ".join(tokens) for tokens in segments(payload))
    runs = [run for run in runs if run[1] == "sbatch" or run[3] not in wrapped]
    response = event.get("tool_response")
    output = response_text(response)
    status, source, extra = exit_status(event)
    compound = not single_shell_command(command, root, event.get("cwd") or root, config)
    if compound:
        extra.update(command_exit_status=status, command_exit_source=source)
        status, source, output = "unknown", None, ""
    budget = hash_budget(config)
    git = git_state(root)
    approvals, unread = False, False  # approvals: read only for a run with no launch record
    notes = ["compound shell command: per-run execution, exit status, and output attribution unknown"] if compound else []
    planned, coverage = [], []
    for explore, label, paths, segment, tokens, cwd in runs:
        entries = launched.get(segment)  # a record in the older shape is a dict: no match, covering decides
        launch = next((e for e in entries if e.get("paths") == paths), None) if isinstance(entries, list) else None
        if launch is not None:  # expired or replaced since, the launch's own approvals are credited
            records = [r for r in (read_json(state_path(root, "approvals", h + ".json"), None)
                                   for h in launch.get("plans", [])) if r]
        else:
            if approvals is False:
                approvals = active_approvals(root, config, event.get("session_id") or "")
                unread = approvals is None
                approvals = approvals or []
                if unread:
                    notes.append("approvals not read (time limit), so no plan is credited")
            records, paths = covering_any(root, label, paths, cwd, approvals)
        # the gated scripts an `sbatch --wrap` payload runs, from the job's folder
        wrapped_paths = wrapped_gated_paths(root, config, tokens, cwd, paths) if label == "sbatch" else []
        if wrapped_paths:  # a plan is credited with the job only if it also names what the job runs
            records = [r for r in records if names_all(root, r, wrapped_paths)]
        paths = paths + wrapped_paths
        # a run counts as launched only when this call's own launch record names this segment
        launch_match, note = taken["match"], taken["note"]
        if launch_match == "matched" and launch is None:
            launch_match, note = "unmatched", "no launch entry for this run in the call's launch record"
        limitations = list((launch or {}).get("limitations") or [])
        if isinstance(cwd, UnknownFolder) and "cwd unresolved: " + cwd.raw not in limitations:
            limitations.append("cwd unresolved: " + cwd.raw)
        for limitation in limitations:
            if limitation.startswith("cwd unresolved: "):
                coverage.append("{} (matched by reading it from the outer folder or the repo root)".format(limitation))
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
            "pins": pins_of(launch, records[-1]) if records else {},
            "pins_checked": launch_match == "matched" and bool(records) and not explore,
            "launch_match": launch_match,
            "attempt_id": attempt["attempt_id"] if launch_match == "matched" else None,
            "started": attempt.get("started") if launch_match == "matched" else None,  # when the launch began
            "call_id": call_id(event),
            # the freeze this launch was checked against, not the approval file as it reads now
            "approval_instance": (None if not records else (launch.get("instance_ids") or {}).get(
                records[-1]["hash"]) if launch is not None else records[-1].get("instance_id")),
            "git": git,
            "hook_env": {key: os.environ[key] for key in HOOK_ENV if os.environ.get(key)},
            "command_env": command_env(tokens),
            "exit_status": status,
            "exit_source": source,
            "response_keys": sorted(response) if isinstance(response, dict) else type(response).__name__,
        }
        if limitations:
            receipt["limitations"] = limitations
        for key in ("validation_check", "exact_match", "exact_step", "explore_scope", "explore_script_pins"):
            if launch and key in launch:  # what the launch recorded about the plan's blocks, or a scoped explore
                receipt[key] = launch[key]
        if launch_match != "matched":
            receipt["outputs_observation"] = "skipped: {} launch".format(launch_match)
        elif compound:
            receipt["outputs_observation"] = "skipped: compound shell command"
        elif label == "sbatch":
            receipt["outputs_observation"] = "skipped: job submission (outputs are written after the call returns)"
        else:
            changed, receipt["outputs_observation"] = observe_outputs(root, launch, budget)
            if changed is not None:
                receipt["outputs_changed"] = changed
        if launch_match != "matched" and note:
            receipt["launch_note"] = note
        if launch_match == "ambiguous":
            receipt["attempt_candidates"] = taken["candidates"]
        receipt.update(extra)
        if event.get("host"):
            receipt["host"] = event["host"]
        if unread and launch is None:
            receipt["approvals_unread"] = True
        receipt.update(launch_details(root, cwd, label, paths, tokens, output, budget))
        add_git_states(root, receipt, git is not None)
        append_line(state_path(root, "receipts.jsonl"), receipt)
        what = "{} job {}".format(label, receipt["job_id"]) if receipt.get("job_id") else label
        notes.append("{} ({})".format(what, "plan " + receipt["plans"][-1] if records
                                      else "explore run" if explore else "no approved plan"))
    result = {"systemMessage": "mycelium-extra: run receipt recorded: {}.".format("; ".join(notes))}
    if coverage:
        result["systemMessage"] += "\nmycelium-extra: coverage: " + "; ".join(sorted(set(coverage))) + "."
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

    An integer exit code in the tool response wins (source "response"); the OpenCode launcher
    maps the shell result's `metadata.exit` to `exit_code` for this. Otherwise Codex and
    OpenCode post events can name no exit status, so without a code they are "unknown". Then
    the event decides: PostToolUse runs only after a tool completes successfully, so a
    foreground run gets 0 (source "event"), but a run started with run_in_background has only
    started, and an interrupted result was cut off. PostToolUseFailure's `error` starts with
    `Exit code N` when the command ran and exited (source "error"); with no such line the
    shell did not start or Claude Code stopped it ("failed"), and is_interrupt marks an abort
    ("interrupted"). Only the error's first line is kept, never its output. Any other payload
    (no hook_event_name, an older Claude Code or another host) is "unknown"."""
    response = event.get("tool_response")
    found = exit_code_in(response)
    if found is not None:
        return found, "response", {}
    if event.get("host") in ("codex", "opencode"):
        # A post event whose response carries no code (a background task, a tool error) is a
        # gap, never an inferred success. The launcher maps OpenCode's `metadata.exit` in.
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
    cwd, event = os.getcwd(), None
    try:
        event = json.loads(text if text is not None else sys.stdin.buffer.read().decode("utf-8", "replace"))
        cwd = event.get("cwd") or cwd
        root = find_root(cwd)
        if root is None:
            return 0
        emit(HANDLERS[argv[1]](event, root, load_config(root)))
    except InvalidApproval as error:
        emit(deny(str(error)) if argv[1] == "tool" else {"systemMessage": str(error)})
    except Exception as error:  # fail open, but tell the user the gate broke; on_error "deny" blocks
        from gate_run import error_output
        emit(error_output(argv[1], error, cwd, event))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
