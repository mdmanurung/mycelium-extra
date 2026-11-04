"""theme.py: the house plot style, imported by every figure script (sys.path holds code/).

Purpose: one theme, one palette and one export size for every figure of this analysis; the plotnine
         counterpart of theme.R (theme_pubr, base_size 8).
Run:     imported, not run. Needs plotnine.
Outputs: save_panel() writes <run>/figures/<stem>.pdf and .png at 89 x 70 mm.
"""

from pathlib import Path

from plotnine import element_text, theme, theme_classic, theme_set

# Parameters ------------------------------------------------------------------
# One colour per label, keyed by the label as it appears in the data. Add every label you plot.
PALETTE = {"control": "#6E6E6E", "treated": "#C8553D"}

# Theme -----------------------------------------------------------------------
theme_set(theme_classic(base_size=8) + theme(legend_position="top", plot_caption=element_text(ha="left")))


# Palette ---------------------------------------------------------------------
# Fail on a label the palette does not name, so no group falls back to a default colour.
def palette_for(labels):
    labels = list(dict.fromkeys(str(label) for label in labels))
    unknown = [label for label in labels if label not in PALETTE]
    if unknown:
        raise ValueError(f"labels not in PALETTE (code/theme.py): {', '.join(unknown)}")
    return {label: PALETTE[label] for label in labels}


# Export ----------------------------------------------------------------------
# PDF for the manuscript and PNG for the report, same size, same stem.
def save_panel(p, run, stem, width=89, height=70):
    folder = Path(run) / "figures"
    folder.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        p.save(folder / f"{stem}.{ext}", width=width, height=height, units="mm", dpi=300, verbose=False)
