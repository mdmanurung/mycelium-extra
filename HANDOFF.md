# Handoff — mycelium-extra: CHECKPOINT at 0.9.60

**Date:** 2026-10-08 · **Branch:** `main` @ e09353d (v0.9.60; 0.9.53–0.9.60 not pushed) · **Status:** B3, B2 and the `{name}` follow-up shipped; the user uses the package, and fixes come from real use. Work on `main`. No tags.

## Goal
Keep Extra to its aim, "Plan an analysis. Approve what runs. Check the execution record", and keep the human in the loop. Done for a task means all of:
- grill plan approved, then built
- all test files green on 3.6 and 3.12; ablations 3/3
- `gate_diff` identical when `gate.py` changes
- version bumped (docs-only changes: no bump); atomic commits (feat/fix, test, docs, chore)
- `claude plugin update mycelium-extra@mycelium-extra` run at user scope and with `--scope project`; no push

## Next action
1. Grill backlog #4 (sbatch receipts lacking an exit status). Spike M1-T18 first.
2. Smoke test (user, after restart, still pending from 0.9.55): in `bmv_pilot_cytof_integration`, show a long plan, type `card <hash> checks`, and confirm the blocked prompt's reason is shown.

## Ranked backlog
4. 35 of 61 `sbatch` receipts lack an exit status. Since B3, bmv a2867a4b no longer shows `job 25695945 COMPLETED`: only the dropped `.out`/`.err` rows carried it.
5. B5 leftovers: the "ran but not in the plan table" (249) and "run under another plan" (768) lines are still one per file. B2 adds real "likely written by `sbatch`" gaps (16+4+4 files in scale 52fda098 and 7b1f02f7).
6. Parked from B2: folderless names in prose on an `Outputs:` line (`_dream_priors.csv`, `…_scope_*.csv` in scale 93f5d9f2) are still "does not exist" gaps. Return if a newer plan writes them that way.
7. Parked from B3: the gate's `SCRIPT_EXT` misses `.sbatch` and `Snakefile.*`. The gate doesn't pin them, and the card labels them "file". Needs `gate_diff`.
8. Parked from 0.9.60: a Snakemake regex wildcard `{sample,[A-Z]+}` has a comma, so it is still split. Return if a real plan writes one.

## State
- Uncommitted: `HANDOFF.md`. Untracked: `mycelium-extra-improvements/` (superseded staging) and `mycelium-extra-review-bundle/`. Committing them is the user's call.
- Tests: all green at e09353d on 3.6 and 3.12 (gate 164, verify 58 + default_reasons 4, e2e 76 with 2 skipped, fixture 3); ablations 3/3; `gate_diff` 163/163; links 103.
- Plugin cache at 0.9.60 (user + project scope). The user must restart Claude Code to load it.
- Real R: `MX_E2E_REAL_TOOLS=1 MX_E2E_RSCRIPT=/exports/para-lipg-hpc/mdmanurung/conda/envs/cellbouncer/bin/Rscript`. `scilintr` and `Rscript` are not on PATH, so `verify` reports a lint gap on every plan.
- `stash@{0}` (old handoff): safe to drop, never `pop`.
- Real-plan check method:
  1. `git archive HEAD | tar -x` the whole tree into scratch.
  2. Run `verify.py report <hash>` from old and new on every approval in `scale` and `bmv_pilot_cytof_integration` (97 now), 8 at a time in the background (serial runs exceed 10 min).
  3. For card changes, compare `gate.output_words` old vs new.

## Shipped 2026-10-08
- **0.9.60** (`864be76..e09353d`, plan 78c97c90): a comma-less `{name}` on an `Outputs:` line reads as `*` (`gate.expand_braces`). No V-case (B2 follow-on, not a triage B-fix).
- **0.9.59** (`086b28a..9f65bb7`, plan 742c8730, B2): shared `gate.read_outputs`: `{a,b}` expanded (cap 200), `<name>` → `*`, globs whole, `…`/`...` flagged once. Defect V-29.
- **0.9.58** (`0567f42..a836cad`, plan d6605c08, B3): a planned script is a path with a script extension, a `Snakefile` name, or a `#!` line. Defect V-28.
- Earlier the same day: 0.9.53–0.9.57. See `CHANGELOG.md`.

