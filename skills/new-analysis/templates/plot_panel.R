# @@FILE@@: manuscript panel @@PANEL@@ of @@NAME@@. [The one claim this panel carries.]
# Inputs:  [each file it reads, with the script that produced it, or [gap]]
# Outputs: <run>/source_data/@@PANEL@@.tsv, <run>/figures/@@PANEL@@.pdf
# Run:     Rscript @@PATH@@ <run dir>   # from the repository root
# Release: point @@DEST@@/outputs/current at the run; config/figure_map.tsv and
#          config/manuscript_checks.json name the files under it, and manuscript-audit checks them.

args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 1L)
run <- args[[1L]]
for (folder in c("source_data", "figures")) dir.create(file.path(run, folder), recursive = TRUE, showWarnings = FALSE)
source_path <- file.path(run, "source_data", "@@PANEL@@.tsv")

# ---- 1. Export: the values the panel draws, after every aggregation ----
plotted <- data.frame(x = c(1, 2, 3), y = c(2, 4, 3))  # replace with the real computation
write.table(plotted, source_path, sep = "\t", quote = FALSE, row.names = FALSE)
rm(plotted)

# ---- 2. Render from the exported table alone, so the released source data can redraw the panel ----
plotted <- read.delim(source_path)
pdf(file.path(run, "figures", "@@PANEL@@.pdf"), width = 60 / 25.4, height = 60 / 25.4)
plot(plotted$x, plotted$y, xlab = "x", ylab = "y")
invisible(dev.off())
