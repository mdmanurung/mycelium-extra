# 15 · Lucid-coder bundles: triage (2026-10-26)

Objective: pick what to build from six outside bundles dropped in `plans-lucidcoder/` (local, untracked). Each was checked against the [guiding principles](README.md#guiding-principles), roadmap files 00 to 14, `skills/` and `hooks/`.

- `docs/conventions_synthesis_2026-10-26/`: repo template, manuscript validator, style and plotting packs, scRNA rules.
- `docs/cc_learnings/` (symlink to the bmv CyTOF repo's `scratch/learnings`): conventions read from 17 public single-cell manuscript repos.
- `docs/mycelium_integrated_implementation_bundle/`: review of third-party lab repos and a `manuscript_audit.py` validator, landed in `0.18.0` as `manuscript-audit`.
- `docs/mycelium_reproducibility_{bundle,execution,review}_2026-10-26/`: a prototype checker, its execution run and the review of it.
- `lucid-coder/`: a v0.1 code-style and correction-learning plugin, superseded by its own docs.

Statuses: `todo`, `in progress`, `built`, `done`, `parked`, `dropped: <reason>`, `blocked: <question for the user>`.

## What the triage found

- About 100 proposals; 18 adds, merged into 11 items below. The rest are covered by existing items, owned by Mycelium, or style and scaffolding work that fails the plan/approve/check test.
- The evidence is mostly a static read of public repos, nine from one lab, with no figure reproduced. Only N1 and N2 rest on this repo's code or the user's own rules.
- Most failures in the reproducibility execution run are defects in the bundles' own prototype checker and installer. The checker shipped in `0.18.0` once its four open defects were fixed (MX01 to MX04, below). The installer does not ship: Mycelium's own installer installs the pack. `data-contract-check` already refuses an output that aliases an input and rejects unknown contract keys.
- `lucid-coder` gave one add (L6). Its fail-open hooks contradict "a gap is never clean".

## Shipped in 0.18.0

| ID | Item | Where | Status |
|---|---|---|---|
| S1 | `manuscript-audit` skill and stdlib validator, read by `verify` as `contract_result.v1` | `skills/manuscript-audit/` | done |
| S2 | Validator repairs: result file inside the project; counts are plain digits; no key or cell values in messages; unknown keys and non-number tolerances are gaps; figures declare `outputs` (`[]` = source-only) | `manuscript_audit.py` | done |
| S3 | Optional `figure_map` coverage: one row per figure contract, files exist, no repeated ids | `manuscript_audit.py` | done |
| S4 | `manuscript-reproducibility` pack, installed by Mycelium's installer | `network/conventions/` | done |
| S5 | R4: the model-input table holds one row per donor per cell type × condition | `docs/validation-recipes.md` | done |
| S6 | `new-analysis` puts steps in `code/`, plan and tracker in `plans/`, adds `run.sbatch` | `skills/new-analysis/` | done |

The bundle's other checks (portability scan, render-from-source, independent recount, notebook hygiene, lockfile) are parked as [R3](00-parked.md#r3-reproducibility-review-follow-ups-2026-10-26).

## Do now

| ID | Item | Touches | Size | Status |
|---|---|---|---|---|
| N1 | Strict-input probe of `data_contract_check.py`, `method_fidelity.py` and `verify.py`: empty or string key lists, bool or `"inf"` thresholds, `5.0` as a count, nested wrong types. Fix what reproduces; `manuscript_audit.py` already passes these since S2. Two bugs confirmed: `max_at_most` accepts `NaN`/`Infinity` (type-only check at `data_contract_check.py:917`, and `values > NaN` is never true at `:682`); `max_at_most: 0` is never checked (`properties.get(name)` truthy test at `:684`) | the three scripts, their tests | S | todo |
| N2 | Existing-outputs probe in grill: an `Outputs:` path that exists, or a skip-if-exists guard, needs a new run dir or an explicit "overwrite" in the plan | `skills/grill/` | S | todo |
| N3 | Five rows in `llm-failure-modes.md`: formula text is not the model (print `model.matrix` columns and rank); no silent default in classification (`np.select(..., default='Pass')`); missing shown as zero in heatmaps; labels keyed to cluster numbers; seed inside parallel R workers (L'Ecuyer) | `skills/grill/references/llm-failure-modes.md` | S | todo |
| N4 | Recipe 7 extension: accounting identity `start = retained + removed`, `removed >= 0` | `docs/validation-recipes.md`, `tests/test_recipes.py` | S | todo |
| N5 | `unique_key` evidence shows counts and row numbers by default; key values opt-in, as S2 already does for `manuscript_audit.py`. Related to C3 | `data_contract_check.py` | S | todo |

## Later: ask for a real case first

None of these has a case in the user's repos yet. Grill asks for one real table or model before building.

| ID | Item | Touches | Size | Status |
|---|---|---|---|---|
| L1 | Fraction, count and total agree within a declared tolerance; category counts sum to the denominator when the plan says categories are exhaustive. Merges recipe 10, a `ratio_consistency` check kind and a between-group claim recipe | recipe script first, check kind only if the recipe proves too weak | M | todo |
| L2 | Recipe: hand-calculated aggregation oracle (unequal denominators, absent category as a zero row, repeated visit, blank key, sample with no retained cells) | `docs/validation-recipes.md`, fixtures | S-M | todo |
| L3 | Recipe: formula versus expanded design (`~ age + age^2` without `I()`, design rank, contrast columns sum to zero) | `docs/validation-recipes.md`, fixtures | M | todo |
| L4 | Plot-first and grill line: the analysis step exports the plot-source table, the figure script reads only that table; say whether the target is encoding or byte identity. The automated check is MX08 in R3 | `skills/plot-first/`, `skills/grill/` | S | todo |
| L5 | One output file per plan row; a figure file name carries its panel ID | `hooks/gate.py` | S-M | parked: needs a gate edit and a shown collision |
| L6 | Eval outcomes split into never fired, infra error and wrong answer; activation rate reported apart from success | C12 `tests/eval` scorer | S | parked: waits for C12 real runs |

L2 and L3 were both called "recipe 9" in their sources. Number them when they land; A1 in [14](14-newplans.md) owns recipes 4 to 8.

## Sources

Per-source tables with every park and drop reason were written to the session scratchpad, not the repo. The bundles stay in `plans-lucidcoder/`.
