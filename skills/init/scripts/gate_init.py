"""Turn on the mycelium-extra approval gate in a repository.

Run from stdin so Mycelium's hooks stay closed:
    sh <plugin>/hooks/py.sh - [--root DIR] [--paths GLOB ...] [--commands CMD ...] [--hours N] [--dry-run]
        [--tools [--scilintr PATH] [--rscript PATH]] < gate_init.py
    sh <plugin>/hooks/py.sh - --diagnose [--root DIR] [--plugin-root DIR] < gate_init.py


Creates .mycelium-extra/gate.json and ignores .mycelium-extra/ in .gitignore.
Never changes an existing gate.json: after init, the gate's settings are the
user's to edit by hand. `--tools` also records where the scilintr linters are in
.mycelium-extra/tools.json (separate from gate.json, so it works on a gate that is
already on). `--diagnose` only reads and reports (effective config, hook registrations, Mycelium version,
available tools, last observed receipt and gate error); it writes nothing. Stdlib-only; runs on Python 3.9+.
"""

import argparse
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

STATE_DIR = ".mycelium-extra"
TESTED_MYCELIUM = ("0.6.0", "0.7.2")  # the versions whose hooks and files the docs were checked against
IGNORE_LINE = STATE_DIR + "/"
# Every key gate.json reads, with the default the gate uses. gate_init runs from stdin and cannot import
# hooks/gate.py, so this mirrors it; skills/init/tests/test_gate_init.py fails if the two drift.
# null: unset (no limit / off).
DEFAULTS = {
    "gated_paths": ["analysis/**", "nbs/**"],
    "gated_commands": ["sbatch", "snakemake", "nextflow"],
    "approval_hours": 24,
    "pin_hash_mb": 200,
    "pin_seconds": 5,
    "pin_scripts": True,
    "card_lint": True,
    "card_coverage": True,
    "focus_notices": False,
    "confirm_writes": False,
    "lint_on_write": True,
    "lint_before_stop": False,
    "lint_before_run": False,
    "on_error": "allow",
    "max_runs_per_approval": None,
    "checkpoint_steps": None,
}


def git(root, *args):
    try:
        return subprocess.run(["git", "-C", root] + list(args), stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, encoding="utf-8", errors="replace")
    except OSError:
        return None


def repo_root(start):
    result = git(start, "rev-parse", "--show-toplevel")
    if result is not None and result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return os.path.abspath(start)


