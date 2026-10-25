# Bayesian modelling: planning guide

Read-only guidance for `grill`, after project evidence. It is a plugin reference, never a `repo:` convention and never a check that ran. A repository's own active convention outranks it.

## Input contract

- The outcome, its likelihood family and the reason for that family.
- Predictors and the grouping structure (participant, batch, study).
- The estimand, in the units the researcher reports.
- What the researcher knows about plausible effect sizes, written in those units.
- The sampler seed and the software versions.

## Stop conditions

- Priors were chosen or changed after looking at the posterior.
- Nothing in the plan simulates data from the priors before the model sees real data.
- A parameter is not identified by the design, and the plan has no response to it.
- A diagnostic the plan names (divergences, R-hat, effective sample size) is unresolved, and the plan treats longer chains as the fix.
- A credible interval is reported as if it carried a frequentist error guarantee.

## Plan checks

Put each in the plan table as a future step with its own Validation cell.

1. Write each prior in interpretable units and say where its scale comes from.
2. Simulate from the priors and look at whether the outcomes are possible. Do not call a prior uninformative because it is wide on a transformed scale.
3. Fit on simulated data with a known answer and check that the answer is recovered.
4. Check the sampler diagnostics the plan names, then posterior predictive fit.
5. Re-fit with one defensible alternative prior and report whether the conclusion moves.
6. For prediction, validate on held-out groups, not held-out rows.

## Output contract

The model code, the priors with their sources, the seed, the sampler diagnostics, the predictive checks, the sensitivity result and the uncertainty of each reported quantity.

## What a pass would not show

That the model is right for the science. A model can converge and still miss the process that made the data. A clean diagnostic shows the sampler did its job on this model.
