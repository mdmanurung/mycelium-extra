# Purpose: join the three earlier steps into one summary figure.
# Run: bash run.sh
# Outputs: outputs/04_combine/figures/04_combine.png

suppressPackageStartupMessages({
  library(ggplot2)
})

MIN_N <- 2 # fewest donors per group

theme_set(theme_classic(base_size = 9))
a <- readRDS("outputs/01_prepare/01_prepare.rds")
b <- readRDS("outputs/02_fit/02_fit.rds")
c <- readRDS("outputs/03_plot/03_plot.rds")
cols <- c("#1b9e77", "#d95f02", "#7570b3")

p <- ggplot(a, aes(PC1, PC2)) +
  geom_point() +
  scale_colour_manual(values = cols)

ggsave("outputs/04_combine/figures/04_combine.png", p)
