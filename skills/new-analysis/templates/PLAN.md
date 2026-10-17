# @@NAME@@: plan

One plan for this analysis. Revise it in place, and add a dated line to
[TRACKER.md](TRACKER.md) when it changes; do not start a second plan file. The headings
follow the mycelium-extra grill brief, so an approved brief goes in section by section.

## Objective

[The question and, for scientific work, the estimand or contrast.]

## Evidence

[Repository paths with sections or lines, decision headings from `.living/decisions.md`,
finding IDs (`F-NNN`).]

## Inputs

Inputs: @@INPUTS@@

## Plan

| ID | Step | Consequential choice | Source | Validation |
|---|---|---|---|---|
@@PLAN_ROWS@@

<!--
Optional, for a reportable run: two comment blocks bind it more tightly than the table does. Write them as
HTML comments in the plan you present, not nested inside this one. See the grill skill's references/run-plans.md.

  exact-execution {"version": 1, "steps": [{"row": "S2", "argv": ["python", "<analysis folder>/02_fit.py", "--model", "mixed", "--threads", "4"], "cwd": ".", "env": {}, "operational": ["--threads"]}]}
  validation-bindings {"version": 1, "checks": [{"id": "V1", "plan_row": "S2", "required": true, "defined_by": "agent-proposed", "test_paths": ["<analysis folder>/tests/expected.tsv"], "invocation": ["python", "<analysis folder>/tests/check.py"], "evidence_path": "<analysis folder>/outputs/check.json"}]}

Without them a path in the Step column is a broad grant (any arguments). `defined_by` is recorded, not verified.
-->

## Assumptions and risk

- [Each default in one line, then the key failure mode and how the plan detects it.]

## Parked

- [Deferred item: return when ...]

## Decisions to record

- [Answers and defaults for `.living/decisions.md`, logged once work begins.]
