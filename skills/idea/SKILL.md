---
name: idea
description: Park a passing idea in one line, with no questions, into Mycelium's todo/ registry. Use on "idea:", "park this", "note this for later"; never starts the idea (idea-triage chooses what to work on).
---

# Mycelium Extra: Idea

Capture the idea and go back to the task. Ask nothing. Use the user's words as written; do not improve, research, or plan the idea.

## 1. Capture

1. Title: the first 8 words of the idea. Description: the full text, verbatim.
2. Fixed fields: Priority `idea`, Status `open`, Category `idea`, Date today (`date +%F`), Author `git config user.name` (else `unknown`).
3. Notes: one line of context that costs no questions: branch (`git branch --show-current`), the analysis folder or file being worked on, and the active plan hash if a grill card is waiting.
4. Capture using [scripts/capture.py](scripts/capture.py). Find Mycelium's `skills/core/scripts/upsert_table_row.py` through the project's `.mycelium/plugin-root`, else `~/.claude/plugins/installed_plugins.json` (`mycelium@mycelium` `installPath`). Use the Python runtime required by the installed helper.
5. Save the user's exact text to a temporary input file. Run the capture helper from stdin: `sh <skill-dir>/../../hooks/py.sh - --plugin-root=<skill-dir>/../.. --root=<project> --helper=<upsert_table_row.py> --python=<Mycelium Python> --text-file=<input file> --context=<branch, current file/folder, pending plan hash> < <skill-dir>/scripts/capture.py` (`--plugin-root` is where it finds `hooks/stateio.py`). It creates the minimum Mycelium item format shown by the helper, reserves the slug exclusively, and serializes captures through the File-keyed registry update (`--key-column 7`). Identical titles retain separate files and rows. Table cells escape pipes/newlines; Description preserves the user's words.
6. If publication fails, report the saved idea and recovery record; do not plain-edit the registry or claim successful capture. After fixing the helper/runtime, use the same command with `--recover` instead of `--text-file`. Recovery is idempotent and preserves changed files for review. Never create another item to retry a pending capture.

## 2. Reply

One line, then continue the task you were doing:

`Parked: <title> → todo/<slug>.md`

Append ` (plan <hash> still waiting)` when a grill card shown in this conversation has not been approved. Approval needs only `approve plan <hash>`, so this reply does not cancel it.

## Limits

- Write only under `todo/`. No analysis code, no `.mycelium-extra/`, no `.living/`, no git commit.
- Do not start the idea, even when it looks quick. The user runs `idea-triage` to choose what to work on next.
- Several ideas in one message: one file and one row each, one reply line.
