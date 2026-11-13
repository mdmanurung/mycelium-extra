"""@@FILE@@: step @@NUM@@ of @@NAME@@, the figure step.

Purpose: [One sentence: what this figure shows and the claim it carries.]
Run:     python @@PATH@@ @@USAGE@@   (the Snakefile passes these paths)
Inputs:  @@INPUT@@ [producer or [gap]]
Outputs: @@DIR@@/figures/@@STEM@@.png and .pdf, @@DIR@@/source_data/@@STEM@@.tsv (same stem: the table holds what the figure draws)
"""

import sys
from importlib.metadata import version
from pathlib import Path

import pandas as pd
from plotnine import aes, geom_jitter, ggplot, labs, position_jitter, scale_colour_manual, stat_summary

sys.path.insert(0, "code")
from theme import palette_for, save_panel  # noqa: E402  the theme, PALETTE, save_panel()

# Parameters -------------------------------------------------------------------
# Values a reader may change, UPPER_SNAKE, with the reason beside each. Delete the block if there are none.
SEED = 0  # pass to every RNG, e.g. np.random.default_rng(SEED)
PACKAGES = ["pandas", "plotnine"]  # every package this script imports, for the session note at the end

# Arguments --------------------------------------------------------------------
@@ARGS_CODE@@

# Plot frame -------------------------------------------------------------------
# One row per donor with a `label` that is a name in PALETTE; the figure plots this table and nothing else.
# Name one check where tables meet, e.g.
# if list(meta["id"]) != list(counts.columns):
#     raise ValueError("meta rows do not match counts")
raise SystemExit("@@FILE@@ is not written yet")
plotted = pd.DataFrame({"donor": [], "label": [], "value": []})

(Path(step_dir) / "source_data").mkdir(parents=True, exist_ok=True)
plotted.to_csv(Path(step_dir) / "source_data" / "@@STEM@@.tsv", sep="\t", index=False)

# Figure -----------------------------------------------------------------------
# Donors are the points; the summary (mean +/- SD) is named in the caption.
p = (
    ggplot(plotted, aes(x="label", y="value", colour="label"))
    + geom_jitter(position=position_jitter(width=0.1, height=0, random_state=1))
    + stat_summary(fun_data="mean_sdl", fun_args={"mult": 1}, colour="black")
    + scale_colour_manual(values=palette_for(plotted["label"]))
    + labs(x="", y="[value, unit]", caption="Points: donors. Bar: mean +/- SD.")
)
save_panel(p, step_dir, "@@STEM@@")

# Session info -----------------------------------------------------------------
# A script that uses scanpy writes sc.logging.print_versions() here instead.
(Path(step_dir) / "logs").mkdir(exist_ok=True)
notes = [f"python {sys.version.split()[0]}"] + [f"{name} {version(name)}" for name in PACKAGES]
(Path(step_dir) / "logs" / "@@STEM@@.session.txt").write_text("\n".join(notes) + "\n")
