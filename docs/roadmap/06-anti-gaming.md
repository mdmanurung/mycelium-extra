# Anti-gaming

[Back to roadmap](README.md)

Every oversight step can turn into a reflex: approve without reading, answer the checkpoint by pattern, re-use one approval for everything. These tasks make that drift visible to the researcher themself. They come last because they only mean something once the checks they watch are real.

## Preconditions for the whole workstream

- C1 (fixture project) and D1 (claims checker) have shipped, so there is something real to audit.
- Seeded errors (D12) are disclosed at install: `init` says that audits may plant a known error, and a user can turn them off. No covert testing.
- All metrics stay local, in `.mycelium-extra/`, which git ignores. Nothing is sent anywhere, and nothing is shown to anyone but the user.
- No SessionStart surface (it competes with Mycelium's SESSION RESUME). The dashboard lives in `verify status`.
- Metrics describe a person's own habits over time. They are not a score, and they never block work.

## D10: Comprehension checkpoint and approval latency

- **Why:** the gate records that a plan was approved, not that it was read. A plan approved four seconds after it appeared, every time, is a sign the approval has become a reflex.
- **Scope:** the gate records, per approval, the time between the plan being shown and the approval, and the plan's length. For plans above a size threshold, approval asks one short question whose answer is in the plan (for example, "which contrast is the reference level?"), generated from the plan table, not by an LLM; a wrong answer shows the relevant row and asks again, it does not deny. Latency and checkpoint results feed the D12 dashboard.
- **Out of scope:** blocking approval on speed; any remote reporting; questions about anything not in the plan.
- **Depends on:** C1, D1, D12.
- **Constraints:** `gate_diff.py` before and after; approval decisions must not change except for the added checkpoint prompt. The checkpoint can be turned off in `gate.json`. Approvals are not pruned.
- **Grill prompt:** `/mycelium-extra:grill Add approval-latency logging and an optional one-question comprehension checkpoint for long plans to the approval gate. The question comes from the plan table, never from an LLM, and a wrong answer re-shows the row instead of denying. Read how gate.py detects and records approvals, and run gate_diff.py before and after.`
- **Acceptance:** latency is recorded for every approval in the fixture; a long plan triggers one question; a wrong answer re-shows the row; with the checkpoint off, `gate_diff.py` shows no change.
- **Tests:** gate tests for latency recording, question generation from a fixture plan table, and the off switch.
- **Effort:** M.
- **Status:** todo.

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
- **Status:** todo.

## D12: Seeded-error audits and a personal dashboard

- **Why:** the only ground truth for "does the user still catch errors?" is an error whose presence is known. Latency and checkpoint scores (D10) are proxies; a seeded error is a direct measure.
- **Scope:** at a rate the user sets (default off; suggested one in twenty verify runs), verify or the claims checker plants one known, harmless discrepancy in its report (for example, a claim marked `VERIFIED` that is not), and records whether the user flagged it before accepting. The report says afterwards that it was a seeded audit and what the real result is. `verify status` gains a short personal section: seeded errors caught versus missed, median approval latency, checkpoint accuracy, explore-to-plan ratio, each over the last 30 days and the 30 before.
- **Out of scope:** comparing users; exporting metrics; seeding errors in data, code, or anything written to disk outside the report.
- **Depends on:** C1, D1.
- **Constraints:** disclosed at install, off by default, and switchable off at any time. A seeded discrepancy is always revealed in the same session, and never reaches provenance or `.living/`: the provenance written after an audit carries the real result. Metrics live in `.mycelium-extra/` only.
- **Grill prompt:** `/mycelium-extra:grill Plan seeded-error audits for verify and the claims checker, plus a personal habits section in verify status. Audits must be disclosed at install, off by default, revealed in the same session, and never reach provenance or .living/. Show where the real result is kept while the audit is pending.`
- **Acceptance:** with the rate at 1, every verify run on the fixture plants and then reveals one discrepancy, and the written provenance carries the real result; `verify status` shows the habits section with both 30-day windows; with the rate at 0, nothing changes.
- **Tests:** unit tests for planting, revealing, and the provenance guarantee; a test that metrics files are written only under `.mycelium-extra/`.
- **Effort:** L.
- **Status:** todo.
