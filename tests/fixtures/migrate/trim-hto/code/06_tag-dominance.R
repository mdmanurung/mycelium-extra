# 06_tag-dominance.R: step 06 of trim-hto.
# Run:     Rscript code/06_tag-dominance.R <base_run_dir> <outputs/run/06_tag-dominance.rds>
# Inputs:  <base_run_dir>/01_valid-tags.rds (step 01 of the baseline run)
args <- commandArgs(trailingOnly = TRUE)
base_dir <- args[[1]]
output_path <- args[[2]]
run_dir <- dirname(output_path)
valid_tags <- readRDS(file.path(base_dir, "01_valid-tags.rds"))
scar <- file.path(base_dir, "01b_scar", "B1a", "run_info.json")
BASE_DIR <- Sys.getenv("BASE_DIR", base_dir)
saveRDS(valid_tags, output_path)
dir.create(file.path(run_dir, "tables"), showWarnings = FALSE)
write.table(valid_tags, file.path(run_dir, "tables", "06_tag_dominance.tsv"))
