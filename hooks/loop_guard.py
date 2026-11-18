"""Loop guard for the iterate skill: keep a research loop honest. Off unless gate.json says otherwise.

Reads "loops" from .mycelium-extra/gate.json: "off" (default), "warn" or "block". It runs whether the
approval gate is on or off, and it is separate from hooks/gate.py. State is the experiment tree,
<analysis>/plans/tree.jsonl, which skills/iterate/scripts/tree.py writes.

  PreToolUse Bash  a git call that commits (commit, merge, cherry-pick, revert, rebase, am, pull, or an alias
                   of one) on a frozen exp/* branch (HEAD is followed through a checkout or switch earlier in
                   the command), a call that moves a frozen branch (branch -f/-m/-d, update-ref, push . or
                   fetch . into it, checkout -B, switch -C, reset), or the fixed run command (the root node's run command)
                   run with env vars set in front of it: denied under "block", noted under "warn".
  PreToolUse       Write, Edit, MultiEdit, NotebookEdit (apply_patch on Codex; edit, write and patch on OpenCode)
  edit tools       that name a file the method tree's `freeze-evaluator` hashed: denied under "block", noted under
                   "warn". Only these tools are checked; `tree.py check-evaluator` and the Stop hook catch the rest.
  Stop             a tree whose `stop-check` exits 3 (the stop rule or iteration floor is not met, nothing recorded
                   as a stop), a hashed evaluator file that changed (hashed inside the Stop budget, with a
                   size+mtime cache), or a tusoskill run (a state/state.json of its
                   shape) whose own `stop-check` exits 3: blocked once per state under "block" (skipped when
                   stop_hook_active), noted under "warn". A turn that left the state unchanged since the last
                   report is not stopped again. The tusoskill script is found at
                   ~/.claude/skills/tusoskill/scripts/biomni_method_state.py, or at $MYCELIUM_TUSOSKILL_SCRIPT;
                   when it is absent the bridge is silent.

Usage: loop_guard.py [--host codex|opencode] tool|stop    (event JSON on stdin; hooks.json calls this)
A hook must never break the session: any error means no reply.
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = ".mycelium-extra"
BASH_TOOLS = ("Bash", "shell", "exec_command", "shell_command")
SEEN = "loop_guard_seen.json"
EDIT_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit", "apply_patch", "write", "edit", "patch")
PATCH_FILE = re.compile(r"^\*\*\* (?:Add File|Update File|Delete File|Move to):\s*(.+?)\s*$", re.M)
STOP_BUDGET = float(os.environ.get("MYCELIUM_LOOP_STOP_BUDGET", 7))  # seconds for the whole Stop handler; hooks.json and codex.json allow 10
HASHES = "loop_guard_hashes.json"  # size, mtime and sha256 of each evaluator file the Stop handler hashed
TUSO_TIMEOUT = 8  # seconds for one stop-check
TUSO_ENV = "MYCELIUM_TUSOSKILL_SCRIPT"
TUSO_SCRIPT = os.path.join("~", ".claude", "skills", "tusoskill", "scripts", "biomni_method_state.py")
SKIP_FOLDERS = {"data", "node_modules", "renv", "venv", "env"}
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
OPENERS = {"{", "}", "(", ")", "if", "then", "else", "elif", "fi", "do", "done", "while", "until", "!"}
# Wrappers that run the next command. Their options that take a value (the value is not the command) come from
# the gate's tables in hooks/shellwords.py, plus the ones listed here.
PREFIX_WRAPPERS = {"env", "command", "nohup", "exec", "nice", "setsid", "timeout", "stdbuf", "ionice", "sudo", "time",
                   "srun", "xargs", "uv", "uvx", "conda", "mamba", "micromamba", "pixi"}
RUN_SUBCOMMAND = {"uv", "conda", "mamba", "micromamba", "pixi"}  # `uv run CMD`, `conda run -n e CMD`
EXTRA_VALUE_FLAGS = {
    "timeout": {"-k", "--kill-after", "-s", "--signal"}, "nice": {"-n", "--adjustment"},
    "stdbuf": {"-i", "-o", "-e", "--input", "--output", "--error"},
    "sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "-r", "-t", "-U", "-R", "-T", "--user", "--group", "--host",
             "--prompt", "--close-from", "--chdir", "--role", "--type", "--other-user", "--chroot", "--command-timeout"},
    "time": {"-f", "--format", "-o", "--output"},
}
GIT_VALUE_OPTIONS = {"--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env", "--attr-source"}
# Subcommands that put a commit on the branch that is checked out.
COMMITTING = {"commit", "merge", "cherry-pick", "revert", "rebase", "am", "pull"}
# Variables that change how a run is shown or where it is placed, never what it computes.
HARMLESS_ENV = {"PYTHONUNBUFFERED", "PYTHONDONTWRITEBYTECODE", "PYTHONIOENCODING", "PYTHONWARNINGS", "NO_COLOR",
                "TERM", "CUDA_VISIBLE_DEVICES"}


def wrapper_value_flags(wrapper):
    import shellwords
    return shellwords.WRAPPER_OPTIONS.get(wrapper, (set(), set()))[0] | EXTRA_VALUE_FLAGS.get(wrapper, set())


def expand_variables(word, values):
    """`word` with `$NAME` and `${NAME}` replaced by the literal value of an earlier bare assignment."""
    if "$" not in word or not values:
        return word
    return re.sub(r"\$(?:\{([A-Za-z_]\w*)\}|([A-Za-z_]\w*))",
                  lambda m: values.get(m.group(1) or m.group(2), m.group(0)), word)


def simple_commands(command, folder, env=frozenset(), depth=0):
    """Yield (words, folder, env) for each simple command: wrappers and block words stripped, `sh -c` bodies,
    shell heredocs and container `exec` commands followed, `cd` tracked, and a `( ... )` subshell scoped. `env` is
    the set of variable names assigned in front of the command, by `env`, by an earlier `export`, by a bare
    assignment of a variable that is already exported, or by an outer command."""
    import shellwords
    env, exported, stack = set(env), set(), []
    values, assigned, allexport = {}, set(), False  # literal values of bare assignments; shell-only variable names
    # a `( ... )` subshell keeps its own exports, assignments and `set -a`; they end with it
    for tokens, opened, closed, heredocs, _before in shellwords.scoped_segments(command):
        for _ in range(closed):
            if stack:
                folder, env, values, exported, assigned, allexport = stack.pop()
        for _ in range(opened):
            stack.append((folder, set(env), dict(values), set(exported), set(assigned), allexport))
        words, own, own_values = list(tokens), set(), {}
        while words:
            word = words[0]
            if shellwords.is_assignment(word):
                name, _eq, value = word.partition("=")
                own.add(name)
                own_values[name] = value
                words.pop(0)
            elif word in OPENERS:
                words.pop(0)
            elif os.path.basename(word) in PREFIX_WRAPPERS:
                wrapper = os.path.basename(word)
                words.pop(0)
                if wrapper in RUN_SUBCOMMAND and words[:1] == ["run"]:
                    words.pop(0)
                value_flags = wrapper_value_flags(wrapper)
                while words and (words[0].startswith("-") or shellwords.DURATION.match(words[0])
                                 or (wrapper == "env" and shellwords.is_assignment(words[0]))):
                    if shellwords.is_assignment(words[0]):
                        own.add(words[0].split("=", 1)[0])
                    value = words[0] in value_flags
                    words.pop(0)
                    if value and words:
                        words.pop(0)
            else:
                break
        if not words:
            # a bare `A=1` sets a shell variable for the commands after it; the child sees it only when A is
            # already exported (by the host's environment or an earlier `export A`)
            env |= {name for name in own if allexport or name in os.environ or name in env or name in exported}
            assigned |= own
            values.update({name: value for name, value in own_values.items() if "$" not in value})
            continue
        words = [expand_variables(word, values) for word in words]
        head = os.path.basename(words[0])
        if head in ("export", "declare", "typeset", "readonly"):
            env |= {w.split("=", 1)[0] for w in words[1:] if "=" in w}
            if head == "export" or (head in ("declare", "typeset") and any(
                    re.match(r"^-[A-Za-z]*x", w) for w in words[1:] if w.startswith("-"))):
                names = {w for w in words[1:] if w.isidentifier()}
                exported |= names  # `export A`: a later `A=1` reaches the child
                env |= names & assigned  # `A=1; export A`: it reaches the child now
        elif head == "set":
            for word in words[1:]:
                if re.match(r"^-[A-Za-z]*a", word):
                    allexport = True  # `set -a`: every later assignment is exported
                elif re.match(r"^\+[A-Za-z]*a", word):
                    allexport = False
            if "allexport" in words[1:] and "-o" in words[1:]:
                allexport = True
        elif head == "cd" and len(words) > 1:
            folder = os.path.normpath(os.path.join(folder, os.path.expanduser(words[1])))
        elif head in shellwords.SHELLS and depth < 4:
            inline = False
            for i, word in enumerate(words[1:], 1):
                if shellwords.SHELL_C.match(word) and i + 1 < len(words):
                    inline = True
                    yield from simple_commands(words[i + 1], folder, env | own, depth + 1)
                    break
            if not inline and any(heredocs):  # `bash <<'EOF' ... EOF` runs the heredoc as a script
                yield from simple_commands("\n".join(heredocs), folder, env | own, depth + 1)
        elif head == "eval" and depth < 4:
            yield from simple_commands(" ".join(words[1:]), folder, env | own, depth + 1)
        elif head in shellwords.CONTAINERS and depth < 4:  # `apptainer exec IMG CMD`: CMD runs with the host's env
            import shlex
            for j, word in enumerate(words[1:], 1):
                if os.path.basename(word) == "git" or shellwords.RUNNERS.match(os.path.basename(word)):
                    yield from simple_commands(" ".join(shlex.quote(w) for w in words[j:]), folder, env | own,
                                               depth + 1)
                    break
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


# Options whose next word is a value, so a value like `--help` in a commit message is not an option.
VALUE_OPTIONS = {"-m", "-F", "-C", "-c", "-S", "--message", "--file", "--author", "--date", "--reuse-message",
                 "--reedit-message", "-X", "-s", "--strategy", "--strategy-option", "--onto", "-x", "--exec"}
# Options that make a commit, merge, rebase or pull end without a commit: abort, usage text, preview.
NO_COMMIT_OPTIONS = {"--abort", "--quit", "--dry-run", "--help", "-h"}


def options_of(rest):
    """The option words of a git call, up to `--`, without the values of options that take one."""
    found, skip = set(), False
    for word in rest:
        if skip:
            skip = False
        elif word == "--":
            break
        elif word in VALUE_OPTIONS:
            skip = True
        elif word.startswith("-"):
            found.add(word)
    return found


def makes_commit(where, git_dir, sub, rest, inline):
    """True when this git call puts a commit on the checked-out branch, through an alias too."""
    if options_of(rest) & NO_COMMIT_OPTIONS:
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


KNOWN_SUBCOMMANDS = COMMITTING | {"checkout", "switch", "reset", "branch", "update-ref", "push", "fetch"}
KEEP = object()  # a checkout or switch that leaves the branch where it was


def has_branch(where, git_dir, name):
    base = ["git", "--git-dir=" + git_dir] if git_dir else ["git", "-C", where]
    try:
        return subprocess.run(base + ["show-ref", "--verify", "--quiet", "refs/heads/" + name], timeout=5,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def rev_parse(where, git_dir, *args):
    """The one-line output of `git rev-parse ARGS`, or None when git fails."""
    base = ["git", "--git-dir=" + git_dir] if git_dir else ["git", "-C", where]
    try:
        out = subprocess.run(base + ["rev-parse"] + list(args), timeout=5, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, universal_newlines=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else None


def commit_of(where, git_dir, name):
    """The commit a name resolves to, or None."""
    return rev_parse(where, git_dir, "--verify", "--quiet", name + "^{commit}")


def repo_key(where, git_dir):
    """One key per repository (its absolute git dir), so a `cd` into a subfolder keeps the same HEAD."""
    return git_dir or rev_parse(where, None, "--absolute-git-dir") or where


def real_subcommand(where, git_dir, sub, rest, inline):
    """(subcommand, rest) with a git alias of a built-in followed, so `git co exp/a` is a checkout."""
    for _ in range(3):
        if sub in KNOWN_SUBCOMMANDS:
            break
        value = dict(configured_aliases(where, git_dir), **inline).get(sub)
        if not value or value.startswith("!"):
            break
        words = value.split()
        sub, rest = words[0], words[1:] + list(rest)
    return sub, rest


UNSET = object()  # no checkout earlier in the command, so `-` is read from the repository


def switch_target(where, git_dir, sub, rest, previous=UNSET):
    """(branch, forced) HEAD is on after a `git checkout` or `git switch`: the new branch's name, None when HEAD is
    detached, or KEEP when the branch does not change (a path checkout, or a name that is not a local branch).
    `forced` is true for -B, -C and --force-create, which reset a branch that exists. `-` is `previous` when the
    command checked out a branch before, else the repository's `@{-1}` now."""
    create, forced, detach, positional = None, False, False, []
    i = 0
    while i < len(rest):
        word = rest[i]
        if word == "--":
            if sub == "checkout" and positional and not create:
                return KEEP, False  # `git checkout BRANCH -- path` restores files
            break
        if word in ("-b", "-c", "--create", "--orphan", "-B", "-C", "--force-create") and i + 1 < len(rest):
            create, forced = rest[i + 1], word in ("-B", "-C", "--force-create")
            i += 2
            continue
        if word in ("-d", "--detach"):
            detach = True
        elif word == "-":  # the previous branch
            back = rev_parse(where, git_dir, "--abbrev-ref", "@{-1}") if previous is UNSET else previous
            positional.append(back or word)
        elif not word.startswith("-"):
            positional.append(word)
        i += 1
    if create:
        return create, forced
    if detach:
        return None, False
    if positional and has_branch(where, git_dir, positional[0]):
        return positional[0], False
    return KEEP, False


