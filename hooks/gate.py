"""mycelium-extra plan-approval gate for Claude Code hooks.

Usage (from hooks/hooks.json): gate.py stop | prompt | tool
Reads the hook JSON on stdin. Stdlib-only; runs on Python 3.6+.

Active only in a repository with .mycelium-extra/gate.json. It never emits
"allow": a command passes by the hook staying silent, so the user's own
permission prompts still apply. It catches mistakes; it is not security.
"""

import fnmatch
import hashlib
import json
import os
import re
import shlex
import sys
import time

STATE_DIR = ".mycelium-extra"
DEFAULTS = {
    "gated_paths": ["analysis/**", "nbs/**"],
    "gated_commands": ["sbatch", "snakemake", "nextflow"],
    "approval_hours": 24,
}
EXPLORE_VAR = "MYCELIUM_EXTRA_EXPLORE"
APPROVE = re.compile(r"^\s*approve plan(?: ([0-9a-f]{8}))?\s*[.!]?\s*$", re.IGNORECASE)
EXPLORE_GRANT = re.compile(r"^\s*(allow|stop) explore\s*[.!]?\s*$", re.IGNORECASE)
PLAN_STATUS = re.compile(
    r"^[\s>*_`]*plan status[\s*_`]*:[\s*_`]*(READY_WITH_ASSUMPTIONS|READY|DECISION_REQUIRED)[\s*_`.]*$",
    re.IGNORECASE | re.MULTILINE)
RUNNERS = re.compile(
    r"^(python[\d.]*|Rscript|R|bash|sh|zsh|jupyter|papermill|quarto|julia|perl|node|source|\.)$")
SHELLS = {"bash", "sh", "zsh"}
SCRIPT_EXT = re.compile(r"(\.(py|R|r|sh|ipynb|qmd|Rmd|rmd|jl|smk|pl)$|(^|/)Snakefile$)")
WRAPPERS = {"env", "time", "nohup", "nice", "command", "exec", "stdbuf", "timeout", "srun",
            "conda", "mamba", "micromamba", "pixi", "uv", "run", "xvfb-run"}
VALUE_FLAGS = {"-n", "-p", "--name", "--prefix", "-e", "--environment", "--env",
               "-J", "--job-name", "-t", "--time", "-A", "--account", "--partition"}
WRITERS = {">", ">>", "rm", "mv", "cp", "tee", "touch", "truncate", "ln", "install",
           "rsync", "dd", "chmod", "mkdir", "rmdir"}
PATHLIKE = re.compile(r"[\w./~-]+")


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
    with open(os.path.join(root, STATE_DIR, "gate.json")) as handle:
        config = dict(DEFAULTS)
        config.update(json.load(handle))
    return config


def state_path(root, *parts):
    return os.path.join(root, STATE_DIR, *parts)


def read_json(path, default):
    try:
        with open(path) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as handle:
        json.dump(data, handle, indent=1)
    os.replace(tmp, path)


def emit(payload):
    if payload:
        json.dump(payload, sys.stdout)
        sys.stdout.write("\n")


def safe_session(session_id):
    return re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "unknown")


# ---------------------------------------------------------------- command parsing

def tokenize(command):
    """Split a shell command into words and operator tokens.

    Quote-aware; `$(...)` stays inside its word; heredoc bodies are dropped,
    since they are stdin data, not commands. Newlines become ";".
    """
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
            for delimiter in heredocs:
                while i < n:
                    end = command.find("\n", i)
                    end = n if end < 0 else end
                    line = command[i:end]
                    i = end + 1
                    if line.strip() == delimiter:
                        break
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
                rest = command[i:].lstrip(" \t-")
                m = re.match(r"""['"]?([A-Za-z_][A-Za-z0-9_]*)['"]?""", rest)
                if m:
                    heredocs.append(m.group(1))
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
    found = []
    for word in PATHLIKE.findall(text):
        rel = gated_rel(root, cwd, word, config) if "/" in word or "." in word else None
        if rel:
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
        paths += [p for p in (gated_rel(root, cwd, t, config) for t in rest
                              if not t.startswith("-")) if p]
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


def analyse_command(command, root, cwd, config):
    """Yield (explore, label, paths, segment) for each gated segment."""
    virtual_cwd = cwd
    for tokens in segments(command):
        if tokens[0] == "cd":
            target = tokens[1] if len(tokens) > 1 else os.path.expanduser("~")
            virtual_cwd = os.path.normpath(os.path.join(virtual_cwd, os.path.expanduser(target)))
            continue
        explore, label, paths = classify(tokens, root, virtual_cwd, config)
        if label == "recurse":
            for inner in analyse_command(paths[0], root, virtual_cwd, config):
                yield (inner[0] or explore,) + inner[1:]
            continue
        wraps = [p[5:] for p in paths if p.startswith("wrap:")]
        paths = [p for p in paths if not p.startswith("wrap:")]
        for payload in wraps:
            for inner in analyse_command(payload, root, virtual_cwd, config):
                yield (inner[0] or explore,) + inner[1:]
        if label:
            yield explore, label, paths, " ".join(tokens)


def writes_state(command):
    if STATE_DIR not in command:
        return False
    tokens = tokenize(command)
    words = {os.path.basename(t) for t in tokens}
    if words & WRITERS:
        return True
    if any(RUNNERS.match(w) for w in words):
        return True
    return "sed" in words and any(t.startswith("-i") for t in tokens)


