# Manuscript-reproducibility extension: integration ledger

Date: 2026-10-26. Branch: `feature/manuscript-reproducibility`. Base commit: `c1d6bfd03c0932385dd79a8b32273c05f1f791b7` (v0.16.1). The implementation bundle (`03_MYCELIUM_EXTRA_ENFORCEMENT`, dated 2026-10-26) was reviewed against upstream pin `4547d660197a6ee56601dca9c112b55c82eb3598`, which is an ancestor of this base; all interfaces the bundle touches were re-verified at the base before changes.

## What was added (additive only)

- `network/conventions/manuscript-reproducibility/` — opt-in convention pack v0.1.0 (7 files, bundle content unchanged).
- `skills/manuscript-audit/` — read-only skill: `SKILL.md`, `agents/openai.yaml`, `scripts/manuscript_audit.py`, `tests/test_manuscript_audit.py`.
- `tests/fixtures/manuscript-project/` — committed sample Mycelium project: pack registration sample, local-override sample, declared contract, red/green-capable data, approved-binding template and decision boundaries, CI example.
- A narrow manuscript-routing paragraph in `skills/grill/references/scientific-conventions.md` (the bundle's `GRILL_ROUTING_PATCH.md`, applied verbatim in substance).
- Docs: `docs/reference/skills/manuscript-audit.md`, rows/entries in `docs/reference/index.md` and `docs/skills.md`, README bullet.

No hook, gate, manifest, approval or verification status was changed. The installer (bundle tooling, adjusted copy plan: skill tree instead of root `tools/`+`tests/`, plus the fixture) ran dry-run first; `--apply` copied only new paths and refuses overwrites.

## Overlap enumeration (what was deliberately not re-implemented)

- Sample design, pairing, batch/contrast structure → `data-contract-check` (stronger: reference-backed alignment, h5ad obs, structured alerts).
- Approved intent vs executed model fields → `skills/verify/scripts/method_fidelity.py`.
- What ran vs the approved plan, receipts, provenance → `verify`.
- The new validator covers only: declared figure-source columns, small keyed tables with declared numeric/ratio invariants, declared-file availability.

## Validator corrections found in integration review (each with a test)

| Bug | Fix | Test |
|---|---|---|
| `--result-json` could overwrite the contract or a declared input | Destination resolved against `--root`; collision refused with exit 1, nothing written | `test_result_json_collision_is_refused`, `test_result_json_writes_benign_destination` |
| argparse usage errors exited 2, colliding with "block" (verify reads 2 as a failed check) | Usage errors exit 1 ("not run" in verify's reader) | `test_usage_error_exits_1_not_2` |
| `ratio_invariant.tolerance` unvalidated (negative/non-finite reached `math.isclose`) | Non-numeric, non-finite or negative tolerance is a malformed declaration → gap; `0` accepted | `test_malformed_tolerance_is_gap`, `test_zero_tolerance_is_accepted` |
| `data-manifest` message re-derived the path without `resolve_under` | Message uses the observed path | covered by green tests |
| Declared column lists and `outputs` accepted malformed types (e.g. strings iterated per character) | `column_list` validation; malformed declarations are gaps | `test_malformed_column_declarations_are_gap`, `test_outputs_string_is_gap` |
| Symlink escape regression guard | `resolve_under` containment already rejects; test added | `test_symlink_escape_is_gap` |

## Source-to-assertion ledger (acceptance case → test → result)

| Acceptance case | Asserted by | Result |
|---|---|---|
| Missing plotted source column fails deterministically | `test_missing_plot_column_red` | pass |
| Duplicate sample key fails deterministically | `test_duplicate_keys_red` | pass |
| Benign control passes | `test_green`, `test_committed_fixture_passes` (committed fixture) | pass |
| Inaccessible file / unrun check is never a pass | `test_missing_source_is_gap_not_pass`, `test_path_escape_is_gap`, `test_symlink_escape_is_gap`, `test_duplicate_json_fields_gap` | pass |
| Negative/non-integer counts and wrong ratio fail | `test_counts_and_ratio_red` (4 subcases) | pass |
| Result JSON is judged correctly by verify's actual reader | `test_verify_reader_maps_*`, `test_verify_reader_detects_changed_contract` (via `gate.load_verify()`) | pass |
| Inactive pack is not cited; statistical-only grill is not polluted; local override precedence preserved | `test_manuscript_routing_is_opt_in_and_bounded` (reference contract; negative controls in text) | pass |
| No hook, gate, manifest or verify file changed; existing files touched only where listed below | `git diff --stat --diff-filter=M c1d6bfd` (6 files: `README.md`, `docs/reference/index.md`, `docs/skills.md`, `opencode/tests/gate.test.js`, `skills/grill/references/scientific-conventions.md`, `skills/grill/tests/test_grill_references.py`); installer overwrite refusal | pass |

## Verified vs unverified

Verified in this sandbox (Python 3.11): the new test suites (`test_manuscript_audit.py`, 21 tests; the grill reference tests, 16), the link checker on changed Markdown, and the OpenCode adapter tests with node (22/22; the adapter's expected skill count was raised from 14 to 15 for `manuscript-audit`).

Full Python sweep at commit `06435d8` (the CI loop over `hooks/tests`, `skills/*/tests` and `tests/test_*.py`, 45 suites): 43 passed, 2 failed. Neither failure comes from this branch:

- `tests/test_end_to_end.py`: `Defects.test_F_06` and `Defects.test_V_02b` expect `CONFORMS_WITH_GAPS` and get `DOES_NOT_CONFORM`. They fail 3 of 3 times both on this branch and on the base commit `c1d6bfd` in a clean worktree, so the failure predates the branch in this sandbox. Not investigated further; whether upstream CI passes them was not checked.
- `skills/verify/tests/test_verify.py`: `test_unknown_exit_status_is_a_gap` failed once during the sweep, while another test sweep was running at the same time. Re-run alone it failed 2 of 4 times on the base commit too, then passed 3 of 3 on both once the machine was quiet. It depends on timing (writers within verify's 5 s clock-skew window).

Skipped tests need tools this sandbox lacks, such as real scilintr with `MX_E2E_REAL_TOOLS`, or a Python 3.6 interpreter.

Errata: the commit message of `06435d8` says "22 tests" for the validator suite; the suite has 21. The OpenCode skill-count change (14 to 15) was not in the first version of this ledger.

Unverified here — labeled as such, not claimed:

- Live host-hook behavior: no native Claude Code / Codex / OpenCode session ran the gate, so receipt/attribution behavior of a bound manuscript check through a real host is unverified.
- A native approved-plan `verify` scenario. A simulated-host oracle now drives the real gate, the checker and `verify` through all outcome states, and the native Claude Code runbook and grader are pre-registered. See [the native-verify record](2026-10-26-manuscript-native-verify.md). No native session has run, so the native result is still unverified.
- Live activation through upstream Mycelium's `install_convention.py --network-dir` was not run; the fixture's `ACTIVE_CONVENTIONS.yaml` is a sample following the shape `scientific-conventions.md` checks, not a product of the upstream installer.
- No published figure was reproduced. Nothing here demonstrates full published-paper reproducibility.
- The fixture's registration YAML format is not validated against upstream Mycelium's installer schema (no upstream checkout available).

## Limitations

The validator trusts the author's declared columns, keys and invariants: an omitted column absent from the declaration escapes detection, which is why the skill requires reading the actual figure scripts. Passing checks are statements about small declared tables, not about scientific validity, aesthetic completeness, or producer execution.