def ref_moves(where, git_dir, sub, rest, branch, frozen, previous=UNSET):
    """Frozen branches this git call moves, rewrites, renames or deletes without committing: `branch -f`, `-m`, `-d`,
    `update-ref`, `push .` and `fetch .` into the branch, a `reset` of the checked-out frozen branch to another
    commit, and `checkout -B` or `switch -C` of it. Not covered: `rebase BASE exp/a` from another branch,
    `symbolic-ref`, `git worktree`, and writes to `.git` by other tools."""
    flags, positional = set(), []
    for word in rest:
        if word == "--":
            break
        if word.startswith("--"):
            flags.add(word.split("=", 1)[0])
        elif word.startswith("-") and len(word) > 1:
            flags |= {"-" + letter for letter in word[1:]}
        else:
            positional.append(word)
    if sub == "branch":
        if flags & {"-m", "-M", "--move", "-d", "-D", "--delete"}:
            hit = [name for name in positional if name in frozen]
            if flags & {"-m", "-M", "--move"} and len(positional) == 1 and branch in frozen:
                hit.append(branch)  # `git branch -m NEW` renames the checked-out branch
            return hit
        if flags & {"-c", "-C", "--copy"}:
            return [positional[-1]] if positional and positional[-1] in frozen else []
        if flags & {"-f", "--force"}:
            return [positional[0]] if positional and positional[0] in frozen else []
    elif sub == "update-ref":
        return [name for name in frozen if "refs/heads/" + name in positional]
    elif sub in ("push", "fetch") and positional[:1] == ["."]:
        targets = [spec.lstrip("+").split(":")[-1] for spec in positional[1:] if ":" in spec]
        return [name for name in frozen if name in targets or "refs/heads/" + name in targets]
    elif sub == "reset" and branch in frozen:
        # `reset COMMIT -- PATH`, `reset COMMIT PATH` and `reset -p` restore files: HEAD stays
        paths = len(positional) > 1 or ("--" in rest and rest.index("--") < len(rest) - 1) \
            or flags & {"-p", "--patch", "--pathspec-from-file"}
        target = commit_of(where, git_dir, positional[0]) if positional and not paths else None
        return [branch] if target and target != commit_of(where, git_dir, "HEAD") else []
    elif sub in ("checkout", "switch"):
        name, forced = switch_target(where, git_dir, sub, rest, previous)
        return [name] if forced and name in frozen else []
    return []


