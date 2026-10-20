# What Mycelium Extra is

Mycelium Extra is a plugin for Claude Code, Codex and OpenCode. It puts you in charge of three moments in an analysis: what is planned, what is allowed to run, and what the record shows afterwards.

## What you control here

- **Your typed word** approves a plan (`approve plan <hash>`), a freeze, or sending a review packet. The agent cannot type these for you.
- **Shown to you** are the plan, the approval card, any change to a script you approved, and the verify report.
- **To say no**, do not approve: a covered run is then denied. To turn the gate off, remove `.mycelium-extra/gate.json`.

## The five jobs

| Job | Tool | You get |
|---|---|---|
| Plan before anything runs | `grill` | A sourced, step-by-step plan. Every consequential choice says who made it: the repository, you, or a labelled default. |
| Allow runs | the approval gate (`init`, then `approve`) | Covered scripts and job launchers are denied until you approve a plan that names them. |
| Check afterwards | `verify` | What ran against the plan, what is a gap, and a `provenance/` record once you confirm. |
| Stay oriented | `focus`, `track-changes` | Which analysis this session works on, and what moved away from what you approved. |
| Keep continuity | `handoff`, `idea`, `harden` and others | A short file a fresh session can start from. |

Planning alone needs no setup. The gate adds execution checks and receipts. See [usage tiers](../usage.md) for the order to adopt them.

## How it relates to Mycelium

Mycelium manages project memory, conventions, review and reports. Mycelium Extra plans, gates and verifies runs, and never overrides Mycelium. It reads Mycelium's `.living/` records when they exist and works in an ordinary repository without them. See [with Mycelium or in a plain repo](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/guides/with-mycelium-or-plain-repo.md).

## What it is not

- Not a security boundary: an agent set on bypassing the gate through Bash can do so.
- Not a judgement of the science. A run that matches its plan can still be the wrong analysis.
- Not able to see code run through MCP notebook tools.

The full list is in [what this does not guarantee](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/concepts/not-guaranteed.md). The control model in plain words is [here](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/concepts/control-model.md).

## Next

[Your first plan in ten minutes](first-plan.md).
