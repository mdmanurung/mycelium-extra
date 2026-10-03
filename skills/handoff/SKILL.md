---
name: handoff
description: Write a short `HANDOFF.md` at the project root so a fresh session can pick the work up by reading one small file instead of the old conversation. Records the goal, the exact next action, current state, decisions the user locked in, dead ends not to redo, and the few `path:line` pointers to read first. Overwrites the previous handoff, carrying forward only what still holds, and stays under about 80 lines. Use when the user invokes mycelium-extra handoff, or asks to hand off, write a handoff, save state, wrap up for a new session, continue in a fresh session, or avoid context bloat. Not Mycelium's session summary (`.mycelium/last-session.md`, which Mycelium's own hooks write and load) and not a report or changelog.
---

# Mycelium Extra: Handoff

Write `HANDOFF.md` at the project root: the least a fresh session needs to keep working. The next session reads this file plus the pointers it names, and nothing else. Every line costs tokens on every resume, so cut anything git, the code, or Mycelium's memory already holds.

## 1. Gather cheaply

- Find the project root (`git rev-parse --show-toplevel`, else the working directory).
- Run only `git status --short`, `git log --oneline -15`, and `git diff --stat`. Write everything else from the conversation. Do not re-read files to summarise them; a pointer is enough.
- If `HANDOFF.md` exists, read it before overwriting. Carry forward locked decisions, dead ends, and open items that still hold. Drop finished work, or keep it as one line with its commit hash.

## 2. Write

Overwrite, never append. Keep it under about 80 lines. Omit a section that would be empty; never pad one.

```markdown
# Handoff — <topic>

**Date:** YYYY-MM-DD · **Branch:** <branch> @ <short-hash> · **Status:** <one line>

## Goal
<1–2 lines: what we are trying to achieve, and what done looks like>

## Next action
<the exact first command or edit, with path:line>

## State
- Uncommitted: <files, or "clean">
- Tests: <passing / failing, with the failing name>
- <anything running: job IDs, servers, envs>

## Locked decisions
- <decision> — <why> (user, YYYY-MM-DD)

## Dead ends — do not redo
- <approach> — <evidence that killed it>

## Read first
- `path:line` — <why it matters>

## Open items
- <item> — <return condition>
```

Rules:

- Point, don't paste: cite `path:line` and commit hashes, never copy code, logs, or long output.
- Facts, not narrative. Each bullet is one line.
- Locked decisions and dead ends earn their space: they stop the next session re-asking or re-trying. Keep the reason with each.
- In a Mycelium repository (`.living/` exists), link to `.mycelium/last-session.md` and to `.living/decisions.md` or `learnings.md` entries by heading; do not copy them. Never write to Mycelium's files from this skill.
- Leave out secrets, tokens, and credentials.

## 3. Finish

- Check `wc -l HANDOFF.md`; if it is over about 80 lines, cut the oldest or least actionable items.
- Do not commit it or change `.gitignore`; that is the user's call.
- If Mycelium's Stop hook asks for `.living/` updates afterwards, follow the hook.
- End with the resume prompt on its own line, then tell the user to run `/clear` (or open a new session) and paste it:

  `Read HANDOFF.md, then <next action>.`
