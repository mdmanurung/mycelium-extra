---
name: data-contract-check
description: Test a plan's data assumptions against the actual sample-level table before an analysis runs, read-only. The plan's assumptions (required columns, cohort levels and row counts, unit of replication, pairing across timepoints, batch versus contrast nesting) go into a small JSON contract; a stdlib checker reports each mismatch as a structured alert with expected, observed, and evidence, and blocks on any failure of a coverage-list kind. Use when the user invokes mycelium-extra data-contract-check, when grill or a plan rests on properties of a metadata or sample table that nobody has verified, or before a statistical test whose validity depends on replication, pairing, or batch structure. Reads CSV/TSV tables and the `obs` of an `.h5ad` file (through h5py when it is installed); also compares keys, identifiers, or an `.h5ad` layer against independent evidence the plan names, and writes a machine-readable result; not for Seurat objects or checking code.
---

# Mycelium Extra: Data contract check

Write down what the plan assumes about its sample table, check it against the file, and bring every failure to the user. The checker decides what blocks; the contract only states the assumptions.

## 1. Write the contract

- Find the sample-level table the analysis will use (one row per sample, acquisition, or pseudobulk unit), from the data manifest, analysis doc, or loading code. Name columns by header, as the table spells them.
- A table is a `.csv` (comma), a `.tsv`, `.tab`, or `.txt` (tab-separated), or a `.h5ad` (its `obs`); any other extension is an unreadable-table gap, so export it to CSV or TSV. A CSV or TSV is read as strict UTF-8 and with strict quoting: a row with more fields than the header (an R `write.table` export with row names does this), or a quote that never closes, is a malformed table and blocks every check on it; a short row's absent trailing cells count as missing values; bytes that are not UTF-8 are a gap, since replacing them could merge distinct identifiers. For an `.h5ad`, `obs` is read through h5py when it is importable; X and layers are never read. The index is a column named as the file names it (`_index` unless the index had a name). Values compare as the strings a CSV export would hold: categories as written, integers as `28`, floats as `28.0`, booleans as `True`/`False`; a missing category, masked value, or NaN counts as missing. An `.h5ad` `obs` is usually one row per cell: a unit check on it counts cells, and `max_share` is a share of cells.
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
    {"kind": "batch_confounding", "batch": "batch", "contrast": "cohort", "max_share": 0.7}
  ]
}
```

- `filters` (`equals`, `in`, `not_in`) apply to every check; a check may add its own `filters`, `table`, and `label`. Values compare as strings (`"TRUE"`, not `true`).
- A contract needs at least one check. A cohort check names a column, row-count constraint, or nonempty `no_missing` columns; an empty check is a usage error. Each filter names one column and exactly one operation; `in` and `not_in` take lists. Counts are nonnegative integers (`min_units_per_group` must be positive); `units_may_span_groups` is a JSON boolean, never a string. Malformed types and unknown keys are usage errors, not relaxed assumptions. A row whose fields are all empty (an Excel `,,,` line) is not a sample and is not counted. Duplicate table headers are an unreadable-table gap because choosing one would lose data (blank header fields from trailing delimiters are ignored).
- `cohort`: required `levels` present, `min_rows` or exact `rows`, and no missing values in `no_missing` columns.
- `unit_of_replication`: at most one row per unit in each `group` × `within` cell; at least `min_units_per_group` distinct units per group (default 2); no unit in two groups unless `units_may_span_groups` is true (a crossover or paired contrast).
- `pairing`: every unit observed at every `within` level (listed, or all levels present).
- `batch_confounding`: blocks when the contrast is fully nested in batch, or when any level shares no batch with another level; warns when some batches hold one level, or a level sits in one batch. With `max_share` (a share above 0 and at most 1, such as `0.7`), it also warns when any batch holds more than that share of one contrast level's rows. The plan sets `max_share` with its reason; without it the check is unchanged. Every run prints the batch-by-contrast table of row counts, each with its share of the level.
- Missing values (`""`, `NA`, `NaN`, `NULL`, `None`, `<NA>`, any case, so a real level named `None` is left out too) in a check's key columns are left out of that check and reported as a warning.
- Any check may carry an `id` (a nonempty, contract-unique string); otherwise it is `checks[N]`. The id is what a result file and a later verifier cite.
- `unique_key`: `{"kind": "unique_key", "columns": ["sample_id"]}`. Every named column is nonempty (an empty or `NA` value blocks here, unlike the other checks, which leave such rows out) and the combination is unique.

### Declared checks against independent evidence

Three kinds compare the table with a file the plan names. The declared file must come from outside the table and outside the analysis code (a sample sheet, a gene annotation, a crosswalk the lab keeps), never from the table it checks: a list copied from the table passes whatever is wrong with it, and the checker cannot tell. A reference is `{"path": ..., "column": "name"}` (a CSV/TSV/`.h5ad` obs column; optional `"filters"`), `{"path": ..., "header": true}` (the header names; optional `"exclude"`), or `{"path": ..., "lines": true}` (one id per line, `#` comments and blank lines skipped). Contract-level `filters` apply to every check except `h5ad_layer`, including a check on a different `table`: a check on a counts matrix or gene list that lacks the filter's column blocks with "columns absent", so put such filters in the checks of the metadata table (their own `filters`) or use a separate contract. A reference file that is missing or malformed blocks; one that cannot be read is a gap. A check has no subset mode for the reference beyond its own `filters`: a matrix that holds extra samples the analysis drops fails until the reference lists them too. None of these kinds accepts a severity or waiver: unknown keys are usage errors.

