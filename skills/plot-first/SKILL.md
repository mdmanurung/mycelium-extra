---
name: plot-first
description: Make plots the primary artifacts for interpreting analysis results, with every conclusion linked to visual evidence and tables used only as a justified last resort. Use when planning, running, continuing, reviewing, or reporting a Mycelium-initiated analysis, or when the user requests plot-first analysis outputs.
---

# Mycelium Extra: Plot first

Make results interpretable from saved plots. Every analysis conclusion must cite
the plot and panel that supports it. Apply this rule to chat replies, analysis
docs, reports, findings, and handoffs that interpret results.

## Plan the evidence

- Read the active plan, analysis doc, and output conventions first. Reuse existing
  plotting code and current figures when they answer the question.
- For each planned question or contrast, name the plot, its output path, its
  source data, and what comparison the reader should see. Plan uncertainty and
  diagnostics where the inference needs them. Do not predetermine the conclusion.
- Put figure scripts in the plan's Step cells and figure files on `Outputs:`.
  Follow the existing approval workflow. Reading this skill grants no execution
  permission and adds no approval step.
- Use the project's figure layout. In a flat scaffold, use numbered paths such as
  `outputs/03_response_by_visit.pdf`. Keep source data and model outputs as
  supporting artifacts; visual summaries do not replace them.

## Make and inspect the plots

- Generate plots from the actual analysis outputs through the existing workflow.
  Save each cited figure as a standalone artifact. A transient notebook display
  or an unsaved interactive session is insufficient.
- Show the comparison the claim depends on. Display the replication unit,
  denominators, missingness, and uncertainty where relevant. Preserve paired or
  repeated observations. Distinguish observations from model estimates.
- Use readable labels, units, legends, and accessible colors. Explain transforms,
  exclusions, and interval meanings in the caption or nearby text.
- Open the rendered figure before interpreting it. Check clipping, scales,
  group labels, and agreement with its source output. File existence alone does
  not establish that the plot supports a claim. If inspection is unavailable,
  name the gap and withhold the conclusion.
- Show null, mixed, and adverse results too. Never select panels just to support
  a preferred story. A visual pattern alone establishes neither significance
  nor causality; keep claims within the design and statistical evidence.

## Write from the evidence

Put a clickable figure link beside each conclusion. Name a panel when needed.
Separate what the plot shows from the interpretation and its limits.
For example, if the inspected output supports it:

> Responses vary across donors ([Figure 1B](outputs/03_response_by_visit.pdf)).
> Estimates remain imprecise ([Figure 1B](outputs/03_response_by_visit.pdf)).

Keep Mycelium's `.living/findings` IDs and `[agent-derived: ...]` tags.
Keep numerical claims bound to their source cells through existing claims blocks
or `register_value`; a plot citation does not replace numeric provenance.

A missing, stale, or contradictory figure leaves the conclusion unsupported.
Name the missing evidence and the next plot needed. Do not invent a citation
or treat a planned figure as an observed result. Reusing results requires a
current figure from the same run, inputs, and model as the cited results.

## Tables as a last resort

First try a plot suited to the question. Use an interpretive table only when
the necessary evidence cannot be read faithfully from a plot, such as an exact
lookup of identifiers or values. State why a plot is inadequate, cite the saved
table beside the claim, and label this as a table fallback. Size or convenience
alone does not justify replacing a plot.

Machine-readable tables remain supporting outputs. Plan, manifest, provenance,
and run-status tables retain their existing formats; these track work rather
than interpret analysis results.

Before handing off, check every result conclusion for an inspected figure link
or an explicit table fallback. Mark missing evidence as incomplete. This is an
agent instruction; the execution gate does not enforce visual support.
