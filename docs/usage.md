# Usage tiers

**Plan only? Start at Tier 1. Running code? Add Tier 2.** Each tier builds on the one before. They are workflow choices, not settings or pricing. Install the [plugin](installation.md) first. Commands use `/mycelium-extra:`; Codex uses `$mycelium-extra:`.

| Tier | Use it when | You add |
|---|---|---|
| 1. Plan | You want to clarify a question before writing or running code | `grill` |
| 2. Run with approval | You want execution checked against your plan | `init` once, then `approve` |
| 3. Verify reportable work | Outputs will go into a finding or report | `freeze`, `verify` |
| 4. Full project workflow | You need structure, review and continuity | `new-analysis`, `plan-review`, `handoff`, and more |

![Planning is the first tier. Add approval and receipts for execution, freeze and verification for reportable work, and project continuity tools when needed.](figures/usage-tiers.svg)

Each tier builds on the previous one. These are workflow choices, not settings, prices or measures of research quality.

## Tier 1: Plan

```text
/mycelium-extra:grill Plan a paired treatment-response analysis. Read the sample table and existing decisions first.
```

Answer the questions that affect the plan, then read its steps, assumptions and `Inputs:` line. Planning writes nothing and runs nothing, and needs no gate. `grill` calls `decision-status` and `data-contract-check` itself when needed.

## Tier 2: Run with approval

1. `/mycelium-extra:init`, once per repository. Check that it covers your analysis paths.
2. `/mycelium-extra:grill <your task>`. Read the plan and its `Inputs:` line.
3. Type `approve plan <hash>` in the same session. A bare `approve` works only when exactly one card is waiting.
4. Run the approved steps as you usually do. In a Mycelium project, use `/mycelium:analyze <name>`.

Covered commands are denied until approved, changed pinned inputs block, and each run leaves a receipt. Default gated paths are `analysis/**` and `nbs/**`; default gated commands are `sbatch`, `snakemake` and `nextflow`. Details: [Approval gate](approval-gate.md).

## Tier 3: Verify reportable work

1. Review the code **before** you freeze it (Mycelium's `review`, or your own), and run the checks you choose. Every code edit belongs before the freeze.
2. Type `freeze <hash>`. It shows each script's diff since approval, which steps to rerun and which numbers moved. `approve` it, then rerun the covered steps.
3. `/mycelium-extra:verify <hash>`. Read the failures and gaps, then confirm if you want the check saved under `<analysis>/provenance/`.

| Result | Meaning |
|---|---|
| `CONFORMS` | The checked record agrees with the approved plan |
| `CONFORMS_WITH_GAPS` | Some evidence or checks are missing |
| `DOES_NOT_CONFORM` | A blocking mismatch or failure was found |

Verification reads records; it never re-runs the analysis, and a match does not make the science valid. See [Verification](verification.md).

## Tier 4: Full project workflow

Add a tool when the project needs it. You do not need all thirteen skills.

| Need | Tool |
|---|---|
| A predictable analysis folder | `new-analysis` |
| An independent challenge before approval | `plan-review` |
| Continuity between sessions | `handoff` |
| Which analysis this session works on | `focus <folder>` |
| What changed against the approved plan | `track-changes` |
| Park an idea / choose the next one | `idea` / `idea-triage` |
| Stop a recurring mistake | `harden` |

`plan-review` sends a packet outside the machine only after you type `send packet <digest>`. Review never approves a run. The whole path, with a diagram and the two approval checkpoints, is in [the full workflow](guides/full-workflow.md).
