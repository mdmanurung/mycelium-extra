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

It prints an inventory (analysis doc, numbered steps at the root or in `code/`, each `Snakefile*` with its rules, scripts and step folder, the `outputs/` layout read through the shared resolver (step folders; an `outputs/current` link or the newest `run_<date>` folder in an older analysis; a flat `outputs/` still works), the newest `logs/CHANGES.md` heading (or, for a legacy run, the label from `RUN.txt`), PNG figures, any figure with no `source_data/` table, `*REPORT*.md`, `numbers.json`) and writes `reports/<name>.qmd`: a mermaid chain per Snakefile, one Methods tab per step, one Results tab per step that has figures or a report. When every step is `.qmd` it writes nothing: those step pages (each rendered into its own `outputs/<stem>/` folder) carry their own Methods and Results, so fill the Question / Approach / Conclusion prose inside each step. It keeps an existing report unless `--overwrite`; a report you have already filled is replaced only when you ask. Never run it by path.

Before any whole-file write over a filled report (`--overwrite`, or a Write instead of Edit), read the report in full and list every `##`/`###` heading and tab; mark each carry or drop, and carry every one the user did not ask to drop. Run `wc -l` on it before and after, and `git diff --stat` after. A line count that falls on a targeted Edit is truncation: restore with `git restore` and redo it. When an Edit fails to match, retry it with a shorter anchor; never fall back to rewriting the file. `track-changes` reports sections that vanished since its last snapshot.

Then read what the inventory names, and run nothing else:

