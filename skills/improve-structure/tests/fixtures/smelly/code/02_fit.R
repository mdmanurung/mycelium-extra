# Purpose: fit the donor model.
# Run: bash run.sh
# Outputs: outputs/02_fit/02_fit.rds

suppressPackageStartupMessages({
  library(readr)
})

counts <- readRDS("data/counts.rds")
meta <- read_tsv("data/meta.tsv")
prep <- readRDS("/home/user/proj/outputs/01_prepare/01_prepare.rds")
earlier <- readRDS(file.path(dirname(input_path), "extra.rds"))
run_table <- read_tsv(file.path(RUN_DIR, "table.tsv"))

MIN_FRAC <- 0.1

# Same normalisation as step 01.
keep <- rowSums(counts > 0) >= 3
counts <- counts[keep, ]
meta <- meta[match(colnames(counts), meta$id), ]
libsize <- colSums(counts)
cpm <- t(t(counts) / libsize) * 1e6
logcpm <- log2(cpm + 1)
donor_means <- rowsum(t(logcpm), meta$donor) / as.vector(table(meta$donor))
pca <- prcomp(donor_means)
scores <- as.data.frame(pca$x[, 1:2])

set.seed(42)
sig <- fit$padj < 0.05
big <- abs(fit$logFC) > 0.58
clusters <- FindClusters(obj, resolution = 0.8)

saveRDS(sig, "outputs/02_fit/02_fit.rds")
