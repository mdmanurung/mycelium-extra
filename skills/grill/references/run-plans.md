# Run plans: freeze the code before a reportable run

A normal grill plan approves intent: Mycelium's analyze skill writes the code after approval, so the commands are not known yet. Use a **run plan** when results will be reported, or a run is long or goes to HPC, and the user wants every command known and frozen when they approve it. It is optional; a single plan still works, just without a freeze.

## Two plans, one PLAN.md

1. **Plan A (intent).** A normal grill plan. After approval, `/mycelium:analyze` writes the scripts, runs `scilintr` after each edit, and test-runs them. Runs under plan A record learnings only; findings wait for plan B's run. If the user grants `allow explore`, prefix these runs so they carry the not-reportable label.
2. **Plan B (run).** Grill again once the code is written and linted. In an analysis folder made by new-analysis, revise its `PLAN.md` in place and log the revision in `TRACKER.md`; never start a second plan file. Plan B differs from a normal plan in three ways:
   - **`Inputs:` freezes the code.** List the Snakefile, `run.sh`, every step script the run uses, and the data inputs. The gate pins them when it shows the approval hash, and blocks any launch after one of them changes, even while plan A is still approved: the newest covering plan decides. An edit after approval (a lint fix, a bug fix) therefore needs plan B presented and approved again.
   - **Evidence shows what will run.** Include the job list from a dry run, `bash analysis/<name>/run.sh -n`, run under plan A's approval (plan A's table names the folder's `run.sh`, as new-analysis asks). A dry run is still a run: Snakemake executes the Snakefile's top-level Python and input functions while building the job list, so the gate treats it like any other run. For each tool the steps call, record where it resolves and its version in the declared environment (`command -v <tool>`, `<tool> --version`, under `conda run -n <env>` when the repository uses one). A missing tool blocks the plan.
   - **`scilintr` is clean first.** Run it on the analysis folder before presenting plan B, as analyze requires, so that no lint fix is needed after approval.

`verify <plan-B hash>` then checks the run against plan B and freezes it into `provenance/`.

## Which changes need a new plan

A change that alters what the analysis claims needs a new plan, sourced and approved: the model, the contrast, which samples are included, a filter or threshold, a covariate, the unit of analysis, or swapping one tool for another.

A change that only alters how the same commands run does not, as long as the frozen files stay unchanged: cores, memory, time, or queue; a retry of the same command; installing a missing tool at the version the plan recorded. If such a change edits a frozen file (for example a resource line in the Snakefile), the gate blocks the launch, and plan B is re-approved with the change named in `TRACKER.md`.
