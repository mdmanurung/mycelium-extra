# Gaps and passes

A clean result and a missing result look the same if you only count the failures. Mycelium Extra counts them apart. The rule is short: **a gap is never clean.** When the tool could not check something, it says "gap" and keeps it visible. It does not call it a pass.

![A supported check says what the inspected evidence establishes. A gap says evidence is absent or too weak. A blocking finding records a contradiction or failure. Scientific validity is a separate question.](../figures/evidence-states.svg)

A gap is absence of evidence, while a block is evidence of a problem. Exact verification statuses and qualification remain separate from scientific judgement.

## What counts as a gap

A gap is evidence the records could not establish. It is not a failure (nothing was found wrong) and not a pass (nothing was found right). The usual causes:

- the check never ran (a linter is not installed, a service was offline, a Slurm job is still pending);
- the check ran and its answer could not be used (it timed out, its output was unreadable, a receipt line was damaged);
- the record is too weak to say (an input pinned by size and time only, an output whose producer is only a candidate, an exit status the host did not report);
- something ran that the plan does not describe (a run with no matched launch, a step outside an exact-execution plan).

Failures are different. A failed run, an edited script, a changed input or a claim its cell contradicts is a **block**. A block is evidence of a problem, and a gap is the absence of evidence.

## Where gaps appear

**In `verify`.** The report ends with one status line:

| Status | Meaning |
|---|---|
| `CONFORMS` | the checked record agrees with the plan, and no finding is a gap |
| `CONFORMS_WITH_GAPS` | nothing blocks, but some evidence is missing; each gap is listed under Findings |
| `DOES_NOT_CONFORM` | a blocking mismatch or failure was found |

The top of the report has rows (`Ran as planned`, `Numbers match`, `Code checks`, `Not checked`, `Next`) that say `yes`, `no`, `partly` or `n/a` with a reason. `partly` means the headline holds but something underneath is unresolved. `Not checked` always ends with what verify cannot see. A separate qualification table says whether the records are complete enough to report from; it is not a scientific judgement. Details: [Status](../verification.md#status) and [Qualification](../verification.md#qualification).

**On the approval card.** The `Coverage` row says how many steps have a Validation cell bound to a check and how many are prose only. The `Not established before running` block names an input or script whose pin is missing or weaker than a content hash. An absent block means none of these was found, not that the plan is covered. A lint line can read `not checked (...)`. See [the card](../approval-gate.md#approving-a-plan).

**In track-changes.** Every item keeps three things apart: what was observed, what is only a potential analytical implication, and what is unknown. Each report ends with a line of what it did not see (shell-made edits, file reads, subagent work not marked in the transcript). A changed number is an observed edit, not a changed conclusion. "No warning" is never evidence of no drift. See [Focus and track changes](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/focus-and-track-changes.md).

**In the gate.** A hook that failed open writes a record to `.mycelium-extra/gate-errors.jsonl` and says so. `verify` later turns that into a gap for the window it covers.

## How to read a status

1. Read the status line, then the `Next` row. It names the one thing to do.
2. For `CONFORMS_WITH_GAPS`, read the gaps under Findings. For each one, decide whether it matters for the claim you want to make. Close it (run the check, resolve the citation, freeze the script) or say in the write-up that the point was not checked.
3. For `DOES_NOT_CONFORM`, fix the first block. Do not weaken the plan, a threshold or a claim to make the status change.
4. Read `Not checked` and the "Not visible to verify" list even on `CONFORMS`. `CONFORMS` means the records agree with the plan. It does not say the code implements the plan's choices, or that the science is right.

Two things look like passes and are not:

- A resolved citation means the identifier exists and matches the text next to it. It does not mean the paper supports the sentence.
- A verified claim means the number matches its output cell. It does not mean the number is true.

## Why this matters

If gaps were quiet, the status would drift toward "looks fine" whenever a tool broke or a service was down. The record would then be most confident exactly where it knew least. Keeping gaps loud is what lets you trust a plain `CONFORMS`. See [What is not guaranteed](not-guaranteed.md) for the limits that remain.
