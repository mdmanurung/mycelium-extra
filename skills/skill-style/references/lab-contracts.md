# Contracts the style rules do not touch

A contract is text that code parses, a user approves, or a test pins. Style rules cut sentences and swap words; a contract needs its exact shape. Treat each item below as read-only for style work.

| Text | Why it is fixed | Where it lives |
|---|---|---|
| Grill brief sections and their order | The user approves the brief; `brief-format.md` is the single source | `skills/grill/references/brief-format.md` |
| Plan tables (columns, hash, `Plan status:` line) | The gate reads them; approvals key on their hash | `skills/grill/`, `hooks/` |
| Exploration tags `[SHAPE]` `[PLOT]` `[FINDING]` `[NEXT]` | Hooks and `verify explore` parse them | `skills/plot-first/SKILL.md` |
| `unsupported: no inspected figure`, `table fallback: <reason>` | Checked as literal strings | `skills/plot-first/SKILL.md` |
| Hook notices (`systemMessage`) | Plain text, no Markdown; one line where the host truncates | `hooks/` |
| Typed commands (`focus ...`, `approve`) | The gate answers them before the agent sees them | `skills/focus/`, `hooks/` |
| Descriptions | Capped by a test; user-invoked flags kept in both hosts | `tests/test_skill_frontmatter.py` |
| Impactful-choice wording in plan rows | The user's approval covers the exact row | project instructions |

## What you may do

- Shorten the prose around a contract.
- Move a long contract into `references/` behind a pointer, with its text unchanged.
- Report a contract that duplicates another (the audit lists duplicate sentences). Fix it by pointing to one source, in a change that also updates the parsing code and its tests.

## What you check

Done when `git diff` shows no change inside a contract row's text, or shows the change together with the code and test that read it.
