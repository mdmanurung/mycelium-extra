**Objective.** Test whether the day 28 minus day 0 change in gene expression differs between vaccine and placebo arms (reference: placebo; positive log2FC means higher in vaccine).

Inputs: data/processed/vaccine-cohort/sample_metadata.tsv data/processed/vaccine-cohort/counts.tsv
Outputs: analysis/vaccine-response/outputs/samples_used.tsv analysis/vaccine-response/outputs/de_results.tsv analysis/vaccine-response/outputs/summary.tsv

| # | Step | Choice | Source | Validation |
|---|---|---|---|---|
| 1 | run `analysis/vaccine-response/scripts/01_select_samples.py` | keep preferred_acquisition == TRUE | repo: .living/decisions.md | 24 rows, 12 donors x 2 visits |
| 2 | run `analysis/vaccine-response/scripts/02_paired_test.py` | median-of-ratios; exact permutation; BH 0.05 | repo: .living/decisions.md | sample IDs identical across tables |
| 3 | run `analysis/vaccine-response/scripts/03_summary.R` | hits at padj < 0.05 | default: matches step 2 | summary row count 1 |

Plan status: READY
