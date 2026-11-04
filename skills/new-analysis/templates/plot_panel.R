# @@FILE@@: manuscript panel @@PANEL@@ of @@NAME@@. [The one claim this panel carries.]
# Inputs:  [each file it reads, with the script that produced it, or [gap]]
# Outputs: <run>/source_data/@@PANEL@@.tsv, <run>/figures/@@PANEL@@.pdf and .png
# Run:     Rscript @@PATH@@ <run dir>   # from the repository root
# Release: point @@DEST@@/outputs/current at the run; config/figure_map.tsv and
#          config/manuscript_checks.json name the files under it, and manuscript-audit checks them.

suppressPackageStartupMessages({
  library(ggplot2)
  library(readr)
})

args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 1L)
run <- args[[1L]]
source("@@DEST@@/code/theme.R") # theme_pubr(base_size = 8), PALETTE, save_panel()
dir.create(file.path(run, "source_data"), recursive = TRUE, showWarnings = FALSE)
source_path <- file.path(run, "source_data", "@@PANEL@@.tsv")

# ---- 1. Export: the values the panel draws, after every aggregation ----
plotted <- tibble::tibble(
  donor = c("d1", "d2", "d3", "d4", "d5", "d6"),
  label = c("control", "control", "control", "treated", "treated", "treated"),
  y = c(2, 3, 2.5, 4, 5, 4.5)
) # replace with the real computation
write_tsv(plotted, source_path)
rm(plotted)

# ---- 2. Render from the exported table alone, so the released source data can redraw the panel ----
# Donors are the points; the summary (mean +/- SD) is named in the caption.
plotted <- read_tsv(source_path, show_col_types = FALSE)
p <- ggplot(plotted, aes(x = label, y = y, colour = label)) +
  geom_jitter(position = position_jitter(width = 0.1, height = 0, seed = 1)) +
  stat_summary(fun.data = mean_sdl, fun.args = list(mult = 1), colour = "black") +
  scale_colour_label(plotted$label) +
  labs(x = NULL, y = "[y, unit]", caption = "Points: donors. Bar: mean +/- SD.")
save_panel(p, run, "@@PANEL@@")
