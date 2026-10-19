# Ask a second model to review a plan

`plan-review` is an optional, read-only challenge of a grill plan by independent reviewers (Codex for engineering, Biomni for biomedicine) before you approve. It approves nothing.

## What you control here

- **Your typed word:** `send packet <digest>`, typed by you as a prompt of its own. Without it nothing leaves the machine. The agent does not type it or write the consent record.
- **Shown to you:** the exact packet, the pre-send scan, the attachment list, which reviewers will receive it, and the one line you must type.
- **To say no:** do not type the line. A reviewer that did not run is `unavailable`, never a clean review.

## Steps

1. Run `grill` and get a plan, but do not approve yet.
2. Invoke the review in Claude Code or OpenCode (Codex can give only the engineering critique):

   ```text
   /mycelium-extra:plan-review
   ```

3. The agent checks the reason on every `default:` row (`default_reasons.py`), builds one packet, and scans it for secrets, contact details, home paths and participant identifiers from the tables under `Inputs:`. The scan is pattern-based; exit 0 is not a clearance.
4. It prepares an immutable copy of the packet and the attachments it picked, and previews the digest. Read the attachment list: attach code and documents only, never data tables or credentials.
5. Type, using the digest it showed (12 or more hex characters):

   ```text
   send packet 0123456789ab
   ```

   (`0123456789ab` is a placeholder.) The gate records your consent. Immediately before sending, `verify` recomputes the hashes and refuses if any byte changed since you agreed.
6. Read the synthesis: which reviewers ran, agreement, single-reviewer concerns, conflicts, and the strongest undecided crux. Proposed amendments come separately; the plan is not edited. If you accept one, `grill` presents the whole revised plan and you approve its new hash.

Biomni runs on cloud credits, and a Biomni task persists in your own project until you delete it. Codex sends to OpenAI.

## Worked example

Real output of the first check, run on the fixture plan `tests/e2e/plans/baseline_plan.md` (synthetic names):

```text
Default reasons: 1 default(s), each with a reason.
```

No captured transcript of a full review exists, because it needs external services, so none is shown.

## What this does not guarantee

A second model is a second opinion, not a check. It can agree and be wrong, and its sources can be invented, so verify citations before a material change. The consent mechanism is cooperative: it shows that what was sent is what you approved, but cannot stop an agent with unrestricted shell access from sending other bytes. See [what this does not guarantee](../concepts/not-guaranteed.md).

## Reference

[plan-review](../reference/skills/plan-review.md) · [Advanced: review packets and consent](../advanced.md#plan-review-packets-and-consent) · next: [harden against repeats](harden-against-repeats.md)
