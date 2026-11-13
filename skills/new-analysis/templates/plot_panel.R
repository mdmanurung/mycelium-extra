# @@FILE@@: manuscript panel @@PANEL@@ of @@NAME@@.
# Purpose: [The one claim this panel carries.]
# Run:     Rscript @@PATH@@ <panels dir>   # from the repository root
# Inputs:  [each file it reads, with the script that produced it, or [gap]]
# Outputs: <panels dir>/source_data/@@PANEL@@.tsv, <panels dir>/figures/@@PANEL@@.pdf and .png
# Release: config/figure_map.tsv and config/manuscript_checks.json name the files under the panels dir,
#          and manuscript-audit checks them.

suppressPackageStartupMessages({
  library(ggplot2)
  library(readr)
})

# Parameters -------------------------------------------------------------------
# Values a reader may change, UPPER_SNAKE, with the reason beside each. Delete the block if there are none.
SEED <- 1 # jitter position, so the panel redraws the same

# Arguments --------------------------------------------------------------------
args <- commandArgs(trailingOnly = TRUE)
stopifnot("pass the panels folder as the one argument" = length(args) == 1L)
panels_dir <- args[[1L]]
source("@@DEST@@/code/theme.R") # the theme, PALETTE, scale_colour_label(), save_panel()
dir.create(file.path(panels_dir, "source_data"), recursive = TRUE, showWarnings = FALSE)
source_path <- file.path(panels_dir, "source_data", "@@PANEL@@.tsv")

# Export -----------------------------------------------------------------------
# The values the panel draws, after every aggregation.
plotted <- tibble::tibble(
  donor = c("d1", "d2", "d3", "d4", "d5", "d6"),
  label = c("control", "control", "control", "treated", "treated", "treated"),
  y = c(2, 3, 2.5, 4, 5, 4.5)
) # replace with the real computation
write_tsv(plotted, source_path)
rm(plotted)

# Render -----------------------------------------------------------------------
# Draw from the exported table alone, so the released source data can redraw the panel.
# Donors are the points; the summary (mean +/- SD) is named in the caption.
plotted <- read_tsv(source_path, show_col_types = FALSE)
p <- ggplot(plotted, aes(x = label, y = y, colour = label)) +
  geom_jitter(position = position_jitter(width = 0.1, height = 0, seed = SEED)) +
  stat_summary(fun.data = mean_sdl, fun.args = list(mult = 1), colour = "black") +
  scale_colour_label(plotted$label) +
  labs(x = NULL, y = "[y, unit]", caption = "Points: donors. Bar: mean +/- SD.")
save_panel(p, panels_dir, "@@PANEL@@")

# Session info -----------------------------------------------------------------
dir.create(file.path(panels_dir, "logs"), recursive = TRUE, showWarnings = FALSE)
writeLines(capture.output(sessionInfo()), file.path(panels_dir, "logs", "@@PANEL@@.session.txt"))
