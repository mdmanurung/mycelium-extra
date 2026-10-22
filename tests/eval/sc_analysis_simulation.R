# Synthetic package execution probe; no biological or calibration claim.
args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 1L, !file.exists(args[[1]]))
stopifnot(dir.create(args[[1]], recursive = TRUE))
out <- normalizePath(args[[1]])
suppressPackageStartupMessages({
  library(dreamlet)
  library(crumblr)
  library(SingleCellExperiment)
  library(BiocParallel)
  library(jsonlite)
})
set.seed(1729)
meta <- expand.grid(condition = c("control", "stimulated"), donor = sprintf("D%02d", 1:8),
                    KEEP.OUT.ATTRS = FALSE, stringsAsFactors = FALSE)
meta$condition <- factor(meta$condition, levels = c("control", "stimulated"))
meta$donor <- factor(meta$donor)
meta$sample_id <- paste(meta$donor, meta$condition, sep = "_")
meta$batch <- rep(c("b1", "b2"), each = 8)
rownames(meta) <- meta$sample_id
types <- c("T", "B", "Mono")
genes <- sprintf("gene%02d", 1:60)
base <- matrix(rgamma(60 * 3, shape = 4, rate = 2), 60, dimnames = list(genes, types))
donor_scale <- setNames(exp(rnorm(8, sd = 0.25)), levels(meta$donor))
cells <- counts <- vector("list", nrow(meta))
for (i in seq_len(nrow(meta))) {
  stimulated <- meta$condition[[i]] == "stimulated"
  sizes <- as.vector(rmultinom(1, 90, if (stimulated) c(.5, .25, .25) else c(.25, .35, .4)))
  labels <- rep(types, sizes)
  cells[[i]] <- data.frame(sample_id = meta$sample_id[[i]], donor = meta$donor[[i]],
                           condition = meta$condition[[i]], cell_type = labels)
  mu <- base[, labels, drop = FALSE] * donor_scale[[as.character(meta$donor[[i]])]]
  if (stimulated) mu[1:5, labels == "T"] <- mu[1:5, labels == "T"] * 4
  counts[[i]] <- matrix(rnbinom(length(mu), mu = mu, size = 12), nrow = 60)
}
cell_meta <- do.call(rbind, cells)
raw <- do.call(cbind, counts)
rownames(raw) <- genes
colnames(raw) <- rownames(cell_meta) <- sprintf("cell%04d", seq_len(ncol(raw)))
sce <- SingleCellExperiment(assays = list(counts = raw), colData = cell_meta)
raw_before <- assay(sce, "counts")
pb <- aggregateToPseudoBulk(sce, assay = "counts", sample_id = "sample_id",
                           cluster_id = "cell_type", verbose = FALSE, BPPARAM = SerialParam())
for (type in types) {
  for (sample in colnames(pb)) {
    expected <- rowSums(raw[, cell_meta$sample_id == sample & cell_meta$cell_type == type, drop = FALSE])
    stopifnot(identical(as.numeric(assay(pb, type)[, sample]), as.numeric(expected)))
  }
}
expected <- list(schema = "mycelium-extra.method_expectations.v1",
                 formula = "~condition + (1 | donor)",
                 contrast = list(numerator = "stimulated", denominator = "control", sign = 1L),
                 random_effects = list("(1 | donor)"), covariates = list("condition"),
                 assay = "counts", exclusions = list())
write_json(expected, file.path(out, "method-expected.json"), pretty = TRUE, auto_unbox = TRUE)
form <- ~ condition + (1 | donor)
proc <- processAssays(pb, form, min.cells = 5, min.count = 2, min.samples = 4,
                      min.prop = .25, quiet = TRUE, BPPARAM = SerialParam())
fit <- dreamlet(proc, form, min.cells = 5, quiet = TRUE, BPPARAM = SerialParam())
de <- topTable(fit, coef = "conditionstimulated", number = Inf)
stopifnot(all(c("T", "B", "Mono") %in% assayNames(fit)))
de <- as.data.frame(de)
signal <- de[de$assay == "T" & de$ID %in% genes[1:5], ]
stopifnot(nrow(signal) == 5L, all(signal$logFC > 0), all(is.finite(de$P.Value)),
          all(details(fit)$n_errors == 0), !any(details(fit)$error_initial))
# crumblr consumes samples x cell types and returns cell types x samples.
cell_counts <- cellCounts(pb)
manual_counts <- unclass(table(factor(cell_meta$sample_id, levels = meta$sample_id),
                               factor(cell_meta$cell_type, levels = types)))
