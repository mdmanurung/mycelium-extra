# Step 3: hit count and median log2FC of the hits (padj < 0.05). Base R only.
# Reads outputs/de_results.tsv and writes outputs/summary.tsv. SIMULATED data.

args <- commandArgs(trailingOnly = FALSE)
self <- sub("^--file=", "", args[grep("^--file=", args)])
analysis_dir <- normalizePath(file.path(dirname(self), ".."))
de <- read.delim(file.path(analysis_dir, "outputs", "de_results.tsv"), stringsAsFactors = FALSE)
hits <- de[de$padj < 0.05, ]
summary <- data.frame(
  n_tested = nrow(de),
  n_hits = nrow(hits),
  median_log2fc_hits = sprintf("%.4f", median(hits$log2fc))
)
write.table(summary, file.path(analysis_dir, "outputs", "summary.tsv"),
            sep = "\t", quote = FALSE, row.names = FALSE)
cat(sprintf("%d of %d genes at padj < 0.05\n", nrow(hits), nrow(de)))
