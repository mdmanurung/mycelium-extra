# 10 · Focus and track changes (0.13.0 tracker)

Objective: build milestones M0 to M2 of `plans/mycelium_extra_focus_track_changes_complete_bundle/` (spec of 2026-10-18) against the real code: a typed `focus` command and a read-only `track-changes` report. Not built: M3 (turn-end notices, draft actions, `focus_id` in launches and receipts) and M4 (AI explanation, usability evaluation).

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
| F04, F21, F31 | **not applicable**: they concern launch-time focus and notices (M3), not built |

## Decisions on the spec

- **Fewer moving parts than specified.** One `focus.py` and one collector file; no `scripts/claude_trace.py` (the transcript scan is a function), no `focus_id` in launches.
- **Cross-analysis edits come from the transcript on demand**, not from a new hook log: the gate records nothing about edits outside the plan's scripts, and adding a log would change `on_post` inside the `gate_diff` oracle for a signal only this report uses.
- **The collector never calls** `freeze_state`, `keep_snapshot`, `pin_scripts`, `verify stale` or `status` (they take locks or write), nor `verify report`.
- **`focus` has no CLI that changes state**, so an agent cannot start, switch or end a focus (spec F1).
- **Plan inputs, outputs and validation blocks are not compared**; `verify diff` already does.

## Not done, on purpose

- M3 and M4, strict focus blocking, an AI explanation, and a usability study. Revisit after the ~2026-10-31 usage measurement of 0.11.0.
- A browser run of the viewer (none on this host). The user should open one `report.html` from disk.

## Limits

- The transcript is Claude Code's; Codex and OpenCode sessions get no cross-analysis edits.
- A plan is linked to a folder only through paths in its table; a plan that names no path is invisible to both commands.
- Secret redaction is pattern based.
