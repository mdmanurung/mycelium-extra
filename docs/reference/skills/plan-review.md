# plan-review

Read-only challenge of a grill plan by independent reviewers before you approve it. Guide: [Second-model review](../../guides/second-model-review.md). It costs cloud credits and sends a packet off the machine, so it is off until you invoke it.

## Synopsis

`/mycelium-extra:plan-review` (Codex: `$mycelium-extra:plan-review`). The skill runs three scripts.

```bash
sh <skill-dir>/../../hooks/py.sh - --plan <(cat <<'EOF' ... EOF) < <skill-dir>/scripts/default_reasons.py
sh <skill-dir>/../../hooks/py.sh - --packet <(cat <<'EOF' ... EOF) [--repo DIR] [--json] < <skill-dir>/scripts/presend_check.py
sh <skill-dir>/../../hooks/py.sh <skill-dir>/scripts/review_packet.py (prepare|preview|verify) [--packet FILE] [--attach FILE ...] [--digest HEX] [--root DIR]
```

`review_packet.py` is the one script that runs by path.

## Scripts and options

| Script | Option | Meaning |
|---|---|---|
| `default_reasons.py` | `--plan` | The plan text (required, by process substitution). Names each plan row whose `default:` has no reason, a reason under three words, or only an empty phrase. Advisory: never blocks, and does not judge whether a reason is correct. `verify` runs the same check on the frozen plan. Exit 3 (no plan table) or a failed run means it did not run; that is never reported as clean. |
| `presend_check.py` | `--packet` | The packet text (required). Flags likely secrets, contact details, home paths and participant identifiers found in tables named under `Inputs:`. |
| | `--repo` | Repository root, to read those tables. |
| | `--json` | Structured result: the packet's SHA-256, each flag as line, kind and masked value, each unread input. |
| `review_packet.py` | `prepare` | With `--packet FILE` and `--attach FILE ...`: re-runs the scan, refuses what it says not to send, writes an immutable copy under `.mycelium-extra/review-packets/<digest>/` with a manifest of sizes and hashes. The digest is the manifest's SHA-256. Refuses `.env` files and types outside its code-and-document list; it does not look inside an allowed type. |
| | `preview` | With `--digest`: the digest, attachments, scan counts and the line you must type. |
| | `verify` | With `--digest`: recomputes hashes; refuses if any byte differs, an unlisted file is present, an attachment changed, or the consent record does not name this digest or is not newer than the packet. Prints the one list of files to send. |
| | `--root` | Project root (default: nearest folder with `.mycelium-extra/gate.json`). |

`presend_check.py` exits: 0 no flags (not a clearance: it is pattern-based), 2 flags with `redactions:` filled in (show them to you), 3 flags with missing or malformed `redactions:`, no single `redactions:` line, or missing input coverage (do not send), 1 did not run. Exit 1 with `needs Python 3.9 or later` is `py.sh` finding no Python.

## The consent step

1. The agent prepares the packet and shows you the packet, the check's output and which reviewers receive it.
2. **You type** `send packet <12 to 64 hex characters of the digest>` as a prompt by itself. The gate records it as `.mycelium-extra/review-consent/<digest>.json`. Anything around the line, an ambiguous prefix or an unknown digest records nothing.
3. The agent runs `review_packet.py verify`, then sends exactly the listed files.

Any change to the packet or an attachment needs a new `prepare` and a new `send packet` from you.

## Reviewers and routes

| Host leading | Reviewers |
|---|---|
| Claude Code | Codex engineering review and Biomni biomedical review (separate read-only requests), then synthesis |
| OpenCode | the same, via the Codex CLI and the connected Biomni MCP; a missing one is `unavailable` |
| Codex | engineering critique only; Biomni and synthesis are labelled unavailable |

A reviewer that did not run, failed, timed out or was refused is `unavailable`; malformed output is `invalid`; still running is `pending`. Only `status: complete` with an empty `issues` list means a reviewer found nothing. Each objection is classified `substantiated`, `refuted`, `unresolved` or `out_of_scope`, and the synthesis leads with the strongest undecided crux. Details are in `references/` (`review-contract.md`, `codex-review.md`, `biomni-review.md`, `synthesis.md`).

## Reads and writes

Reads the grill brief, repository instructions, `.living/` decisions and findings, manifests, data-contract results and code. Writes only the packet folder and, by your typed prompt, the consent record. It does not edit the plan or `.living/`, create receipts, approve anything, or write `.mycelium-extra/reviews/`. Proposed amendments are given apart from the plan; a revised plan goes through normal approval. A review is not an execution authorisation.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| Consent exists only as your typed `send packet` prompt, recorded by the gate | Enforced by the gate |
| `verify` refuses a packet whose bytes, attachments or consent do not match | Enforced by the script |
| Sending only the verified files | The agent's instruction: the mechanism is cooperative, not a sandbox, and cannot stop an agent with shell access from sending other bytes |
| Showing you the packet and reviewers first; not typing or paraphrasing your consent; never calling a missing review complete | The agent's instruction |

Raw reviewer transcripts stay local and ephemeral; a Biomni task persists in your Phylo project until you delete it.
