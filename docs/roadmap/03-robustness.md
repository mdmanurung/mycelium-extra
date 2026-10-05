# Robustness

[Back to roadmap](README.md)

Tasks that make the existing tools trustworthy before new ones are added. C1 comes first: most later tasks need it as their test bed.

### C1: Fixture Mycelium project for end-to-end tests

- **Why:** each skill's tests check its own script in isolation. Nothing tests the chain a user actually goes through (init, approval, gated run, verify, provenance) on a realistic project, so a change in one skill can break the hand-off to the next while every unit test still passes. Nothing checks either that the failure-mode checklist's Check column is true. Several roadmap tasks (A2, A6, C3, D1, D4, E4, D10 to D12) need such a project to test against.
- **Scope:** as in [docs/design/c1-fixture-project.md](../design/c1-fixture-project.md): a committed project in Mycelium's layout with a simulated paired vaccine-response dataset of known ground truth (`tests/fixtures/mycelium-project/`); a harness that copies it to a temporary directory, builds the timeline (commit, approve, run, post-hook) through the real hooks, and runs each skill's documented command form (`tests/e2e/harness.py`); a catalog of planted defects, each applied alone to a clean copy (`tests/e2e/defects.py`); and `tests/test_end_to_end.py`, with the clean baseline chain, one case per defect, and catalog contract tests that tie each defect to a row of `llm-failure-modes.md` or `analysis-decisions.md`.
- **Out of scope:** running Claude Code, Codex, or grill itself; Mycelium's own hooks; network access; real Slurm, Snakemake, conda, or R (simulated, or used only when present).
- **Depends on:** none.
- **Constraints:** stdlib only and Python 3.6 compatible; the project stays under 40 files and 200 KB. Simulated hook input uses the payload shape `hooks/tests/test_gate.py` and `skills/verify/tests/test_verify.py` use, not a new one. Do not vendor Mycelium code: reproduce only the file layout the skills read, following Mycelium's `folder-structure.md` at a named version. Expected messages are copied from the current code, so a wording change fails loudly. The test environment is hermetic: no inherited conda or virtualenv variables, a temporary `HOME`, fixed time zone and locale.
- **Grill prompt:** `/mycelium-extra:grill Build the C1 fixture project, harness, defect catalog, and end-to-end test as specified in docs/design/c1-fixture-project.md. Start with the baseline chain and the data generator, then add defects one layer at a time. For each defect, show the current code path that should catch it before writing the case.`
- **Acceptance:** the baseline chain passes on a clean checkout with `Verify status: CONFORMS`; every defect case passes; every failure mode whose Check names a tool has at least one defect the tool catches; for the three named guard ablations, the matching defect case fails with a message naming the check.
- **Tests:** `tests/test_end_to_end.py` is the deliverable; `tests/e2e/ablate.py` runs the ablations. Record one ablation run in the PR description.
- **Effort:** L.
- **Status:** done: build-order commits 1-5 landed. 60 end-to-end tests (the baseline chain with and without R, 49 defects, 5 catalog tests, 4 event-shape tests) pass on Python 3.6 and 3.12 in about 40 s; `ablate.py` reports 3 of 3 ablations bite.

### C2: Optional fail-closed gate

- **Why:** on an internal error the gate fails open and says so. That is the right default for a solo user, who would otherwise be locked out by a gate bug. In a lab where the gate is part of an agreed protocol, a silent pass after a crash weakens the record, and the plain-text notice is easy to miss in a long session.
- **Scope:** an `on_error` key in `.mycelium-extra/gate.json` with values `"allow"` (current behaviour, the default) and `"deny"`. With `"deny"`, an internal error denies the tool call with a reason naming the error and how to switch back. `init` documents the key but does not set it. The receipt for an errored call records the error either way.
- **Out of scope:** changing the default; changing the approval-scan timeout, which already denies; any SessionStart notice.
- **Depends on:** none.
- **Constraints:** run `hooks/tests/gate_diff.py` before and after the change and show that no decision changes under the default. The deny path must not depend on the code that just failed: build its output from constants. A missing or malformed `on_error` value falls back to `"allow"` with a plain-text notice.
- **Grill prompt:** `/mycelium-extra:grill Add an on_error setting to gate.json so a lab can make the approval gate deny instead of fail open on an internal error. Read gate.py's main() error path and the approval-scan timeout first, and plan how the deny path stays independent of the code that failed. Include the gate_diff.py runs.`
- **Acceptance:** with `on_error: "deny"`, a forced internal error (for example, a corrupt approvals file) denies with the stated reason; with the key absent the behaviour is byte-identical to today per `gate_diff.py`.
- **Tests:** three cases in `hooks/tests/test_gate.py`: key absent, `"allow"`, `"deny"`, each with a forced internal error; one case with an invalid value.
- **Effort:** S.
- **Status:** todo.

### C3: Audit plan-review's redaction handling

- **Why:** plan-review sends a review packet to Codex and to Biomni. Its contract already has a `redactions:` field, a "minimize external disclosure" rule, an exclusion list (raw data, participant identifiers, credentials, unpublished full tables), and a rule to mark a review incomplete when redaction removes an essential fact. What is untested is whether the packet an agent actually assembles obeys those rules, and whether `redactions:` is filled in rather than left as `[]`.
- **Scope:** an audit of the existing rules against two or three realistic packets built from the C1 fixture (including one with participant IDs and a credential in the plan text); a short list of gaps found; fixes limited to the contract wording, the synthesis report, and a stdlib pre-send check that flags likely identifiers or secrets in the packet and refuses to send while `redactions:` is empty and a flag is raised.
- **Out of scope:** building a general-purpose redaction engine; changing which reviewers run; storing packets or transcripts (the first version keeps them ephemeral, and that stays).
- **Depends on:** C1 for realistic packets.
- **Constraints:** extend, do not replace, `skills/plan-review/references/review-contract.md`. The pre-send check reports what it flagged and why; the user decides. Patterns are conservative and listed in the file so a user can see what is and is not caught. A clean check is not evidence that nothing sensitive remains: say so in the output.
- **Grill prompt:** `/mycelium-extra:grill Audit plan-review's existing redaction rules (the redactions field, the exclusion list, minimize external disclosure, incomplete-on-redaction) against packets built from the fixture project, one of which contains participant IDs and a token. Report each gap before proposing a fix, and keep any fix to the contract wording plus a small pre-send check.`
- **Acceptance:** a gap list exists in the PR; the packet with planted identifiers is flagged before sending; a packet with no flags still states that the check is pattern-based.
- **Tests:** contract additions in `skills/plan-review/tests/test_plan_review.py`; unit tests for the pre-send check with true positives, known false positives, and one documented miss.
- **Effort:** M.
- **Status:** todo.
