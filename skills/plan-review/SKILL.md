---
name: plan-review
description: Read-only, pre-approval challenge of a sourced Mycelium Extra grill plan by independent Codex engineering and Biomni biomedical reviewers. Claude assembles one evidence packet, preserves disagreement, and recommends amendments without editing or approving the plan. Use after grill and before plan approval when the user requests independent review. In Codex, act only as the engineering reviewer; do not claim a Claude-led dual review.
---

# Mycelium Extra: Plan review

Challenge a proposed plan before approval. This skill is consultation only: do not run project analysis, edit repository files or `.living/`, create gate receipts, approve a plan, or apply recommendations. A review is not an execution authorization.

## 1. Locate the draft

- Find the current grill brief and its complete plan table in the conversation or a path the user names. If several candidates exist, ask which draft to review. Do not silently review an older approved plan.
- Read only the relevant repository instructions, applicable `.living/` decisions and findings, manifests, data-contract results, and code paths. Distinguish proposed steps from observed implementation. Cite paths and headings/lines.
- Check the reason on each default. Run, with the plan table as it stands:

  ```bash
  python3 - --plan <(cat <<'EOF'
  <the plan>
  EOF
  ) < <skill-dir>/scripts/default_reasons.py
  ```

  It names each plan row whose `default:` has no reason, a reason under three words, or only an empty phrase (the list is `EMPTY_PHRASES` at the top of the script). It is advisory: it never blocks the review or approval, and it does not judge whether a reason is correct. Put its output in the packet's `unknowns:` and in the report, and propose a reason or a `user` source for each flagged row as an amendment. Exit 3 (no plan table found) or a failed run means the check did not run; say so, never report it as clean.
- Use [review-contract.md](references/review-contract.md) to build one canonical packet for both reviewers. Include the objective, estimand, unit of inference, design, input/data summary, constraints, sourced decisions and findings, exact proposed plan, assumptions, and validation. Mark unknown fields unknown. Exclude raw data, participant identifiers, credentials, unpublished full tables, and irrelevant history (the full list and the `redactions:` entry shape are in the contract). If a necessary fact cannot be shared, say so and stop that external review.
- Check the packet before anything leaves the machine. Run, with the packet as it stands and the repository root:

  ```bash
  python3 - --packet <(cat <<'EOF'
  <the packet>
  EOF
  ) --repo <repository-root> < <skill-dir>/scripts/presend_check.py
  ```

  It flags likely secrets, contact details, home paths, and the participant identifiers found in the tables the plan names under `Inputs:`. Exit 3 means flags with empty/malformed `redactions:` or missing/truncated input coverage: do not send until the flags and coverage gaps are disclosed and resolved, or the user explicitly consents to the stated gap. Redaction entries require nonempty `kind` and `field` strings; `replaced_with` is optional. Known short IDs use exact token boundaries. Exit 2 means flags with `redactions:` filled in: show them to the user. Exit 0 is not a clearance: the check is pattern-based and says so. Exit 1 or a failed run means it did not run; say so, never report it as clean.
  Quote or backtick an input path containing spaces. Missing, unreadable, or truncated input tables are reported as unchecked identifier coverage; carry those gaps into the packet and report.
