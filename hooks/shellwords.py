"""Shell command words for the plan-approval gate: the tokenizer and the word tables.

Splits a shell command into words and operator tokens, keeps folder moves (`cd`, a wrapper's folder
option) and turns a word into a repository-relative path. hooks/gate.py imports every name here and
re-exports it, so `gate.tokenize` and the rest keep working. Stdlib-only and cheap to import: the hooks
load it on every call.
"""

import fnmatch
import os
import re


RUNNERS = re.compile(
    r"^(python[\d.]*|Rscript|R|bash|sh|zsh|jupyter|papermill|quarto|julia|perl|node|source|\.)$")
LAUNCHERS = ("py.sh", "mxpy")  # the plugin's Python launcher, as hooks/py.sh and as hooks/mxpy
SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "fish", "csh", "tcsh"}
CONTAINERS = {"apptainer", "singularity", "docker", "podman"}  # `exec IMAGE CMD`: CMD is read as if run directly
# ponytail: a plugin or tool root (`$MYC/skills/..`, `$CLAUDE_PLUGIN_ROOT/..`) is never a planned analysis script;
# any other variable is unresolved. Add a name here if a host's own scripts are denied.
PLUGIN_ROOT_VAR = re.compile(r"^\$\{?(MYC\w*|MYCELIUM\w*|CLAUDE_\w+|\w*PLUGIN_ROOT|\w*SKILL_DIR)\}?/")
SHELL_C = re.compile(r"^-[A-Za-z]*c[A-Za-z]*$")  # `-c`, `-lc`, `-ec`, `-ce`: the shell runs inline code
# Mycelium >= 0.8.2 opens its post-action cycle for these runners (tested with the 0.9.x line); `./run.sh` is
# labelled by its path.
MYCELIUM_SEES = re.compile(r"^(python[\d.]*|Rscript|R|jupyter|bash|sh|zsh|dash|ksh|snakemake|sbatch|nextflow|.*\.sh)$")
SCRIPT_EXT = re.compile(r"(\.(py|R|r|sh|ipynb|qmd|Rmd|rmd|jl|smk|pl)$|(^|/)Snakefile$)")
WRAPPERS = {"env", "time", "nohup", "nice", "ionice", "setsid", "command", "exec", "stdbuf", "timeout", "srun",
            "conda", "mamba", "micromamba", "pixi", "uv", "uvx", "run", "xvfb-run",
            "poetry", "pipx", "rye", "pdm", "hatch", "npx",
            "xargs", "parallel", "watch", "screen"}  # package-manager and process-launcher runners
VALUE_FLAGS = {"-n", "-p", "--name", "--prefix", "-e", "--environment", "--env", "-C", "--chdir",
               "-J", "--job-name", "-t", "--time", "-A", "--account", "--partition"}
# Value options of the wrappers that precede a command, and the ones that move the command's
# folder; `classify` skips an option's value instead of mistaking it for the command.
_CONDA_OPTIONS = ({"-n", "--name", "-p", "--prefix", "-r", "--root-prefix", "-a", "--attach", "--label",
                   "-e", "--environment", "--manifest-path", "--config", "--cwd"}, {"--cwd"})
