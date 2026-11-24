# Purpose: plot the gate classifier's false passes and false denies by command family,
#          dev seeds against the sealed held-out set, for one scored commit.
# Run:     Rscript tests/bench/plot_gate_baseline.R tests/bench/results/<commit>
# Inputs:
#   <dir>/dev.json      score_gate.py --json on seeds.jsonl and mined.jsonl
#   <dir>/heldout.json  score_gate.py --sealed --json on the held-out file (counts only)
# Outputs:
#   <dir>/gate_by_family.tsv  one row per corpus, family and error class: failing cases and denominator
#   <dir>/gate_by_family.pdf  the figure
#   <dir>/gate_by_family.png  the same figure for embedding
#   <dir>/sessionInfo.txt     R session

suppressPackageStartupMessages({
  library(dplyr)
  library(ggplot2)
  library(jsonlite)
  library(purrr)
  library(readr)
  library(tibble)
})

# ggprism and ggpubr are not installed in this environment; theme_classic stands in
theme_set(theme_classic(base_size = 8))
# purrr here predates list_rbind(), so bind_rows() joins the per-family rows

run_dir <- commandArgs(trailingOnly = TRUE)[[1]]

# Read the scores ------------------------------------------------------------

# one row per corpus file and family, from the scorer's JSON
read_scores <- function(path, split) {
  report <- read_json(path)
  imap(report, \(corpus, corpus_name) {
    imap(corpus[["families"]], \(fam, family) {
      tibble(
        split = split,
        corpus = corpus_name,
        family = family,
        n = fam[["n"]],
        n_run = fam[["n_run"]],
        false_pass = fam[["false_pass"]],
        false_deny = fam[["false_deny"]]
      )
    }) |>
      bind_rows()
  }) |>
    bind_rows()
}

scores <- bind_rows(
  read_scores(file.path(run_dir, "dev.json"), "dev"),
  read_scores(file.path(run_dir, "heldout.json"), "held-out")
)

# Build the plot frame -------------------------------------------------------

# false passes are over run cases, false denies over benign cases; mined cases are anchors, not shown
plot_frame <- scores |>
  filter(corpus != "mined.jsonl") |>
  transmute(
    split,
    family,
    `false pass` = false_pass,
    `false deny` = false_deny,
    n_run,
    n_benign = n - n_run
  ) |>
  tidyr::pivot_longer(
    c(`false pass`, `false deny`),
    names_to = "error",
    values_to = "failing"
  ) |>
  mutate(
    denominator = if_else(error == "false pass", n_run, n_benign),
    share = if_else(denominator > 0, failing / denominator, NA_real_),
    label = if_else(
      denominator > 0,
      sprintf("%d/%d", failing, denominator),
      "none"
    ),
    error = factor(error, levels = c("false pass", "false deny")),
    split = factor(split, levels = c("dev", "held-out"))
  )

write_tsv(plot_frame, file.path(run_dir, "gate_by_family.tsv"))

# Plot -----------------------------------------------------------------------

# bars from 0; each bar labelled failing/denominator so small n stays visible
p <- ggplot(plot_frame, aes(x = share, y = family)) +
  geom_col(fill = "grey40", width = 0.7, na.rm = TRUE) +
  geom_text(aes(x = 1.02, label = label), hjust = 0, size = 2.2) +
  facet_grid(split ~ error, scales = "free_y", space = "free_y") +
  scale_x_continuous(
    limits = c(0, 1.35),
    breaks = c(0, 0.5, 1),
    expand = c(0, 0)
  ) +
  labs(
    x = "Share of cases misclassified",
    y = NULL,
    title = "Gate classifier errors by command family"
  ) +
  theme(
    plot.title = element_text(face = "bold"),
    strip.text = element_text(face = "bold")
  )

ggsave(
  file.path(run_dir, "gate_by_family.pdf"),
  plot = p,
  width = 140,
  height = 110,
  units = "mm",
  device = cairo_pdf
)
ggsave(
  file.path(run_dir, "gate_by_family.png"),
  plot = p,
  width = 140,
  height = 110,
  units = "mm",
  dpi = 200
)

writeLines(capture.output(sessionInfo()), file.path(run_dir, "sessionInfo.txt"))
