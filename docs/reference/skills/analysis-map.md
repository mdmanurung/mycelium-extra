# analysis-map

Charts a research program too big for one session as a map of decision tickets, then resolves them one at a time. It plans decisions. It runs no analysis and writes no plan rows. Adapted from Matt Pocock's wayfinder and chief-of-staff skills (MIT).

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`). Run it as `/mycelium-extra:analysis-map` (Codex: `$mycelium-extra:analysis-map`). The status script is read-only:

```bash
<skill-dir>/../../hooks/mxpy - analysis/<name> < <skill-dir>/scripts/map_status.py
```

## Files

For `analysis/<name>/`, written only by this skill:

- `plans/MAP.md` is the index: Destination, Notes, Decisions so far, Not yet specified, Out of scope.
- `plans/map/NN-<slug>.md` is one ticket each. The detail lives once, in the ticket.

It never writes `todo/` or `.living/`. A decision that must bind later goes through [decision-status](decision-status.md) after you confirm.

## Ticket types

| Type | Who | How it resolves |
|---|---|---|
| research | AFK | [research-note](research-note.md) writes a cited note. The ticket links it. |
| prototype | HITL | [prototype-analysis](prototype-analysis.md) makes a throwaway artifact. It resolves when you react to it. |
| grilling | HITL | [grill](grill.md) interviews you, with [glossary](glossary.md) when present. |
| task | HITL or AFK | Manual work that unblocks a decision, such as requesting data access. |

A HITL ticket resolves only through your own answers. An impactful choice is yours and never closes on a default.

## Chart and work a map

Charting names the destination, asks breadth-first, writes `MAP.md` and the first tickets, and runs `map_status.py`. It resolves no ticket. If the way is clear and fits one session, it says so and writes no map.

Working a map takes the frontier (open, unblocked, unclaimed tickets), claims one, resolves it by its type, and closes it with a Resolution and one line under Decisions so far. Each close ends with a strategic step: what would make the next ticket cheaper, or `Strategic: none`.

When no ticket is open and no fog remains, the skill lists the decisions and offers `/mycelium-extra:grill` with them as input.

## Status script

Prints the frontier, blocked, claimed and fog counts. It flags cycles, tickets that name a missing ticket, and closed tickets without a Resolution. Exit 0 means sound, 1 means problems.

## Reads and writes

Reads the map, its tickets and any note a ticket links. Writes only `plans/MAP.md` and `plans/map/`.

## Default on or off

Off until you type it.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| Problems in the map (cycles, missing tickets, closed without a Resolution) | Enforced: `map_status.py` exits 1 |
| Running an analysis | Enforced: the map grants nothing; a run still needs an approved plan |
| Claiming a ticket, closing it, leaving impactful choices to you | The agent's instruction |
