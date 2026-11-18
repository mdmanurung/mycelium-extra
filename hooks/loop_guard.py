"""Loop guard for the iterate skill: keep a research loop honest. Off unless gate.json says otherwise.

Reads "loops" from .mycelium-extra/gate.json: "off" (default), "warn" or "block". It runs whether the
approval gate is on or off, and it is separate from hooks/gate.py. State is the experiment tree,
<analysis>/plans/tree.jsonl, which skills/iterate/scripts/tree.py writes.

  PreToolUse Bash  a `git commit` on a frozen exp/* branch, or an env-var-prefixed run of the fixed run
                   command (the root node's run command): denied under "block", noted under "warn".
  Stop             a tree whose `stop-check` exits 3 (the stop rule is not met, nothing recorded as a stop):
                   blocked once per turn under "block" (skipped when stop_hook_active), noted under "warn".

Usage: loop_guard.py [--host codex|opencode] tool|stop    (event JSON on stdin; hooks.json calls this)
A hook must never break the session: any error means no reply.
"""

import importlib.util
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = ".mycelium-extra"
BASH_TOOLS = ("Bash", "shell", "exec_command", "shell_command")
ESCAPES = ("Escapes: record a stop with `{mxpy} - --analysis {analysis} stop --reason user < {tree}` (or "
           "`--reason blocker`), or set \"loops\" to \"warn\" in .mycelium-extra/gate.json.")


def find_root(cwd):
    path = os.path.abspath(cwd or ".")
    while True:
        if os.path.isfile(os.path.join(path, STATE_DIR, "gate.json")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def loops_mode(root):
    """off, warn or block. Anything else, or an unreadable gate.json, is off."""
    try:
        with open(os.path.join(root, STATE_DIR, "gate.json"), encoding="utf-8") as handle:
            value = json.load(handle).get("loops", "off")
    except (OSError, ValueError, AttributeError):
        return "off"
    return value if value in ("warn", "block") else "off"


def load_tree_module():
    path = os.path.join(HERE, "..", "skills", "iterate", "scripts", "tree.py")
    spec = importlib.util.spec_from_file_location("iterate_tree", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def trees_of(root):
    """[(analysis, tree)] for every readable tree in the repository."""
    module = load_tree_module()
    out = []
    for path in module.find_trees(root):
        analysis = module.analysis_of(path)
        try:
            out.append((analysis, module.load(analysis)))
        except Exception:  # an unreadable tree is tree.py's to report; the guard stays out of the way
            continue
    return out, module


def current_branch(cwd):
    try:
        out = subprocess.run(["git", "-C", cwd, "symbolic-ref", "--short", "HEAD"], capture_output=True,
                             text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def command_of(event):
    name = event.get("tool_name", "")
    if name.split("__")[-1].split(".")[-1] not in BASH_TOOLS:
        return ""
    data = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    command = data.get("command", data.get("cmd", ""))
    if isinstance(command, list):
        import shlex
        command = " ".join(shlex.quote(str(word)) for word in command)
    return command if isinstance(command, str) else ""


def git_commits(command, cwd):
    """Yield the folder of each `git commit` in the command (a `cd` and git's -C move it)."""
    import shellwords
    folder = cwd
    for tokens in shellwords.segments(command):
        words = list(tokens)
        while words and shellwords.is_assignment(words[0]):
            words.pop(0)
        if not words:
            continue
        if words[0] == "cd" and len(words) > 1:
            folder = os.path.normpath(os.path.join(folder, os.path.expanduser(words[1])))
            continue
        if os.path.basename(words[0]) != "git":
            continue
        where, i = folder, 1
        while i < len(words) and words[i].startswith("-"):
            if words[i] in ("-C", "-c") and i + 1 < len(words):
                if words[i] == "-C":
                    where = os.path.normpath(os.path.join(where, os.path.expanduser(words[i + 1])))
                i += 2
            else:
                i += 1
        if i < len(words) and words[i] == "commit":
            yield where


def env_runs(command, run_cmd):
    """True when a segment runs `run_cmd` behind at least one env-var assignment (`VAR=1 cmd`, `env VAR=1 cmd`)."""
    import shellwords
    import shlex
    try:
        fixed = shlex.split(run_cmd)
    except ValueError:
        return False
    if not fixed:
        return False
    for tokens in shellwords.segments(command):
        words, assigned, via_env = list(tokens), 0, False
        while words:
            if shellwords.is_assignment(words[0]):
                assigned += 1
            elif words[0] == "env":
                via_env = True
            elif not (via_env and words[0].startswith("-")):
                break
            words.pop(0)
        if assigned and words[:len(fixed)] == fixed:
            return True
    return False


def tool_hook(event, mode, root):
    command = command_of(event)
    if not command or ("git" not in command and not any(ch == "=" for ch in command)):
        return {}
    cwd = event.get("cwd") or os.getcwd()
    trees, module = trees_of(root)
    if not trees:
        return {}
    frozen = {}
    for analysis, tree in trees:
        for branch in module.frozen_branches(tree):
            frozen[branch] = analysis
    problems = []
    if frozen and "commit" in command:
        for where in git_commits(command, cwd):
            branch = current_branch(where)
            if branch in frozen:
                problems.append("`git commit` on {}, which is frozen: a run answered that node. Add a child node "
                                "(`tree.py add SLUG --parent ...`), branch from it and commit there.".format(branch))
    for analysis, tree in trees:
        run_cmd = (tree["plan"] or {}).get("run_cmd")
        if run_cmd and "=" in command and env_runs(command, run_cmd):
            problems.append("the fixed run command `{}` was run with an environment variable in front. Nodes "
                            "differ only in committed code or config, never in env vars. Put the value in a "
                            "config file, commit it on the node's branch and run the command as planned.".format(run_cmd))
    if not problems:
        return {}
    text = "loop guard: " + " ".join(problems)
    if mode == "block":
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": text + " The user can set \"loops\" to "
                                       "\"warn\" or \"off\" in .mycelium-extra/gate.json."}}
    return {"systemMessage": text, "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": text}}


def stop_hook(event, mode, root):
    if event.get("stop_hook_active"):
        return {}  # one block per turn
    trees, module = trees_of(root)
    lines = []
    for analysis, tree in trees:
        code, message = module.stop_check(tree)
        if code == 3:
            lines.append("{}: {} {}".format(os.path.relpath(analysis, root) or ".", message,
                                             ESCAPES.format(mxpy=os.path.join(HERE, "mxpy"), tree=os.path.join(
                                                 HERE, "..", "skills", "iterate", "scripts", "tree.py"),
                                             analysis=os.path.relpath(analysis, root) or ".")))
    if not lines:
        return {}
    text = "loop guard: the research loop is not finished. " + " ".join(lines)
    if mode == "block":
        return {"decision": "block", "reason": text}
    return {"systemMessage": text}


def main(argv):
    args = list(argv)
    if args[:1] == ["--host"]:
        args = args[2:]
    action = args[-1] if args else ""
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))
        if not isinstance(event, dict) or action not in ("tool", "stop"):
            return 0
        root = find_root(event.get("cwd") or os.getcwd())
        mode = loops_mode(root) if root else "off"
        if mode == "off":
            return 0
        sys.path.insert(0, HERE)
        reply = (tool_hook if action == "tool" else stop_hook)(event, mode, root)
    except Exception:
        return 0
    if reply:
        print(json.dumps(reply))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
