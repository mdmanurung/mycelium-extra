---
name: analysis-map
disable-model-invocation: true
description: Chart a research program too big for one session as a map of decision tickets, then resolve them one at a time. Plans decisions; runs no analysis.
---

# Mycelium Extra: Analysis map

Chart the way to a big goal as decision tickets in local markdown, then resolve them one per session until the route is clear. Adapted from Matt Pocock's wayfinder and chief-of-staff skills (MIT).

The map plans decisions. It runs no analysis and writes no plan rows. When the route is clear, `/mycelium-extra:grill` turns the decisions into plan rows, and gate approval stays the only way to run.

## Files

For analysis `analysis/<name>/`, both are Extra's own, written only by this skill:

- `plans/MAP.md`: the index. Sections: Destination, Notes, Decisions so far, Not yet specified, Out of scope. Template: `<skill-dir>/templates/MAP.md`.
- `plans/map/NN-<slug>.md`: one ticket each. Template: `<skill-dir>/templates/ticket.md`.

Never write `todo/` or `.living/`. A decision that must bind later goes through `decision-status` after the user confirms.

The map holds a one-line gist and a link per decision. The detail lives once, in the ticket. In text for the user, name a ticket by its title, never by its number.

## Ticket types

| Type | Who | How it resolves |
|---|---|---|
| research | AFK | `research-note` writes a cited note. The ticket links the note. |
| prototype | HITL | `prototype-analysis` makes a throwaway artifact. Resolves when the user reacts to it. |
| grilling | HITL | `grill` interviews the user, with `glossary` when present. |
| task | HITL or AFK | Manual work that unblocks a decision: request data access, transfer files, build a reference, ask the collaborator. |

A HITL ticket resolves only through the user's own answers. Never answer for them. A task records what was done and the facts later tickets need (paths, row counts).

## Chart a map

Use when the user states a goal too big for one session. Done when `plans/MAP.md` and its first tickets exist and `map_status.py` exits 0.

1. Name the destination with the user. Pick a shape: see `references/destinations.md` for the three.
2. Ask breadth-first across the whole space. If the way is already clear and fits one session, stop and say so; no map is needed.
3. Write `plans/MAP.md` from the template: Destination and Notes filled, the fog under Not yet specified.
4. Write a ticket for each question you can state precisely now, with its type and `Blocked by` (separate several blockers with `;`).
5. Run `map_status.py` (below). Stop. Charting resolves no ticket.

Fog or ticket: write a ticket when you can state the question precisely now, even if you cannot answer it. Write fog when you cannot yet phrase it that sharply. Do not slice fog into ticket-sized pieces.

## Work the map

Use when the user names a map or a ticket. Resolve one ticket per session; research tickets may run in parallel.

1. Run `map_status.py`. The frontier is the open, unblocked, unclaimed tickets. Take the user's ticket, else the first on the frontier.
2. Claim it first: set `Claimed: <date> <session>` in the ticket. Done when the file shows it.
3. Resolve it as its type says. Read Notes and any closed ticket it depends on.
4. Close it: write the Resolution, set `Status: closed`, clear `Claimed`, add one line to Decisions so far. Cite saved figures by path only if you inspected them; otherwise write `unsupported: no inspected figure`.
5. Clear the fog the answer exposed: graduate what you can now state into tickets and delete that fog line. A ticket past the destination closes with a one-line reason under Out of scope. A decision that voids other tickets means you update or delete them.
6. Strategic step: see below. Then run `map_status.py` again.

An impactful choice (one that would change a headline estimate, ranking, selected feature or conclusion) is the user's. A ticket may record it as the user's answer. It never closes on a default.

## Strategic step

After each close, ask what in the environment would make the next ticket cheaper. Write the answer as a `Strategic:` line in Notes, or as a new task ticket when it needs work. Examples and triggers: `references/strategic.md`. Done when the line or ticket exists, or you wrote `Strategic: none`.

## Status script

Read-only, stdlib only. It prints the frontier, blocked, claimed and fog counts. It flags cycles, tickets that name a missing ticket, and closed tickets without a Resolution. Exit 0 sound, 1 problems.

```bash
<skill-dir>/../../hooks/mxpy - analysis/<name> < <skill-dir>/scripts/map_status.py
```

## Finish

The route is clear when no ticket is open and no fog remains. Say so, list Decisions so far, and offer `/mycelium-extra:grill` with the decisions as input. Done when the user has the offer.
