---
name: handoff-resume
disable-model-invocation: true
description: Hand off, restart and resume in one chain; hooks check each link and the next session reads HANDOFF.md first.
---

# Mycelium Extra: Handoff and resume

Claude cannot restart its own session. This skill writes the handoff, arms a marker, and a hook makes the next session read `HANDOFF.md` before anything else. You type two things: `/clear`, then any message.

Run the helper as `<skill-dir>/../../hooks/mxpy <skill-dir>/../../hooks/resume_run.py <mode>`.

1. Run mode `request`. Done when it prints `handoff-resume requested`. From here the Stop hook blocks the end of your turn until step 3 is done.
2. Write `HANDOFF.md` by following the handoff skill (`../handoff/SKILL.md`, sections 1 and 2). Done when the file has a `## Next action` section.
3. Run mode `arm`. Done when it prints `armed`. If it prints `not armed`, fix what it names and run it again.
4. Tell the user, in these words: `Type /clear, then send any message (for example "go"). The new session reads HANDOFF.md first.`

The next session's first prompt gets the instruction to read `HANDOFF.md`, run its Check first, and do its Next action. With a pending plan it reprints the plan unchanged, so the gate shows a fresh card to approve; approvals never carry over a restart.

- `resume_run.py status` shows the marker; `resume_run.py cancel` removes it.
- The marker fires once, only in a different session, and only within 48 hours.
- Same person, same session, short break: use `where` instead.

Hooks: `Stop` blocks the requesting session until the handoff is fresh and armed (for at most an hour). `UserPromptSubmit` gives another session the resume instruction once; the marker goes when that session ends its first turn. Two sessions that open at once in the same repo can still race for it. `PostToolUse` records which session ran `request`, so only that session is held and only another one resumes. All three stay silent when no marker exists. A session id missing from the event means no action.
