"""01_calc.py: step 01 of tables_only, a tiny working script for tests/e2e_real.py.

Input:  none (synthetic)
Output: outputs/01_calc/01_calc.parquet
Run:    python code/01_calc.py outputs/01_calc/01_calc.parquet   (the Snakefile passes this path)
"""

import sys

import pandas as pd

(output_path,) = sys.argv[1:]
pd.DataFrame({"donor": ["d1", "d2", "d3"], "value": [1.0, 2.0, 3.0]}).to_parquet(output_path)
