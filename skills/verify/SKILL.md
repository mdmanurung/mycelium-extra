---
name: verify
description: After an approved mycelium-extra grill plan has run, check what actually ran against the plan, then, once the user confirms, write the frozen plan, its run receipts, and the check into the analysis folder's `provenance/`. Reports per planned script whether it ran, failed, has no receipt, was edited or deleted since it ran, or was only passed to other code (a lint or parse call); flags explore runs, runs and scripts outside the plan table, changed pinned inputs, outputs written before the approval or not tied to a run of the plan (from the plan's `Outputs:` line, the gate's receipts, Slurm, and Snakemake's records), and scratchpad computation Mycelium's lineage saw but the gate did not. Then names the `/mycelium:review` command that checks the code against the frozen plan. Use when the user invokes mycelium-extra verify, asks whether an analysis ran according to plan, or wants provenance recorded after an approved run. Its `stale` sweep lists every verified plan whose scripts, pinned inputs, or outputs changed since its provenance was written; use it when the user asks what is stale, out of date, or needs re-running. Its `status` table lists every approved or verified plan with its analysis folder, runs, verify status, staleness, recorded lint, and Mycelium manifest status; use it when the user asks for status, an overview, or what has been planned, run, or verified. Claude Code only, since it reads the approval gate's receipts; runs under Codex are not receipted. Not for planning (use grill) and not for judging code quality (use Mycelium's review).
---

# Mycelium Extra: Verify

Check one approved plan against the gate's record of what ran, and record the result as provenance once the user agrees. The script judges only what the records show; it never re-runs anything, and nothing here edits receipts or approvals.

## 1. Find the plan

- Requires the approval gate (`.mycelium-extra/gate.json`). Without it, say so and stop.
- Use the hash the user gives. Otherwise list the approved plans, newest first, and ask which one:

  ```bash
  python3 - --plugin-root <skill-dir>/../.. list < <skill-dir>/scripts/verify.py
  ```

Always run the script from stdin, from inside the repository. Running it by path opens Mycelium's post-action cycle. The script finds the gate's state folder itself, so never put that folder's name on the command line.

## 2. Check, read-only

```bash
python3 - --plugin-root <skill-dir>/../.. report <hash> [--analysis-dir <folder>] < <skill-dir>/scripts/verify.py
```

The analysis folder is guessed from the plan's scripts; pass `--analysis-dir` when the guess is wrong. `--json` gives the raw result.

It also runs scilintr on the analysis folder's code (outputs, logs, and provenance skipped; the planned scripts when there is no folder): `scilintr` for Python, `Rscript -e 'scilintr::main()'` for R, as Mycelium's analyze skill requires. A Jupyter notebook's code cells are extracted (magic and shell lines commented out) and linted with its kernel's language; findings are cited as `<notebook>.ipynb[code cell N]:<line>`, and a notebook whose code does not parse is a gap. The `{r}` and `{python}` chunks of `.qmd` and `.Rmd` files are linted the same way, with prose and other lines blanked so a finding cites the document's own line (`<doc>.qmd:<line>`); display blocks, other engines, and inline `` `r x` `` code are not linted, and `eval=FALSE` chunks are. The `## Lint` section lists remaining findings and every `ANALYSIS_OK` waiver. If a linter is missing, say how to install it (`pip install scilintr`, `install.packages("scilintr")`); never treat an unchecked language as clean.

It also checks the reason on each `default:` in the frozen plan's Source column, with plan-review's `scripts/default_reasons.py` (loaded from the plugin root). A row with no reason, a reason under three words, or only an empty phrase such as `standard` is an advisory `info` finding that names the row; it does not change the status. If that script is missing or fails, the check is a gap.

The report ends with `Verify status:` and one of these values:
- `CONFORMS`
- `CONFORMS_WITH_GAPS`: something the records cannot show, such as a run with no receipt, an unrecorded exit status, an output not tied to a run, or code scilintr could not check.
  The gate takes a run's exit status from Claude Code's hook event: `PostToolUse` fires only after a command succeeds, so its receipt records exit 0 (`"exit_source": "event"`; the row reads `ran (exit 0 from hook event)`), and `PostToolUseFailure` gives the code from the `Exit code N` line, or `failed` or `interrupted` when there is none. A receipt with exit status `unknown` (a run started in the background, a payload without an event name) or null (from an older gate) is a gap, never a success, so a plan whose only evidence is such a run gets `CONFORMS_WITH_GAPS`. An `sbatch` receipt's exit status is the submit's; the job's state comes from `sacct`.
- `DOES_NOT_CONFORM`: at least one of:
  - a failed run (a nonzero exit, a failure with no exit code, or an interrupted run) or Slurm job
  - a planned script edited after its run
  - a pinned input that changed since the approval
  - a scilintr finding that is neither fixed nor waived
  - a file named exactly on the `Outputs:` line that was written before the approval (older files inside a named folder or glob are earlier runs' outputs, so they are only counted)
  - an incomplete Snakemake job

A plan re-approved under the same hash keeps its earlier runs; the report says so.

## 3. Report to the user

- Give the status, the planned-scripts table, and each `block` and `gap` finding with what it means for the results. Keep the `info` lines short.
- Never paste the plan, or its `Plan status:` line, into the reply. The gate would offer the reply as a new plan to approve.
- For each `block`, name the fix and leave the choice to the user. Typical fixes:
  - re-run the step under the plan
  - re-check a changed input and approve a new plan
  - drop an output written before the approval
- Do not fix anything in this skill.
- A gap is not a failure. Say what it hides. For example, an output not tied to a run is often a run Claude Code moved to the background.

## 4. Write provenance, after the user confirms

Ask once whether to record this check, naming the analysis folder and the status. Only after an explicit yes:

```bash
python3 - --plugin-root <skill-dir>/../.. write <hash> --analysis-dir <folder> < <skill-dir>/scripts/verify.py
```

It writes `<folder>/provenance/`:
- `plan-<hash>.md`: the frozen plan as approved.
- `receipts-<hash>.jsonl`: the receipts of this plan's runs.
- `outputs-<hash>.tsv`: each output's path, write time, size, full sha256 (or size and mtime past the hash budget), and likely run.
- `verify-<hash>.md`: this report.
- `lint-<hash>.txt`: the scilintr output and every `ANALYSIS_OK` waiver.
- `env-<hash>.txt`, only when a run used a conda env (`conda run -n|-p`, `conda activate` in its job script, an interpreter under `<env>/bin/`, or the session's `CONDA_PREFIX`) and no `conda-lock.yml` was found: the env's packages in `conda list --explicit --md5` form, read from its `conda-meta` so conda need not be on PATH. An env changed after its last run (`conda-meta/history` is newer) or not found is a gap.
- `PROVENANCE.md`: one row per verified plan.

Writing again for the same plan replaces its files and its row. A non-conforming check can be written too, since its status is recorded with it. The files belong with the analysis, so commit them with it. The script warns if git ignores the folder.

## 5. Hand off

- Mycelium's Stop hook will ask for a `.living/` update. Record the verify status, and the plan's "Decisions to record" from `plan-<hash>.md`, through Mycelium's normal logging. This skill does not write `.living/`.
- Give the review command, which checks the code against the frozen plan:

  ```
  /mycelium:review <folder> — check the code against the approved plan in <folder>/provenance/plan-<hash>.md
  ```

- End with one line: the status and the next action.

## Stale sweep

When the user asks what is stale or out of date, sweep every verified plan, read-only:

```bash
python3 - --plugin-root <skill-dir>/../.. stale [--json] < <skill-dir>/scripts/verify.py
```

It reads the committed `provenance/receipts-<hash>.jsonl` and `outputs-<hash>.tsv` (found through git, so ignored folders are skipped), and needs no gate. For each stale plan it lists scripts edited or deleted since they ran, pinned inputs that changed, and outputs rewritten or deleted since verify recorded them, plus the session IDs of its runs. Outputs are compared by size and time only, never hashed.

- In a Mycelium project, run each stale plan's `findings:` command, which searches `.living/findings/` for its session IDs and `plan <hash>` (the gate suggests `<session-id>; plan <hash>` as a ledger's Run/Session cell), to name the findings that rest on a stale plan. A finding's ledger may cite a run ID instead; if nothing matches, say the link is unknown, not that no finding is at risk.
- Suggest, per stale plan: re-verify it (`verify <hash>`), or re-plan the re-run with grill. Write nothing.

When the user asks for status or an overview, show one table, read-only:

```bash
python3 - --plugin-root <skill-dir>/../.. status [--json] < <skill-dir>/scripts/verify.py
```

One row per plan the gate approved (local, this clone only) or verify recorded (committed `provenance/`): the analysis folder (the provenance folder, else guessed from the plan table), runs, the verify status from `PROVENANCE.md` or `not verified`, `stale` changes, the lint verify recorded (`N finding(s)`, `clean`, `gap: <language> not checked`, or `not run`; scilintr is not re-run), and the folder's entry in any `ANALYSIS_MANIFEST.md`: `listed: <first word of its status>`, `listed`, or `not listed`. A `not listed` analysis skipped Mycelium's manifest step. Show the table as printed, then suggest at most one next step, such as verifying the newest unverified plan. Write nothing.

`explore [--all]` lists explore runs of gated code for grill's "promote explore runs" (see the grill skill); it only reads.


Runs under Codex are not receipted: the Codex manifest loads no hooks (`"hooks": {}`), so Codex writes no approvals and no receipts, and nothing records which host a run came from. A plan run in Codex shows `no receipt` for every script.

The report lists what it cannot see:
- A receipt's time is when the hook fired, so outputs of a run moved to the background postdate it.
- Mycelium's lineage covers finished sessions only.
- Code run through MCP notebook tools bypasses both the gate and the lineage.
- A run proves a script ran, not that it implements the plan's choices; the review step checks that.

Output attribution is a best match by time, so it only ever produces gaps, never blocks.

## Plan diff

Before the user re-approves a revised plan (for example a run plan presented again after a fix, see grill's `references/run-plans.md`), show what changed since the plan it replaces, read-only:

```bash
python3 - --plugin-root <skill-dir>/../.. diff <old-hash> <new-hash> < <skill-dir>/scripts/verify.py
```

It reads each plan from the approvals, or, for one shown but not yet approved, from the gate's pending plans, and compares their tables row by row (keyed by the step number) and their `Inputs:` lines. A changed Choice cell is flagged as a possible scientific change; whether it is one is the user's call, so name it and let them decide. Write nothing; the revision itself belongs in the analysis folder's `TRACKER.md`.
