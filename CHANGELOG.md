# Changelog

All notable changes to mycelium-extra are listed here, newest first. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are the `version` in the three plugin manifests. Entries from 0.9.16 to 0.9.29 were rebuilt from `git log`.

## [Unreleased]

### Added

- MIT `LICENSE`, named in both plugin manifests.
- `CHANGELOG.md`; a version bump now adds an entry here.

### Changed

- The README is a landing page; skill, gate, Mycelium, and development details moved to `docs/`.
- The README summary table says that `plan-review` sends a packet to Codex and Biomni after you agree.

## [0.9.29] - 2026-10-04

### Added

- `grill`: an LLM failure-mode checklist (`skills/grill/references/llm-failure-modes.md`) with scenarios and a reference test.
- Docs: a Mermaid workflow diagram in the README, the improvement roadmap (`docs/roadmap/`), the C1 fixture-project design, and a committed `HANDOFF.md`.

## [0.9.28] - 2026-10-04

### Added

- `verify` lints the `{r}` and `{python}` chunks of `.qmd` and `.Rmd` files; findings cite the document's own line.

## [0.9.27] - 2026-10-04

### Fixed

- `verify` reports a `.py` script that does not parse as a lint gap, not clean.

## [0.9.26] - 2026-10-04

### Fixed

- Gate: code piped into a runner (`echo ... | python3`) is checked against the whole command again.

## [0.9.25] - 2026-10-04

### Fixed

- Gate: state-folder writes and inline runs are judged by what the code targets (per-segment heredocs, path strings in Python code, literal variables expanded, `-c`/`-e` gated only when it names gated code).

## [0.9.24] - 2026-10-03

### Added

- Promote explore runs: `verify explore` lists them and `grill` drafts a plan that re-runs them for approval.

## [0.9.23] - 2026-10-03

### Fixed

- Gate: the approve line has no Markdown bold, since notices are plain text.

## [0.9.22] - 2026-10-03

### Changed

- Gate: the approval notice is a card with the approve line and bulleted runs, pins, and outputs.

## [0.9.21] - 2026-10-03

### Fixed

- `verify` uses the session conda env only when a run declares no env.

## [0.9.20] - 2026-10-03

### Added

- `verify` records the packages of a run's conda env into provenance (`env-<hash>.txt`).

## [0.9.19] - 2026-10-03

### Fixed

- `new-analysis`: the notebook stub raises instead of asserting its input.

## [0.9.18] - 2026-10-03

### Added

- `verify` lints Jupyter notebook code cells.

### Fixed

- `verify status` shows an unchecked linter as a gap, not clean.

## [0.9.17] - 2026-10-03

### Added

- `verify status`: a table of plans, runs, verify status, staleness, lint, and manifest entry.

## [0.9.16] - 2026-10-03

### Added

- Ledger rows link to the approved plan; `verify stale` searches by plan hash.

### Changed

- A run plan's dry run goes under the first plan's approval; an ungated `snakemake -n` was reverted, since a Snakefile runs Python.

## 0.7.0 to 0.9.15 - 2026-09-30 to 2026-10-03

Summary: the skills, the approval gate, run receipts, pinned inputs, and `verify` were built up over these versions. There is no 0.9.13. See `git log` for details.
