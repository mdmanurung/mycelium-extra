---
name: verify
description: "After an approved mycelium-extra grill plan has run, check what ran against the plan and, once the user confirms, write the frozen plan, its run receipts, and the check into the analysis folder's `provenance/`. Flags failed, missing, edited, or unplanned runs, explore runs, changed pinned inputs, outputs not tied to a run of the plan, and `<!-- claims -->` numbers that disagree with their output cell; records the runs' conda and pip packages. Use when the user invokes mycelium-extra verify, asks whether an analysis ran according to plan, or wants provenance recorded. Subcommands: `stale` (what is out of date or needs re-running), `status` (an overview of what was planned, run, or verified), `multiplicity` (what was tried before the plan was settled), `explore` (this session's explore runs). Not for planning (use grill) or judging code quality (use Mycelium's review)."
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

It also runs scilintr on the analysis folder's code (outputs, logs, and provenance skipped; the planned scripts when there is no folder): `scilintr` for Python, and for R `Rscript -e` calling `scilintr::lint_project()` on one folder holding a copy of the R code, so its cross-file rules run too, as Mycelium's analyze skill requires. A Jupyter notebook's code cells are extracted (magic and shell lines commented out) and linted with its kernel's language; findings are cited as `<notebook>.ipynb[code cell N]:<line>`, and a notebook whose code does not parse is a gap. The `{r}` and `{python}` chunks of `.qmd` and `.Rmd` files are linted the same way, with prose and other lines blanked so a finding cites the document's own line (`<doc>.qmd:<line>`); display blocks, other engines (an `engine=` option picks the language, so `{r engine="bash"}` is skipped), and inline `` `r x` `` code are not linted, and `eval=FALSE` chunks and documents set to `eval: false` are. A file pulled in with `child=` or `knitr::read_chunk()` is found relative to the document and linted under its own path; one named by a path that is not a quoted string, or not found, is a gap. The `## Lint` section lists remaining findings, every `ANALYSIS_OK` waiver, and each finding a waiver suppressed with its reason (a second run with waivers off); an R waiver with no reason that suppresses a finding blocks. The linters' paths come from `.mycelium-extra/tools.json` when init recorded them, else `PATH`. If a linter is missing, say how to install it (`pip install scilintr`, `install.packages("scilintr")`) or how to record its path (`python3 - --tools --scilintr PATH --rscript PATH < <init skill-dir>/scripts/gate_init.py`); never treat an unchecked language as clean.

It also checks the reason on each `default:` in the frozen plan's Source column, with plan-review's `scripts/default_reasons.py` (loaded from the plugin root). A row with no reason, a reason under three words, or only an empty phrase such as `standard` is an advisory `info` finding that names the row; it does not change the status. If that script is missing or fails, the check is a gap.

