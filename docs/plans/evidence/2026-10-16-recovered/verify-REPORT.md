# Verification and end-to-end stress audit

Ownership: skills/verify/**, tests/e2e/**, tests/test_end_to_end.py, docs/design/c1-fixture-project.md. Existing dirty edits preserved; see preexisting.diff. No commits, pushes, native host configuration changes, external messages, or production jobs.

## Reproduced and repaired

1. Header-only claim table crashed with IndexError. It now leaves an explicit unverified claim gap; `rows` still returns zero legitimately.
2. Duplicate column labels silently verified the first column even if another differed. Duplicate named columns now produce an ambiguity gap.
3. A finite claim with an enormous exponent crashed while constructing its rounding quantum. Unsupported quantization now yields mismatch rather than aborting all claims.
4. Numeric syntax whose exponent cannot be represented yielded None then AttributeError; fraction-to-percentage arithmetic could raise Decimal Overflow. Both now leave explicit numeric-range gaps, preserving other verdicts.
5. Truncated JSONL was silently ignored, while valid JSON scalar/list receipts crashed. The shared reader validates basic receipt shape and timestamps, skips invalid records, and `report` explicitly marks incomplete history as a gap. List/status/explore/multiplicity remain usable with such records.
6. Invalid calendar dates in lineage and Slurm timestamps crashed parsers. Invalid lineage times are ignored, and invalid Slurm completion times remain unknown without overriding the scheduler state.
7. Structurally malformed Snakemake metadata and invalid/nonfinite job times crashed verification. Such records now leave explicit workflow-evidence gaps.
8. Integrated the gate agent's compound-shell receipt schema: unknown individual execution stays a gap; failed/interrupted overall command evidence remains blocking. It never claims that every syntactically named shell step ran.
9. Corrupted approval JSON (scalar/list/boolean, nonfinite approval time, invalid plan/pins) crashed or disappeared from inventory. All approval-dependent actions now share the gate validator and exit with a controlled invalid-state message; independent stale/explore remain available. Receipt timestamps outside the supported calendar range are rejected.
10. Frozen plans incorrectly labeled all approval sessions as Claude Code. Host-neutral session wording now preserves the facts actually recorded.

## Supporting integration repairs

- A-3 ablation still searched for the gate condition before the user's pre-existing max-runs addition. Updated its exact target, retaining the existing G-02 mutant oracle.
- V-02a and V-02b intentionally now report compound-execution gaps for `python script || true`. V-02b still records a known scientific miss: a truncated output cannot be diagnosed from receipts alone.
- V-30 uses a single simulated `sbatch $S` invocation to isolate the SubmitLine attribution guard. Its earlier compound assignment plus submission cannot safely identify an individual scheduler job from aggregate tool output under the new gate contract. Failed-job blocking remains asserted.
- Updated skill and fixture contracts to explain the intentional differences.

## Validation

- Baseline verification/default-reason tests: 70 passed (57.716 s).
- Baseline end-to-end: 79 tests, 2 optional skips (118.248 s).
- Final verification/default-reason tests before the approval-boundary followup: 77 passed (66.544 s). The parent owns the final 78-test compatibility matrix; see fixed-state-boundaries.log for the followup.
- Focused updated end-to-end cases V-02a/V-02b/V-30: 3 passed (5.589 s).
- All four guard ablations bite: each planted defect passes against real code and fails with its named guard disabled.
- Full final end-to-end: 79 tests, 2 optional skips, passed in 146.614 s (final-e2e.log).
- `git diff --check` passed for owned scopes.

Fail-before evidence: reproduction-claims.log, reproduction-overflow.log, reproduction-receipts.log, reproduction-external.log, reproduction-compound.log.
Pass-after evidence: fixed-claims.log, fixed-receipts.log, fixed-external.log, fixed-compound.log, fixed-approvals.log, fixed-state-boundaries.log (2 tests, 10.780 s).
Other receipts: baseline-verify.log, baseline-e2e.log, final-verify.log, final-e2e.log, updated-e2e-cases.log, ablations-final.log.

## Feature coverage

| Capability | Evidence | Scope |
|---|---|---|
| list | test_write_needs_the_folder_and_list_shows_plans; limit marker test; damaged history test | Script-level, real synthetic gate records |
| report | conforming/unknown/failed/edited/deleted runs; changed pinned inputs; output attribution; claims; fact tags | Read-only report consistency, not scientific validity |
| write | test_write_provenance_and_rewrite; conda/pip snapshot tests | Repeat writes and index replacement tested; no whole-bundle transaction guarantee |
| stale | test_stale_lists_what_changed_since_provenance; e2e edit journey | Input/code/output changes, deleted outputs and gate-free provenance |
| status | test_status_lists_plans_with_verify_lint_stale_and_manifest | Saved lint/verification, manifest and stale integration |
| diff | test_diff_shows_changed_rows_and_flags_choice | Pending/approved table rows and scientific-choice flags |
| explore | test_explore_lists_this_sessions_runs_for_a_plan | Session/all-session records and code differences |
| multiplicity | test_multiplicity_lists_revisions_and_runs_before_the_selected_plan | Earlier approvals, missing approvals, exploratory runs, version markers |
| claims | rounding/truncation/inequality/percent/rows/JSON; wrong row/column; exploratory output; nonfinite numbers; new adversarial cases | Blocked contradictions versus gaps |
| Slurm | failed/completed/missing scheduler; SubmitLine hidden-script matching; arrays/shared IDs; invalid completion timestamp | Fake sacct; no production submission |
| Snakemake | script/notebook commands, historical pickled metadata, inputs not run, wrapper attribution, incomplete jobs, new malformed metadata cases | Synthetic metadata; actual Snakemake not required |
| lint | Python/R/notebooks/Rmd/Quarto extraction, waiver reasons, missing tools and deadline | Deterministic fake linters and extracted-source checks |
| environments | declared/interpreter/session conda prefixes; lockfile paths; pip name/version/direct URL/local install/staleness | Synthetic environment metadata, no package installs |
| multi-skill end-to-end | init, data contract, approval, runs, lineage, report, confirmed synthetic write, status/stale, decisions, scaffold | Disposable projects and simulated unavailable R/schedulers |

## Remaining limits

Native Claude Code/Codex dispatch and agent compliance were not exercised by this worker. Paid reviewers, real Slurm, actual Snakemake execution, actual scientific linters, and scientific validity were not established by fake-tool tests. Root owns cross-Python compatibility and the rest of the project audit.

Provenance updates span several files and are not transactional under interruption or competing writers. Saved environment metadata cannot recover uninstalled packages. Timestamp-based output ownership remains probabilistic. Basic receipt validation is not an exhaustive schema validator for every nested historical field. Existing scientific known misses remain documented; a command receipt does not prove that a method implements the chosen analysis.
