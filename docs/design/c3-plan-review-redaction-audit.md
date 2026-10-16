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
| G4 | Codex runs rooted in the repository and can open any file there, `data/` and `.env` included. The packet rules do not reach what it reads. | Data-free copy via `git archive` of named paths; otherwise a role-prompt instruction, and the reviewer status says Codex could read beyond the packet. An instruction is not enforcement. |
| G5 | The user was shown the packet but not any check of it, and the report did not record one. | The check's output is shown with the packet and the result goes in the reviewer status. |
| G6 | A clean result could be read as clearance. | The output and the contract say a clean result is not evidence that nothing sensitive remains. |
| G7 | A flag could echo the secret into the transcript. | Matched values are masked. |

## Known misses (documented, not fixed)

A secret with no keyword and no known shape (a bare base64 string); a name, a diagnosis or an age in free text; an identifier in a table the plan does not name under `Inputs:`, including the sample IDs that are only column headers of a counts table; re-identification by combining facts; a packet edited after the check. A known false positive: a value of an ID column that is also an ordinary word (a `sample` column holding `control`) is flagged wherever the word appears, and a four-part version number looks like an IPv4 address. `skills/plan-review/tests/test_presend_check.py` pins each of these.
