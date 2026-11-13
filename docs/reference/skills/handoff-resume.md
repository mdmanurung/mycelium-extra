# handoff-resume

Writes the handoff, arms a marker, and makes the next session read `HANDOFF.md` first. It cannot restart the session itself: you type `/clear`, then any message.

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`). Run it as `/mycelium-extra:handoff-resume` (Codex: `$mycelium-extra:handoff-resume`). The skill calls the helper:

```bash
<skill-dir>/../../hooks/mxpy <skill-dir>/../../hooks/resume_run.py request|arm|cancel|status
```

## The chain

1. **Request.** `resume_run.py request` prints `handoff-resume requested`. From here the Stop hook blocks the end of the turn until the handoff is fresh and armed.
2. **Write.** The agent writes `HANDOFF.md` by following [handoff](handoff.md). The file needs a `## Next action` section.
3. **Arm.** `resume_run.py arm` checks the file and writes `.mycelium-extra/resume.json`. It prints `armed`, or `not armed` with what to fix.
4. **Restart.** The agent tells you: `Type /clear, then send any message (for example "go"). The new session reads HANDOFF.md first.`
5. **Resume.** The first prompt of the new session gets one instruction: read `HANDOFF.md`, run its Check first, do its Next action. With a pending plan, the new session reprints the plan unchanged. The gate then shows a fresh card to approve.

`resume_run.py status` shows the marker. `resume_run.py cancel` removes it.

## Hooks

Three hook entries in `hooks/hooks.json` run `hooks/resume_run.py`. All stay silent when no marker exists, and a session id missing from the event means no action.

| Hook | Job |
|---|---|
| `PostToolUse` | Records which session ran `request`, so only that session is held and only another session resumes. |
| `Stop` | Blocks the requesting session until `HANDOFF.md` is fresh and armed, for at most an hour. |
| `UserPromptSubmit` | Gives a different session the resume instruction once. The marker goes when that session ends its first turn. |

## Reads and writes

Reads `HANDOFF.md` and the marker. Writes `HANDOFF.md` (through the handoff skill) and `.mycelium-extra/resume.json`. It is separate from the approval gate and works without `gate.json`.

## Default on or off

Off until you type it. The marker fires once, only in a different session, and only within 48 hours. `HANDOFF.md` must be at most 15 minutes old to arm.

## Limits

- It cannot restart itself. You type `/clear` and a message.
- Approvals do not carry over. The new session shows a fresh card for any pending plan.
- Codex and OpenCode have no resume hook, so they get the files but no automatic instruction. Paste the resume prompt by hand.
- Two fresh sessions that open at once in the same repo can race for the marker.
- Same person, same session, short break: use [where](where.md) instead.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| The requesting session cannot end its turn before the handoff is armed | Enforced: the Stop hook blocks it |
| Only a different session gets the resume instruction, once | Enforced: the hooks check the session id |
| What `HANDOFF.md` holds | The agent's instruction (see [handoff](handoff.md)) |
| Reading the handoff and doing its Next action | The agent's instruction, given by the hook |
