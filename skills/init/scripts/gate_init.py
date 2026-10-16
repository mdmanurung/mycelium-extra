"""Turn on the mycelium-extra approval gate in a repository.

Run from stdin so Mycelium's hooks stay closed:
    python3 - [--root DIR] [--paths GLOB ...] [--commands CMD ...] [--hours N] [--dry-run]
        [--tools [--scilintr PATH] [--rscript PATH]] < gate_init.py

Creates .mycelium-extra/gate.json and ignores .mycelium-extra/ in .gitignore.
Never changes an existing gate.json: after init, the gate's settings are the
user's to edit by hand. `--tools` also records where the scilintr linters are in
.mycelium-extra/tools.json (separate from gate.json, so it works on a gate that is
already on). Stdlib-only; runs on Python 3.6+.
"""

import argparse
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
DEFAULTS = {
    "gated_paths": ["analysis/**", "nbs/**"],
    "gated_commands": ["sbatch", "snakemake", "nextflow"],
    "approval_hours": 24,
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
        with open(os.path.join(root, ".gitignore"), encoding="utf-8") as handle:
            lines = [line.strip() for line in handle]
    except OSError:
        return False
    return any(line in (STATE_DIR, IGNORE_LINE, "/" + STATE_DIR, "/" + IGNORE_LINE)
               for line in lines)


def add_ignore(root):
    path = os.path.join(root, ".gitignore")
    text = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    prefix = "\n" if text and not text.endswith("\n") else ""
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(prefix + "# mycelium-extra approval gate: short-lived execution state\n"
                     + IGNORE_LINE + "\n")


def glob_base(pattern):
    base = []
    for part in pattern.split("/"):
        if any(ch in part for ch in "*?["):
            break
        base.append(part)
    return "/".join(base)


def missing_paths(root, patterns):
    return [p for p in patterns if not os.path.isdir(os.path.join(root, glob_base(p) or "."))]


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


def mycelium_notice(root):
    """One plain-text line when the Mycelium this repository points at (`.mycelium/plugin-root`, which Mycelium
    writes) is not a version mycelium-extra was tested with; nothing when there is no Mycelium here. Reads
    only; never writes Mycelium's files. An unreadable version is said, not assumed fine."""
    pointer = os.path.join(root, ".mycelium", "plugin-root")
    try:
        with open(pointer, encoding="utf-8") as handle:
            plugin = handle.read().strip()
    except OSError:
        return None
    tested = ", ".join(TESTED_MYCELIUM)
    for manifest in (".claude-plugin", ".codex-plugin"):
        try:
            with open(os.path.join(plugin, manifest, "plugin.json"), encoding="utf-8") as handle:
                version = json.load(handle).get("version")
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(version, str) and version:
            if version in TESTED_MYCELIUM:
                return None
            return ("note: Mycelium {} is installed here; mycelium-extra was tested with {}. Its hook and file "
                    "behaviour is unchecked on this version.".format(version, tested))
    return ("note: could not read Mycelium's version from {} (listed by {}); mycelium-extra was tested with {}."
            .format(plugin or "an empty path", os.path.join(".mycelium", "plugin-root"), tested))


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
    args = parser.parse_args(argv)
    if args.hours is not None and (not math.isfinite(args.hours) or args.hours <= 0):
        parser.error("--hours must be finite and positive")

    root = os.path.abspath(args.root) if args.root else repo_root(os.getcwd())
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
    if args.tools:
        record_tools(root, (args.scilintr, args.rscript), args.dry_run)
    notice = mycelium_notice(root)
    if notice:
        print(notice)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
