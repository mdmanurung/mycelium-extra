"""@@FILE@@: step @@NUM@@ of @@NAME@@, the figure step. [The one claim this figure carries.]

Input:  @@INPUT@@
Output: @@DIR@@/figures/@@STEM@@.png and .pdf, @@DIR@@/source_data/@@STEM@@.tsv (same stem: the table holds what the figure draws)
Run:    python @@PATH@@ @@USAGE@@   (the Snakefile passes these paths)
"""

import sys
from pathlib import Path

import pandas as pd
from plotnine import aes, geom_jitter, ggplot, labs, position_jitter, scale_colour_manual, stat_summary

sys.path.insert(0, "code")
from theme import palette_for, save_panel  # noqa: E402  theme_pubr-like base_size 8, PALETTE, save_panel()

@@ARGS_CODE@@
SEED = 0  # pass to every RNG, e.g. np.random.default_rng(SEED)

# Plot frame ------------------------------------------------------------------
# One row per donor with a `label` that is a name in PALETTE; the figure plots this table and nothing else.
raise SystemExit("@@FILE@@ is not written yet")
plotted = pd.DataFrame({"donor": [], "label": [], "value": []})

(Path(step_dir) / "source_data").mkdir(parents=True, exist_ok=True)
plotted.to_csv(Path(step_dir) / "source_data" / "@@STEM@@.tsv", sep="\t", index=False)

# Figure ----------------------------------------------------------------------
# Donors are the points; the summary (mean +/- SD) is named in the caption.
p = (
    ggplot(plotted, aes(x="label", y="value", colour="label"))
    + geom_jitter(position=position_jitter(width=0.1, height=0, random_state=1))
    + stat_summary(fun_data="mean_sdl", fun_args={"mult": 1}, colour="black")
    + scale_colour_manual(values=palette_for(plotted["label"]))
    + labs(x="", y="[value, unit]", caption="Points: donors. Bar: mean +/- SD.")
)
save_panel(p, step_dir, "@@STEM@@")
