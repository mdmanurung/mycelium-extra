---
name: data-contract-check
description: Test a plan's data assumptions against the actual sample-level table before an analysis runs, read-only. The plan's assumptions (required columns, cohort levels and row counts, unit of replication, pairing across timepoints, batch versus contrast nesting) go into a small JSON contract; a stdlib checker reports each mismatch as a structured alert with expected, observed, and evidence, and blocks on any failure of a coverage-list kind. Use when the user invokes mycelium-extra data-contract-check, when grill or a plan rests on properties of a metadata or sample table that nobody has verified, or before a statistical test whose validity depends on replication, pairing, or batch structure. Not for per-cell matrices or h5ad internals (v1 reads CSV/TSV tables only), and not for checking code.
---

# Mycelium Extra: Data contract check

Write down what the plan assumes about its sample table, check it against the file, and bring every failure to the user. The checker decides what blocks; the contract only states the assumptions.

## 1. Write the contract

- Find the sample-level table the analysis will use (one row per sample, acquisition, or pseudobulk unit), from the data manifest, analysis doc, or loading code. Name columns by header, as the table spells them.
- State only assumptions the plan relies on. Take each value from the plan or the repository, not from a first look at the data: a contract fitted to the data checks nothing.
- The unit column must hold resolved identity. The checker cannot follow a crosswalk: if one person carries two IDs (for example a repeat-donor map), a unit check on the raw ID column undercounts repeats. Say so in the report, or use a column that already resolves identity.
- Pass the contract by process substitution (section 2), which writes no file. Inside grill it is the only allowed form. Outside grill, a `mktemp` file outside the repository also works; never write the contract into the repository before the plan is approved.

```json
{
  "schema": "mycelium-extra.data_contract.v1",
  "table": "data/processed/<dataset>/sample_metadata.tsv",
  "filters": [{"column": "preferred_acquisition", "equals": "TRUE"}],
  "checks": [
    {"kind": "schema", "columns": ["participant", "cohort", "visit", "batch"]},
    {"kind": "cohort", "column": "cohort", "levels": ["A", "B"], "min_rows": 40, "no_missing": ["batch"]},
    {"kind": "unit_of_replication", "unit": "participant", "group": "cohort", "within": ["visit"], "min_units_per_group": 3},
    {"kind": "pairing", "unit": "participant", "within": "visit", "levels": ["0", "28"]},
    {"kind": "batch_confounding", "batch": "batch", "contrast": "cohort"}
  ]
}
```

- `filters` (`equals`, `in`, `not_in`) apply to every check; a check may add its own `filters`, `table`, and `label`. Values compare as strings (`"TRUE"`, not `true`).
- `cohort`: required `levels` present, `min_rows` or exact `rows`, and no missing values in `no_missing` columns.
- `unit_of_replication`: at most one row per unit in each `group` × `within` cell; at least `min_units_per_group` distinct units per group (default 2); no unit in two groups unless `units_may_span_groups` is true (a crossover or paired contrast).
- `pairing`: every unit observed at every `within` level (listed, or all levels present).
- `batch_confounding`: blocks when the contrast is fully nested in batch, or when any level shares no batch with another level; warns when some batches hold one level, or a level sits in one batch.
- Missing values (`""`, `NA`, `NaN`, `NULL`) in a check's key columns are left out of that check and reported as a warning.

## 2. Run it

From the project root, stdin form only, so Mycelium's hooks stay closed:

```bash
python3 - --contract <(cat <<'EOF'
{"schema": "mycelium-extra.data_contract.v1", "table": "...", "checks": [...]}
EOF
) < <skill-dir>/scripts/data_contract_check.py
```

Output is one line per check (`PASS`, `WARN`, or `BLOCK`, with the rows it ran on), followed by its alerts. `--json` gives `{"checks": [...], "alerts": [...]}`; `--root <dir>` resolves relative table paths from another directory. Exit 0 is clean or warnings only, 2 is blocking, 1 is a malformed contract (bad JSON, unknown kind, missing required key): fix its syntax, never its assumptions. A missing table or column, or a filter that leaves no rows, is a failed assumption and blocks. Running the script by path opens Mycelium's post-action cycle, so never do that.

## 3. Act on the alerts

- **Blocking alert**: report it to the user with its expected, observed, and evidence lines, and what it means for the plan (for example, "20 participants have two acquisitions at the same visit, so a cell-level or row-level test would count them twice"). In grill, it becomes a plan edit the user approves or a `DECISION_REQUIRED`. Do not start the analysis while a blocking alert stands.
- **Never loosen the contract to make it pass** (drop a check, change a threshold, add a filter, switch the unit column) without the user agreeing. That silent adjustment is the failure this skill exists to catch. When the user agrees to a change, re-run and cite both runs.
- **Warning**: list it at the end with its count; it does not stop the plan.
- **Relaxations** (`units_may_span_groups`) are echoed next to their check. Use one only when the plan's design calls for it (a crossover or paired contrast), and name it in the report.
- A check the table cannot answer (a column or table the plan needs is absent, or its filters leave no rows) blocks; report which property is unverified and where it might live.

## 4. Report

One line per check: the kind, the assumption, pass / warn / block, and the observed counts. In grill, a passing contract is `repo` evidence for the plan's rows it covers; cite the table path and the contract's checks. Record the contract with the plan's "Decisions to record" so the executing workflow can re-run it.