PYTHON = re.compile(r"^python[\d.]*$")
PYTHON_VALUE_FLAGS = {"-X", "-W"}


def same_command(words, fixed, folder=".", cwd="."):
    """True when `words` start with the fixed command, with python/python3 and `./x` spelled alike, an interpreter
    option such as `python -u` skipped, and a script path read from the folder the command runs in (`cd code &&
    python run.py`) or as an absolute path."""
    words = list(words)
    if len(fixed) > 1 and PYTHON.match(os.path.basename(words[0])) and PYTHON.match(fixed[0]) \
            and not fixed[1].startswith("-"):
        while len(words) > 1 and words[1].startswith("-"):
            del words[1:3 if words[1] in PYTHON_VALUE_FLAGS else 2]
    if len(words) < len(fixed):
        return False
    for given, planned in zip(words, fixed):
        if given == planned:
            continue
        if PYTHON.match(os.path.basename(given)) and PYTHON.match(planned):
            continue
        if "/" in given or "/" in planned or (os.path.splitext(given)[1] and os.path.splitext(planned)[1]):
            if os.path.normpath(given) == os.path.normpath(planned):
                continue
            if os.path.abspath(os.path.join(folder, given)) == os.path.abspath(os.path.join(cwd, planned)):
                continue
        return False
    return True


