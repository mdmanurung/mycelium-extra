"""@@FILE@@: manuscript panel @@PANEL@@ of @@NAME@@. [The one claim this panel carries.]

Inputs:  [each file it reads, with the script that produced it, or [gap]]
Outputs: <run>/source_data/@@PANEL@@.tsv, <run>/figures/@@PANEL@@.pdf and .png
Run:     python @@PATH@@ <run dir>   # from the repository root
Release: point @@DEST@@/outputs/current at the run; config/figure_map.tsv and
         config/manuscript_checks.json name the files under it, and manuscript-audit checks them.
"""

import sys
from pathlib import Path

import pandas as pd
from plotnine import aes, geom_jitter, ggplot, labs, position_jitter, scale_colour_manual, stat_summary

sys.path.insert(0, "@@DEST@@/code")
from theme import palette_for, save_panel  # noqa: E402  theme_pubr-like base_size 8, PALETTE, save_panel()

(run,) = sys.argv[1:]
source_path = Path(run) / "source_data" / "@@PANEL@@.tsv"
source_path.parent.mkdir(parents=True, exist_ok=True)

# ---- 1. Export: the values the panel draws, after every aggregation ----
plotted = pd.DataFrame(
    {
        "donor": ["d1", "d2", "d3", "d4", "d5", "d6"],
        "label": ["control", "control", "control", "treated", "treated", "treated"],
        "y": [2, 3, 2.5, 4, 5, 4.5],
    }
)  # replace with the real computation
plotted.to_csv(source_path, sep="\t", index=False)
del plotted

# ---- 2. Render from the exported table alone, so the released source data can redraw the panel ----
# Donors are the points; the summary (mean +/- SD) is named in the caption.
plotted = pd.read_csv(source_path, sep="\t")
p = (
    ggplot(plotted, aes(x="label", y="y", colour="label"))
    + geom_jitter(position=position_jitter(width=0.1, height=0, random_state=1))
    + stat_summary(fun_data="mean_sdl", fun_args={"mult": 1}, colour="black")
    + scale_colour_manual(values=palette_for(plotted["label"]))
    + labs(x="", y="[y, unit]", caption="Points: donors. Bar: mean +/- SD.")
)
save_panel(p, run, "@@PANEL@@")
