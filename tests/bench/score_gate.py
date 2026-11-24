#!/usr/bin/env python3
"""Score the gate's command classifier against a labelled corpus.

Run: python3 tests/bench/score_gate.py CORPUS.jsonl [CORPUS.jsonl ...] [--json] [--sealed] [--hooks DIR]

Each corpus line is one case:
    {"id": "s01", "family": "mpi-launcher", "command": "mpirun -n 4 python analysis/a.py",
     "cwd": ".", "expect": ["analysis/a.py"], "label": "hand"}

`expect` lists what the gate should treat as a covered run: a repository path, or
`cmd:<label>` for a gated command that names no path (`sbatch`, `snakemake`).
An empty list means the command runs no covered script.

A case with a non-empty `expect` is a run case (`n_run`); the rest are benign.
Per case, a false pass is an expected target the classifier did not return, and a
false deny is a returned target that was not expected. Files are scored separately
and never pooled. `--sealed` prints counts only, never ids or commands, for a
held-out file the implementer must not read; each sealed look appends one line
to tests/bench/results/heldout_looks.log.

The classifier runs in a fixed scratch layout (LAYOUT below) with the gate's
default settings. No model is called and no hook is run as a process.
"""

import argparse
import datetime
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The scratch repository every case runs in. Changing it changes every score.
LAYOUT = (
    "analysis/a.py",
    "analysis/b.R",
    "analysis/x.py",
    "analysis/run.sh",
    "analysis/report.qmd",
    "analysis/Snakefile",
    "analysis/sub/c.py",
    "analysis/__init__.py",
    "nbs/n.ipynb",
    "scripts/ok.py",
    "tools/y.py",
    "data/in.csv",
    "run.sbatch",
)


def load_gate(hooks):
    sys.path.insert(0, hooks)
    import gate  # noqa: E402

    return gate


def build_layout():
    root = tempfile.mkdtemp(prefix="bench-gate-")
    for rel in LAYOUT:
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("# bench\n")
    os.makedirs(os.path.join(root, ".mycelium-extra"))
    with open(os.path.join(root, ".mycelium-extra", "gate.json"), "w", encoding="utf-8") as handle:
        handle.write("{}")
    return root


def targets(gate, command, root, cwd, config):
    """What the classifier treats as covered runs in `command`."""
    found = set()
    for _explore, label, paths, _segment, _tokens, _cwd in gate.analyse_command(command, root, cwd, config):
        if paths:
            found.update(paths)
        else:
            found.add("cmd:" + label)
    return found


def read_cases(path):
    cases = []
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if line.strip():
                case = json.loads(line)
                missing = {"id", "family", "command", "expect"} - set(case)
                if missing:
                    raise ValueError("{}:{} lacks {}".format(path, number, sorted(missing)))
                cases.append(case)
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("{} has duplicate ids".format(path))
    return cases


def score_file(gate, path, root, config):
    rows = []
    for case in read_cases(path):
        cwd = os.path.normpath(os.path.join(root, case.get("cwd", ".")))
        expected = set(case["expect"])
        try:
            observed = targets(gate, case["command"], root, cwd, config)
            error = None
        except Exception as exc:  # a crash is scored as returning nothing
            observed, error = set(), "{}: {}".format(type(exc).__name__, exc)
        rows.append({
            "id": case["id"],
            "family": case["family"],
            "command": case["command"],
            "runs": bool(expected),
            "false_pass": sorted(expected - observed),
            "false_deny": sorted(observed - expected),
            "error": error,
        })
    return rows


def summarise(rows):
    families = {}
    for row in rows:
        entry = families.setdefault(row["family"], {"n": 0, "n_run": 0, "false_pass": 0, "false_deny": 0})
        entry["n"] += 1
        entry["n_run"] += row["runs"]
        entry["false_pass"] += bool(row["false_pass"])
        entry["false_deny"] += bool(row["false_deny"])
    return {
        "n": len(rows),
        "n_run": sum(r["runs"] for r in rows),
        "false_pass": sum(bool(r["false_pass"]) for r in rows),
        "false_deny": sum(bool(r["false_deny"]) for r in rows),
        "errors": sum(bool(r["error"]) for r in rows),
        "families": families,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("corpus", nargs="+")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--sealed", action="store_true", help="counts only, for a held-out file")
    parser.add_argument("--looks-log", default=os.path.join(ROOT, "tests", "bench", "results", "heldout_looks.log"),
                        help="where a sealed look is recorded")
    parser.add_argument("--hooks", default=os.path.join(ROOT, "hooks"), help="the hooks folder to score")
    args = parser.parse_args(argv)

    gate = load_gate(os.path.abspath(args.hooks))
    config = dict(gate.DEFAULTS, _notices=[])
    root = build_layout()
    try:
        report = {}
        for path in args.corpus:
            rows = score_file(gate, path, root, config)
            summary = summarise(rows)
            if not args.sealed:
                summary["failures"] = [r for r in rows if r["false_pass"] or r["false_deny"] or r["error"]]
            report[os.path.basename(path)] = summary
    finally:
        shutil.rmtree(root)

    if args.sealed:  # every look at a held-out file is on record (roadmap 19, card: baseline and end of round only)
        with open(args.looks_log, "a", encoding="utf-8") as log:
            for name, summary in report.items():
                log.write("{}\t{}\t{}\tn={n} false_pass={false_pass} false_deny={false_deny}\n".format(
                    datetime.datetime.now().isoformat(timespec="seconds"), os.path.abspath(args.hooks), name, **summary))

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    for name, summary in report.items():
        print("{}: n={n} n_run={n_run} false_pass={false_pass} false_deny={false_deny} errors={errors}".format(name, **summary))
        for family, entry in sorted(summary["families"].items()):
            print("  {:<22} n={n:<4} n_run={n_run:<4} false_pass={false_pass:<3} false_deny={false_deny}".format(family, **entry))
        for row in summary.get("failures", []):
            print("  FAIL {id} {command!r} pass={false_pass} deny={false_deny} {error}".format(**row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