- The analysis doc (Purpose, Steps table, Key Findings, Outputs), `PLAN.md`, `TRACKER.md`, `HANDOFF.md` where they exist (at the root or under `plans/`).
- Every step script and every Snakefile.
- The run the report describes: figures, summary tables, `*REPORT*.md`, receipts, `numbers.json`, and `provenance/` when `verify write` has run. Open every PNG you will cite.
- [../plot-first/SKILL.md](../plot-first/SKILL.md): its citation rules apply to every Results line.
- `lucid-writer`, when it is installed (skip silently when not): load its skill before you write **Answer in brief**, the **Question / Approach / Conclusion** lines or Key Findings. It sets the evidence ceiling for each sentence (description, association, prediction, cause, mechanism) and the plain-prose rules; the report is a deliverable, so its prose follows them. Format-fixed records (the `<!-- claims -->` block, captions' `Figure N.` lines, inspection lines, tags, `unsupported:` and `table fallback:` markers, the Outputs table) keep their formats. Map `unsupported: no inspected figure` and `source data missing` to lucid-writer's `[EVIDENCE NEEDED]` only when the user asks for clean text; otherwise keep ours.
- The scan also prints `info: lucid-coder learned rules that apply (...)` when lucid-coder is installed and has active rules. Read each one's text (`/lucid-coder:rules`) before you write figures or captions. They are the user's rules, so follow them; this skill does not enforce them and lucid-coder stays their authority.
- These user-level skills, when they are installed (skip silently when not): `biology-core` and `biological-statistics` before writing Results and Answer in brief (what was measured, observation versus association versus causality, multiplicity families, paired designs, nominal versus simultaneous intervals); `scientific-writing` before any prose; `hadley-viz` before each inspection line (denominators, pairing, colour, what the next plot needs); lucid-coder's `figure-style`, else `data-visualization-master`, for what a figure's style should be. None of them makes a plot here: figures come only from approved steps.

## 2. Fill with Edit

- **Overview.** The meta line (status, the runs under `outputs/` the report reads, findings IDs; fix the plan and tracker links when they sit at the root rather than under `plans/`), the Purpose in the user's words from `<NAME>.md`, then **Answer in brief**: one line per Results tab, written last, giving the answer, its size, and what it does not show. The scanner draws the rules of each Snakefile in file order and nothing between workflows: add the edges that join them (which run feeds which), the data inputs, and any parity check. Keep the chain equal to the Snakefiles: one `s<NN>["code/<file>"] --> o<NN>[("<output>")]` per rule, inputs on the left. A step added since the scaffold gets a node and a tab in Methods and Results.
- **Methods**, one tab per step. Two sentences on what the step does and the choice it makes. Then one code block, 5–15 lines copied verbatim from the script, with `filename=` and a comment giving the line range (`# lines 41–58`). Quote the lines that do the work (the model call, the test, the filter), never the imports or argument parsing. Link the script; do not paste it whole.
- **Results**, one tab per question, numbered as in the plan (`1. What changes after X`); the scaffold's step tabs are placeholders to rename. Each tab opens with three labelled lines, **Question.** (one question), **Approach.** (data, model or test, multiplicity family), **Conclusion.** (the answer, its size, what it does not show), so a reader has the context before the evidence. Then the evidence: figure captions are numbered through the report (`Figure N. caption. \`path\``) and name the source file. Each conclusion follows plot-first: the figure link inside the sentence, the panel as a separate word, and the `[agent-derived: ...]` tag at line end. Below it, the inspection line: path, what you saw, any defect, or `not inspected: <reason>`. Numbers come from `outputs/numbers.json` or the analysis doc's `<!-- claims -->` block; write a number nowhere else first. A table needs `table fallback: <reason>`. A null or adverse result gets its tab too.
- **Figures** follow the user's learned rule `user.report_embedded_figures` (r-0002): embed every cited figure as a PNG image next to its conclusion, `![caption](../outputs/<NN>_<what-it-shows>.png)`, never as a link to a PDF. The link in the conclusion's sentence still names the panel, as plot-first says. A PDF does not render in HTML. When a step saves only PDFs, say so in the inspection line and ask for a scripted export step in the next plan (a `code/NN_export-png.sh` row that runs `pdftoppm -r 150 -png <figure>.pdf <outputs/step/figures/stem>`), then embed its pages. Do not convert one by hand and do not fall back to a link.
- **Claims.** Put one `<!-- claims -->` block in the report, at the end of Results, with a line for every number a reader would quote in Answer in brief and the Conclusions: `value | file column [row]`, with the file relative to the analysis folder (see `skills/verify/SKILL.md`, section 3). Take values from an output table cell or a JSON path in `outputs/`; a `numbers.json` key is read by its index in `values`, as `outputs/numbers.json values.<i>.value` (for the first key, `1200 | outputs/numbers.json values.0.value`). The index shifts when keys are added or removed, so recheck it after each change; the key name does not work as the column. The block is a comment, so it does not render. Never add, edit or drop a line to make the check pass.
- **Open items.** A figure whose stem has no `source_data/` table is listed as `source data missing: <figure>` and its Results tab says so; keep those lines (layout contract rule 3). What stays unresolved, each with the plot or check that would settle it; the same list goes to Open Questions in `<NAME>.md`.
- **Reproducibility.** Leave as scaffolded unless the run commands changed.

Write nothing outside `reports/` except the `## Outputs` row in step 3 and, for the artifact verb (section 5), the page under `.mycelium-extra/artifacts/` and its `TRACKER.md` line.

## 3. Render and record

Run `quarto render <folder>/reports/<name>.qmd`. The gate lets it through without a plan because the document says `engine: markdown`: no cell executes, so it is typesetting, not a run. (A `.qmd` with `engine: knitr` or `jupyter`, or a `_quarto.yml` in the folder or above it, is a gated run again.) The report's theme is `reports/report.scss` and `reports/report-dark.scss` (the plugin's `DESIGN.md` tokens; dark follows the reader's system setting). The scanner writes them when absent and never replaces an existing copy, so a project can restyle its own. The output is `reports/<name>.html`, one self-contained file; open it or check it holds the figures (`<img` count) and the mermaid block before handing off. Quarto must be on PATH; if it is missing, say so and stop.

After a render, record it with the script, not by hand (same stdin form as step 1; `--date=YYYY-MM-DD` is optional and defaults to today):

```bash
sh <skill-dir>/../../hooks/py.sh - --dest=<folder> --templates=<skill-dir>/../new-analysis/templates --outputs-row < <skill-dir>/scripts/analysis_report.py
```

It adds `| reports/<name>.html | Quarto report (rendered <date>, run <run>) |` to the `## Outputs` table of the analysis doc, once per render: a row for the same path is replaced, never doubled. The run is the date and hash in the newest `logs/CHANGES.md` heading, or, for a legacy run, the label in the current run's `RUN.txt`. When `reports/README.md` exists, it also sets the run cell of the `<name>.qmd` and `<name>.html` rows. Mycelium's `analysis/ANALYSIS_MANIFEST.md` has a `report:` field; suggest the HTML path for it and let `/mycelium:analyze` or the user write it.

## 4. Hand off

Before the hand-off, check the report's numbers and citations against the run. Get the plan hash from `verify list`, then run, from the repository root:

```bash
sh <skill-dir>/../../hooks/py.sh - --plugin-root <skill-dir>/../.. report <hash> --analysis-dir <folder> --claims <folder>/reports/<name>.qmd --resolve-citations < <skill-dir>/../verify/scripts/verify.py
```

It is read-only. `--resolve-citations` sends one request per DOI, PMID or arXiv id to Crossref, NCBI and arXiv; leave out `--contact` unless the user gives an address. Quote the five rows at the top of its output as printed. A claim the cell contradicts is a report error to fix in the text (ask the user which side is wrong; never edit the output). A claim or citation it could not check stays an open item in the hand-off. If no approved plan covers the run, say `numbers not checked: no approved plan` and skip it.

Then say which tabs are filled, which conclusions are `unsupported: no inspected figure`, what the check found, and whether the HTML was rendered. Offer the `lucid-evidence-auditor` agent (lucid-writer's independent claim audit) only if the user asks for one. No `.living/` writes: findings crystallize through Mycelium's own post-action.

## 5. Artifact: a one-off evaluation page

`/mycelium-extra:analysis-report artifact <folder>` builds a Claude Artifact for a quick read of whether the run answered the question. The `.qmd` and its HTML stay the record; the page is an evaluation copy and is not stored as documentation.

It runs only in Claude Code, where the Artifact tool exists. On Codex or OpenCode, print `The artifact verb needs Claude Code's Artifact tool; the record is reports/<name>.html.` and stop.

1. **Read, add nothing.** Read the filled `reports/<name>.qmd`, the numbers file (`numbers(folder, run)`: the flat `outputs/numbers.json`; a legacy run's `<run>/numbers.json` first), the run label (the newest `logs/CHANGES.md` heading, or a legacy run's `RUN.txt`), every cited PNG and the verify status (`verify status`, else `provenance/PROVENANCE.md`; no provenance means `not verified`). The page holds no conclusion, number or figure that the report lacks. Stop and say so if the report is still the scaffold.
2. **Write the page in one pass** to `.mycelium-extra/artifacts/<name>.html` at the repository root (`init` gitignores `.mycelium-extra/`; if `git check-ignore .mycelium-extra` finds nothing, say so in one line and write there anyway), following [references/artifact-page.md](references/artifact-page.md): the contract, the tokens, the Read-mode rules and the evaluator's order (answer in brief, each question with its figure and conclusion, open items and what is not verified, then methods quotes and reproducibility folded). The layout is free; the design is fixed. No template, no Quarto post-processing.
3. **Banner.** Every page opens with a banner naming the run label, the plan hash, and the `.qmd` path with its short hash (`git hash-object <qmd>`, first 8 characters). It says `Evaluation copy. The record is reports/<name>.html`. An unverified run says `not verified`.
4. **Figures** go in as data URIs (`data:image/png;base64,...`). The page may not pass 16 MB. When it would, stop, name the largest figures with their sizes, and ask the user which to drop or shrink. Do not downsample on your own.
5. **Check before publishing**, from the repository root, with every option as `--flag=value`:

   ```bash
   sh <skill-dir>/../../hooks/py.sh - --page=.mycelium-extra/artifacts/<name>.html --report=<folder>/reports/<name>.qmd --hooks=<skill-dir>/../../hooks < <skill-dir>/scripts/artifact_check.py
   ```

   Without `--numbers`, `--hooks` makes the check read the numbers file through `numbers()`. It checks the contract, the banner, and that every number on the page is in the `.qmd` or `numbers.json`; a list like `1,2,3` is checked number by number. A finding stops the publish: fix the page and run it again. Never edit the check to pass.
6. **Publish only after the user agrees.** Ask every time. Name the page, its size and the figure count, and say the page is private by default. Never publish unasked. In the same session, a re-run for the same analysis updates the same URL. Otherwise each run makes a new page, and the URL goes in `plans/TRACKER.md` as one line: `| <date> | Artifact (evaluation copy of reports/<name>.qmd): <url> |`.

The check does not judge whether a number means what the page says. Read the page once against the report before you publish.

End every run of this skill, the report or the artifact, with one line: `Run "handoff test" on the .qmd to check that a cold reader can follow it.`
