# Run plans: freeze the code before a reportable run

A normal grill plan approves intent: Mycelium's analyze skill writes the code after approval, so the commands are not known yet. Use a **run plan** when results will be reported, or a run is long or goes to HPC, and the user wants every command known and frozen when they approve it. It is optional; a single plan still works, just without a freeze.

## Two plans, one PLAN.md

1. **Plan A (intent).** A normal grill plan. After approval, `/mycelium:analyze` writes the scripts, runs `scilintr` after each edit, and test-runs them. The gate pins each script at its first run, so an edit after that run (a lint or bug fix) blocks the next run until the user approves the plan again; for a debugging loop the user can say `allow explore`. Runs under plan A record learnings only; findings wait for plan B's run. If the user grants `allow explore`, prefix these runs so they carry the not-reportable label.
2. **Plan B (run).** Grill again once the code is written and linted. In an analysis folder made by new-analysis, revise its `PLAN.md` in place and log the revision in `TRACKER.md`; never start a second plan file. Plan B differs from a normal plan in three ways:
   - **`Inputs:` freezes the code.** List the Snakefile, `run.sh`, every step script the run uses, and the data inputs. The gate pins them when it shows the approval hash. An edit to a listed script is re-pinned with a notice and the launch goes ahead; the user reviews the edits once with `freeze <hash>` and approves them before the reportable rerun. A changed data input still blocks the launch until the plan is shown and approved again, even while plan A is still approved: the newest covering plan decides.
   - **Evidence shows what will run.** Include the job list from a dry run, `bash analysis/<name>/run.sh -n`, run under plan A's approval (plan A's table names the folder's `run.sh`, as new-analysis asks). A dry run is still a run: Snakemake executes the Snakefile's top-level Python and input functions while building the job list, so the gate treats it like any other run. For each tool the steps call, record where it resolves and its version in the declared environment (`command -v <tool>`, `<tool> --version`, under `conda run -n <env>` when the repository uses one). A missing tool blocks the plan.
   - **`scilintr` is clean first.** Run it on the analysis folder before presenting plan B, as analyze requires, so that no lint fix is needed after approval.

`verify <plan-B hash>` then checks the run against plan B and freezes it into `provenance/`.

When plan B is presented again after an edit, `verify diff <old> <new>` shows a complete difference summary against the plan it replaces: the objective, every changed, added, removed and reordered row, dropped columns, `Inputs:` and `Outputs:`, validation and exact-execution blocks, and the runs allowed. Show it; do not summarize it from memory. If the scientific question is unchanged (the Objective and every Choice cell are the same), the user needs that summary and a fresh approval, not another full interview: revisit a question only where the summary shows it changed.

## Optional blocks for a reportable run

Two comment blocks in the plan text bind the run more tightly than a path in the table does. Both are optional; add one only where a reportable result depends on it, not for every sentence of the plan. The gate checks them before it will offer `approve plan <hash>`: an invalid block is shown as errors and the plan cannot be approved until it is fixed.

**Exact execution** freezes the command of a step. Without it a path in the Step column is a broad grant (any arguments), so a changed `--model` or threshold runs under the same approval. Declare the commands whose arguments are part of the science:

```text
<!-- exact-execution {"version": 1, "steps": [
  {"row": "2", "argv": ["python", "analysis/x/fit.py", "--model", "mixed", "--threads", "4"],
   "cwd": ".", "env": {}, "operational": ["--threads"]}]} -->
```

`row` is the table's ID (or position); `argv` starts at the program (no `conda run`, `srun` or `VAR=` words); `operational` lists the flags that may differ in value or be added or removed (cores, memory, queue). Spell out every analytical argument in `argv`; do not put one in `operational`. Use literal values: a `$VAR` or `$(...)` cannot be frozen. The script must still be named in the Step cell.

**Validation bindings** tie an acceptance check to a result:

```text
<!-- validation-bindings {"version": 1, "checks": [
  {"id": "V1", "plan_row": "3", "required": true, "defined_by": "researcher-approved",
   "test_paths": ["analysis/x/tests/expected_rows.tsv"],
   "invocation": ["python", "analysis/x/tests/check_rows.py"],
   "evidence_path": "analysis/x/outputs/check_rows.json"}]} -->
```

`test_paths` are the test, its fixtures and its expected values; the gate pins their bytes, so editing one after approval blocks the next run until the user approves the plan again. `invocation` is the command that runs the check from the repository root, and `evidence_path` is where it writes its result. Put the check under a gated path (such as `analysis/x/tests/`) and name its script in a Step cell, or the gate does not see the run and cannot record it; a test under `tests/` is not gated unless the user adds it to `gated_paths`. `defined_by` says who wrote the expectation: `researcher-approved` or `independent` only when that is true, otherwise `agent-proposed`; the gate records it and cannot verify it.

**Exploratory agent tests versus approved acceptance expectations.** While developing, write and run any test you like; it is exploratory, not an approved expectation, and nothing about it is frozen. Bind a check only when the user approves a specific expectation (a row count from fixture truth, an expected contrast sign) as a condition on the result. Never loosen a bound expectation to make a result pass: the change blocks the run and goes back to the user.

## Can the frozen entry point rerun without you?

Name the entry point (`run.sh` or the Snakefile) in a Step cell and under `Inputs:`, and say in the plan whether the researcher can rerun it alone: its environment, its inputs, and how long it takes. `verify` then reports three separate facts and never launches anything:

- **entry point declared**: the plan names it. This says nothing about whether it works.
- **rerun attempted**: a matched run of it began after `verify write` saved the outputs table. The run before that save is the original run.
- **rerun reproduced specified artifacts**: that rerun exited 0, its attempt saw each saved output rewritten, and the content hashes equal the ones saved before it. Anything less is "reproduction not established", with the reason.

Do not start a costly rerun to improve this line. Offer the command, say what it costs, and let the researcher decide. A rerun that was never attempted is stated as such, not as "not reproducible".

## Which changes need a new plan

A change that alters what the analysis claims needs a new plan, sourced and approved: the model, the contrast, which samples are included, a filter or threshold, a covariate, the unit of analysis, or swapping one tool for another.

A change that only alters how the same commands run does not, as long as the frozen files stay unchanged: cores, memory, time, or queue; a retry of the same command; installing a missing tool at the version the plan recorded. If such a change edits a pinned script (for example a resource line in the Snakefile), the gate re-pins it with a notice and the launch goes ahead; if it edits an input, a validation file or an exact-execution file, the gate blocks the launch, and plan B is re-approved with the change named in `TRACKER.md`.

With an exact-execution block the three cases are different actions. An **operational retry** (a listed flag with another value, a log redirect) is allowed as is and is recorded. A **re-freeze** of a pinned script is `freeze <hash>` and one approve; a bound test file that changed needs the plan shown and approved again with the change named. A **changed scientific intent** (another model, filter, contrast, threshold, seed or input, or a loosened expectation) goes back to the user, who approves a revised plan; the gate denies the run and says so, so do not work around it.
