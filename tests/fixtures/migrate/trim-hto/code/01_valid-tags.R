# 01_valid-tags.R: step 01 of trim-hto.
# Run:     Rscript code/01_valid-tags.R <outputs/run/01_valid-tags.rds>
args <- commandArgs(trailingOnly = TRUE)
output_path <- args[[1]]
dir.create(file.path(dirname(output_path), "tables"), showWarnings = FALSE)
valid_tags <- data.frame(tag = "A", n = 1)
saveRDS(valid_tags, output_path)
write.table(valid_tags, file.path(dirname(output_path), "tables", "01_valid_tags.tsv"))
write.table(valid_tags, file.path(dirname(output_path), "tables", "01_tags_per_donor.tsv"))
