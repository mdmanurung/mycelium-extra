# C3: plan-review redaction audit

Roadmap task [C3](../roadmap/03-robustness.md), 2026-10-16. The question: does the packet an agent assembles for Codex and Biomni obey the redaction rules in `skills/plan-review/references/review-contract.md`, and is `redactions:` filled in rather than left `[]`?

## What was audited, and what was not

I read the skill and its four references as written, then built three packets from the C1 fixture (`tests/fixtures/mycelium-project`) and ran the new check on them. I did not run a model through `plan-review`, so how an agent behaves when it assembles a packet is still unobserved. The rules below are enforced only where the agent runs `scripts/presend_check.py`, which `SKILL.md` now tells it to do; a skill is an instruction, not a hook.

| Packet | Content | Result |
|---|---|---|
| A | the baseline plan, estimand and sizes; no identifiers | exit 0: nothing flagged, and it says the check is pattern-based |
| B | A plus donors `D07`, `D12`, samples `D07_day28`, `D12_day0`, a GitHub-shaped token, an AWS-shaped key, an email, a home path; `redactions: []` | exit 3, 7 flags (3 identifiers and the 4 secrets and contact details above), `redactions:` is empty, do not send |
| C | one donor ID and `redactions:` filled in | exit 2, 1 flag, the user decides |

No flag prints a matched value: a secret shows its first 3 characters and its length, an identifier its first character. The tokens in the tests are built from parts so no secret-shaped string sits in the repository.

## Gaps found

| # | Gap | Fix |
|---|---|---|
| G1 | The rules were prose. Nothing compared a packet with them. | `scripts/presend_check.py`, run before the user sees the packet. |
| G2 | `redactions:` had no entry shape, and `[]` was the template default, so a packet could ship identifiers with `redactions: []`. | Entry shape (`kind`, `field`, `replaced_with`, never the value). `[]` is acceptable only after a clean check. Flags with `redactions:` empty exit 3: do not send. |
| G3 | The exclusion list missed contact details, host names and home paths, URLs with a password, free-text clinical notes and person-linked dates, and did not name the ID columns of the plan's own input tables as identifiers. | Contract list extended; the check covers emails, home paths, IPv4 addresses, URL credentials and the ID-like columns of the tables named under `Inputs:`. |
| G4 | Codex runs rooted in the repository and can open any file there, `data/` and `.env` included. The packet rules do not reach what it reads. | A data-free workspace of the explicitly selected attachments built by `review_packet.py prepare` (see C11 below); otherwise a role-prompt instruction, and the reviewer status says Codex could read beyond the packet. An instruction is not enforcement. |
| G5 | The user was shown the packet but not any check of it, and the report did not record one. | The check's output is shown with the packet and the result goes in the reviewer status. |
| G6 | A clean result could be read as clearance. | The output and the contract say a clean result is not evidence that nothing sensitive remains. |
| G7 | A flag could echo the secret into the transcript. | Matched values are masked. |

## Known misses (documented, not fixed)

A secret with no keyword and no known shape (a bare base64 string); a name, a diagnosis or an age in free text; an identifier in a table the plan does not name under `Inputs:`, including the sample IDs that are only column headers of a counts table; re-identification by combining facts; a packet edited after the check and sent by a route that does not call `review_packet.py verify`. A known false positive: a value of an ID column that is also an ordinary word (a `sample` column holding `control`) is flagged wherever the word appears, and a four-part version number looks like an IPv4 address. `skills/plan-review/tests/test_presend_check.py` pins each of these.

## C11: binding consent to the bytes sent

Roadmap task C11, 2026-10-17. The gap C3 left: the scan ran on a packet, the user agreed in conversation, and nothing tied either to the bytes that were then sent. `scripts/review_packet.py` (`prepare`, `preview`, `verify`) and the `--json` and SHA-256 additions to `presend_check.py` close the part that a script can close. Demonstrated by `skills/plan-review/tests/test_review_packet.py` and `test_presend_check.py`, run on Python 3.6 and 3.12:

| Behaviour | Test |
|---|---|
| The scan result names the SHA-256 of the exact bytes it read, as text and as JSON; a one-character edit changes it. This test failed before the change. | `test_gap_a_scan_result_names_the_bytes_it_covered`, `test_json_result_has_the_packet_hash...`, `test_text_result_names_the_packet_hash` |
| Unread and unsupported input tables are named by masked name and reason; no value or path appears in full. | `test_json_result_has_the_packet_hash_and_names_coverage_without_values` |
| Prepare, preview, a consent record for the digest, then verify succeeds and prints exactly `packet.txt` plus the selected attachments. The digest is the SHA-256 of the manifest bytes, which hold the packet hash. | `test_prepare_preview_consent_verify...`, `test_manifest_digest_covers_the_packet_hash` |
| `verify` refuses: no consent record; a packet edited after consent; an attachment changed in the snapshot or in the source after prepare; a consent whose digest is another digest, a prompt that does not name this digest, or a time not after the packet's; a file in the packet folder the manifest does not list (reported by `preview` too). | `test_no_consent...`, `test_edited_packet...`, `test_changed_attachment...`, `test_source_attachment...`, `test_consent_for_another_digest...`, `test_consent_prompt...`, `test_consent_older...`, `test_unexpected_extra_file...` |
| `prepare` refuses attachments under `data/`, outside the project, missing, symlinked into `data/`, or of a table type, and refuses a packet the scan says not to send. Flag output for the packet and attachments never carries a token or email in full. | `test_attachment_boundary`, `test_unredacted_flag...`, `test_flagged_values_are_never_echoed` |
| No script path writes a consent record. | `test_no_consent_refuses_and_scripts_never_write_one` |

Not demonstrated, and stated limits:

- The consent record is written by the approval gate after it observes the user's `send packet <digest12>` prompt. That gate change has not landed, so no real consent record exists yet; the tests write the record directly to simulate it, and the record format is a contract the gate change must meet.
- The mechanism is cooperative. It sends nothing and does not stop an agent with unrestricted shell access from sending other bytes or writing a consent record. No real Codex or Biomni call was made, so what a reviewer then does with the workspace is unobserved; a read-only Codex sandbox is not shown to confine reads to the workspace.
- The attachment scan is the same pattern-based scan as the packet's, shown to the user as counts and masked values; it is not a clearance. Consent is not consumed by `verify`: it holds for that digest until the files change.
