# M8-T03 (cheap form) triage — plan b9f40280

Snapshot 2026-10-06 15:38: extra 74ddf53 (0.9.45); scale 99bbf6b (74 receipts, 20 plans); bmv_pilot_cytof_integration a6c7f49 (230 receipts, 29 plans).
Ran from the working tree: `verify.py status`, then `report <hash> --json` for 49 plans. `write` never run. Nothing edited in either repo.
Caveat: `scilintr` and `Rscript` were not on PATH in this shell, so every report carries a lint gap and no lint finding is counted.

## Statuses (45 reports; 4 crashed)
| repo | CONFORMS | CONFORMS_WITH_GAPS | DOES_NOT_CONFORM | crashed |
|---|---|---|---|---|
| scale | 0 | 11 | 9 | 0 |
| bmv | 0 | 11 | 14 | 4 |

## Class B — verify wrong or misleading (defect candidates)
| ID | What | Evidence | Where |
|---|---|---|---|
| B1 | `status` and `report` crash when a plan names scripts by both absolute and relative path | bmv plans 5c219254, 9d20e8eb, 790a9510, 87c4be15 (the newest bmv plans); `ValueError: Can't mix absolute and relative paths`; `status` for the whole repo dies | `guess_analysis_dir`, verify.py:485 (`os.path.commonpath`); `--analysis-dir` bypasses it for `report` only |
| B2 | `Outputs:` shorthand parsed literally: `{a,b}` braces and `…_x.csv` ellipsis become paths like `flashier_seminmf_` or `.csv`, then "does not exist" gaps | scale 7b1f02f7, 93f5d9f2, e6fa6657, f5b40765, afe4b5fa, 781c90d4, 52fda098 (21 findings); bmv 3 findings, form not checked | Outputs-line parsing in verify/gate |
| B3 | A log file (a redirect target) counts as a planned script, so a run rewriting it "edits the script after its run" and blocks | scale 781c90d4: `logs/fit_seminmf_raw.log` | planned-path extraction |
| B4 | An older plan blocks for "script edited after its run" even when a later approved plan re-ran the script after that edit; no "superseded by plan X" note | 13 of 25 such blocks (bmv 12, scale 1) | verify.py:1085 and 1105 |
| B5 | Volume: per-file "likely written by" gaps are 6,395 of 7,898 findings (81%); 21 of 45 reports have over 100 findings, the largest 819 | scale 13eee415 (760 of 819) | gap reporting for outputs |

## Class D — can't tell
- D1: scale 7b1f02f7 blocks because the plan's own doc `docs/plans/2026-10-03-bcells-flashier-seminmf.md` is on the `Outputs:` line and was written before approval. Legitimate, or a plan that lists its own file?

## Class A — about the analyses, not Extra
- bmv c47b4284: Slurm jobs 25697486 and 25697516 ended OUT_OF_MEMORY.
- bmv d717de9a: pinned `basemalvac_ebmf_replication.R` is now missing.
- scale 2f197be2, 7a4554cb, b09e336e: a pinned input changed since approval.
- 12 "edited after its run" blocks with no later run (bmv 7, scale 5).

## Class C — known or expected, counted only
- 29 runs with no exit status in 16 plans (the KB-04/V-20 family; background and `sbatch`).
- 249 "ran but not in the plan table"; 10 "run with no approved plan".
- 61 `scilintr` not found, in 42 reports (this shell's PATH, not the repos).
- Untracked-when-run, wrapper with no Snakemake records, unlabelled fact tags in older plans.
- Zero reports reached CONFORMS, partly because of the missing lint tools above.

## Status after 2026-10-06 (added at handoff)
- **B1 fixed** in 0.9.46 (`V-26`). Plan paths inside the project are read root-relative in `gate.py` and `verify.py`.
- **B4 re-read and fixed** in 0.9.47 (`V-27`). The "13 of 25 superseded" framing above was wrong: checked against approval times, none of the edited-script blocks was covered by an approval. The blocks were right; the finding now says whether an approval covers the current version. Status unchanged.
- **Open:** B2, B3, B5, D1. Lint was not checked (no `scilintr`/`Rscript` on PATH in that shell).
