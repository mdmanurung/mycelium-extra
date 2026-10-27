# analysis-report

Fills the Quarto report that [new-analysis](new-analysis.md) scaffolds at `analysis/<name>/reports/<name>.qmd`. It is the working, literate record of one analysis: narrative, quoted script excerpts, a diagram of the step chain, and the inspected figures behind each conclusion. It is not Mycelium's `report`, which writes the manuscript-grade LaTeX PDF (`<name>-report.tex`) in the same folder.

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`).

```
/mycelium-extra:analysis-report <folder>
```

```bash
sh <skill-dir>/../../hooks/py.sh - --dest=<folder> --templates=<skill-dir>/../new-analysis/templates [--overwrite] [--dry-run] < <skill-dir>/scripts/analysis_report.py
```

The script scans the folder and writes the skeleton; the agent reads what the inventory names, fills the `.qmd`, and renders it.

## Options

| Option | Meaning |
|---|---|
| `--dest` | The analysis folder (required). Any layout: steps `NN_*.R|py|ipynb` at the root or in `code/`, zero or more `Snakefile*`, runs under `outputs/`. |
| `--templates` | `new-analysis`'s `templates/` folder, which holds `report.qmd` (required). |
| `--overwrite` | Replace an existing `reports/<name>.qmd`. Without it an existing report is kept. |
| `--dry-run` | Print the inventory; write nothing. |

The inventory (JSON on stdout) lists the analysis doc, the steps, each Snakefile with its rules, the step script each rule's shell line names and its `RUN` folder, the dated runs and the `outputs/current` target, PNG figures, `*REPORT*.md` files and `numbers.json`. The mermaid block has one subgraph per Snakefile with its rules in file order (a folder with no Snakefile chains the steps by number); the agent adds the edges between workflows.

## The report

`new-analysis` writes the skeleton from `skills/new-analysis/templates/report.qmd`:

| Tab | Holds |
|---|---|
| Overview | Status, run and findings line; the Purpose from `<NAME>.md`; **Answer in brief**, one line per Results tab; a mermaid `flowchart LR` of inputs → `code/NN_step` → output, one node pair per Snakefile rule |
| Methods | One sub-tab per step: two sentences, then 5–15 lines quoted verbatim from the script with `filename=` and the line range |
| Results | One sub-tab per question (the scaffold's step tabs are placeholders): conclusions in plot-first form (figure link in the sentence, `[agent-derived: ...]` at line end), each with an inspection line |
| Open items | What stays unresolved and the plot or check that would settle it |
| Reproducibility | `bash run.sh`, `quarto render`, where numbers and provenance live |

`engine: markdown`: nothing executes at render; code blocks are quotations and figures are PNGs already under `outputs/`. Output: `reports/<name>.html`, a single self-contained file (`embed-resources: true`).

## Skills it reads

`plot-first` always. When installed at user level: `biology-core` and `biological-statistics` before Results, `scientific-writing` before prose, `hadley-viz` before each figure inspection line. None of them makes a plot.

## Rendering

`quarto render <folder>/reports/<name>.qmd` needs no plan: the gate reads the document's front matter, and a `.qmd` with `engine: markdown` (no cell executes) and no `_quarto.yml` in its folder or any parent up to the repository root is typesetting, not a run. Any other `.qmd`, a script operand, or `quarto run` stays gated. Quarto must be installed; the skill does not install it.

## Writes

`reports/<name>.qmd`, `reports/<name>.html`, and one `## Outputs` row in `<NAME>.md` after a render. Nothing in `.living/`.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| `quarto render` on a markdown-engine `.qmd` passes; any executable document or script stays gated | Enforced by the gate |
| The scanner keeps an existing report unless `--overwrite` | Enforced by the script |
| Snippets copied verbatim with a line range; conclusions cite inspected figures | The agent's instruction |
| Numbers only from `outputs/numbers.json` or the `<!-- claims -->` block | The agent's instruction |
