# c1b (branch c1-harness): build-order commit 2 delivered

Base: bundle `improvements` (1db67c1) + c1 commit 1 `f7a54d9` (`git am /mnt/shared-workspace/c1/patches/*.patch`).
My commit: `f3d74ff test(e2e): add the harness and the baseline chain test`, exported with `git format-patch f7a54d9`.
Patch: /mnt/shared-workspace/c1b/patches/0001-test-e2e-add-the-harness-and-the-baseline-chain-test.patch
(md5 9f52ed4556af6e0a2671022310658c4c, the same as the local copy). `git am` of c1 0001 + c1b 0001 onto a fresh clone of the bundle
applies cleanly, and tests/test_end_to_end.py passes there.

## What the commit adds
- tests/e2e/harness.py (stdlib, 3.6 grammar): `Project.fresh(r=None|False)`, `hook`, `pre_bash`, `approve`, `approval`, `receipts`,
  `agent_bash(command, effect=None, response="claude"|"legacy")`, `skill`, `stdin_skill`, `data_contract`, `verify`/`verify_command`,
  `lineage`, `snakemake_record`, `space_outputs`, `fill_ledger`; helpers `registered_events`, `copy_summary`, `status_line`.
  Hooks run as hooks.json registers them: `python3 hooks/gate_run.py <entry>`, with the event-to-entry map read from hooks.json at test time.
- tests/e2e/plans/baseline_plan.md and baseline_contract.json (text copied from design 5.1/5.2).
- tests/test_end_to_end.py: `BaselineChain.test_baseline_chain` (R if on PATH), `test_baseline_chain_without_r`, both the 11 steps of
  design 7 ending in `Verify status: CONFORMS`; `BashEvents` (4 small tests: success shape has no exit code, failure event only sent
  when registered, legacy shape, hooks.json mapping).
- No new tests/e2e/expected/ files were needed (commit 1 shipped them).
- docs/design/c1-fixture-project.md corrections (below); docs/roadmap/03-robustness.md C1 Status: `in-progress: build-order commits 1-2 landed`.

## Design corrections (in the same commit)
1. Hook events (6.1): success = `PostToolUse`, `tool_response {stdout, stderr, interrupted, isImage}`, no exit code; failure =
   `PostToolUseFailure` with top-level `error` (`Exit code N\n<stderr>`), `is_interrupt`, `duration_ms`, no tool_response, and sent only
   if hooks.json registers it (today it does not, so before E3 a failed run leaves no receipt). `response="legacy"` keeps the
   `{stdout, stderr, exit_code}` dict. Hooks go through gate_run.py (as hooks.json does), not gate.py directly.
   Confirmed on current base code: the verify script rows read `ran (exit status not recorded)`, no finding, `Verify status: CONFORMS`.
   Step 6 accepts either `ran` form; KB-04 row now says the realistic shape hits it on every baseline run.
2. Timing (6.4): the gate has no time injection (receipt ts = time.time()), so `space_outputs` moves each output's mtime with os.utime to
   the midpoint of (previous receipt ts + 5, its receipt ts + 5] when it would otherwise credit an earlier receipt; fails if the window
   < 20 ms. No sleep. Outputs can carry an mtime up to ~5 s in the future; verify does not object.
3. Data contract (6.1, step 2): run in the documented `<(cat <<'EOF' ...)` form through `bash -c` (no temp file); the exact string is
   sent to PreToolUse (silent). Inline probe: `python3 -c "print(open('data/processed/vaccine-cohort/counts.tsv').readline().split()[:3])"`
   via agent_bash after run 03: gate silent, no receipt, lineage action `script: null`, report says `1 inline command(s)`.
   `verify write <h> --analysis-dir analysis/vaccine-response` in the documented form: the gate does NOT deny it (checked every run
   by `skill()`), so no known-bug entry was added.
4. R: with /opt/conda/bin/Rscript, 03 runs for real and summary.tsv matches expected sha256. Without R: PATH drops every dir holding
   Rscript (test asserts `command -v Rscript` fails), 03 runs as `copy_summary` effect with a real receipt. Both pass.
   Also: skill commands now get a PostToolUse after they run (realistic); the data-contract stdin form leaves no receipt.

## Checks
- 3.6 grammar (ast feature_version=(3,6)): harness.py, test_end_to_end.py OK.
- test_end_to_end.py: 6 tests OK, ~10 s total (each chain ~5 s), with R and without R.
- Full suite scrubbed (env -u ...), before (at f7a54d9, per c1 NOTES: all 9 OK) and after: all 10 files OK (test_gate OK skipped=1,
  34.7 s; test_verify 43.0 s). Without the env -u wrapper: only skills/verify/tests/test_verify.py FAILED (failures=3), the known
  CONDA_* leak from COMMON.md; test_end_to_end.py passes unscrubbed too (harness scrubs its own env).
- Negative 1 (remove de_results.tsv after the runs): test fails at step 6, report has `gap: Output ... de_results.tsv does not exist.`,
  `Verify status: CONFORMS_WITH_GAPS`.
- Negative 2 (approve() skipped): fails at step 4: "the gate denied `python3 .../01_select_samples.py`: mycelium-extra gate: blocked
  because no active approved plan covers this run. ..." plus the chain trace.
- Negative 3 (space_outputs disabled): fails at step 6, de_results.tsv credited to run 01. Note: verify still said CONFORMS in that case
  (same plan), so mis-attribution within one plan is silent; maintainers may want to know.
- Negative tests were run from a scratch monkeypatch script, not committed.

## Limitations / open questions
- The probe runs after run 03 so that it cannot be the earliest receipt-window candidate; it leaves no receipt anyway.
- Before E3, a failing planned run produces no receipt at all with realistic events (PostToolUseFailure unregistered).
- Only files under tests/, the design doc and the roadmap C1 Status line were changed.
