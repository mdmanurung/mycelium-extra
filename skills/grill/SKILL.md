---
name: grill
description: Critically scope and challenge a proposed research, analysis, software, or project task using the current repository before asking bounded, consequential questions. Use when the user invokes grill, asks to pressure-test a plan, or wants a repository-aware decision brief, especially in a Mycelium-enabled project.
---

# Mycelium Extra: Grill

Turn a proposed task into a short, evidence-grounded decision brief. Inspect first, challenge the approach, ask only questions that the user must answer, then stop. Remain read-only during this skill unless the user separately requests implementation.

## 1. Orient and retrieve

- Locate the project root and obey applicable repository instructions. Detect Mycelium through `MYCELIUM.md` and `.living/INDEX.md`; partial or absent structure is acceptable.
- In a Mycelium project, read `MYCELIUM.md`, then `.living/INDEX.md`; drill into only relevant entries, manifests, analysis documentation, findings, decisions, learnings, conventions, code, and configuration. Use the repository's own guidance where present. Read [references/mycelium.md](references/mycelium.md) for locations and a safe fallback when the index or plugin scripts are missing.
- In another repository, use its instructions, README, relevant docs, tests, and actual code. If no repository is available, use the user's supplied context and mark missing evidence.
- Search narrowly with `rg` and inspect relevant files; avoid loading entire memory histories or large data. Do not run repository scripts just to gather context unless needed and safe. Do not assert that something is absent until a reasonable targeted search has checked it.

## 2. Reconstruct and challenge

Keep a compact internal evidence map: claim, source/path, date or commit if material, status (`intended`, `implemented`, `observed`, `proposed`), applicability, and confidence. Distinguish current user intent from repository evidence and your inference. A file's existence does not prove its outputs are current; a past decision does not prove the current implementation follows it.

Test only relevant axes: goal, evidence/data, assumptions, meaningful alternatives, failure modes, and validation. For scientific work, distinguish exploration, prediction, and causal or mechanistic inference; identify the unit of analysis and obvious leakage or confounding risks when relevant. Challenge a premise directly when the repository contradicts it. Do not manufacture objections or expand the scope into an exhaustive audit.

Resolve apparent conflicts by checking authority, recency, **applicability**, and whether a source explicitly supersedes another. Implementation describes what ran; conventions and decisions may describe what should run. Ask only if a remaining conflict would materially alter the next step and the user owns that choice. Otherwise choose a defensible path and expose the assumption.

## 3. Gate every question

Before asking, check in order:

1. Can repository evidence or another available source answer it? Investigate.
2. Can you make a defensible technical choice within existing constraints? Decide and disclose the assumption.
3. Could plausible answers materially change the scientific question, data, method, interpretation, deliverable, or next consequential action? If not, drop it.
4. Does the user own this choice, and is it needed now? If not, defer it.

Ask the highest-value qualifying question, one at a time, with the evidence and a recommended default. Ask zero questions if the next action is already clear. Default to at most **two rounds and five total user questions**. This budget is a circuit breaker, not a target. At the limit, summarize established decisions, state recommended assumptions, and identify at most one genuinely blocking user decision. Do not restart a question tree or evade the budget by subdividing a question. If the user says “good enough,” stop and prepare the brief.

## 4. Converge and hand off

After each answer, ask internally: **Would plausible answers to any remaining user-owned unknown change the next consequential action?** If no, stop. Park issues whose answer is only needed at a later stage with a return condition. End with one status:

- `READY`: no consequential unknown remains.
- `READY_WITH_ASSUMPTIONS`: a stable next action exists with disclosed, reversible assumptions.
- `DECISION_REQUIRED`: one specific user-owned choice truly blocks a stable next action; present options, recommendation, and consequence of each. Do not pretend an arbitrary question cap resolves a blocker.

Normally provide a 200–500 word brief with: objective; repository evidence (cite file paths and sections/lines when helpful); chosen approach and why; assumptions; key challenge or failure mode and validation; parked items; next action. Scale down for simple tasks. Label inferences clearly. Do not copy project knowledge into a giant specification. Do not write to `.living/`, manifests, todo, or analysis files during grilling; let the subsequent work follow the repository's normal lifecycle. Do not assume another plugin skill can be invoked programmatically; describe the next action in ordinary language.
