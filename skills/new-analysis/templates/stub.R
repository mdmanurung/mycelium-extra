# @@FILE@@: step @@NUM@@ of @@NAME@@.
# Input:  @@INPUT@@
# Output: @@OUTPUT@@
# Run:    Rscript @@FILE@@ @@USAGE@@   (the Snakefile passes these paths)

args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == @@NARGS@@)
@@ARGS_CODE@@
set.seed(0)

# Fail loudly on unexpected data: check shapes and counts, never drop rows silently.

stop("@@FILE@@ is not written yet")