- `sample_alignment`: `{"kind": "sample_alignment", "key": "sample_id", "reference": {"path": "samples.tsv", "column": "sample_id"}}`, or `"header_keys": true, "exclude": ["gene"]` when the keys are a matrix's column names. Blocks on empty or repeated keys on either side, a different number of keys, and keys present on one side only. Optional `"agree_on": ["donor"]` also blocks when those columns differ between the table and the reference for the same key. Keys are compared as sets: a different order is not a failure for keyed data. Equal key sets do not prove the analysis uses them correctly: a script that pairs counts and metadata by position instead of by key passes this check. That needs a project test that shuffles the metadata and asserts the result is unchanged (shuffle-invariance), bound to the actual analysis.
- `identifiers`: `{"kind": "identifiers", "column": "gene", "namespace": {"path": "genes.txt", "lines": true}}`. Blocks on empty or repeated identifiers and on identifiers not in the namespace (exact string match; a crosswalk table works through its canonical-id column). Nothing is repaired or renamed. Without a `namespace`, date-like strings (`1-Mar`, `Sep-7`, `2020-03-01`) are a warning ("suspicion, not a verdict": some are legitimate) and the check is always a gap, because identifier validity is unverified; it is never a pass.
- `h5ad_layer`: `{"kind": "h5ad_layer", "table": "x.h5ad", "h5_path": "layers/counts", "properties": {"non_negative": true, "integer_valued": true, "max_at_most": 50000}, "sample_values": 100000}`. The path (`X`, `layers/<name>`, `obsm/<name>`) must exist, or the check blocks. `properties` are optional and bounded: dense arrays are read by leading rows and CSR/CSC matrices by their first stored values, never loaded whole, and at most `sample_values` values are looked at (default 100000). A declared property that a sampled value violates blocks; NaN or infinite values, non-numeric data, or an unrecognised encoding are gaps; a pass that saw only part of the values is a warning that says how many. h5py (and numpy) must be installed, otherwise it is a gap that names the missing reader. This cannot tell which normalization algorithm produced the values (log1p of counts per 10,000 and of counts per million both look alike); a known-answer test of the transformation belongs to the project. It reads neither obs nor the contract's filters.

For all three, a pass means only the stated comparison held.

## 2. Run it

