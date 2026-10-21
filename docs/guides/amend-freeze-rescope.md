# Amend, freeze, re-scope

An approval is a working scope: you and the agent may keep editing the scripts it lists. Three typed actions change what is approved: an amendment, a freeze, and a re-scope through `grill`.

![An additive plan revision may use an amendment card. A freeze pins reviewed scripts for reportable work. A changed question, choice, input or threshold calls for a revised plan and approval.](../figures/change-options.svg)

These actions change different things and are not interchangeable. The table below names the correct route, including a separate exploration option for debugging.

## What you control here

- **Your typed word:** `approve amendment <hash>`, `freeze <hash>` then `approve freeze <hash>`, and `approve plan <hash>` for a re-scoped plan. Each verb works only on its own kind of card.
- **Shown to you:** a change-only card for an amendment, the diff of every changed script for a freeze, and a notice each time the gate re-pins an edited script.
- **To say no:** do not approve. To stop re-pinning altogether set `"pin_scripts": false` in `gate.json`.

## Which one do I need?

| Situation | Do this |
|---|---|
| The plan only gains a script or a row | Ask `grill` to amend; approve the amendment card |
| A script you approved was edited, and the run will be reported | `freeze <hash>` |
| The question, a choice, an input or a threshold changes | Re-scope: `grill` writes a revised plan; approve its new hash |
| You only want to debug inside the plan | `allow explore <hash>` ([approve and run](approve-and-run.md)) |

## Steps

### Amend

Ask `grill` to add the new script or row and present the whole plan again. If every earlier row, the objective, the inputs and every existing script are unchanged, and the only new grants are scripts or files, the card shows only `Adds`, `Row`, `Reads`, `Writes`, `Grant` and `Unchanged`:

```text
approve amendment 1a2b3c4d
```

(`1a2b3c4d` is a placeholder; use the hash on your card.)

Anything else (a changed or removed row, a new input, a folder or command grant) gets the whole card, so the delta view never hides a change.

### Freeze

Review the code first (Mycelium's `review`, or your own), then type it yourself:

```text
freeze 84bb5fce
```

The card lists each changed script with its diff, the numbers that moved, the steps to rerun, and the outputs that may be stale. Then:

```text
approve freeze 84bb5fce
```

Run the plan's steps again and `verify`. The rerun belongs to the new approval instance. A freeze covers scripts only; a changed input or validation file means showing the plan again.

### Re-scope

Ask `grill` for the revised plan (it restates your question and asks only what is still open). Before you approve, compare it with the old one:

```text
/mycelium-extra:verify diff 84bb5fce <new-hash>
```

A changed objective or Choice cell is flagged as a possible scientific change; whether it is one is your call. To see how far the work has already moved, run [track-changes](stay-oriented.md); `grill` reads its brief when it revises a plan.

## Worked example

Real harness output, fixture project (synthetic names). After approval, step 1's script was edited and the plan run again. Then the user typed `freeze 84bb5fce`:

```text
mycelium-extra · freeze 84bb5fce · 1 script changed, 0 new since approval 10-19 19:59
  analysis/vaccine-response/scripts/01_select_samples.py +2 -0   (re-pinned 1x, last 10-19 19:59)
      @@ -30,0 +31,2 @@
      +
      +# an edit after approval
  Numbers: none changed.
  Other changed lines: 1
Rerun      steps 1, 2, 3 (step 1 names a changed script; later steps may read its outputs)
Stale      declared outputs may be out of date until the rerun: analysis/vaccine-response/outputs/samples_used.tsv, analysis/vaccine-response/outputs/de_results.tsv, analysis/vaccine-response/outputs/summary.tsv
Runs       4 under this approval so far
Gaps now   1 gap and 0 blocks besides unfrozen code (before any rerun; `verify report 84bb5fce` after the rerun shows them)
▶ approve freeze 84bb5fce   then: run the plan again, then verify
```

After `approve freeze 84bb5fce`:

```text
mycelium-extra: plan 84bb5fce frozen: the scripts as reviewed are pinned (analysis/vaccine-response/scripts/01_select_samples.py, analysis/vaccine-response/scripts/02_paired_test.py, analysis/vaccine-response/scripts/03_summary.R). Run the plan's steps again under this approval, then verify. Edits after this re-pin with a notice, as before.
```

## What this does not guarantee

A freeze pins the bytes you reviewed. It does not show the code is correct or that a review happened, and it follows only the script a command runs, not files it imports. A re-pin notice is a prompt to look, not a verdict. See [what this does not guarantee](../concepts/not-guaranteed.md).

## Reference

[gate](../reference/gate.md) · [verify](../reference/skills/verify.md) · [grill](../reference/skills/grill.md) · [control model](../concepts/control-model.md)
