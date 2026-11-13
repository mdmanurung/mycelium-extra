---
name: ask-extra
disable-model-invocation: true
description: Ask which Mycelium Extra skill fits your situation. Names one to three skills to type and why; starts none of them.
---

# Mycelium Extra: Ask

Pick the skill for the situation, name it as the user types it, and stop. Adapted from Matt Pocock's ask-matt skill (MIT).

This skill only hints. User-invoked skills have no description, so nothing but the user can start them. Never run a skill from here and never say you did.

## 1. Get the situation

If the user already said what is going on, go to step 2. Otherwise ask one question and wait:

"Which fits best: lost track, starting something, exploring, something looks wrong, want to report, or want the structure cleaner?"

Done when you can name one row group in [references/router-table.md](references/router-table.md).

## 2. Name one to three skills

Read `references/router-table.md`, then the group that fits. For each pick, give the typed form from the table exactly, and one line on why it fits this user's situation, in their words. Order the picks by what to do first.

Done when every name you give appears in the table. If no row fits, say so in one line and name the closest group.

## 3. Check before you promise

Before you say what a skill does beyond the table line, read that skill's `SKILL.md`. The table line is for choosing, not for describing.

Done when no claim about a skill rests on the table line alone.

## Keep the table current

`references/router-table.md` is generated from each skill's own frontmatter. Do not edit it by hand. To rebuild it:

```bash
<skill-dir>/../../hooks/mxpy - --repo . < <skill-dir>/scripts/make_router_table.py > <skill-dir>/references/router-table.md
```

A new user-invoked skill needs a group in `GROUPS` in that script. Until then it lists under "Other" and `tests/test_ask_extra.py` warns.
