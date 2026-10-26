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
| No existing file modified, no hook/manifest change | `git status` scope check at apply time; installer overwrite refusal | pass |

## Verified vs unverified

Verified in this sandbox (Python 3.11): the new test suites, the full existing Python test sweep, the link checker on changed Markdown, and the OpenCode adapter tests where node is available. Results are in the delivery notes.

Unverified here — labeled as such, not claimed:

- Live host-hook behavior: no native Claude Code / Codex / OpenCode session ran the gate, so receipt/attribution behavior of a bound manuscript check through a real host is unverified.
- A native approved-plan `verify` scenario (approved plan → pinned checker → `verify` Validation section in all outcome states) was not executed; the reader side is covered by the `read_result` compatibility tests only.
- Live activation through upstream Mycelium's `install_convention.py --network-dir` was not run; the fixture's `ACTIVE_CONVENTIONS.yaml` is a sample following the shape `scientific-conventions.md` checks, not a product of the upstream installer.
- No published figure was reproduced. Nothing here demonstrates full published-paper reproducibility.
- The fixture's registration YAML format is not validated against upstream Mycelium's installer schema (no upstream checkout available).

## Limitations

The validator trusts the author's declared columns, keys and invariants: an omitted column absent from the declaration escapes detection, which is why the skill requires reading the actual figure scripts. Passing checks are statements about small declared tables, not about scientific validity, aesthetic completeness, or producer execution.
