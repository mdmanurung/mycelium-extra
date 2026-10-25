# Longitudinal and repeated-measures analysis: planning guide

Read-only guidance for `grill`, after project evidence. It is a plugin reference, never a `repo:` convention and never a check that ran. A repository's own active convention outranks it.

## Input contract

- A participant ID that is the same string in every table, and the visit or time point of each row.
- The time origin and the actual sampling times, not only the planned schedule.
- When an intervention happened, and any censoring, dropout or missed-visit record.
- The outcome and where it was measured, with the batch or run it came from.

## Stop conditions

- No participant ID, or two IDs for one person that no crosswalk joins.
- The time origin is unclear and the answer depends on it.
- Visits of one participant would fall on both sides of a train/test split.
- Dropout depends on the outcome and the plan's claim needs complete follow-up, with no plan to look at it.
- A pseudotime or progression score is described as chronological time.

## Plan checks

Put each in the plan table as a future step with its own Validation cell.

1. State the estimand: change within a person, a difference in trajectories between groups, or prediction for a new person. The model follows from it.
2. Count participants per group and visits per participant, and list who is missing which visit, before choosing a model.
3. Name the participant as a random effect (and a slope only if the schedule supports one). Cells or visits are not independent replicates.
4. Name a simpler comparison the researcher would accept, such as a per-participant difference.
5. Add one discriminating check: shuffle visit labels within each participant and expect the effect to vanish; drop one participant at a time and expect the sign to hold.

## Output contract

The model formula, participants and visits per cell, the table of missing visits, how the validation split was made at participant level, and the uncertainty of each reported effect.

## What a pass would not show

That the effect is causal, that dropout was ignorable, or that the time axis means what the paper says it means. A passing check shows only the property it tested.
