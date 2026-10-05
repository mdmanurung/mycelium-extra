# Handoff — mycelium-extra: A2 CI written and checked locally; first GitHub run waits on a push

**Date:** 2026-10-05 · **Branch:** `improvements` (v0.9.33 + C1 steps 3-5 + A2 CI, no bump), `main` at v0.9.32, ahead of `origin/main` (3a11123, v0.9.28) · **Status:** the 24-patch series plus the name and handoff commits are landed locally and green. Nothing pushed, tagged, or sent to `gh`.

## Goal
Work the roadmap the series adds. C1 is done, A2 is written; next from `IMPLEMENTATION-MAP.md` "Do now": E1 (pip/rule envs) or B2.

## Next action
Ask the user (a) whether to push a branch of their own repo and open a PR so A2's acceptance can run (green on both legs, plus one deliberately failing gate_diff run as evidence), and (b) which of E1, B2 comes next.

## State
- A2 at `24819a7`: `.github/workflows/ci.yml` (containers `python:3.6-bullseye` under `LC_ALL=C` and `python:3.14-bookworm`; `gate-diff` job on PRs with `fetch-depth: 0` and `safe.directory`), `tests/test_versions.py`, `tests/check_links.py` (moved from staging; exit 2 with no file, skips `@@...@@`). Checked in a fresh clone on 3.6 and 3.12: 13 test files OK, ablate 3/3, links 45/0, `gate_diff --base main` 160/160, and dropping `rm` from `WRITE_ALL` gives exit 1 with 3 FAIL. 3.14 itself not run here (no interpreter); no removed AST/stdlib APIs found by grep. Roadmap A2 status: in-progress.
- C1 steps 3-5 landed on `improvements`: `ac83c96` (DC-01..11, G-01..07, catalog 1/3/5), `716a149` (V-01..20, S-01..03, M-01, catalog 2/4), `2c19fb1` (KB-01..06 as plain asserts, `ablate.py`). `tests/test_end_to_end.py`: 60 OK on 3.6 and 3.12; `ablate.py`: 3 of 3 bite. Design doc updated where code differed (DC-03, G-03, V-12, V-13, new V-19/V-20, 8.5, 10). `main` not yet fast-forwarded to these.
- `main` is at `2e9e177` (E3 done, v0.9.33); `improvements` is 4 commits ahead (C1 steps 3-5 + this handoff). Fast-forward with `git fetch . improvements:main` when the user says so. `origin/main` is still 3a11123 (v0.9.28) — nothing was pushed.
- All 12 unit test files plus `tests/test_end_to_end.py` and `tests/test_fixture_data.py` pass on Python 3.6.8 (re-run 2026-10-05 after C1). Skips: 7 in `test_data_contract_check.py` (no h5py), 1 in `test_new_analysis.py` (`test_r_stub_fails_loudly`, no Rscript). `test_gate.py` 102/102, `test_verify.py` 33 OK.
- `gate_diff.py --base 3a11123`: 127/160 identical. 30 differences are receipt state (`exit_source`, `exit_status: null` → `"unknown"`, `sbatch --wrap` paths, the 6 hook-event cases); the other 3 are the E2 text commands, which pass now (`out`). The 3 E2 write twins still deny. Against HEAD: 160/160.
- Uncommitted: only `mycelium-extra-improvements/`, untracked on purpose — a staging folder, not part of the change.
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
- **Verify gap found by C1 (not a case yet):** a plan that names only the Snakefile gets a direct receipt for it, so an `incomplete: true` rule is never reported (`verify.py:686` `if direct:` wins over `elif inside:`). V-13 works around it by keeping the steps in the plan table.
- Known misses recorded as tests (flip on purpose when fixed): DC-08 sign flip, DC-09 positional join, DC-10 Excel gene names, DC-11 CPM, V-02b partial output under `|| true`, V-20 output credited to an earlier run of the same plan.
- **B2:** move the dated verify history to the changelog. No longer blocked.
- Unrecorded: pip packages inside conda envs; snakemake `--use-conda` rule envs. `sbatch -o/-e/-i` values under gated paths are probably denied wrongly.
- `init --paths` with a non-ASCII glob on Python 3.6 under `LC_ALL=C` stores it as `\udcXX` escapes in `gate.json` (argv arrives as surrogates). It does not crash, but the glob will not match on a UTF-8 locale. Rare: Mycelium names analyses in ASCII.
- Untested in real use: `hints`, `harden`, `verify stale/status/explore`, R scilintr CLI, R-kernel notebooks and `.Rmd` R chunks (no Rscript here); D6's h5ad path (no h5py here). Parked chunk-lint cases: document-level `execute: eval: false`, `child=`, `knitr::read_chunk`, `{r engine=...}`.
