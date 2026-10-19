# track-changes

A read-only account of how one analysis moved from what you approved. It reuses the gate's and `verify`'s records and does not grade them again. Guides: [Stay oriented](../../guides/stay-oriented.md), [Amend, freeze, re-scope](../../guides/amend-freeze-rescope.md).

## Synopsis

```bash
sh <skill-dir>/../../hooks/py.sh - --plugin-root <skill-dir>/../.. [--repo DIR] [--analysis FOLDER] [--session ID] [--original HASH] [--current HASH] [--transcript FILE] [--json] [--no-write] [--explain ITEM_ID] < <skill-dir>/scripts/track_changes.py
```

Invoke with `/mycelium-extra:track-changes`. Run from stdin, never by path.

## Options

| Option | Meaning |
|---|---|
| `--plugin-root DIR` | This plugin's folder (required). |
| `--repo DIR` | Repository (default: current folder). |
| `--analysis FOLDER` | The analysis. Default: this session's open `focus`. A focus left open by another session is never used. With no focus, pass this; nothing is guessed. |
| `--session ID` | The session whose focus to use (default `$CLAUDE_CODE_SESSION_ID`). Codex and OpenCode do not set it: pass `--session` or `--analysis` there. |
| `--original HASH` | The approved plan that states the original intent. Required when several approved plans name paths in the folder; the script then stops and lists them. Never picked by date. |
| `--current HASH` | The plan to compare against. |
| `--transcript FILE` | A Claude Code transcript, to see direct edits to other analyses. Default: the one recorded when the focus started. Without one, those edits are not observed, and the report says so. |
| `--json` | Print the snapshot instead of the card. |
| `--no-write` | Print only; write no files. |
| `--explain ITEM_ID` | One bounded block for one item (a unique id prefix is enough) with five headings: Observed, Potential, Unknown, Authorization, Evidence. Read-only; writes no files. |

## What it compares

Original and current approved plans; scripts against what each approval pinned (with diffs); the runs the gate recorded; declared outputs older than the code; and, with a transcript, direct editor-tool edits to other analyses while a focus was open. The plans' inputs, outputs and validation blocks are not compared here; `verify diff <old> <new>` does that.

## Output

A short card (Baseline, Attention, Also, Unknown, then one `▶` line), a Markdown review brief and an offline HTML report. Every item separates what was observed, what is only potential and what is unknown. Wording is fixed: *Observed code change*, *Potential analytical implication*, *Execution evidence gap*, *Relationship to current focus not established*. It never says a change is safe, validated, no-impact, in scope or out of scope. Field meanings: `skills/track-changes/references/schema.md`.

## Writes

Only `.mycelium-extra/track-changes/<analysis>/`: `snapshot.json`, `brief.md`, `report.html` (not with `--no-write` or `--explain`). It refuses to write if that folder is a link or resolves outside the project. The report holds code diffs, so `.mycelium-extra/` should be git-ignored; the script warns when it is not. `grill` reads `brief.md` when a task revises an approved plan.

## Default on or off

On when invoked. `focus_notices` in [gate.json](../gate-json.md) (default `false`) is a separate turn-end line.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| Writes only its own folder; never approves, freezes, runs or pins | Enforced by the script |
| Typed `freeze <hash>`, `focus switch` and `approve` are the only ways to act on a finding | Enforced: the gate answers only your typed commands |
| Printing the card as it comes, keeping the fixed wording, offering next steps as drafts | The agent's instruction |

## Limits

Not an approval, a gate or a check of scientific correctness. It does not attribute who edited a file: only editor tool calls in a transcript are listed; shell-made edits and unmarked subagent work are not observed. Silence is not assurance; what it could not observe is listed in every report.
