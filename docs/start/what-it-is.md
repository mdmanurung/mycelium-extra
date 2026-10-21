# What Mycelium Extra is

**The intent.** An LLM agent can plan, write and run analysis code faster than you can read it. Mycelium Extra keeps the decisions with you and leaves a record you can check. It is a plugin for Claude Code, Codex and OpenCode, and the habits it teaches work with any tool: see [the method](method.md).

You stay in charge. Only you can approve a plan, a freeze or a review packet, by typing the approval yourself. The agent cannot type it for you.

![The researcher decides, the agent proposes and executes within approved work, and the saved records show what was observed and what could not be checked.](../figures/roles.svg)

These roles are complementary: records expose what was checked, while methods and interpretation still need your judgement.

## What it does

| Moment | Tool | What you get |
|---|---|---|
| **Before** | `grill` | A step-by-step plan where every consequential choice says who made it: the repository, you, or a labelled default. Nothing runs. |
| **During** | the approval gate (`init`, then `approve`) | Covered scripts and job launchers are denied until you approve a plan that names them. Each allowed run leaves a receipt. |
| **After** | `verify` | What ran against the plan, what is a gap, and a `provenance/` record once you confirm. |
| **Between sessions** | `focus`, `track-changes`, `handoff` and others | Which analysis a session works on, what moved away from what you approved, and a short file a fresh session can start from. |

Planning alone needs no setup. The gate adds execution checks and receipts. [Usage tiers](../usage.md) give the order to adopt them.

## Scope

Mycelium Extra is **for** a researcher who lets an agent help with analysis and wants to know afterwards what was decided, by whom, and whether the run matched.

It is **not**:

- a security boundary: an agent set on bypassing the gate through Bash can do so;
- a judge of the science: a run that matches its plan can still be the wrong analysis;
- able to see code run through MCP notebook tools.

The full list is in [what it does not guarantee](../concepts/not-guaranteed.md).

## How it relates to Mycelium

[Mycelium](https://github.com/arjunrajlaboratory/mycelium) manages project memory, conventions, review and reports. Mycelium Extra plans, gates and verifies runs, and never overrides Mycelium. It reads Mycelium's `.living/` records when they exist and works in an ordinary repository without them.

## Next

- Want the habits, not the commands? Read [the method](method.md).
- Ready to try it? [Install](../installation.md), then follow [your first plan](first-plan.md).
