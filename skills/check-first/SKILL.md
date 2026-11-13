---
name: check-first
disable-model-invocation: true
description: "Write the check that would catch a wrong result before the analysis code, one step at a time. Use when a step will decide something; not for exploratory looks or figure polishing."
---

# Mycelium Extra: Check first

Write the check that would catch a wrong result, watch it fail, then write the step. One step at a time. Adapted from Matt Pocock's tdd skill (MIT).

A check here is an invariant or a known-answer test. It never scores the biology. A passing check says the step did what the plan says. It does not say the finding is true, and the report must not claim it.

## When not to use it

- Exploratory looks where nothing is decided yet: use an exploratory run (`allow explore`, see `docs/commands.md`).
- One-off figure polishing.
- Refactoring. It is not part of this loop.

## The loop

1. **Agree the seams.** A seam is what one step hands on: the files in `outputs/<stem>/` and the plan's Validation row. Propose each seam with one line on what a check there catches and what it misses. Write no check at a seam the user has not agreed. Detail: `references/seams-and-slices.md`.
2. **Pick the first slice.** One step, run on a few whole units (donors, batches, plates with all their rows and controls). Never random rows: per-unit steps need all of a unit's rows. Widen only after it passes.
3. **Get the expected value from outside the code.** A hand-computed literal on a toy table, a simulated dataset with known truth, a published value, or a negative control. Never recompute it with the step's own code path, and never copy it from the previous output. Detail: `references/independent-truth.md`.
4. **Red.** Run the check against a wrong or missing step. It must fail. If it passes, the check is blind: fix the check first.
5. **Green.** Write only enough step code to pass. Do not add features the check does not ask for.
6. **Widen.** Run the step on the full data. The check stays; add the next slice's check. Write one check per slice, after seeing the shape of the data it will meet, never all checks up front.

## Which checks fit when there is no metric

Use invariants and sanity checks, not performance targets:

- metadata and matrix align by name (identity, not order)
- counts are conserved per donor through each filter
- contrast sign: the group you call "treated" is the numerator
- no batch aliasing: the contrast is not nested in batch
- a negative control stays null (a permuted label gives no signal)
- replicate agreement: donors give the same direction where the plan expects it

## Where checks go

- A check is a plan row. Put it in the grill Validation column and, for a frozen check, in a `validation-bindings` block (`docs/advanced.md`, Validation bindings). Recipes R1 to R4 in `docs/validation-recipes.md` cover the common ones. A paired-contrast check has no recipe yet; use the toy-table pattern in `references/independent-truth.md`.
- A check file lives outside `analysis/**` and `nbs/**` (the gated paths), for example `checks/<stem>/`. Pin it under `test_paths` so approval freezes the expected values.
- A check that needs an expected value or tolerance the user did not approve is an impactful choice: stop and ask. A tolerance that decides pass or fail can change a conclusion.
- Write a check's result to a JSON file with `status` `passed` or `failed`. A check that cannot run writes `unsupported` and exits 0.

## Anti-patterns

- **Tautological:** the expected value comes from the same code path, or from last run's output. It passes by construction.
- **Method-coupled:** the check breaks when the method is swapped for an equivalent one (a different normalization that gives the same ranking). Check the property, not the intermediate object.
- **Horizontal slicing:** all checks written before any real data shape is seen. They test imagined data.

## Example

`examples/` holds a runnable known-answer check of a paired difference, with one wrong and one correct implementation. Run `python3 skills/check-first/examples/paired_check.py wrong` (exit 1) and `... right` (exit 0).
