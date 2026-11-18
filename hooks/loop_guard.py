"""Loop guard for the iterate skill: keep a research loop honest. Off unless gate.json says otherwise.

Reads "loops" from .mycelium-extra/gate.json: "off" (default), "warn" or "block". It runs whether the
approval gate is on or off, and it is separate from hooks/gate.py. State is the experiment tree,
<analysis>/plans/tree.jsonl, which skills/iterate/scripts/tree.py writes.

  PreToolUse Bash  a git call that commits (commit, merge, cherry-pick, revert, rebase, am, pull, or an alias
                   of one) on a frozen exp/* branch, or the fixed run command (the root node's run command)
                   run with env vars set in front of it: denied under "block", noted under "warn".
  Stop             a tree whose `stop-check` exits 3 (the stop rule is not met, nothing recorded as a stop):
                   blocked once per tree state under "block" (skipped when stop_hook_active), noted under
                   "warn". A turn that left the tree unchanged since the last report is not stopped again.

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
SEEN = "loop_guard_seen.json"
ESCAPES = ("Only the user ends the loop. Ask the user whether to continue or stop, and record a stop (the "
           "iterate skill's `tree.py stop`) only when the user says so. The user can also set \"loops\" to "
           "\"warn\" in .mycelium-extra/gate.json.")


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


def current_branch(cwd, git_dir=None):
    base = ["git", "--git-dir=" + git_dir] if git_dir else ["git", "-C", cwd]
    try:
        out = subprocess.run(base + ["symbolic-ref", "--short", "HEAD"], capture_output=True,
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


# Words that open or close a compound command, wrappers that run the next command, and git's own options.
OPENERS = {"{", "}", "(", ")", "if", "then", "else", "elif", "fi", "do", "done", "while", "until", "!", "time",
           "sudo"}
PREFIX_WRAPPERS = {"env", "command", "nohup", "exec", "nice", "setsid", "timeout", "stdbuf", "ionice"}
WRAPPER_VALUE_FLAGS = {"-u", "--unset", "-C", "--chdir", "-n", "--adjustment", "-k", "--kill-after", "-s",
                       "--signal", "-i", "-o", "-e"}
GIT_VALUE_OPTIONS = {"--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env", "--attr-source"}
# Subcommands that put a commit on the branch that is checked out.
COMMITTING = {"commit", "merge", "cherry-pick", "revert", "rebase", "am", "pull"}
# Variables that change how a run is shown or where it is placed, never what it computes.
HARMLESS_ENV = {"PYTHONUNBUFFERED", "PYTHONDONTWRITEBYTECODE", "PYTHONIOENCODING", "PYTHONWARNINGS", "NO_COLOR",
                "TERM", "CUDA_VISIBLE_DEVICES"}


def simple_commands(command, folder, env=frozenset(), depth=0):
    """Yield (words, folder, env) for each simple command: wrappers and block words stripped, `sh -c` bodies
    followed, `cd` tracked. `env` is the set of variable names assigned in front of the command, by `env`, by
    an earlier `export`, or by an outer command."""
    import shellwords
    env = set(env)
    for tokens in shellwords.segments(command):
        words, own = list(tokens), set()
        while words:
            word = words[0]
            if shellwords.is_assignment(word):
                own.add(word.split("=", 1)[0])
                words.pop(0)
            elif word in OPENERS:
                words.pop(0)
            elif os.path.basename(word) in PREFIX_WRAPPERS:
                words.pop(0)
                while words and (words[0].startswith("-") or shellwords.DURATION.match(words[0])
                                 or (word == "env" and shellwords.is_assignment(words[0]))):
                    if shellwords.is_assignment(words[0]):
                        own.add(words[0].split("=", 1)[0])
                    value = words[0] in WRAPPER_VALUE_FLAGS
                    words.pop(0)
                    if value and words:
                        words.pop(0)
            else:
                break
        if not words:
            env |= own  # a bare `A=1` sets a shell variable for the commands after it
            continue
        head = os.path.basename(words[0])
        if head in ("export", "declare", "typeset", "readonly"):
            env |= {w.split("=", 1)[0] for w in words[1:] if "=" in w}
        elif head == "cd" and len(words) > 1:
            folder = os.path.normpath(os.path.join(folder, os.path.expanduser(words[1])))
        elif head in shellwords.SHELLS and depth < 4:
            for i, word in enumerate(words[1:], 1):
                if shellwords.SHELL_C.match(word) and i + 1 < len(words):
                    yield from simple_commands(words[i + 1], folder, env | own, depth + 1)
                    break
        elif head == "eval" and depth < 4:
            yield from simple_commands(" ".join(words[1:]), folder, env | own, depth + 1)
        yield words, folder, env | own


def git_calls(command, cwd):
    """Yield (where, git_dir, subcommand, words, inline_aliases) for each `git` call in the command."""
    for words, folder, _env in simple_commands(command, cwd):
        if os.path.basename(words[0]) != "git":
            continue
        where, git_dir, aliases, i = folder, None, {}, 1
        while i < len(words) and words[i].startswith("-"):
            word = words[i]
            if word in ("-C", "-c") and i + 1 < len(words):
                if word == "-C":
                    where = os.path.normpath(os.path.join(where, os.path.expanduser(words[i + 1])))
                elif words[i + 1].lower().startswith("alias.") and "=" in words[i + 1]:
                    name, value = words[i + 1][6:].split("=", 1)
                    aliases[name] = value
                i += 2
            elif word in GIT_VALUE_OPTIONS and i + 1 < len(words):
                git_dir = os.path.join(where, os.path.expanduser(words[i + 1])) if word == "--git-dir" else git_dir
                i += 2
            else:
                if word.startswith("--git-dir="):
                    git_dir = os.path.join(where, os.path.expanduser(word.split("=", 1)[1]))
                i += 1
        if i < len(words):
            yield where, git_dir, words[i], words[i + 1:], aliases


def configured_aliases(where, git_dir):
    """The repository's `alias.*` settings as {name: value}."""
    base = ["git", "--git-dir=" + git_dir] if git_dir else ["git", "-C", where]
    try:
        out = subprocess.run(base + ["config", "--get-regexp", "^alias[.]"], capture_output=True, text=True,
                             timeout=5)
    except (OSError, subprocess.SubprocessError):
        return {}
    pairs = (line.split(None, 1) for line in out.stdout.splitlines())
    return {pair[0][6:]: pair[1] if len(pair) > 1 else "" for pair in pairs}


