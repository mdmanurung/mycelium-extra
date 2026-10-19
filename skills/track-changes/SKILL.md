---
name: track-changes
description: Show what changed in one analysis against its approved intent, read-only. Compares the original and current approved plans, the scripts against what each approval pinned, the runs the gate recorded, and, if a Claude Code transcript is available, direct edits made to other analyses while a focus was open. Prints a short card and writes a Markdown review brief and an offline HTML report under `.mycelium-extra/track-changes/`. Every item says what was observed, what is only potential, and what is unknown. Use when the user invokes mycelium-extra track-changes, asks what changed since the plan was approved, whether the work drifted from the focus, or wants a briefing before `freeze` or Mycelium's review. It approves, freezes, runs, and validates nothing. Not for planning (use grill), judging correctness (use Mycelium's review), or checking whether a run matches its plan (use verify).
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
- The plans' inputs, outputs and validation blocks are not compared here; `verify diff <old> <new>` does that.
- Field meanings and the axes: `references/schema.md`.
