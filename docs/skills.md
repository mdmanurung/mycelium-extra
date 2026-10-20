# Skill reference

Start with [Usage tiers](usage.md) to choose a workflow. This page is an index: each skill has its own reference page with its synopsis, subcommands, what it writes, defaults and how to switch it off. You do not need to learn them all.

Commands use Claude Code syntax. In Codex, replace `/mycelium-extra:` with `$mycelium-extra:`. In OpenCode, use the same `/mycelium-extra:` commands (`@grill` also works). See [Host compatibility](installation.md#host-compatibility).

## Common prompts

| Need | Command |
|---|---|
| Make a plan | `/mycelium-extra:grill <your question>` |
| Enable execution checks | `/mycelium-extra:init` |
| Check a completed run | `/mycelium-extra:verify <hash>` |
| Create an analysis folder | `/mycelium-extra:new-analysis analysis/<name>: <question>` |
| Resume in a fresh session | `/mycelium-extra:handoff` |
| Say which analysis this session works on | type `focus <folder>` |
| See what changed against the approved plan | `/mycelium-extra:track-changes` |
| Park a passing idea | `/mycelium-extra:idea <idea>` |
| Choose the next idea | `/mycelium-extra:idea-triage` |

For the gate itself, see [the approval gate](approval-gate.md) and the [verification reference](verification.md).

## grill

Turn your question into a sourced, numbered plan; read-only. See [grill](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/grill.md).

## init

Turn on the approval gate for a repository. See [init](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/init.md).

## verify

Check what ran against the approved plan; save provenance after you confirm. See [verify](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/verify.md).

## new-analysis

Scaffold a new analysis folder. See [new-analysis](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/new-analysis.md).

## plan-review

Challenge a plan before approval, with consent before anything leaves the machine. See [plan-review](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/plan-review.md).

## decision-status

Resolve which past Mycelium decision applies. See [decision-status](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/decision-status.md).

## data-contract-check

Compare a plan's assumptions with sample tables or H5AD `obs`. See [data-contract-check](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/data-contract-check.md).

## focus

Say which analysis this session works on. See [focus](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/focus.md).

## track-changes

Show what changed against the approved plan; read-only. See [track-changes](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/track-changes.md).

## handoff

Write a short `HANDOFF.md` for a fresh session. See [handoff](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/handoff.md).

## idea

Park a passing idea without a question. See [idea](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/idea.md).

## idea-triage

Rank the open ideas so you can choose the next one. See [idea-triage](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/idea-triage.md).

## harden

Turn a learning's mitigation into a test. See [harden](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/harden.md).
