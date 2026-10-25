# @@NAME@@: tracker

Status of each plan item, and a dated log. IDs match [PLAN.md](PLAN.md). Results go in
[@@DOC@@](../@@DOC@@) (Key Findings and Outputs), not here.

Statuses: `todo` · `in progress` · `done` · `blocked` · `dropped (reason)`.
To update an item, change its status here and add one line to the log.

| ID | Item | Status | Depends on | Verify |
|---|---|---|---|---|
@@TRACKER_ROWS@@

## Log

- @@DATE@@: folder created with mycelium-extra new-analysis.

<!-- Example, only when a run needed more than a rerun (not a log of every command), linked to the attempts in verify's
Recovery section: - YYYY-MM-DD: item 2 failed (exit 1) as `--model original`, then ran as `--model alternative` (plan <hash>,
verify Recovery). The model changed, so the researcher approves or revises the plan before the result is reported. -->
