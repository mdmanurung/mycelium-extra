# data-contract-check

Tests a plan's data assumptions against the actual sample table before an analysis runs. You write the assumptions as a small JSON contract; a stdlib checker reports each mismatch with expected, observed and evidence. Guide: [Plan an analysis](../../guides/plan-an-analysis.md). Usually called by [grill](grill.md) when sample assumptions matter.

## Synopsis

```bash
sh <skill-dir>/../../hooks/py.sh - --contract <(cat <<'EOF'
{"schema": "mycelium-extra.data_contract.v1", "table": "...", "checks": [...]}
EOF
) [--root DIR] [--json] [--result-json PATH] < <skill-dir>/scripts/data_contract_check.py
```

Invoke with `/mycelium-extra:data-contract-check`. Run from the project root, stdin form only. Never run the script by path.

## Options

| Option | Meaning |
|---|---|
| `--contract PATH` | The contract JSON (required). Pass it by process substitution so no file is written. Inside grill that is the only allowed form; elsewhere a `mktemp` file outside the repository also works. |
| `--root DIR` | Directory relative table paths resolve from (default `.`). |
| `--json` | `{"checks": [...], "alerts": [...]}` instead of text. |
| `--result-json PATH` | Also write `mycelium-extra.contract_result.v1`: contract and input hashes, each check's id, kind, status, message, alerts and `runnable`, the exit code and an overall status. Write it outside the repository until the plan is approved. |

## The nine check kinds

| Kind | What it checks |
|---|---|
| `schema` | the named columns exist |
| `cohort` | required levels present, `min_rows` or exact `rows`, no missing values in `no_missing` columns |
| `unit_of_replication` | at most one row per unit per group-by-`within` cell; at least `min_units_per_group` units per group (default 2); no unit in two groups unless `units_may_span_groups` |
| `pairing` | every unit observed at every `within` level |
| `batch_confounding` | contrast fully nested in batch, or levels sharing no batch (block); optional `max_share` warns when a batch holds more than that share of one level |
| `unique_key` | the named columns are nonempty and their combination is unique |
| `sample_alignment` | the table's sample keys match a declared sample sheet or matrix header (`reference`; optional `agree_on`) |
| `identifiers` | identifiers are unique and found in a declared `namespace` file; without one, date-like strings warn and the check is a gap |
| `h5ad_layer` | properties of an `.h5ad` matrix path: `non_negative`, `integer_valued`, `max_at_most` (a finite number; `0` is a limit too), on a bounded sample (`sample_values`, default 100000) |

Common fields: `filters` (`equals`, `in`, `not_in`) at contract or check level, `table`, `label`, `id`. The last three kinds compare the table with a file from outside the table and outside the analysis code; a list copied from the table passes whatever is wrong with it. `h5ad_layer` ignores contract-level filters.

Tables: `.csv` (comma), `.tsv`, `.tab`, `.txt` (tab) or `.h5ad` (its `obs`, through h5py). Strict UTF-8 and quoting. Any other extension is an unreadable-table gap.

## Profile a table (optional)

`--profile-only --profile-spec PATH [--root DIR] [--json]` describes one CSV or TSV instead of checking it: rows read, group counts and missing values. It is not a validation result and is never read by `verify`. Counts below `small_cell_suppression` (default 5) are never shown; the group breakdown is left out whole. A table cut off by `max_rows_inspected` (default 250000) is `partial` and gives no total. An `.h5ad`, an unreadable table or an absent column is `unavailable` (exit 3). A bad spec is exit 1. The ordinary `--contract` command line is unchanged. The spec fields are in the skill's section 5.

## Output and exit codes

One line per check: `PASS`, `WARN`, `GAP` or `BLOCK`, with the rows it ran on; a `note:` line naming what passing does not show; the batch-by-contrast table for `batch_confounding`; then the alerts.

| Exit | Meaning |
|---|---|
| 0 | clean, or warnings only |
| 1 | malformed contract (bad JSON, unknown kind or key, missing key, `max_share` out of range); also `py.sh` finding no Python 3.9 or later |
| 2 | blocking alert |
| 3 | a gap and nothing blocking |

A missing table or column, or a filter that leaves no rows, is a failed assumption and blocks. A table the checker cannot read (an `.h5ad` without h5py, a non-HDF5 file) is a gap: the check did not run, which is neither a pass nor a failure.

## Reads and writes

Reads the named tables, reference files and the contract. Writes nothing, except the file you name with `--result-json`.

## Default on or off

On when invoked. The gate's hint `data-contract-check` appears only after `hints on`, on prompts that mention a sample table or cohort counts.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| The checker decides what blocks; a contract cannot downgrade a block | Enforced by the script |
| Read-only, never writing the contract into the repository before approval | The agent's instruction (the script cannot see how the contract was passed) |
| Never loosening the contract to make it pass without your agreement; reporting every block and gap | The agent's instruction |

## Limits

A pass means only the stated comparison held. Equal key sets do not prove the analysis pairs counts and metadata by key; that needs a project test that shuffles the metadata. `h5ad_layer` cannot tell which normalisation produced the values. Seurat objects are not read. If one person has two IDs, a unit check on the raw column undercounts repeats; say so or use a resolved column.