def gated_ancestor(path):
    """Same walk-up as hooks/gate.py find_root: the nearest dir with gate.json."""
    path = os.path.abspath(path)
    while True:
        if os.path.isfile(os.path.join(path, STATE_DIR, "gate.json")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def is_ignored(root):
    result = git(root, "check-ignore", "-q", os.path.join(STATE_DIR, "gate.json"))
    if result is not None and result.returncode in (0, 1):
        return result.returncode == 0
    try:
        with open(os.path.join(root, ".gitignore"), encoding="utf-8", errors="replace") as handle:
            lines = [line.strip() for line in handle]
    except OSError:
        return False
    return any(line in (STATE_DIR, IGNORE_LINE, "/" + STATE_DIR, "/" + IGNORE_LINE)
               for line in lines)


def add_ignore(root):
    path = os.path.join(root, ".gitignore")
    text = b""
    if os.path.exists(path):
        with open(path, "rb") as handle:  # bytes: a non-UTF-8 .gitignore must not abort init
            text = handle.read()
    prefix = "\n" if text and not text.endswith(b"\n") else ""
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(prefix + "# mycelium-extra approval gate: short-lived execution state\n"
                     + IGNORE_LINE + "\n"
                     + "# mycelium-extra verify: write lock and in-flight transaction, never committed\n"
                     + "**/provenance/.publish.lock\n**/provenance/.transactions/\n")


def glob_base(pattern):
    base = []
    for part in pattern.split("/"):
        if any(ch in part for ch in "*?["):
            break
        base.append(part)
    return "/".join(base)


def missing_paths(root, patterns):
    return [p for p in patterns if not os.path.isdir(os.path.join(root, glob_base(p) or "."))]


def bare_folders(root, patterns):
    """Patterns with no glob that name a folder (or nothing): the gate matches such a pattern against the
    folder itself, never against the files under it."""
    return [p for p in patterns if glob_base(p) == p and os.path.isdir(os.path.join(root, p or "."))]


def find_tool(flag, env, name):
    """A tool's path: the flag, else the environment variable, else PATH; None when none is set."""
    value = flag or os.environ.get(env) or shutil.which(name)
    return os.path.abspath(os.path.expanduser(value)) if value and os.sep in value else value


def run_tool(command):
    try:
        return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8",
                              errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None


def check_scilintr(path):
    """The Python linter exits 0 on an empty file."""
    with tempfile.TemporaryDirectory() as folder:
        empty = os.path.join(folder, "empty.py")
        open(empty, "w").close()
        done = run_tool([path, empty])
    return done is not None and done.returncode == 0


def r_scilintr_version(path):
    """The installed R package's version through this Rscript, else None."""
    done = run_tool([path, "-e", 'cat(format(packageVersion("scilintr")))'])
    return done.stdout.strip() if done is not None and done.returncode == 0 and \
        done.stdout.strip()[:1].isdigit() else None


def record_tools(root, flags, dry_run):
    """Write the linters that work to .mycelium-extra/tools.json, keeping a path already recorded for
    one that does not; say what is missing and how to give its path."""
    path = os.path.join(root, STATE_DIR, "tools.json")
    try:
        with open(path, encoding="utf-8") as handle:
            tools = json.load(handle)
    except (OSError, ValueError):
        tools = {}
    if not isinstance(tools, dict):
        print("note: {} is not a JSON object; rebuilding it from checked tools.".format(path))
        tools = {}
    python = find_tool(flags[0], "MX_SCILINTR", "scilintr")
    rscript = find_tool(flags[1], "MX_RSCRIPT", "Rscript")
    version = r_scilintr_version(rscript) if rscript else None
    if python and check_scilintr(python):
        tools["scilintr"] = python
    else:
        print("scilintr (Python) not found or not working: {}. Pass --scilintr PATH (such as a venv's "
              "bin/scilintr) or set MX_SCILINTR.".format(python or "no `scilintr` on PATH"))
    if version:
        tools["rscript"], tools["scilintr_r"] = rscript, version
    else:
        print("scilintr (R) not found or not working: {}. Pass --rscript PATH of an Rscript whose R has "
              "scilintr installed (after `module load`, `which Rscript`) or set MX_RSCRIPT.".format(
                  rscript or "no `Rscript` on PATH"))
    if dry_run:
        print("would write {}: {}".format(path, json.dumps(tools)))
        return
    if tools:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(tools, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print("wrote {}: {}".format(path, json.dumps(tools, sort_keys=True)))


def mycelium_version(root):
    """(plugin root, version) of the Mycelium `.mycelium/plugin-root` names: (None, None) when there is no
    pointer; (path, None) when the version cannot be read. Reads only."""
    pointer = os.path.join(root, ".mycelium", "plugin-root")
    try:
        with open(pointer, encoding="utf-8") as handle:
            plugin = handle.read().strip()
    except OSError:
        return None, None
    for manifest in (".claude-plugin", ".codex-plugin"):
        try:
            with open(os.path.join(plugin, manifest, "plugin.json"), encoding="utf-8") as handle:
                version = json.load(handle).get("version")
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(version, str) and version:
            return plugin, version
    return plugin, None


def mycelium_notice(root):
    """One plain-text line when the Mycelium this repository points at (`.mycelium/plugin-root`, which Mycelium
    writes) is not a version mycelium-extra was tested with; nothing when there is no Mycelium here. Reads
    only; never writes Mycelium's files. An unreadable version is said, not assumed fine."""
    plugin, version = mycelium_version(root)
    if plugin is None:
        return None
    tested = ", ".join(TESTED_MYCELIUM)
    if version in TESTED_MYCELIUM:
        return None
    if version:
        return ("note: Mycelium {} is installed here; mycelium-extra was tested with {}. Its hook and file "
                "behaviour is unchecked on this version.".format(version, tested))
    return ("note: could not read Mycelium's version from {} (listed by {}); mycelium-extra was tested with {}."
            .format(plugin or "an empty path", os.path.join(".mycelium", "plugin-root"), tested))


# ---------------------------------------------------------------- --diagnose (read-only)

def _number(value):
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:  # an integer too large for a float
        return False


def _strings(value):
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _whole(value, low):
    return isinstance(value, int) and not isinstance(value, bool) and value >= low


# gate.json key -> (what the gate accepts, test). These mirror the checks in hooks/gate.py and
# hooks/gate_run.py; gate_init runs from stdin and cannot import them, so keep the two in step.
CONFIG_RULES = {
    "gated_paths": ("a list of strings", _strings),
    "gated_commands": ("a list of strings", _strings),
    "approval_hours": ("a number of 0 or more", lambda v: _number(v) and v >= 0),
    "pin_hash_mb": ("a number of 0 or more", lambda v: _number(v) and v >= 0),
    "pin_seconds": ("a number of 0 or more", lambda v: _number(v) and v >= 0),
    "pin_scripts": ("true or false", lambda v: isinstance(v, bool)),
    "card_lint": ("true or false", lambda v: isinstance(v, bool)),
    "card_coverage": ("true or false", lambda v: isinstance(v, bool)),
    "focus_notices": ("true or false", lambda v: isinstance(v, bool)),
    "confirm_writes": ("true or false", lambda v: isinstance(v, bool)),
    "lint_on_write": ("true or false", lambda v: isinstance(v, bool)),
    "lint_before_stop": ("true or false", lambda v: isinstance(v, bool)),
    "lint_before_run": ('false, "warn" or "block"', lambda v: v is False or v in ("warn", "block")),
    "on_error": ('"allow" or "deny"', lambda v: v in ("allow", "deny")),
    "max_runs_per_approval": ("a whole number of 1 or more (or null/unset)", lambda v: v is None or _whole(v, 1)),
    "checkpoint_steps": ("a whole number of 1 or more, or 0 for off (or null/unset)", lambda v: v is None or _whole(v, 0)),
}


# What the gate does with an invalid value (hooks/gate.py reads each key its own way); keep in step with it.
INVALID_EFFECT = {
    "pin_scripts": "pinning is on", "card_lint": "on", "lint_on_write": "on", "card_coverage": "off",
    "focus_notices": "off", "confirm_writes": "off", "lint_before_stop": "off", "lint_before_run": "off", "on_error": "allow",
    "max_runs_per_approval": "no limit", "checkpoint_steps": "off",
}
# gated_paths and gated_commands are not type-checked by the gate, so there is no default to fall back to.
UNCHECKED_EFFECT = ("nothing: the gate does not check it, so an int makes the gate error (the run is then "
                    "allowed, or denied if on_error is deny) and a string is read one character at a time")


def last_json_line(path):
    """The last parseable JSON line of a .jsonl file, else None (also when the file is absent)."""
    last = None
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    last = json.loads(line)
                except ValueError:
                    continue
    except OSError:
        pass
    return last


def load_json(path):
    """(data, error): the parsed file, or None and a one-line reason."""
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle), None
    except OSError as error:
        return None, error.strerror or str(error)
    except ValueError as error:
        return None, "not valid JSON ({})".format(error)


def default_plugin_root():
    """This plugin's root: $CLAUDE_PLUGIN_ROOT or $PLUGIN_ROOT, else three folders above this script when it
    runs from a file (run from stdin, as the skill does, it has no path)."""
    for name in ("CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT"):
        if os.environ.get(name):
            return os.environ[name]
    here = globals().get("__file__")
    return os.path.abspath(os.path.join(os.path.dirname(here), "..", "..", "..")) if here else None


def hook_commands(events):
    """{event: set of command strings} of a hooks mapping; non-conforming entries are skipped."""
    found = {}
    if not isinstance(events, dict):
        return found
    for event, groups in events.items():
        commands = set()
        for group in groups if isinstance(groups, list) else []:
            for hook in group.get("hooks", []) if isinstance(group, dict) else []:
                if isinstance(hook, dict) and isinstance(hook.get("command"), str):
                    commands.add(hook["command"])
        found[event] = commands
    return found


def diagnose_hooks(plugin, out):
    if not plugin or not os.path.isdir(os.path.join(plugin, "hooks")):
        out.append("hooks: plugin root not found ({}); pass --plugin-root DIR, the folder holding hooks/.".format(
            plugin or "no CLAUDE_PLUGIN_ROOT or PLUGIN_ROOT set, and run from stdin"))
        return
    out.append("hooks (plugin root {}):".format(plugin))
    registered = {}
    for name in ("hooks.json", "codex.json"):
        data, error = load_json(os.path.join(plugin, "hooks", name))
        if error:
            out.append("  {}: unreadable: {}".format(name, error))
            registered[name] = None
            continue
        registered[name] = hook_commands(data.get("hooks") if isinstance(data, dict) else None)
        out.append("  {}: {} events registered: {}".format(
            name, len(registered[name]), ", ".join(sorted(registered[name])) or "none"))


def diagnose(root, plugin_root):
    """The read-only report, as a list of lines. Nothing here writes a file or creates a folder."""
    out = ["mycelium-extra diagnose (read-only; nothing was written)", "repository: " + root]
    gated = gated_ancestor(root)
    state = os.path.join(gated or root, STATE_DIR)
    if gated is None:
        out.append("gate: off here (no {}/gate.json from {} upward); effective config would be the defaults.".format(
            STATE_DIR, root))
        saved = {}
    else:
        saved, error = load_json(os.path.join(state, "gate.json"))
        out.append("gate: on, from {}/gate.json".format(os.path.join(gated, STATE_DIR)))
        if error or not isinstance(saved, dict):
            out.append("  gate.json unreadable: {}; the gate reads it as broken.".format(
                error or "expected a JSON object"))
            saved = {}
    config = dict(DEFAULTS)
    config.update(saved)
    out.append("effective config (defaults merged with gate.json):")
    for key in sorted(config):
        out.append("  {}: {}{}".format(key, json.dumps(config[key]), "" if key in saved else "  (default)"))
    out.append("  null means no run limit for max_runs_per_approval and no checkpoint for checkpoint_steps; "
               "checkpoint_steps: 0 also turns checkpoints off.")
    for key in sorted(saved):
        rule = CONFIG_RULES.get(key)
        if rule is None:
            out.append("  PROBLEM {}: not a key this gate reads (typo?); ignored.".format(key))
        elif not rule[1](saved[key]):
            effect = (UNCHECKED_EFFECT if key in ("gated_paths", "gated_commands") else
                      INVALID_EFFECT.get(key, "the default"))
            out.append("  PROBLEM {}: {} is invalid; the gate wants {}, and uses {}.".format(
                key, json.dumps(saved[key]), rule[0], effect))
    diagnose_hooks(plugin_root, out)
    plugin, version = mycelium_version(gated or root)
    if plugin is None:
        out.append("mycelium: none found here (no .mycelium/plugin-root); mycelium-extra works without it.")
    elif version:
        out.append("mycelium: {} at {} ({}).".format(
            version, plugin, "tested" if version in TESTED_MYCELIUM else
            "not one of the tested versions " + ", ".join(TESTED_MYCELIUM)))
    else:
        out.append("mycelium: version unreadable at {} (listed by .mycelium/plugin-root).".format(plugin))
    recorded = load_json(os.path.join(state, "tools.json"))[0]
    recorded = recorded if isinstance(recorded, dict) else {}
    out.append("optional readers and linters (presence only; nothing is run):")
    out.append("  h5py: {}".format("importable" if importlib.util.find_spec("h5py") else "not importable"))
    for name in ("scilintr", "Rscript", "sacct"):
        path = shutil.which(name)
        out.append("  {}: {}".format(name, path or "not on PATH"))
    if recorded:
        out.append("  recorded by `--tools` in tools.json: " + json.dumps(recorded, sort_keys=True))
    out.append("last observed:")
    receipt = last_json_line(os.path.join(state, "receipts.jsonl"))
    if isinstance(receipt, dict):
        out.append("  newest receipt: host {}; exit_status {}; kind {}.".format(
            receipt.get("host") or "not recorded (Claude Code, or a receipt from before hosts were recorded)",
            "present: " + json.dumps(receipt["exit_status"]) if "exit_status" in receipt else "absent",
            receipt.get("kind", "unknown")))
    else:
        out.append("  no run receipt recorded yet.")
    error = last_json_line(os.path.join(state, "gate-errors.jsonl"))
    if isinstance(error, dict):
        out.append("  last gate error: {} hook, decision {}: {}".format(
            error.get("event", "unknown"), error.get("decision", "unknown"), error.get("error", "")))
    else:
        out.append("  no gate error recorded.")
    out.append("note: a hook registered in a manifest, or a gate.json in the repository, does not prove the host "
               "has enabled or trusted the hooks. Check /hooks in Codex or Claude Code, and restart the session.")
    return out


def main(argv):
    parser = argparse.ArgumentParser(prog="gate_init")
    parser.add_argument("--root", default=None, help="repository to gate (default: git toplevel of cwd)")
    parser.add_argument("--paths", nargs="+", help="gated_paths globs (default: analysis/** nbs/**)")
    parser.add_argument("--commands", nargs="+", help="gated_commands (default: sbatch snakemake nextflow)")
    parser.add_argument("--hours", type=float, help="approval_hours (default: 24)")
    parser.add_argument("--tools", action="store_true",
                        help="also record where scilintr (Python) and Rscript with scilintr are, in tools.json")
    parser.add_argument("--scilintr", help="--tools: path of the Python scilintr (default: $MX_SCILINTR, else PATH)")
    parser.add_argument("--rscript", help="--tools: path of an Rscript whose R has scilintr (default: $MX_RSCRIPT, else PATH)")
    parser.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    parser.add_argument("--diagnose", action="store_true",
                        help="read-only report: effective config, hooks, Mycelium, tools, last receipt and gate error")
    parser.add_argument("--plugin-root", default=None,
                        help="--diagnose: this plugin's folder (default: $CLAUDE_PLUGIN_ROOT, $PLUGIN_ROOT, or beside the script)")
    args = parser.parse_args(argv)
    if args.diagnose and (args.paths or args.commands or args.hours is not None or args.tools
                          or args.scilintr or args.rscript or args.dry_run):
        parser.error("--diagnose only reports; do not combine it with options that change or record anything")
    if args.plugin_root and not args.diagnose:
        parser.error("--plugin-root only applies to --diagnose")
    if args.hours is not None and (not math.isfinite(args.hours) or args.hours < 0):
        parser.error("--hours must be finite and 0 or more")

    root = os.path.abspath(args.root) if args.root else repo_root(os.getcwd())
    if args.diagnose:
        print("\n".join(diagnose(root, os.path.abspath(args.plugin_root) if args.plugin_root
                                  else default_plugin_root())))
        return 0
    existing = gated_ancestor(root)
    if existing:
        config = dict(DEFAULTS)
        try:
            with open(os.path.join(existing, STATE_DIR, "gate.json"), encoding="utf-8") as handle:
                saved = json.load(handle)
            if not isinstance(saved, dict):
                raise ValueError("expected a JSON object")
            config.update(saved)
        except (OSError, ValueError) as error:
            print("already gated: {} (gate.json unreadable: {})".format(existing, error))
            return 1
        print("already gated: {}".format(existing))
        print("effective config: " + json.dumps(config, sort_keys=True))
        print("no changes made to gate.json; edit {}/gate.json by hand to change it.".format(
            os.path.join(existing, STATE_DIR)))
        if args.tools:
            record_tools(existing, (args.scilintr, args.rscript), args.dry_run)
        notice = mycelium_notice(existing)
        if notice:
            print(notice)
        return 0

    config = {}
    if args.paths:
        config["gated_paths"] = args.paths
    if args.commands:
        config["gated_commands"] = args.commands
    if args.hours is not None:
        config["approval_hours"] = int(args.hours) if args.hours == int(args.hours) else args.hours
    effective = dict(DEFAULTS, **config)
    ignored = is_ignored(root)
    verb = "would create" if args.dry_run else "created"

    if not args.dry_run:
        os.makedirs(os.path.join(root, STATE_DIR), exist_ok=True)
        with open(os.path.join(root, STATE_DIR, "gate.json"), "w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2)
            handle.write("\n")
        if not ignored:
            add_ignore(root)

    print("{} {}/gate.json: {}".format(verb, os.path.join(root, STATE_DIR), json.dumps(config)))
    if ignored:
        print(".gitignore: {} already ignored".format(IGNORE_LINE))
    else:
        print(".gitignore: {} {}".format("would add" if args.dry_run else "added", IGNORE_LINE))
    print("effective config: " + json.dumps(effective, sort_keys=True))
    missing = missing_paths(root, effective["gated_paths"])
    if len(missing) == len(effective["gated_paths"]):
        print("WARNING: none of gated_paths exist here ({}); only gated_commands will be "
              "blocked until they do.".format(", ".join(missing)))
    elif missing:
        print("note: not present yet: " + ", ".join(missing))
    bare = bare_folders(root, effective["gated_paths"])
    if bare:
        print("WARNING: gated_paths without a glob match only the folder itself, not the files in it ({}); "
              "write e.g. {}/** to cover them.".format(", ".join(repr(p) for p in bare), (bare[0] or ".").rstrip("/")))
    if args.tools:
        record_tools(root, (args.scilintr, args.rscript), args.dry_run)
    notice = mycelium_notice(root)
    if notice:
        print(notice)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
