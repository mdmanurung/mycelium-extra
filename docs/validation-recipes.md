# Validation recipes

[Back to the advanced features](advanced.md)

Eight small acceptance checks that catch a wrong analysis a plain run would not, and how to correct a wrong expectation afterwards. Each recipe is built from what the repository already has: a [validation binding](advanced.md#validation-bindings), the [data-contract checks](skills.md), and a development fixture that proves the check fails when it should. Nothing here adds a mandatory step; a plan without a `validation-bindings` block is approved and run as before.

A bound check is one claim, not a certificate. `verify` reads the check's result file and reports `passed`, `failed`, `not run`, `changed`, `unsupported`, `unattributable` or `stale` (see [Validation in the report](advanced.md#validation-in-the-report)). It does not run the check and does not say the analysis is right.

**On this page:** [How a recipe is written](#how-a-recipe-is-written) · [How a result is read](#how-a-result-is-read) · [Contract kinds, and what they cannot show](#contract-kinds-and-what-they-cannot-show) · [Running a step that takes paths on the command line](#running-a-step-that-takes-paths-on-the-command-line) · [1. Sample and key join](#1-sample-and-key-join) · [2. Contrast direction](#2-contrast-direction) · [3. Complete result table](#3-complete-result-table) · [4. Missing values and type conversion](#4-missing-values-and-type-conversion) · [5. Join cardinality and denominator](#5-join-cardinality-and-denominator) · [6. Identifier normalization](#6-identifier-normalization) · [7. Output invariants](#7-output-invariants) · [8. Negative controls](#8-negative-controls) · [Correcting a wrong expectation](#correcting-a-wrong-expectation) · [Limits](#limits)

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

## 4. Missing values and type conversion

| | |
|---|---|
| **Claim** | No value that was present before a conversion step is missing, non-finite or filled in afterwards, unless the plan says so. |
| **Inputs** | the table before the step, the table after it, the row key, the columns under review |
| **Expected answer** | Declared by the researcher: which columns are converted, and whether missing values may be filled (`--allow-fill`). The check never decides that missing means zero. |
| **Invocation** | `python3 recipe_checks.py --out RESULT missingness --before B --after A --key ID --columns af` |
| **Pass / fail / unavailable** | Pass: no new `NA`, `Inf`, `-Inf` or unparsable value, no unplanned fill, no key lost. Fail: any of those, with up to five keys. Unavailable: a missing file or column, or an unreadable table, gives `unsupported`. |
| **Deliberate failure** | `af_raw.tsv` holds `` `4.968e-6 ``; `as.numeric` turns it into `NA` (`af_bad.tsv`), a `-Inf` appears (`af_inf.tsv`), or the `NA` becomes `0` (`af_zero.tsv`). |
| **Benign control** | `af_good.tsv`: the tick is removed on purpose and a value that was `NA` stays `NA`. A group with more missing values is a description for [`--profile-only`](reference/skills/data-contract-check.md#profile-a-table-optional), not a failure here. |
| **Limit** | It compares two tables by key. It does not say the conversion rule was right, or that a value that stayed present is correct. |

## 5. Join cardinality and denominator

| | |
|---|---|
| **Claim** | A join has the cardinality the plan declared, and a count is taken over the units the question is about. |
| **Inputs** | the left and right tables and the key; for a denominator, the table of every unit the question covers and the table the analysis counts from |
| **Expected answer** | Declared: `many_to_one`, `one_to_one` or `one_to_many`, and the universe of units. A one-to-many join passes when the plan says so. |
| **Invocation** | `python3 recipe_checks.py --out RESULT join --left L --right R --key ID --relation many_to_one` and `... denominator --universe ALL --table T --key ID` |
| **Pass / fail / unavailable** | Pass: the right keys fit the relation (and, with `--require-all-left`, every left key matches); every unit of the universe is in the table. Fail: a repeated right key multiplies rows, or a universe unit is missing. Unavailable: as in recipe 4. |
| **Deliberate failure** | `annotations_duplicate.tsv` repeats `v1`, so a many-to-one join doubles that variant. `variants.tsv` has no row for `P003`, so a prevalence over `participants_all.tsv` drops one participant. |
| **Benign control** | `annotations_unique.tsv` fits `many_to_one`; the duplicate table fits a declared `one_to_many`. A variant-only denominator is right for a question about observed variants. |
| **Limit** | It reads the keys of the inputs, not the join the analysis ran. Pair it with recipe 1's shuffle check when the join itself is the claim. |

## 6. Identifier normalization

| | |
|---|---|
| **Claim** | Two raw keys merge into one normalized key only where the plan lists them as one entity. |
| **Inputs** | the table of raw key and normalized key per row; optionally a crosswalk of raw key and canonical key |
| **Expected answer** | The crosswalk comes from a source outside the analysis. The check never normalizes, and never decides that `chr1` and `1` are the same. |
| **Invocation** | `python3 recipe_checks.py --out RESULT collide --map M --raw raw_id --norm norm_id [--crosswalk X]` |
| **Pass / fail / unavailable** | Pass: no normalized key has several raw keys, or every such raw key is in the crosswalk with that canonical key. Fail: an unlisted merge. Unavailable: as in recipe 4. |
| **Deliberate failure** | `keys_collide.tsv`: `V1` and `v1` both become `v1`, with no crosswalk. |
| **Benign control** | The same map with `crosswalk.tsv`, which lists both spellings; and `keys_ok.tsv`, which has no merge. |
| **Limit** | It shows the merges match the list. It does not show the list is right or that unmerged keys are distinct entities. |

## 7. Output invariants

| | |
|---|---|
| **Claim** | A chosen output has no repeated observational unit, its keys equal the metadata keys, and named columns hold counts. |
| **Inputs** | the output table, its key, the columns that name a unit (for example participant and visit), optionally the metadata table and the count columns |
| **Expected answer** | Declared by the researcher. Row order is ignored, so a keyed table passes after a shuffle. Value ranges never reveal how a step normalized. |
| **Invocation** | `python3 recipe_checks.py --out RESULT invariants --table T --key sample_id --unit participant_id,visit --meta M --integer gene_a,gene_b` |
| **Pass / fail / unavailable** | Pass: every declared invariant holds. Fail: a repeated key or unit, a key on one side only, or a count column with a fraction or a negative value. Unavailable: as in recipe 4. |
| **Deliberate failure** | `units_duplicate.tsv` repeats participant `P1` at visit `0`; `counts_logged.tsv` holds log values where counts belong. |
| **Benign control** | `counts_ok.tsv` passes; a metadata table with the same keys in another order passes. |
| **Limit** | A log transform that happens to give integers passes. When the transform is the claim, use a known-answer test on a tiny input instead. |

## 8. Negative controls

| | |
|---|---|
| **Claim** | A check detects the defect it exists for. |
| **Inputs** | a copy of a small fixture with one change: a sample id broken, one visit removed, a comparison sign flipped |
| **Expected answer** | The mutated copy fails the named check and the original passes. Run it when you write the check, not at every analysis. |
| **Invocation** | the check from recipes 1, 2 or 7 (or the `pairing` data-contract check) on the mutated copy |
| **Pass / fail / unavailable** | Pass: the mutated copy fails and the original passes. A mutated copy that passes means the check is blind to that defect. |
| **Deliberate failure** | `sample_metadata.tsv` with one `sample_id` renamed fails recipe 7; `sample_metadata_dropout.tsv` fails a `pairing` contract; a flipped sign fails recipe 2. |
| **Benign control** | The unmutated fixture passes all three. |
| **Limit** | It tests the check, not the analysis. A check that catches every planted defect can still miss a real one you did not think of. |

```text
<!-- validation-bindings {"version": 1, "checks": [
  {"id": "no-new-missing", "plan_row": "4", "required": true, "defined_by": "researcher-approved",
   "test_paths": ["analysis/variants/checks/recipe_checks.py"],
   "invocation": ["python3", "analysis/variants/checks/recipe_checks.py", "--out", "analysis/variants/outputs/missingness.json",
                  "missingness", "--before", "analysis/variants/data/af_raw.tsv", "--after", "analysis/variants/outputs/af.tsv",
                  "--key", "variant_id", "--columns", "af"],
   "evidence_path": "analysis/variants/outputs/missingness.json"},
  {"id": "join-cardinality", "plan_row": "5", "required": true, "defined_by": "researcher-approved",
   "test_paths": ["analysis/variants/checks/recipe_checks.py"],
   "invocation": ["python3", "analysis/variants/checks/recipe_checks.py", "--out", "analysis/variants/outputs/join.json",
                  "join", "--left", "analysis/variants/data/variants.tsv", "--right", "analysis/variants/data/annotations.tsv",
                  "--key", "variant_id", "--relation", "many_to_one"],
   "evidence_path": "analysis/variants/outputs/join.json"}]} -->
```

`--out` goes before the subcommand. The script is the check, so list it in `test_paths` to pin it at approval; the expected answers are in the invocation, which is pinned too. Copy `tests/fixtures/validation-recipes/recipe_checks.py` into the project; it uses only the standard library. The fixtures in that folder are synthetic and show that the checks work, not that they suit your data. `tests/test_recipes.py` runs every red and green case.

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

## Single-cell R1–R4 bindings

R1, R2 and R4 compose the shipped `data-contract-check`; R3 adds recorded method fidelity. These are optional acceptance checks bound to approved intent, with no change to the gate or approval semantics. The runnable fixtures are in `tests/fixtures/sc-conventions/`. Run the commands below from the repository root; `/tmp` results demonstrate the check only. For a live approved project, copy the contracts into its checks directory, adapt input paths independently, and bind the actual checker and expectations before approval. The plan must use project-local evidence paths like the example below so existing run attribution can observe them.

| Check | Independently specified expectation | Negative fixture | Benign control | What it establishes |
|---|---|---|---|---|
| R1 design | Two independent donors; each donor observed at control and stimulated; each batch overlaps conditions | `r1_missing_pair.json`, `r1_aliased.json` | `r1_design.json`; retain donor and condition identities | Declared pairing, replication and batch overlap, not design-matrix rank, covariance choice or convergence |
| R2 input | Equal independent sample keys; declared count layer has nonnegative integer values | `r2_wrong_keys.json`; test-generated fractional/negative count layer | `r2_keys.json`, reordered metadata; test-generated integer count layer | Key agreement and declared sampled layer properties, not the analysis's join or normalization algorithm |
| R4 model-input unit | The table that feeds the model has one row per donor in each cell type × condition cell, and at least two donors per cell | `r4_cell_level.json` (cell-level table; cell IDs are unique) | `r4_unit.json` (pseudobulk table) | The model input is at the declared biological unit, independently of R1's sample table; not that the aggregation summed the right counts |
| R3 recorded method | Exact approved formula, contrast numerator/denominator/sign, random effects, covariates, assay and exclusions | `r3_wrong_sign.json`; tests mutate every field | `r3_observed.json`; JSON key order and ordering within declared lists may vary | Agreement of the recorded model fields with approved expectations; no extraction or authentication of the actual fit |

```bash
python3 skills/data-contract-check/scripts/data_contract_check.py --contract tests/fixtures/sc-conventions/r1_missing_pair.json --root . --result-json /tmp/sc-r1-red.json
# exit 2; missing donor pair blocks
python3 skills/data-contract-check/scripts/data_contract_check.py --contract tests/fixtures/sc-conventions/r1_design.json --root . --result-json /tmp/sc-r1-green.json
# exit 0; these declared design checks pass
python3 skills/data-contract-check/scripts/data_contract_check.py --contract tests/fixtures/sc-conventions/r2_wrong_keys.json --root . --result-json /tmp/sc-r2-red.json
# exit 2; independently listed sample keys differ
python3 skills/data-contract-check/scripts/data_contract_check.py --contract tests/fixtures/sc-conventions/r2_keys.json --root . --result-json /tmp/sc-r2-green.json
# exit 0; key sets agree
python3 skills/data-contract-check/scripts/data_contract_check.py --contract tests/fixtures/sc-conventions/r4_cell_level.json --root . --result-json /tmp/sc-r4-red.json
# exit 2; donors repeat within a cell type x condition cell
python3 skills/data-contract-check/scripts/data_contract_check.py --contract tests/fixtures/sc-conventions/r4_unit.json --root . --result-json /tmp/sc-r4-green.json
# exit 0; one row per donor per cell
python3 skills/verify/scripts/method_fidelity.py --expected tests/fixtures/sc-conventions/r3_expected.json --observed tests/fixtures/sc-conventions/r3_wrong_sign.json --result-json /tmp/sc-r3-red.json
# exit 2; recorded contrast sign differs
python3 skills/verify/scripts/method_fidelity.py --expected tests/fixtures/sc-conventions/r3_expected.json --observed tests/fixtures/sc-conventions/r3_observed.json --result-json /tmp/sc-r3-green.json
# exit 0; recorded fields agree
```

R2's separate `r2_layer.json` names `tests/fixtures/sc-conventions/counts.h5ad`, `layers/counts`, and the shipped checker's `integer_valued` and `non_negative` properties. It needs the existing optional `h5py` reader. `tests/test_recipes.py` creates a two-value HDF5 fixture when that reader is installed and checks both fractional/negative rejection and integer acceptance. Without it, the test verifies an explicit backend gap and skips the layer red/green qualification. No HDF5 pass is claimed from a missing backend. Run the same checker invocation with `--contract tests/fixtures/sc-conventions/r2_layer.json` against the actual counts file in a live project. Keep the existing shuffle-invariance and known-answer transformation checks for the stronger join and transformation claims.

The fixture plan below illustrates approval bindings for all three checks. It is an example to adapt and approve, not an approval event. Its checker and expected contract bytes are pinned; the observed model record is a runtime input rather than an expectation to freeze. Pin the actual execution/extractor code in the analysis plan as well, and use exact execution declarations when command identity matters.

```text
<!-- validation-bindings {"version": 1, "checks": [
  {"id": "sc-design", "plan_row": "4", "required": true, "defined_by": "researcher-approved",
   "test_paths": ["skills/data-contract-check/scripts/data_contract_check.py", "tests/fixtures/sc-conventions/r1_design.json"],
   "invocation": ["python3", "skills/data-contract-check/scripts/data_contract_check.py", "--contract", "tests/fixtures/sc-conventions/r1_design.json", "--root", ".", "--result-json", "analysis/sc/outputs/r1.json"],
   "evidence_path": "analysis/sc/outputs/r1.json"},
  {"id": "sc-inputs", "plan_row": "5", "required": true, "defined_by": "researcher-approved",
   "test_paths": ["skills/data-contract-check/scripts/data_contract_check.py", "tests/fixtures/sc-conventions/r2_keys.json"],
   "invocation": ["python3", "skills/data-contract-check/scripts/data_contract_check.py", "--contract", "tests/fixtures/sc-conventions/r2_keys.json", "--root", ".", "--result-json", "analysis/sc/outputs/r2.json"],
   "evidence_path": "analysis/sc/outputs/r2.json"},
  {"id": "sc-method", "plan_row": "6", "required": true, "defined_by": "researcher-approved",
   "test_paths": ["skills/verify/scripts/method_fidelity.py", "tests/fixtures/sc-conventions/r3_expected.json"],
   "invocation": ["python3", "skills/verify/scripts/method_fidelity.py", "--expected", "tests/fixtures/sc-conventions/r3_expected.json", "--observed", "analysis/sc/outputs/executed-model.json", "--result-json", "analysis/sc/outputs/r3.json"],
   "evidence_path": "analysis/sc/outputs/r3.json"}]} -->
```

R3 consumes `mycelium-extra.method_expectations.v1` and `mycelium-extra.executed_model.v1` JSON records; the two fixture files show their complete schemas. All six fields are mandatory. `contrast.sign` is the recorded coefficient multiplier (`1` or `-1`), not the estimated effect sign or a claim of statistical significance. Formula and assay strings compare exactly. Random effects, covariates and exclusions are explicit unique string lists compared without order; an explicit empty list means none, while an absent or null field is a gap. Unknown schemas, extra fields, malformed values, unreadable inputs and unavailable records also produce a gap, never a pass. This deliberately narrow checker does not parse formula equivalence or infer a method from prose.

R3 emits the existing `mycelium-extra.contract_result.v1` envelope: exit `0` / `pass` for recorded agreement, `2` / `block` for field drift, and `3` / `gap` for unusable evidence. Its `contract.sha256` identifies the expected bytes; `inputs` identifies both files by path, byte size and SHA-256. Existing `verify` consumes the result without a new interface. `tests/test_recipes.py` executes R1/R2 and uses the real `verify.judge_check` to show that changing even whitespace in a pinned contract reports `changed`; `tests/test_method_fidelity.py` exercises the same result consumer for R3. These tests use fixture receipts and do not establish a native-host attributed run. A live run still needs a matched invocation under the actual approved plan and attributable evidence. Missing approval, invocation, output or exit evidence retains the existing gap/unattributable outcomes.

```bash
python3.12 tests/test_recipes.py
python3.12 tests/test_method_fidelity.py
```

Both checker and tests use Python 3.6-compatible syntax and standard-library interfaces; optional HDF5 checks retain their existing reader requirement. A scientist must separately validate the fit extractor and establish that the runtime record actually came from the fitted model. Writing the approved settings back into a record can pass R3 without fitting anything; no generic JSON comparison can resolve that authenticity boundary.
