# 08 · Working scope, amendment and freeze (0.11.0 tracker)

Objective: an approval is a working scope. The researcher edits listed scripts without a block, and reviews code once, at `freeze <hash>`, before a reportable rerun. Audited against `267d9e2` (0.10.2) on 2026-10-18; the layouts were chosen by the user (re-pin C, amendment B, freeze C) and the post-freeze rule too (edits keep re-pinning).

Statuses: **done**, **in progress**, **todo**, **parked**.

As built, two details differ from the first draft: freeze C's verify preview became `Gaps now`, a `verify report` run in a child process with a 4 s limit that leaves out unfrozen code and the linter; and the `gate_diff` expectations were re-based on 0.10.2 (`267d9e2`) with `--write-expect`, so the file now holds only this release's four reviewed differences (a script edit now re-pins, the amendment card, `freeze` and `approve amendment` are new). Python 3.9 is not installed here, so 3.9 syntax was checked by reading, not by running.

## Audit: what the first plan got wrong or left out

| # | Finding in the code | Consequence |
|---|---|---|
| A1 | `on_tool` read the pin as `approval.scripts` first, then the `script-pins` ledger (`gate.py` ~2854). Approvals and instances are immutable (C04). | Re-pins live in an append-only `repins/<hash>.jsonl`; `current_script_pin()` reads it. The approval file and instance are never rewritten. |
| A2 | Five readers of script pins: `on_tool`, `approved_script`, `script_state`, `baseline_lines.recorded`, verify `edit_evidence`; plus verify's script row. `provenance.py`, `opencode/index.js` and `hooks/codex.json` do not read them. | Only `on_tool` and `edit_evidence` follow the re-pin. The card readers keep the **approved** baseline on purpose: the card must show what the user has not seen. |
| A3 | Every hook timeout is 10 s, including `UserPromptSubmit`; the PreToolUse pin budget is `pin_seconds` (5 s). | The freeze card computes only diffs. The verify preview of freeze C must be cheap, lint off, read-only and fail open ("preview not computed (time)"). |
| A4 | `explore` runs record `explore_script_pins` and never check plan script pins. | Unaffected. The messages at ~3185 and ~3201 still say "re-approval" for protected test and exact-execution files, which stay blocked, so their wording stays. |
| A5 | Stale **inputs**, changed **validation** files, **exact-execution** mismatches and the run limit still deny. | Only scripts stop blocking. These four keep their order and text. |
| A6 | `gate_diff` has cases `tool script edited since approval` and `... newest plan pins it`; both flip from deny to allow. | They are new reviewed differences. The oracle also needs a procedure-card scenario (open item in HANDOFF). |
| A7 | `APPROVE` (`gate.py:46`) accepts only `approve` or `approve plan`. OpenCode passes prompts through unfiltered. | Accept `approve plan\|amendment\|freeze` as synonyms; no new state. |
| A8 | `freeze C` promises "status would be: ran as frozen after rerun". No instance exists yet, so that is a hypothesis. | Replace with what is computable: the open gaps of the current check, labelled as such. If that cannot run in budget the line says so. |
| A9 | The first plan said "steps 1, 2, 4 unaffected". The code has no dataflow between rows. | The rerun list is the changed scripts' rows plus every later row, unless a row's `Inputs:` and `Outputs:` words prove independence. The "stales" line names only outputs whose producer is `supported` (C05); others read "may be out of date". |
| A10 | `lint_before_stop` and two lint notices (`gate.py` 3091, 3627, 3692) say verify "blocks on any finding". | Fix the wording in M2. |

## Milestones

Order is fixed: each one lands on `v0110` as its own commit, tests green, before the next starts.

### M1 · Re-pin (done: `3ce080d`)
- Scope: an edit to a script the plan lists (or a first-run-pinned one) is let through, re-pinned in `repins/<hash>.jsonl` (snapshot kept), with the notice of layout C to the user and the agent. The numbers heuristic compares changed literals with the plan rows that name the script. Verify: a run of code no approval froze is a gap ("`freeze <hash>`"), plus one info line listing re-pins, plus `edit_evidence` knows re-pinned versions.
- Files: `hooks/gate.py` (`read_repins`, `current_script_pin`, `diff_numbers`, `plan_numbers`, `repin_notice`, `repin_scripts`, `on_tool`), `skills/verify/scripts/verify.py` (`approved_script_pin`, `repin_findings`, script row, `qualify`), tests in `hooks/tests/test_gate.py`, `skills/verify/tests/test_verify.py`.
- Exit: edit gives allow + notice + journal line, the approval file is byte-identical, verify reports the unfrozen run, a denied run (lint) re-pins nothing; whole `test_gate.py`, `test_verify.py`, opencode and codex suites green.

