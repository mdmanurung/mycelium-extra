# @@FILE@@: step @@NUM@@ of @@NAME@@, the figure step. [The one claim this figure carries.]
# Input:  @@INPUT@@
# Output: @@DIR@@/figures/@@STEM@@.png and .pdf, @@DIR@@/source_data/@@STEM@@.tsv (same stem: the table holds what the figure draws)
# Run:    Rscript @@PATH@@ @@USAGE@@   (the Snakefile passes these paths)
# scilintr stage: replace this line with `# STAGE: <stage>` (blind_qc, selection, evaluation or library;
#   label columns are allowed only in evaluation) so its label and stage rules run on this file.

suppressPackageStartupMessages({
  library(dplyr)
  library(ggplot2)
  library(readr)
})

args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == @@NARGS@@)
@@ARGS_CODE@@
source("code/theme.R") # theme_pubr(base_size = 8), PALETTE, save_panel()
set.seed(0)

# Plot frame ------------------------------------------------------------------
# One row per donor with a `label` that is a name in PALETTE; the figure plots this table and nothing else.
stop("@@FILE@@ is not written yet")
plotted <- tibble(donor = character(), label = character(), value = numeric())

dir.create(file.path(step_dir, "source_data"), recursive = TRUE, showWarnings = FALSE)
write_tsv(plotted, file.path(step_dir, "source_data", "@@STEM@@.tsv"))

# Figure ----------------------------------------------------------------------
# Donors are the points; the summary (mean +/- SD) is named in the caption.
p <- ggplot(plotted, aes(x = label, y = value, colour = label)) +
  geom_jitter(position = position_jitter(width = 0.1, height = 0, seed = 1)) +
  stat_summary(fun.data = mean_sdl, fun.args = list(mult = 1), colour = "black") +
  scale_colour_label(plotted$label) +
  labs(x = NULL, y = "[value, unit]", caption = "Points: donors. Bar: mean +/- SD.")

save_panel(p, step_dir, "@@STEM@@")
