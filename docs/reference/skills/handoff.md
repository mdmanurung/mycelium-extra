# handoff

Writes a short `HANDOFF.md` at the project root so a fresh session can resume from one small file. Guide: [Hand off](../../guides/hand-off.md). It is not Mycelium's session summary (`.mycelium/last-session.md`).

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`).

`/mycelium-extra:handoff` (Codex: `$mycelium-extra:handoff`). No script and no flags. The gate suggests it after `hints on`, on wrap-up wording or when context passes about 120k tokens.

## What it does

1. Gathers cheaply: `git status --short`, `git log --oneline -15`, `git diff --stat`; everything else comes from the conversation.
2. If the last grill brief ended `READY` or `READY_WITH_ASSUMPTIONS` and you have not approved it, it looks the brief up by content in `.mycelium-extra/pending/*.json` and points `HANDOFF.md` at the stored copy (or pastes the whole brief when there is none). It never summarises a pending plan.
3. If `HANDOFF.md` exists, reads it, carries forward only what still holds, and prints its first ten lines to you before overwriting.
4. Writes `HANDOFF.md`, under about 80 lines (a verbatim pending plan does not count). The first line carries the time and commit copied from `date` and `git rev-parse`; then Check first (the `git log <hash>..HEAD` and `git status` the next session runs to see what changed since), Goal, Next action, Pending plan, State, Locked decisions, Dead ends, Read first, Open items. Empty sections are omitted.
5. Ends with a resume prompt: `Read HANDOFF.md, run its Check first, then <next action>.` With a pending plan the prompt tells the new session to print the stored plan unchanged; the gate then shows a fresh card, and you approve the hash that card shows.

## Reads and writes

Reads git state, the conversation, `.mycelium-extra/pending/` and `.mycelium-extra/track-changes/<analysis>/brief.md` (listed as a pointer). Writes only `HANDOFF.md`, overwriting. It does not commit, change `.gitignore`, or write `.living/` or Mycelium's files. A focus is never restored for you: the next action may tell you which `focus analysis/X` to type.

## Default on or off

On when invoked.

## Enforced versus the agent's instruction

Nothing here is enforced. The Check first step is an instruction to the next session, not a check anything runs for it. Overwriting without a backup, printing the old head first, the 80-line limit, leaving out secrets and not committing are all the agent's instructions. The file is usually untracked, so the old copy is not kept anywhere; copy it aside first if you want it.