### M2 · Wording and small fixes (done: `db3e8da`)
- `lint_before_stop` / `lint_before_run` text: say what verify does with open findings (a gap, not a block).
- `docs/approval-gate.md` lines 24, 86, 91 and `docs/usage.md:157`: replace "cannot run until you re-approve".
- Exit: no doc or message in the repo says an edited script is blocked (grep).

### M3 · Amendment card (done: `f4f9bb5`)
- Scope: a branch of `procedure_card`: when `baseline_plan` finds an earlier approval and `compare_rows` shows only added rows (no changed, removed, reordered, columns, objective, inputs, blocks changed), the card is the layout-B delta: `Adds`, `Row`, `Reads/Writes`, `Grant`, `Unchanged`, then `▶ approve amendment <new hash>`. Any other difference falls back to the normal card, so the delta view never hides a change.
- It approves the amended plan's own hash and text. Nothing about the old approval changes.
- Files: `hooks/gate.py` (`procedure_card`, a small `amendment_delta`), `APPROVE` regex; tests for added-only, changed-row fallback, removed-row fallback, new input fallback.
- Exit: both card shapes covered; `gate_diff` card scenario added here.

### M4 · Freeze (done: `c3b971c`)
- Scope: the prompt `freeze <hash>` (answered by the hook like `card`, so the agent never sees it) builds a pending entry for that hash whose scripts are the current effective pins and whose card is layout C: per-script diffs against the approved pins, new scripts, unchanged inputs line, the rerun list (A9) and the open-gaps line (A8). `approve` / `approve freeze <hash>` writes a new approval record and instance with `scripts` = those pins (new `approved_at`, so older re-pins are history; the ledger is cleared as on re-approval). Runs after it belong to the new instance, so verify checks the new freeze and shows earlier runs as history.
- Refusals, each with one sentence: no approval for the hash; nothing changed since approval; inputs, validation or exact-execution changed (re-present the plan: not a freeze matter); more than 20 changed scripts (list, no diff).
- After a freeze, edits keep re-pinning (user decision, 2026-10-18). Instances get no `frozen` field.
- Files: `hooks/gate.py` (`on_prompt`, a `freeze_card`, `APPROVE`), `skills/verify` (none beyond M1 unless the preview reuses `check`), tests: freeze with edit, with new script, with nothing changed, with stale input, same bytes twice reuses the instance, approve then verify shows the new instance.
- Exit: edit → run → `freeze` → `approve` → rerun → `verify report` ends without the unfrozen-code gap.

### M5 · Docs, oracle, release (in progress: docs and manifests `18dd666`; oracle and suites below)
- `docs/approval-gate.md`, `docs/day.md` (the 13:00 "Review, then freeze" step), `docs/advanced.md`, `README.md`, `skills/verify/SKILL.md`, `skills/grill/references/run-plans.md` follow the code; CHANGELOG; version 0.11.0 in every place `tests/test_versions.py` checks.
- `gate_diff`: regenerate expectations on a scratch clone with the patched timeouts (HANDOFF), review each new difference, record them.
- Update memory (`human-in-the-loop-priority` is reversed; `researcher-first-redesign` status). Push only on request.
- Exit: whole suite green on 3.9, 3.11 `LC_ALL=C` and 3.12; `gate_diff` differences all reviewed.

## Out of scope for 0.11.0
- Blocking edits again after a freeze (the user chose re-pinning).
- Any change to input pins, validation bindings, exact execution or the run limit.
- OpenCode synthetic-message check, C12 evaluation, native host checks: unchanged from HANDOFF.
- A bmv session may have run a script on 2026-10-17 12:35–12:44 while the gate failed open: ask the user once; no code.
- Measurement on ~2026-10-31 (approvals per day, verify use, `denies.jsonl`, latency).

## Risks
- `diff_numbers` is a literal scan (strings, indexes count); it only raises a flag, never blocks. If it misleads, a per-language parser is the upgrade.
- A researcher can now run edited code under an approval that never saw it. The mitigations are the notice on every re-pin, the verify gap until a freeze, and the freeze card. They do not stop a reportable-looking result being quoted before verify: verify's summary row is where that shows.
- Load: the hooks hash scripts inside `pin_seconds`; a re-pin adds one hash and one journal line per edit.
