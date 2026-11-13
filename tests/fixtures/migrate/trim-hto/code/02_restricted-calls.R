# 02_restricted-calls.R: step 02 of trim-hto.
# Run:     Rscript code/02_restricted-calls.R <outputs/run/01_valid-tags.rds> <outputs/run/02_restricted-calls.rds>
args <- commandArgs(trailingOnly = TRUE)
input_path <- args[[1]]
output_path <- args[[2]]
run_dir <- dirname(input_path)
scar <- file.path(run_dir, "01b_scar", "B1a", "run_info.json")
calls <- readRDS(input_path)
saveRDS(calls, output_path)
grid <- read.delim("outputs/latest/01b_scar/B1a/ambient_grid.tsv")
