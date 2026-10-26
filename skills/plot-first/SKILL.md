---
name: plot-first
description: Make saved, inspected plots the evidence for analysis conclusions; every conclusion links a figure, and an interpretive table needs a stated reason. Use when writing or checking a conclusion from analysis outputs, or when the user asks for plot-first outputs; grill and new-analysis load it themselves.
---

# Mycelium Extra: Plot first

Every analysis conclusion cites the saved, inspected figure that supports it. This applies to chat replies, analysis docs, reports, `.living/findings/` entries, and handoffs that interpret results. This is agent guidance: reading it grants no execution permission, adds no approval step, and the gate does not enforce it.

Invoked directly with a folder: read `<folder>/<NAME>.md` and the reports it names, list each conclusion with its figure link, table fallback, or `unsupported`, and write nothing. Making a missing plot needs a grill plan.

## Plan the evidence

- When planning, there is no plan yet: start from the repository's output conventions (`.living/conventions.md`, else the scaffold's `outputs/`). When continuing work, read the approved plan (`plans/PLAN.md` or `provenance/plan-<hash>.md`) and the analysis doc first, and reuse plotting code and current figures that answer the question.
- For each question or contrast, name the figure path, its source data, and the comparison the reader should see. Plan uncertainty and diagnostic plots where the inference needs them. Do not predetermine the conclusion.
- A cited figure comes from a script named in a plan Step cell with its file on `Outputs:`. A figure drawn by inline code (`python3 -c`, `Rscript -e`, a notebook cell not in the plan) is exploration and is never cited.
- Name files by what they show, as the repository's conventions say; in a new-analysis scaffold the name starts with the step number (`outputs/03_response_by_visit.pdf`). Do not bake a manuscript figure number into an analysis file name. A manuscript panel reads only its exported source-data table (new-analysis `--panels`); other figures name their source file in the plan row. Source data and model outputs stay as supporting artifacts.

## Make and inspect the plots

- Generate plots from the actual analysis outputs through the approved steps and save each cited figure as a file under `outputs/`. A transient notebook display, an unsaved interactive session, or a figure inside an executed notebook copy under `logs/` is not a cited figure.
- Show the comparison the claim depends on: the replication unit, denominators, missingness, and uncertainty where relevant. Preserve paired or repeated observations. Distinguish observations from model estimates. When the result has no replication unit or is an enumeration (identifiers, gene sets), say so and go straight to the table fallback with that reason.
- Use readable labels, units, legends, and accessible colors. State transforms, exclusions, and interval meanings in the caption or nearby text.
- Inspect before interpreting. For each figure you cite, write one line where the conclusion lives: the path, what you saw (groups, n, axes, interval type), and any defect such as clipping or a mislabelled group. A figure you could not render (no image viewer, a PDF page you could not open) is `not inspected: <reason>`, and its conclusion stays unsupported.
- Show null, mixed, and adverse results too. Never select panels to support a preferred story. A visual pattern alone establishes neither significance nor causality; keep claims within the design and the statistical evidence.

## Write from the evidence

Put the figure link inside the sentence and name the panel as a separate word; the fact tag ends the line, because `verify` counts tags only at line end. Write the path relative to the file the link is in; in a chat reply, write it from the repository root. For example, if the inspected output supports it:

```markdown
- Responses vary across donors ([figure](outputs/03_response_by_visit.pdf), panel B). [agent-derived: `outputs/03_response_by_visit.pdf`]
- Estimates stay imprecise ([figure](outputs/03_response_by_visit.pdf), panel B; wide 95% intervals). [agent-derived: `outputs/03_response_by_visit.pdf`]
```

Separate what the plot shows from the interpretation and its limits. In `.living/findings/`, cite the figure in the entry's prose under its `## F-NNN:` heading; never change the registry table's columns, IDs, or Run/Session cells. Keep numbers bound to their source cells through the analysis doc's `<!-- claims -->` block or Mycelium's `register_value` (`outputs/numbers.json`); a figure citation does not replace numeric provenance.

Before reusing a figure from an earlier run, check it against `provenance/outputs-<hash>.tsv` or run verify `stale`; a figure with no recorded producer is `unsupported`, not stale by eye. Do not invent a citation or treat a planned figure as an observed result.

## Tables as a last resort

First try a plot suited to the question. Use an interpretive table only when the evidence cannot be read faithfully from a plot, such as an exact lookup of identifiers or values. Write `table fallback: <reason>` immediately before the link to the saved table. Size or convenience alone is not a reason.

Plan, manifest, provenance, run-status and `## Outputs` tables, and the tables `verify` prints, keep their formats: they track work rather than interpret results. Machine-readable tables stay supporting outputs.

## Before handing off

Check every result conclusion for an inspected figure link or a `table fallback:` line. Where neither exists, write `unsupported: no inspected figure` after the conclusion in the same document and name the next plot needed; do not move it to a parked list.
