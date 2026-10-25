# Verification

A finished job does not tell you the analysis is right. Did every planned step run? Did an input change? Does the number in the write-up match the saved table? `verify <hash>` compares the approved plan with the records that answer those questions. It reads the record and **never re-runs the analysis**, and it covers the same scripts as approval.

New to it? Start with [Tier 3](usage.md#tier-3-verify-reportable-work). **Full detail** on every check is in the [complete verification reference](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/verification-full.md).

![Conformity uses CONFORMS, CONFORMS_WITH_GAPS or DOES_NOT_CONFORM. Qualification separately uses qualified or not qualified and lists its dimensions. Neither assesses scientific validity.](figures/independent-assessments.svg)

These are the exact recorded vocabularies, not a combined health score. Read the reasons and missing evidence even when the conformity line reads CONFORMS.

For an optional practice exercise, use `/mycelium-extra:verify exercise`, then `exercise reveal` after your answer. These labelled synthetic records are printed only; nothing is saved. See [the exercise](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/exercise.md#quick-synthetic-review).

## What the report shows

The report opens with the status and five one-line rows. When every answer is yes, you can stop reading there:

```text
# Verify plan 84bb5fce: CONFORMS

Ran as planned  yes: 3 of 3 steps ran, 3 run(s), all completed
Numbers match   yes: 8 of 8 claimed cells match
Code checks     lint clean; 2 threshold finding(s) are Choices you approved
Not checked     3 Validation cell(s) are prose; whether the code implements the choices (that is review)
Next            confirm saving provenance to analysis/vaccine-response/provenance/
```

Each row says `yes`, `no`, `partly` or `n/a`, with the reason. `Not checked` always ends with what verify cannot see: whether the code implements the choices. `Next` names the one thing to do.

Below the rows, the report lists:

- **Each planned script:** ran, failed, no receipt, edited or deleted since it ran, or only passed to other code.
- **Command and folder runs** credited to the plan, such as an approved `snakemake` or `sbatch`.
- **Other runs:** explore runs, runs under another plan, and scripts that ran but are not in the plan.
- **Pinned inputs** that changed since approval.
- **Outputs:** each file on the `Outputs:` line, when it was written, and which run wrote it. Only a `supported` producer is named; otherwise it reads `unresolved` with its candidates.
- **Launch evidence:** a run is a *checked launch* only when the gate saw both its start and its end.
- **Lint** of the analysis code, with every waiver listed.
- **Claims:** each `<!-- claims -->` value is checked against the output cell it names, after rounding.
- **Citations:** DOI, PMID and arXiv identifiers, resolved only when you ask with `--resolve-citations`. Offline they stay a gap.
- **Plan evidence:** each read-only command the plan recorded in its `<!-- plan-evidence -->` block, re-run now. A row reads `still true` (the output is unchanged), `changed` (a gap, with the first line that differs) or `not checked` (a gap, with the reason: a command that may write, a timeout, an exit status of 2 or more). `< file` reads and is allowed; `>`, `>>` and `2>` are not.
- **Gate errors:** a hook that failed open did not check what it saw, and the report says so.

## Status

The report ends with one of three statuses.

- **`DOES_NOT_CONFORM`:** a *block*, such as a failed run, a failed required check, an edited script, a changed input, an output older than the approval, a lint finding neither fixed nor waived, a claim its cell contradicts, or a claim read from an explore run.
- **`CONFORMS_WITH_GAPS`:** no block, but something the records cannot show, such as a missing exit status, an unattributed output, a retry that changed the command, or a tool that was not installed.
- **`CONFORMS`:** no block and no gap.

A gap is never a pass. `CONFORMS` means the record agrees with the plan, not that the analysis is right.

## Qualification

Separately, `report` says whether the records are complete enough to report from. It is not a scientific judgement. Each dimension is `established`, `not established` (with its reason) or `not applicable`, and a run is `qualified` only when every applicable one is established:

| Dimension | Established when |
|---|---|
| authorization | every run is a checked launch of this approval, and no gate error or run outside a declared exact execution |
| completion | every planned step's latest attempt completed (exit 0; for Slurm, `sacct` shows `COMPLETED`) |
| code and input identity | scripts and pinned inputs are unchanged and compared by content hash |
| lineage | every declared output has a `supported` producer |
| required validation | every check marked `required` passed |
| claim linkage | each claim matched and its output has a supported producer |
| no blocking finding / no open gap | the report has none |

A `qualified` run is always `CONFORMS`; the reverse does not hold. `--require-reportable` exits 3 when a run is not qualified.

## What it writes

After you confirm, `verify` writes `<analysis>/provenance/`: the frozen plan, its receipts, an outputs table with sha256 and producer, the lint output, recorded environments, the report, a `PROVENANCE.md` index, and `evidence-<hash>.json`, a portable handoff for other tools. Commit it with the analysis. Writes are recoverable: an interrupted publication is restored or finished by the next `write`, and nothing is overwritten silently.

## When something fails

State every discrepancy the same way: **expected**, **observed**, **evidence**, **consequence**, whether the run stopped, and the **next legitimate action**. An operational retry (same command) stays visible and needs no new approval. A changed command after a failure is a gap until you say it is equivalent. A planned script edited after approval is a gap until you [`freeze`](approval-gate.md#freeze) it.

Also in the [complete reference](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/verification-full.md): output producers, recovery, rerun evidence, citations and the disclosure draft (`verify disclose <hash>`, a read-only methods paragraph where each sentence names its record).
