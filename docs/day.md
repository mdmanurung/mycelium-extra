# A day with Mycelium Extra

[Back to the usage tiers](usage.md)

This follows one researcher through one working day on a reportable analysis, in order, so you can see where Mycelium Extra speaks up and where it stays out of the way. The times are illustrative. The commands and messages are the ones the plugin has today (0.10.1); for the exact output of each step, see the [worked example](example.md).

The question for the day: *does the day 28 minus day 0 change in gene expression differ between vaccine and placebo?* The repository already has the gate turned on (`/mycelium-extra:init`, once). Examples use Claude Code's `/mycelium-extra:` prefix; Codex uses `$mycelium-extra:`, and OpenCode uses `/mycelium-extra:` too.

## 09:00 Pick up where you stopped

Yesterday ended with `handoff`, so the repository holds a short `HANDOFF.md`: the goal, the exact next action, decisions you locked in, and dead ends not to redo. Start a fresh session and paste the resume prompt `handoff` printed. Nothing needs re-explaining, and a plan that was still waiting for approval comes back word for word.

You do nothing else yet. The gate is quiet until something covered tries to run.

## 09:15 Ask for a plan

```text
/mycelium-extra:grill Test whether the day 28 minus day 0 change in gene expression differs between vaccine and placebo. Reference is placebo.
```

`grill` reads the repository's own records first (decisions, learnings, the data manifest, earlier analyses) and asks you only what the records cannot answer: which contrast direction, which samples to keep, which test. Everything it can source it fills in and cites. It writes nothing and runs nothing.

It ends with a brief: a table of steps, each with the choice made, where the choice came from, and how you will check it, followed by `Plan status: READY`. Where nothing could be sourced it uses a `default:` and says why, so you can overrule it.

If a second opinion is worth the cost today, `plan-review` sends the brief to independent reviewers. It asks first (you type `send packet <digest>`), because the packet leaves your machine. It never approves anything.

## 09:45 Read the card, then approve

When the reply ends with `Plan status: READY`, the gate shows a card: your question, the goal, each step with its choice and who decided it, what the plan lets run, which files are pinned, and what will be written. This is the one moment to check the *science*. The card shows what the gate allows; it does not judge the choices.

When it is right, type:

```text
approve
```

A bare `approve` works when the plan shown last is the only one waiting. With none, or several, waiting it approves nothing and lists the hashes, so you type `approve plan <hash>`. The approval lasts 24 hours by default and covers this session.

## 10:00 Code gets written and linted

The agent writes the three scripts. Each time it writes a script under a gated folder, the linter runs on it and any finding goes back to the agent, once per change. You see nothing unless a script still has open findings when the turn ends; then you get one line naming it.

The first run is the plan's step 1. It is allowed, because the plan names the script. A run of anything the plan does not name is denied with the reason, and the agent is told not to work around it.

## 11:30 Something breaks: debug without ceremony

Step 2 fails on a sample ID mismatch. Fixing a script that has already run would normally need the plan approved again, since approved scripts are pinned. For a debugging loop, grant exploration for this plan:

```text
allow explore 84bb5fce
```

Now the agent can fix and re-run code on the plan's own analysis paths as often as needed, with no new prompt each time. A run outside those paths is denied and left to you. Every explore run is logged and marked not reportable, so the debugging attempts can never be mistaken for the real run later. When you are done, `stop explore`.

## 13:00 Review, then freeze

The code works on a test run. Before the reportable run:

1. Ask for the principal methodological and code review (Mycelium's `review`, or your own in an ordinary repository) and run the checks you rely on. Fix what they find; every edit belongs before the freeze.
2. Ask `grill` for a run plan. It revises the same `PLAN.md`, lists the scripts, Snakefile and `run.sh` under `Inputs:`, and shows a dry run.
3. Read it and approve the new hash. The finished code is now pinned: if any listed file changes, the launch is blocked until the revised plan is approved.

This is the second of the two checkpoints (see [Two checkpoints](usage.md#two-checkpoints)). The gate checks the pins; it does not check that a review happened.

## 14:00 The real run

Run it your usual way, for example `sbatch run.sh` on the cluster. The gate checks the command against the approved plan before it starts, then records a receipt: what ran, from which commit, with which script fingerprints, and what the outputs were. An `sbatch` receipt records the submission; the job's outcome comes from `sacct` or the job logs, so `verify` reads those later.

## 16:00 Check what actually happened

```text
/mycelium-extra:verify <run plan hash>
```

`verify` compares the plan with the receipts, outputs, lint and any numbers you declared in a `<!-- claims -->` block, and says one of:

| Result | What you do |
|---|---|
| `CONFORMS` | The record agrees with the plan. Confirm saving it under `<analysis>/provenance/` and commit it with the analysis. |
| `CONFORMS_WITH_GAPS` | Read the gaps (a missing exit status, a linter that was not found). Close them or write them into the report. |
| `DOES_NOT_CONFORM` | Something blocking was found: a failed run, a changed pinned file, an open lint finding. Fix it, revise the plan, and repeat the affected steps. |

It checks the execution record, not the science and not the methods. It does not re-run anything.

## 16:45 Park the next idea, close the day

While reading the results you think of a better filter. Do not break the flow:

```text
/mycelium-extra:idea filter low-count genes before the paired test
```

One line goes into the todo registry and the work continues. At the end of the day:

```text
/mycelium-extra:handoff
```

Tomorrow's first session starts from the file it writes.

## When the gate says no

| You see | It means | You type |
|---|---|---|
| "blocked because no active approved plan covers this run" | The run is not in an approved plan, or the approval is older than 24 hours | Ask `grill` for a plan that names it, then `approve` |
| A pinned input or script changed | The file differs from what you approved | Approve the revised plan; the card shows what changed |
| An explore run was denied | It touches a path outside the plan | Approve a plan that names it, or `allow explore` for the session |
| `approve` approved nothing and listed hashes | Several plans, or an older one, are waiting | `approve plan <hash>` |

The gate is a record and a check on execution mistakes, not a security boundary and not a judgement of scientific validity. See the [approval gate reference](approval-gate.md) for settings and limits, and the [verification reference](verification.md) for what the report shows.
