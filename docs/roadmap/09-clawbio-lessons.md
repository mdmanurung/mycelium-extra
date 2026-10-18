# 09 · ClawBio lessons (0.12.0 tracker)

Objective: take what ClawBio's 2026 talks teach about checks that pass while the analysis is wrong, and no ClawBio code, dependency or upstream Mycelium work. The full review and the dropped items are in `plans/mycelium-claw/09-clawbio-lessons-actionable-plan.md`.

Statuses: **done**, **blocked**, **parked**.

| Step | Deliverable | Status | Evidence |
|---|---|---|---|
| 1 | `docs/validation-recipes.md`, `V-DC12`, `tests/test_recipes.py` | done (`76f5bc6`) | end-to-end 104 tests OK; links 221 checked, 0 broken |
| 2 | `verify refs`, correction guide | done (`ca65d58`) | verify 222 tests OK |
| 3 | `card_coverage` Coverage row, layout A, default off | done (`dbc486d`) | gate 444 tests OK; `gate_diff` 173/173 identical; 7 of 7 ablations bite |
| 4 | "When something fails" in `docs/verification.md` | done (`591745d`) | links OK |
| 5 | `docs/exercise.md` with a recorded rehearsal of the missing-label stop | done (`591745d`) | step 4 run once at 0.11.0 on the fixture; steps 1 to 3 not rehearsed live |
| 5b | Regenerate `docs/example.md` at 0.12.0 | **blocked** | needs `scilintr` and an `Rscript` whose R has it; none on this host. Run `MX_E2E_SCILINTR=<path> MX_E2E_RSCRIPT=<path> python3.12 tests/e2e/make_example.py` where both exist |

Baseline before the work (0.11.0 at `50b9ca0`, python3.12): gate 441, verify 218, validation 27, end-to-end 103, links 208 checked, 0 broken.

## Not done, on purpose

- Trace view for one plan row (mostly regroups the report), portable replay, a capability catalog, a metadata schema, evaluation frameworks.
- Turning `card_coverage` on by default: decide after the ~2026-10-31 before/after usage measurement of 0.11.0.
- The `gate-diff` CI job has not been run on this change (needs a push; it ran locally, 173/173).

## Limits

- `verify refs` finds only references recorded in saved bundles; "no recorded reference" is not proof a file was unused.
- A bound check is declared and pinned; the card does not say it ran.
- Fixture results show the checks work on the fixture project and the recorded host and versions.
