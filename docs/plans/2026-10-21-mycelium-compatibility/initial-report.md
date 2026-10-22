# Mycelium compatibility and single-cell simulations — 2026-10-21

**Result: no conflict observed in the tested file interfaces against current
Mycelium 0.9.2. Single-cell executable fixtures pass; live agent qualification
and scientific effectiveness remain unverified.**

## Versions and scope

- Extra source: `fc4efa3a2d594e4fcf1fc1b76be5026f471302a7`, version 0.15.0,
  plus the changes listed in the adjacent receipt.
- Upstream HEAD fetched from GitHub:
  [`2c9d7a461b75b93020c274bff2a508697dc05caa`](https://github.com/arjunrajlaboratory/mycelium/commit/2c9d7a461b75b93020c274bff2a508697dc05caa),
  version 0.9.2. Disposable checkout: `/tmp/mycelium-compat-20261021`.
- Seven relevant upstream files are byte-identical to the previously inspected
  0.9.1 checkout (`8f8b167`) and this machine's installed Codex cache
  (`0.9.2+codex.20261017115753`): contract checker, lineage writer, todo updater,
  installer, analysis template, analyze skill and folder-structure reference.
  Hashes: [interfaces.json](2026-10-21-mycelium-compatibility/interfaces.json).
- The Codex configuration currently disables `mycelium@mycelium` and enables
  `mycelium-extra@mycelium-extra`. Cache parity does not establish simultaneous
  hook dispatch. Configuration was inspected, not changed.

## Compatibility checks

`MYCELIUM_UPSTREAM` pointed at the fresh upstream checkout; no upstream half was
silently skipped in these checks.

| Interface | Observed result |
|---|---|
| Data-contract corpus | Three tests pass: table-reading/status agreement, local expectations, intentional schema/duplicate-header differences. This corpus does not establish statistical-check parity. |
| Real convention installer | Installs bioinformatics (6 files) and revised single-cell-analysis (28 files) into a disposable project, preserving every byte; registry and canonical guidance reference both packs. Development files are absent. |
| Real analysis template | Extra scaffolds an analysis using the template found through `.mycelium/plugin-root`. |
| Real todo updater | Two equal-title ideas retain separate files, verbatim bodies and exactly one registry link per file. |
| Real lineage writer | Extra's verify reader consumes the actual upstream-generated manifest, session, successful exit, static-detection flag and output hash. This does not upgrade static lineage into proof of production. |

The installer still replaces an existing pack directory on update; that is
documented upstream behavior, not exercised against a user's installation here.
No upstream files, hook registrations or project installations were changed.

## Single-cell work: implemented versus qualified

The prior R3 checker and M1/M3 tooling are already in current main (`d226cb0`,
`b1bad35`, followed by `8bbfc7c`), rather than only in the historical worktree.
The revised v0.4.0 pack remains local under ignored `plans/`; it is not distributed
by the plugin. Its 48-entry bundle manifest verifies without a mismatch.

One preparation defect was reproduced and fixed: M1 copied
`plans/sc-conventions/`, which still includes `ROADMAP.md` and two Python router
development files. It now copies the reviewed `plans/sc-conventions-revised/`
pack. Regression tests check development-file exclusion and revised policy fields
across all 32 workspaces. The original bundle is preserved; its manifest has one
pre-existing mismatch, `AGENT_PROMPT.md`.

| Scenario family | Executed simulation or check | Limit |
|---|---|---|
| Paired-donor expression | Prepared missing-visit probes block in the shipped pairing checker; complete-pair controls pass in both revision arms. R1 also checks independent replication. | Does not fit a donor-aware expression model. |
| Batch/condition aliasing | Prepared completely aliased probes block; overlapping-batch controls pass in both arms. | A passing cross-tab check alone does not prove every proposed design matrix is estimable. |
| Composition | Fixtures retain 20 T cells / 100 retained cells; planted project text proposes 20/80. Fixture tests verify the discrepancy is present only in the probe. | No observed agent detection or fitted compositional model; denominator reconciliation remains a live task. |
| Active/inactive packs and local overrides | Registry activation and project-local override files verified in paired workspaces. | No observed agent compliance with activation or precedence. |
| Non-single-cell task, missing guide, hostile guide | All cases prepared with isolated agent inputs and separate reviewer material; absent and poisoned guides verified against benign controls. | No live claim that the agent avoids irrelevant routing, hallucination or instruction injection. |
| Input alignment and assay state (R2) | Executed key-alignment and actual HDF5 count-layer red/green fixtures; optional-reader rerun passes all 13 recipe tests without skips. | Synthetic count fixtures, not a production H5AD or full R/Python round trip. |
| Recorded method fidelity (R3) | Eight tests cover formula, contrast/sign, random effects, covariates, assay, exclusions, invalid records, input preservation and verify ingestion. | Compares records; does not extract or authenticate a fitted model. |
| Candidate router | All ten policy rules exercise unknown/false/true disqualifiers; ties require a decision. | Demonstration prototype, not an automatic scientific selector. |

The preparation tests are not 32 successful agent runs. A fresh schedule was also
prepared against **current main**, using baseline `fd714898` and integrated
`fc4efa3`, at `/tmp/mycelium-sc-qualification-20261021/current-main-scenarios/`.
All 32 schedule entries remain `NOT_RUN`; both arms share identical project/pack
inputs for each scenario. Reviewer material must remain inaccessible to evaluated
sessions.

## Reproduce and continue

Final local validation: 111 focused unittest cases (two skips: the optional HDF5
reader and an Rscript-dependent scaffold check), plus all-ten-rule router checks. Repeating recipes
with the existing h5py-enabled Scanpy interpreter passes 13/13 without skips,
closing the reader gap. The broader end-to-end suite passes 111 cases with two
optional real-R-linter skips. No dependencies were installed.

```bash
MYCELIUM_UPSTREAM=/path/to/mycelium python3.12 tests/test_contract_compatibility.py
MYCELIUM_UPSTREAM=/path/to/mycelium python3.12 tests/test_mycelium_integration.py
python3.12 tests/test_sc_conventions_eval.py
python3.12 tests/test_method_fidelity.py
python3.12 tests/test_recipes.py
python3.12 tests/eval/sc_conventions.py prepare --integrated HEAD --out /tmp/sc-current-main-review
```

Supply the reviewed pack at the documented local path before preparation. Use an
existing interpreter with h5py for the optional HDF5 recipe test. Raw test logs and
source hashes are adjacent to this report.

**Remaining qualification:** choose the first live host, run the paired scenarios
with frozen host/model/settings, and obtain independent human adjudication with
transcript evidence. M3 still needs independent roles, held-out workspaces, key
custody and explicit model/spend authorization. No model calls, sealed-key access,
SLURM jobs, real-project installation, commit or push were performed here.
