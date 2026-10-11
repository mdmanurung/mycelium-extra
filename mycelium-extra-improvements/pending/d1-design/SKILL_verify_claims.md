---
name: verify-claims
description: Read-only check that the quantitative claims in a report match the artifacts a plan's runs wrote. Extracts typed numeric claims (p-values, fold changes, counts, percentages, intervals) from Markdown, locates values in the plan's output tables, JSON, and logs, and verdicts each claim VERIFIED, MISMATCH, UNVERIFIED, or EXPLORE-ONLY. Use after a reportable run has produced a report, before findings are recorded from it or it is shared, and after any edit that touches a number in a checked report. Not for recomputing statistics, checking figures, checking prose without numbers, or checking explore outputs (they are not reportable; a clean check would lend them status they do not have). Never use it to rescue a failing report by editing text, artifacts, thresholds, or the claims block.
---

# Verify claims

Check that a report's numbers match its artifacts. Catch transcription errors before
they enter the record. This skill checks; it never fixes.

## 1. When to run, when not

Run it:

- After a reportable run, when the plan's `Outputs:` line names a Markdown report.
  `verify <hash>` runs this stage itself; invoke standalone only for a report outside
  a plan's provenance.
- Before a finding is recorded from a report, and before a report leaves the
  repository.
- After any edit that touches a number in a previously checked report.

Do not run it:

- On explore outputs. They are not reportable, and a clean claims check would lend
  them status they do not have.
- To recompute the analysis. The checker compares text to artifacts; it does not
  rederive statistics. A wrong method with faithfully transcribed numbers passes.
- On a report whose claims carry no numbers. Say there is nothing to check.
- Repeatedly while a report is still being drafted. Run once when the report is
  final for the session, or after numeric edits.

## 2. Invocation

Read-only. Run from stdin so Mycelium's hooks do not treat it as a post-action run:

```bash
python3 - claims <report.md> [--plan <hash>] < <plugin-root>/skills/verify/scripts/claims.py
```

- With `--plan`, artifacts come from that plan's receipts. Without it, artifacts are
  the analysis folder's `outputs/` — say so in your summary, because the basis is
  weaker.
- If the artifact basis is ambiguous (several plans, several `outputs/` folders),
  ask the user at most one question. Otherwise ask none: this is a check, not an
  interview.
- Budgets (`claims_max_file_mb`, `claims_max_cells`, `claims_seconds`) come from
  `gate.json`. A budget-truncated check reports itself partial; treat partial as a
  gap, never as clean.
- If the script errors or its output does not parse, report the stage as a gap.
  Never report a report as clean because the checker failed.

## 3. Verdicts and what to do with each

- **VERIFIED** — the value matches a located artifact value in a matching context.
  `verified-transform` means a convention hop was needed (% ↔ fraction, fold ↔
  log2, p ↔ −log10 p); still verified, noted in the counts.
- **MISMATCH** — stop. Show each mismatch with report line, expected vs. observed,
  and the artifact coordinate. Do not edit the report or the artifact yourself; the
  user decides which is wrong. If the artifact is wrong, the plan may need
  re-running: name grill as the route.
- **EXPLORE-ONLY** — the number is real but matches only an explore-run output.
  Fail. Name grill's promote-explore flow as the route; never copy the value into a
  reportable context.
- **UNVERIFIED** — list as gaps with line numbers. Common causes: derived
  statistics, literature values, figure-only claims. The user judges each. An
  authored claims block (§4) that is mostly unverified fails the check.
- **EXCLUDED** — stoplisted numbers (versions, citations, accessions, years, figure
  references). Counted in the summary, not listed.

All verified: say so, with the counts. Do not claim the analysis is correct — the
checker compares text to artifacts, nothing more.

## 4. Authoring claims blocks

When you write a report in a gated repository, declare the load-bearing claims so
this check runs first-class:

```markdown
<!-- claims
- pvalue padj = 0.032 | IL7R, monocytes DE
- count n = 48 | donors passing QC
- percent 34% | cells annotated NK
- external HR = 0.72 | Smith 2024, comparator arm
-->
```

One claim per line: kind, qualifier + value, `|`, context. `external` marks values
from outside the plan's artifacts (literature, reference databases); they are
excluded from gap counts. Declare few — the claims a reader would quote. The block
is checked exactly; regex-extracted prose claims are best-effort around it.

Never add or edit a claims block to make a failing check pass. If a claim fails,
the claim or the artifact is wrong; the block is not a tuning knob.

## 5. Reporting to the user

One summary, then stop:

```
claims: reports/week3.md — 41 verified (3 via transform), 2 mismatch, 17 unverified, 1 explore-only
  MISMATCH  L42  "padj = 0.032" — expected 0.032, observed 0.041
            evidence: outputs/de_results_monocytes.csv, column padj, row IL7R
  EXPLORE   L88  "AUC = 0.91" — matches only explore-run output tmp/explore_3/auc.txt
```

End with a status line of its own: `Claims: PASS`, `Claims: PASS_WITH_GAPS (N
unverified)`, or `Claims: FAIL (N mismatch[, M explore-only])`. Cite line numbers;
do not paste the JSON. The machine-readable record is `claims_report.json` (schema
`mycelium-extra.claims.v1`); under `verify <hash>` it joins the provenance bundle
after the user confirms.

## 6. Guardrails

- Read-only. Never edit the report, the artifacts, or the claims block during a
  check.
- Never loosen a threshold, narrow the claim set, or exclude a claim kind to reach
  PASS.
- Never check against artifacts from a different plan without telling the user.
- A partial, errored, or unparseable check is a gap, never clean.
- The checker adjudicates; the user decides. Every MISMATCH and every gap goes to
  the user with evidence.

## 7. Limits

- Recall: prose claims without numbers, claims about figures, and derived
  statistics (means across cells, deltas between groups) are mostly UNVERIFIED by
  design. The stage catches transcription errors, not analytical errors.
- False VERIFIED is the dangerous direction. Context thresholds and the
  common-value guard bias toward UNVERIFIED. VERIFIED means "consistent with a
  located artifact value in a matching context," not "correct."
- A report table copied from an artifact is checked cell-wise when headers match
  ≥ 50%; reordered rows match by label where possible, else degrade to UNVERIFIED,
  never MISMATCH.
- v1 reads CSV/TSV/JSON/text artifacts and Markdown reports. Not figures, not h5ad
  internals, not rendered HTML.

## 8. Relation to other skills

- **grill**: plans name reports on their `Outputs:` line, which is what makes a
  claims check first-class under `verify <hash>`. A MISMATCH that implicates the
  artifact rather than the text routes back to grill for a re-run plan.
- **verify**: this stage runs inside `verify <hash>`; standalone use is the
  exception.
- **handoff**: mention open mismatches so the next session sees them.
- **harden**: a recurring mismatch pattern (same kind, same cause) is a mitigation
  candidate.
