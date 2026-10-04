# Test fixtures

`mycelium-project/` is a small, SIMULATED Mycelium project used by the end-to-end tests
(`tests/test_end_to_end.py`, design in `docs/design/c1-fixture-project.md`). It follows the layout
of Mycelium 0.8.1 (`skills/core/references/folder-structure.md`).

The repository commits only the project's content. File times, git history, approvals, receipts,
and the data-lineage manifest are built by `tests/e2e/harness.py` on every run, in a temporary copy.

## The data

12 donors (D01 to D06 vaccine, D07 to D12 placebo) at `day0` and `day28`, plus a re-sequenced
library `D03_day28_rerun` with `preferred_acquisition=FALSE`; 60 genes with real HGNC symbols, of
which 8 interferon-response genes are up 4-fold at day 28 in the vaccine arm only. The ground truth
is in `tests/e2e/expected/truth.json`, outside the project, so no analysis step can read it.

## Regenerating

    python3 tests/fixtures/make_fixture_data.py            # seed 0
    python3 tests/fixtures/make_fixture_data.py --check    # compare, write nothing

The generator writes the two TSVs, the Key Findings block of `VACCINE_RESPONSE.md`, and
`tests/e2e/expected/{truth.json,baseline.json,summary.tsv}`. It refuses a seed unless
median-of-ratios recovers exactly the 8 true genes at padj < 0.05 and total-count CPM gives at
least 3 false positives; seeds 0, 1, 5, 16 and 25 pass. `tests/test_fixture_data.py` runs
`--check`, so a hand edit to the data fails the suite. Change the data through the generator only.

`expected/summary.tsv` comes from the generator's Python twin of `03_summary.R`; the end-to-end
test compares it with the real R output when `Rscript` is on `PATH`.

## Size budget

Under 40 files and 200 KB for `mycelium-project/`, so a reviewer can read all of it.
`tests/test_fixture_data.py` enforces the budget.