From the project root, stdin form only, so Mycelium's hooks stay closed:

```bash
sh <skill-dir>/../../hooks/py.sh - --contract <(cat <<'EOF'
{"schema": "mycelium-extra.data_contract.v1", "table": "...", "checks": [...]}
EOF
) < <skill-dir>/scripts/data_contract_check.py
```

Output is one line per check (`PASS`, `WARN`, `GAP`, or `BLOCK`, with the rows it ran on), a `note:` line for a declared check naming what passing does not show, then the batch-by-contrast table for a `batch_confounding` check, then its alerts. `--result-json PATH` also writes a machine-readable result (`mycelium-extra.contract_result.v1`) for a verifier or a report: the contract's path and sha256; every input file (`table`, `reference`, `namespace`) with its sha256, or a stated weaker identity (`size+mtime_ns` above 1 GiB, `absent`, `unavailable`); each check's id, kind, status, message and alerts; the exit code, an overall `status`; and for each check `runnable`, which is `ran` or the reason it could not run (`table_missing`, `table_unreadable`, `table_malformed`, `optional_reader_missing`, `columns_absent`, `columns_unreadable`, `no_rows`, `reference_unusable`, `reference_unreadable`, `values_not_judgeable`). A run that could not read a table or a reader is never recorded as a pass, and a warnings-only run (exit 0) keeps every warning. A usage error (exit 1) writes a result with status `error`. The hashes are taken after the checks ran. Write the result file outside the repository until the plan is approved, like the contract. `--json` gives `{"checks": [...], "alerts": [...]}`, with the table as `cross_table` on its check; `--root <dir>` resolves relative table paths from another directory. Exit 0 is clean or warnings only, 2 is blocking, 3 is a gap with nothing blocking, 1 is a malformed contract (bad JSON, unknown kind, missing required key, `max_share` out of range): fix its syntax, never its assumptions. Exit 1 with `mycelium-extra needs Python 3.9 or later` on stderr is `py.sh` finding no suitable Python, not a contract error (set `MYCELIUM_EXTRA_PYTHON`). A missing table or column, or a filter that leaves no rows, is a failed assumption and blocks. A table or column the checker cannot read (an `.h5ad` without h5py, which is an optional reader, a file that is not HDF5, an `obs` encoding it does not recognise) is a gap: the check did not run, so it is neither a pass nor a failure. Running the script by path opens Mycelium's post-action cycle, so never do that.

## 3. Act on the alerts

- **Blocking alert**: report it to the user with its expected, observed, and evidence lines, and what it means for the plan (for example, "20 participants have two acquisitions at the same visit, so a cell-level or row-level test would count them twice"). In grill, it becomes a plan edit the user approves or a `DECISION_REQUIRED`. Do not start the analysis while a blocking alert stands.
- **Never loosen the contract to make it pass** (drop a check, change a threshold, add a filter, switch the unit column) without the user agreeing. That silent adjustment is the failure this skill exists to catch. When the user agrees to a change, re-run and cite both runs.
- **Warning**: list it at the end with its count; it does not stop the plan. A `max_share` warning is the plan's own threshold: quote the batch-by-contrast table with it, so the user sees how unbalanced the design is.
- **Gap**: say which checks did not run and why, and how to close it (install h5py in the environment the check runs in, or export `obs` to a TSV and name that table). A gap never counts as a pass; the plan's rows it would cover stay unverified.
- **Relaxations** (`units_may_span_groups`) are echoed next to their check. Use one only when the plan's design calls for it (a crossover or paired contrast), and name it in the report.
- A check the table cannot answer (a column or table the plan needs is absent, or its filters leave no rows) blocks; report which property is unverified and where it might live.

## 4. Report

One line per check: the kind, the assumption, pass / warn / gap / block, and the observed counts. In grill, a passing contract is `repo` evidence for the plan's rows it covers; cite the table path and the contract's checks. Record the contract with the plan's "Decisions to record" so the executing workflow can re-run it.
