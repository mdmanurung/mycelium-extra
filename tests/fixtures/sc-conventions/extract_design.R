# Purpose: write the design facts a limma/edgeR-style fit used, for recipe R5.
# Run:     source("extract_design.R"), then call extract_design() once after the fit.
# Inputs:  the design matrix from model.matrix(), the contrast vector or one-column
#          matrix from makeContrasts(), the formula, the sample table file the fit read.
# Outputs: one JSON file, mycelium-extra.fit_design.v1 (read by method_fidelity.py).

extract_design <- function(design, contrast, formula, sample_table_path, out_path, coefficient = NULL) {
  # A makeContrasts() matrix has one column per contrast; take that column by name.
  weights <- if (is.matrix(contrast)) contrast[, 1] else contrast
  # makeContrasts() renames "(Intercept)" to "Intercept"; a weight on a name the design lacks must fail.
  stopifnot("contrast names are design columns" = all(names(weights)[weights != 0] %in% colnames(design)))
  weights <- setNames(weights[colnames(design)], colnames(design))
  weights[is.na(weights)] <- 0

  # Rows as plain lists so the JSON is a matrix, not a named object.
  design_rows <- lapply(seq_len(nrow(design)), \(i) unname(design[i, ]))

  record <- list(
    schema = "mycelium-extra.fit_design.v1",
    formula = paste(deparse(formula), collapse = " "),
    design_columns = colnames(design),
    design = design_rows,
    coefficient = coefficient,
    contrast = as.list(weights[weights != 0]),
    sample_table_sha256 = digest::digest(file = sample_table_path, algo = "sha256")
  )
  jsonlite::write_json(record, out_path, auto_unbox = TRUE, digits = NA, null = "null", pretty = TRUE)
}
