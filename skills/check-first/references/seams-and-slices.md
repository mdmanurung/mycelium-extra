# Seams and slices

## What a seam is for a script

A seam is a place where a step hands something on and you can look at it without reading the code. For a script that owns `outputs/<stem>/`, the seams are:

- the files it writes (a table, an `.rds`, an `.h5ad`), with their columns and row keys
- the numbers it prints to the log that the plan relies on
- the plan's Validation row for that step

Inside the script (a helper's local object) is not a seam. A check that reads it breaks when you rewrite the helper.

## Propose seams, then ask

Before any check is written, list the seams for the step and ask the user to agree them. One line each: what a check there would catch, and what it would miss.

| Seam | Catches | Misses |
|---|---|---|
| `outputs/02_de/de_table.tsv`, one row per gene per contrast | wrong sign, dropped genes, duplicated rows | a wrong model that still gives plausible numbers |
| `outputs/02_de/n_cells_per_donor.tsv` | cells lost in a filter | which cells were lost |

Write no check at a seam the user has not agreed. The agreed seams go into the plan's Validation column.

## Pick the first slice

The first slice is the smallest run that still has every property the step depends on.

1. Take the first step whose output the next step trusts without looking (the join of metadata to matrix, the contrast definition, the aggregation).
2. Choose whole units: two or three donors, or one batch with all its plates, each with all rows and its controls. Random rows break per-unit steps (reference offsets, per-donor fits, per-batch thresholds).
3. Include one unit that breaks the rule on purpose: a donor missing a condition, a duplicated id. The step must handle it in a way the plan states.
4. Write the check for this slice, see it fail, write the step, see it pass.
5. Widen: more donors, then the full data. Add the next step's check only after you have seen the output shape of this one.

## Why one slice at a time

Checks written before you have seen the real data shape test an imagined shape. They pass on the toy table and miss the column that is called something else, or the donor with two samples. Let each slice teach you what the next check must cover.

## Do not

- Refactor inside the loop. Fix and tidy after green, as a separate step.
- Check the model fit with a threshold you chose on the spot. A threshold is an impactful choice and needs an approved plan row.