def env_runs(command, run_cmd, cwd="."):
    """The variable names run in front of `run_cmd` (`VAR=1 cmd`, `env VAR=1 cmd`, an earlier `export`, `sh -c`,
    `nohup`, `srun`, `uv run`, `conda run`, a container `exec`), without the harmless display and device ones.
    Empty when there are none."""
    import shlex
    try:
        fixed = shlex.split(run_cmd)
    except ValueError:
        return set()
    if not fixed:
        return set()
    names = set()
    for words, folder, env in simple_commands(command, cwd):
        if same_command(words, fixed, folder, cwd):
            names |= env - HARMLESS_ENV
    return names


def edit_targets(event):
    """Absolute paths a file-edit tool call names, or [] for any other tool."""
    name = event.get("tool_name", "").split("__")[-1].split(".")[-1]
    if name not in EDIT_TOOLS:
        return []
    data = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    found = [data[key] for key in ("file_path", "filePath", "path", "notebook_path")
             if isinstance(data.get(key), str) and data[key]]
    for key in ("command", "patch", "patchText", "input"):
        if isinstance(data.get(key), str):
            found += PATCH_FILE.findall(data[key])
    base = event.get("cwd") or os.getcwd()
    return [os.path.realpath(os.path.join(base, os.path.expanduser(path))) for path in found]


