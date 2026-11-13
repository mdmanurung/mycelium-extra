"""Write the design facts a patsy/numpy-style fit used, for recipe R5.

Run: from extract_design import extract_design; call it once after the fit.
Inputs: the design matrix (a patsy DesignMatrix, or an array with `columns`), the contrast
as a dict of design column name to weight, the formula, the sample table file the fit read.
Outputs: one JSON file, mycelium-extra.fit_design.v1 (read by method_fidelity.py).
"""
import hashlib
import json
from pathlib import Path


def extract_design(design, contrast, formula, sample_table_path, out_path, columns=None, coefficient=None):
    # patsy keeps the names on design_info; a bare array needs `columns`.
    names = columns if columns is not None else design.design_info.column_names
    # Rows as plain lists so the JSON is a matrix, not a named object.
    rows = [[float(v) for v in row] for row in design]
    record = {
        "schema": "mycelium-extra.fit_design.v1",
        "formula": str(formula),
        "design_columns": list(names),
        "design": rows,
        "coefficient": coefficient,
        "contrast": {name: float(w) for name, w in contrast.items() if w != 0},
        "sample_table_sha256": hashlib.sha256(Path(sample_table_path).read_bytes()).hexdigest(),
    }
    Path(out_path).write_text(json.dumps(record, indent=2) + "\n")
