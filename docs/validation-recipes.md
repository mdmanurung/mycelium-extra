# Validation recipes

[Back to the advanced features](advanced.md)

Three small acceptance checks that catch a wrong analysis a plain run would not, and how to correct a wrong expectation afterwards. Each recipe is built from what the repository already has: a [validation binding](advanced.md#validation-bindings), the [data-contract checks](skills.md), and a development fixture that proves the check fails when it should. Nothing here adds a mandatory step; a plan without a `validation-bindings` block is approved and run as before.

A bound check is one claim, not a certificate. `verify` reads the check's result file and reports `passed`, `failed`, `not run`, `changed`, `unattributable` or `stale` (see [Validation in the report](advanced.md#validation-in-the-report)). It does not run the check and does not say the analysis is right.

**On this page:** [How a recipe is written](#how-a-recipe-is-written) · [1. Sample and key join](#1-sample-and-key-join) · [2. Contrast direction](#2-contrast-direction) · [3. Complete result table](#3-complete-result-table) · [Correcting a wrong expectation](#correcting-a-wrong-expectation) · [Limits](#limits)

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
| **Pass / fail / unavailable** | Pass: both result files say passed. Fail: an id is on one side only, or any log2 fold change moves. Not run: no matched run of the invocation under this approval. |
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
| **Pass / fail / unavailable** | Pass: signs are as stated. Fail: a sign is reversed. Not run: no matched run. An unavailable backend is not a pass; a check that cannot import the step reports `failed` or `not run`, never a silent skip. |
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
| **Pass / fail / unavailable** | Pass: the two gene sets are equal. Fail: genes are in one table and not the other; the result file names them. Not run: no matched run, or the result table did not exist when the check ran. |
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
