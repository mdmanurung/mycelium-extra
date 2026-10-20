# What Mycelium Extra is

Mycelium Extra is a plugin for Claude Code, Codex and OpenCode. It gives you control over three moments in an analysis: what is planned, what is allowed to run, and what the record shows afterwards.

You stay in charge. Only you can approve a plan, a freeze or a review packet, by typing the approval yourself. The agent cannot type it for you.

## What it does

| Job | Tool | What you get |
|---|---|---|
| Plan before anything runs | `grill` | A step-by-step plan where every consequential choice says who made it: the repository, you, or a labelled default. |
| Allow runs | the approval gate (`init`, then `approve`) | Covered scripts and job launchers are denied until you approve a plan that names them. |
| Check afterwards | `verify` | What ran against the plan, what is a gap, and a `provenance/` record once you confirm. |
| Stay oriented | `focus`, `track-changes` | Which analysis this session works on, and what moved away from what you approved. |
| Keep continuity | `handoff`, `idea`, `harden` and others | A short file a fresh session can start from. |

Planning alone needs no setup. The gate adds execution checks and receipts. See [usage tiers](../usage.md) for the order to adopt them.

## How it relates to Mycelium

Mycelium manages project memory, conventions, review and reports. Mycelium Extra plans, gates and verifies runs, and never overrides Mycelium. It reads Mycelium's `.living/` records when they exist and works in an ordinary repository without them. See [with Mycelium or in a plain repo](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/guides/with-mycelium-or-plain-repo.md).

## What it is not

- It is not a security boundary: an agent set on bypassing the gate through Bash can do so.
- It does not judge the science. A run that matches its plan can still be the wrong analysis.
- It cannot see code run through MCP notebook tools.

The full list is in [what this does not guarantee](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/concepts/not-guaranteed.md).

## Next

New here? Follow [your first plan](first-plan.md).
