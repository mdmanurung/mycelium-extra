"""Known-answer check of a paired difference (treated minus control, per donor).

Purpose: show check-first. The expected values below are hand-computed literals
on a toy table, not output of the code under test.
Run:     python3 paired_check.py wrong    (exit 1, red)
         python3 paired_check.py right    (exit 0, green)
Outputs: prints the failures; with --out FILE writes {"status", "message"} JSON.
"""

import json
import sys

# Toy table (donor, condition, value). Rows are shuffled on purpose, and d4 has
# no treated row, so a step that pairs by position or keeps d4 goes wrong.
ROWS = [
    ("d2", "trt", 9.0),
    ("d1", "ctrl", 10.0),
    ("d3", "ctrl", 12.0),
    ("d1", "trt", 14.0),
    ("d4", "ctrl", 7.0),
    ("d2", "ctrl", 8.0),
    ("d3", "trt", 11.0),
]

# Hand-computed: d1 14-10, d2 9-8, d3 11-12. Mean (4 + 1 - 1) / 3.
EXPECTED_DIFF = {"d1": 4.0, "d2": 1.0, "d3": -1.0}
EXPECTED_MEAN = 1.3333
EXPECTED_DROPPED = ["d4"]

# Negative control: every donor has the same value in both conditions.
NULL_ROWS = [("d1", "ctrl", 5.0), ("d1", "trt", 5.0), ("d2", "trt", 3.0), ("d2", "ctrl", 3.0)]


def paired_diff_wrong(rows):
    """Pairs by row position: the i-th control with the i-th treated row."""
    ctrl = [(d, v) for d, c, v in rows if c == "ctrl"]
    trt = [(d, v) for d, c, v in rows if c == "trt"]
    diff = {d: t - v for (d, v), (_, t) in zip(ctrl, trt)}
    mean = sum(diff.values()) / len(diff)
    return {"diff": diff, "mean": mean, "dropped": []}


def paired_diff_right(rows):
    """Pairs by donor name and drops donors that lack one condition."""
    by_donor = {}
    for donor, cond, value in rows:
        by_donor.setdefault(donor, {})[cond] = value
    diff = {d: v["trt"] - v["ctrl"] for d, v in by_donor.items() if len(v) == 2}
    dropped = sorted(d for d, v in by_donor.items() if len(v) < 2)
    return {"diff": diff, "mean": sum(diff.values()) / len(diff), "dropped": dropped}


def check(impl):
    """Return a list of failure messages; empty means every check passed."""
    fails = []
    out = impl(ROWS)
    if out["diff"] != EXPECTED_DIFF:
        fails.append(f"per-donor difference {out['diff']} != {EXPECTED_DIFF}")
    if abs(out["mean"] - EXPECTED_MEAN) > 1e-3:
        fails.append(f"mean {out['mean']:.4f} != {EXPECTED_MEAN}")
    if out["dropped"] != EXPECTED_DROPPED:
        fails.append(f"dropped {out['dropped']} != {EXPECTED_DROPPED}")
    null = impl(NULL_ROWS)
    if any(v != 0 for v in null["diff"].values()):
        fails.append(f"negative control not null: {null['diff']}")
    return fails


if __name__ == "__main__":
    impls = {"wrong": paired_diff_wrong, "right": paired_diff_right}
    if len(sys.argv) < 2 or sys.argv[1] not in impls:
        sys.exit("usage: paired_check.py wrong|right [--out FILE]")
    fails = check(impls[sys.argv[1]])
    for f in fails:
        print("FAIL:", f)
    print("RED" if fails else "GREEN")
    if "--out" in sys.argv:
        result = {"status": "failed" if fails else "passed", "message": "; ".join(fails)}
        with open(sys.argv[sys.argv.index("--out") + 1], "w") as fh:
            json.dump(result, fh)
    sys.exit(1 if fails else 0)
