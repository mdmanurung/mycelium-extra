---
name: idea-triage
disable-model-invocation: true
description: Rank the ideas parked in todo/ so the user can choose the next one.
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

Waiting for the user's pick is the agent's instruction, not a gate rule: nothing enforces it, unless `.mycelium-extra/gate.json` sets `confirm_writes` to true. Then, before writing a triage block or a status, run `sh <skill-dir>/../../hooks/py.sh <skill-dir>/../../hooks/confirm_write.py prepare --kind idea-triage --target todo/TODO_REGISTRY.md --target <each item file>`, show the user the `confirm write <id>` line, and write only after they type it: the gate denies the write before.

- `park all` changes nothing: stop without writing triage blocks or updating statuses.
- Write a `## Triage <date>` block (pitch, impact, risk, go/no-go test) into each scored item's file. Never delete or reorder items.
- Set the picked item's registry Status to `in-progress` and its file's Status to match. Use `upsert_table_row.py` as the `idea` skill does, keyed by the exact File cell with `--key-column 7`, without a plain-edit fallback. If the helper fails, retain the triage text, report the registry gap and retry the exact File-keyed update after fixing the helper. Duplicate titles identify different items.
- Offer `/mycelium-extra:grill <the pitch as a question>`. Do not start it unasked.
- Items not picked stay `open`. `discarded` needs the user's words: set `wont-do` and add the reason to the file.
