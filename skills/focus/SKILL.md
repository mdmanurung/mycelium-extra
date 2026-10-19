---
name: focus
description: Explain and use `focus`, the typed command that says which analysis this Claude session is working on (`focus <folder>`, `focus status`, `focus switch <folder>`, `focus end`), and list the folders a focus can name. Focus is advisory: it grants no run, extends no approval, and is changed only by the user typing the command. Use when the user invokes mycelium-extra focus, asks how to declare or switch the current analysis, asks which analysis is in focus, or wants the folders they can focus on. Not for approving a plan (use grill), for scaffolding a folder (use new-analysis), or for seeing what changed (use track-changes).
---

# Mycelium Extra: Focus

`focus` records, for one Claude session, "we are working on `analysis/X`". The user types it; this skill only explains it and lists folders.

## What the user types

Send each as the whole prompt. The gate answers it; the agent does not run it.

| Prompt | Effect |
|---|---|
| `focus analysis/X` or `focus nbs/topic` | Start a focus on an existing folder under a gated root (`analysis/` and `nbs/` by default, or the folders in `gate.json`'s `gated_paths`). Refused if one is already open, the folder does not exist, or it is outside those roots. |
| `focus <folder> plan <hash>` | Same, and note that approved plan `<hash>` is the original intent. Refused unless that plan's table names a path inside the folder. |
| `focus status` | A short card: objective (quoted from the analysis doc), plan, and whether a run is authorized in this session. |
| `focus switch <folder>` | End this focus and start the next; the first stays in the record. |
| `focus end` | Close it. This does not mean the analysis is done or reportable. |

## What you do

- To list folders a focus can name: `sh <skill-dir>/../../hooks/py.sh - list < <skill-dir>/../../hooks/focus.py`. Read-only. Then tell the user the exact line to type.
- Never write `.mycelium-extra/focus/` yourself and never type a focus command for the user. Only the user's typed command changes a focus.
- While a focus is open the gate adds one advisory line to each prompt. Stay on that analysis unless the user directs otherwise. If the user asks something that clearly belongs to another analysis, say so in one line and offer `focus switch <folder>`; still answer them, and never refuse ordinary conversation.
- Focus is not permission. A run needs an approved plan as before; `focus status` shows that separately.
- A folder that does not exist yet is created with `new-analysis`, then focused.
- To see what changed against the approved intent, use `track-changes`.
