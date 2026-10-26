# 14 · New plans: unified roadmap (2026-10-24)

Objective: merge two outside plan bundles into one ordered build list that fits the guiding principles in the [roadmap README](README.md). Both bundles are local and gitignored (`plans/_DONE/newplans/`, archived 2026-10-26).

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
  - `REFERENCE_INDEX.csv` has 264 rows (206 `specialized-tool-reference`, 32 `preferred-biomni-domain-reference`, 26 `secondary-legacy`; 232 from `skills_deduplicated.zip`, 32 from `biomni-codex-skills.zip`). Each row is a third-party skill name, path and description, with no skill content. Most rows are outside this plugin's field: quantum computing, astronomy, CAD, manufacturing, market research, battery models, fluid dynamics. 36 descriptions are empty and 17 hold a YAML artifact (`>-` or `>`) instead of text. `pkpd-modeling` appears twice. The index is not worth shipping, which matches dropping it under Q2.
  - `registry.json` lists 16 methods and 13 packs, every `scientific_validation` is `pending`, and `references` says `count: 264, mode: index-only`.
- Both bundles append to `skills/grill/references/scientific-conventions.md`; they touch different files otherwise. Land B after A and rebase the one reference.
- Neither bundle needs `hooks/` except A3, which edits card rendering in `hooks/gate.py` only.

## Order

Order is by value, then risk. Each item is one feature in its own PR. Version bumps stay a separate commit and need the user's word.

| ID | Item | Touches | Risk | Status |
|---|---|---|---|---|
| A1 | Validation recipes 4 to 8 with runnable checks and synthetic fixtures | `docs/validation-recipes.md`, `tests/test_recipes.py`, `tests/fixtures/validation-recipes/` | low: docs and tests | done on main (`015b9b6`) |
| A2 | `data-contract-check --profile-only`: bounded, descriptive, small-cell suppressed | `data_contract_check.py`, its tests, `SKILL.md` | low to medium: new CLI mode, old mode must stay byte-equal | done on main (`015b9b6`) |
| A4 | Sharper `discriminating_check` wording; one lost-coverage item in `track-changes` | `plan-review` references, `track_changes.py`, tests | medium: read-only, but journal identities must stay stable | done on main (`e759059`) |
| A3 | Input/output overlap advisory on the full approval and freeze cards | `hooks/validation.py` or adjacent helper, `gate.py` card path, `test_gate.py` | highest: `gate.py`, needs `gate_diff` before and after | done on main (`8d83a27`, `79757ac`) |
| B1 | Folded method guidance for 2 or 3 methods (no new skill) | `skills/grill/references/` | low: docs and a static test | done on main (`acc21ef`) |

PR-D in bundle B (route one or two methods as their own skills) is `dropped`; see Closed below.

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
- The generated `docs/examples/*.html` reports were refreshed on 2026-10-25 with `tests/e2e/make_track_changes_example.py` and `tests/e2e/make_journal_example.py`. The portable journal demo keeps its existing independent synthetic history; the HTML pages come from fresh synthetic sessions. No real analysis was run.
- Evidence: 7 new tests, 48 track-changes tests in all, pass on 3.9, 3.12 and 3.14. With the new call disabled, 4 of the new tests fail and 1 errors.

## M3 build notes (A3)

- `gate.overlap_findings(root, text)` compares declared names after `repo_relative` (which resolves `..` and links) and reads no file. `procedure_card` shows the detail on the full card and one `Data writes` line on the compact card, only for HIGH or REVIEW. Nothing changed in `on_tool`, `on_post`, `on_prompt` or any decision.
- Completed 2026-10-25 (`79757ac`): freeze and amendment cards reuse the same declared-path overlap block. Existing non-overlap cards stay unchanged. Gate comparison: 173 of 173 identical before and after; candidate suite: 493 tests, 2 skipped.
- Evidence: 6 new tests; `GateTest` passes (151); with `overlap_findings` returning nothing, 5 of the 6 fail and the control test passes. `gate_diff.py` against HEAD: 173 of 173 identical. Against the pinned base with the reviewed oracle: 116 of 173 identical, 57 expected differences, exit 0. The oracle file is unchanged.

