# Changelog

All notable changes to mycelium-extra are listed here, newest first. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are the `version` in the three plugin manifests. Entries from 0.9.16 to 0.9.29 were rebuilt from `git log`.

## [Unreleased]

## [0.9.32] - 2026-10-04

### Fixed

- Non-ASCII text no longer breaks anything on Python 3.6 with a non-UTF-8 locale (`LC_ALL=C`). Before this, the gate's Stop hook failed on any plan with an `α` or an em dash, so that plan could not be approved, and `verify write` crashed on it.
  - The gate reads each hook event as UTF-8, which is what Claude Code sends; before, 3.6 decoded it to lone surrogates.
  - Every text file the gate, `verify`, `init`, `data-contract-check`, and `new-analysis` read or write is `utf-8`. `verify` and `new-analysis` write with `surrogateescape`, so a non-ASCII analysis name or path is written as its original bytes; `new-analysis` no longer stops halfway through a scaffold.
  - `git`, `sacct`, and scilintr output is decoded as `utf-8`, with bad bytes replaced.
  - `verify`, `decision-status`, `data-contract-check`, and plan-review's `default_reasons.py` print non-ASCII to an ASCII stdout as `α` and so on, instead of crashing.

  On a UTF-8 locale nothing changes: `gate_diff.py` reports 148/148 identical under both `LC_ALL=C` and `en_US.UTF-8`. The end-to-end harness now sends events as raw UTF-8 and its plan has an `α`; a new `decision-status` test runs under an ASCII locale on any Python.
- `LICENSE` and `docs/roadmap/01-packaging.md` now spell the copyright holder "Mikhael Manurung", the name both plugin manifests already carry. `.claude-plugin/marketplace.json` names the owner `mdmanurung` and is unchanged.

## [0.9.31] - 2026-10-04

### Fixed

- `verify` and `new-analysis` no longer crash on a machine whose `python3` is 3.6 and whose locale is not UTF-8. `verify` wrote a middle dot in its report header, its `PROVENANCE.md` row, and its stale listing, which raised `UnicodeEncodeError` on an ASCII stdout; the separator is now `-`, and old `PROVENANCE.md` files still parse because the row is split on `|`. `new-analysis` read its templates with the locale's encoding and raised `UnicodeDecodeError` before writing anything; its reads and writes now name `utf-8`. `tests/test_end_to_end.py` passes as a result.

## [0.9.30] - 2026-10-04

### Added

- MIT `LICENSE`, named in both plugin manifests.
- `CHANGELOG.md`; a version bump now adds an entry here.
- Gate: the receipt hook also runs on `PostToolUseFailure`, so a failed command leaves a receipt with its exit code (`Exit code N`), `failed`, or `interrupted`; receipts gain `exit_source`, `error_line`, and `background`.
- `data-contract-check`: reads the `obs` of an `.h5ad` file through h5py (a gap without it); `batch_confounding` prints the batch-by-contrast table on every run and takes an optional `max_share` warning; exit 3 means a gap with nothing blocking.
- `plan-review` and `verify`: an advisory check that names each plan row whose `default:` has no reason, a reason under three words, or only an empty phrase such as `standard`.
- Tests: an end-to-end fixture project (`tests/fixtures/mycelium-project/`, simulated data and its generator) and a harness that replays the gate's hooks through a full grill-approve-run-verify chain.

### Changed

- `verify`: a run's exit 0 is taken from the hook event, so an ordinary run conforms; an `unknown` exit status is a gap; a run under Codex is stated to be unreceipted.
- The README is a landing page; skill, gate, Mycelium, and development details moved to `docs/`.
- The README summary table says that `plan-review` sends a packet to Codex and Biomni after you agree.

### Fixed

- Gate: a state-folder name that only reaches written text (`os.path.join(x, '.mycelium-extra')` passed to `.write()`, a `sed -i` script word) no longer denies the command; Python the running interpreter cannot parse is scanned token by token before the any-mention rule.
- Gate: `sbatch -D`/`--chdir` with `--wrap` resolves the payload's scripts against that folder, and the folder is no longer read as a gated path.
- Tests: the verify and gate tests hide the host's conda and virtualenv variables and `~/.conda`.

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
