# Purpose: fit the donor model on the step 01 scores.
# Run: bash run.sh
# Outputs: outputs/02_fit/02_fit.rds

PADJ_MAX <- 0.05 # reporting cut, set by the plan
SEED <- 42 # one stochastic step, the permutation

scores <- readRDS(file.path(Sys.getenv("OUTPUTS"), "01_prepare", "01_prepare.rds"))

set.seed(SEED)
fit <- lm(PC1 ~ PC2, data = scores)
sig <- summary(fit)$coefficients[, 4] < PADJ_MAX

saveRDS(sig, "outputs/02_fit/02_fit.rds")
