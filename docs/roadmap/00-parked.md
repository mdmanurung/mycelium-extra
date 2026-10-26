# Parked work

[Back to roadmap](README.md)

Work already drafted outside the repository, waiting to land.

## T0: Split the README into a landing page plus docs/

- **Why:** the README is about 31 KB. A new user meets the receipt schema and the gate's Bash parsing rules before learning what the plugin is for.
- **Scope:** README.md keeps the intro, the summary table, the workflow diagram, Installation, and Quick start, plus a Documentation section. Four new files: `docs/skills.md` (all skill references and the common-prompts table), `docs/approval-gate.md` (approving, gating, pinned inputs, receipts, explore runs, hints, and the full Limits), `docs/mycelium-integration.md`, `docs/development.md`. Prose is condensed; no behaviour, default, path, or limit is dropped.
- **Out of scope:** HANDOFF.md, the B items, any change to skill or hook behaviour.
- **Depends on:** none.
- **Constraints:** none from locked decisions. The Limits list stays complete: it is the plugin's statement of what it does not do.
- **Grill prompt:** `/mycelium-extra:grill Split README.md into a short landing page plus docs/skills.md, docs/approval-gate.md, docs/mycelium-integration.md, and docs/development.md. Start from the drafted files, rebase them onto the current README (it has gained a workflow diagram since the draft), and check that every default, command, path, and limit in the old README appears in the new files.`
- **Acceptance:** the landing page is under about 120 lines and lets a new user install and run the quick start without opening docs/. The Mermaid workflow diagram stays on the landing page. A token check (every gate.json key, schema name, status string, and default value in the old README is found in the new files) passes. Every relative link resolves. The diff touches only README.md and docs/.
- **Tests:** a token-coverage and link check, run once before committing. Optionally keep it as `docs/tests/test_docs_links.py` for CI (A2).
- **Effort:** S.
- **Status:** done. The draft was rebased onto 3a11123, so the workflow diagram stays on the landing page, and B1 is folded in. A content check (every heading, table cell, code line, sentence, and inline-code token of the old README found in README.md or docs/*.md) passes except for the B1 sentence, and every relative link resolves. `docs/skills.md` adds a short `init` entry pointing to `docs/approval-gate.md`, which documents it.

## R2: ROADMAP synthesis refinements (2026-10-14)

- **Why:** the 2026-10-14 synthesis of outside skill repositories left 88 refinement ideas (Batches A to D and round 2) scheduled for releases after 0.9.63 that never shipped. Triaged 2026-10-26.
- **Status:** done for 3 as the handoff freshness check (BIP1-02, BIP2-14, PI-24; `91ffcc0`). 58 are covered by later features and 27 are dropped: no failure in real use backs them.
- **Covered:**
  - ADY1-01, ADY2-03, PRB1-06: Principle 'the checker adjudicates; never loosen a check to pass' (roadmap README; `docs/concepts/gaps-and-passes.md`). Direction-aware wording adds nothing without a failure.
  - ANT1-14, BIP2-25, PI-17, PRB2-05, ADY2-07: grill section 1 requires a targeted search before stating absence; A4 `discriminating_check` and `polya-heuristics.md` require a check that can fail. A separate positive-control rule has no observed failure.
  - ANT2-01, ECC5-12: 'A gap is never clean' is a guiding principle and is enforced in `verify` (`docs/concepts/gaps-and-passes.md`); C19 fixed 'no finding' when the linter never ran.
  - ADY1-03, ECC1-07, ECC5-29, PI-09, ECC5-02, BIP2-21: plan-review sends one packet to independent reviewers, preserves disagreement, treats only `status: complete` with empty `issues` as clean, and labels packets as data (`skills/plan-review/SKILL.md`, review-contract).
  - ADY2-05, ADY2-06, ANT2-12, ECC3-02, PI-10: plan-review's issue schema carries evidence, severity and recommendation; agentic M2 added four fields and a status per objection (`docs/roadmap/12-agentic-reasoning.md`).
  - ADY1-05, BIP2-18, ECC2-09, ECC3-11: handoff carries the pending plan verbatim, locked decisions with the user's reason, and dead ends with evidence (`skills/handoff/SKILL.md`).
  - ECC1-05, ECC5-20: Amendment and freeze cards (0.11.0) re-approve changed criteria; track-changes compares the original and current approved plans.
  - ECC2-01, ECC3-12, ECC4-08: Only a typed `approve plan <hash>` approves; recall, summaries and handoffs approve nothing (`docs/approval-gate.md`).
  - PRB1-09: Plan rows carry `depends_on`, and `explain plan` names downstream rows a wrong choice breaks (`references/socratic.md`).
  - PRB2-03: Hooks already return a closed decision payload (`permissionDecision` plus reason) on every host.
  - ECC2-03: verify pins inputs and reports changed or unmeasured inputs as gaps, not zero.
  - ECC5-27: track-changes `currency: older_than_change` and verify's 'written after the approval by a run of this plan' check stale outputs.
  - ECC2-12: Proof levels and authority are separate by design (`docs/concepts/control-model.md`): verify reports never approve.
  - ANT2-05, PI-27: The card's Coverage row (default on since 0.14.0) shows what was skipped.
  - BIP1-03, BIP2-15, ECC5-15: Slurm completion is separate from submission and unknown states are gaps (C05, `07-execution-fidelity.md`). No stall daemon wanted.
  - BIP2-16, ECC1-08, PI-16, PRB1-08: verify judges completion from receipts and outputs, never from a checked box; an unreceipted step is 'not run'.
  - ANT2-02, BIP2-02, ECC5-21, PI-21: Denominators: validation recipes and `scientific-conventions.md` bind rates to their unit; data-contract-check and the profile count units.
  - BIP1-04, PI-15: Finding dispositions `substantiated
  - BIP2-11, ECC5-10, ECC5-11: Independence and falsifier-first: polya-heuristics backward-chains to a discriminating check; plan-review keeps reviewer evidence separate.
  - ADY2-17, PRB1-03: The `idea` skill parks a noticed idea in one line without derailing the task.
  - ANT1-03, ANT2-09, PRB1-02: Parked items need a return condition (grill section 3, brief Parked); idea-triage reviews old ideas.
- **Dropped:**
  - ANT2-11: Waiver owner and expiry: no waiver was ever left unowned in real use; `verify` waivers have no owner field and nobody asked for one.
  - BIP1-05, BIP2-10: Skeptic trigger on extreme claims: no observed miss; plan-review already challenges claims, and the roadmap rejects automatic reviewers.
  - PI-13, ECC3-09: `[decision]`/`[deviation]` TRACKER markers: Mycelium owns decision logging (`.living/decisions.md`); a second ledger duplicates it.
  - BIP1-01, BIP2-12, ECC3-16: Bounded review cycles: plan-review runs once per request; no runaway cycle was ever observed.
  - PI-11: Pre-mortem: no plan failed in a way a pre-mortem would have caught; grill's failure-modes walk (`llm-failure-modes.md`) covers the guard role.
  - BIP2-19, BIP2-20, PI-01, PI-02: Wording rules: brief-format.md (0.17.0) already asks for plain scientific terms in cells; no observed card misread from hedging.
  - PI-25: Worktree fingerprint around the suite: CI runs on a clean checkout, and no result was ever bound to the wrong tree.
  - ADY2-02, ANT1-06, ANT1-15, ANT1-18, ANT2-06, ECC1-02, ECC5-34, PI-04, PRB2-06, ECC2-04: Stop-if convention: the longitudinal and Bayesian method guides carry stop rules where they matter; no run went past an undeclared stop in real use.
  - ANT1-05, PI-20: Carried thresholds and edge invariants: recipes 4-8 test output invariants per step; carrying them across steps has no observed failure.
  - PI-03: Gate message template: no misread gate message is recorded; wording fixes land per finding (tracker 13).
- **Return condition:** a real session shows the failure a dropped idea guards against. Re-grill that one idea; do not reopen the batch.
- **Source:** the triage table and the synthesis index, local and gitignored under `plans/_DONE/ROADMAP/`.
