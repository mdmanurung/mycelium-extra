# Five Safes and the consent step

The `send packet` consent records a disclosure decision apart from permission to run. That is the Five Safes idea of a separate output decision. Extra records the decision. It does not enforce access or export.

## The framework

The UK Data Service lists five safes: safe data ("data is treated to protect any confidentiality concerns"), safe projects ("research projects are approved by data owners for the public good"), safe people ("researchers are trained and authorised to use data safely"), safe settings ("a SecureLab environment prevents unauthorised use") and safe outputs ("screened and approved outputs that are non-disclosive").

Source: UK Data Service, "What is the Five Safes framework?", <https://ukdataservice.ac.uk/help/secure-lab/what-is-the-five-safes-framework/>, accessed 2026-11-13. The framework was introduced by Desai, Ritchie and Welpton (2016); this page did not read that paper.

## How the consent maps

Approving a grill plan lets scripts run. Sending a review packet to an outside reviewer is a different act: it discloses material. Extra keeps the two apart. The second needs its own typed line, `send packet <digest>`, bound to the digest of the packet. See [The consent step](reference/skills/plan-review.md#the-consent-step).

This resembles the safe-outputs check: someone looks at what leaves and says yes or no for that exact content. The match is loose. In a Trusted Research Environment (TRE) a trained checker screens outputs. Here the researcher is the checker and the screen is the packet shown before consent.

## What Extra enforces

- Consent exists only as the researcher's typed prompt, recorded by the gate.
- `review_packet.py verify` refuses a packet whose bytes, attachments or consent do not match the digest.
- Any change to the packet needs a new digest and a new consent.

## What Extra does not enforce

- Who may read the data (safe people, safe settings). The host or TRE decides.
- Whether files leave the machine by another route. Sending only the verified files is the agent's instruction. A shell can send other bytes.
- Whether the output is non-disclosive. Extra shows the packet and the check's output. The researcher judges.
- Data treatment and project approval (safe data, safe projects). These sit with the data owner.

Run Extra inside the host's controls. Do not treat the consent record as a substitute for them.

## Audit trail limit

Extra builds no hash chain over its records. A chain kept next to the records can be rewritten together with them, so it proves nothing to an outside auditor. External audit needs a checkpoint kept somewhere the writer cannot change: a signed commit pushed to a remote, a ticket, or a copy held by the data owner.

Extra already writes durable checkpoints. `track-changes --save-checkpoint` saves `analysis/name/journal/checkpoints/*.json`, and you commit them. See [Historical Journal and durable checkpoints](focus-and-track-changes.md#historical-journal-and-durable-checkpoints). Retaining them independently is up to you.
