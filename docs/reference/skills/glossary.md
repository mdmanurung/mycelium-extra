# glossary

Sharpens an analysis's language while you plan, and keeps a short log of exploratory loops. It approves nothing and runs nothing. Adapted from Matt Pocock's grill-with-docs skill (MIT).

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`).

The drift check is read-only and runs from stdin:

```bash
sh <skill-dir>/../../hooks/py.sh - --analysis analysis/<name> [--json] [--max-hits N] [--glossary PATH] < <skill-dir>/scripts/check_terms.py
```

## What it does

| Part | What happens |
|---|---|
| Sharpen terms | Asks in rounds, each question with a recommended answer that "yes" accepts. It challenges a word that clashes with `GLOSSARY.md`, `data/**/DATA_DICTIONARY.md` or a table column, and invents concrete edge cases (a donor sampled twice, a cell with two donor labels). |
| `GLOSSARY.md` | `analysis/<name>/GLOSSARY.md`, created when the first term resolves. Tight definitions, one `_Avoid_` line each, no implementation details, only terms specific to this analysis. |
| Drift check | `scripts/check_terms.py` lists each term and every `_Avoid_` word found in the analysis doc, `code/` comments and table headers. Exit 0 none found and nothing skipped, 1 drift or a clash, 2 could not run or incomplete (no analysis doc, no terms, scan cut at 400 files). Inline code and path-like words are not searched unless `--include-code-spans`. |
| Decisions | A decision stays out of the glossary. If an alternative would change a headline estimate, ranking, selection or conclusion, and the choice is a real trade-off, the skill offers it to `decision-status` and writes only after you confirm. A rejected alternative with a load-bearing reason goes in as a dead end. No `docs/adr/`. |
| `ITERATIONS.md` | `analysis/<name>/plans/ITERATIONS.md`: one entry per exploratory loop with the question, the inspected figure paths, the belief and its claim level, what would change your mind (written before the next look), the stopping rule and the next question. No metric field: a number would make loops look more settled than they are. |

## Reads and writes

Reads the analysis doc, `code/`, tables under `outputs/` and `data/` (header line only) and the data dictionary. Writes only `GLOSSARY.md` and `plans/ITERATIONS.md`, and `.living/decisions.md` only through `decision-status` after you confirm. The checker writes nothing.

## Default on or off

Off until you type it. It adds no hook, no notice and no gate rule.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| The drift check never writes | Enforced: the script only reads (tested) |
| A gap is not a pass | Enforced: exit 2 when the glossary or a file cannot be read, the glossary has no terms, there is no analysis doc, or the scan was cut |
| Asking before a decision is recorded | The agent's instruction (the `confirm_writes` setting makes it a gate rule for `.living/`) |
| An impactful term needs its own approved plan row | The agent's instruction; the plan itself is the gate's |
| Claim level and inspected figures in `ITERATIONS.md` | The agent's instruction; `verify` does not read this file |

See [decision-status](decision-status.md) for recording a decision and [focus](focus.md) for staying on one analysis.
