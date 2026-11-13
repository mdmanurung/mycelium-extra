"""Purpose: a leftover step. Run: python code/07_orphan.py"""

import pandas as pd

table = pd.read_csv("data/meta.tsv", sep="\t")
print(len(table))
