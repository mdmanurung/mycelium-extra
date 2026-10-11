---
name: idea-triage
description: Rank the ideas parked in `todo/` (from the `idea` skill or Mycelium's `todo-idea`) by impact, likelihood and risk, so the user can choose what to work on next. Scores each idea on two impact axes, counts the things that must go right, rates the riskiest assumption, checks whether existing findings already answer it, and names the cheapest go/no-go test for the top pick. Shows a ranked table with a "park all" option; the user chooses. Use when the user invokes mycelium-extra idea-triage, or asks to triage ideas, pick the next idea, choose what to work on next, or review the idea list. Based on Fischbach and Walsh (2024) problem selection. Not for planning a chosen idea (use grill) and not for capturing one (use idea).
---

# Mycelium Extra: Idea triage

Help the user choose; never choose for them. Triage reads and annotates `todo/` only. It runs no analysis and starts nothing until the user picks.

## 1. Collect

- Read `todo/TODO_REGISTRY.md`. Keep rows with Status `open` and Priority `idea`, or the rows the user names. No registry or no rows: say so in one line and stop.
- More than 8 rows: score the 8 oldest, and say how many were left out. Ask which others to include.
- Read each item's file. A missing file is a gap, not a skip.

## 2. Score each idea

Read [references/triage-rubric.md](references/triage-rubric.md) first. For each idea write, in this order, one line each:

1. **Pitch:** what, how, why it matters, biggest risk.
2. **Type and impact:** basic science, tool, or application, then the two axis ratings (low, medium, high). It needs medium-high on one axis; two low-to-medium ratings mean the idea needs rethinking.
3. **Likelihood:** the number of things that must all go right, the riskiest assumption rated 1 to 5, and months until a test can show it.
4. **Already answered?** Search `.living/findings/`, `analysis/**/*.md`, and `todo/` for the idea's key terms with `rg`. Name each hit, or write `no hits`. A finding that already answers it makes the idea a read, not a run.
5. **Red flags:** apply the rubric's list; write `none` when none apply.

Use only what the item file, the repository, and the user say. An unknown rating is `unknown`, never a guess; unknown on the riskiest assumption is itself a risk.

## 3. Show

Rank by likelihood and impact together, best first, at most 5 rows:

| # | Idea | Impact | Risk (1-5) | Months to test | Flags |
|---|------|--------|-----------|----------------|-------|

Then, for the top idea only: the **cheapest go/no-go test** (the specific question, the most direct crude test, the result that means go, and what to do on failure). Below the table always offer: `park all` (change nothing) and `reframe <#>` (rewrite one idea to lower its risk or raise its impact). Stop and wait for the user.

## 4. After the user picks

- Write a `## Triage <date>` block (pitch, impact, risk, go/no-go test) into each scored item's file. Never delete or reorder items.
- Set the picked item's registry Status to `in-progress` and its file's Status to match. Use `upsert_table_row.py` as the `idea` skill does, with the same plain-edit fallback.
- Offer `/mycelium-extra:grill <the pitch as a question>`. Do not start it unasked.
- Items not picked stay `open`. `discarded` needs the user's words: set `wont-do` and add the reason to the file.
