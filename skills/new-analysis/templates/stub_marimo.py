# /// script
# requires-python = ">=3.10"
# dependencies = ["marimo", "pandas", "pyarrow"]
# ///
"""@@FILE@@: step @@NUM@@ of @@NAME@@, a marimo notebook.

Purpose: [what this step shows, in one sentence]
Run:     python @@PATH@@   (the Snakefile runs it headless from the analysis folder)
         marimo edit @@PATH@@   (to work in it)
Inputs:  @@INPUT@@ [producer: the step before, or the data link]
Outputs: @@OUTPUT@@ [what it holds]

Cell rules: every top-level name is unique across cells; `mo` comes from the setup cell;
every cell is named; a markdown cell before a code cell says the intent, one after it the result.
"""

import marimo

app = marimo.App(width="medium")

with app.setup:
    # Parameters a reader may change, each with its reason.
    import os
    from pathlib import Path

    import marimo as mo
    import pandas as pd

    SEED = 0  # pass to every RNG, e.g. np.random.default_rng(SEED)
    STEP = Path(os.environ["STEP_DIR"])  # this step's folder, outputs/@@STEM@@, set by the Snakefile
    OUTPUTS = Path(os.environ["OUTPUTS"])  # outputs/, to read earlier steps
    INPUT = @@INPUT_PY@@
    OUTPUT = @@OUTPUT_PY@@


@app.cell(hide_code=True)
def intro():
    mo.md(
        """
        # @@FILE@@

        Step @@NUM@@ of @@NAME@@. Reads the table the step before wrote; it computes nothing that a figure needs refitted.
        """
    )
    return


@app.cell
def load():
    if not INPUT.exists():
        raise FileNotFoundError(INPUT)
    raise NotImplementedError("@@FILE@@ is not written yet")
    return


if __name__ == "__main__":
    app.run()
