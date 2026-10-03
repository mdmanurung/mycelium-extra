---
name: plan-review
description: Read-only, pre-approval challenge of a sourced Mycelium Extra grill plan by independent Codex engineering and Biomni biomedical reviewers. Claude assembles one evidence packet, preserves disagreement, and recommends amendments without editing or approving the plan. Use after grill and before plan approval when the user requests independent review. In Codex, act only as the engineering reviewer; do not claim a Claude-led dual review.
---

# Mycelium Extra: Plan review

Challenge a proposed plan before approval. This skill is consultation only: do not run project analysis, edit repository files or `.living/`, create gate receipts, approve a plan, or apply recommendations. A review is not an execution authorization.

## 1. Locate the draft

- Find the current grill brief and its complete plan table in the conversation or a path the user names. If several candidates exist, ask which draft to review. Do not silently review an older approved plan.
- Read only the relevant repository instructions, applicable `.living/` decisions and findings, manifests, data-contract results, and code paths. Distinguish proposed steps from observed implementation. Cite paths and headings/lines.
- Use [review-contract.md](references/review-contract.md) to build one canonical packet for both reviewers. Include the objective, estimand, unit of inference, design, input/data summary, constraints, sourced decisions and findings, exact proposed plan, assumptions, and validation. Mark unknown fields unknown. Exclude raw data, participant identifiers, credentials, unpublished full tables, and irrelevant history. If a necessary fact cannot be shared, say so and stop that external review.
- The packet leaves the machine (Codex to OpenAI, Biomni to Phylo, which also bills credits). Show the user the packet and which reviewers will receive it, and send only after the user agrees.

## 2. Route by host

- **Claude Code lead:** request the independent Codex review using [codex-review.md](references/codex-review.md). Request the Biomni review as one consult-only Biomni task following [biomni-review.md](references/biomni-review.md). Send the same factual packet; add only role-specific questions. Reviewers may work in parallel if both are read-only.
- **Codex host:** this invocation can supply the Codex engineering critique, but it cannot impersonate an independent second Codex reviewer or Claude adjudicator. Return the structured Codex critique to the user/Claude. Label Biomni and Claude synthesis unavailable here unless those separate actors actually ran.
- An unavailable, failed, timed-out, or malformed reviewer is `unavailable` or `invalid`, never a clean review. Never fabricate a missing review or claim that two independent reviewers agreed when only one responded.

## 3. Normalize and adjudicate

- Normalize responses to the common issue schema in [review-contract.md](references/review-contract.md). Keep each reviewer's original ID, evidence, uncertainty, and recommendation. Verify cited scientific sources before using them for material plan changes.
- Use [synthesis.md](references/synthesis.md) in Claude Code. Record agreement, single-reviewer concerns, conflicts, accepted and rejected recommendations, and user-owned choices. Consensus is not required.
- Give proposed amendments separately from the plan. Do not rewrite the plan, its Source column, or `.living/` during this skill. If the user later requests a revised plan, source accepted reviewer choices as `user (accepted review: codex)` or `user (accepted review: biomni; PMID ...)` with the underlying evidence, then present the entire revised plan for normal approval. A prior approval does not cover a changed plan.

## 4. Report

State which reviewers actually ran, what evidence each saw, any redactions or missing context, and whether each result was complete, unavailable, or invalid. Provide the synthesis and one concrete next action. Keep raw reviewer transcripts ephemeral locally (a Biomni task persists in the user's Phylo project until they delete it); do not write `.mycelium-extra/reviews/` or durable provenance in this first version.

Stop here. Execution remains with Mycelium's analyze skill after the normal Mycelium Extra approval; verification remains with Mycelium Extra verify.
