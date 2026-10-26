# analysis-report

Fills the Quarto report that [new-analysis](new-analysis.md) scaffolds at `analysis/<name>/reports/<name>.qmd`. It is the working, literate record of one analysis: narrative, quoted script excerpts, a diagram of the step chain, and the inspected figures behind each conclusion. It is not Mycelium's `report`, which writes the manuscript-grade LaTeX PDF (`<name>-report.tex`) in the same folder.

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`).

```
/mycelium-extra:analysis-report analysis/<name>
```

There is no script. The agent reads the folder and edits the `.qmd`.

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

## Rendering

`quarto render analysis/<name>/reports/<name>.qmd` is a gated run: the gate reads `quarto` as a runner and denies it with no approved plan. Make it a plan step, or run it yourself (`! quarto render ...` in the session). Quarto must be installed; the skill does not install it.

## Writes

`reports/<name>.qmd`, and one `## Outputs` row in `<NAME>.md` after a render. Nothing in `.living/`.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| `quarto render` needs an approved plan or your own shell | Enforced by the gate |
| Snippets copied verbatim with a line range; conclusions cite inspected figures | The agent's instruction |
| Numbers only from `outputs/numbers.json` or the `<!-- claims -->` block | The agent's instruction |
