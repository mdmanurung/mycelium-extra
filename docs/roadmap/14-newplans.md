# 14 · New plans: unified roadmap (2026-10-24)

Objective: merge two outside plan bundles into one ordered build list that fits the guiding principles in the [roadmap README](README.md). Both bundles are local and gitignored (`plans/newplans/`).

- **Bundle A**, `mycelium_extra_workflow_integrated_bundle_v2_2026-10-23`: a spec of four PRs (A1 to A4) plus synthetic fixtures. Target `630fc30`.
- **Bundle B**, `mycelium-extra-science-direct-v5`: an overlay that adds a `science` skill, 16 method guides, 13 convention packs and a 264-row source index. Target 0.15.0.

Both were checked against `630fc30` (0.15.0) and [decisions](../decisions.md) on 2026-10-24. Statuses: `todo`, `in progress`, `built`, `done`, `parked`, `dropped: <reason>`, `blocked: <question for the user>`.

## What the check found

- Bundle A fits the principles. Every PR is optional or advisory and adds no skill, hook or gate rule. Its ADRs say to stop on a clash with `docs/decisions.md`; none clashes.
- Bundle A's PR-2 says to reuse the strict table reader. `read_table` (`skills/data-contract-check/scripts/data_contract_check.py:85`) reads the whole file before it returns, so a row budget cannot be honest with it. A2 needs its own streaming loop with the same strict `csv` settings.
- Bundle A's recipe names R1 to R5 clash with the existing single-cell R1 to R3 on `docs/validation-recipes.md`. The new recipes are numbered 4 to 8 on that page.
- `discriminating_check` already exists in `skills/plan-review/references/review-contract.md`, and `track_changes.plan_items` already hands inputs, outputs and validation blocks to `verify diff` (`track_changes.py:199`). Bundle A's revision 2 matches both. A4 is wording plus one summary item.
- Bundle B adds a 14th skill. Bundle A's ADR-01 says "extend skills; do not add skills". The two bundles disagree, and resolved: fold (Q4).
- Bundle B's 16 guides and 13 packs are summaries of archives that include CC-BY-NC-SA and unlicensed sources. Its own `SOURCES.md` asks for a rights review before any publish; resolved: rewrite a subset from scratch (Q2).
- Bundle B's `single-cell-analysis` pack overlaps `tests/fixtures/sc-conventions/` and the pack the user installed. Resolved: it may ship beside them, never replace them (Q5).
- Bundle B read-through (all 16 guides, 13 packs, registry, index, both docs pages, both test files, the apply script):
  - Each guide is about 3 KB of the same template. Only the input contract, three steps and two blocking checks differ, so the method depth is thin.
  - Every guide says original archives are "retained separately in the private v4 bundle". That line must not ship in a public repo.
  - The `multimodal-immunology` pack has an empty "Routing and authority" list: no guide is named.
  - Every pack depends on Mycelium's `robust-analysis` pack. A project without it gets a dependency it cannot resolve.
  - Its apply-script test builds a fake repo, so it shows the script works, not that the guides are right. All 16 `scientific_validation` fields read `pending`.
  - `REFERENCE_INDEX.csv` has 264 rows of third-party skill names and descriptions, with no content.
- Both bundles append to `skills/grill/references/scientific-conventions.md`; they touch different files otherwise. Land B after A and rebase the one reference.
- Neither bundle needs `hooks/` except A3, which edits card rendering in `hooks/gate.py` only.

## Order

Order is by value, then risk. Each item is one feature in its own PR. Version bumps stay a separate commit and need the user's word.

| ID | Item | Touches | Risk | Status |
|---|---|---|---|---|
| A1 | Validation recipes 4 to 8 with runnable checks and synthetic fixtures | `docs/validation-recipes.md`, `tests/test_recipes.py`, `tests/fixtures/validation-recipes/` | low: docs and tests | built 2026-10-24, worktree `feat/newplans-m1`, uncommitted |
| A2 | `data-contract-check --profile-only`: bounded, descriptive, small-cell suppressed | `data_contract_check.py`, its tests, `SKILL.md` | low to medium: new CLI mode, old mode must stay byte-equal | built 2026-10-24, same worktree, uncommitted |
| A4 | Sharper `discriminating_check` wording; one lost-coverage item in `track-changes` | `plan-review` references, `track_changes.py`, tests | medium: read-only, but journal identities must stay stable | built 2026-10-25, committed on `feat/newplans-m1` |
| A3 | Input/output overlap advisory on the full approval and freeze cards | `hooks/validation.py` or adjacent helper, `gate.py` card path, `test_gate.py` | highest: `gate.py`, needs `gate_diff` before and after | built 2026-10-25, see M3 notes |
| B1 | Folded method guidance for 2 or 3 methods (no new skill) | `skills/grill/references/` | low: docs and a static test | blocked: Q6 |

