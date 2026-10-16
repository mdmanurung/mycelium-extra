# Gate and hook audit, 2026-10-16

Starting HEAD: 384e6394b71cdae6ab983f0b10fa8d4f5e65c900.
Owned: hooks/gate.py, hooks/tests/test_gate.py, hooks/tests/gate_diff.py.
Pre-existing gate/test changes implementing max_runs_per_approval were preserved in pre-existing.patch.

## Repairs

1. Compound shell results no longer claim each gated script executed successfully, or attribute the first Slurm job ID to several submissions. Per-run status is unknown; command_exit_status/source retain aggregate outcome. Verify owner added aggregate failure checks.
2. Bash state protection resolves symlink targets even when the literal state-folder name is absent. Ordinary reads and nonstate piped writes remain allowed.
3. Existing literal quoted/backticked paths with spaces are granted and pinned whole; path fragments do not grant a different folder.
4. Malformed/truncated approval records, invalid timestamps, invalid nested fingerprints, and corrupt first-run script-pin ledgers produce controlled state denials instead of disabling the gate through generic on_error behavior. Generic on_error policy remains intact. Legacy no-pins records remain accepted (fixture corrected to genuine hex hash).
5. Differential harness compares both gates with the same verify/error helper layout and normalizes source-path/line warning noise.

## Evidence

- receipt-before.log: two failing regressions on compound status and duplicate scheduler ID; receipt-after.log passes both.
- state-alias-before.log: symlink write incorrectly allowed; state-alias-after.log passes alias writes, reads, and existing write protection tests.
- spaces-before.log: quoted spaced script denied; spaces-after.log passes grant/pin/fragment tests.
- corrupt-before.log: corrupt approval not blocked; corrupt-after.log passes controlled-denial and generic-error-policy tests.
- final-state-boundaries.log: 7 tests pass on Python3.6/C including nested malformed pin ledgers and both entrypoints.
- final-boundaries-and-pipes.log: 5 boundary tests pass after piped-write false-positive refinement.
- final-targeted-py314.log: 7 tests pass on Python3.14.5.
- final-legacy-fixture.log: both entrypoints accept genuine legacy records without pins.
- baseline-tests.log: 247 tests passed, 2 skips. This long-running baseline overlapped edits; immutable pre-existing snapshot and failing-before cases are stronger defect baseline evidence.
- gate-diff-complete-py36.log and gate-diff-complete-py314.log: BOTH 145/167 identical. All22 differences intentional: four new regression cases (symlink write deny, spaced-script allow, fragment-folder denial, malformed-state denial) plus18 compound receipt changes. No unexpected differences.
- Root owns final full immutable-tree matrix after all edits settled. Earlier root runs saw legacy fixture before its update and one transient in-place edit SyntaxError; do not count those as final frozen results.

## Coverage and limits

Existing gate suite covers grants/denial/sessions, stale approval and inputs, script and notebook pins, budgets, directories, parser wrappers and sbatch cwd, state writers, lint cards/write/run/stop, parallel lint records, receipt environment/Git/schedulers, exploration, native-host payload adapters, loader errors, unavailable tools, and source compatibility.
New tests are deterministic and disposable; no actual scheduler submissions, paid reviews, production analysis, external sends, host trust/config edits, commits, or pushes.
Native host skill compliance and dispatch were not established by launcher tests. Dynamic shell/interpreter execution remains heuristic and the gate is not a security sandbox. Space-path support recognizes explicit existing literal paths; this does not turn Markdown or shell text into a complete language parser. Pin budgets and folder listing fingerprints retain documented evidence limits.

## Independent-review followups

- Trailing background operator at every shell-wrapper layer now keeps per-run status unknown. Tokenizer reports real unquoted operators so an ordinary literal ampersand argument remains allowed. background-before.log fails both entrypoints; background-after-py36.log passes4 tests and background-after-py314.log passes2.
- Approval timestamps must be representable by time.localtime and year1..9999; overflow and unsupported years produce controlled state errors. timestamp-before.log fails on1e300; timestamp-after-py36.log and timestamp-after-py314.log exercise both entrypoints after repair.
- gate-diff-selfcheck-final.log: identical-source comparison167/167 identical, validating warning/layout normalization without hiding behavior differences.