def evaluator_problems(event, root):
    """One message per hashed evaluator file the edit call names."""
    paths = edit_targets(event)
    if not paths:
        return []
    trees, module = trees_of(root)
    problems = []
    for analysis, tree in trees:
        hashed = {os.path.realpath(path): path for path in module.evaluator_files(tree, analysis)}
        for path in paths:
            if path in hashed:
                problems.append("{} is a hashed evaluator file of {}: it was frozen so the benchmark cannot move "
                                "under the candidates. Do not edit it. If the user wants it changed, the user "
                                "sets \"loops\" to \"warn\" for that edit, and you then re-freeze with "
                                "`tree.py freeze-evaluator --refreeze --note \"<what changed, user agreed>\"`.".format(
                                    os.path.relpath(hashed[path], root), os.path.relpath(analysis, root) or "."))
    return problems


def respond(problems, mode):
    text = "loop guard: " + " ".join(problems)
    if mode == "block":
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": text + " The user can set \"loops\" to "
                                       "\"warn\" or \"off\" in .mycelium-extra/gate.json."}}
    return {"systemMessage": text, "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": text}}


def tool_hook(event, mode, root):
    if edit_targets(event):
        problems = evaluator_problems(event, root)
        return respond(problems, mode) if problems else {}
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
        heads, backs = {}, {}  # repository -> the branch HEAD is on, and the one before it, after a checkout or switch
        # earlier in this command
        for where, git_dir, sub, rest, inline in git_calls(command, cwd):
            key = repo_key(where, git_dir)
            sub, rest = real_subcommand(where, git_dir, sub, rest, inline)
            branch = heads[key] if key in heads else current_branch(where, git_dir)
            if branch in frozen and makes_commit(where, git_dir, sub, rest, inline):
                problems.append("`git {}` on {}, which is frozen: a run answered that node. Add a child node "
                                "(`tree.py add SLUG --parent ...`), branch from it and commit there.".format(
                                    sub, branch))
            back = backs.get(key, UNSET)
            for name in ref_moves(where, git_dir, sub, rest, branch, frozen, back):
                problems.append("`git {}` moves {}, which is frozen: a run answered that node, so its branch stays "
                                "as it was. Add a child node (`tree.py add SLUG --parent ...`) and branch "
                                "from it.".format(sub, name))
            if sub in ("checkout", "switch"):
                moved, _forced = switch_target(where, git_dir, sub, rest, back)
                if moved is not KEEP:
                    heads[key], backs[key] = moved, branch
    for analysis, tree in trees:
        run_cmd = (tree["plan"] or {}).get("run_cmd")
        names = env_runs(command, run_cmd, cwd) if run_cmd and "=" in command else set()
        if names:
            problems.append("the fixed run command `{}` was run with {} in front. Nodes differ only in "
                            "committed code or config, never in env vars. Put the value in a config file, "
                            "commit it on the node's branch and run the command as planned.".format(
                                run_cmd, ", ".join(sorted(names))))
    problems = list(dict.fromkeys(problems))  # two trees sharing a run command give one sentence
    return respond(problems, mode) if problems else {}


