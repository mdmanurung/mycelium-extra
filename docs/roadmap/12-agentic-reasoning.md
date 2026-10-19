# 12 · Agentic reasoning (tracker)

Objective: make the agent's reasoning inspectable at the two places it matters — before approval (`grill` resolving a blocked plan; `plan-review` classifying objections) and after a report (`verify` interpreting one) — without adding questions, prompts, or unverifiable claims. Milestones come from `plans/_DONE/mycelium-agentic/AGENTIC_ENGINEERING_PATTERNS_COMPLETE_BUNDLE.md` (archived 2026-10-19, all four milestones landed).

Statuses: **done**, **parked**, **dropped**.

## Milestones

| Milestone | Deliverable | Status | Where |
|---|---|---|---|
| M0 | Working scope, re-pin, amendment and freeze (the engineering half of the bundle) | done (`0.11.0`) | [08-working-scope.md](08-working-scope.md) |
| M1 | `skills/grill/references/polya-heuristics.md`: backward chain from claim to discriminating check, plus five selective heuristics for a blocked plan | done | this tracker; `skills/grill/SKILL.md` links it |
| M2 | Material-objection classification in `skills/plan-review/`: four fields and a status per material objection, synthesis leading with the single strongest undecided crux | done | `skills/plan-review/references/review-contract.md`, `synthesis.md` |
| M3 | Focus and track-changes (typed `focus`, read-only `track-changes`) | done (`0.13.0`) | [10-focus-track-changes.md](10-focus-track-changes.md) |
| M4 | Three-line post-report interpretation template (*Established / Still uncertain / Next insight*) in `skills/verify/SKILL.md`; opt-in evidence lookup inside one grill question (`ER-1`) | done (`0.13.2`, `0d5bfa8`) | `skills/verify/SKILL.md`, `skills/grill/references/evidence-assistance.md` |
| M5a | Opt-in Socratic probe, read-only `explain row N` / `challenge row N`, and the librarian dossier for evidence lookup, as grill references (no hook, skill or adapter) | done on branch `v0132-socratic`, unlanded; reopened by the user 2026-10-19 | `skills/grill/references/socratic.md`, `evidence-assistance.md`, `skills/grill/tests/test_grill_references.py` |
| M5b | Live Socratic study with real researchers | **parked** | needs the ~2026-10-31 usage measurement first; see [00-parked.md](00-parked.md) |

## What the reasoning additions may not do

- **M1** adds plan rows, never questions: it is subordinate to the five-question cap and the 150-word brief, and a heuristic result is a labeled `default: <reason>`, never `repo:` evidence.
- **M1/`ER-1`** never settle a user-owned choice (question, estimand, accepted trade-off) and never upgrade an association to a mechanism by wording.
- **`ER-1`** is an option inside one rule-3 `user` question, never a sixth question or a default; it is offline first, sends zero project data if an external lookup is agreed, treats retrieved content as untrusted, and writes nothing.
- **M2** classifies objections from evidence: not substantiated because a reviewer asserted it, not refuted because the author disagrees. `no substantiated material concern` describes the objections raised, not the plan's correctness, and never replaces a reviewer's `status`.
- **M4** (verify) is skill guidance only. `verify.py` output, exit statuses, and receipts are unchanged, so no conformance verdict depends on how a summary is phrased.

## Evidence

- `skills/grill/tests/test_grill_references.py`: the backward chain and all five heuristics are present, the cap subordination and the `default:`-not-`repo:` rule are asserted, and the evidence-assistance file keeps its opt-in shape (option inside the question, no sixth question, follow-up counts toward the cap, offline first, zero project data, untrusted, the shipped `--resolve-citations` check for invented citations, no writes).
- `skills/plan-review/tests/test_plan_review.py`: the four objection fields and the four statuses are asserted, non-material issues may not be promoted to cruxes, and the synthesis must open with one undecided crux or `no substantiated material concern`.
- `skills/verify/tests/test_verify.py`: the three-line look-back (Established / Still uncertain / Next insight) stays in `skills/verify/SKILL.md`, and the shipped checks the same file documents are asserted too — offline citations stay gaps, a mocked resolver's mismatch and a 404 block, and every `disclose` line carries a `[source: ...]` tag or a `[BLANK: ...]` marker.
- No hook, gate decision, message, or `gate_diff` expectation changes with any milestone here; M1/M2/M4 are documentation and tests in skills, and M3 shipped with its own tracker and `gate_diff` run.

## Limits

- The heuristics and the objection rubric are behaviour contracts checked by tests over the reference text; they cannot show that an agent applied them well to a specific plan. That is what M5 would measure.
- `ER-1` names no service and performs no fetch itself: the route is whatever the host offers, and the consent step is a conversation, not an enforced boundary.
- A status of `unresolved` is a statement about what could be settled before execution, not a prediction of failure.