PR-D in bundle B (route one or two methods as their own skills) stays `parked` until B1 exists and routing accuracy is measured.

## M1: first usable milestone (A1 then A2)

M1 ships the two items that need no hook edit and change no default behavior. A researcher gets tested recipes for missing values, joins, key collisions, output invariants and negative controls, and an opt-in descriptive look at a metadata table. A run without these behaves as before.

### A1 · Recipes 4 to 8

- **Scope**: five recipes on `docs/validation-recipes.md`, each with the page's nine fields (claim, inputs, expected answer, invocation, binding, pass/fail/unavailable, deliberate failure, benign control, limit). One stdlib script, `tests/fixtures/validation-recipes/recipe_checks.py`, holds the five checks. Each writes the `{"status", "message"}` result `verify` already reads. Fixtures are the synthetic tables from bundle A.
- **Recipes**: 4 missingness and type conversion; 5 join cardinality and row conservation; 6 identifier normalization and key collision; 7 output invariants (keyed correspondence under a row shuffle); 8 negative controls (break one key, flip one sign, drop one visit).
- **Out of scope**: automatic imputation, tolerances chosen for the user, quality scores, plots, a change to `verify.judge_check`.
- **Acceptance**:
  1. Each recipe has a red fixture the check fails and a benign control it passes (bundle A ids R1-01 to R5-02).
  2. A missing input, unreadable table or absent column gives `unsupported` at exit 0, never a pass.
  3. A check that removes its guard passes the red fixture; one test proves it.
  4. Every binding block on the page parses with the gate's reader (`tests/test_recipes.py` already counts blocks; the count changes).
  5. No edit under `hooks/` or `opencode/`.
- **Tests**: extend `tests/test_recipes.py`. Run `python3 tests/test_recipes.py`, `tests/test_fixture_data.py`, `tests/check_links.py`.
- **Effort**: M.

### A2 · `--profile-only`

- **Scope**: `--profile-only --profile-spec SPEC` on `data_contract_check.py`. `--contract` stays required unless `--profile-only` is given. The spec is `mycelium-extra.data-profile-request.v1`; unknown keys, negative, bool or oversized numbers are usage errors. Output is a short human block headed "descriptive, not a validation result", or JSON with `--json`, schema `mycelium-extra.data-profile.v1`. CSV and TSV are read by a streaming loop with the same strict settings as `read_table` (UTF-8, strict quoting, duplicate headers, extra fields). A `.h5ad` table gives `inspection: unavailable`, because `read_h5ad_obs` cannot read `obs` within a budget.
- **Privacy**: aggregates only. Counts below `small_cell_suppression` are hidden, and a complementary cell is hidden too so subtraction cannot recover them. If that cannot be done for a table, drop the breakdown and say so. No row or participant ids in any output.
- **Coverage**: `inspection` is `complete`, `partial` or `unavailable`. A partial scan sets `rows_total` to null and labels counts "inspected rows only".
- **Out of scope**: profile saved to a file (add with a realpath collision guard when asked), plots, imputation, H5AD, any use by `verify`, any change to `contract_result.v1`.
- **Acceptance**: bundle A ids P2-01 to P2-12, and a regression that the old invocation gives identical stdout, `--json` and exit code on the existing fixtures. A profile never carries `status: passed`.
- **Tests**: new cases in `skills/data-contract-check/tests/test_data_contract_check.py`; `tests/test_contract_compatibility.py` unchanged and green.
- **Effort**: M.

### M1 done when

- A1 and A2 acceptance holds, on Python 3.9 and the newest interpreter on the host.
- The CI test sweep, `tests/e2e/ablate.py` and `tests/check_links.py` pass as CI runs them.
- `git diff main -- hooks opencode` is empty.
- The roadmap README lists this page, and each item's Status here matches what was built.

### M1 build notes

- Recipe 7 covers bundle A's shuffle case by key: a metadata copy in another row order passes, a broken id fails. A positional-join check stays with recipe 1 (`V-DC09`).
- A2 uses a separate parser when `--profile-only` is present, so the ordinary usage text and errors are byte-identical (a test pins the usage line).
- A2 hides the whole group breakdown when any cell is below the limit. Complementary suppression of single cells is deferred until someone needs the finer table.
- Evidence (2026-10-25): `tests/test_recipes.py` (17) and the checker tests (116) pass on Python 3.9 (C locale), 3.12 and 3.14. The full test sweep passes on 3.12. 17 of 17 ablations bite. `check_links.py` reports 0 broken of 504 after one relative link in `docs/plans/2026-10-21-mycelium-compatibility/initial-report.md` was fixed (it was broken on `main` too). `sphinx -b html -W` builds. `git diff main -- hooks opencode` is empty.

