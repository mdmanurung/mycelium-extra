# 03_show.R: step 03 of smoke, the figure step; a tiny working script for tests/e2e_real.py.
# Input:  outputs/02_fit/02_fit.tsv
# Output: outputs/03_show/figures/03_show.png and .pdf, outputs/03_show/source_data/03_show.tsv
# Run:    Rscript code/03_show.R outputs/02_fit/02_fit.tsv outputs/03_show   (the Snakefile passes these paths)

suppressPackageStartupMessages({
  library(ggplot2)
})

args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 2)
input_path <- args[[1]]
step_dir <- args[[2]]
source("code/theme.R")
set.seed(0)

# Plot frame ------------------------------------------------------------------
plotted <- read.delim(input_path)
dir.create(file.path(step_dir, "source_data"), recursive = TRUE, showWarnings = FALSE)
write.table(
  plotted,
  file.path(step_dir, "source_data", "03_show.tsv"),
  sep = "\t", quote = FALSE, row.names = FALSE
)

# Figure ----------------------------------------------------------------------
p <- ggplot(plotted, aes(x = label, y = fit, colour = label)) +
  geom_jitter(position = position_jitter(width = 0.1, height = 0, seed = 1)) +
  scale_colour_label(plotted$label) +
  labs(x = NULL, y = "fit (a.u.)", caption = "Points: donors.")
save_panel(p, step_dir, "03_show")
