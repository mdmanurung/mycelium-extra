# MYCELIUM.md (fixture stub)

SIMULATED fixture project for mycelium-extra's end-to-end tests. It follows the layout of
Mycelium 0.8.1 (`skills/core/references/folder-structure.md`). It is a stub, not Mycelium's
full protocol text.

## Conventions

- Results come from `analysis/` only. A number that appears in a finding, a report, or a
  manuscript must be produced by a script under `analysis/<name>/scripts/`.
- Raw data under `data/raw/` is read-only. Processed tables live in `data/processed/`.
- Decisions go to `.living/decisions.md`, learnings to `.living/learnings.md`, findings to
  `.living/findings/`.

## Post-action protocol

After analysis or data processing: log the session in `.living/log/`, update the findings
ledger, and record any decision or learning.
