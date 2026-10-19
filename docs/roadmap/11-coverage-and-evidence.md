# 11 · Coverage exceptions, decision trace, recipe gaps and evidence assistance (tracker)

Objective: show a researcher what is not established before a run (CT-1) and how each approved choice links to observed evidence after it (DT-1), close the gaps left in the validation recipes page (VR-1), and offer an opt-in evidence lookup inside grill (ER-1). Audited against `62d4725` (0.12.0, local main) on 2026-10-19. Version number, release, push and PR are decided later with the user and are not part of this tracker.

Statuses: **done**, **in progress**, **todo**, **parked**.

## Audit: what the first plan got wrong or left out

| # | Finding | Consequence |
|---|---|---|
| A1 | The mycelium_grill roadmap specification (named here as plain text, never linked) was written against 0.10.2. 0.11.0 and 0.12.0 changed the base: re-pin, amendment, freeze, the recipes page, `verify refs` and `card_coverage`. | Every proposal is re-checked against the code on main before it is built; where the specification and the code differ, the code and the approved plan win. |
| A2 | `plans/` is gitignored. | No tracked doc links into it, and `tests/check_links.py` runs in CI. The specification is named, not linked. |
| A3 | A hyphenated ID cannot appear after `planned:` in a Check cell: the legend test accepts only `planned: [A-Z]\d+`. | Milestone IDs of this tracker (CT-1, DT-1, VR-1, ER-1) are never written in that form in `skills/grill/references/llm-failure-modes.md` or `skills/grill/references/analysis-decisions.md`. |
| A4 | The ER-1 offer rides inside an existing grill question. | It costs none of the five questions; only a follow-up after a lookup counts toward the cap. |
| A5 | Retrieved sources reuse the existing `[agent-asserted: <DOI or URL>]` tag. | No new tag; an unread source is marked `unverified`, which the card already quotes. |
| A6 | Main's 0.12.0 (`62d4725`) already holds the recipes page, `verify refs` and the opt-in `card_coverage` row. | CT-1 extends `card_coverage` and adds no default-on card change, so the ~2026-10-31 before/after measurement of 0.11.0 is not confounded. |
| A7 | Another session works on branch `v0130` and edits `hooks/gate.py`. | A later `gate.py` merge is expected; CT-1 keeps its `gate.py` change small and local. |
| A8 | DT-1 (a read-only trace) is listed under "Not done, on purpose" in `09-clawbio-lessons.md`. | The user reinstated it on 2026-10-19; that line points here. |

## Milestones

Order is fixed: each one is its own commit on branch `v0120b`, tests green, before the next starts. Commits: M0 `a861001`, M1 `86ffafa`, M2 `8884233`, M3 `3df29df`, M4 `9d136c5` (built on the agentic branch and merged to `main` first), and the ClawBio tracker work (`5b`, `B4`) in `316b7af`. Renumbering the tracker from `10` to `11` happened when Phase 10 (focus and track changes) took that number in `0.13.0`.

### M0 · Tracker (done)
- Scope: this page, the Phases row and Workstreams bullet in `README.md`, and one pointer clause in the "Not done, on purpose" trace-view bullet of `09-clawbio-lessons.md`.
- Files: `docs/roadmap/11-coverage-and-evidence.md`, `docs/roadmap/README.md`, `docs/roadmap/09-clawbio-lessons.md`.
- Exit: `tests/check_links.py` reports 0 broken; `skills/grill/tests/test_grill_references.py` and the roadmap-heading tests in `tests/test_end_to_end.py` pass.

### M1 · CT-1 opt-in coverage exceptions (done)
- Scope: with `card_coverage: true` only, the compact card also lists `Not established before running` lines for inputs and scripts whose pin is `missing` or `not pinned…` (at most 3, then a pointer to `card <hash> full`); `card <hash> full` lists every non-sha256 pin, unbound prose when the plan has no bindings block, and one out-of-scope line. With the key off every card is byte-identical to today. The existing Coverage row already counts prose-only rows and exact steps and is not duplicated.
- Files: `hooks/gate.py` (a small helper beside `coverage_text`), `hooks/tests/test_gate.py`, `docs/approval-gate.md`.
- Exit: key off gives identical cards and `gate_diff` stays identical against its current base (oracle file, base and `ci.yml` pins untouched); key on gives the new lines; a failing helper prints `not computed (<error>)` and the plan stays approvable.

