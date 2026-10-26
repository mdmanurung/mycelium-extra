# Exercise: one success, one stop

[Back to the usage tiers](usage.md)

A practice run on the fixture project (`tests/fixtures/mycelium-project`): read what you are approving, see a run succeed, find one output's evidence, then break an input on purpose and watch the run stop. It teaches reading evidence, not scientific judgement. Finishing it is not an approval credential or a score.

**Time:** a design target of 15 to 20 minutes after installation. It has not been measured with other people. **Needs:** the plugin installed ([Installation](installation.md)), a clone of this repository and Python 3.9 or later. Nothing here runs R or a linter, so it works without `scilintr`.

Do all of it in a scratch copy, so the fixture stays as it is:

```bash
cp -r tests/fixtures/mycelium-project /tmp/mx-exercise && cd /tmp/mx-exercise
```

## Quick synthetic review

For a text-only exercise, ask `/mycelium-extra:verify exercise`. It shows an invented plan, receipt, output cell and report excerpt based on C1's V-23 claim-mismatch case. Find the discrepancy, then ask `/mycelium-extra:verify exercise reveal` in the same session. No analysis runs, project reads, files or personal scores are saved. The exercise needs no gate. The longer scratch-project rehearsal below is separate.

## 1. Read the plan before you approve it

Open the worked example's [plan and card](example.md#2-the-brief). Find, on the card or in the plan table:

- what question is asked, and the reference level (placebo);
- which steps can run, and that a path in the Step column grants *any arguments*;
- which Validation cells are prose and which are bound to a check. Unless your `.mycelium-extra/gate.json` sets `"card_coverage": false`, the `Coverage` row counts them for you; otherwise `card <hash> full` lists the bindings.

A prose Validation cell is a promise nothing runs. Write down which of the three steps have one.

## 2. Read the table before the plot

Run the example's steps as the [worked example](example.md) shows, then open `analysis/vaccine-response/outputs/de_results.tsv` before any summary. Check it against the claim: 60 genes, one row each, the sign you expect for the vaccine arm. A plot that looks right can hide a table that is not.

## 3. Find one output's evidence

Run `verify report <hash>` (see [Verification](verification.md#what-the-report-shows)). For `de_results.tsv`, find:

1. the run that wrote it (the attempt and its time);
2. its producer strength (`supported`, `candidate` or `unresolved`);
3. a check bound to the step, if any, and its outcome (`passed`, `failed`, `not run`).

If the plan binds no check to that step, the report says so under `Not checked`. That line is the part to remember: the outcome describes what ran, not everything that could go wrong.

## 4. Remove one sample label

Your approved plan should declare the alignment check from [recipe 1](validation-recipes.md#1-sample-and-key-join). Run it on the intact data, then blank one sample label and run it again:

```bash
sh hooks/py.sh - --contract checks/sample_alignment_contract.json --root . --result-json out.json \
  < skills/data-contract-check/scripts/data_contract_check.py
```

The intact data gives `PASS  checks[0] sample_alignment (25 rows)` and exit code 0. With the last `sample_id` in `sample_metadata.tsv` blanked, it gives exit code 2:

```text
BLOCK checks[0] sample_alignment (25 rows)
    BLOCK the table has empty or missing keys
      observed: 1 of 25
    BLOCK keys in the table but not in the independent list
      - '' (empty)
    BLOCK keys in the independent list but not in the table
      - 'D12_day28'
```

Check three things: the analysis entry point must stop here and not fit; no label was invented to make it continue; and an `outputs/` file from the earlier intact run, if still on disk, is old, not the result of this run (compare its time with the failed check's).

## 5. Choose how to recover

You are told: "the backend is not installed; use the other one" or "flip the contrast so positive means higher in placebo". Decide which is which:

| Proposal | What it is | What to do |
|---|---|---|
| Rerun the same command after a transient error | An equivalent retry | Retry; both attempts stay in the report |
| Change an argument the plan does not list as `operational` | A different computation | Show the change, approve an updated plan |
| Edit the script | A re-pin: the gate lets it through and verify shows a gap until you [`freeze`](approval-gate.md#freeze) | Review the diff at freeze, then rerun |
| Flip the contrast | An analytical change; the contrast check (recipe 2) fails, as `V-DC08` shows | New plan, new approval |

See [When something fails](verification.md#when-something-fails) for who enforces each row.

## 6. Say what the evidence shows

In two sentences: what the passing check establishes, and one thing it does not. For example, "the sample ids match between the metadata and the counts. It does not show that the analysis joins them by id; that needs the shuffle check." Compare with the Limit line of the recipe you used.

## Facilitator notes

- Run steps 1 to 3 as a group on the worked example and give each person step 4 alone; step 5 is a discussion, with the table above as the answer key.
- The expected output in step 4 comes from the fixture's `sample_metadata.tsv` (last row `D12_day28`) on the host and versions recorded in the [rehearsal](#rehearsal). A different data version changes the quoted key.
- Optional extensions, not part of the 15 to 20 minutes: [correct a wrong expectation](validation-recipes.md#correcting-a-wrong-expectation) with `verify refs`, and the prefiltered table of [recipe 3](validation-recipes.md#3-complete-result-table).
- Do not read a person's finishing as competence. The exercise shows one fixture, on one host, and no detection rate.

## Rehearsal

Step 4 was run once on 2026-10-18 in a scratch copy of the fixture at version 0.11.0 (Python 3.12.15, Linux 4.18, no R or linter): the intact data passed with exit code 0; one blanked label gave exit code 2 with the three BLOCK lines above. Steps 1 to 3 were not rehearsed live in this version, because [the worked example](example.md) was written at 0.10.2 and could not be regenerated here (it needs `scilintr` and an `Rscript` whose R has it).
