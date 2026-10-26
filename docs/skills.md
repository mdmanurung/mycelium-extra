# Skill reference

New here? Start with [Usage tiers](usage.md) to choose a workflow. This page indexes the skills. Each one but `plot-first` (guidance only) has a reference page with its synopsis, subcommands, what it writes, its defaults and how to switch it off. You don't need to learn them all.

Commands use Claude Code syntax. In Codex, use `$mycelium-extra:` instead of `/mycelium-extra:`. OpenCode takes the same `/mycelium-extra:` commands. See [Host compatibility](installation.md#host-compatibility).

![Planning, execution, inspection, continuity and retained lessons are different tasks. The skill reference below gives their actual read/write behavior and prerequisites.](figures/task-skills.svg)

This is a task map, not a list of commands to execute in sequence. Read the skill entry for its prerequisites, confirmations and write behavior.

## Common prompts

| Need | Command |
|---|---|
| Make a plan | `/mycelium-extra:grill <your question>` |
| Enable execution checks | `/mycelium-extra:init` |
| Check a completed run | `/mycelium-extra:verify <hash>` |
| Create an analysis folder | `/mycelium-extra:new-analysis analysis/<name>: <question>` |
| List which conclusions in an analysis cite an inspected plot | `/mycelium-extra:plot-first <analysis folder>` |
| Resume in a fresh session | `/mycelium-extra:handoff` |
| Say which analysis this session works on | type `focus <folder>` |
| See what changed against the approved plan | `/mycelium-extra:track-changes` |
| Park a passing idea | `/mycelium-extra:idea <idea>` |
| Choose the next idea | `/mycelium-extra:idea-triage` |

To learn how the gate works, read [the approval gate](approval-gate.md) and the [verification reference](verification.md).

## grill

Turns your question into a sourced, numbered plan. It is read-only. For scientific work, after asking your question and retrieving project evidence, it discovers activated Mycelium convention packs and reads the relevant guides selectively. Marketplace presence alone does not activate a pack. Applicable rules, exceptions, sources and falsifiable checks enter the plan; they provide neither scientific proof nor execution approval, and the five-question cap remains unchanged. See [grill](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/grill.md).

## init

Turns on the approval gate for a repository. See [init](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/init.md).

## verify

Checks what ran against the approved plan and saves provenance once you confirm. See [verify](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/verify.md).

## new-analysis

Scaffolds a new analysis folder. With `--panels`, it adds a manuscript layer (a plot stub per panel, a figure map and a `manuscript-audit` contract), also to an existing folder without overwriting anything. See [new-analysis](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/new-analysis.md).

## plot-first

Makes saved plots the primary artifacts for interpreting analysis results. Each conclusion links an inspected figure and panel. An interpretive table needs a stated reason a plot is inadequate. `grill` loads this guidance for analysis plans; `new-analysis` carries it into the analysis doc and plan. Existing numeric provenance and workflow status tables stay in place. This is agent guidance, not a gate-enforced check. See the [skill instructions](https://github.com/mdmanurung/mycelium-extra/blob/main/skills/plot-first/SKILL.md).

## plan-review

Challenges a plan before you approve it. Nothing leaves the machine without your consent. See [plan-review](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/plan-review.md).

## decision-status

Finds which past Mycelium decision applies. See [decision-status](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/decision-status.md).

## data-contract-check

Compares a plan's assumptions with your sample tables or H5AD `obs`. See [data-contract-check](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/data-contract-check.md).

## manuscript-audit

Read-only audit of a manuscript repository's figure/table lineage, source data and reporting, with an optional small deterministic contract check: run ad hoc on stdin before approval, or as a project copy bound in a plan's `test_paths` so `verify` can attribute its result. See [manuscript-audit](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/manuscript-audit.md).

## focus

Say which analysis this session works on. See [focus](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/focus.md).

## track-changes

Shows what changed against the approved plan. It is read-only. See [track-changes](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/track-changes.md).

## handoff

Writes a short `HANDOFF.md` for a fresh session. See [handoff](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/handoff.md).

## idea

Parks a passing idea without a question. See [idea](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/idea.md).

## idea-triage

Ranks the open ideas so you can pick the next one. See [idea-triage](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/idea-triage.md).

## harden

Turns a learning's mitigation into a test. See [harden](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/harden.md).
