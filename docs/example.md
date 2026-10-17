# A worked example

[Back to the usage tiers](usage.md)

One session on the fixture project (`tests/fixtures/mycelium-project`): plan, approve, run, verify. Every output block below is what the hooks and `verify` printed in a real run on 2026-10-17, at version 0.10.1. The two exceptions are the plan, which is written by hand because the model writes it in a real session (the file is `tests/e2e/plans/baseline_plan.md`), and Mycelium's lineage manifest, which the test harness writes where Mycelium's own hook would. Regenerate with Python 3.9 or later (for example `python3.12 tests/e2e/make_example.py`; see the top of that file for the tools it needs) when an output format changes.

## 1. Ask

You describe the question to grill. It searches the repository's records, asks what only you can decide, and ends with a brief.

```text
/mycelium-extra:grill Test whether the day 28 minus day 0 change in gene expression differs between the vaccine and placebo arms of the vaccine cohort. Reference is placebo.
```

## 2. The brief

The plan table is what the gate reads. Only the Step column grants a run; its paths and commands are the whole grant.

```markdown
**Objective.** Test whether the day 28 minus day 0 change in gene expression differs between vaccine and placebo arms (reference: placebo; positive log2FC means higher in vaccine).

Inputs: data/processed/vaccine-cohort/sample_metadata.tsv data/processed/vaccine-cohort/counts.tsv
Outputs: analysis/vaccine-response/outputs/samples_used.tsv analysis/vaccine-response/outputs/de_results.tsv analysis/vaccine-response/outputs/summary.tsv

| # | Step | Choice | Source | Validation |
|---|---|---|---|---|
| 1 | run `analysis/vaccine-response/scripts/01_select_samples.py` | keep preferred_acquisition == TRUE | repo: .living/decisions.md | 24 rows, 12 donors x 2 visits |
| 2 | run `analysis/vaccine-response/scripts/02_paired_test.py` | median-of-ratios; exact permutation; BH, α = 0.05 | repo: .living/decisions.md | sample IDs identical across tables |
| 3 | run `analysis/vaccine-response/scripts/03_summary.R` | hits at padj < 0.05 | default: matches step 2 | summary row count 1 |

Plan status: READY
```

## 3. Before approval, a run is denied

The agent tries step 1 straight away.

```text
$ python3 analysis/vaccine-response/scripts/01_select_samples.py

mycelium-extra gate: blocked because no active approved plan covers this run.
  - python3 analysis/vaccine-response/scripts/01_select_samples.py
Active approved plans (last 24 h): none.
Present a plan whose plan table names these paths (prose, Evidence, and Source citations do not count) and that ends with the grill status line; the user approves it by typing `approve plan <hash>`. Do not work around this block; if the user wants an exploratory run instead, they will say so.
```

## 4. The approval card

When the reply ends with `Plan status: READY`, the Stop hook shows this card. You check the science on it, then type the last line.

```text
mycelium-extra · plan 84bb5fce ready for approval
Since earlier plans: no baseline (no earlier approval names these paths)
Question   none in the plan
Goal       Test whether the day 28 minus day 0 change in gene expression differs between vaccine and placebo arms (reference: placebo; positive log2FC means higher in vaccine).
Defaults to confirm: step 3

Sequence   (* = a default decided; confirm it)
    1 01_select_samples.py
        - choice: keep preferred_acquisition == TRUE  [repo: .living/decisions.md]
        - check: 24 rows, 12 donors x 2 visits
        - lint: clean
  ↓ 2 02_paired_test.py
        - choice: median-of-ratios; exact permutation; BH, α = 0.05  [repo: .living/decisions.md]
        - check: sample IDs identical across tables
        - lint: clean
  ↓ 3 03_summary.R*
        - choice: hits at padj < 0.05
        - assumed: matches step 2
        - check: summary row count 1
        - lint: 1 open (R002)

CAN RUN (in full) · broad grant: any arguments
  script   analysis/vaccine-response/scripts/01_select_samples.py  pinned
  script   analysis/vaccine-response/scripts/02_paired_test.py  pinned
  script   analysis/vaccine-response/scripts/03_summary.R  pinned
Reads 2 pinned under data/processed/vaccine-cohort/: counts.tsv, sample_metadata.tsv
Writes 3 under analysis/vaccine-response/outputs/: de_results.tsv, samples_used.tsv, summary.tsv
▶ approve plan 84bb5fce
```

