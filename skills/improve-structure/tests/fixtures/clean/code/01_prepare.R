# Purpose: normalise counts and make donor means.
# Run: bash run.sh
# Outputs: outputs/01_prepare/01_prepare.rds

suppressPackageStartupMessages({
  library(readr)
})

MIN_CELLS <- 3 # smallest pseudo-bulk group worth keeping
SEED <- 1 # fixed so the PCA sign is stable

set.seed(SEED)
counts <- readRDS("data/counts.rds")
meta <- read_tsv("data/meta.tsv")

# Normalise and summarise per donor.
counts <- counts[rowSums(counts > 0) >= MIN_CELLS, ]
logcpm <- log2(t(t(counts) / colSums(counts)) * 1e6 + 1)
donor_means <- rowsum(t(logcpm), meta$donor) / as.vector(table(meta$donor))
scores <- as.data.frame(prcomp(donor_means)$x[, 1:2])

saveRDS(scores, "outputs/01_prepare/01_prepare.rds")
