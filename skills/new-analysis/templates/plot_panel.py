"""@@FILE@@: manuscript panel @@PANEL@@ of @@NAME@@.

Purpose: [The one claim this panel carries.]
Run:     python @@PATH@@ <panels dir>   # from the repository root
Inputs:  [each file it reads, with the script that produced it, or [gap]]
Outputs: <panels dir>/source_data/@@PANEL@@.tsv, <panels dir>/figures/@@PANEL@@.pdf and .png
Release: config/figure_map.tsv and config/manuscript_checks.json name the files under the panels dir,
         and manuscript-audit checks them.
"""

import sys
from importlib.metadata import version
from pathlib import Path

import pandas as pd
from plotnine import aes, geom_jitter, ggplot, labs, position_jitter, scale_colour_manual, stat_summary

sys.path.insert(0, "@@DEST@@/code")
from theme import palette_for, save_panel  # noqa: E402  the theme, PALETTE, save_panel()

# Parameters -------------------------------------------------------------------
# Values a reader may change, UPPER_SNAKE, with the reason beside each. Delete the block if there are none.
SEED = 1  # jitter position, so the panel redraws the same
PACKAGES = ["pandas", "plotnine"]  # every package this script imports, for the session note at the end

# Arguments --------------------------------------------------------------------
(panels_dir,) = sys.argv[1:]
source_path = Path(panels_dir) / "source_data" / "@@PANEL@@.tsv"
source_path.parent.mkdir(parents=True, exist_ok=True)

# Export -----------------------------------------------------------------------
# The values the panel draws, after every aggregation.
plotted = pd.DataFrame(
    {
        "donor": ["d1", "d2", "d3", "d4", "d5", "d6"],
        "label": ["control", "control", "control", "treated", "treated", "treated"],
        "y": [2, 3, 2.5, 4, 5, 4.5],
    }
)  # replace with the real computation
plotted.to_csv(source_path, sep="\t", index=False)
del plotted

# Render -----------------------------------------------------------------------
# Draw from the exported table alone, so the released source data can redraw the panel.
# Donors are the points; the summary (mean +/- SD) is named in the caption.
plotted = pd.read_csv(source_path, sep="\t")
p = (
    ggplot(plotted, aes(x="label", y="y", colour="label"))
    + geom_jitter(position=position_jitter(width=0.1, height=0, random_state=SEED))
    + stat_summary(fun_data="mean_sdl", fun_args={"mult": 1}, colour="black")
    + scale_colour_manual(values=palette_for(plotted["label"]))
    + labs(x="", y="[y, unit]", caption="Points: donors. Bar: mean +/- SD.")
)
save_panel(p, panels_dir, "@@PANEL@@")

# Session info -----------------------------------------------------------------
# A script that uses scanpy writes sc.logging.print_versions() here instead.
(Path(panels_dir) / "logs").mkdir(exist_ok=True)
notes = [f"python {sys.version.split()[0]}"] + [f"{name} {version(name)}" for name in PACKAGES]
(Path(panels_dir) / "logs" / "@@PANEL@@.session.txt").write_text("\n".join(notes) + "\n")