Step 3's `lint` bullet shows one open scilintr finding. The card is for your eyes and never blocks; `verify` decides below, and here that threshold is an approved Choice.

## 5. Approval

```text
> approve plan 84bb5fce

mycelium-extra: plan 84bb5fce approved. Gated runs whose paths appear in that plan may run for 24 h. Pinned inputs: data/processed/vaccine-cohort/sample_metadata.tsv, data/processed/vaccine-cohort/counts.tsv. Pinned scripts: analysis/vaccine-response/scripts/01_select_samples.py, analysis/vaccine-response/scripts/02_paired_test.py, analysis/vaccine-response/scripts/03_summary.R.
```

## 6. The gated runs and their receipts

The three steps run with no hook speaking. Each leaves a receipt (here the first, trimmed to its main fields).

```text
command: "python3 analysis/vaccine-response/scripts/01_select_samples.py"
plans: ["84bb5fce"]
script: "analysis/vaccine-response/scripts/01_select_samples.py"
script sha256: "102be7022f98"
script git: "committed"
exit source: "event"
```

## 7. Verify

`verify report` checks what ran against the approved plan and prints the result.

```markdown
# Verify plan 84bb5fce

Approved 2026-10-17 16:58 - analysis folder `analysis/vaccine-response` - 3 run(s) under this plan - HEAD b19559e1de21 (clean)

## Scope

- Checked against approval instance f5d56f380a4d8adf: 3 run(s) under it - launch evidence 3 matched, 0 unmatched, 0 ambiguous, 0 legacy (launch link not recorded).
- Producers: 3 of 3 output(s) have a supported producer; 0 candidate, 0 unresolved (only a supported producer is named).
- Qualification: **qualified**; separate from the verify status below, and not a scientific judgement.

| Evidence | State | Basis |
|---|---|---|
| authorization | established | 3 of 3 run(s) are matched launches under approval instance f5d56f380a4d8adf |
| completion | established | all 3 planned step(s): the latest attempt of each completed |
| code and input identity | established | 5 script(s) and input(s) unchanged, compared by content hash |
| lineage | established | 3 of 3 declared output(s) have a supported producer (a matched attempt saw each change) |
| required validation | not applicable | the plan binds no check (its Validation cells are prose) |
| claim linkage | established | 8 claim cell(s) matched and their outputs have supported producers |
| no blocking finding | established | no finding blocks this plan |
| no open gap | established | no finding is an open gap |

- Limitation: qualification covers evidence linkage, not whether the analysis is scientifically right.

## Planned scripts

| Script | Status | Last run | Notes |
|---|---|---|---|
| `analysis/vaccine-response/scripts/01_select_samples.py` | ran (exit 0 from hook event) | 2026-10-17 16:58 |  |
| `analysis/vaccine-response/scripts/02_paired_test.py` | ran (exit 0 from hook event) | 2026-10-17 16:58 |  |
| `analysis/vaccine-response/scripts/03_summary.R` | ran (exit 0 from hook event) | 2026-10-17 16:58 |  |

## Pinned inputs

| Input | Pinned | Now |
|---|---|---|
| `data/processed/vaccine-cohort/counts.tsv` | sha256 914e90d45f3d | sha256 914e90d45f3d |
| `data/processed/vaccine-cohort/sample_metadata.tsv` | sha256 528eb39bc0b3 | sha256 528eb39bc0b3 |

## Outputs

| Output | Written | By | Evidence | Fingerprint |
|---|---|---|---|---|
| `analysis/vaccine-response/outputs/samples_used.tsv` | 2026-10-17 16:58 | `python3 analysis/vaccine-response/scripts/01_select_samples.py` at 2026-10-17 16:58 | attempt-observed, supported | sha256 b980761d554c |
| `analysis/vaccine-response/outputs/de_results.tsv` | 2026-10-17 16:58 | `python3 analysis/vaccine-response/scripts/02_paired_test.py` at 2026-10-17 16:58 | attempt-observed, supported | sha256 67c17edf1d9b |
| `analysis/vaccine-response/outputs/summary.tsv` | 2026-10-17 16:58 | `Rscript analysis/vaccine-response/scripts/03_summary.R` at 2026-10-17 16:58 | attempt-observed, supported | sha256 409ac0ca64d2 |

## Lint

- `analysis/vaccine-response/reports/report.Rmd:10` [R002] R002: magic numeric threshold in comparison -- extract to a named constant (e.g. FDR_THRESHOLD) or move to config.
- `analysis/vaccine-response/scripts/03_summary.R:8` [R002] R002: magic numeric threshold in comparison -- extract to a named constant (e.g. FDR_THRESHOLD) or move to config.
0 `ANALYSIS_OK` waiver(s).

## Claims

- `analysis/vaccine-response/VACCINE_RESPONSE.md`: 8 verified (0 via transform), 0 mismatch, 0 unverified, 0 explore-only; 8 other number(s) not claimed
  - Coverage: 1 block(s), 8 claim line(s); 8 cell(s) checked, 8 matched, 0 mismatched, 0 unverified; 8 prose number(s) listed, not checked.

## Findings

- **info**: 4 other script(s) in the analysis folder are not in the plan, and no run of them since the approval was recorded.
- **info**: Fact tags in `analysis/vaccine-response/VACCINE_RESPONSE.md` Key Findings: 5 agent-derived.
- **info**: scilintr: 3 Python file(s) clean.
- **info**: `analysis/vaccine-response/reports/report.Rmd:10` [R002]: its threshold is a Choice the plan approved, so it does not block.
- **info**: `analysis/vaccine-response/scripts/03_summary.R:8` [R002]: its threshold is a Choice the plan approved, so it does not block.
- **info**: 8 number(s) in `analysis/vaccine-response/VACCINE_RESPONSE.md` near its claims block are not claims, so not checked: L21 `0.05`, L21 `28`, L21 `0`, L24 `2`, L24 `924`, L25 `12`, L25 `6`, L25 `6`.
- **info**: 3 Validation cells are prose only; nothing checks them.

## Not visible to verify

- A receipt's time is when the gate's hook fired. A run Claude Code moved to the background writes its outputs after that, so such outputs show as not tied to a run.
- Mycelium's lineage covers finished Mycelium sessions only.
- Code run through MCP notebook tools (`nb_*_execute`) bypasses both the gate and the lineage.
- A run of a planned script proves it ran, not that it implements the plan's choices; that is what the review step checks.
- Claims are checked only where a document's `<!-- claims -->` block names the output cell; other numbers in the text are listed, not checked, and a verified claim matches its cell, not the truth.
- With `snakemake --use-conda`, rules run in their own envs under `.snakemake/conda/`; the conda env recorded is the one Snakemake ran in, not the rules' envs.
- Pip packages are read from the conda env's site-packages: one uninstalled after the run is not seen, and `pip install --user` packages under `~/.local` are not read.

Verify status: CONFORMS
```

`Verify status: CONFORMS`: every planned script ran under the approved plan, the inputs are unchanged, and the claimed numbers match their output cells. scilintr flagged `padj < 0.05` as a magic threshold, but that value is the Choice approved in step 3, so it is listed as info; a threshold the plan does not name would block. `verify write <hash>` then records the plan, receipts and report under `provenance/`.
