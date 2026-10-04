# Handoff — mycelium-extra: the series is on `main`; the four decisions are answered

**Date:** 2026-10-04 · **Branch:** `improvements` (v0.9.33, uncommitted), `main` at v0.9.32, ahead of `origin/main` (3a11123, v0.9.28) · **Status:** the 24-patch series plus the name and handoff commits are landed locally and green. Nothing pushed, tagged, or sent to `gh`.

## Goal
Work the roadmap the series adds, starting with C1 steps 3–5. Done = `ablate.py` exists and the catalog tests run.

## Next action
`mycelium-extra-improvements/IMPLEMENTATION-MAP.md` → C1 step 3 (defect layers). It is the keystone: A2, A6, C3, D1, D4 and E4 all wait on it.

## State
- `main` and `improvements` point at the same commit. `origin/main` is still 3a11123 (v0.9.28) — nothing was pushed.
- All 12 test files pass on Python 3.6.8. Skips: 7 in `test_data_contract_check.py` (no h5py), 1 in `test_new_analysis.py` (`test_r_stub_fails_loudly`, no Rscript). `test_gate.py` is 102/102. `test_verify.py` was re-run after the name fix: 32 OK. The other suites were not re-run; the commits since are docs only and no test reads `LICENSE` or `CHANGELOG.md`.
- `gate_diff.py --base 3a11123`: 127/160 identical. 30 differences are receipt state (`exit_source`, `exit_status: null` → `"unknown"`, `sbatch --wrap` paths, the 6 hook-event cases); the other 3 are the E2 text commands, which pass now (`out`). The 3 E2 write twins still deny. Against HEAD: 160/160.
- Uncommitted: E3b (0.9.33: `verify.py`, `test_verify.py`, docs, roadmap, manifests, `CHANGELOG.md`, this file), and `mycelium-extra-improvements/`, untracked on purpose — a staging folder, not part of the change.
- `stash@{0}` ("session handoff (pre-series)", on main) holds the pre-series handoff. Everything in it is carried forward; it can be dropped. Do not `git stash pop` — it conflicts with the series' HANDOFF edits.
- Installed plugin updated 0.9.28 → 0.9.31 (user scope, 2026-10-04); it needs a Claude Code restart to take effect, so a session started before that still runs 0.9.28. The `mycelium-extra` marketplace is the **folder** `/exports/para-lipg-hpc/mdmanurung/mycelium-extra`, not GitHub, so staying local never blocks an update: `claude plugin marketplace update mycelium-extra`, `claude plugin update mycelium-extra@mycelium-extra`, restart.
- The gate is on here and blocked nothing this session.

## Locked decisions
- **A missing exit status is a gap, for both `"unknown"` and old `null` receipts** — no code change; the `else` at `verify.py:689-692` keeps covering both, and `test_verify.py:131` stays as written. The 3a11123 gate read the exit code from the tool response alone, with no background or interrupt flag, so a `null` cannot tell "finished OK" from "only started" or "cut off" (default, 2026-10-04).
- **Tags: deferred, not created.** `notes/docs.md` now carries all 16 commands. Its v0.9.29 sha was wrong — `1db67c1` never existed outside a deleted scratch clone; the real bump is `4f5ab08`, whose subject is just "chore: bump version". v0.9.30 = `49f9154`, v0.9.31 = `573fbdb`. `main` fast-forwarded, so all three shas are stable and the tags are safe whenever wanted (user, 2026-10-04).
- **Stay local.** No push, no `git push --tags`, no `gh repo edit` (the description/topics line in `APPLY.md` decision 3 is unrun). The `keep-mycelium-extra-local` memory now says what it meant: no upstream Mycelium issues or PRs; push their own repo only on request (user, 2026-10-04).
- **Name: "Mikhael Manurung"** everywhere — the manifests' spelling won, so `LICENSE` and `docs/roadmap/01-packaging.md` changed and no version bump was needed (user, 2026-10-04).
- Handoff goes to root `HANDOFF.md`, not `.mycelium/last-session.md` (user, 2026-10-03).
- Hints off by default, per repository (user, 2026-10-03).
- Remaining scilintr findings block verify; a missing, timed-out, unreadable or unparseable check is a gap, never clean (user, 2026-10-03).
- `harden` ships test files only (user, 2026-10-03).
- Dropped: gating Biomni/ToolUniverse MCP calls; verify reading ClawBio checksums (user, 2026-10-03).
- Don't prune approvals; approval-scan timeout denies; keep `GIT_OPTIONAL_LOCKS=0` and `not_a_run` receipts (user, 2026-10-01/02).
- Manifest column = `listed: <first status word>` / `listed` / `not listed`, by folder path or heading (user, 2026-10-03).
- Hook notices (`systemMessage`) are plain text, no markdown; card layout "B" (user, 2026-10-03).
- `.qmd`/`.Rmd` findings cite the document's own line, not `[chunk N]` (user, 2026-10-04).
- `eval=FALSE` chunks are linted; display blocks, other engines, inline `` `r x` `` are not (default, 2026-10-04).
- Explore outputs are never promoted to results; promotion = re-run under a new plan (default, 2026-10-03).
- Conda env read from `conda-meta`, never by running conda; only `conda-lock.yml` suppresses it (default, 2026-10-03).
- verify's separator is ASCII ` - `, not `·`: the `PROVENANCE.md` row is split on `|`, so old files still parse and `|` would break the table (default, 2026-10-04).

