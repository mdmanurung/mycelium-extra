# Handoff — mycelium-extra: CHECKPOINT at 0.9.57

**Date:** 2026-10-08 · **Branch:** `main` @ 6342836 (v0.9.57; 0.9.53–0.9.57 not pushed) · **Status:** user uses the package; fixes come from real use. B1 (0.9.46), B4 (0.9.47), approval card (0.9.48), card baseline (0.9.49), B5 grouped output attribution (0.9.50), card diff at the bottom (0.9.51), `.gitignore` warning (0.9.52) done. Work on `main`. No tags.

## Goal
Keep Extra to its aim, "Plan an analysis. Approve what runs. Check the execution record", and keep the human in the loop. Done for a task = grill plan approved, built, all test files green on 3.6 and 3.12, ablations 3/3, `gate_diff` identical when `gate.py` changes, version bumped (docs-only: no bump), atomic commits (feat/fix, test, docs, chore), no push.

## Next action
None while the user uses the package. In a gated repo, show a long plan and type `card <hash> checks` to confirm Claude Code shows the blocked prompt's reason, then use it on real analyses. Resume from what use turns up; candidates are in Open items. Any new work starts with a grill plan ending `Plan status: READY_WITH_ASSUMPTIONS`.

## State
- Uncommitted: `HANDOFF.md`; untracked `mycelium-extra-improvements/` (old staging, superseded) and `mycelium-extra-review-bundle/` (plans + `M8-T03_triage.md`; commit is the user's call).
- Tests: all green at de65d19 on 3.6 and 3.12 (gate 160, verify 56, e2e 74, ablations 3/3, `gate_diff` 163/163, links 102, versions OK).
- Plugin updated to 0.9.57 (user and project scope, 2026-10-08); rerun `claude plugin update mycelium-extra@mycelium-extra` after each version bump.
- Real R: `MX_E2E_REAL_TOOLS=1 MX_E2E_RSCRIPT=/exports/para-lipg-hpc/mdmanurung/conda/envs/cellbouncer/bin/Rscript`; `scilintr` and `Rscript` are not on PATH by default, so `verify` reports a lint gap on every plan.
- `stash@{0}` (old handoff): safe to drop, never `pop`.
- Scratch tools (session scratchpad, may be gone): `cards.py` (old vs new card on the 56 real plans), `coexist.py` and `mycgate.py` (Mycelium + Extra hooks side by side). Method for card changes: render all 56 approved plans of `scale` and `bmv_pilot_cytof_integration` with `git archive HEAD` code vs working tree; copy `.gitignore` into the temp root (git ignores a symlinked one).

## Shipped this session (one line each)
- 0.9.53 (`cea3471..64c7d6d`): handoff carries a pending grill plan word for word (points to `.mycelium-extra/pending/<session>.json`, found by content); new session reprints it, same text = same hash.
- 0.9.54 + 0.9.56: grill brief ≤150 words; table, quoted question, Inputs/Outputs/Facts/status lines, guards and flagged Evidence exempt.
- 0.9.57 (`6aec93b..6342836`, plan 8988ae5d): only the Step column grants; headerless tables as before; verify reads every cell (`every_cell=True`). 5 of 95 real plans lose a Choice-cell grant; their verify reports are identical.
- 0.9.55 (`fc63eff..baab2c9`): card >35 lines becomes a digest; `card <hash> checks|diff|full` (UserPromptSubmit `decision: block`) shows the rest. 86 real plans: median 40→31, max 83→43.
- 0.9.50 B5 (`52be169..7c2482f`): `describe_run` (`skills/verify/scripts/verify.py:589`) names the script when a long interpreter path hides it; outputs not tied to the plan's runs give one gap per (producing run, folder). 9,883 per-file lines became 466 grouped + 57 singles on real repos.
- 0.9.51 (`c2d303c..cf467fb`): the changed-script summary stays on top of the card; the diff (30 lines max) sits above `▶ approve plan`. `Question` line moved from ~41 to ~10. `script_state` returns (pinned, summary, diff).
- 0.9.52 (`29de37d..6baa9aa`): the card warns when `.living/` exists in a git repo and `.mycelium-extra/` is not ignored (`state_unignored`, `UNIGNORED` in `hooks/gate.py`). Never blocks.
- Mycelium co-existence audit (no commit, no conflict found): Mycelium 0.7.2 and Extra hooks run in parallel without interference; state folders are apart (`.mycelium/`, `.living/` vs `.mycelium-extra/`); the gate allowed all 21 `.living/`, `.mycelium/` and Mycelium-script commands it was fed and denied only an unplanned analysis run. Not exercised: Mycelium's post-action directive and its stop block never fired in the harness.

## Locked decisions
- **Human in the loop (user, 2026-10-06):** script pins block by default; an edited script is never softened. D10–D12 stay opt-in/parked.
- **Approval card (user, 2026-10-06):** layout A+B; Evidence lines with fail/flag; steps marked done show "agent says: done"; baseline from approval history, any age; grants always printed in full, never collapsed; quoted plan text sanitised; plans without Step plus Choice or Validation columns keep the old card; diff block at the bottom, summary on top (0.9.51). **Digest (user, 2026-10-08, layout A):** cards past `CARD_LINES` (35) show the digest; the diff only behind `card <hash> diff`; grants still in full.
- **Brief length (user, 2026-10-08):** grill brief at most 150 words, plan table excluded.
- **B1 (user):** plan paths are root-relative; absolute-in-root accepted and normalised.
- **B5 (user):** goal "so that i know which file produce with output"; status unchanged; `block` findings stay per file.
- **Complement Mycelium (user):** warn, never block, on Mycelium interplay; the warning lives on the card only, not in `verify`.
- **Scope (user):** benchmark shrunk to Extra's own claims; Track R optional; consume Mycelium's records first; audience = user + own lab repos; stay 0.x; no PLAN/RUN/CHECK routing skills. Filter `G13` in `mycelium-extra-review-bundle/02_ARCHITECTURE_AND_PRINCIPLES.md`.
- grill asks the question first in free text and the user may skip it; each fix = own patch version; push, tags, `gh repo edit` only when asked; never base a PR on 3a11123.
- Missing exit status is a gap, never success; a missing or unparseable check is a gap; remaining scilintr findings block.

## Dead ends — do not redo
- Perf: `.pyc` launcher, `python3 -S`, `$PWD` probe, gate daemon, rewriting `tokenize()`. A SessionStart message (competes with Mycelium's).
- `gate.fingerprint(path, budget, pin=...)` skips the hash when the size changed: never use it where the sha is needed.
- Calling edited-script blocks "superseded, so false positive": none was covered by an approval (B4).
- Commands that write and mention the Extra state folder are blocked by the gate even in scratch: write files with the Write tool, run scratch scripts by path (the folder name built from parts inside the script).
- `find` over `/exports/para-lipg-hpc/mdmanurung` (times out; use `rg --max-depth`); testing the locale bug on Python ≥ 3.7.
- Rotating single check on the card, short card plus a file (review panel rejected both). Superseded for long cards by the user's digest choice (2026-10-08): on-demand `card <hash>` prompt, no file.
- Two foreign runs in `test_verify.py`: owner is the earliest receipt within `TOLERANCE` (5 s), so back-date receipts with `stamp_last_receipt`.
- Default `python3` here is 3.6.8; Mycelium's helpers need 3.11+ (`from datetime import UTC`). Use `python3.12` for them; Extra must stay 3.6-compatible.

## Read first
- `mycelium-extra-review-bundle/M8-T03_triage.md` — triage; B2, B3, D1 open (B1, B4, B5 done).
- `hooks/gate.py` `procedure_card`, `approval_card`, `script_state`, `state_unignored`; `skills/verify/scripts/verify.py:589` (`describe_run`), `~1262-1300` (grouped attribution gaps).
- `docs/development.md:5` — test, CI, version-bump rules (Python 3.6). `tests/e2e/defects.py` and `docs/design/c1-fixture-project.md` §8: update both when a defect case changes.

## Open items
- **B5 leftovers (parked):** "ran but not in the plan table" (249 gaps) and "run under another plan" info lines (768 across 56 plans) are still one line each.
- **M7-T01** plan-review redaction audit (first grill question asked twice, unanswered); **M7-T05** record what was sent: user decision.
- **M1-T18 spike:** hook payload fields keying `PreToolUse` to `PostToolUse`; Mycelium lineage vs receipts.
- Known misses: DC-08..DC-11, V-02b, V-20. 35 of 61 `sbatch` receipts have no exit status.
- `review-bundle/03_EXECUTION_BACKLOG.md` is stale (Snakefile claim, execution queue).
- Parallel lanes (planned, not started): A B2/B3 (`verify.py`), B M7-T01/T02 (`skills/plan-review/`), C M3-T11/T12 (`skills/data-contract-check/`), D read-only spike M1-T18. One worktree per lane, no version bump on a branch, pre-assign defect IDs.
- Forest plot arm order (outside Extra) appears done in bmv `05_plot_response.R` (PfGA2_GA1, PfGA2_GA2, CVTU3, MAVAC, TUCM2, EG, TZ); confirm with the user.
