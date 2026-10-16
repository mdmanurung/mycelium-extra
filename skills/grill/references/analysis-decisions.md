# Analysis decision points

A coverage list, not a question list. For each point that applies, the plan must record the choice and its source: `repo: <path>`, `user`, or `default: <reason>`. Most points should resolve from the repository or a stated default; ask only under the gate in `SKILL.md`. Skip points that do not apply.

| Decision point | Settle | Where evidence usually lives |
| --- | --- | --- |
| Estimand and claim type | Exploratory, predictive, or causal; the exact contrast and direction; the population the claim covers | Analysis doc, `specification.md`, decisions |
| Unit of replication | Donor, sample, or cell as the test unit; pseudobulk or mixed model versus cell-level tests; paired or repeated structure | Metadata schema, prior decisions, existing model code |
| Cohort and exclusions | Inclusion rules; excluded samples and why; pre-specified or data-derived | `DATA_MANIFEST.md`, `data/metadata/*/provenance.md`, decisions |
| Input and matrix state | Which file or object; `X` versus `layers`/`raw`/assay; counts, normalized, log, or scaled at each downstream call | Data manifest, loading code, a single inline probe |
| Reference and identifiers | Genome and annotation build; gene ID type (Ensembl or symbol); species mapping; marker or gene-set source and version | Ingest provenance, config, learnings |
| QC thresholds | Genes, counts, mitochondrial fraction, doublets, ambient RNA; for cytometry, gating and debris or dead-cell rules; their origin | Analysis doc, config, learnings, active conventions |
| Normalization and transformation | Method, and whether every arm or batch gets the same treatment | Pipeline code, conventions |
| Batch versus biology | Whether batch or site is confounded with the contrast; whether integration or correction could remove the signal; batch-aware alternatives | Metadata cross-tabs, decisions, prior reviews |
| Annotation | Label source, resolution, reference; whether labels were derived from the same data that is then tested | Annotation code, findings, decisions |
| Model or test | Why this family; assumptions and how they are checked; covariates and why (no colliders or mediators) | Model code, statistical conventions |
| Multiplicity | Number of tests; correction method and scope (per cell type, global); pre-specified versus post hoc subgroups | Decisions, conventions |
| Leakage and circularity | Selection or feature choice on the evaluation data; clustering then testing on the same cells; train/test split by subject | Code, prior reviews |
| Validation and sensitivity | Which choices get a sensitivity run; null or permutation checks; the result that would change the conclusion | Active robust-analysis conventions, analysis doc |
| Outputs and reporting | Deliverable (figure, table, report); values a report will cite; n, uncertainty, and units in figures | Analysis doc, `numbers.json`, report conventions |

## Declaring a data check in the plan

When a row above rests on a property of a table or file, record it as a `data-contract-check` check, with its evidence named in the plan's "Decisions to record" and the independent source (`repo: <path>`) it compares against. The checker only compares what the plan declares and cannot confirm the source is independent. Example for "Reference and identifiers" and "Unit of replication":

```json
{"kind": "identifiers", "column": "gene", "namespace": {"path": "data/metadata/<dataset>/gene_annotation.tsv", "column": "symbol"}}
{"kind": "sample_alignment", "key": "sample_id", "reference": {"path": "data/metadata/<dataset>/sample_sheet.tsv", "column": "sample_id"}}
{"kind": "h5ad_layer", "table": "data/processed/<dataset>/cells.h5ad", "h5_path": "layers/counts", "properties": {"non_negative": true, "integer_valued": true}}
```

A passing key or identifier check does not show the analysis joins by key (needs a shuffle-invariance test in the project) or that a normalization is the planned one (needs a known-answer test). Say which of those the plan still covers by hand.
