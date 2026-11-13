# @@FILE@@: step @@NUM@@ of @@NAME@@, the figure step.
# Purpose: [One sentence: what this figure shows and the claim it carries.]
# Run:     Rscript @@PATH@@ @@USAGE@@   (the Snakefile passes these paths)
# Inputs:  @@INPUT@@ [producer or [gap]]
# Outputs: @@DIR@@/figures/@@STEM@@.png and .pdf, @@DIR@@/source_data/@@STEM@@.tsv (same stem: the table holds what the figure draws)
# scilintr stage: replace this line with `# STAGE: <stage>` (blind_qc, selection, evaluation or library;
#   label columns are allowed only in evaluation) so its label and stage rules run on this file.

suppressPackageStartupMessages({
  library(dplyr)
  library(ggplot2)
  library(readr)
})

# Parameters -------------------------------------------------------------------
# Values a reader may change, UPPER_SNAKE, with the reason beside each. Delete the block if there are none.
SEED <- 0 # every stochastic step below uses this

# Arguments --------------------------------------------------------------------
args <- commandArgs(trailingOnly = TRUE)
stopifnot("the Snakefile passes @@NARGS@@ path argument(s)" = length(args) == @@NARGS@@)
@@ARGS_CODE@@
source("code/theme.R") # the theme, PALETTE, scale_colour_label(), save_panel()
set.seed(SEED)

# Plot frame -------------------------------------------------------------------
# One row per donor with a `label` that is a name in PALETTE; the figure plots this table and nothing else.
# Name one check where tables meet, e.g.
# stopifnot("meta rows match counts" = identical(meta$id, colnames(counts)))
stop("@@FILE@@ is not written yet")
plotted <- tibble(donor = character(), label = character(), value = numeric())

dir.create(file.path(step_dir, "source_data"), recursive = TRUE, showWarnings = FALSE)
write_tsv(plotted, file.path(step_dir, "source_data", "@@STEM@@.tsv"))

# Figure -----------------------------------------------------------------------
# Donors are the points; the summary (mean +/- SD) is named in the caption.
p <- ggplot(plotted, aes(x = label, y = value, colour = label)) +
  geom_jitter(position = position_jitter(width = 0.1, height = 0, seed = 1)) +
  stat_summary(fun.data = mean_sdl, fun.args = list(mult = 1), colour = "black") +
  scale_colour_label(plotted$label) +
  labs(x = NULL, y = "[value, unit]", caption = "Points: donors. Bar: mean +/- SD.")

save_panel(p, step_dir, "@@STEM@@")

# Session info -----------------------------------------------------------------
dir.create(file.path(step_dir, "logs"), recursive = TRUE, showWarnings = FALSE)
writeLines(capture.output(sessionInfo()), file.path(step_dir, "logs", "@@STEM@@.session.txt"))
