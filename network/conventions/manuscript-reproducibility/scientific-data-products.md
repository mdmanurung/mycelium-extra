# Scientific data-product contracts

Explicitly name the scale of each matrix/table and primary indexing keys. Record how each data product was computed and from which version of data/annotation/reference.

| Product | Required declaration | Objective sanity check | Scientific caveat |
|---|---|---|---|
| Sample metadata | sample ID; resolved donor ID; condition; visit; batch; exclusions | unique sample key; matched IDs; no duplicate resolved units in design strata | matching keys does not establish pairing, independence or estimability |
| Pseudobulk DE input | raw integer gene-count sums per sample × cell type | nonnegative integer values; manual sum on fixture; gene/sample identity | normalized expression must never become DESeq2 raw counts |
| Normalized expression | transformation, normalization denominator, assay/layer name | numeric finite; mark scale | `log2(a/b)` invalid for signed CLR and inappropriate for already log NPX |
| Cell-type composition | numerator count; all-retained or alternative denominator; zero-completion and pseudocount policy | count ≤ denominator; finite 0–1 fraction; zero policy | composition differences not absolute abundance |
| Annotation | labels/review rules; reference model identity/weights; exclusions/reasons | duplicate-rule detection; unknown label check; deterministic rule precedence | expert decisions are not validated by lint |
| Latent factor | factor loading version; gene order/intersection; normalization; projection method | input feature alignment; deterministic identity checks | a latent score is estimated, not an error-free direct measurement |
| Model result | outcome; estimand; model formula; contrast direction; covariate nesting; multiplicity | matches approved declared expectation (recorded fidelity) | metadata-only comparison cannot authenticate actual fitted model |
| Figure source data | exact plotted variables, groups, numerical intervals, transformations | declared columns exist, values finite, script/output traceable | declared columns may omit actual aesthetics; inspect code separately |

Under a real approved plan use Mycelium Extra's `data-contract-check` for sample-level replication and batch structure and `verify/scripts/method_fidelity.py` for declared versus recorded model-field agreement. The shipped supplementary validator checks some table/figure contracts only; it is NOT a replacement for either existing check.
