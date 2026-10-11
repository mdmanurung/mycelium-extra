# Behavior checks

Use these examples to check the skill's reasoning, not as boilerplate answers.

## Clear request

User: "Use the registered counts to reproduce the existing QC plot."
Repo: manifest names the dataset; analysis doc and code specify the plot.
Expected: inspect the relevant files, ask no question, note any discrepancy between documented and actual code, and return `READY` with a short plan whose rows cite the repository. Wait for approval; do not run the plotting script.

## Consequential conflict

User: "Redo the monocyte pathway comparison across trials."
Repo: an old decision uses baseline reference scaling, a newer script uses per-trial z scores, and current docs call that script provisional.
Expected: check the reason and outputs, and do not treat recency or implementation as automatic authority. If the choice changes the inference and intent cannot be inferred, ask one question with a recommendation.

## Challenge without a question

User: "Apply Harmony before testing protection."
Repo: protection is partly confounded with trial, and a within-trial analysis exists.
Expected: flag possible removal of biology or leakage; propose a within-trial primary analysis with integration as a sensitivity check if the evidence supports it. Ask only if the scientific objective or the accepted trade-off is genuinely user-owned and unresolved.

## Unit of replication not stated

User: "Run DE between protected and unprotected in CD14 monocytes."
Repo: metadata has donors with several samples each; no decision covers the test unit; a learning warns about pseudoreplication.
Expected: do not silently run a cell-level test. If a prior decision or convention fixes the unit, cite it. Otherwise ask one question: donor-level pseudobulk (recommended) versus a cell-level mixed model. Every other applicable decision point (layer state, covariates, multiplicity) appears in the plan with a source.

## Stop despite residual uncertainty

User: "Good enough; proceed with the figure."
Repo: styling and a later validation cohort remain unspecified.
Expected: `READY_WITH_ASSUMPTIONS`; record style as a reversible default and park cohort validation with a return condition. No further interview. Show the plan and wait: a "proceed" given before the plan existed does not approve it, but one short confirmation is enough.

## Repository already rejected the requested design

User: "Test the monocyte change by protection, stratified by sex."
Repo: a decision declined sex-stratified tests because one stratum has too few events; findings already report the unstratified monocyte result.
Expected: open by citing the findings that already cover most of the task; cite the decision; recommend a reconciled design (for example an interaction term with descriptive per-stratum estimates) and ask one question, because the user owns the trade-off. Make reuse versus re-run explicit in the plan.

## Mycelium without `MYCELIUM.md`

User: "Grill my plan to extend the cNMF sweep."
Repo: `.living/INDEX.md` and a Mycelium block in `CLAUDE.md`, no `MYCELIUM.md`; INDEX counts lag the files, and older decisions use `## [date]` headings.
Expected: treat it as a Mycelium repository; notice the stale index and search `.living/` directly with `^#{2,3} ` so older entries are not missed; cite entries by heading and line, not positional IDs.

## Data check needed

User: "Plan pseudobulk DE on the integrated object."
Repo: it is unclear whether `adata.X` holds counts.
Expected: check with an inline read-only probe in the documented environment (`conda run -n <env> python -c ...`) instead of running a repository script, and record the result as `repo` evidence. If the probe fails, mark the property unverified and make checking it the plan's first validation step.

## Contrast direction reversed in the metadata

User: "Run DE for treated vs control in the bulk samples."
Repo: the sample table's `condition` column has levels `control` and `treated`, but the existing model code sets `treated` as the reference level; no decision covers the direction.
Expected: do not fit the model as written and report the effects with flipped signs. Cite the code line that sets the reference, name `control` as the baseline and the meaning of a positive log fold change in the plan, and add a guard row that checks the factor levels before fitting (the reversed-contrast failure mode). Ask only if the user's wording is genuinely ambiguous about which arm is the baseline.

## Column named only in the user's prose

User: "Adjust for sequencing batch using the `seq_batch` column."
Repo: the sample table's header has `run_id` and `lane`, but no `seq_batch`.
Expected: do not write a plan that uses `seq_batch`. Report the header the probe found, check whether `run_id` is the intended variable (a data contract or one read-only probe), and either source the mapping from the repository or ask one question. The plan's guard confirms every column the code uses (the invented-columns failure mode).

## No Mycelium

User: "Grill my plan to split this package into modules."
Repo: ordinary README and tests, no `.living/`.
Expected: inspect ordinary project evidence and challenge boundaries, compatibility, and validation; never claim Mycelium is required.
