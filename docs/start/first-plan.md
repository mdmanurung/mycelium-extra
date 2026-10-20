# Your first plan in ten minutes

You will plan, approve, run and verify one small analysis. Commands use Claude Code's `/mycelium-extra:` prefix; in Codex, use `$mycelium-extra:`. A complete real transcript is in [a worked example](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/example.md).

## What you control here

- **Your typed word:** `approve plan <hash>` (or bare `approve` when exactly one card is waiting). Nothing covered runs before you type it.
- **Shown to you:** the plan, then a card with the question, each choice and who made it, the checks, and what the plan lets run.
- **To say no:** don't approve, or ask `grill` to change the plan. To skip the gate entirely, don't run `init`.

## 1. Install

Follow [Installation](../installation.md) for your host, then restart it. Check that `/mycelium-extra:grill` is available.

## 2. Turn the gate on (once per repository)

```text
/mycelium-extra:init
```

`init` writes `.mycelium-extra/gate.json` and ignores `.mycelium-extra/` in `.gitignore`. By default it gates scripts under `analysis/**` and `nbs/**` and the commands `sbatch`, `snakemake` and `nextflow`, and an approval lasts 24 hours. It never changes a gate that is already on.

## 3. Grill

```text
/mycelium-extra:grill Test whether the day 28 minus day 0 change differs between the vaccine and placebo arms.
```

`grill` first asks for your question and the claim you hope to make, in your own words. It then reads the repository, asks only what you must decide (at most five questions), and ends with a brief and one status line: `Plan status: READY`, `READY_WITH_ASSUMPTIONS` or `DECISION_REQUIRED`. It runs nothing.

Read the plan table. Only its **Step** column grants a run, so check that it names every script.

## 4. Approve

The Stop hook shows the card. Check the science on it, then type:

```text
approve plan 84bb5fce
```

(`84bb5fce` is the hash from [the example](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/example.md); yours differs.) Type `card <hash> full` first to see every grant, file and check.

## 5. Run

Run the steps through your usual workflow. The gate denies a run the plan does not name, and says why. Each allowed run leaves a receipt in `.mycelium-extra/receipts.jsonl`.

## 6. Verify

```text
/mycelium-extra:verify 84bb5fce
```

Read the five summary rows first (`Ran as planned`, `Numbers match`, `Code checks`, `Not checked`, `Next`), then the status: `CONFORMS`, `CONFORMS_WITH_GAPS` or `DOES_NOT_CONFORM`. A gap is not a failure, and it never shows as a pass. Confirm if you want the check saved; it goes under `<analysis>/provenance/`.

## What this does not guarantee

`CONFORMS` means the record agrees with the plan. It does not mean the analysis is right. See [what this does not guarantee](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/concepts/not-guaranteed.md).

## Next

Guides by task: [plan](../guides/plan-an-analysis.md), [approve and run](../guides/approve-and-run.md), [verify](../guides/verify-and-provenance.md). Reference: [grill](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/grill.md), [init](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/init.md), [verify](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/verify.md).
