---
name: idea
description: Park a passing idea in one line, with no questions, so the main work keeps its flow. Writes `todo/<slug>.md` and one `todo/TODO_REGISTRY.md` row (priority `idea`, status `open`) in Mycelium's own todo format, then replies with one line. Use when the user invokes mycelium-extra idea, or says "idea:", "park this", "note this for later", "remind me to try", or "add to the idea list". Never runs code, never changes the current plan or the approval gate. Not Mycelium's `todo-idea` mode (which asks up to six questions) and not for choosing what to work on (use idea-triage).
---

# Mycelium Extra: Idea

Capture the idea and go back to the task. Ask nothing. Use the user's words as written; do not improve, research, or plan the idea.

## 1. Capture

1. Title: the first 8 words of the idea. Description: the full text, verbatim.
2. Fixed fields: Priority `idea`, Status `open`, Category `idea`, Date today (`date +%F`), Author `git config user.name` (else `unknown`).
3. Notes: one line of context that costs no questions: branch (`git branch --show-current`), the analysis folder or file being worked on, and the active plan hash if a grill card is waiting.
4. Slug: lowercase kebab-case of the title. If `todo/<slug>.md` exists, append `-2`, `-3`.
5. Create `todo/<slug>.md` from Mycelium's `TODO_ITEM_TEMPLATE.md` (`todo/` in the project, else the same file in the Mycelium plugin). Without a template, write this minimum:

   ```markdown
   # <Title>

   | Field | Value |
   |-------|-------|
   | **Date** | <date> |
   | **Author** | <author> |
   | **Priority** | idea |
   | **Status** | open |
   | **Category** | idea |

   ## Description

   <the user's words>

   ## Notes

   <context line>
   ```

6. Add one row to `todo/TODO_REGISTRY.md`: `| <Title> | idea | open | idea | <date> | <author> | [<slug>.md](<slug>.md) |`. Create the registry with Mycelium's header (Item, Priority, Status, Category, Date, Author, File) when it does not exist.
   - Prefer Mycelium's `skills/core/scripts/upsert_table_row.py todo/TODO_REGISTRY.md '<Title>' '<row>'`; it locks the table. Find it through `~/.claude/plugins/installed_plugins.json` (the `mycelium@mycelium` `installPath`); do not take the last directory of a listing.
   - That script needs Python 3.7 or newer. If it is missing or exits non-zero for any reason, do not retry: insert the row above the line `<!-- Add new entries above this line -->` with an edit (at the end of the table when the line is absent).

## 2. Reply

One line, then continue the task you were doing:

`Parked: <title> → todo/<slug>.md`

Append ` (plan <hash> still waiting)` when a grill card shown in this conversation has not been approved. Approval needs only `approve plan <hash>`, so this reply does not cancel it.

## Limits

- Write only under `todo/`. No analysis code, no `.mycelium-extra/`, no `.living/`, no git commit.
- Do not start the idea, even when it looks quick. `idea-triage` chooses what to work on next.
- Several ideas in one message: one file and one row each, one reply line.
