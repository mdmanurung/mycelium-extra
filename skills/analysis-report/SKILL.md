---
name: analysis-report
disable-model-invocation: true
description: Fill the Quarto report new-analysis scaffolds in reports/ after a run. Narrative, quoted script excerpts, a step diagram and inspected figures in Overview, Methods, Results and Reproducibility tabs.
---

# Mycelium Extra: Analysis report

Fill `analysis/<name>/reports/<name>.qmd` after a run. The file is the literate record of the analysis: what each step does, the lines that do it, and the figures that support each conclusion. It is not a rerun of the analysis: `engine: markdown` executes nothing, code blocks are quotations, and figures are files already under `outputs/`. Mycelium's `/mycelium:report` writes the manuscript-grade LaTeX PDF in the same `reports/` folder under a different name; this report is the working one you render after each run.

Invoke with `/mycelium-extra:analysis-report <folder>`. The folder need not come from `new-analysis`: the scanner reads what is there (steps at the root or in `code/`, one Snakefile or several, dated runs under `outputs/`).

## 1. Scan the folder

Run from the repository root, from stdin, every option as `--flag=value` (a bare path is read as a script run and blocked):

```bash
sh <skill-dir>/../../hooks/py.sh - --dest=<folder> --templates=<skill-dir>/../new-analysis/templates [--overwrite] [--dry-run] < <skill-dir>/scripts/analysis_report.py
```

It prints an inventory (analysis doc, numbered steps at the root or in `code/`, each `Snakefile*` with its rules, scripts and run folder, the dated runs under `outputs/` and where `current` points, PNG figures, `*REPORT*.md`, `numbers.json`) and writes `reports/<name>.qmd`: a mermaid chain per Snakefile, one Methods tab per step, one Results tab per step that has figures or a report. When every step is `.qmd` it writes nothing: those step pages (rendered under `reports/site/`) carry their own Methods and Results, so fill the Question / Approach / Conclusion prose inside each step. It keeps an existing report unless `--overwrite`; a report you have already filled is replaced only when you ask. Never run it by path.

Before any whole-file write over a filled report (`--overwrite`, or a Write instead of Edit), read the report in full and list every `##`/`###` heading and tab; mark each carry or drop, and carry every one the user did not ask to drop. Run `wc -l` on it before and after, and `git diff --stat` after. A line count that falls on a targeted Edit is truncation: restore with `git restore` and redo it. When an Edit fails to match, retry it with a shorter anchor; never fall back to rewriting the file. `track-changes` reports sections that vanished since its last snapshot.

Then read what the inventory names, and run nothing else:

- The analysis doc (Purpose, Steps table, Key Findings, Outputs), `PLAN.md`, `TRACKER.md`, `HANDOFF.md` where they exist (at the root or under `plans/`).
- Every step script and every Snakefile.
- The run the report describes: figures, summary tables, `*REPORT*.md`, receipts, `numbers.json`, and `provenance/` when `verify write` has run. Open every PNG you will cite.
- [../plot-first/SKILL.md](../plot-first/SKILL.md): its citation rules apply to every Results line.
- These user-level skills, when they are installed (skip silently when not): `biology-core` and `biological-statistics` before writing Results and Answer in brief (what was measured, observation versus association versus causality, multiplicity families, paired designs, nominal versus simultaneous intervals); `scientific-writing` before any prose; `hadley-viz` before each inspection line (denominators, pairing, colour, what the next plot needs); lucid-coder's `figure-style`, else `data-visualization-master`, for what a figure's style should be. None of them makes a plot here: figures come only from approved steps.

## 2. Fill with Edit

- **Overview.** The meta line (status, the runs under `outputs/` the report reads, findings IDs; fix the plan and tracker links when they sit at the root rather than under `plans/`), the Purpose in the user's words from `<NAME>.md`, then **Answer in brief**: one line per Results tab, written last, giving the answer, its size, and what it does not show. The scanner draws the rules of each Snakefile in file order and nothing between workflows: add the edges that join them (which run feeds which), the data inputs, and any parity check. Keep the chain equal to the Snakefiles: one `s<NN>["code/<file>"] --> o<NN>[("<output>")]` per rule, inputs on the left. A step added since the scaffold gets a node and a tab in Methods and Results.
- **Methods**, one tab per step. Two sentences on what the step does and the choice it makes. Then one code block, 5–15 lines copied verbatim from the script, with `filename=` and a comment giving the line range (`# lines 41–58`). Quote the lines that do the work (the model call, the test, the filter), never the imports or argument parsing. Link the script; do not paste it whole.
- **Results**, one tab per question, numbered as in the plan (`1. What changes after X`); the scaffold's step tabs are placeholders to rename. Each tab opens with three labelled lines, **Question.** (one question), **Approach.** (data, model or test, multiplicity family), **Conclusion.** (the answer, its size, what it does not show), so a reader has the context before the evidence. Then the evidence: figure captions are numbered through the report (`Figure N. caption. \`path\``) and name the source file. Each conclusion follows plot-first: the figure link inside the sentence, the panel as a separate word, and the `[agent-derived: ...]` tag at line end. Below it, the inspection line: path, what you saw, any defect, or `not inspected: <reason>`. Numbers come from `outputs/numbers.json` or the analysis doc's `<!-- claims -->` block; write a number nowhere else first. A table needs `table fallback: <reason>`. A null or adverse result gets its tab too.
- **Figures** are `![caption](../outputs/<NN>_<what-it-shows>.png)` or the link form above. A PDF does not render in HTML: when a step saves only a PDF, say so in the inspection line and ask for a PNG in the next plan rather than converting one by hand.
- **Open items.** What stays unresolved, each with the plot or check that would settle it; the same list goes to Open Questions in `<NAME>.md`.
- **Reproducibility.** Leave as scaffolded unless the run commands changed.

