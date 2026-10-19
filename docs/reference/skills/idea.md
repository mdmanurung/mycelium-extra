# idea

Parks a passing idea in one line, with no questions, so the main work keeps its flow. Guide: [Stay oriented](../../guides/stay-oriented.md). Mycelium's own `todo-idea` mode asks up to six questions first; `idea` is the no-question path into the same registry.

## Synopsis

`/mycelium-extra:idea <idea>`, or say "idea:", "park this", "note this for later". The skill runs:

```bash
sh <skill-dir>/../../hooks/py.sh - --plugin-root=<plugin> --root=<project> --helper=<upsert_table_row.py> --python=<Mycelium Python> (--text-file=<file> | --recover) [--context=<text>] < <skill-dir>/scripts/capture.py
```

| Option | Meaning |
|---|---|
| `--plugin-root` | this plugin's folder (required; where it finds `hooks/stateio.py`) |
| `--root` | project root (default: current folder) |
| `--helper` | Mycelium's `skills/core/scripts/upsert_table_row.py` (required) |
| `--python` | the Python the helper needs (required) |
| `--text-file` | file holding your exact text |
| `--recover` | finish a pending capture after a failed publication; idempotent; replaces `--text-file` (the two are mutually exclusive) |
| `--context` | the one-line note: branch, current analysis folder, waiting plan hash |

## What it writes

`todo/<slug>.md` and one row in `todo/TODO_REGISTRY.md` with priority `idea`, status `open`, category `idea`, today's date and your git name. The title is the first 8 words; the description is your words verbatim. The registry update is serialized and keyed on the File cell, so identical titles keep separate files and rows. Several ideas in one message give one file and row each.

The reply is one line, `Parked: <title> → todo/<slug>.md`, with ` (plan <hash> still waiting)` when a grill card is unapproved. If publication fails, the idea and a recovery record are kept; fix the helper and rerun with `--recover`.

## Reads

The Mycelium helper (found through `.mycelium/plugin-root`, else `~/.claude/plugins/installed_plugins.json`), git branch and user name.

## Default on or off

On when invoked.

## Enforced versus the agent's instruction

The capture script enforces exclusive slug reservation and the serialized registry write. "Write only under `todo/`", no analysis code, no `.mycelium-extra/`, no `.living/`, no commit, and not starting the idea are the agent's instructions. The skill never changes a plan or the gate; approval still needs only `approve plan <hash>`.

Next: [idea-triage](idea-triage.md) ranks parked ideas.
