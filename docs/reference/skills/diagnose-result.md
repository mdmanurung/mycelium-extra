# diagnose-result

Finds why an analysis result looks wrong, surprising or unstable, or why a step fails or got slow. It builds a feedback loop first, then ranks hypotheses, then probes them one at a time. Adapted from Matt Pocock's diagnosing-bugs skill (MIT).

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`).

```bash
sh <skill-dir>/../../hooks/py.sh - OLD NEW --key donor,gene [--rtol 1e-6] [--atol 1e-8] [--max-rows 10] [--redact-keys] < <skill-dir>/scripts/diff_tables.py
```

The script is the only code in the skill. The rest is the agent's procedure.

## Phases

| Phase | What happens |
|---|---|
| 1. Build a loop | One command that gives the same verdict each run and can go red on the symptom: a check on one step output, a seeded rerun of one step on the smallest set of whole donors or batches, a replay of a saved `outputs/<stem>/` file, a differential loop, bisection, a permutation or simulated-null loop, or a saved and inspected figure. If none can be built, the agent says so and asks for what it needs. |
| 2. Reproduce and minimise | Confirm the loop shows your symptom, then cut donors, genes, steps or parameters one at a time until every remaining piece is needed. |
| 3. Hypothesise | Three to five ranked hypotheses, each with a prediction. The agent shows them before testing. |
| 4. Probe | One probe per hypothesis, one variable at a time, every debug output tagged with a unique prefix such as `[DEBUG-a4f2]` or `debug-a4f2_`. |
| 5. Fix and check | A regression check at a seam where the real pattern occurs, outside the gated paths. If no such seam exists, that is the finding. |
| 6. Clean up | Loop is green, tagged output is gone, the confirmed cause is written in one sentence with its supporting figure. |

The loop kinds are in `skills/diagnose-result/references/loops.md`. The hypothesis catalogue (batch or donor confounding, depth and ambient RNA, leakage, positional alignment, many-to-many joins, a label in "Other", mutated copies, muted warnings, silent filters, changed defaults, unseeded randomness, reference drift, stale steps) is in `references/hypotheses.md`. It prompts; it is not a checklist.

## `diff_tables.py`

Compares two `.csv` or `.tsv` tables (either may be `.gz`) by key columns. It reports rows and columns on one side only, type-like changes (integer, number, text), numeric differences beyond `--rtol` and `--atol`, the first `--max-rows` offending rows, and a one-line summary. `NA`, `N/A` and `nan` match each other; an empty cell is its own value. Text compares exactly (`007` differs from `7`), integers compare exactly, and an infinite value differs from anything but itself. A different column order is reported.

| Exit | Meaning |
|---|---|
| 0 | Identical within tolerance |
| 1 | Different |
| 2 | Unusable input: missing file, missing or empty key, empty file, duplicate keys or column names, or a row wider than the header |

`--redact-keys` hides key values, text cell values and column names, for keys that are donor IDs. Rows show as `row N (OLD)` or `row N (NEW)` and columns by position. Duplicate keys exit 2 because they signal a many-to-many source. The script reads two files and writes nothing.

## Reads and writes

Reads `logs/CHANGES.md`, `outputs/<stem>/` files and git history of the code. Writes only tagged debug files to a scratch folder outside `outputs/<stem>/`, and removes them in phase 6. A rerun of a step needs an approved plan or an allowed exploratory run. It never writes to `.living/` and never edits gated code (`analysis/**`, `nbs/**`) without an approved plan.

## Default on or off

Off until you invoke `/mycelium-extra:diagnose-result`. It adds no hook, notice or prompt.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| Gated paths cannot be edited without an approved plan | Enforced by the approval gate |
| A change to a preprocessing step, filter, threshold, model, covariate or seed is a labelled probe, and you decide whether it enters the analysis | The agent's instruction |
| Showing hypotheses before testing, redacting identifiers, tagging debug output | The agent's instruction |
| `diff_tables.py` never writes | Enforced by the script (it opens files read-only) |

See [where](where.md) to find stale steps and [track-changes](track-changes.md) to review what changed against the approved intent.
