# Purpose: fit a small paired limma model on r5_samples.tsv and write its design facts (R5 proof).
# Run:     Rscript r5_fit_demo.R <fixtures dir> <out.json> [reverse]
# Inputs:  r5_samples.tsv  8 samples, 4 donors, control and stimulated, two batches
# Outputs: <out.json>      mycelium-extra.fit_design.v1 from the fit objects

suppressPackageStartupMessages(library(limma))
args <- commandArgs(trailingOnly = TRUE)
source(file.path(args[[1]], "extract_design.R"))

samples <- read.delim(file.path(args[[1]], "r5_samples.tsv"))
samples$condition <- factor(samples$condition, levels = c("control", "stimulated"))
design <- model.matrix(~ condition + batch + donor, data = samples)

set.seed(1)
expr <- matrix(rnorm(20 * nrow(samples)), nrow = 20, dimnames = list(NULL, samples$sample_id))
fit <- lmFit(expr, design)
contrast <- makeContrasts(conditionstimulated, levels = design)
if (length(args) > 2 && args[[3]] == "reverse") contrast <- -contrast
fit <- eBayes(contrasts.fit(fit, contrast))

# Take the design and contrast from the fit objects, not from the script's own variables.
extract_design(
  fit$design,
  fit$contrasts,
  ~ condition + batch + donor,
  file.path(args[[1]], "r5_samples.tsv"),
  args[[2]],
  coefficient = "conditionstimulated"
)
