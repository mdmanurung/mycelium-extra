# Validation recipes

[Back to the advanced features](advanced.md)

Three small acceptance checks that catch a wrong analysis a plain run would not, and how to correct a wrong expectation afterwards. Each recipe is built from what the repository already has: a [validation binding](advanced.md#validation-bindings), the [data-contract checks](skills.md), and a development fixture that proves the check fails when it should. Nothing here adds a mandatory step; a plan without a `validation-bindings` block is approved and run as before.

A bound check is one claim, not a certificate. `verify` reads the check's result file and reports `passed`, `failed`, `not run`, `changed`, `unsupported`, `unattributable` or `stale` (see [Validation in the report](advanced.md#validation-in-the-report)). It does not run the check and does not say the analysis is right.

**On this page:** [How a recipe is written](#how-a-recipe-is-written) · [How a result is read](#how-a-result-is-read) · [Contract kinds, and what they cannot show](#contract-kinds-and-what-they-cannot-show) · [Running a step that takes paths on the command line](#running-a-step-that-takes-paths-on-the-command-line) · [1. Sample and key join](#1-sample-and-key-join) · [2. Contrast direction](#2-contrast-direction) · [3. Complete result table](#3-complete-result-table) · [Correcting a wrong expectation](#correcting-a-wrong-expectation) · [Limits](#limits)

## How a result is read

Two things decide the outcome: the exit status the gate recorded for the check command, and the JSON the check wrote to its `evidence_path`. In this order:

1. **The exit status decides first.** A non-zero exit is `failed`. An exit status the gate did not record is `unsupported` — a gap, never a pass.
2. **An attributable result file can say more, in one direction only.** If the file says `not run` or `changed`, that overrides the exit status (a `data-contract-check` that exits 3 for an unreadable table is `not run`, not `failed`); if it says `failed`, the outcome stays `failed` and its reason is appended. A file can never turn a non-zero exit into a pass.
3. **At exit 0, the file decides.** A plain JSON object whose `status` is `passed` or `failed` gives that outcome, with its `message`. A file that is unreadable, is not an object, or has no `status` of `passed` or `failed`, is `unsupported`. A result file the matched attempt is recorded as having created but that is now missing, or one written by something other than that attempt, is `unattributable`.
4. **A data-contract result (`mycelium-extra.contract_result.v1`) is judged on its own terms:** it passes only when `exit_code` is 0, `status` is `pass` or `warn`, and no check blocks; `status: block` or `exit_code: 2` is `failed`; `exit_code` 1 or 3, or `status` `gap`/`error`, is `not run`, because nothing was judged; a malformed `checks`/`contract` is `unsupported`, and a contract whose `sha256` is not the pinned one is `changed`. Its `warn` lines are kept.

So a check that needs a backend it cannot get should write `{"status": "unsupported", "message": "scilintr not available"}`, exit `0`, and be reported as a gap with that reason. Raising an exception, or exiting non-zero, would report `failed` instead — a claim that the check ran and the analysis was wrong.

## Contract kinds, and what they cannot show

Recipes 1 and 3 use the `sample_alignment` kind. The kinds a plan's pairing and replication assumptions usually need are:

| The plan says | Contract `kind` | What passing shows |
|---|---|---|
| The ids of two tables agree | `sample_alignment` | The two key sets are equal (or agree on the declared columns). Order is not compared: a different row order is not a failure. |
| Every unit is observed at every listed level | `pairing` | The metadata holds every unit at every `within` level, so a paired or repeated-measures contrast is at least representable. |
| One row per unit per cell, with enough units | `unit_of_replication` | At most one row per unit in each `group` × `within` cell, and at least `min_units_per_group` distinct units per group. |
| The cohort levels and row counts the plan asserts | `cohort` | The declared `levels` are present, the row count is within `min_rows`/`rows`, and `no_missing` columns are complete. |
| Cases and controls are not fully nested in batch | `batch_confounding` | The contrast is not wholly nested in batch, and no level sits in a single batch with no overlap (a `max_share` share is reported as a warning). |

What these cannot show:

- **`sample_alignment` compares keys as sets.** A correct id set and a keyed join are different claims: a positional join between two tables with the same ids passes `sample_alignment` and fails the reordering check (recipe 1's `V-DC09`, which passes the alignment check and fails the shuffle check). Nothing here shows which row a value came from.
- **`pairing`, `unit_of_replication` and `cohort` read the declared structure, not the model.** A plan that says "random effect per donor" is checked for one row per donor per visit. No check here can see a mis-specified random-effects model, a wrong covariance structure, or a convergence problem; those are the analysis's own diagnostics, and the report does not judge them.
- **Only the files in `test_paths` are pinned at approval.** A checker reached by a bare command, or importing a system tool (a `scilintr` on `PATH`, a library in an `Rscript` environment, a package the host happens to have), is not byte-frozen by the plan: its version is part of what the run assumed, and the approval does not pin it. Pin the checker's own script under `test_paths` when it is the thing you are trusting.

## Running a step that takes paths on the command line

A check may import the analysis code, but a step written as a command line — a `.py` taking `argv`, an `.R` run through `Rscript`, a workflow rule — is better run as a subprocess. The check then exercises the entry point the plan names, at paths the check controls, and no import machinery is in the way.

```python
import subprocess
import sys

def run_step(samples, counts, out):
    """Run the analysis step the plan names, on paths this check controls."""
    try:
        proc = subprocess.run([sys.executable, "analysis/vaccine-response/scripts/02_de.py",
                               "--metadata", samples, "--counts", counts, "--out", out],
                              capture_output=True, text=True)
    except FileNotFoundError:            # no interpreter or step: a gap, not a failed analysis
        return {"status": "unsupported", "message": "the step or its interpreter is not available"}
    if proc.returncode != 0:             # a failed step is a failed check, with stderr as the reason
        return {"status": "failed", "message": proc.stderr.strip()[:200]}
    return judge(out)                    # judge the values the step wrote, never its log text
```

For an R step, use `["Rscript", "analysis/vaccine-response/scripts/02_de.R", ...]` and treat a missing `Rscript` (`FileNotFoundError`) as `unsupported` with exit `0`. Write the values the check compares into the result file: the report never reads a log to decide an outcome.

## How a recipe is written

Every recipe states the same nine things, so you can judge it before approving it:

- the **claim** it supports, and nothing more;
- the **inputs** it reads;
- the **expected answer** and where that answer comes from;
- the **invocation** the plan names;
- the **binding** that freezes the check and its expectation at approval;
- what **pass, fail and unavailable** each mean;
- a **deliberate failure**, with the development fixture that reproduces it;
- a **benign control** that must still pass;
- the **limit** of the claim.

The fixtures live in `tests/e2e/defects.py` and run on the fixture project (`tests/fixtures/mycelium-project`). Their ids (`V-DC08`, `V-DC09`, `V-DC12`) are in the table of each recipe. They are development tests: they show the check works on that project, not that it works on yours.

## 1. Sample and key join

| | |
|---|---|
| **Claim** | Sample ids match between the metadata and the counts, and the analysis gives the same answer when the metadata rows are reordered. |
| **Inputs** | `sample_metadata.tsv`, `counts.tsv` |
| **Expected answer** | Equal id sets on both sides (from the data-contract check); identical log2 fold changes after a row permutation (the answer is the analysis's own output, so the check compares the analysis with itself under a reordering, not with an outside truth). |
| **Invocation** | `python3 analysis/vaccine-response/checks/check_sample_alignment.py` and `python3 analysis/vaccine-response/checks/check_shuffle.py` |
| **Pass / fail / unavailable** | Pass: both result files say passed. Fail: an id is on one side only, or any log2 fold change moves. Not run: no matched run of the invocation under this approval, or a result file that says `not run`. Unsupported: a result file whose `status` is missing or unreadable, or an exit status the gate did not record. The ladder is in [How a result is read](#how-a-result-is-read). |
| **Deliberate failure** | `V-DC09`: step 02 pairs counts and metadata by position, not by sample id. The alignment check still passes, because equal id sets do not show a keyed join; only the shuffle check fails. |
| **Benign control** | The unmutated step 02: both checks pass. The shuffle itself is the control, since a correct keyed analysis ignores row order. |
| **Limit** | It shows that this code ignores metadata row order on the test data. It does not show that the pairing logic is right on real data. |

```text
<!-- validation-bindings {"version": 1, "checks": [
  {"id": "sample-alignment", "plan_row": "4", "required": true, "defined_by": "researcher-approved",
   "test_paths": ["analysis/vaccine-response/checks/check_sample_alignment.py",
                  "analysis/vaccine-response/checks/sample_alignment_contract.json"],
   "invocation": ["python3", "analysis/vaccine-response/checks/check_sample_alignment.py"],
   "evidence_path": "analysis/vaccine-response/outputs/sample_alignment_check.json"},
  {"id": "shuffle-invariance", "plan_row": "5", "required": true, "defined_by": "researcher-approved",
   "test_paths": ["analysis/vaccine-response/checks/check_shuffle.py"],
   "invocation": ["python3", "analysis/vaccine-response/checks/check_shuffle.py"],
   "evidence_path": "analysis/vaccine-response/outputs/shuffle_check.json"}]} -->
```

The contract file is a [data-contract](skills.md) JSON; its `sample_alignment` check names `key` and a `reference` (here the counts header). Keys are compared as sets, so a different order is not a failure for keyed data.

## 2. Contrast direction

| | |
|---|---|
| **Claim** | On a tiny dataset whose answer is known, the real analysis step reports a positive log2 fold change for a gene that is higher in the vaccine arm and a negative one for a gene that is lower. |
| **Inputs** | A small dataset built inside the check (donors, arms and counts written in the script) and the analysis step itself. |
| **Expected answer** | Sign of two genes, from the dataset's construction. It is independent of the analysis only as far as you wrote it independently: a check built from the same assumption as the code passes a wrong code. |
| **Invocation** | `python3 analysis/vaccine-response/checks/check_contrast_direction.py` |
| **Pass / fail / unavailable** | Pass: signs are as stated. Fail: a sign is reversed. Not run: no matched run. An unavailable backend is a gap, not a pass: write `{"status": "unsupported", "message": "..."}` and exit `0`, or import failure reports `failed` when the check raises. A check never skips silently. |
| **Deliberate failure** | `V-DC08`: step 02's contrast is reversed (control as numerator). The result file names both values. |
| **Benign control** | The unmutated step 02. |
| **Limit** | It tests the direction the check encodes, on one synthetic dataset. A reference level that differs on real data is not seen. |

```text
<!-- validation-bindings {"version": 1, "checks": [
  {"id": "contrast-direction", "plan_row": "4", "required": true, "defined_by": "researcher-approved",
   "test_paths": ["analysis/vaccine-response/checks/check_contrast_direction.py"],
   "invocation": ["python3", "analysis/vaccine-response/checks/check_contrast_direction.py"],
   "evidence_path": "analysis/vaccine-response/outputs/contrast_direction_check.json"}]} -->
```

## 3. Complete result table

| | |
|---|---|
| **Claim** | Every gene that was tested is a row of the result table, and no other gene is. |
| **Inputs** | `counts.tsv` (the tested universe) and `outputs/de_results.tsv` |
| **Expected answer** | The gene column of `counts.tsv`. |
| **Invocation** | `python3 analysis/vaccine-response/checks/check_complete_table.py`, a wrapper that runs the data-contract checker on a contract file |
| **Pass / fail / unavailable** | Pass: the two gene sets are equal. Fail: genes are in one table and not the other; the result file names them. Not run: no matched run, the result table did not exist when the check ran, or the contract result exits 3 for an unreadable table. Unsupported: the contract result is missing or malformed. The wrapper runs the checker with `--result-json`, which exits `2` on a block (recorded `failed`) and `3` on a gap (recorded `not run`). |
| **Deliberate failure** | `V-DC12`: step 02 drops low-count genes after testing and writes the rest to `de_results.tsv`. The other five declared checks pass, because their known-answer dataset has no low-count gene; only this one sees the missing genes. |
| **Benign control** | The unmutated step 02 writes all 60 genes and the check passes. |
| **Limit** | It compares the table with the declared universe. It does not say the universe was the right one, and a table filtered *before* testing is complete by this definition. |

```text
<!-- validation-bindings {"version": 1, "checks": [
  {"id": "complete-table", "plan_row": "9", "required": true, "defined_by": "researcher-approved",
   "test_paths": ["analysis/vaccine-response/checks/check_complete_table.py",
                  "analysis/vaccine-response/checks/complete_table_contract.json"],
   "invocation": ["python3", "analysis/vaccine-response/checks/check_complete_table.py"],
   "evidence_path": "analysis/vaccine-response/outputs/complete_table_check.json"}]} -->
```

The contract is the same `sample_alignment` kind used in recipe 1, pointed at the result table instead of the metadata:

```json
{"schema": "mycelium-extra.data_contract.v1", "table": "analysis/vaccine-response/outputs/de_results.tsv",
 "checks": [{"id": "complete-table", "kind": "sample_alignment", "key": "gene",
             "reference": {"path": "data/processed/vaccine-cohort/counts.tsv", "column": "gene"}}]}
```

Renamed columns need an explicit mapping in the check (for example comparing the `gene_symbol` column to the reference `gene` column). Meaning that no check compares, such as the unit of an effect size, stays your judgement.

## Correcting a wrong expectation

A check can be faithful to a wrong expected answer: the plan, the code and the expectation share one mistake, every check passes, and the result is still wrong. Approval froze the expectation, so it does not change by itself. When you find the mistake:

1. **Keep the original.** Leave the old expectation file and the saved provenance as they are. The run conformed to the plan it was approved under; that stays true.
2. **Record the correction.** Use Mycelium's usual decision log, and `decision-status` for a decision that is being superseded. Say which file was wrong and why.
3. **Find the affected analyses.** From the repository root, run `verify refs <old path> --sha <old sha256>` (see [Advanced features](advanced.md)). Each check that pinned the file is listed as *definite* (same path and same digest), *possible* (same path, different or unrecorded digest, or a bundle with no validation record) or has *no recorded reference*. *No recorded reference* is not proof the file was unused.
4. **Decide.** Rerun under a new approval, amend the finding, ask for review, or keep the result with a stated limitation. Nothing rewrites an old receipt or a finding for you.

An edit to a pinned expectation is a changed dependency, not automatically a confirmed correction: the gate denies runs that depend on it until you approve the plan again.

## Limits

- Hooks are not a security boundary, and a check the gate did not see run has no record; see [Validation bindings](advanced.md#validation-bindings) for what the card says about each check.
- A passing check is one observation. It is not scientific validation, and `defined_by` is a declaration, not authenticated authorship.
- A standalone preflight followed by a separately permitted command is not prevented by bindings. To make an analysis conditional on a preflight, put both in one entry point that runs the analysis only when the preflight succeeds.
- The fixture results show these checks work on the fixture project and the host and versions the tests ran on.
