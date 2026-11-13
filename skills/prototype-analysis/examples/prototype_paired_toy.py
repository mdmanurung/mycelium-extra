"""PROTOTYPE, throwaway. Run: python3 skills/prototype-analysis/examples/prototype_paired_toy.py
Question: after a min-count filter, does the donor-level paired contrast recover the known effect?
Toy design: 6 donors, control and treated cells each, true effect +1.0 (treated minus control).
Stdlib only, in memory, seeded. Nothing here feeds a reported result."""
import random
import statistics
import sys

SEED = 7
DONORS = 6
CELLS = 200          # cells per donor per condition
TRUE_EFFECT = 1.0    # set by us: treated minus control
THRESHOLDS = [0.0, 1.0, 2.0]  # the min-count filter under test (an impactful choice)


def simulate(rng):
    rows = []
    for d in range(DONORS):
        offset = rng.gauss(0, 1.0)  # donor baseline
        for cond, shift in (("control", 0.0), ("treated", TRUE_EFFECT)):
            for _ in range(CELLS):
                rows.append((f"D{d + 1}", cond, 2.0 + offset + shift + rng.gauss(0, 1.5)))
    return rows


def show(title, rows, removed=None):
    donors = sorted({r[0] for r in rows})
    print(f"\n[{title}] rows={len(rows)} donors={len(donors)}")
    for d in donors:
        n = {c: sum(1 for r in rows if r[0] == d and r[1] == c) for c in ("control", "treated")}
        gone = "" if removed is None else f" removed={removed.get(d, 0)}"
        print(f"  {d} control={n['control']} treated={n['treated']}{gone}")
    if removed is not None and not any(removed.values()):
        print("  removed 0")


def drop_low(rows, threshold):
    keep = [r for r in rows if r[2] >= threshold]
    removed = {}
    for r in rows:
        if r[2] < threshold:
            removed[r[0]] = removed.get(r[0], 0) + 1
    return keep, removed


def donor_contrast(rows):
    out = {}
    for d in sorted({r[0] for r in rows}):
        mean = {c: statistics.fmean(r[2] for r in rows if r[0] == d and r[1] == c)
                for c in ("control", "treated")}
        out[d] = mean["treated"] - mean["control"]
    return out


def main():
    rng = random.Random(SEED)
    print(f"seed={SEED} true effect={TRUE_EFFECT:+.2f} (treated minus control)")
    rows = simulate(rng)
    show("simulated", rows)
    summary = []
    for threshold in THRESHOLDS:
        kept, removed = drop_low(rows, threshold)
        show(f"filter value >= {threshold}", kept, removed)
        diffs = donor_contrast(kept)
        mean = statistics.fmean(diffs.values())
        sign = "+" if mean > 0 else "-"
        agree = sum(1 for v in diffs.values() if v > 0)
        print(f"  contrast treated-control: mean {mean:+.2f} (sign {sign}), "
              f"{agree}/{len(diffs)} donors positive")
        summary.append((threshold, mean))
    print("\nVerdict inputs (the user judges):")
    for threshold, mean in summary:
        print(f"  threshold {threshold}: estimate {mean:+.2f} vs truth {TRUE_EFFECT:+.2f}"
              f" (bias {mean - TRUE_EFFECT:+.2f})")
    spread = max(m for _, m in summary) - min(m for _, m in summary)
    if spread > 0.1:
        print(f"IMPACTFUL: the threshold moves the estimate by {spread:.2f}. "
              "Propose it as a plan row for the user; do not pick it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