stopifnot(all(cell_counts[meta$sample_id, types] == manual_counts))
cobj <- crumblr(cell_counts)
fit_meta <- as.data.frame(colData(pb))
stopifnot(identical(colnames(cobj), rownames(fit_meta)))
composition_fit <- variancePartition::dream(cobj, form, fit_meta, BPPARAM = SerialParam())
composition_fit <- variancePartition::eBayes(composition_fit)
composition <- variancePartition::topTable(composition_fit, coef = "conditionstimulated", number = Inf)
stopifnot(composition["T", "logFC"] > 0, all(is.finite(composition$P.Value)),
          all(rowSums(cell_counts) == 90))
stopifnot(identical(raw_before, assay(sce, "counts")))

record_model <- function(model) {
  formula <- model$formula
  design <- model$design
  groups <- levels(model$data$condition)
  encoding <- tapply(design[, "conditionstimulated"], model$data$condition, mean)
  list(schema = "mycelium-extra.executed_model.v1",
       formula = paste(deparse(formula), collapse = " "),
       contrast = list(numerator = groups[[2]], denominator = groups[[1]],
                       sign = as.integer(sign(encoding[[2]] - encoding[[1]]))),
       random_effects = lapply(reformulas::findbars(formula), function(term) {
         paste0("(", paste(deparse(term), collapse = " "), ")")
       }),
       covariates = as.list(all.vars(reformulas::nobars(formula))),
       assay = assayNames(sce)[[1]],
       exclusions = as.list(setdiff(colnames(pb), rownames(model$data))))
}
write_json(record_model(fit[["T"]]), file.path(out, "method-observed.json"), pretty = TRUE, auto_unbox = TRUE)
wrong_fit <- variancePartition::dream(proc[["T"]], ~ condition, fit_meta, BPPARAM = SerialParam())
write_json(record_model(wrong_fit), file.path(out, "method-omitted-donor.json"), pretty = TRUE, auto_unbox = TRUE)
shuffled <- sce[, sample(seq_len(ncol(sce)))]
pb_shuffled <- aggregateToPseudoBulk(shuffled, assay = "counts", sample_id = "sample_id",
                                    cluster_id = "cell_type", verbose = FALSE, BPPARAM = SerialParam())
for (type in types) {
  stopifnot(identical(unname(assay(pb_shuffled, type)[genes, colnames(pb)]),
                      unname(assay(pb, type)[genes, colnames(pb)])))
}
saveRDS(list(sce = sce, pseudobulk = pb, processed = proc, fit = fit,
             composition_fit = composition_fit, composition_counts = cell_counts,
             metadata = meta), file.path(out, "simulation.rds"))
write.table(meta, file.path(out, "samples.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)
write.table(de, file.path(out, "expression.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)
write.table(composition, file.path(out, "composition.tsv"), sep = "\t", quote = FALSE)
write.table(raw, file.path(out, "counts.tsv"), sep = "\t", quote = FALSE, col.names = NA)
write.table(cell_meta, file.path(out, "cells.tsv"), sep = "\t", quote = FALSE, col.names = NA)
write.table(cell_counts, file.path(out, "cell-counts.tsv"), sep = "\t", quote = FALSE, col.names = NA)
write_json(list(synthetic = TRUE, seed = 1729, donors = 8, samples = 16, cells = ncol(raw),
                genes = nrow(raw), formula = paste(deparse(form), collapse = " "),
                raw_counts_unchanged = TRUE, pseudobulk_sums_checked = TRUE,
                pseudobulk_cell_order_invariant = TRUE, composition_denominator = "all 90 simulated cells per sample",
                fitted_methods = list("dreamlet: ~condition + (1 | donor)",
                                      "crumblr/dream: ~condition + (1 | donor)",
                                      "negative control dream: ~condition"),
                versions = setNames(lapply(c("dreamlet", "variancePartition", "crumblr", "limma"),
                                           function(p) as.character(packageVersion(p))),
                                    c("dreamlet", "variancePartition", "crumblr", "limma")),
                limitations = "Synthetic execution probe; no power, error-rate or scientific-effectiveness claim."),
           file.path(out, "receipt.json"), pretty = TRUE, auto_unbox = TRUE)
writeLines(capture.output(sessionInfo()), file.path(out, "sessionInfo.txt"))
