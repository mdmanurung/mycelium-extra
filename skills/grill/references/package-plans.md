# Package plans: seams, test-first rows and independent expectations

Use this file when the task changes a bioinformatics package: the repository has a `DESCRIPTION` (R) or a `pyproject.toml` or `setup.cfg` with a package folder (Python). It adds rows and checks to the plan, never questions beyond the cap. It does not run tests or write code; grill stays read-only.

## Seams

A seam is the public function or method a test calls: an exported R function, or a name in the Python package's public API. Each plan row that changes behaviour names its seam in Choice, for example `aggregate_pseudobulk(): sums counts per donor x cell type`. Prefer an existing seam over a new one, and the highest seam that shows the behaviour. If the right seam is unclear and the user owns the interface, it is one `user` question; otherwise it is a `default:` row naming the seam.

## Test-first rows

Each behaviour row's Validation cell names the test that fails before the change and passes after it, by path: `tests/testthat/test-pseudobulk.R: fails until sums match the hand-computed 2x3 table`. One test per row, written before the code. The red-green loop itself is Pocock's `/mattpocock-skills:tdd` where it is installed; otherwise the repository's runner (`devtools::test()`, `testthat::test_file()`, `pytest`). The test file goes on the plan's `Outputs:` line. A test the user approves as the acceptance check goes in a `validation-bindings` block ([run-plans.md](run-plans.md)), so a later edit to it is caught.

## Independent expectations

An expected value never comes from the code under test, or from recomputing it the same way (`expect_equal(f(x), sum(x))` when `f` is `sum`). Name its source in the Validation cell:

- a literal worked out by hand on a toy input small enough to check on paper;
- a published worked example (a vignette, a paper's table), cited by DOI or URL;
- a reference tool's output on the same toy data (edgeR, limma, DESeq2, scanpy), saved as a fixture with the tool's name and version in the fixture's header.

## Cases a bioinformatics test plan covers

Walk this list; each case that applies is a row or a parked item with a reason.

- **Unit of replication**: a donor-level function gives one value per donor, not per cell.
- **Order**: shuffle samples, cells or genes in the input; the result follows the names, not the positions.
- **Missing levels**: a group, donor or cell type absent from one sample gives `NA` or an error, never a silent zero or a dropped row.
- **Edge sizes**: one donor, one group, a gene with all-zero counts, an empty input.
- **Representations**: a sparse and a dense matrix, or a `SummarizedExperiment` and its count matrix, give the same answer.
- **Seeds**: a stochastic function takes its seed as an argument, and two runs with one seed agree.

## Reproducible tests

Toy data are small, committed under `tests/`, and built by a script kept beside them. Tests read no network and no file outside the repository. A fixture made by another tool records that tool's version. A change to exported behaviour names its `NEWS.md` or `CHANGELOG.md` line and version bump as a plan row.

## Decisions worth an ADR in a package

Exported API shape, the main data container (`SummarizedExperiment`, `SingleCellExperiment`, `AnnData`), S3 versus S4 classes, and a new hard dependency carry lock-in. They qualify when the three tests in [brief-format.md](brief-format.md) "Decisions to record" all hold.

## An analysis that uses a package in development

When an analysis loads the package from a working copy (`pip install -e`, `devtools::load_all()`), list that copy in `gate.json`'s `dev_packages`, so each run receipt records the package's commit and whether it had uncommitted changes.
