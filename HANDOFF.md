# Handoff — mycelium-extra feature work

**Date:** 2026-10-04 · **Branch:** main @ 6f2eddb · **Status:** v0.9.28 committed and installed (.qmd/.Rmd chunk lint); next item not chosen.

## Goal
Grow mycelium-extra so that it complements Mycelium without overriding it. Each feature is grilled (`/mycelium-extra:grill`), approved, built with tests, then committed as `feat`/`fix` + `chore: bump version`.

## Next action
Ask the user to pick from "Open items" (suggested: pip packages inside conda envs, ~20 min), then run `/mycelium-extra:grill <item>`.

## State
- Uncommitted: only this file (never committed; that's the user's call).
- Tests: all pass on Python 3.6.8 and 3.12. Run `python3 hooks/tests/test_gate.py` and each `skills/*/tests/test_*.py` by name (the gate approves named paths, not globs); run `python3 hooks/tests/gate_diff.py` before and after touching gate.py (differences must be notice text only).
- Installed plugin: 0.9.28 (user scope); restart needed to load it. After a bump: `claude plugin marketplace update mycelium-extra`, then `claude plugin update mycelium-extra@mycelium-extra`, then restart.
- The gate is on in this repo: test runs need an approved plan naming the test files (approvals last 24 h).
- scilintr 0.1.2 probe venv lives in this session's scratchpad (volatile): `python3.12 -m venv X && X/bin/pip install scilintr`. It lints `.py` only (`_engine.py:125`).

## Shipped this round
- 0.9.16–24: ledger plan hash, `verify status`, notebook lint, conda snapshot, approval card, `verify explore` (see `git log`).
- 0.9.25–26 gate false positives (e39b83d, aa12019); 0.9.27 `.py` parse gap (e511d00).
- 0.9.28 `.qmd`/`.Rmd` r/python chunk lint (ea0d247): `chunk_code()` blanks non-chunk lines so findings cite the document line.

## Locked decisions
- Handoff goes to root `HANDOFF.md`, not `.mycelium/last-session.md` (Mycelium's Stop hook republishes that) (user, 2026-10-03).
- Hints are off by default, per repository (user, 2026-10-03).
- Remaining scilintr findings block verify; a missing, timed-out, unreadable or unparseable check is a gap, never clean (user, 2026-10-03).
- `harden` ships test files only (user, 2026-10-03).
- Dropped: gating Biomni/ToolUniverse MCP calls; verify reading ClawBio checksums (user, 2026-10-03).
- Don't prune approvals; approval-scan timeout denies; keep `GIT_OPTIONAL_LOCKS=0` and `not_a_run` receipts (user, 2026-10-01/02).
- Manifest column = `listed: <first status word>` / `listed` / `not listed`, matched by folder path or heading (user, 2026-10-03).
- Hook notices (`systemMessage`) are plain text: no markdown; card layout "B" (user, 2026-10-03).
- `.qmd`/`.Rmd` findings cite the document's own line, not `[chunk N]` (user, 2026-10-04).
- `eval=FALSE` chunks are linted; display blocks, other engines, inline `` `r x` `` are not (default, 2026-10-04).
- Explore outputs are never promoted to results; promotion = re-run under a new plan (default, 2026-10-03).
- Conda env read from `conda-meta`, not by running conda; only `conda-lock.yml` suppresses it; session `CONDA_PREFIX` only when a run declares no env (default, 2026-10-03).

## Dead ends — do not redo
- Perf: `.pyc` launcher, `python3 -S`, `$PWD` probe, gate daemon, rewriting `tokenize()` (measured, 2026-10-01). Box loadavg ~30: use paired A/B medians only.
- A mycelium-extra SessionStart message: competes with Mycelium's "SESSION RESUME" (`mycelium-health.sh:482`).
- Treating scilintr exit 0 as clean: it exits 0, silent, on a missing path, `.R`, `.ipynb`, `.qmd`, and code that does not parse.
- Running `conda list --explicit`: conda is not on PATH here.

## Read first
- `docs/development.md:5`: dev, test and version-bump rules (3 manifests; Python 3.6-compatible code).
- `hooks/gate.py`: `approval_card`, `on_stop`, `on_tool`, `on_post`.
- `skills/verify/scripts/verify.py`: `lint()`, `chunk_code()`, `notebook_code()`, `conda_snapshots()`, `status()`, `explore_runs()`, `check()`, `write()`.
- Memory: `backlog-2026-10`, `complement-mycelium-not-override`, `keep-mycelium-extra-local`, `show-layout-options`.

## Open items
- pip packages inside conda envs not recorded; snakemake `--use-conda` rule envs not recorded.
- Untested in real use: `hints`, `harden`, `verify stale/status/explore`, R scilintr CLI, R-kernel notebooks and `.Rmd` R chunks (no Rscript here).
- Parked chunk-lint cases: document-level `execute: eval: false`, `child=` docs, `knitr::read_chunk`, `{r engine=...}` — revisit if a real repo uses them.
- Known receipt gap: a Snakemake rule input counts as a run (roadmap E3b). Exit status now comes from the hook event (`PostToolUse` or `PostToolUseFailure`); Codex runs are unreceipted by design (no hooks in the Codex manifest).
