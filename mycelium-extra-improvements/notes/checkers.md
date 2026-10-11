# checkers workstream (branch checker-features), base 1db67c1

## Status
- D6: DONE, one commit (patch 0001).
- D9: NOT DONE. I ran out of iteration budget after D6. Nothing for D9 is committed, and its roadmap Status stays `todo`. The design notes below are meant to be picked up.

## Commit 0001 feat(data-contract-check): read h5ad obs and warn on graded batch imbalance (max_share)
Files: skills/data-contract-check/scripts/data_contract_check.py, tests/test_data_contract_check.py,
tests/fixtures/imbalance.tsv (new), SKILL.md, docs/roadmap/05-mindfulness-core.md (D6 Status done, Acceptance wording).
- `.h5ad` tables: `obs` is read through h5py, which is imported lazily inside read_h5ad_obs, so the script stays stdlib-only when h5py is absent. X and layers are never read. Only the columns the contract names are read, plus the index.
  Supported encodings: anndata >= 0.8 (dataframe 0.2.0 with `_index` and `column-order`; array and string-array
  datasets; categorical groups with codes/categories, where code -1 is missing; nullable-integer, nullable-boolean, and nullable-string-array groups with values/mask)
  and anndata 0.7 (a codes dataset whose `categories` attr references `__categories/<col>`). A compound or other obs is a gap, and so is a file that is not HDF5.
  A column in an unrecognised encoding is a gap only for the checks that name it; the other checks still run.
  Values are stringified the way a CSV export would write them: 28, 28.0, True/False. NaN, masked values, and missing categories become "", which counts as missing.
- New gap concept: alert severity "gap", blocking false; check status GAP; exit code 3 when there is a gap and nothing blocks (2 still wins). The header line gets ", N gaps" only when N > 0, so CSV output is byte-identical to before.
- `max_share`: optional. It warns when count(batch, level)/count(level) > max_share (strictly greater). It is validated as a number in (0, 1] and is not a bool; a bad value is a usage error (exit 1). It is evaluated after the existing checks and is skipped on the early returns for full nesting and fewer than two levels.
- The cross-table (counts, plus each cell's share of its level, plus totals) is printed on every run of batch_confounding that has rows, including runs that block. In JSON it is `checks[i].cross_table`.
- Existing behaviour is unchanged: all 13 existing tests pass, and their bodies are unchanged. Only the `run` helper was refactored to wrap a new `invoke`.

## Tests run
- Before: full suite, 8 files, all OK (test_gate skipped=1). The env -u CONDA_* form from COMMON.md was used throughout.
- After: full suite, all OK. test_data_contract_check: 27 tests OK. These include 7 h5ad tests, run here with h5py 3.14 and anndata 0.12.1 installed; one of them round-trips a file through anndata's real writer.
- With PYTHONPATH pointing at a stub `h5py.py` that raises ImportError: 27 run, 7 skipped, each with a clear reason. The absence test (WithoutH5pyTest) uses the same stub, so it always runs and asserts GAP and exit 3.
- 3.6 grammar check (ast feature_version=(3,6)): OK on both changed .py files.
- Negative test: disabling the max_share alert (`if over and False`) makes 3 tests fail and 1 error, so the tests catch it. The file was restored afterwards.
- Not done: a negative test for removing the cross-table print. The table assertions in test_max_share_warning_shows_the_table and test_table_shown_when_the_check_blocks would catch it, but I did not run that break.

## Deviations / decisions for the maintainer
- Exit code 3 for "gap, nothing blocking" is new. The roadmap says "gap" and the checker previously had no gap concept. Callers that read only the exit code see non-zero, so a gap is never treated as clean.
- max_share counts rows. On a per-cell obs it is therefore a share of cells, not of samples, and SKILL.md says so. An optional `unit` field that would count distinct units instead was NOT added, because it would grow the scope. It is worth deciding.
- Outside my ownership, not edited: README.md line 148 still says "v1 reads CSV/TSV tables; it does not yet check h5ad internals." Suggested replacement: "It reads CSV/TSV tables and the obs of an .h5ad file (through h5py when installed; without it, a gap)."
- The grill checklist (llm-failure-modes.md) was not changed: no row's Check column changes because of D6.

## D9 (not built): design notes from reading the code
- Syntax: the plan table's Source column cell is `default: <reason>` (grill SKILL.md section 3 and the Plan bullet; analysis-decisions.md; new_analysis.py:318 scaffolds the placeholder `[repo: / user / default:]`; c1 design row 3 has `default: matches step 2`).
- plan-review has no scripts/ yet. Suggested: skills/plan-review/scripts/default_reasons.py, stdlib, with `check_plan(plan)` returning flags of the form {row (first cell), column, text, problem}. It would be run from stdin with `--plan <(...)`, exit 0 when advisory flags are found and exit 1 on a read error.
- Put the EMPTY_PHRASES list as a constant at the top of the module (stdin runs have no `__file__`, so a separate data file is awkward).
- Rule sketch: strip empty phrases and filler words; flag "no reason" if nothing is left, "empty phrase" if a phrase was removed and fewer than 3 words remain, and "too short" for fewer than 3 meaningful words. With 3, "matches step 2" in the C1 fixture is not flagged.
- verify hook-up: add a helper that does sys.path.insert(PLUGIN_ROOT/skills/plan-review/scripts) and imports default_reasons. Each flag becomes report.add("info", ...), so the status does not change. Report a gap if the module cannot be imported or raises, because a missing check is a gap. Call it from check() just before `envs = conda_snapshots(...)` (about line 838, away from E3's line 660). Tests go in a new skills/verify/tests/test_verify_defaults.py, set up by copying test_verify.py's approve() pattern via the real gate hooks.
