---
name: where
disable-model-invocation: true
description: Show a short ADHD-format card for one analysis, with its aim, state, next action and approach.
---

# Mycelium Extra: Where

Answers "what is going on in this analysis?" from files, in a fixed shape: aim first, then where you are, then the next action. Nothing is written by a model and the analysis is not touched.

## What the user types

Send each as the whole prompt. The gate answers it before the agent sees it.

| Prompt | Card |
|---|---|
| `where` or `where am i` | Full card: aim, right now, do next (with a time estimate), approach checklist, later, watch out. |
| `where short` | The name, then five lines: aim, state, next, then, block. |
| `where all` | One line per analysis under a gated root, newest activity first. |

The analysis is the open `focus` folder, else the analysis folder of the current directory. The typed word needs the gate on; while the gate is off or paused by `/goal`, use `/mycelium-extra:where`.

## What you do

Run the same code from the slash command and paste its output unchanged. Add nothing.

```bash
sh <skill-dir>/../../hooks/py.sh - [short|all] < <skill-dir>/../../hooks/whereami.py
```

`--no-write` skips the save. Then give the user one thing to type next, taken from the card's DO NEXT.

## What it reads and writes

- Aim: `focus` objective or the analysis doc's `## Objective` or `## Purpose`; a scaffold placeholder counts as not written.
- Steps: numbered scripts in `code/` against `outputs/<stem>/`. `[x]` current, `[~]` stale (a script or an earlier step is newer), `[ ]` not run, `[!]` where the last run failed (the step with only a `logs/` folder), no mark when no Snakefile rule names the step. Order is the number order, so side-branch scripts such as `01b_` mark later steps stale. Older run-folder and flat layouts get no per-step marks.
- Next: failed run, stale or missing steps, a waiting plan, an open `plans/TRACKER.md` row, then `verify`. The time estimate sums the last benchmarks of the steps `run.sh` would redo.
- Writes only `.mycelium-extra/now/<analysis path, "/" as "__">.md` with the full card. Never a file in the analysis folder.
