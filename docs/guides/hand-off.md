# Hand off to a fresh session

`handoff` writes one short `HANDOFF.md` so a new session can resume from a single file instead of the old conversation.

## What you control here

- **Your typed word:** the invocation, and whether to commit the file. It is never committed for you and `.gitignore` is not changed. You also type `/clear` (or open a new session) and paste the resume prompt.
- **Shown to you:** the first ten lines of any older `HANDOFF.md` before it is replaced, and the resume prompt at the end.
- **To say no:** do not invoke it. It never writes to Mycelium's files, and a handoff never restores a focus or an approval for you.

## Steps

1. Invoke it at any pause, or when the context is large:

   ```text
   /mycelium-extra:handoff
   ```

   With `hints on`, the Stop hook also suggests it once per session when the context passes 120k tokens.
2. It reads only `git status --short`, `git log --oneline -15` and `git diff --stat`, plus the conversation. It carries forward only decisions and dead ends that still hold, and stays under about 80 lines.
3. If a grill plan was shown but not approved, the file points to the plan's stored text instead of summarising it, so the new session can re-present it unchanged.
4. If the work was on one analysis folder, the next action includes the line for you to type first, such as `focus analysis/vaccine-response`.
5. In the new session paste the resume prompt it printed. With a pending plan, approve the hash on the fresh card; it equals the old hash when the text is unchanged. If it differs, compare it with the stored copy before approving.

## Worked example

No captured handoff session exists for this page, so no output is shown. The file's sections, from `skills/handoff/SKILL.md` (an empty section is left out):

```markdown
# Handoff — <topic>
## Goal
## Next action
## Pending plan
## State
## Locked decisions
## Dead ends — do not redo
## Read first
## Open items
```

The resume prompt has this form:

```text
Read HANDOFF.md, then <next action>.
```

## What this does not guarantee

A handoff is the agent's summary of the session. It can omit or misstate something, so read it before relying on it. It points to code and decisions; it does not verify them. See [what this does not guarantee](../concepts/not-guaranteed.md).

## Reference

[handoff](../reference/skills/handoff.md) · [focus](stay-oriented.md) · next: [second-model review](second-model-review.md)