def seen_before(root, key, fingerprint, record=True):
    """True when this tree state was already reported. Records it otherwise (unless `record` is false), so a state
    is reported once."""
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
    if not record:
        return False
    seen[key] = fingerprint
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(seen, handle)
    except OSError:
        pass
    return False


def tusoskill_runs(root):
    """Run folders within three levels of `root` whose state/state.json has tusoskill's shape: a run id and the
    integer counters `iteration` and `max_iterations`."""
    found, level = [], [os.path.abspath(root)]
    for _ in range(3):
        for folder in level:
            try:
                with open(os.path.join(folder, "state", "state.json"), encoding="utf-8") as handle:
                    state = json.load(handle)
            except (OSError, ValueError):
                continue
            ints = [state.get(k) for k in ("iteration", "max_iterations")] if isinstance(state, dict) else []
            if len(ints) == 2 and all(isinstance(v, int) and not isinstance(v, bool) for v in ints) \
                    and isinstance(state.get("run_id"), str):
                found.append(folder)
        level = [os.path.join(f, d) for f in level for d in _subfolders(f)]
    return found


def _subfolders(path):
    try:
        return sorted(n for n in os.listdir(path)
                      if not n.startswith(".") and n not in SKIP_FOLDERS and os.path.isdir(os.path.join(path, n)))
    except OSError:
        return []


def _run_fingerprint(run):
    """Size and mtime of every file in the run's state folder (state.json, ledgers, blocker), or None."""
    folder = os.path.join(run, "state")
    try:
        names = sorted(n for n in os.listdir(folder) if os.path.isfile(os.path.join(folder, n)))
        return ";".join("{}:{}:{}".format(n, os.stat(os.path.join(folder, n)).st_size,
                                          os.stat(os.path.join(folder, n)).st_mtime_ns) for n in names)
    except OSError:
        return None


def tusoskill_lines(root, deadline=None, tag=""):
    """(messages, unchecked, slow) for the tusoskill runs. A run is checked once per state (fingerprint of its state
    folder), so a Stop with nothing changed does not rerun its stop-check. Each check gets at most TUSO_TIMEOUT
    seconds and none starts after `deadline` (a time.monotonic() value); runs not started are listed in `unchecked`
    and are tried at the next Stop. A run whose check timed out is listed in `slow` and recorded as seen, so a slow
    check costs the budget once per state, not on every Stop.
    Nothing when its script is absent or a state file does not have its shape; its code is run, never copied."""
    script = os.path.expanduser(os.environ.get(TUSO_ENV) or TUSO_SCRIPT)
    if not os.path.isfile(script):
        return [], [], []
    out, unchecked, slow = [], [], []
    for run in tusoskill_runs(root):
        where = os.path.relpath(run, root) or "."
        key, fingerprint = "{}:tusoskill".format(where), _run_fingerprint(run)
        fingerprint = None if fingerprint is None else fingerprint + tag  # a state noted under warn is new under block
        if fingerprint is None or seen_before(root, key, fingerprint, record=False):
            continue
        left = None if deadline is None else deadline - time.monotonic()
        if left is not None and left <= 0:
            unchecked.append(where)
            continue
        try:
            check = subprocess.run([sys.executable, script, "stop-check", "--root", run], capture_output=True,
                                   text=True, timeout=TUSO_TIMEOUT if left is None else min(TUSO_TIMEOUT, left))
        except subprocess.TimeoutExpired:
            seen_before(root, key, fingerprint)
            slow.append(where)
            continue
        except (OSError, subprocess.SubprocessError):
            continue
        seen_before(root, key, fingerprint)  # checked in this state, whatever it said
        if check.returncode != 3:
            continue
        try:
            report = json.loads(check.stdout)
            audit = report.get("self_audit_line") if isinstance(report, dict) else None
        except ValueError:
            audit = None
        out.append("{}: the method run's own stop gate says keep iterating ({}). Start the next candidate. Only "
                   "the user ends it early: when the user says to stop, run `python {} record-blocker --root {} "
                   "--kind user --detail \"<the user's words>\"`. The user can also set \"loops\" to \"warn\" "
                   "in .mycelium-extra/gate.json.".format(where, audit or (check.stdout.strip()[:120] or "exit 3"),
                                                           script, run))
    return out, unchecked, slow