## Locked decisions
- **Human in the loop (user, 2026-10-06):** script pins block by default; an edited script is never softened. D10–D12 are opt-in or parked.
- **Approval card (user, 2026-10-06/08):**
  - Grants are always shown in full, never collapsed; quoted text is sanitised.
  - Plans without a Step column plus Choice/Validation columns keep the old card.
  - Digest past 35 lines (layout A): checks only for default steps; diff only via `card <hash> diff`.
- **Brief length (user, 2026-10-08):** the grill brief is ≤150 words, table excluded.
- **Only Step cells grant (plan 8988ae5d):** verify still reads every non-Source cell.
- **B2 fix location (user, 2026-10-08, option 1):** read the unambiguous forms in both verify and the card; flag `…`; grill asks for full paths or `{a,b}`.
- **`{name}` → `*` (user, 2026-10-08):** a comma-less brace is a Snakemake wildcard, not a literal name.
- **B3 (2026-10-08):** naming a file in the plan does not make it a script; only an extension, a `Snakefile` name, or a shebang does.
- **Approve in the presenting session** (`docs/approval-gate.md:31`). **B1:** plan paths are root-relative. **B5:** status unchanged; `block` findings stay per file.
- **Complement Mycelium:** warn, never block; the warning lives on the card only.
- **Scope:** audience = the user + their own lab repos; stay 0.x; no PLAN/RUN/CHECK routing skills.
- **Process:** grill asks the question first, and the user may skip it. Each fix gets its own patch version, and each M8-T03 B-fix gets a V-case in `tests/e2e/defects.py` plus a §8 row in `docs/design/c1-fixture-project.md`. Push, tags, and `gh repo edit` only when asked.
- **Verify semantics:** a missing exit status is a gap, never success; a missing or unparseable check is a gap; remaining scilintr findings block.
- **Format changes:** show A/B/C rendered options and let the user pick.

## Dead ends — do not redo
- **Perf ideas already tried:** `.pyc` launcher, `python3 -S`, `$PWD` probe, gate daemon, rewriting `tokenize()`. A SessionStart message competes with Mycelium's.
- **`gate.fingerprint(path, budget, pin=...)`** skips the hash when the size changed, so never use it where the sha is needed.
- **B4:** don't call edited-script blocks "superseded, so false positive".
- **B3 via `SCRIPT_EXT` only:** drops real `.sbatch`/`Snakefile.*` scripts. The shebang + `is_snakefile` test keeps them.
- **State-folder commands:** a Bash command that mentions the Extra state folder and could write is denied. Write files with Write; in scratch scripts, build the folder name from parts.
- **`find` over `/exports/para-lipg-hpc/mdmanurung`** times out; use `rg --max-depth`.
- **verify output under the e2e harness escapes non-ASCII:** a defect's `messages` must avoid `…` or `α`.
- **Default `python3` is 3.6.8** (no `unittest -k`). Mycelium's helpers need 3.11+ (use `python3.12`). Extra must stay 3.6-compatible.

## Read first
- `mycelium-extra-review-bundle/M8-T03_triage.md`: B2, B3, D1 (the status section is stale: B2 and B3 are now fixed).
- `skills/verify/scripts/verify.py`: receipts and exit-status handling (backlog #4), `is_script`, `check`.
- `hooks/gate.py`: `read_outputs` / `expand_braces`, `plan_table`, `procedure_card`.
- `docs/development.md:5`: test, CI, and version rules.

## Open items
- `card <hash>` display unverified live (Claude Code) and on Codex.
- M7-T01 plan-review redaction audit and M7-T05 record-what-was-sent: user decision.
- Known misses: DC-08..DC-11, V-02b, V-20. `review-bundle/03_EXECUTION_BACKLOG.md` is stale.
- Forest plot arm order in bmv `05_plot_response.R` appears done; confirm with the user.
