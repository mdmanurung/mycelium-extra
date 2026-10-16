# Anti-gaming

[Back to roadmap](README.md)

Every oversight step can turn into a reflex: approve without reading, answer the checkpoint by pattern, re-use one approval for everything. These tasks make that drift visible to the researcher themself. They come last because they only mean something once the checks they watch are real.

## Preconditions for the whole workstream

- C1 (fixture project) and D1 (claims checker) have shipped, so there is something real to audit.
- Review exercises (D12, reshaped) are synthetic, labelled as exercises, off by default, and never placed in a real report. No covert testing, and no falsified genuine record.
- All metrics stay local, in `.mycelium-extra/`, which git ignores. Nothing is sent anywhere, and nothing is shown to anyone but the user.
- No SessionStart surface (it competes with Mycelium's SESSION RESUME). A habits summary, if one is ever built, lives in `verify status`; none exists today.
- Metrics describe a person's own habits over time. They are not a score, and they never block work.

## D10: Comprehension checkpoint and approval latency

- **Why:** the gate records that a plan was approved, not that it was read. A plan approved four seconds after it appeared, every time, is a sign the approval has become a reflex.
- **Scope:** the gate records, per approval, the time between the plan being shown and the approval, and the plan's length. When `checkpoint_steps` is set in `gate.json` (off by default), a plan with more step rows than that asks one short question whose answer is in the plan, generated from the plan table, not by an LLM; a wrong answer shows the relevant row and asks again, it does not deny. The log is for the researcher to read; no dashboard consumes it.
- **Out of scope:** blocking approval on speed; any remote reporting; questions about anything not in the plan.
- **Depends on:** C1, D1. (The user approved D10 on 2026-10-16 as the log and the opt-in checkpoint only; D12's dashboard was not built first.)
- **Constraints:** `gate_diff.py` before and after; approval decisions must not change except for the added checkpoint prompt. The checkpoint is off unless `checkpoint_steps` is set. Approvals are not pruned.
- **Grill prompt:** `/mycelium-extra:grill Add approval-latency logging and an optional one-question comprehension checkpoint for long plans to the approval gate. The question comes from the plan table, never from an LLM, and a wrong answer re-shows the row instead of denying. Read how gate.py detects and records approvals, and run gate_diff.py before and after.`
- **Acceptance:** latency is recorded for every approval in the fixture; with `checkpoint_steps` set, a long plan triggers one question; a wrong answer re-shows the row; with the checkpoint off, `gate_diff.py` shows no change.
- **Tests:** gate tests for latency recording, question generation from a fixture plan table, and the off switch.
- **Effort:** M.
- **Status:** done (0.9.73): every approval appends a line to `approvals.jsonl` (latency, plan rows and length; never shown, never blocking). `checkpoint_steps` in `gate.json` (off by default) asks one question from the plan table when a plan has more step rows; a wrong answer re-shows the row, a right one approves. No latency scoring is done: latency is only logged, never displayed, scored, compared, or used to block or slow an approval. The D12 dashboard is not built.

## D11: Approval expiry by reuse count

- **Why:** one approval can cover many runs of the same scripts. After enough re-runs, often with edits, the approved plan no longer describes what is running, but the gate still passes it.
- **Scope:** a `max_runs_per_approval` setting in `gate.json` (unset by default). Once a plan's approved scripts have run that many times, the next run asks for re-approval, showing what changed since the first approved run (edited scripts, changed pinned inputs).
- **Out of scope:** time-based expiry; deleting or pruning approvals.
- **Depends on:** C1, D1.
- **Constraints:** approvals are not pruned: an expired approval stays in the record, marked expired. `gate_diff.py` shows no change with the setting unset. Explore runs do not count toward the limit.
- **Grill prompt:** `/mycelium-extra:grill Add an optional per-approval run limit to gate.json: after N runs under one approval, the next run asks for re-approval and shows what changed since the first run. Approvals are never pruned, only marked expired. Read how receipts link runs to approvals, and run gate_diff.py before and after.`
- **Acceptance:** with the limit at 3, the fourth run on the fixture asks for re-approval and lists the changes; with the limit unset, behaviour is unchanged per `gate_diff.py`.
- **Tests:** gate tests for the limit, explore runs not counting, and the expired-but-kept record.
- **Effort:** S.
- **Status:** done (0.9.71), and optional: it is off unless set and is not part of the default journey. `max_runs_per_approval` in `gate.json`; the denial lists the commit and script changes since the first counted run, the approval file is untouched, and `verify list`/`status` mark an approval that reached the limit. The count lags by runs in flight.

## D12: Synthetic review exercises (reshaped; not implemented)

The earlier proposal planted a known false claim in the researcher's genuine verification report and recorded whether it was caught. That is dropped: a genuine verification report must not contain an invented discrepancy, even briefly.

- **Why:** the only ground truth for "does the user still catch errors?" is an error whose presence is known. A synthetic exercise gives that ground truth without touching real work.
- **Scope:** an opt-in command, off by default, that shows a clearly labelled synthetic exercise: a fixture plan, receipts, and report with one known discrepancy, built from the fixture project's defect cases (C1). It says at the start that it is an exercise, asks what the user finds, and then reveals the known answer. A personal summary in `verify status` (exercises caught versus missed, over the last 30 days and the 30 before) may follow, kept in `.mycelium-extra/` only.
- **Out of scope:** any change to a genuine plan, receipt, report, provenance file, `.living/` entry, or claims check; seeding errors in the user's data or code; comparing users; exporting metrics; scheduled or covert exercises.
- **Depends on:** C1, D1.
- **Constraints:** every exercise carries an unmistakable label and lives in its own folder, never next to or inside real provenance. Nothing it writes can be mistaken for, or read by `verify`, `status`, or `stale` as, a real run. Metrics live in `.mycelium-extra/` only. Off by default and switchable off at any time.
- **Grill prompt:** `/mycelium-extra:grill Plan opt-in synthetic review exercises built from the fixture project's defect cases. They must be labelled as exercises, kept out of real reports and provenance, and revealed in the same session. Show where an exercise lives so that verify cannot mistake it for a real run.`
- **Acceptance:** an exercise is created only on request; its files are labelled and never appear in `verify list`, `status`, or `stale`; the real result of any genuine verify run is unchanged by it; with the feature off, nothing changes.
- **Tests:** unit tests for labelling and isolation, and a test that no exercise file is written outside its own folder under `.mycelium-extra/`.
- **Effort:** M.
- **Status:** reshaped, not implemented. The seeded-discrepancy design is replaced; no code exists.