def makes_commit(where, git_dir, sub, rest, inline):
    """True when this git call puts a commit on the checked-out branch, through an alias too."""
    if "--abort" in rest or "--quit" in rest:
        return False
    for _ in range(3):  # an alias may name another alias
        if sub in COMMITTING:
            return True
        aliases = dict(configured_aliases(where, git_dir), **inline)
        value = aliases.get(sub)
        if value is None:
            return False
        if value.startswith("!"):
            return any(os.path.basename(w[0]) == "git" and bool(w[1:]) and w[1] in COMMITTING
                       for w, _f, _e in simple_commands(value[1:], where))
        sub = (value.split() or [""])[0]
    return False


def same_command(words, fixed):
    """True when `words` start with the fixed command, with python/python3 and `./x` spelled alike."""
    import re
    if len(words) < len(fixed):
        return False
    for given, planned in zip(words, fixed):
        if given == planned:
            continue
        if re.match(r"^python[\d.]*$", os.path.basename(given)) and re.match(r"^python[\d.]*$", planned):
            continue
        if "/" in given or "/" in planned:
            if os.path.normpath(given) == os.path.normpath(planned):
                continue
        return False
    return True


def env_runs(command, run_cmd, cwd="."):
    """The variable names run in front of `run_cmd` (`VAR=1 cmd`, `env VAR=1 cmd`, an earlier `export`, `sh -c`,
    `nohup`), without the harmless display and device ones. Empty when there are none."""
    import shlex
    try:
        fixed = shlex.split(run_cmd)
    except ValueError:
        return set()
    if not fixed:
        return set()
    names = set()
    for words, _folder, env in simple_commands(command, cwd):
        if same_command(words, fixed):
            names |= env - HARMLESS_ENV
    return names


def tool_hook(event, mode, root):
    command = command_of(event)
    if not command or ("git" not in command and "=" not in command):
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
    if frozen and "git" in command:
        for where, git_dir, sub, rest, inline in git_calls(command, cwd):
            branch = current_branch(where, git_dir)
            if branch in frozen and makes_commit(where, git_dir, sub, rest, inline):
                problems.append("`git {}` on {}, which is frozen: a run answered that node. Add a child node "
                                "(`tree.py add SLUG --parent ...`), branch from it and commit there.".format(
                                    sub, branch))
    for analysis, tree in trees:
        run_cmd = (tree["plan"] or {}).get("run_cmd")
        names = env_runs(command, run_cmd, cwd) if run_cmd and "=" in command else set()
        if names:
            problems.append("the fixed run command `{}` was run with {} in front. Nodes differ only in "
                            "committed code or config, never in env vars. Put the value in a config file, "
                            "commit it on the node's branch and run the command as planned.".format(
                                run_cmd, ", ".join(sorted(names))))
    if not problems:
        return {}
    text = "loop guard: " + " ".join(problems)
    if mode == "block":
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": text + " The user can set \"loops\" to "
                                       "\"warn\" or \"off\" in .mycelium-extra/gate.json."}}
    return {"systemMessage": text, "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": text}}


def seen_before(root, key, fingerprint):
    """True when this tree state was already reported. Records it otherwise, so a state is reported once."""
    path = os.path.join(root, STATE_DIR, SEEN)
    try:
        with open(path, encoding="utf-8") as handle:
            seen = json.load(handle)
    except (OSError, ValueError):
        seen = {}
    if not isinstance(seen, dict):
        seen = {}
    if seen.get(key) == fingerprint:
        return True
    seen[key] = fingerprint
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(seen, handle)
    except OSError:
        pass
    return False


def stop_hook(event, mode, root):
    if event.get("stop_hook_active"):
        return {}  # one block per turn
    trees, module = trees_of(root)
    lines = []
    for analysis, tree in trees:
        code, message = module.stop_check(tree)
        if code != 3:
            continue
        where = os.path.relpath(analysis, root) or "."
        try:
            stat = os.stat(module.tree_path(analysis))
            fingerprint = "{}:{}".format(stat.st_size, stat.st_mtime_ns)
        except OSError:
            continue
        # a tree is reported once per state: a turn that did not touch the loop is not stopped again
        if not seen_before(root, where, fingerprint):
            lines.append("{}: {}".format(where, message))
    if not lines:
        return {}
    text = "loop guard: the research loop is not finished. " + " ".join(lines) + " " + ESCAPES
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
