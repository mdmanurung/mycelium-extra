---
name: handoff
description: Write a short `HANDOFF.md` at the project root so a fresh session can pick the work up by reading one small file instead of the old conversation. Records the goal, the exact next action, current state, decisions the user locked in, dead ends not to redo, and the few `path:line` pointers to read first. Overwrites the previous handoff, carrying forward only what still holds, and stays under about 80 lines. Use when the user invokes mycelium-extra handoff, or asks to hand off, write a handoff, save state, wrap up for a new session, continue in a fresh session, or avoid context bloat. Not Mycelium's session summary (`.mycelium/last-session.md`, which Mycelium's own hooks write and load) and not a report or changelog.
---

# Mycelium Extra: Handoff

Write `HANDOFF.md` at the project root: the least a fresh session needs to keep working. The next session reads this file plus the pointers it names, and nothing else. Every line costs tokens on every resume, so cut anything git, the code, or Mycelium's memory already holds.

## 1. Gather cheaply

- Find the project root (`git rev-parse --show-toplevel`, else the working directory).
- Run only `git status --short`, `git log --oneline -15`, and `git diff --stat`. Write everything else from the conversation. Do not re-read files to summarise them; a pointer is enough.
- If the conversation's last grill brief ended `Plan status: READY` or `READY_WITH_ASSUMPTIONS` and the user has not approved it, do not summarise it. Where the approval gate is on, its Stop hook stored the brief word for word; find it by content (a parallel session may have stopped later, so not by the newest file). From the project root, pass a distinctive line of the brief (its `> Question:` line, or its Objective if the question was declined):

  ```bash
  python3 - '<distinctive line>' <<'EOF'
  import glob, json, os, sys
  hits = []
  for path in glob.glob(".mycelium-extra/pending/*.json"):
      try:
          entries = json.load(open(path, encoding="utf-8"))
      except (OSError, ValueError):
          continue
      if isinstance(entries, list):
          hits += [(e.get("ts", 0), path, e["hash"]) for e in entries
                   if sys.argv[1] in e.get("text", "") and "Plan status:" in e.get("text", "")]
  if not hits:
      print("none")
  else:
      ts, path, digest = max(hits)
      done = os.path.isfile(os.path.join(".mycelium-extra", "approvals", digest + ".json"))
      print(path, digest, "approved" if done else "pending")
  EOF
  ```

  `approved` means nothing to carry. `pending` gives the file and hash for the Pending plan section. `none` (no gate, or no match): copy the brief into `HANDOFF.md` word for word instead.
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

## Pending plan
- `<hash>` not approved; stored word for word in `<pending file>`. Re-present it unchanged; do not re-grill. Print it with:
  `python3 -c "import json;print(next(e['text'] for e in json.load(open('<pending file>')) if e['hash']=='<hash>'))"`

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
- A pending plan is never summarised: point to its stored copy, or, when there is none, paste the whole brief under `## Pending plan (verbatim)`. That section does not count toward the line limit. With a pending plan, the next action is to re-present it.
- Leave out secrets, tokens, and credentials.

## 3. Finish

- Check `wc -l HANDOFF.md`; if it is over about 80 lines (not counting a verbatim pending plan), cut the oldest or least actionable items.
- Do not commit it or change `.gitignore`; that is the user's call.
- If Mycelium's Stop hook asks for `.living/` updates afterwards, follow the hook.
- End with the resume prompt on its own line, then tell the user to run `/clear` (or open a new session) and paste it:

  `Read HANDOFF.md, then <next action>.`

  With a pending plan, the resume prompt is `Read HANDOFF.md, then print pending plan <hash> as its Pending plan section says, unchanged, as your whole reply, with nothing before or after it.` Tell the user the gate then shows a fresh card: approve the hash that card shows. It equals `<hash>` when the text is unchanged; if it differs, the reprint changed the plan, so compare it with the stored copy before approving.
