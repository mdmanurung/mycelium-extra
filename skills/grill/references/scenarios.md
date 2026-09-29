# Behavior checks

Use these examples to check the skill's reasoning, not as boilerplate answers.

## Clear request

User: “Use the registered counts to reproduce the existing QC plot.”
Repo: manifest names the dataset; analysis doc and code specify the plot.
Expected: inspect the relevant files, ask no question, note any discrepancy between documented and actual code, return `READY` with a concrete next action.

## Consequential conflict

User: “Redo the monocyte pathway comparison across trials.”
Repo: an old decision uses baseline reference scaling, a newer script uses per-trial z scores, and current docs call that script provisional.
Expected: check the reason and outputs; avoid treating recency or implementation as automatic authority. If choice changes inference and intent is not inferable, ask one question with a recommendation.

## Challenge without a question

User: “Apply Harmony before testing protection.”
Repo: protection is partly confounded with trial and a within-trial analysis exists.
Expected: identify possible removal of biology or leakage; propose a within-trial primary analysis and integration as a sensitivity check if evidence supports it. Ask only if the scientific objective or accepted trade-off is genuinely user-owned and unresolved.

## Stop despite residual uncertainty

User: “Good enough; proceed with the figure.”
Repo: styling and a later validation cohort remain unspecified.
Expected: `READY_WITH_ASSUMPTIONS`, record style as reversible and cohort validation as parked with a return condition. No further interview.

## No Mycelium

User: “Grill my plan to split this package into modules.”
Repo: ordinary README and tests, no `.living/`.
Expected: inspect ordinary project evidence and challenge boundaries, compatibility, and validation; never claim Mycelium is required.
