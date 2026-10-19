# decision-status

Works out which past decision still binds a task when `.living/decisions.md` holds several entries on the same choice. Guide: [With Mycelium or in a plain repo](../../guides/with-mycelium-or-plain-repo.md). Usually called by [grill](grill.md) when a plan depends on prior decisions.

## Synopsis

```bash
sh <skill-dir>/../../hooks/py.sh - [--living-dir DIR] [--tag TAG ...] [--term REGEX ...] [--include-learnings] [--json] < <skill-dir>/scripts/decision_threads.py
```

Invoke with `/mycelium-extra:decision-status`. Run from stdin, never by path.

## Options

| Option | Meaning |
|---|---|
| `--living-dir DIR` | Mycelium memory folder (default `.living`). |
| `--tag TAG` | Exact tag, case-insensitive. Repeatable. |
| `--term REGEX` | Regex searched in heading and body. Repeatable. Always pass terms too: about half of real entries carry no tags. |
| `--include-learnings` | Also search `learnings.md`. |
| `--json` | Raw records. |

The output is extraction only. `status`, `supersedes`, `scope`, `revisit` are raw field text; `hints` are status words in the heading. None is a verdict.

## How it resolves

For each decision point, the first rule that fits:

1. **Explicit supersession**: an entry that names an earlier one (a `**Supersedes**:` line, or replace, supersede, overturn or reverse wording) replaces it for its scope. An addendum amends.
2. **Scope match**: entries answering different questions do not conflict; the one whose scope matches binds.
3. **Contested**: otherwise ask you. An entry with no status is `unknown`, not `current`. Recency alone never wins.

At most three questions per session, one per message. Past the cap, each remaining point is carried forward as `contested`.

## Reads and writes

Reads `.living/decisions.md` (required; without it the skill says so and stops), `.living/INDEX.md` and optionally `learnings.md`. After you confirm, appends one entry `### [YYYY-MM-DD] Resolution: <decision point>` with Context, Decision, Status, Supersedes, Scope, Revisit when, Resolved-by, Tags to the end of `.living/decisions.md`. It never edits, reorders, renumbers or deletes an existing entry. Nothing else is written.

## Default on or off

On when invoked. The gate suggests it after `hints on`, on prompts about which decision binds.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| The parser only reads | Enforced by the script |
| Asking you before appending, and writing nothing for an inferred resolution | The agent's instruction: nothing stops the agent from appending |
| The three-question cap; append-only edits | The agent's instruction |

A Mycelium hook may then ask for post-action `.living/` updates; follow it. When called from grill, the skill writes nothing: a resolution you confirm goes in the brief's "Decisions to record".
