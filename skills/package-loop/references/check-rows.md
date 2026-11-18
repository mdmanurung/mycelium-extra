# Check commands and the rows to ask

Every row here is the user's. Show the forms as a list of what exists, with no recommended value, and write nothing into the tree until the user approves.

## Run command forms

| Package | Forms in use |
|---|---|
| R | `Rscript -e 'devtools::check()'`, `R CMD build . && R CMD check --no-manual pkg_*.tar.gz`, `Rscript -e 'testthat::test_local()'` for tests only |
| Python | `pytest -q`, `pytest -q && ruff check .` |

Which one is a plan row because they check different things: `R CMD check` also runs examples, the vignette build and the documentation checks. Offer a source only for a form the repository already uses (its CI file, `README`, `Makefile`).

## Which NOTEs fail

Run the check once on the starting commit and list its NOTE headings (`check_summary.py --notes`). Ask which headings count as failures. A NOTE about a new dependency or an undefined global differs from one about the system clock or the package size. A package that goes to CRAN or Bioconductor has its own rule for NOTEs: cite it if the user names the target.

## Readout parts

| Part | Where it comes from |
|---|---|
| `ERROR`, `WARNING`, `NOTE` counts | `R CMD check` or `devtools::check()` output |
| `failed`, `passed`, `errors` counts | the pytest summary line |
| `ruff: N errors` | the `ruff check` summary |

`check_summary.py` prints counts only. The row says which count, or which combination, makes a node `better`, `same` or `worse`.
