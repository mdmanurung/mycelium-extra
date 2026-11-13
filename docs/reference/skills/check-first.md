# check-first

Writes the check that would catch a wrong result before the analysis code, one step at a time. It makes no run, grants nothing and writes no `.living/` file. Adapted from Matt Pocock's tdd skill (MIT).

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`). Run it as `/mycelium-extra:check-first` when a step will decide something.

The skill has no script. Its example runs on the standard library:

```bash
python3 skills/check-first/examples/paired_check.py wrong   # red, exit 1
python3 skills/check-first/examples/paired_check.py right   # green, exit 0
```

## The loop

1. Agree the seams with you: the files in `outputs/<stem>/` and the plan's Validation row. No check is written at a seam you have not agreed.
2. Pick the first slice: one step on a few whole units (donors, batches, plates with their rows and controls), never random rows.
3. Take the expected value from outside the code: a hand-computed literal on a toy table, a simulated dataset with known truth, a published value, or a negative control.
4. Run the check against a wrong or missing step. It must fail (red).
5. Write only enough step code to pass (green).
6. Widen to the full data, then write the next slice's check.

## What the checks are

With no clear metric, checks are invariants and sanity checks: metadata and matrix align by name, counts are conserved per donor, the contrast sign is right, the contrast is not nested in batch, a negative control stays null, and donors agree where the plan expects it. They are never a performance target. A passing check shows the step did what the plan says. It does not show the biology is right.

## Where checks go

A check is a plan row: the grill Validation column and, when frozen, a `validation-bindings` block ([Validation bindings](../../advanced.md#validation-bindings)). The recipes in [Validation recipes](../../validation-recipes.md) (R1 to R4; there is no paired-contrast recipe yet) are ready patterns. The check files live outside `analysis/**` and `nbs/**` and are pinned under `test_paths`. A tolerance or replicate count you did not approve is an impactful choice, so the skill stops and asks.

## When not to use it

- Exploratory looks at the data where nothing is decided yet. Use an exploratory run instead (`allow explore`, see [Commands](../../commands.md)).
- One-off figure polishing.
- Refactoring. It is not part of the loop.

## Reads and writes

Reads the plan, the validation docs and the step's outputs. Writes check files you agreed, outside the gated paths. Nothing is written to `.mycelium-extra/` or `.living/`.

## Default on or off

Off until you type it. No setting changes this.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| A frozen check and its expected values are pinned at approval | Enforced: `test_paths` are hashed into the approval |
| `verify` reads the check's result file and reports passed, failed or not run | Enforced: the report reads records, it runs nothing |
| Agreeing seams first, red before green, independent expected values | The agent's instruction |
| Check files stay outside `analysis/**` and `nbs/**` | The agent's instruction |

See [grill](grill.md) for the plan that holds the Validation rows, [verify](verify.md) for how a bound check is read, and [harden](harden.md) for turning a repeated lesson into a test.
