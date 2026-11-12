# theme.R: the house plot style, sourced by every figure script (source("code/theme.R")).
# Purpose: one theme, one palette and one export size for every figure of this analysis.
# Run:     sourced, not run. Needs ggplot2 and ggpubr.
# Outputs: save_panel() writes <dir>/figures/<stem>.pdf and .png at 89 x 70 mm.

suppressPackageStartupMessages({
  library(ggplot2)
  library(ggpubr)
})

# Parameters ------------------------------------------------------------------
# One colour per label, keyed by the label as it appears in the data. Add every label you plot.
PALETTE <- c(control = "#6E6E6E", treated = "#C8553D")

# Theme -----------------------------------------------------------------------
theme_set(ggpubr::theme_pubr(base_size = 8))

# Palette scales --------------------------------------------------------------
# Fail on a label the palette does not name, so no group falls back to a default colour.
palette_for <- function(labels) {
  labels <- unique(as.character(labels))
  unknown <- setdiff(labels, names(PALETTE))
  if (length(unknown) > 0L) {
    stop(sprintf("labels not in PALETTE (code/theme.R): %s", paste(unknown, collapse = ", ")), call. = FALSE)
  }
  PALETTE[labels]
}

scale_colour_label <- function(labels) scale_colour_manual(values = palette_for(labels))
scale_fill_label <- function(labels) scale_fill_manual(values = palette_for(labels))

# Export ----------------------------------------------------------------------
# PDF (cairo) for the manuscript and PNG for the report, same size, same stem.
save_panel <- function(p, dir, stem, width = 89, height = 70) {
  dir.create(file.path(dir, "figures"), recursive = TRUE, showWarnings = FALSE)
  ggsave(file.path(dir, "figures", paste0(stem, ".pdf")),
    plot = p, width = width, height = height, units = "mm", device = cairo_pdf
  )
  ggsave(file.path(dir, "figures", paste0(stem, ".png")),
    plot = p, width = width, height = height, units = "mm", dpi = 300
  )
}