## M2 build notes (A4)

- `track_changes.lost_coverage` adds one `plan` attention item when an approved revision removes a required binding, redefines one (rows, test files, command or evidence path), or stops declaring an output. It reads bindings with `hooks/validation.read_block` and outputs with `gate.output_words`, so there is no second parser. The item id comes from the two plan hashes, so rescans give the same id.
- An unreadable block on either side is a limitation line, never "no losses". A new binding beside a removed one is listed with "not assessed".
- Deferred from the plan: removed table rows (category 3) and removed inputs (category 4). Rows already get their own per-step items, and `verify diff` shows inputs.
- `plan-review` wording only: `review-contract.md` now says what a `discriminating_check` should contain and that it grants nothing. No new field.
- The limitation text in the generated `docs/examples/*.html` is now stale; regenerate with `tests/e2e/make_track_changes_example.py` and `tests/e2e/make_journal_example.py` when you next refresh the examples.
- Evidence: 7 new tests, 48 track-changes tests in all, pass on 3.9, 3.12 and 3.14. With the new call disabled, 4 of the new tests fail and 1 errors.

## M3 build notes (A3)

- `gate.overlap_findings(root, text)` compares declared names after `repo_relative` (which resolves `..` and links) and reads no file. `procedure_card` shows the detail on the full card and one `Data writes` line on the compact card, only for HIGH or REVIEW. Nothing changed in `on_tool`, `on_post`, `on_prompt` or any decision.
- Not done: the freeze card and the amendment card get no overlap line; an amendment shows only its delta.
- Evidence: 6 new tests; `GateTest` passes (151); with `overlap_findings` returning nothing, 5 of the 6 fail and the control test passes. `gate_diff.py` against HEAD: 173 of 173 identical. Against the pinned base with the reviewed oracle: 116 of 173 identical, 57 expected differences, exit 0. The oracle file is unchanged.

## Later milestones

- **M2, A4** (built, see above): `plan-review` wording only (no new field, no `disconfirming_test`). One attention item in `track-changes` for a removed or changed validation binding, a dropped output, or a removed row between two approved plans. It reuses `verify.plan_changes` and the strict binding reader. A missing baseline reads `not established`, never "no losses". Acceptance: bundle A ids C4-01 to C4-13.
- **M3, A3** (built, see above): literal declared overlap only, shown on the full card, never on `on_tool` or `on_post`. Run `gate_diff` before and after; show any decision that differs. Acceptance: bundle A ids I3-01 to I3-10.
- **M4, B1**: see the section above. Bundle B's apply script and registry are not used.

## Decisions (2026-10-25)

- **Q1** one feature commit per item, no version bump yet. Done: `015b9b6`, `e759059`, `8d83a27`.
- **Q2 (c)** the science guides are rewritten from scratch for a small subset of methods, with no archive text and no archive license. Bundle B's guide, pack and index text is not copied. The 264-row index is dropped.
- **Q3 (a)** A4 then A3. Done.
- **Q4 fold** there is no 14th `science` skill and no `skills/science/`. Method guidance goes into existing skills: `grill` reads it as a lower-priority reference after the repository's own conventions.
- **Q5 yes** a `single-cell-analysis` convention may ship beside the user's installed pack and the `sc-conventions` fixtures. It never replaces either; `grill` cites it as a plugin reference, not as an active `repo:` convention.

## M4: folded method guidance (B1, reshaped)

- **Scope**: 2 or 3 short method guides, written fresh, under `skills/grill/references/methods/`, and one line in `skills/grill/references/scientific-conventions.md` saying when to consult one. Each guide has an input contract, blocking conditions, an output contract and what a pass would not show. No registry, no `science/` tree, no apply script.
- **Out of scope**: the other 13 methods, any new command, any change to hooks, an installer for packs.
- **Acceptance**: a test that every guide has the three sections and no link to a missing file; `check_links.py` clean; `git diff main -- hooks opencode skills/science` empty; the existing `grill` reference tests pass.
- **Status**: blocked: which 2 or 3 methods (see the open question below).

## Open question

- **Q6**: which methods go first? Recommended: single-cell analysis (donor-level pseudobulk), longitudinal analysis, Bayesian modelling.

## Limits

- The bundles' file and function names were checked by reading `630fc30`. The plans' claims about tests (for example R1-01) are specs, not results.
- Passing tests show that a named failure is caught, not that a recipe suits a real study.
