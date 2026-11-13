# Invocation, splitting and routers

Adapted from Matt Pocock's writing-for-agents skill (MIT), SKILL-MECHANICS.

## Two choices

| | Model-invoked | User-invoked |
|---|---|---|
| Frontmatter | no `disable-model-invocation` | `disable-model-invocation: true` and Codex `allow_implicit_invocation: false` |
| Description | a pointer with the trigger branches, always loaded | one human line; triggers stripped |
| Cost | context every turn | your memory of the name |
| Reach | the agent, other skills and you | only you typing the name |

Pick model-invoked when the agent has to reach the skill itself, for example `grill` loads `plot-first`, or when another skill points at it. The audit prints the total description words of all model-invoked skills: that is the always-loaded cost to watch.

## Splitting

Split by sequence when later steps tempt the agent to rush the one in front of it. Hiding them works only across a real boundary, such as a handoff or a subagent. Sharpen the completion criterion first.

Split by invocation when a distinct trigger word you really type should fire a skill alone. The new description is a permanent cost, so the independent reach must be worth it.

Two user-invoked skills cannot invoke each other. Put shared reference in a plain file outside the skill system, and point to it from both. The `docs/` folder or a shared `references/` file fits.

## Routers

A router is one user-invoked skill that lists the others and when to use each. It hints; it cannot fire them. Add one when you can no longer recall the names. In this plugin `where` (state of one analysis) and `docs/skills.md` (the list) already work as routers; check them before you add another.
