# Purpose: scatter of donor scores.
# Run: bash run.sh
# Outputs: outputs/03_plot/figures/03_plot.png

suppressPackageStartupMessages({
  library(ggplot2)
})

MIN_N <- 2 # fewest donors per group

theme_set(theme_bw(base_size = 8))
scores <- readRDS(file.path(Sys.getenv("OUTPUTS"), "01_prepare", "01_prepare.rds"))
cols <- c("#1b9e77", "#d95f02", "#7570b3")

p <- ggplot(scores, aes(PC1, PC2)) +
  geom_point() +
  scale_colour_manual(values = cols)

ggsave("outputs/03_plot/figures/03_plot.png", p)
