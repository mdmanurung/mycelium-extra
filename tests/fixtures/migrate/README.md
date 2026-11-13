# migrate fixtures

`trim-hto/` is a trimmed copy of the structure of a real run-folder analysis (the Snakefile of
`04-timepoint-hto`): `RUN`/`OUT`/`BASE` block, a batch-wildcard step whose folder (`01b_scar`)
differs from its script stem (`01b_scar-denoise`), `BASE` reads, two qmd steps that render to
`reports/site/`, an old-style `run.sh`, a website `_quarto.yml`, scripts in `code/` with cross-step
reads, and two run folders with `RUN.txt`. `gitignore.txt` is the analysis's `.gitignore` (named so
here, because a real one would hide the fixture's outputs from this repository). Tests copy the
folder; nothing runs it.
