# Walkthrough: one analysis, start to finish

This page follows one analysis from question to checked result. The data are **simulated with known truth**, so you can see whether the plugin and the analysis got it right. The fixture is `tests/fixtures/mycelium-project/`: 12 donors, vaccine against placebo, day 0 and day 28, 60 genes. One donor also has a rerun library. Eight interferon (IFN) genes are set to rise 4-fold in the vaccine arm, and nothing else changes (`tests/e2e/expected/truth.json`).

Real tool output below comes from a replay of this session. Long output is trimmed with "…". New to the plugin? Start at [Start here](../index.md).

## The question

> Does the change in gene expression from day 0 to day 28 differ between the vaccine and placebo arms? Placebo is the reference.

## 1. Plan

You give the question to `grill`. It reads the repository, asks only what you must decide, and ends with a plan table. It runs nothing.

```text
/mycelium-extra:grill Test whether the day 28 minus day 0 change in gene expression differs between the vaccine and placebo arms of the vaccine cohort. Reference is placebo.
```

The plan table is what the gate reads. Only the **Step** column grants a run.

```markdown
| # | Step | Choice | Source | Validation |
|---|---|---|---|---|
| 1 | run `analysis/vaccine-response/scripts/01_select_samples.py` | keep preferred_acquisition == TRUE | repo: .living/decisions.md | 24 rows, 12 donors x 2 visits |
| 2 | run `analysis/vaccine-response/scripts/02_paired_test.py` | median-of-ratios; exact permutation; BH, α = 0.05 | repo: .living/decisions.md | sample IDs identical across tables |
| 3 | run `analysis/vaccine-response/scripts/03_summary.R` | hits at padj < 0.05 | default: matches step 2 | summary row count 1 |

Plan status: READY
```

Step 1 holds a repository decision: keep one library per donor and visit, the preferred one. That drops the rerun.

## 2. Approve

Before you approve, the agent tries to start step 1. The gate denies it, because no approved plan covers the run yet:

```text
$ python3 analysis/vaccine-response/scripts/01_select_samples.py

mycelium-extra gate: blocked because no active approved plan covers this run.
```

The agent cannot work around the block. Nothing runs until you decide.

The Stop hook shows a card. It lists the goal, each choice and who made it, the checks, and what the plan lets run. Check the science on it. Then type `approve`, which approves the card shown last.

```text
mycelium-extra · plan 84bb5fce · 3 steps · ready for approval
Goal      Test whether the day 28 minus day 0 change in gene expression differs
          between vaccine and placebo arms (reference: placebo; …
Choices   1 keep preferred_acquisition == TRUE  [repo: .living/decisions.md]
          …
▶ approve  (or approve plan 84bb5fce)
```

Approval pins the two input files and the three scripts by content hash. A changed input or script is caught later.

## 3. Run

The three approved steps run. Each run leaves a receipt in `.mycelium-extra/receipts.jsonl`. Step 1 reports what it removed. Each script writes its own folder, `outputs/<script stem>/`, with `figures/`, `source_data/` and `tables/` inside; a rerun overwrites it, and `logs/CHANGES.md` records what changed. The [analysis layout](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/concepts/analysis-layout.md) names every place.

```text
samples in: 25, out: 24 (dropped: D03_day28_rerun)
```

```{figure} figures/scenario/samples.svg
:alt: Grid of 12 donors by day 0 and day 28, coloured by arm. The rerun library D03_day28_rerun is drawn dashed and crossed out.

Sample selection: 24 of 25 libraries kept, the rerun library excluded. Keeping both would count donor D03 twice at day 28.
```

## 4. Result

Step 2 tests the paired day 28 minus day 0 change per gene, vaccine against placebo. Step 3 counts hits at padj < 0.05.

```{figure} figures/scenario/paired-change.svg
:alt: Per-donor change from day 0 to day 28 for the IFN genes. Vaccine donors rise, placebo donors stay flat.

Each point is one donor. IFN genes rise in the vaccine arm and stay flat in placebo.
```

```{figure} figures/scenario/volcano.svg
:alt: Volcano plot of the paired test. The eight known IFN genes are highlighted at the right edge.

The paired test. 8 of 60 genes pass padj < 0.05, and they are exactly the 8 true IFN genes. All 8 share p = 0.0022, the smallest value an exact 6-against-6 permutation test can give (1/462).
```

The truth file lets you check this: the hits should be the 8 IFN genes and nothing else, and they are. That is a test of the analysis. It is not something the plugin decides.

## 5. Check

`verify report` compares what ran with what you approved.

```text
# Verify plan 84bb5fce: CONFORMS

Ran as planned  3 of 3 steps ran, 3 run(s), all completed
Numbers match   8 of 8 claimed cells match
…
```

```{figure} figures/scenario/verify-outcome.svg
:alt: Verify status per plan check. Steps 1 to 3, unchanged inputs and claimed numbers pass; two gaps are marked.

Verify outcome per check. A gap is shown as a gap, never as a pass.
```

The two gaps:

```text
Validation cells: 3 are prose: nothing checks them
03_summary.R lint: not checked: Rscript not found
```

The record agrees with the plan, but two points rest on nothing checked. The Validation cells are sentences, not checks a tool can run. The R step was never linted, because this machine has no Rscript. A gap is not a failure. It tells you which claim rests on evidence nobody checked. Close it, or say in the write-up that the point was not checked. Confirm when you want the result saved under `provenance/`.

## What you just saw

- **Plan.** The question came first, and every choice named its source. The plan table was the whole grant.
- **Approve.** You read one card and typed one word. The run tried before that was denied.
- **Check.** `verify` compared the record with the plan and listed what it could not confirm. The known truth then showed the analysis found the 8 IFN genes.

`CONFORMS` means the record agrees with the plan. It does not mean the science is right. See [what this does not guarantee](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/concepts/not-guaranteed.md).

## Try it yourself

Redraw every figure and number on this site from the fixture. It needs only Python 3.9 or later:

```bash
python3 docs/scenario/make_figures.py
```

In this replay R is hidden, so step 3 copies the expected summary instead of running R. That is why its lint shows as a gap.

Regenerate the full real session on the fixture. It needs Python 3.9 or later, scilintr and Rscript (see the top of the file):

```bash
MX_E2E_SCILINTR=/path/to/scilintr MX_E2E_RSCRIPT=/path/to/Rscript \
  python3 tests/e2e/make_example.py /tmp/example.md
```

Or do it by hand in a copy of `tests/fixtures/mycelium-project/`, after you install the plugin and restart the host:

```text
/mycelium-extra:init
/mycelium-extra:grill Test whether the day 28 minus day 0 change in gene expression differs between the vaccine and placebo arms of the vaccine cohort. Reference is placebo.
approve
/mycelium-extra:verify
```

All commands and options are on the [commands page](commands.md). The saved session is in [a worked example](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/example.md).
