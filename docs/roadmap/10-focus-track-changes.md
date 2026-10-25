# 10 · Focus and track changes (0.13.0 tracker)

Objective: build milestones M0 to M2 of the focus and track-changes spec (2026-10-18, archived with this tracker's bundle at `plans/_DONE/mycelium_extra_focus_track_changes_complete_bundle/`) against the real code: a typed `focus` command and a read-only `track-changes` report. M3 (turn-end notice, `focus_id` in launches and receipts) and M4 (bounded evidence explanation) are built. The human usability study stays parked.

Statuses: **done**, **parked**, **dropped**.

## Baseline (M0, before any change)

0.12.0 at `62d4725`, python3.12, `LC_ALL=C`: gate 444 OK (2 skipped), verify 222, validation 27, codex 6, opencode 8, provenance 5, data-contract-check 99 (20 skipped), end-to-end 104, init 26, plan-review 47, every other test file OK. No failures. The spec was audited at `50b9ca0`; the five commits since touch none of its seams.

## Grammar

`focus analysis/<path> [plan <hash>]`, `focus switch analysis/<path> [plan <hash>]`, `focus status`, `focus end` (anchored, whole prompt). `track_changes.py --plugin-root <p> [--repo D] [--analysis A] [--original H] [--current H] [--transcript F] [--json] [--no-write]`.

## What is authority, advice, evidence, inference

| Kind | Where |
|---|---|
| Authority (unchanged) | approvals, instances, pins, re-pins, receipts, `freeze`, `verify` |
| Advisory | the focus record and the one context line it adds |
| Observed | plan row text, pin and file bytes, receipt fields, direct editor tool calls in a transcript |
| Potential | an analytical implication, a declared output possibly out of date |
| Unknown | shell edits, file reads, unmarked subagent work, run completion without an exit code |

## Steps

| Step | Deliverable | Status | Evidence |
|---|---|---|---|
| 1 | `hooks/focus.py`, `on_prompt` verbs and context line, `skills/focus` | done (`a4bb213`) | `test_focus.py` 17 OK on 3.6, 3.11, 3.12; `gate_diff` 173/173 identical, fuzz 253/253 |
| 2 | `skills/track-changes`: collector, card, brief, offline HTML | done | `test_track_changes.py` 26 OK; viewer run in Node against a DOM stub |
| 3 | Docs, README and index rows, handoff line | done | links checked |
| 4 | Version 0.13.0 | done | `test_versions.py` |

## Measured (python3.12, this host)

- Median wall time of one `gate.py prompt` for an ordinary prompt, 30 calls: 113 ms with no focus folder, 119 ms with a focus open, 119 ms for another session while the folder exists, 120 ms for `focus status`. About 6 ms from one small JSON read.
- `gate_diff` against `62d4725`: 173/173 identical; fuzz seed 1, 253/253. Fuzz seed 3 differed in 3 of 253 cases, but a control run of the unchanged base `gate.py` against itself differed in 17 of 253 at that seed, so that seed's fuzz is not deterministic and says nothing about this change.

## Real repositories (read-only dry run, 2026-10-19)

- Both repos keep analyses under `nbs/<topic>`, not `analysis/<name>`: `scale` had 158 plan hits for `nbs/09_factorizations` and none for any `analysis/` folder. The spec's `analysis/X` would have made both commands useless there, so a focus target is any existing folder under a gated root (`gated_paths`, default `analysis/` and `nbs/`). A sibling folder under the focus's parent is "another analysis".
- Busy folders name many plans (`scale` `nbs/09_factorizations` 44 of 45 approvals; `bmv` `nbs/cytof_exvivo` 80 of 99, `analysis/manuscript` 15), so `track-changes` there stops and asks for `--original`, listing the 8 newest with date and objective. Focusing a deeper folder, or `focus <folder> plan <hash>`, avoids the question.
- The work `focus status` does (all approvals, plan match for every folder, two active-approval scans) took 0.6 s for 99 approvals; the prompt hook allows 10 s. `track-changes` collect took 0.1 to 0.25 s per folder.

## Acceptance map (spec F01 to F32)

| ID | Where tested |
|---|---|
| F01, F28 | `test_focus`: no approval, expired approval, other session |
| F02, F07 | `test_focus`: missing, traversal, symlink, odd characters, no session id |
| F03, F05, F06 | `test_focus`: two sessions, history kept, prose not matched, crashed session |
| F08, F20 | `test_track_changes`: no snapshot, script absent from the original, re-pin count |
| F09, F10 | amended plan authorized; several candidate plans need `--original` |
| F11, F12 | numbers the plan already holds claim nothing; new numbers are potential only |
| F13 to F16 | transcript: other analysis, shared helper, shell not attributed, subagent contextual |
| F17 to F19 | failed then retried; unmatched launch; `sbatch` submission only |
| F22 | big transcript read in part, corrupt lines skipped, caps |
| F23, F24, F29 | hostile values, secret strings, no network, no `innerHTML`, copy-only buttons |
| F25 | nothing under `.mycelium-extra/` outside `track-changes/` changes |
| F26, F30, F32 | no gate; no observation is not "on task"; explicit analysis works without focus |
| F27 | `gate_diff` identical; codex and opencode suites unchanged |
| F04, F21, F31 | done (M3): `test_receipt_carries_the_focus_at_launch_not_at_completion`, `test_a_job_started_before_the_focus_is_never_assigned_to_it`, `test_the_turn_end_notice_is_opt_in_plain_and_told_once` in `hooks/tests/test_focus.py`; `gate_diff` 173/173 identical with `card_coverage` off |

## Decisions on the spec

- **Fewer moving parts than specified.** One `focus.py` and one collector file; no `scripts/claude_trace.py` (the transcript scan is a function), no `focus_id` in launches.
- **Cross-analysis edits come from the transcript on demand**, not from a new hook log: the gate records nothing about edits outside the plan's scripts, and adding a log would change `on_post` inside the `gate_diff` oracle for a signal only this report uses.
- **The collector never calls** `freeze_state`, `keep_snapshot`, `pin_scripts`, `verify stale` or `status` (they take locks or write), nor `verify report`.
- **`focus` has no CLI that changes state**, so an agent cannot start, switch or end a focus (spec F1).
- **Plan inputs, outputs and validation blocks use `verify diff`**. The new scope-loss attention item also names removed or redefined bindings and dropped outputs (`e759059`).

## Not done, on purpose (parked)

M3 and M4 were parked on 2026-10-19 to keep the ~2026-10-31 usage measurement unconfounded; the user reopened both the same day and both are built. M3: `focus_id`/`focus_folder` in matched receipts and the opt-in `focus_notices` turn-end line (see "M3 as built" below). M4: `track_changes.py --explain`. Strict focus blocking, an AI explanation and the usability study stay out of scope.

| Milestone | Scope | Files it touches | Acceptance cases | Status |
|---|---|---|---|---|
| **M3** | Launch-time `focus_id`/`focus_folder` in matched receipts, copied into the receipt by `on_post` (never relabelling an in-flight job); opt-in deduplicated turn-end notice under `"focus_notices": true`, default `false` | `hooks/gate.py`, `hooks/tests/test_focus.py`, `docs/approval-gate.md` | `F04`, `F21`, `F31` | done (the user overrode the measurement condition on 2026-10-19) |
| **M4** | `track_changes.py --explain <item_id>` emitting the five-heading bounded evidence block, plus Review Brief pointers from `grill`, `handoff` and `docs/mycelium-integration.md` | `skills/track-changes/scripts/track_changes.py`, `skills/track-changes/SKILL.md`, `skills/grill/SKILL.md`, `skills/handoff/SKILL.md`, `docs/mycelium-integration.md` | none (no `F` case; a usability study is Track R work) | done (same override) |

Both milestones are opt-in or additive by design: neither changes an allow, deny or message decision (`gate_diff` must stay identical), and the default-off flag keeps the measurement unconfounded. The spec bundle that produced them is archived at `plans/_DONE/mycelium_extra_focus_track_changes_complete_bundle/`; this tracker is self-contained. A human usability study stays parked under Track R and is not part of either milestone.

### M3 as built

- `hooks/gate.py`: `open_focus` reads this session's open focus (one directory test when there is none; any error means none). `write_launch` keeps `focus_id` and `focus_folder` in the launch record; `on_post` copies them into a *matched* receipt only, so a switch while a job runs, a focus opened after the launch, and an unmatched receipt never get a label.
- `focus_notice` (Stop hook, `"focus_notices": true`, default `false`): reads the last MiB of `receipts.jsonl`, takes receipts carrying the current `focus_id`, and for script paths under another gated analysis folder (not the focus folder, not a parent of it) adds one plain line, aggregated per turn and told once per (focus, folder) through `.mycelium-extra/pending/<session>.focus-notices.json`. Any failure is no notice.
- `skills/init/scripts/gate_init.py` knows `focus_notices` (and the previously missing `card_coverage`), so `--diagnose` no longer calls them typos.
- Not built from the spec's M3 list: the editable draft-action templates and a notice for direct edits (that needs the transcript, which a hook must not scan); `track-changes` still shows those on request.
- Evidence: `gate_diff` 173/173 identical with `card_coverage` off, so M3 changes no allow, deny or message decision; `hooks/tests/test_focus.py` 26 tests OK.

One verification limit carried forward: the viewer was checked in headless Firefox and by the user in a browser on 2026-10-19, so no browser run remains outstanding.

## Limits

- The transcript is Claude Code's; Codex and OpenCode sessions get no cross-analysis edits.
- A plan is linked to a folder only through paths in its table; a plan that names no path is invisible to both commands.
- Secret redaction is pattern based.