Write nothing outside `reports/` except the `## Outputs` row in step 3.

## 3. Render and record

Run `quarto render <folder>/reports/<name>.qmd`. The gate lets it through without a plan because the document says `engine: markdown`: no cell executes, so it is typesetting, not a run. (A `.qmd` with `engine: knitr` or `jupyter`, or a `_quarto.yml` in the folder or above it, is a gated run again.) The report's theme is `reports/report.scss` and `reports/report-dark.scss` (the plugin's `DESIGN.md` tokens; dark follows the reader's system setting). The scanner writes them when absent and never replaces an existing copy, so a project can restyle its own. The output is `reports/<name>.html`, one self-contained file; open it or check it holds the figures (`<img` count) and the mermaid block before handing off. Quarto must be on PATH; if it is missing, say so and stop.

After a render: add `| reports/<name>.html | Quarto report (rendered <date>) |` to the `## Outputs` table of `<NAME>.md` (one sentence in its Outputs section when the doc has no table). Mycelium's `analysis/ANALYSIS_MANIFEST.md` has a `report:` field; suggest the HTML path for it and let `/mycelium:analyze` or the user write it.

## 4. Hand off

Say which tabs are filled, which conclusions are `unsupported: no inspected figure`, and whether the HTML was rendered. No `.living/` writes: findings crystallize through Mycelium's own post-action.

## 5. Artifact: a one-off evaluation page

`/mycelium-extra:analysis-report artifact <folder>` builds a Claude Artifact for a quick read of whether the run answered the question. The `.qmd` and its HTML stay the record; the page is an evaluation copy and is not stored as documentation.

It runs only in Claude Code, where the Artifact tool exists. On Codex or OpenCode, print `The artifact verb needs Claude Code's Artifact tool; the record is reports/<name>.html.` and stop.

1. **Read, add nothing.** Read the filled `reports/<name>.qmd`, `outputs/numbers.json`, every cited PNG and the verify status (`verify status`, else `provenance/PROVENANCE.md`; no provenance means `not verified`). The page holds no conclusion, number or figure that the report lacks. Stop and say so if the report is still the scaffold.
2. **Write the page in one pass** to `reports/<name>.artifact.html`, following [references/artifact-page.md](references/artifact-page.md): the contract, the tokens, the Read-mode rules and the evaluator's order (answer in brief, each question with its figure and conclusion, open items and what is not verified, then methods quotes and reproducibility folded). The layout is free; the design is fixed. No template, no Quarto post-processing.
3. **Banner.** Every page opens with a banner naming the run label, the plan hash, and the `.qmd` path with its short hash (`git hash-object <qmd>`, first 8 characters). It says `Evaluation copy. The record is reports/<name>.html`. An unverified run says `not verified`.
4. **Figures** go in as data URIs (`data:image/png;base64,...`). The page may not pass 16 MB. When it would, stop, name the largest figures with their sizes, and ask the user which to drop or shrink. Do not downsample on your own.
5. **Check before publishing**, from the repository root, with every option as `--flag=value`:

   ```bash
   sh <skill-dir>/../../hooks/py.sh - --page=<folder>/reports/<name>.artifact.html --report=<folder>/reports/<name>.qmd --numbers=<folder>/outputs/numbers.json < <skill-dir>/scripts/artifact_check.py
   ```

   It checks the contract, the banner, and that every number on the page is in the `.qmd` or `numbers.json`. A finding stops the publish: fix the page and run it again. Never edit the check to pass.
6. **Publish only after the user agrees.** Ask every time. Name the page, its size and the figure count, and say the page is private by default. Never publish unasked. In the same session, a re-run for the same analysis updates the same URL. Otherwise each run makes a new page, and the URL goes in `plans/TRACKER.md` as one line: `| <date> | Artifact (evaluation copy of reports/<name>.qmd): <url> |`.

The check does not judge whether a number means what the page says. Read the page once against the report before you publish.

End every run of this skill, the report or the artifact, with one line: `Run "handoff test" on the .qmd to check that a cold reader can follow it.`
