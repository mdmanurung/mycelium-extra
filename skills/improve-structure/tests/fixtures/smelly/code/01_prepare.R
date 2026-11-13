# Purpose: normalise counts and make donor means.
# Run: bash run.sh
# Outputs: outputs/01_prepare/01_prepare.rds

suppressPackageStartupMessages({
  library(readr)
})

MIN_DONOR_CELLS <- 3 # smallest pseudo-bulk group worth keeping

counts <- readRDS("data/counts.rds")
meta <- read_tsv("data/meta.tsv")

# Normalise and summarise per donor.
keep <- rowSums(counts > 0) >= 3
counts <- counts[keep, ]
meta <- meta[match(colnames(counts), meta$id), ]
libsize <- colSums(counts)
cpm <- t(t(counts) / libsize) * 1e6
logcpm <- log2(cpm + 1)
donor_means <- rowsum(t(logcpm), meta$donor) / as.vector(table(meta$donor))
pca <- prcomp(donor_means)
scores <- as.data.frame(pca$x[, 1:2])

saveRDS(scores, "outputs/01_prepare/01_prepare.rds")