### M2 · DT-1 decision trace (done)
- Scope: `verify report <hash> --trace [ROW]`, text only. A summary table without ROW; one row's declared edges, receipts, outputs and validation with ROW. Labels `declared`, `observed`, `check result`, `candidate`, `unresolved`; it closes with a line that scientific correctness is not determined. The default report, `--json` and `write` stay byte-identical; `--trace` is refused with other actions and with `--json`.
- Files: `skills/verify/scripts/verify.py` (additive), `skills/verify/tests/test_verify.py`, `skills/verify/SKILL.md`, `docs/advanced.md`, `docs/verification.md`.
- Exit: spec cases 1 to 7 and the misuse cases covered; report text and the `--json` key set unchanged; `gate_diff` shows no new difference.

### M3 · VR-1 gap fill (done)
- Scope: the recipes page itself landed in `76f5bc6` and `ca65d58`. This milestone reviews `docs/validation-recipes.md` and `tests/test_recipes.py` against the code and fixes confirmed items only: result semantics (an unavailable check writes `unsupported`, a gap; a nonzero exit is `failed`), the pairing and replicates mapping to data-contract kinds with the random-effects limit, and steps that take argv paths or are written in R.
- Files: `docs/validation-recipes.md`, `tests/test_recipes.py`, optionally a pointer in `skills/grill/references/run-plans.md`.
- Exit: each finding fixed or rejected with a reason; `tests/test_recipes.py` and `tests/check_links.py` green.
- Delivered: a "How a result is read" section stating the full outcome ladder from the code (exit status first, then the file, with `not run`/`changed` overriding a non-zero exit and a file never turning a non-zero exit into a pass, plus the `mycelium-extra.contract_result.v1` rules and the instruction to write `{"status": "unsupported"}` with exit `0` for an unavailable backend); a "Contract kinds, and what they cannot show" table mapping pairing and replication questions to `sample_alignment`, `pairing`, `unit_of_replication`, `cohort` and `batch_confounding`, with the set-comparison limit, the random-effects limit and the unpinned-checker limit; a `run_step(samples, counts, out)` subprocess wrapper for steps that take paths on the command line (including `Rscript` and a missing interpreter as a gap); and 7 new tests in `tests/test_recipes.py` that call `verify.judge_check` itself for the `(returncode, outcome)` pairs — `(0, passed)`, `(1, failed)` twice, `(0, unsupported)`, a file that says `passed` under exit 1 staying `failed`, a contract `gap` overriding exit 3 to `not run`, an unrecorded exit status being `unsupported`, and a vanished result file being `unattributable`.
- Not done in this milestone: no pointer was added to `skills/grill/references/run-plans.md`; the recipes page is already linked from `docs/advanced.md` and `docs/skills.md`, and the tests bind the page to the code.

### M4 · ER-1 opt-in evidence lookup (done)
- Scope: grill only. One reference file (when it applies, the offer, offline first, retrieved content untrusted, `[agent-asserted: <DOI or URL>]` tags, no writes), one sentence in `skills/grill/SKILL.md`, one scenario, one contract test. No Librarian adapter.
- Files: `skills/grill/references/evidence-assistance.md`, `skills/grill/SKILL.md`, `skills/grill/references/scenarios.md`, `skills/grill/tests/test_grill_references.py`.
- Exit: the `SKILL.md` change is one added sentence; `hooks/`, `skills/verify/`, `skills/grill/references/llm-failure-modes.md` and `skills/grill/references/analysis-decisions.md` are unchanged; `gate_diff` shows every case identical.
- Delivered in `9d136c5` (roadmap §12 M1/M3 with it, since the file is the same reference page the grill heuristics work added): the offer, what it may and may not do, the offline-first order and the `[agent-asserted: <DOI or URL>]` tag; a scenario and contract assertions in `skills/grill/tests/test_grill_references.py` (12 tests OK). `hooks/` was not touched, so `gate_diff` is unaffected.

## Out of scope
- ED-1, deferred.
- D2 and D3: implemented in 0.13.2 (`0d5bfa8`) — see `05-mindfulness-core.md`; this lane's own changes are CT-1, DT-1, VR-1, ER-1 and the tracker itself.
- No Librarian adapter, skill or server. The user reopened the librarian idea on 2026-10-19 as a role inside grill's `evidence-assistance.md` (a dossier), not an adapter; see `12-agentic-reasoning.md` M5a.
- Regenerating `docs/example.md`: done in `316b7af` at 0.12.0 (ClawBio step `5b`), with the Python `scilintr` from the archive `codex` environment and the `cellbouncer` `Rscript`; `tests/test_example.py` passes.
- Version, release, push, tag and PR: decided later with the user. No CHANGELOG or manifest edits here.

## Risks
- A later merge with `v0130` will touch `hooks/gate.py`; a small, local CT-1 diff keeps it mechanical.
- A coverage line can be read as a pass. Every line says what is not established, never that a check passed, and a gap is never reported as clean.