def _stamp(path):
    stat = os.stat(path)
    return (stat.st_size, stat.st_mtime_ns)


def evaluator_hasher(root, deadline, skipped):
    """A hasher for `evaluator_drift` that stays inside the Stop budget. A file whose size and mtime match the last
    hash it took is not read again. A file it cannot finish before `deadline` is added to `skipped` and left
    unchecked (None). When it was the first file to hash, so it had the whole budget, it is also remembered as too
    big for its size and mtime and the next Stop skips it at no cost; any other file stays unmarked and is hashed
    first at the next Stop. The cache is `loop_guard_hashes.json`, written by `save()`."""
    import hashlib
    path = os.path.join(root, STATE_DIR, HASHES)
    try:
        with open(path, encoding="utf-8") as handle:
            cache = json.load(handle)
    except (OSError, ValueError):
        cache = {}
    cache = cache if isinstance(cache, dict) else {}
    changed, started = [], []

    def hasher(file):
        stat = os.stat(file)
        entry = cache.get(file)
        if isinstance(entry, list) and entry[:2] == [stat.st_size, stat.st_mtime_ns]:
            if entry[2] is None:  # too big for one Stop, as it stands: do not spend the budget on it again
                skipped.append(file)
            return entry[2]
        if time.monotonic() > deadline:  # an earlier file used the budget: try this one at the next Stop
            skipped.append(file)
            return None
        alone = not started  # the first file to hash has the whole budget; a later one shares what is left
        started.append(file)
        digest = hashlib.sha256()
        with open(file, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                if time.monotonic() > deadline:
                    skipped.append(file)
                    if alone:  # it could not finish with the whole budget: too big for any Stop
                        cache[file] = [stat.st_size, stat.st_mtime_ns, None]
                        changed.append(file)
                    return None
                digest.update(chunk)
        cache[file] = [stat.st_size, stat.st_mtime_ns, digest.hexdigest()]
        changed.append(file)
        return cache[file][2]

    def save():
        if changed:
            try:
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(cache, handle)
            except OSError:
                pass

    return hasher, save


def stop_hook(event, mode, root, pending=None):
    """The Stop reply. Reported states are not recorded here: they go to `pending` as (key, fingerprint) pairs, which
    `main` records once the reply is out, so a hook the host kills mid-run loses nothing. A fingerprint of None
    clears the key. Fingerprints carry the mode, so a state noted under "warn" is still new under "block"."""
    if event.get("stop_hook_active"):
        return {}  # one block per turn
    pending = [] if pending is None else pending
    deadline = time.monotonic() + STOP_BUDGET
    trees, module = trees_of(root)
    loop_lines, drift_lines, unhashed = [], [], []
    # hashing gets half the budget, so the method runs' stop-check still has time at every Stop
    hasher, save_hashes = evaluator_hasher(root, time.monotonic() + STOP_BUDGET / 2, unhashed)

    def fresh(key, fingerprint):
        """True when this state was not reported before; queues it (or the clearing of the key) for recording."""
        pending.append((key, fingerprint))
        return fingerprint is not None and not seen_before(root, key, fingerprint, record=False)

    for analysis, tree in trees:
        where = os.path.relpath(analysis, root) or "."
        try:
            stat = os.stat(module.tree_path(analysis))
            fingerprint = "{}:{}:{}".format(stat.st_size, stat.st_mtime_ns, mode)
        except OSError:
            continue
        code, message = module.stop_check(tree)
        # a tree is reported once per state: a turn that did not touch the loop is not stopped again
        if code == 3 and fresh(where, fingerprint):
            loop_lines.append("{}: {}".format(where, message))
        before = len(unhashed)
        drift = [(os.path.relpath(path, root), why) for path, why in module.evaluator_drift(tree, analysis, hasher)]
        if drift:
            # the file's size and mtime join the key, so a second edit of the same file is a new drift
            marks = [(path, why) + (_stamp(os.path.join(root, path)) if why == "changed" else ())
                     for path, why in drift]
            if fresh(where + ":evaluator", json.dumps([marks, mode])):
                drift_lines.append("{}: the frozen evaluator changed ({}). Results since then are not comparable to "
                                   "the baseline. Restore the file, or ask the user and re-freeze with `tree.py "
                                   "freeze-evaluator --refreeze --note ...`.".format(
                                       where, ", ".join("{} {}".format(p, why) for p, why in drift)))
        elif len(unhashed) == before:
            pending.append((where + ":evaluator", None))  # checked and clean: a later drift is reported again
        if len(unhashed) > before:
            names = sorted(os.path.relpath(path, root) for path in unhashed[before:])
            # one state blocks once: the tree and the evaluator files' size and mtime, not the list of unhashed files
            state = [fingerprint] + [_stamp(path) for path in module.evaluator_files(tree, analysis)
                                     if os.path.exists(path)]
            if fresh(where + ":evaluator-unchecked", json.dumps([state, mode])):
                drift_lines.append("{}: the Stop hook had no time to hash these frozen evaluator files: {}. They are "
                                   "not checked here. Run `tree.py check-evaluator` yourself before you report "
                                   "results.".format(where, ", ".join(names)))
        else:
            pending.append((where + ":evaluator-unchecked", None))
    save_hashes()
    bridge, unchecked, slow = tusoskill_lines(root, deadline, ":" + mode)
    if slow:
        bridge.append("the stop-check of these method runs took longer than the hook allows, so it is skipped until "
                      "their state changes: {}. Run tusoskill's `stop-check` for them yourself before you finish."
                      .format(", ".join(slow)))
    if unchecked:
        bridge.append("the time budget ran out before these method runs were checked: {}. They are checked at the "
                      "next Stop.".format(", ".join(unchecked)))
    parts = []
    if loop_lines:
        parts.append("the research loop is not finished. " + " ".join(loop_lines) + " " + ESCAPES)
    parts += drift_lines + bridge
    if not parts:
        return {}
    text = "loop guard: " + " ".join(parts)
    if mode == "block":
        return {"decision": "block", "reason": text}
    return {"systemMessage": text}


def record_seen(root, pending):
    """Write the states `stop_hook` queued: a fingerprint is recorded, None clears the key."""
    path = os.path.join(root, STATE_DIR, SEEN)
    try:
        with open(path, encoding="utf-8") as handle:
            seen = json.load(handle)
    except (OSError, ValueError):
        seen = {}
    seen = seen if isinstance(seen, dict) else {}
    before = dict(seen)
    for key, fingerprint in pending:
        if fingerprint is None:
            seen.pop(key, None)
        else:
            seen[key] = fingerprint
    if seen != before:
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(seen, handle)
        except OSError:
            pass


def unparsed_reply(event, root):
    """Under `block`, a deny for a command the guard could not read, when it holds a git call or the fixed run
    command; None otherwise."""
    command = command_of(event)
    if not command:
        return None
    risky = re.search(r"(?<![\w.-])git(?![\w-])", command) is not None
    if not risky:
        trees, _module = trees_of(root)
        risky = any((tree["plan"] or {}).get("run_cmd") and tree["plan"]["run_cmd"] in command
                    for _analysis, tree in trees)
    if not risky:
        return None
    return respond(["could not parse this command."], "block")


def main(argv):
    args = list(argv)
    if args[:1] == ["--host"]:
        args = args[2:]
    action = args[-1] if args else ""
    event = root = None
    mode, pending, reply = "off", [], None
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))
        if not isinstance(event, dict) or action not in ("tool", "stop"):
            return 0
        root = find_root(event.get("cwd") or os.getcwd())
        mode = loops_mode(root) if root else "off"
        if mode == "off":
            return 0
        sys.path.insert(0, HERE)
        reply = tool_hook(event, mode, root) if action == "tool" else stop_hook(event, mode, root, pending)
    except Exception as err:
        print("loop guard: {}: {}".format(type(err).__name__, err), file=sys.stderr)
        try:
            if action == "tool" and mode == "block" and isinstance(event, dict):
                reply = unparsed_reply(event, root)
        except Exception:
            reply = None
        if reply is None:
            return 0
    if reply:
        print(json.dumps(reply))
        sys.stdout.flush()
    try:
        record_seen(root, pending)  # after the reply is out
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
