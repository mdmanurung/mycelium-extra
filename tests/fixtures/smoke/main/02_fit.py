"""02_fit.py: step 02 of smoke, a tiny working script for tests/e2e_real.py.

Input:  outputs/01_scan/01_scan.tsv
Output: outputs/02_fit/02_fit.tsv
Run:    python code/02_fit.py outputs/01_scan/01_scan.tsv outputs/02_fit/02_fit.tsv   (the Snakefile passes these paths)
"""

import csv
import sys

FACTOR = 2  # the "fit": every value is multiplied by this
input_path, output_path = sys.argv[1:]

with open(input_path, newline="") as handle:
    rows = list(csv.DictReader(handle, delimiter="\t"))
with open(output_path, "w", newline="") as handle:
    writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
    writer.writerow(["donor", "label", "fit"])
    for row in rows:
        writer.writerow([row["donor"], row["label"], float(row["value"]) * FACTOR])
