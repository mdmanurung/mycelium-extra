---
name: analysis-report
disable-model-invocation: true
description: Fill the Quarto report new-analysis scaffolds in reports/ after a run. Narrative, quoted script excerpts, a step diagram and inspected figures in Overview, Methods, Results and Reproducibility tabs.
---

# Mycelium Extra: Analysis report

Fill `analysis/<name>/reports/<name>.qmd` after a run. The file is the literate record of the analysis: what each step does, the lines that do it, and the figures that support each conclusion. It is not a rerun of the analysis: `engine: markdown` executes nothing, code blocks are quotations, and figures are files already under `outputs/`. Mycelium's `/mycelium:report` writes the manuscript-grade LaTeX PDF in the same `reports/` folder under a different name; this report is the working one you render after each run.

Invoke with `/mycelium-extra:analysis-report analysis/<name>`.

## 1. Read, run nothing

- `<NAME>.md` (Purpose, Steps table, Key Findings, Outputs), `plans/PLAN.md`, `plans/TRACKER.md`.
- Every script in `code/` that the Snakefile runs, and `Snakefile` itself.
- `outputs/` (figures, tables, `numbers.json`), `logs/`, and `provenance/` when `verify write` has run.
- Read [../plot-first/SKILL.md](../plot-first/SKILL.md): its citation rules apply to every Results line.

If `reports/<name>.qmd` is missing (a folder older than this template), copy the skeleton from `new-analysis`'s `templates/report.qmd` by hand: `new-analysis` refuses a non-empty folder.

## 2. Fill with Edit

- **Overview.** The meta line (status, the run under `outputs/` the report reads, findings IDs), the Purpose in the user's words from `<NAME>.md`, then **Answer in brief**: one line per Results tab, written last, giving the answer, its size, and what it does not show. Keep the mermaid chain equal to the Snakefile: one `s<NN>["code/<file>"] --> o<NN>[("<output>")]` per rule, inputs on the left. A step added since the scaffold gets a node and a tab in Methods and Results.
- **Methods**, one tab per step. Two sentences on what the step does and the choice it makes. Then one code block, 5–15 lines copied verbatim from the script, with `filename=` and a comment giving the line range (`# lines 41–58`). Quote the lines that do the work (the model call, the test, the filter), never the imports or argument parsing. Link the script; do not paste it whole.
- **Results**, one tab per question, numbered as in the plan (`1. What changes after X`); the scaffold's step tabs are placeholders to rename. Each conclusion follows plot-first: the figure link inside the sentence, the panel as a separate word, and the `[agent-derived: ...]` tag at line end. Below it, the inspection line: path, what you saw, any defect, or `not inspected: <reason>`. Numbers come from `outputs/numbers.json` or the analysis doc's `<!-- claims -->` block; write a number nowhere else first. A table needs `table fallback: <reason>`. A null or adverse result gets its tab too.
- **Figures** are `![caption](../outputs/<NN>_<what-it-shows>.png)` or the link form above. A PDF does not render in HTML: when a step saves only a PDF, say so in the inspection line and ask for a PNG in the next plan rather than converting one by hand.
- **Open items.** What stays unresolved, each with the plot or check that would settle it; the same list goes to Open Questions in `<NAME>.md`.
- **Reproducibility.** Leave as scaffolded unless the run commands changed.

Write nothing outside `reports/` except the `## Outputs` row in step 3.

## 3. Render and record

`quarto render analysis/<name>/reports/<name>.qmd` is a gated run (quarto is a runner). Either it is a step of an approved plan, or the user runs it: suggest `! quarto render analysis/<name>/reports/<name>.qmd`. The output is `reports/<name>.html`, one self-contained file.

After a render: add `| reports/<name>.html | Quarto report (rendered <date>) |` to the `## Outputs` table of `<NAME>.md`. Mycelium's `analysis/ANALYSIS_MANIFEST.md` has a `report:` field; suggest the HTML path for it and let `/mycelium:analyze` or the user write it.

## 4. Hand off

Say which tabs are filled, which conclusions are `unsupported: no inspected figure`, and whether the HTML was rendered. No `.living/` writes: findings crystallize through Mycelium's own post-action.
