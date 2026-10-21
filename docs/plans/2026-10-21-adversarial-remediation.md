# Adversarial audit remediation, 2026-10-21

Scope: repair the nine defects in the dated adversarial audit of `ec58e1e`.
The original audit and observations remain unchanged. The validation below
predates the user's subsequent request to commit and push the repairs. No version
bump, release, plugin installation or external-service qualification is included.

## Repair tracker

| Finding | Repair | Regression evidence | State |
| --- | --- | --- | --- |
| 1: result overwrites inputs | Refuse all declared input destinations and symlink aliases, even after a contract error; publish through unique temporary files with failure cleanup | `tests/test_adversarial_regressions.py`: input preservation and result-writer cases | Verified locally |
| 2: shell approval bypasses | Decode supported ANSI-C literals; leave unsupported escapes unresolved; recognize `ionice` and `setsid` options | `hooks/tests/test_gate_scan_fixes.py`: denied runs, benign controls and actual Bash byte comparison | Verified locally |
| 3: pending-directory symlink | Use the shared guarded writer; report CLI refusal without a traceback | `tests/test_adversarial_regressions.py`: pending-write case | Verified locally |
| 4: sensitive evidence paths | Withhold sensitive analysis/output/reference coordinates as null and scrub other exported strings | `tests/test_adversarial_regressions.py`: evidence projection case | Verified locally |
| 5: malformed CSV verifies claims | Require strict quoting and consistent field counts before reading cells or counting rows | `tests/test_adversarial_regressions.py`: cells, row counts and end-to-end unverified claims | Verified locally |
| 6: invalid validation IDs crash | Add only valid string IDs to the duplicate-ID set | `tests/test_adversarial_regressions.py`: structured errors and real hook response | Verified locally |
| 7: non-finite consent timestamps | Require finite floating timestamps, retaining the newer-than-preparation contract | `tests/test_adversarial_regressions.py`: non-finite/boolean/stale refusals and finite newer control | Verified locally |
| 8: refused write creates outside directories | Check state symlinks before directory creation, for writes and locks; retain the publication-time check | `tests/test_adversarial_regressions.py`: no outside filesystem side effects | Verified locally |
| 9: malformed H5AD categorical codes | Validate list shape, integer type, category bounds and the standard -1 missing sentinel | `tests/test_adversarial_regressions.py` and `skills/data-contract-check/tests/test_data_contract_check.py`: malformed encodings and valid controls | Verified locally |

## Validation

The [repair receipt](2026-10-21-adversarial-remediation/receipt.json) binds the
candidate to source hashes, commands, outcomes, skips and log hashes.

- 40 Python test programs: 1331 passed, 34 skipped, no failures.
- Original standard-library probes: 137/137 pass on Python 3.12 and Python 3.14
  under the C locale; optional H5AD probes: 3/3 pass on Python 3.11.
- H5AD reader suite: 102/102 pass with the existing optional-reader environment.
- Original-source controls: new general regressions, shell regressions and
  malformed-H5AD regressions fail against `ec58e1e`.
- Existing differential corpus: 173/173 identical before and after the repair;
  the pinned reference still has exactly its 57 reviewed intentional differences.
- Guard ablations: 17/17 bite; direct Node adapter run: 22/22 pass.
- Markdown links: 483 checked, none broken; changed Python files parse as 3.9.

The Python suite's skips include unavailable optional tools/readers and the
local-only conventions pack absent from the isolated worktree. The separate H5AD
run exercises reader-dependent cases. The five sealed-key `Leakage` tests were
excluded; public scorer tests ran. Full logs remain at the paths in the receipt;
the receipt retains each log hash and its final outcome.

The existing differential corpus is kept unchanged. Its 173 comparisons do not
cover every shell spelling; the newly denied spellings have explicit regression
tests. Native agent dispatch, scientific validity, real-browser accessibility and
concurrent symlink-swap resistance are not established by these local checks.

## Delivery

The validated changes were applied to the main working checkout without a commit
or version bump. Production and regression source hashes match the isolated
candidate. Delivery checks passed: 10 regression tests, 137 standard-library
probes, three H5AD probes and 483 Markdown links. All 17 original artifacts were
verified: the current handoff was refreshed with its original text retained as a
historical section; the other 16 artifacts are byte-identical.

## Source publication

The user subsequently authorized committing and pushing the repairs. The repair
code, regression tests and validation receipt are published together. The dated
audit artifacts and older handoff archives remain local and unchanged. The receipt
records the validation-time state; its no-commit/no-push note is historical.