- `presend_check.py --json` (same arguments) prints the result as JSON: the packet's SHA-256, each flag as line, kind and masked value, and each unread or unsupported input as a masked name and reason. A flag never carries its value in full.
- The packet leaves the machine (Codex to OpenAI, Biomni to Phylo, which also bills credits). Show the user the packet, the check's output, and which reviewers will receive it, and send only after the user agrees. The agreement is bound to the exact bytes, in this order:
  1. **Prepare.** Save the packet to a file, then run `python3 <skill-dir>/scripts/review_packet.py prepare --packet <file> --attach <repo-relative code or doc file> ...` from the project root. It re-runs the scan and refuses what the scan says not to send. It writes an immutable copy of the packet and of each explicitly selected attachment under `.mycelium-extra/review-packets/<digest>/` with a manifest of their sizes and SHA-256 hashes. The digest is the SHA-256 of that manifest, so it covers the packet's hash. Attach only code and documents the reviewer needs: never `data/`, tables, raw or participant-level files, credentials, or `.env`; the script refuses those and unlisted file types.
  2. **Preview.** Run `review_packet.py preview --digest <digest>` and show the user its output: the digest, the attachment list, the scan counts, and the line the user must type.
  3. **The user types** `send packet <first 12 or more hex characters of the digest>` as a prompt of their own. Do not type it, paraphrase it, or write a consent file: consent is the user's observed prompt. The approval gate records it as `.mycelium-extra/review-consent/<digest>.json` and replies with the digest and the next step. Only that exact prompt counts (nothing around it, a prefix of 12 to 64 hex characters that names one prepared packet); a prompt embedded in longer text, an ambiguous prefix or an unknown digest records nothing. Never create the record yourself to get past `verify`.
  4. **Verify, then send.** Immediately before the send, run `review_packet.py verify --digest <digest>`. It recomputes the hashes, refuses if any byte differs, if the folder holds a file the manifest does not list, if an attachment changed since `prepare`, or if the consent record does not name this digest or is not newer than the packet. On success it prints the one list of files to send. Send exactly those files by the route in the reviewer reference, nothing else. Any change to the packet or an attachment means a new `prepare` and a new `send packet` from the user.
  The mechanism is cooperative, not a sandbox: it sends nothing, and it cannot stop an agent with unrestricted shell access from sending other bytes. It shows that what you send is what the user approved.

## 2. Route by host

- **Claude Code lead:** request the independent Codex review using [codex-review.md](references/codex-review.md). Request the Biomni review as one consult-only Biomni task following [biomni-review.md](references/biomni-review.md). Send the same factual packet; add only role-specific questions. Reviewers may work in parallel if both are read-only.
- **Codex host:** this invocation can supply the Codex engineering critique, but it cannot impersonate an independent second Codex reviewer or Claude adjudicator. Return the structured Codex critique to the user/Claude. Label Biomni and Claude synthesis unavailable here unless those separate actors actually ran.
- A reviewer that was not run, failed, timed out, or was refused by `verify` is `unavailable`; one whose output is malformed is `invalid`; one still running (for example Biomni after its bounded polling) is `pending`. None of these is a clean review, and none is an empty completed review: only `status: complete` with an empty `issues` list means the reviewer found nothing. Never fabricate a missing review or claim that two independent reviewers agreed when only one responded.

## 3. Normalize and adjudicate

- Normalize responses to the common issue schema in [review-contract.md](references/review-contract.md). Keep each reviewer's original ID, evidence, uncertainty, and recommendation. Verify cited scientific sources before using them for material plan changes.
- Use [synthesis.md](references/synthesis.md) in Claude Code. Record agreement, single-reviewer concerns, conflicts, accepted and rejected recommendations, and user-owned choices. Consensus is not required.
- Give proposed amendments separately from the plan. Do not rewrite the plan, its Source column, or `.living/` during this skill. If the user later requests a revised plan, source accepted reviewer choices as `user (accepted review: codex)` or `user (accepted review: biomni; PMID ...)` with the underlying evidence, then present the entire revised plan for normal approval. A prior approval does not cover a changed plan.

## 4. Report

State which reviewers actually ran, what evidence each saw (the digest and the attachment list they received), any redactions or missing context, the pre-send check's result, and whether each result was complete, unavailable, or invalid. Provide the synthesis and one concrete next action. Keep raw reviewer transcripts ephemeral locally (a Biomni task persists in the user's Phylo project until they delete it); do not write `.mycelium-extra/reviews/` or durable provenance in this first version.

Stop here. Execution remains with Mycelium's analyze skill after the normal Mycelium Extra approval; verification remains with Mycelium Extra verify.
