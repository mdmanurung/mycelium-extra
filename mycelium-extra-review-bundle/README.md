# Mycelium Extra — Development Review Bundle (revised 2026-10-06, scope-aligned)

Start with [`00_EVALUATION.md`](00_EVALUATION.md): what was evaluated, the two revision passes, the crosswalk to the
repository's roadmap, and the one decision still open.

## Files

0. [`00_EVALUATION.md`](00_EVALUATION.md): evaluation, revision log, crosswalk, open decision.
1. [`01_ASSESSMENT.md`](01_ASSESSMENT.md): the original assessment. Unchanged; sections 3 and 27 (the benchmark as the
   project's main experiment) are superseded by `00` and Track R in `03`.
2. [`02_ARCHITECTURE_AND_PRINCIPLES.md`](02_ARCHITECTURE_AND_PRINCIPLES.md): architecture with owners marked, principles `G1`–`G13`.
3. [`03_EXECUTION_BACKLOG.md`](03_EXECUTION_BACKLOG.md): tasks `M#-T##` with effort and state, four lanes, Track R.
4. [`04_MILESTONE_GATES.md`](04_MILESTONE_GATES.md): dependency rules, gates, critical path.
5. [`05_PARKED_AND_NON_GOALS.md`](05_PARKED_AND_NON_GOALS.md): parked, dropped, non-goals, reactivation rule.
6. [`06_TRACEABILITY_MATRIX.md`](06_TRACEABILITY_MATRIX.md): finding → task, with the Mycelium source consumed.

## What the package is for

Mycelium gives an analytical project a memory (decisions, findings, run lineage, report values, review). Extra adds
what Mycelium lacks:

> **Plan an analysis. Approve what runs. Check the execution record.**

Its claim, which the plan evaluates: Extra **surfaces the consequential choices before code runs, lets only approved
plans run, and reports honestly what ran against the plan, at low friction.** It does not judge scientific
correctness, and it does not rebuild what Mycelium already records (`G13`).

## Sequence

```text
M2 evaluate (grill-coverage baseline) ──► M3 plan Choice block + input checks ──► M4 frozen-release re-run
M1 execution integrity (consumes Mycelium lineage) runs beside, not before
M7 privacy first; M6 and M8 follow observed failures; M9 waits for a publish decision
```

Audience: one researcher and their own lab repositories. Extra stays 0.x. The study "does Extra reduce scientific
errors compared with no Extra" is an optional research track (Track R in `03`), not a gate.

## Filter for any new work

1. Plan, approve, or check-the-execution-record work (or scaffolding)? Otherwise Mycelium or Track R.
2. Does Mycelium already do it? Consume its record; build only the link.
3. Does it still work in a plain repository, as a weaker fallback or a gap?
4. Is the need shown in the user's repositories or the fixture?
