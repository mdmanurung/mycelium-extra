# ask-extra

Names the skills that fit your situation, grouped by what you are doing. It only hints: it cannot start another skill. Adapted from Matt Pocock's ask-matt skill (MIT).

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`).

```text
/mycelium-extra:ask-extra [what is going on]
```

Rebuild the table the skill reads (read-only; prints to stdout):

```bash
<skill-dir>/../../hooks/mxpy - --repo . < <skill-dir>/scripts/make_router_table.py
```

## What you get

If you did not say what is going on, one question: lost track, starting something, exploring, something looks wrong, want to report, or want the structure cleaner. Then one to three skills, each with the exact text to type and one line on why it fits.

## Groups

| Group | Skills it points to |
|---|---|
| I lost track | `where`, `focus`, `re-pitch`, `handoff` |
| I am starting something | `new-analysis`, `grill`, `analysis-map`, `research-note`, `glossary`, `questionnaire`, `setup-wizard`, `repo-setup`, `init`, `idea-triage` |
| I am exploring | `prototype-analysis`, `plot-first`, `check-first` |
| Something looks wrong | `diagnose-result`, `verify`, `track-changes` |
| I want to report | `analysis-report`, `verify`, `manuscript-audit` |
| I want the structure cleaner | `improve-structure`, `skill-style`, `harden` |

The full table, with each skill's own one-line summary, is `skills/ask-extra/references/router-table.md`.

## How the table stays current

`scripts/make_router_table.py` reads the frontmatter of every `skills/*/SKILL.md` and prints the table. The group map lives in that script. A user-invoked skill with no group lists under "Other", and the test prints a warning. `tests/test_ask_extra.py` fails when a user-invoked skill is missing from the table, when the table names a skill that does not exist, or when the committed table differs from the generated one.

## Reads and writes

Reads `references/router-table.md`, and a skill's own `SKILL.md` before it says more than the table line. Writes nothing.

## Default on or off

Off until you type it. It never loads context on its own.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| The table lists every user-invoked skill and names only skills that exist | Enforced: `tests/test_ask_extra.py` |
| The table matches the skills' descriptions | Enforced: the same test compares it with the generated text |
| It starts no other skill | Enforced: user-invoked skills have no description the agent can reach |
| Naming one to three skills, and checking a skill's `SKILL.md` before describing it | The agent's instruction |

See [where](where.md) for the state of one analysis, and [skill-style](skill-style.md) for writing a skill the router can name.