WRAPPER_OPTIONS = {
    "xargs": ({"-n", "--max-args", "-P", "--max-procs", "-I", "-i", "--replace", "-d", "--delimiter", "-a",
               "--arg-file", "-s", "--max-chars", "-L", "--max-lines", "-E", "--eof", "--process-slot-var"}, set()),
    "parallel": ({"-j", "--jobs", "-N", "--max-args", "-n", "--colsep", "-C", "-a", "--arg-file", "-S", "--sshlogin",
                  "--results", "--joblog", "--tmpdir", "--delay", "--timeout", "--retries", "--load", "--memfree"}, set()),
    "watch": ({"-n", "--interval", "-d", "--differences"}, set()),
    "screen": ({"-S", "-dmS", "-t", "-c", "-e", "-h", "-p", "-s", "-T"}, set()),
    "ionice": ({"-c", "--class", "-n", "--classdata", "-p", "--pid", "-P", "--pgid", "-u", "--uid"}, set()),
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
    "xargs": {"-0", "--null", "-r", "--no-run-if-empty", "-t", "--verbose", "-p", "--interactive", "-x", "--exit",
              "-o", "--open-tty", "--show-limits"},
    "parallel": {"-k", "--keep-order", "--dry-run", "--bar", "--eta", "--progress", "--line-buffer", "--lb", "-u",
                 "--ungroup", "-X", "-m", "-q", "--quote", "--halt-on-error", "--no-notice", "--will-cite",
                 "--citation", "-v", "--verbose", "--pipe", "--group"},
    "watch": {"-t", "--no-title", "-b", "--beep", "-e", "--errexit", "-g", "--chgexit", "-c", "--color", "-x",
              "--exec", "-p", "--precise", "-w", "--no-wrap"},
    "screen": {"-d", "-m", "-dm", "-D", "-r", "-R", "-RR", "-x", "-X", "-L", "-U", "-q", "-A", "-a", "-f",
               "-fn", "-fa", "-l", "-ln", "-O", "-wipe", "-ls", "-list"},
    "ionice": {"-t", "--ignore", "-h", "--help", "-V", "--version"},
    "setsid": {"-c", "--ctty", "-f", "--fork", "-w", "--wait", "-h", "--help", "-V", "--version"},
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
HEAD_SKIP = {"sudo", "do", "then", "else", "elif", "!", "{", "if", "while", "until", "function", "coproc"}
DURATION = re.compile(r"^\d+(?:\.\d+)?[smhd]?$")  # a `timeout` duration: 5, 1.5s, 2m, 1h
PATHLIKE = re.compile(r"[\w./~-]+")
LOADS_FOLDER = re.compile(r"\bsys\.path\b|\b(os\.)?chdir\s*\(|\bsetwd\s*\(|\.libPaths\s*\(")


def ansi_literal(value):
    """Decode literal ANSI-C escapes; unsupported spellings stay visibly unresolved."""
    escapes = {"a": "\a", "b": "\b", "e": "\x1b", "E": "\x1b", "f": "\f", "n": "\n",
               "r": "\r", "t": "\t", "v": "\v", "\\": "\\", "'": "'", '"': '"', "?": "?"}

    def escape(match):
        token = match.group(1)
        if token in escapes:
            return escapes[token]
        base = 8 if token[0] in "01234567" else 16
        number = int(token if base == 8 else token[1:], base)
        if (token[0] in "01234567x" and number > 127) or 0xD800 <= number <= 0xDFFF:
            raise ValueError("non-text byte or surrogate")
        return chr(number)

    try:
        return re.sub(r"\\(x[0-9a-fA-F]{1,2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|[0-7]{1,3}|.)",
                      escape, value, flags=re.S).split("\x00", 1)[0]
    except (ValueError, OverflowError):
        return "$<unresolved-ansi-c>"


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
            if command[i + 1] == "\n":  # a line continuation joins the two lines; it is not a word or a separator
                i += 2
                continue
            word.append(command[i + 1])
            in_word = True
            i += 2
        elif c == "$" and command.startswith("$'", i):
            literal = re.match(r"\$'((?:\\[\s\S]|[^'\\])*)'", command[i:])
            word.append(ansi_literal(literal.group(1)) if literal else "$<unresolved-ansi-c>")
            in_word = True
            i += literal.end() if literal else n - i
        elif c in "'\"":
            j = i + 1
            while j < n and command[j] != c:
                if c == '"' and command[j] == "\\" and command[j + 1:j + 2] in ('"', "\\"):
                    j += 1  # a backslash escapes `"` and `\` inside double quotes: not the closing quote
                word.append(command[j])
                j += 1
            in_word = True
            i = j + 1
        elif c == "$" and command.startswith("$(", i):
            depth, j = 0, i
            while j < n:
                if command[j] in "'\"":  # a quoted `)` does not close the substitution
                    end = command.find(command[j], j + 1)
                    j = n if end < 0 else end
                elif command[j] == "(":
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
            while j < n and command[j] == c and j - i < (3 if c == "<" else 2):  # `<<<`: a here-string
                j += 1
            op = command[i:j]
            if op in ("<<",) and command.startswith("-", j):
                j += 1
            if c == "|" and command.startswith("&", j):  # `|&`: stdout and stderr piped, one operator
                j += 1
            elif c in "<>" and command.startswith("&", j):
                j += 1
                while j < n and (command[j].isdigit() or command[j] == "-"):
                    j += 1
            elif c == ">" and command.startswith("|", j):  # `>|`: clobber redirect, one operator
                j += 1
            elif c == "&" and command.startswith(">", j):  # `&>`: stdout and stderr, one operator
                j += 1
            tokens.append(command[i:j])
            if operators is not None:
                operators.append(command[i:j])
            i = j
            if op == "<<":
                bodies.append("")
                rest = command[i:].lstrip(" \t-")
                m = re.match(r"""'([^']*)'|"([^"]*)"|([A-Za-z_][A-Za-z0-9_]*)""", rest)
                if m:  # a quoted delimiter may hold spaces (`<<'END OF FILE'`), and the quote is the delimiter
                    delimiter = next(group for group in m.groups() if group is not None)
                    heredocs.append((delimiter, len(bodies) - 1))
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


def operand_exists(cwd, token):
    """True if a command operand names a file or folder that exists, resolved from the command's folder."""
    return os.path.exists(os.path.normpath(os.path.join(cwd, os.path.expanduser(token))))


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
        # after a folder change a bare name names a folder too (`setwd("analysis")`); otherwise it needs a path shape
        rel = gated_rel(root, cwd, word, config) if (loads or "/" in word or "." in word) else None
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
    if re.search(r"[$`*?\[]", value):  # an expansion or a glob: the shell decides where this goes
        return cwd if unknown else UnknownFolder(cwd, value)
    path = os.path.normpath(os.path.join(cwd, os.path.expanduser(value)))
    return UnknownFolder(path, cwd.raw, cwd.readings) if unknown and not os.path.isabs(
        os.path.expanduser(value)) else path


def cd_target(cwd, tokens):
    rest = tokens[1:]
    while rest and rest[0] != "-" and rest[0].startswith("-") and rest[0] in ("-P", "-L", "-e", "-@", "--"):
        rest.pop(0)  # `cd -P -- DIR`: options come before the folder
    target = rest[0] if rest else os.path.expanduser("~")
    if target == "-" or re.match(r"^[+-]\d+$", target):  # OLDPWD or the directory stack: not tracked here
        return move_folder(cwd, "$OLDPWD")
    if re.search(r"[$`*?\[]", target):  # an expansion or a glob: move_folder reads it as unresolved
        return move_folder(cwd, target)
    return os.path.normpath(os.path.join(cwd, os.path.expanduser(target)))


def substitutions(text):
    """The commands inside `$(...)` and backticks in one shell word."""
    found, i, n = [], 0, len(text)
    while i < n:
        if text.startswith("$(", i):
            depth, j = 0, i
            while j < n:
                if text[j] in "'\"":  # a quoted `)` does not close the substitution
                    end = text.find(text[j], j + 1)
                    j = n if end < 0 else end
                elif text[j] == "(":
                    depth += 1
                elif text[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            found.append(text[i + 2:j])
            i = j + 1
        elif text[i] == "`":
            end = text.find("`", i + 1)
            if end < 0:
                break
            found.append(text[i + 1:end])
            i = end + 1
        else:
            i += 1
    return found


def scoped_segments(command, bodies=None):
    """Like segments(), with parentheses kept as scope: yield (tokens, opened, closed, heredocs, before).

    `closed` parentheses end before this segment and `opened` ones start before it, so
    `(cd D); cmd` reads cmd in the outer folder and `popd` is never mistaken for a plain cd.
    `heredocs` holds this segment's `<<` bodies, in order; `before` is the separator that led to it
    (`|` when the previous segment's output is its stdin).
    """
    bodies = [] if bodies is None else bodies
    current, opened, closed, own, used, before = [], 0, 0, [], 0, ""
    for token in tokenize(command, bodies):
        if token in ("<<", "<<-"):
            own.append(bodies[used])
            used += 1
        if token == "(":
            if current:
                yield current, opened, closed, own, before
                current, opened, closed, own = [], 0, 0, []
            opened += 1
            before = token
        elif token == ")":
            if current:
                yield current, opened, closed, own, before
                current, opened, closed, own = [], 0, 0, []
            closed += 1
            before = token
        elif is_separator(token):
            if current:
                yield current, opened, closed, own, before
                current, opened, closed, own = [], 0, 0, []
            before = token
        else:
            current.append(token)
    if current:
        yield current, opened, closed, own, before


def reads_code(tokens):
    """Whether this segment runs code from stdin as shell: a shell, not an interpreter of another language.

    A heredoc or pipe into `python3` or `Rscript` is that language's code, which the shell reader
    cannot parse: scanning it as shell would deny harmless data, so only a shell's stdin is read.
    """
    return os.path.basename(tokens[0]) in SHELLS
