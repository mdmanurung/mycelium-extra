# Hypothesis catalogue

Prompts, not a checklist. Pick the ones the symptom makes plausible, write each as a prediction, and rank them. Each line gives a quick test.

## The result is wrong or surprising

- **Batch or donor confounding.** The effect lines up with batch, sequencing run or donor. Test: colour the figure by batch and by donor; refit with batch removed from the contrast.
- **Depth, ambient RNA or doublets.** The signal follows counts per cell or a marker in the wrong population. Test: plot the result against total counts and ambient markers; rerun on the cells that pass a stricter cut as a labelled probe.
- **Label or information leakage.** A feature was built from the outcome, or the same donor sits on both sides of a split. Test: permute labels across donors and see whether the result survives.
- **Position-based alignment.** Two vectors or tables were combined by order, and one was reordered. Test: join by name and compare with the positional result.
- **Many-to-many join.** Row count grew after a join. Test: count rows and unique keys before and after.
- **A label fell into "Other".** A recode missed a level. Test: tabulate the labels before and after the recode.
- **A mutated view or copy.** An object changed in place, or a subset assigned to a view. Test: compare the object before and after the suspect line; rerun with an explicit copy.
- **A muted warning.** A suppressed message hid a failed convergence or a dropped group. Test: rerun with warnings on.
- **A filter removed rows silently.** Test: count rows entering and leaving each filter, per donor.
- **A changed default after a package update.** Test: compare package versions in the saved session info with the current ones, and rerun with the old default set explicitly.
- **Reference or annotation drift.** A gene or cell-type reference changed version. Test: compare reference files' versions or hashes between runs.

## The result is unstable

- **Unseeded randomness.** Test: fix the seed, rerun 20 times, count how often the symptom shows. Check every stochastic step, including parallel workers.
- **Few donors.** Test: leave one donor out in turn and plot how the estimate moves.

## The pipeline fails or is slow

- **A stale step.** An earlier step is older than its script or input. Test: use the `where` card to see which steps are stale.
- **A step grew with the data.** Test: time the step on 2, 4 and 8 donors; the shape of the curve names the cost.
- **A resource limit.** Memory or walltime. Test: ask the scheduler for the job's peak memory and elapsed time (for example `sacct`), then rerun with a higher limit as a labelled probe. Do not diagnose from log text.

## Reminder

Changing a filter, threshold, covariate, model or seed to test a hypothesis is a probe. Keep it labelled and out of the analysis. Applying it is the user's decision.
