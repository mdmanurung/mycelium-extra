# @@FILE@@: step @@NUM@@ of @@NAME@@.
# Purpose: [One sentence: what this step answers or prepares.]
# Run:     Rscript @@PATH@@ @@USAGE@@   (the Snakefile passes these paths)
# Inputs:  @@INPUT@@ [producer or [gap]]
# Outputs: @@OUTPUT@@ [what the table holds]
# scilintr stage: replace this line with `# STAGE: <stage>` (blind_qc, selection, evaluation or library;
#   label columns are allowed only in evaluation) so its label and stage rules run on this file.

# Parameters -------------------------------------------------------------------
# Values a reader may change, UPPER_SNAKE, with the reason beside each. Delete the block if there are none.
SEED <- 0 # every stochastic step below uses this

# Arguments --------------------------------------------------------------------
args <- commandArgs(trailingOnly = TRUE)
stopifnot("the Snakefile passes @@NARGS@@ path argument(s)" = length(args) == @@NARGS@@)
@@ARGS_CODE@@
step_dir <- dirname(output_path) # this step's folder, outputs/@@STEM@@
set.seed(SEED)

# Load data --------------------------------------------------------------------
# Name one check where tables meet, e.g.
# stopifnot("meta rows match counts" = identical(meta$id, colnames(counts)))
stop("@@FILE@@ is not written yet")

# Session info -----------------------------------------------------------------
dir.create(file.path(step_dir, "logs"), recursive = TRUE, showWarnings = FALSE)
writeLines(capture.output(sessionInfo()), file.path(step_dir, "logs", "@@STEM@@.session.txt"))
