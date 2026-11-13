# 01_scan.R: step 01 of smoke, a tiny working script for tests/e2e_real.py.
# Input:  none (synthetic)
# Output: outputs/01_scan/01_scan.tsv
# Run:    Rscript code/01_scan.R outputs/01_scan/01_scan.tsv   (the Snakefile passes this path)

args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 1)
output_path <- args[[1]]

scan <- data.frame(
  donor = paste0("d", 1:6),
  label = rep(c("control", "treated"), each = 3),
  value = c(2, 3, 2.5, 4, 5, 4.5)
)
write.table(scan, output_path, sep = "\t", quote = FALSE, row.names = FALSE)
