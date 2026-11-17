# Decision log

One TSV per analysis records each impactful choice the run makes, so `verify` can match it to the plan. Idea from pstack's `show-me-your-work`; the columns and the rules differ because the plan here already fixes the choices.

Path: `<analysis>/logs/decisions.tsv`, committed with the analysis. A step folder `outputs/<stem>/` is overwritten on a rerun and would lose it.

## Columns

`ts`, `phase`, `decision`, `why`, `evidence`, `result`, `plan_row`, `source`.

- `phase`: the step or stage (`03_fit`). The value `start` is a marker row.
- `decision`: what was chosen, one line.
- `why`: the reason in plain words.
- `evidence`: a pointer, never prose: a path, `file:line` or a commit.
- `result`: what happened (`ran`, `reverted`, `inconclusive`, `open`) or the value it gave.
- `plan_row`: the approved plan's step number. It is required. A plan table with an ID column (`#`, `id`, `no`) is matched by that ID; one without (grill's Step, Choice, Source, Validation) by the row's 1-based position in the step table (the table whose header has Step or Choice), so a Gate or Value table elsewhere in the plan does not shift the numbers.
- `source`: that row's Source cell (`user`, `inherited: <path>`, `repo: <path>`).

## Rules

- Log every impactful choice (see the grill skill) and every fork the run took, at the time it happens. Do not log every action.
- The log is one file kept across runs. `verify` judges only rows whose `ts` is at or after the plan's approval; earlier rows are counted and left alone, and a `ts` that is not ISO 8601 UTC is a gap.
- Append only. A wrong row gets a later row that supersedes it. Never edit or delete a row.
- Write a `start` row when a run begins, so a reader sees where one run ends and the next starts.
- A choice with no approved plan row is an unplanned impactful choice. Do not log it: stop and ask the researcher. `verify` blocks on a row whose `plan_row` is empty or unknown.
- A row linked to a `default:` row is flagged as info. An impactful choice is never a default.
- At the end of the run, read the log against what actually ran (the receipts, the outputs). Add superseding rows for what it misses. Fix the log, not the story.

## Append a row

```bash
<skill-dir>/../../hooks/mxpy - <analysis>/logs/decisions.tsv PHASE DECISION WHY EVIDENCE RESULT PLAN_ROW SOURCE < <skill-dir>/../verify/scripts/decision_log.py
```

It writes the header once, stamps the time (UTC), flattens tabs and newlines, and refuses a decision row with no plan row. A negative number stays as written.

## What it does not show

The log shows what the run says it chose, not that the code did it. `verify` checks the rows against the plan, not against the code.