# ---------------------------------------------------------------- approvals

def active_approvals(root, config):
    folder = state_path(root, "approvals")
    horizon = time.time() - float(config["approval_hours"]) * 3600
    approvals = []
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            record = read_json(os.path.join(folder, name), None)
            if record and record.get("approved_at", 0) >= horizon:
                approvals.append(record)
    return approvals


def covered(label, paths, approvals):
    for record in approvals:
        plan = record.get("plan", "")
        if paths:
            if all(path_in_plan(path, plan) for path in paths):
                return True
        elif re.search(r"\b{}\b".format(re.escape(label)), plan):
            return True
    return False


def plan_paths(plan):
    tokens = set()
    for word in PATHLIKE.findall(plan):
        word = word.rstrip(".,;:").rstrip("/")
        if word.startswith("./"):
            word = word[2:]
        if "/" in word:
            tokens.add(word)
    return tokens


def path_in_plan(path, plan):
    named = plan_paths(plan)
    parts = path.split("/")
    return any("/".join(parts[:depth]) in named for depth in range(len(parts), 1, -1))


# ---------------------------------------------------------------- events

def on_tool(event, root, config):
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    state = os.path.realpath(state_path(root))
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
    if writes_state(command):
        return deny("mycelium-extra: this command appears to modify {}/, which holds gate state. "
                    "Reading it is fine; changing it is the user's call.".format(STATE_DIR))
    approvals = None
    blocked = []
    granted = explore_granted(root, event.get("session_id"))
    for explore, label, paths, segment in analyse_command(command, root, event.get("cwd") or root, config):
        if explore and granted:
            log_explore(root, event, segment, paths)
            continue
        if explore:
            return deny("mycelium-extra gate: the exploratory-run prefix works only after the user "
                        "types `allow explore` in this session, and they have not. Do not work "
                        "around this block; ask the user.")
        if approvals is None:
            approvals = active_approvals(root, config)
        if not covered(label, paths, approvals):
            blocked.append((label, paths))
    if not blocked:
        return None
    hashes = ", ".join(r["hash"] for r in approvals) or "none"
    lines = ["mycelium-extra gate: blocked because no active approved plan covers this run."]
    for label, paths in blocked:
        lines.append("  - {}{}".format(label, (" " + ", ".join(paths)) if paths else ""))
    lines.append("Active approved plans (last {} h): {}.".format(config["approval_hours"], hashes))
    lines.append("Present a plan that names these paths and ends with the grill status line; "
                 "the user approves it by typing `approve plan <hash>`. Do not work around this "
                 "block; if the user wants an exploratory run instead, they will say so.")
    return deny("\n".join(lines))


def deny(reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def grant_path(root, session_id):
    return state_path(root, "explore-grants", safe_session(session_id) + ".json")


def explore_granted(root, session_id):
    return os.path.isfile(grant_path(root, session_id))


def log_explore(root, event, segment, paths):
    path = state_path(root, "explore.log")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as handle:
        handle.write(json.dumps({"ts": time.time(), "session_id": event.get("session_id"),
                                 "command": segment, "paths": paths}) + "\n")


def on_prompt(event, root, config):
    prompt = event.get("prompt") or ""
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
        return None
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
        record = {"hash": wanted, "approved_at": time.time(), "session_id": event.get("session_id"),
                  "plan": plan["text"]}
        write_json(state_path(root, "approvals", wanted + ".json"), record)
        message = ("mycelium-extra: plan {} approved. Gated runs whose paths appear in that plan "
                   "may run for {} h.".format(wanted, config["approval_hours"]))
    return {"systemMessage": message,
            "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": message}}


def on_stop(event, root, config):
    notices = []
    text = (event.get("last_assistant_message") or "").strip()
    status = PLAN_STATUS.search(text)
    if status and status.group(1).upper() != "DECISION_REQUIRED":
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
        session = safe_session(event.get("session_id"))
        path = state_path(root, "pending", session + ".json")
        pending = [p for p in read_json(path, []) if p["hash"] != digest]
        pending.append({"hash": digest, "ts": time.time(), "text": text})
        write_json(path, pending[-10:])
        notices.append("mycelium-extra: to approve this plan, type: approve plan " + digest)
    fresh = new_explore_runs(root, event.get("session_id"))
    if fresh:
        notices.append("mycelium-extra: {} exploratory run(s) this session are not reportable: {}".format(
            len(fresh), "; ".join(fresh[:5]) + (" ..." if len(fresh) > 5 else "")))
    return {"systemMessage": "\n".join(notices)} if notices else None


def new_explore_runs(root, session_id):
    log = state_path(root, "explore.log")
    if not os.path.isfile(log):
        return []
    marker = state_path(root, "pending", safe_session(session_id) + ".explore-seen")
    seen = read_json(marker, 0)
    runs = []
    with open(log) as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if record.get("session_id") == session_id:
                runs.append(record["command"])
    if len(runs) > seen:
        write_json(marker, len(runs))
    return runs[seen:]


HANDLERS = {"tool": on_tool, "prompt": on_prompt, "stop": on_stop}


def main(argv):
    if len(argv) != 2 or argv[1] not in HANDLERS:
        print("usage: gate.py stop|prompt|tool", file=sys.stderr)
        return 0
    try:
        event = json.load(sys.stdin)
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
