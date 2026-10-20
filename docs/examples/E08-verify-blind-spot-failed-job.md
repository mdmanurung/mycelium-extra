# E08. The researcher's hand check found a failed job that verify had not raised

Control point: **honesty**

Anonymised from a real project. Source: a hand-written addendum beside a real `verify` report in project B, plus CHANGELOG defect V-30 (the later fix). Output blocks regenerated on the fixture with the current release.

## 1. Socratic: ask these first

- The report says no receipt for two planned scripts. Does "no receipt" mean "did not run"?
- Which jobs does the scheduler list for this period, and how many did the record capture?
- A missing linter returned a status. Is that the same as clean?

## 2. Situation

The addendum records three things done by hand:

1. Planned-script edit times versus job start times (each script predated its successful run by seconds).
2. A failed submission sat under the plan and the report did not mention it. Of 4 submitted jobs, 2 were receipted at all. The submit commands were shell loops with an unexpanded variable, so no per-script row matched; the state had been fetched from the scheduler but never consulted.
3. Without the linter on the login PATH the same command returned CONFORMS_WITH_GAPS: "a missing-linter status, not a clean result". With it, 97 findings in pre-existing Python blocked.

## 3. What the tool shows today (regenerated)

Plain submit, job FAILED:

```text
Ran as planned  no: 0 of 1 steps ran to completion; not completed: <batch script> (job 4242 FAILED)
- block: `<batch script>`: Slurm job 4242 ended FAILED.
Verify status: DOES_NOT_CONFORM
```

Shell loop around the submit:

```text
Ran as planned  not attributable: 1 of 1 steps were named in a compound shell command, so what ran and whether it succeeded cannot be t...
- gap: `<batch script>` was named in a compound command at <time>, but its execution and exit status cannot be attributed to this step.
Verify status: CONFORMS_WITH_GAPS
```

CHANGELOG: 59 of 86 real `sbatch` receipts named no planned script, so failed jobs were invisible; `verify` now also reads the job's work directory and submit line from the scheduler.

## 4. Track-changes shape

Observed: 2 failed and 2 completed jobs by scheduler record. Potential: results quoted from the plan include a failed attempt's neighbours. Gap: 2 of 4 jobs unreceipted. Unknown: what the loop ran.

## 5. Librarian block

None.

## 6. What the human decided, and what would have happened

The researcher kept the hand check in the provenance folder beside the report and treated both status words as unfinished. Without the addendum the report would have been read as "no failures".

Basis: project B: 3 provenance bundles; 138 of 144 approvals have no bundle.
