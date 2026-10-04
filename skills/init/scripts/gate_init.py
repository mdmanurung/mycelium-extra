"""Turn on the mycelium-extra approval gate in a repository.

Run from stdin so Mycelium's hooks stay closed:
    python3 - [--root DIR] [--paths GLOB ...] [--commands CMD ...] [--hours N] [--dry-run] < gate_init.py

Creates .mycelium-extra/gate.json and ignores .mycelium-extra/ in .gitignore.
Never changes an existing gate.json: after init, the gate's settings are the
user's to edit by hand. Stdlib-only; runs on Python 3.6+.
"""

import argparse
import json
import os
import subprocess
import sys

STATE_DIR = ".mycelium-extra"
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


def main(argv):
    parser = argparse.ArgumentParser(prog="gate_init")
    parser.add_argument("--root", default=None, help="repository to gate (default: git toplevel of cwd)")
    parser.add_argument("--paths", nargs="+", help="gated_paths globs (default: analysis/** nbs/**)")
    parser.add_argument("--commands", nargs="+", help="gated_commands (default: sbatch snakemake nextflow)")
    parser.add_argument("--hours", type=float, help="approval_hours (default: 24)")
    parser.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    args = parser.parse_args(argv)

    root = os.path.abspath(args.root) if args.root else repo_root(os.getcwd())
    existing = gated_ancestor(root)
    if existing:
        config = dict(DEFAULTS)
        try:
            with open(os.path.join(existing, STATE_DIR, "gate.json"), encoding="utf-8") as handle:
                config.update(json.load(handle))
        except (OSError, ValueError) as error:
            print("already gated: {} (gate.json unreadable: {})".format(existing, error))
            return 0
        print("already gated: {}".format(existing))
        print("effective config: " + json.dumps(config, sort_keys=True))
        print("no changes made; edit {}/gate.json by hand to change it.".format(
            os.path.join(existing, STATE_DIR)))
        return 0

    config = {}
    if args.paths:
        config["gated_paths"] = args.paths
    if args.commands:
        config["gated_commands"] = args.commands
    if args.hours is not None:
        if args.hours <= 0:
            parser.error("--hours must be positive")
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
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
