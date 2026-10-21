# Verify and record provenance

`verify` checks what ran against the approved plan. Once you confirm, it saves the plan, receipts and report with the analysis. It never re-runs anything.

**Method habit 5** ([the method](../start/method.md)). Without the plugin: log each command, code version, input checksums and exit status, then compare them with the plan and list what you could not check.

![Verification reads the approved plan, receipts and output evidence; reports outcomes and missing evidence; then explicit confirmation precedes publication of saved provenance.](../figures/verify-save.svg)

Verification reads records and never re-runs the analysis. The save confirmation is an instruction to the agent, not a second gate or a scientific approval.

## What you control here

- **Your typed word:** which plan to check (its hash), and a yes before anything is written to `provenance/`. That yes is the agent's instruction, not a gate rule: nothing enforces it.
- **Shown to you:** five summary rows, a status, and every block and gap. Gaps are never shown as passes.
- **To say no:** don't confirm the write. `report` and the other subcommands are read-only.

## Steps

1. Don't have the hash? List approved plans: `/mycelium-extra:verify list`.
2. Check one plan:

   ```text
   /mycelium-extra:verify report 84bb5fce
   ```

   Add `--resolve-citations` to resolve DOI, PMID and arXiv identifiers online; offline they stay a gap.
3. Read the rows `Ran as planned`, `Numbers match`, `Code checks`, `Not checked`, `Next`, then the `Verify status:` line.
4. Fix blocks outside `verify`: re-run under the plan, re-check a changed input and approve a new plan, or correct a claim. You choose.
5. Save the check:

   ```text
   /mycelium-extra:verify write 84bb5fce
   ```

   It writes `<analysis>/provenance/` (`plan-`, `receipts-`, `outputs-`, `verify-`, `lint-` files and `PROVENANCE.md`). Commit it with the analysis.

### Other read-only questions

| Ask | Subcommand |
|---|---|
| What changed between two plans | `verify diff <old> <new>` |
| What was tried before this result | `verify multiplicity <hash>` |
| An overview of plans, runs and status | `verify status` |
| What is out of date | `verify stale` |
| A draft AI-use methods paragraph | `verify disclose <hash>` |
| One line per plan row, with its evidence | `verify report <hash> --trace` |

To make your numbers checkable, declare them in a `<!-- claims -->` block that names each output cell. The format is in `skills/verify/SKILL.md`.

## Worked example

This is real harness output on the fixture project (synthetic names), for plan `84bb5fce` after its three steps ran. First, the report's opening rows, from [a worked example](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/example.md#7-verify):

```markdown
# Verify plan 84bb5fce: CONFORMS

Ran as planned  yes: 3 of 3 steps ran, 3 run(s), all completed  
Numbers match   yes: 8 of 8 claimed cells match  
Code checks     lint clean; 2 threshold finding(s) are Choices you approved  
Not checked     3 Validation cell(s) are prose; whether the code implements the choices (that is review)  
Next            confirm saving provenance to analysis/vaccine-response/provenance/  
```

`verify multiplicity 84bb5fce` on the same run, with no earlier plans:

```markdown
0 earlier plan revision(s), 0 explore run(s) before the approval, 0 run(s) under earlier plans, 3 run(s) under this plan.

| When | What | Detail | Exit |
|---|---|---|---|
| 2026-10-19 19:58 | plan 84bb5fce | approved (selected); first plan |  |
| 2026-10-19 19:58 | run | `python3 analysis/vaccine-response/scripts/01_select_samples.py` | 0 |
| 2026-10-19 19:58 | run | `python3 analysis/vaccine-response/scripts/02_paired_test.py` | 0 |
| 2026-10-19 19:58 | run | `Rscript analysis/vaccine-response/scripts/03_summary.R` | 0 |
```

A `disclose` line shows how it leaves blanks for you instead of filling them in:

```text
[BLANK: no conda environment was recorded for these runs, so tool versions other than the plugin's are not in the records]
```

## What this does not guarantee

`CONFORMS` means the checked record agrees with the plan. A run proves a script ran, not that it implements the plan's choices (that is code review). A matching claim matches its cell, not the truth. A resolved citation shows the identifier exists, not that the paper supports your sentence. See [what this does not guarantee](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/concepts/not-guaranteed.md).

## Reference

[verify](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/verify.md) · [state files](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/state-files.md) · [gaps and passes](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/concepts/gaps-and-passes.md) · next: [amend, freeze, re-scope](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/guides/amend-freeze-rescope.md)
