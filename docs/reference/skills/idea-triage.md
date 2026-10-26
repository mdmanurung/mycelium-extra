# idea-triage

Ranks the ideas parked in `todo/` so you can choose what to work on next. It helps you choose; it never chooses for you. Guide: [Plan an analysis](../../guides/plan-an-analysis.md). Based on Fischbach and Walsh (2024), *Cell*, problem selection.

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`).

`/mycelium-extra:idea-triage` (Codex: `$mycelium-extra:idea-triage`). No script and no flags.

## What it does

1. **Collect.** Reads `todo/TODO_REGISTRY.md`; keeps rows with status `open` and priority `idea`, or rows you name. No registry or no rows: one line and stop. More than 8 rows: scores the 8 oldest, says how many were left out. A missing item file is a gap.
2. **Score** each idea, using `references/triage-rubric.md`: pitch; type and the two impact ratings; number of things that must go right, riskiest assumption (1 to 5) and months to test; whether `.living/findings/`, `analysis/**/*.md` or `todo/` already answer it; red flags. An unknown rating is `unknown`, never a guess.
3. **Show** a table of at most 5 rows (idea, impact, risk, months to test, flags), then for the top idea the cheapest go/no-go test. Below it, always: `park all` (change nothing) and `reframe <#>` (rewrite one idea to lower its risk or raise its impact). It then waits.
4. **After you pick**, writes a `## Triage <date>` block into each scored item's file, sets the picked item to `in-progress` (registry and file), and offers `/mycelium-extra:grill <the pitch as a question>` without starting it. Unpicked items stay `open`; `discarded` needs your words and sets `wont-do` with the reason.

## Reads and writes

Reads `todo/`, and searches `.living/findings/` and `analysis/**/*.md`. Writes only `todo/` item files and registry rows, only after you pick. `park all` writes nothing. The registry update uses Mycelium's `upsert_table_row.py` keyed by the File cell, with no plain-edit fallback; if the helper fails the triage text is kept and the registry gap is reported. It never deletes or reorders items and runs no analysis.

## Default on or off

On when invoked.

## Enforced versus the agent's instruction

Nothing is enforced. Waiting for your pick, writing nothing on `park all`, offering rather than starting `grill`, and setting `wont-do` only on your words are the agent's instructions. Check `todo/` afterwards.