## Dead ends — do not redo
- Perf: `.pyc` launcher, `python3 -S`, `$PWD` probe, gate daemon, rewriting `tokenize()` (measured, 2026-10-01). Box loadavg ~30: paired A/B medians only.
- A mycelium-extra SessionStart message: competes with Mycelium's "SESSION RESUME" (`mycelium-health.sh:482`).
- Treating scilintr exit 0 as clean: it exits 0, silent, on a missing path, `.R`, `.ipynb`, `.qmd`, and code that does not parse.
- Running `conda list --explicit`: conda is not on PATH here.
- Testing the locale bug on Python ≥ 3.7: PEP 538 coerces the C locale to UTF-8 and hides it. Use a real 3.6 interpreter.
- `git format-patch -N <commit>`: exports the N commits **ending at** that commit. Use `A..B` with `--start-number`.
- `gate_diff.py --base 1db67c1` (cited in `APPLY.md`): that commit lived only in a deleted scratch clone. Use `--base 3a11123`.
- `git switch main` with `HANDOFF.md` dirty: refused, because series commits touch it. `git fetch . improvements:main` fast-forwards `main` without switching and refuses anything that is not a fast-forward.

## Read first
- `mycelium-extra-improvements/IMPLEMENTATION-MAP.md` — the 33 remaining tasks and the build order.
- `mycelium-extra-improvements/APPLY.md` — "Not done yet" and the maintainer decisions, at the end.
- `docs/development.md:5` — dev, test and version-bump rules (3 manifests; Python 3.6-compatible code).
- `hooks/gate.py`: `approval_card`, `on_stop`, `on_tool`, `on_post`. `skills/verify/scripts/verify.py`: `lint()`, `chunk_code()`, `status()`, `check()`, `write()`.
- Memory: `backlog-2026-10`, `complement-mycelium-not-override`, `keep-mycelium-extra-local`, `show-layout-options`.

## Open items
- **C1 steps 3–5** (defect layers, catalog tests, `ablate.py`): the keystone. Add the known-miss case from `APPLY.md`: with output times not spaced, verify credits an output to the wrong run of the same plan and still says CONFORMS. KB-04, KB-05 and KB-06 (`docs/design/c1-fixture-project.md` §8.5) are fixed now: write them as plain asserts, not `expectedFailure`, or the suite reports FAILED on an unexpected success.
- **B2:** move the dated verify history to the changelog. No longer blocked.
- Unrecorded: pip packages inside conda envs; snakemake `--use-conda` rule envs. `sbatch -o/-e/-i` values under gated paths are probably denied wrongly.
- `init --paths` with a non-ASCII glob on Python 3.6 under `LC_ALL=C` stores it as `\udcXX` escapes in `gate.json` (argv arrives as surrogates). It does not crash, but the glob will not match on a UTF-8 locale. Rare: Mycelium names analyses in ASCII.
- Untested in real use: `hints`, `harden`, `verify stale/status/explore`, R scilintr CLI, R-kernel notebooks and `.Rmd` R chunks (no Rscript here); D6's h5ad path (no h5py here). Parked chunk-lint cases: document-level `execute: eval: false`, `child=`, `knitr::read_chunk`, `{r engine=...}`.
