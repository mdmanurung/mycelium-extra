"""@@FILE@@: manuscript panel @@PANEL@@ of @@NAME@@. [The one claim this panel carries.]

Inputs:  [each file it reads, with the script that produced it, or [gap]]
Outputs: <run>/source_data/@@PANEL@@.tsv, <run>/figures/@@PANEL@@.pdf
Run:     python @@PATH@@ <run dir>   # from the repository root
Release: point @@DEST@@/outputs/current at the run; config/figure_map.tsv and
         config/manuscript_checks.json name the files under it, and manuscript-audit checks them.
"""

import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

(run,) = sys.argv[1:]
for folder in ("source_data", "figures"):
    os.makedirs(os.path.join(run, folder), exist_ok=True)
source_path = os.path.join(run, "source_data", "@@PANEL@@.tsv")

# ---- 1. Export: the values the panel draws, after every aggregation ----
plotted = [{"x": 1, "y": 2}, {"x": 2, "y": 4}, {"x": 3, "y": 3}]  # replace with the real computation
with open(source_path, "w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=["x", "y"], delimiter="\t")
    writer.writeheader()
    writer.writerows(plotted)
del plotted

# ---- 2. Render from the exported table alone, so the released source data can redraw the panel ----
with open(source_path, newline="") as handle:
    plotted = list(csv.DictReader(handle, delimiter="\t"))
figure, axis = plt.subplots(figsize=(60 / 25.4, 60 / 25.4))
axis.scatter([float(r["x"]) for r in plotted], [float(r["y"]) for r in plotted])
axis.set_xlabel("x")
axis.set_ylabel("y")
figure.savefig(os.path.join(run, "figures", "@@PANEL@@.pdf"))