## Later milestones

- **M2, A4** (done, see above): `plan-review` wording only (no new field, no `disconfirming_test`). One attention item in `track-changes` for a removed or changed validation binding, a dropped output, or a removed row between two approved plans. It reuses `verify.plan_changes` and the strict binding reader. A missing baseline reads `not established`, never "no losses". Acceptance: bundle A ids C4-01 to C4-13.
- **M3, A3** (done, see above): literal declared overlap only, shown on the full card, never on `on_tool` or `on_post`. Run `gate_diff` before and after; show any decision that differs. Acceptance: bundle A ids I3-01 to I3-10.
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
- **Status**: longitudinal analysis and Bayesian modelling shipped on main (`acc21ef`). The requested single-cell pointer is now implemented in `skills/grill/references/methods/single-cell.md`, linked from section 6 of `scientific-conventions.md`. It defers to the existing activation rules and pack routing rather than copying method policy. `skills/grill/tests/test_method_guides.py` checks the guide contracts and inactive-pack boundary.

## Method choice

- **Q6**: longitudinal and Bayesian guides, plus the single-cell routing pointer requested by the 2026-10-25 completion task. The pointer adds no scientific policy or pack activation.

## Limits

- The bundles' file and function names were checked by reading `630fc30`. The plans' claims about tests (for example R1-01) are specs, not results.
- Passing tests show that a named failure is caught, not that a recipe suits a real study.

## Closed (2026-10-26)

Every bundle item is now built, dropped or declined, so the bundles are archived.

Built:

- Doc paragraphs the bundle asked for: the overlap note's limit in `docs/advanced.md`, and the difference between changed approved scope and an unapproved run in `docs/mycelium-integration.md` and the track-changes `references/schema.md`.
- Profile measurement (bundle doc 17, item 5), below.

Dropped, each with its reason:

- **PR-D**, one method per skill: Q4 folded method guidance into `grill`, and a skill per method would undo that. Revive only if live routing (F2 in the remaining-features plan) shows a method guide misroutes.
- **Bundle B PR-B and PR-C**, scientist review of the 16 guides and a host check of the overlay: the overlay was not adopted. The three B1 guides have no scientist review; that stays a stated limit of the guides.
- **The end-to-end scenario demo** (bundle docs 00 and 16): recipes 4 to 8 reuse its fixtures and test each failure family on its own.
- **The HTML check at 390px and 200% zoom, and the reviewer comprehension test** (doc 17, items 6 and 7): both need a person at a browser. They belong with the live validation packet if anyone asks for them.

### Profile measurement

`data-contract-check --profile-only --json` on synthetic TSV metadata (six columns, two `group_by` columns, two missingness columns), five runs each, Python 3.12.6 on `res-hpc-exe032`, 2026-10-26. Wall time and peak RSS from GNU `time`.

| Input | Rows read | Result | Median / max time | Peak RSS |
|---|---|---|---|---|
| Small, 8 KB | 200 of 200 | complete, exit 0 | 0.09 s / 0.11 s | 18 MB |
| Large, 29 MB, default budget | 250,000 of 1,000,000 | partial, exit 0 | 1.20 s / 1.23 s | 47 MB |
| Large, `max_rows_inspected: 1000000` | 1,000,000 | complete, exit 0 | 4.59 s / 4.80 s | 135 MB |
| Malformed, one invalid UTF-8 byte | none | unavailable, exit 3 | 0.09 s / 0.09 s | 18 MB |

An `.h5ad` is not profiled by design (unavailable, exit 3), so it has no row. Memory grows with the rows read, about 120 bytes per row, so the 5,000,000-row ceiling would need roughly 600 MB. The default budget of 250,000 rows stays under 50 MB and two seconds; keep it.