It also checks claims: each `<!-- claims -->` block in the analysis doc (`<NAME>.md`, Mycelium's analysis doc), in a Markdown file on the `Outputs:` line, or in a document passed with `--claims <path>` (repeatable). Each block line names a value and the output cell it came from, `value | file column [row]`, with the file relative to the analysis folder or the repository. `row` is the first-column label; a table with more than one row needs it, so a common value such as `0.05` never verifies against some row of a column. `rows` as the column is the table's data-row count, and a JSON output takes a dotted path (`qc.n`, `qc.kept.1`). A value may start with `<`, `>`, `<=` or `>=`, and end with `%` (also tried against a fraction, reported as via transform). A value agrees when the cell, rounded half-up, half-even, or truncated to the value's last digit, equals it. The `## Claims` section counts each document's verdicts. A claim the cell contradicts, or one read from an output an explore run wrote, blocks; a claim whose file, column or row cannot be found, a file over `--hash-mb`, or a block line that does not parse is a gap. Numbers in the block's section (heading to heading) that no claim covers are listed as `info`: the block, not the prose, is the checked record.

The report ends with `Verify status:` and one of these values:
- `CONFORMS`
- `CONFORMS_WITH_GAPS`: something the records cannot show, such as a required validation check not established or a recovery whose equivalence is not established, a run with no receipt, an unrecorded exit status, an output not tied to a run, or code scilintr could not check.
  The gate takes a run's exit status from Claude Code's hook event: `PostToolUse` fires only after a command succeeds, so its receipt records exit 0 (`"exit_source": "event"`; the row reads `ran (exit 0 from hook event)`), and `PostToolUseFailure` gives the code from the `Exit code N` line, or `failed` or `interrupted` when there is none. A receipt with exit status `unknown` (a run started in the background, a payload without an event name) or null (from an older gate) is a gap, never a success, so a plan whose only evidence is such a run gets `CONFORMS_WITH_GAPS`. An `sbatch` receipt's exit status is the submit's; the job's state and `ExitCode` come from `sacct` (a submission is not a completion): `COMPLETED` with a nonzero `ExitCode` blocks, and a pending, running, unknown or partly finished array job is a gap.
- `DOES_NOT_CONFORM`: at least one of:
  - a failed run (a nonzero exit, a failure with no exit code, or an interrupted run) or Slurm job
  - a planned script edited after its run. The finding adds whether an approval covers the current version: a plan pinned it, it ran under a plan approved after the file was last modified (by file time), it ran only under a plan approved before that, or it has not run under any plan. The status stays `DOES_NOT_CONFORM` in every case; name the plan to check instead when one covers it
  - a required validation check whose result says it failed
  - a pinned input that changed since the approval
  - a scilintr finding that is neither fixed nor waived, or an R waiver with no reason that suppresses one
  - a file named exactly on the `Outputs:` line that was written before the approval (older files inside a named folder or glob are earlier runs' outputs, so they are only counted)
  - an incomplete Snakemake job
  - a claims-block value that the output cell it names contradicts, or that an explore run's output holds

The report also has a `## Validation` section when the approved plan declares `<!-- validation-bindings -->`, and a `## Recovery` section when a step has more than one attempt. Read both as evidence about the plan's own checks and the run history, not as a judgement of the science:
- Each check gets one outcome. `passed` needs a matched run of the check's invocation that created or changed its evidence file, pinned test files still as approved, and a result that says passed (a data-contract result passes with exit 0 and no block; warnings are kept). `failed` on a required check blocks; `not run`, `changed` (a pinned expectation edited or missing after approval), `unattributable` (a result the gate did not see the attempt write, or one modified afterwards) and `unsupported` (not a result `verify` can read) on a required check are gaps worded "not established": the expectation is not counted as met, and the plan is never `CONFORMS`. An optional check is an info line. `defined_by` is shown as the plan declared it, "not verified".
- Recovery lists every attempt of a step in order with what changed. A failed attempt followed by an equivalent retry (same command, or only flags the plan's `exact-execution` step calls operational) is info. A success after a changed command, script, engine config file or folder is a gap, "equivalence not established", and the earlier failure stays in the history. Do not describe it as recovered; say what changed and leave the choice to the user. A run of an instance with `exact-execution` that matched no declared step is a gap, "outside the exact reportable contract".

A plan re-approved with the same text and the same pins keeps one approval instance and its earlier runs; the report says so. Re-approved with other pins, it is a new instance: `report` checks the newest one by default (`--instance <id>` picks an earlier one), runs under another instance are listed as history and do not establish the freeze, and no run under the checked instance is a gap.

Before the tables the report has a `## Scope` block: which approval instance was checked, how many runs had a matched, unmatched, ambiguous or legacy launch, and how many outputs have a supported producer. Runs credited to the plan with no checked launch (Post without a matching Pre), ambiguous launches and attempts that never reported back are gaps; receipts from before launch matching are one info line.

A compound shell command's overall exit status cannot establish that each named step executed. Such receipts keep the overall status separately: an overall failure blocks, while each step's unknown execution is a gap. Malformed receipt or Snakemake records are skipped and reported as gaps, so damaged history cannot establish conformity. Header-only tables and duplicate column labels leave claims unverified; claims or percentage transforms outside the supported numeric range also leave explicit gaps.

## 3. Report to the user

- Give the status, the planned-scripts table, and each `block` and `gap` finding with what it means for the results. Keep the `info` lines short.
- Never paste the plan, or its `Plan status:` line, into the reply. The gate would offer the reply as a new plan to approve.
- For each `block`, name the fix and leave the choice to the user. Typical fixes:
  - re-run the step under the plan
  - re-check a changed input and approve a new plan
  - drop an output written before the approval
- Do not fix anything in this skill.
- A gap is not a failure. Say what it hides. For example, an output not tied to a run is often a run Claude Code moved to the background. An output written by a run of another plan is reported once per producing run and folder, naming the run's script; the Outputs table (and `write`'s `outputs-<hash>.tsv`) lists every file.
- For a claim mismatch, show the line, the claimed and the observed value, and the cell. Do not edit the document, the output, or the claims block: the user decides which is wrong, and a wrong output means a re-run under a new plan (grill). A verified claim means the text matches its cell, not that the analysis is right.

When you write findings or a report in a gated repository, declare the numbers a reader would quote in a claims block, each naming its cell, so verify checks them:

```markdown
<!-- claims
8 | outputs/summary.tsv n_hits
0.016234 | outputs/de_results.tsv padj SIGLEC1
24 | outputs/samples_used.tsv rows
-->
```

Never add, edit, or drop a claims line to make a failing check pass.

## 4. Write provenance, after the user confirms

Ask once whether to record this check, naming the analysis folder and the status. Only after an explicit yes:

```bash
python3 - --plugin-root <skill-dir>/../.. write <hash> --analysis-dir <folder> < <skill-dir>/scripts/verify.py
```

It writes `<folder>/provenance/`:
- `plan-<hash>.md`: the frozen plan as approved.
- `receipts-<hash>.jsonl`: the receipts of this plan's runs.
- `outputs-<hash>.tsv`: each output's path, write time, size, full sha256 (or size and mtime past the hash budget), the run named when its producer is `supported`, and the evidence: `producer_attempt`, `evidence_method`, `strength`, `approval_instance`. A table without those four columns is a legacy bundle.
- `validation-<hash>.json`, only when the plan has a validation binding: the frozen binding, each check's outcome and reason, and the raw evidence's path and sha256.
- `verify-<hash>.md`: this report, with its claims counts.
- `lint-<hash>.txt`: the scilintr output, every `ANALYSIS_OK` waiver, and the findings each suppressed.
- `env-<hash>.txt`, only when a run used a conda env (`conda run -n|-p`, `conda activate` in its job script, an interpreter under `<env>/bin/`, or the session's `CONDA_PREFIX`) and no `conda-lock.yml` was found: the env's packages in `conda list --explicit --md5` form, read from its `conda-meta` so conda need not be on PATH. An env changed after its last run (`conda-meta/history` is newer) or not found is a gap.
- `pip-<hash>.txt`, only when such an env holds Python packages conda did not install (not in any `conda-meta` record's files, or reinstalled since, so `INSTALLER` is no longer `conda`), even when a `conda-lock.yml` was found: one requirements block per env, usable with `pip install -r`, noting a name also in `conda-meta` and a non-pip installer; a git install is written as `name @ git+<url>@<commit>`, and an editable or local-path install is commented out with its path. A pip folder newer than the env's last run, one without a readable name and version, or an env not found is a gap; a package uninstalled after the run and `pip install --user` packages are not seen.
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

`explore [--all]` lists explore runs of gated code for grill's "promote explore runs" (see the grill skill); it only reads. It keeps every attempt of a command, failed ones too, with its code version (script sha256), exit and scope. Promotion needs an approved rerun with fresh output identity: `report` marks an output written inside an explore attempt and not re-observed under a matched approved attempt `not re-run under approval`, and never relabels it. An explore run never validates a check or owns an output.


Codex uses its own hook configuration (`hooks/codex.json`) and records approvals and receipts with `host: codex`. It requires enabled/trusted hooks and a new session after installation. Codex 0.160.0 sends command output without exit metadata in `PostToolUse`, so these receipts have `exit_status: unknown` and verification reports `CONFORMS_WITH_GAPS`. Never infer success from a Codex post event or from text printed by the command. A run without a dispatched post hook remains `no receipt`. Older unreceipted Codex runs cannot be recovered by upgrading.

The report lists what it cannot see:
- A receipt's time is when the hook fired, so outputs of a run moved to the background postdate it.
- Mycelium's lineage covers finished sessions only.
- Code run through MCP notebook tools bypasses both the gate and the lineage.
- A run proves a script ran, not that it implements the plan's choices; the review step checks that.
- A gate error in the plan's window (`gate-errors.jsonl`, from approval to now, same or unnamed session) is a gap: observation is incomplete there. It does not say which action went unobserved, so do not say one did. An unreadable journal is a gap (observation history unavailable); errors before the approval or from another session are ignored.

Output producers are graded, never just guessed from time. Only `supported` names a producer: a matched run of this plan whose Pre and Post bracketed the output's change, with no overlapping attempt that could have written it (`attempt-observed`). Snakemake's per-output record joined to a wrapper run by time is a `workflow-record` candidate (two wrappers: unresolved). Mycelium's lineage is a `lineage-record` candidate only: it counts when one matched attempt is joined by an explicit id or by inference (session, command, script, exactly one attempt; say the join is inferred), not for unresolved/static-only detection, a nonzero exit, a missing path or a changed hash, and a static path or a hash read from disk is not proof of a write. It can confirm an observed producer (`lineage agrees`) or name a second one (unresolved), never make `supported`. Time alone (`timing-only`, including receipts from before launch matching) is at most a `candidate` and always a gap, even for one run within five seconds; the By column then reads `unresolved` and the candidates are listed beside it. Say so: a candidate is a lead, not a producer. An output written before the approval, or by an explore run (a claim read from it blocks), is a block; the rest are gaps. An observed change shows the file changed during that run, not that its code wrote it, and a folder on `Outputs:` is watched as a folder, so ask for files or a one-level glob when the producer matters.

## Plan diff

Before the user re-approves a revised plan (for example a run plan presented again after a fix, see grill's `references/run-plans.md`), show what changed since the plan it replaces, read-only:

```bash
python3 - --plugin-root <skill-dir>/../.. diff <old-hash> <new-hash> < <skill-dir>/scripts/verify.py
```

It reads each plan from the approvals, or, for one shown but not yet approved, from the gate's pending plans, and compares them whole, with whitespace collapsed and nothing shortened: the objective; the table row by row (keyed by the ID column, `#`, `no`, `no.` or the first), reporting changed, added and removed rows, dropped columns and a changed row order; the `Inputs:` and `Outputs:` lines; the raw text of the `<!-- validation-bindings -->` and `<!-- exact-execution -->` blocks (compared, not interpreted); and the runs the table allows (scope). A row whose ID is used twice or missing is reported as "cannot compare", never silently overwritten. A changed objective or Choice cell is flagged as a possible scientific change; whether it is one is the user's call, so name it and let them decide. It reports exact equality of what the plans say, not that the science is unchanged, and a whitespace-only edit is no change. Write nothing; the revision itself belongs in the analysis folder's `TRACKER.md`.

## Multiplicity

When the user asks what was tried before a result (which tests, models, or thresholds, how many runs, how many plan revisions), show the record for one approved plan, read-only:

```bash
python3 - --plugin-root <skill-dir>/../.. multiplicity <hash> [--json] < <skill-dir>/scripts/verify.py
```

A counts line, then one timeline, oldest first: each earlier approved plan that names one of this plan's scripts or `Outputs:` paths (a revision), with its changed Choice cells; each run of those scripts or in the analysis folder, as an explore run, a run under an earlier plan, or a run under this plan, with its command and exit status; and this plan, marked `approved (selected)`. It stops at this plan's last run. A run whose script differs from the version this plan last ran is marked `other code version`. Counts come from receipts and approvals only; a run whose approvals were not read is counted as a gap. Receipts do not record which files a run wrote, and a value changed inside a script shows only as another code version. Show the table as printed and judge nothing: which run is the real one, and whether the tries need a correction, is the user's call. Write nothing.

## Runs

When the user asks which runs a results folder holds, or whether the runs this analysis cites are still good, list them, read-only:

```bash
python3 - --plugin-root <skill-dir>/../.. runs [RESULTS_DIR] [--json] < <skill-dir>/scripts/verify.py
```

Without `RESULTS_DIR` it uses `results/` in the newest approval's analysis folder. A run is a `run_<YYYYMMDD>_<slug>` folder (iterations end `_vNN`) with a label `RUN.txt` inside it, or, for a frozen run, a sibling `<run>.RUN.txt`. The table shows run, version, kind, status, updated (the newest file inside, not the folder), id (a content id of the file names and sizes), and why. `results/current` is shown as a pointer. Findings are gaps or info: an unlabelled run, a frozen-label sibling, a malformed label (with its line), `superseded_by` or `reads` naming a run that does not exist, and a state word in a run name (`final`, `complete`, `smoke`, `latest`, `current`, `review`). Several runs of one slug and kind that all say `current` give a suggestion, never a status. A Citations section checks each symlink in the analysis's `data/` and `code/` that points into another analysis's run: a gap when the cited run is unlabelled, superseded, failed or scratch, or the link dangles; info otherwise, and when the cited run changed after this analysis's newest approval. Show it as printed. Only the user sets a status; write nothing, and do not read the notes of a label for run names.
