---
name: track-changes
description: "Show, read-only, what changed in one analysis against its approved plan: plan, scripts, recorded runs, and off-focus edits. Use for \"what changed since approval\" or a briefing before freeze or review; it approves and runs nothing."
---

# Mycelium Extra: Track changes

A read-only account of how one analysis moved from what the researcher approved. It reuses the gate's and `verify`'s records; it does not grade them again. Silence is not assurance: what it could not observe is listed in every report.

## 1. Run it

```bash
sh <skill-dir>/../../hooks/py.sh - --plugin-root <skill-dir>/../.. [--analysis <folder>] [--original <hash>] [--current <hash>] [--transcript <file>] [--json] [--no-write] [--explain <item_id>] < <skill-dir>/scripts/track_changes.py
```

- The analysis is this session's open `focus` (the session comes from `$CLAUDE_CODE_SESSION_ID`, or `--session`). A focus left open by another session is never used. Codex and OpenCode do not set that variable: pass `--session` or `--analysis` there. With no focus for this session, pass `--analysis`. Never guess one.
- If several approved plans name paths inside the folder, it stops and lists them. Ask the user which plan states the original intent, then pass `--original`. Do not pick by date.
- The transcript is the one recorded when the focus started; `--transcript` names another. Without one, edits to other analyses are not observed, and the report says so.
- Pipe the script from stdin as shown. Running it by path opens Mycelium's post-action cycle.
- It writes only `.mycelium-extra/track-changes/<analysis>/` (`snapshot.json`, `brief.md`, `report.html`). Tell the user the report is local, holds code diffs, and that `.mycelium-extra/` should be git-ignored.

## 2. Show the card

Print the card as it comes: Baseline, Attention, Also, Unknown, then one `▶` line. Say which file is the brief and which is the HTML. Do not paraphrase an item into a verdict.

Wording to keep, because it is what the evidence supports: *Observed code change*, *Potential analytical implication*, *Execution evidence gap*, *Relationship to current focus not established*. Never say a change is "safe", "validated", "no impact", "in scope" or "out of scope". A number changing in code is an observed edit, not a changed conclusion. Another analysis's folder may be a supporting dependency.

### Explain one item

`--explain <item_id>` (a unique id prefix is enough; ids are in `snapshot.json` and `brief.md`) prints one bounded block with five headings: Observed, Potential, Unknown, Authorization, Evidence. It is read-only and writes no files. Relay it as printed and keep its wording: it says what was seen, what is only potential and what was not observed, never whether the change is safe, validated, or in scope.

For the plan itself, point the user to the **Plan** tab: the approved plan's steps in order, each with the read-only command it recorded and that command's output, as recorded. That page never runs one; `verify report` re-runs them and reports drift.

## 3. Offer next steps, as drafts

Each item lists what the user could do; none of it runs from here and none of it is an approval.

- Edited since approval: review the diff, then the user types `freeze <hash>`.
- A plan row changed: if it was not intended, `grill` revises the plan and the user approves the new hash.
- Failed or unmatched runs: `verify report <hash>` grades what they establish.
- Work in another analysis: the user may type `focus switch analysis/Y`, or note why it supports this one.

Offer the brief to Mycelium's review before a freeze: it is one file, `brief.md`, and nothing in it needs to be re-derived.

## What it is not

- Not an approval, a gate, or a check of scientific correctness.
- Not an attribution of who edited a file: only direct editor tool calls in a transcript are listed; shell-made edits and unmarked subagent work are not observed.
- Between two approved plans it shows one attention item when a required validation binding is gone or redefined, or a declared output is no longer named. It does not judge whether a replacement is equivalent, and it says nothing about a plan whose bindings it cannot read. Inputs and exact-execution blocks are not compared here; `verify diff <old> <new>` lists every difference.
- Field meanings and the axes: `references/schema.md`.

## Historical Analysis Journal (explicit)

Add `--journal` to collect historical records across sessions and open the offline
Journal at its overview. It does not execute verify, a scheduler or analysis code.
`--journal --json` prints the journal payload only, with all loaded events;
`--journal --no-write` creates no repository state. Normal reporting still writes
only the existing snapshot/brief/report paths.

When the user explicitly requests a durable observation, add
`--journal --save-checkpoint`. This is separate from ordinary display: never save
one automatically per invocation. It writes a validated compact checkpoint under
`<analysis>/journal/checkpoints/<digest>.json` and a short lock. Unchanged saves
reuse the first record. Never use `--no-write` or read-only `--explain` with saving.
Commit checkpoints for a fresh clone. They retain projections, not whole logs,
transcripts or diffs, and certify neither scientific validity nor complete history.

Repeat `--note notes/path.md#anchor` to attach researcher-owned references relative
to the repository root. Do not create or modify notes; their bytes and anchors are
references, never authorization. Changed/missing references remain explicit.

The overview defaults to the latest checkpoint baseline, else latest recorded
session, else available history. Use the period control for all history. Keep
conformity and qualification separate; show coverage even when no concern is
found. `Explore history` reveals searchable records, then `Evidence and provenance`
opens the selected source projection. No routine feed or raw dump starts open.
For exact identity/time/privacy contracts see `references/schema.md`.
