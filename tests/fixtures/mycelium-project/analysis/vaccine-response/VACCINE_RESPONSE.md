# vaccine-response

SIMULATED data. Does the day 28 minus day 0 change in gene expression differ between the vaccine
and placebo arms? Reference: placebo; a positive log2FC means higher in vaccine.

## Steps

1. `scripts/01_select_samples.py`: keep `preferred_acquisition == TRUE` (decision 2026-04-01);
   writes `outputs/samples_used.tsv`.
2. `scripts/02_paired_test.py`: join counts by `sample_id`, median-of-ratios size factors
   (decision 2026-03-02, confirmed 2026-07-15), per-donor day 28 minus day 0 difference of
   log2(normalised + 1), vaccine mean minus placebo mean, exact two-sided permutation over all
   924 arm labellings, BH; writes `outputs/de_results.tsv`.
3. `scripts/03_summary.R`: hit count and median log2FC of the hits; writes `outputs/summary.tsv`.

`run.sh`, `Snakefile` and `run_all.sbatch` run the same three steps.

## Key Findings

<!-- key-findings:start (written by tests/fixtures/make_fixture_data.py) -->
- 8 of 60 genes are at padj < 0.05 (BH), all with positive log2FC (a larger day 28 minus day 0 change in vaccine than in placebo) [agent-derived: `outputs/summary.tsv`].
- Hits: IFI27, IFI44L, IFIT1, ISG15, MX1, OAS1, RSAD2, SIGLEC1 [agent-derived: `outputs/de_results.tsv`].
- Median log2FC of the hits: 1.6806; range 1.4455 to 2.2219 [agent-derived: `outputs/summary.tsv`].
- Smallest p: 0.002165 (the permutation floor, 2 of 924 labellings); largest padj among the hits: 0.016234 [agent-derived: `outputs/de_results.tsv`].
- 24 libraries from 12 donors (6 vaccine, 6 placebo) after removing D03_day28_rerun [agent-derived: `outputs/samples_used.tsv`].

<!-- claims
8 | outputs/summary.tsv n_hits
60 | outputs/summary.tsv n_tested
1.6806 | outputs/summary.tsv median_log2fc_hits
1.4455 | outputs/de_results.tsv log2fc MX1
2.2219 | outputs/de_results.tsv log2fc OAS1
0.002165 | outputs/de_results.tsv p IFI27
0.016234 | outputs/de_results.tsv padj SIGLEC1
24 | outputs/samples_used.tsv rows
-->
<!-- key-findings:end -->
