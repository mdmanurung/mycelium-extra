---
name: verify
description: "After an approved mycelium-extra grill plan has run, check what ran against the plan and, once the user confirms, write the frozen plan, its run receipts, and the check into the analysis folder's `provenance/`. Flags failed, missing, edited, or unplanned runs, explore runs, changed pinned inputs, outputs not tied to a run of the plan, `<!-- claims -->` numbers that disagree with their output cell, and DOI, PMID or arXiv identifiers it was asked to resolve and could not (`--resolve-citations`; offline they stay a gap). Records the runs' conda and pip packages. Use when the user invokes mycelium-extra verify, asks whether an analysis ran according to plan, wants provenance recorded, or needs a draft AI-use disclosure paragraph for the analysis. Subcommands: `exercise` (a labelled synthetic review exercise; `exercise reveal` shows its answer), `list`, `report`, `write`, `disclose` (a read-only draft methods paragraph on what the agent did), `diff` (what changed between two plans), `stale` (what is out of date or needs re-running), `status` (an overview of what was planned, run, or verified), `multiplicity` (what was tried before the plan was settled), `explore` (this session's explore runs), `runs` (the labelled run folders of a results folder), `refs` (which saved plans pinned a given file). Not for planning (use grill) or judging code quality (use Mycelium's review)."
---

# Mycelium Extra: Verify

Check one approved plan against the gate's record of what ran, and record the result as provenance once the user agrees. The script judges only what the records show; it never re-runs anything, and nothing here edits receipts or approvals.

## Synthetic review exercise (only when requested)

Run `sh <skill-dir>/../../hooks/py.sh - --plugin-root <skill-dir>/../.. exercise < <skill-dir>/scripts/verify.py`. Keep the printed synthetic label. Ask what discrepancy the user finds. After their answer, run the same command with `exercise reveal` in this session. It needs no gate, reads no project state and writes nothing. Never insert the exercise into a genuine report or treat it as a score. Do not start an exercise without the user's request.

## 1. Find the plan

- `list`, `report`, `write`, `diff`, `multiplicity` and `explore` require the approval gate (`.mycelium-extra/gate.json`). Without it, say so and stop. `stale`, `status`, `runs` and `refs` read committed provenance and run on a clone with no gate.
- Use the hash the user gives. Otherwise list the approved plans, newest first, and ask which one:

  ```bash
  sh <skill-dir>/../../hooks/py.sh - --plugin-root <skill-dir>/../.. list < <skill-dir>/scripts/verify.py
  ```

Always run the script from stdin, from inside the repository. Running it by path opens Mycelium's post-action cycle. The script finds the gate's state folder itself, so never put that folder's name on the command line.

## 2. Check, read-only

```bash
sh <skill-dir>/../../hooks/py.sh - --plugin-root <skill-dir>/../.. report <hash> [--analysis-dir <folder>] < <skill-dir>/scripts/verify.py
```

The analysis folder is guessed from the plan's scripts; pass `--analysis-dir` when the guess is wrong. `--json` gives the raw result. `report <hash> --trace [ROW]` (hash first) prints a read-only decision trace instead: one line per plan row, or with ROW that row's declared script and exact command, the attempts that ran it, its bound checks' results and its supported outputs, each labelled `declared`, `observed`, `check result`, `candidate` or `unresolved`. It is refused with `--json`, `write` and the other actions, and writes nothing.

It also runs scilintr on the analysis folder's code (outputs, logs, and provenance skipped; the planned scripts when there is no folder): `scilintr` for Python, and for R `Rscript -e` calling `scilintr::lint_project()` on one folder holding a copy of the R code, so its cross-file rules run too, as Mycelium's analyze skill requires. A Jupyter notebook's code cells are extracted (magic and shell lines commented out) and linted with its kernel's language; findings are cited as `<notebook>.ipynb[code cell N]:<line>`, and a notebook whose code does not parse is a gap. The `{r}` and `{python}` chunks of `.qmd` and `.Rmd` files are linted the same way, with prose and other lines blanked so a finding cites the document's own line (`<doc>.qmd:<line>`); display blocks, other engines (an `engine=` option picks the language, so `{r engine="bash"}` is skipped), and inline `` `r x` `` code are not linted, and `eval=FALSE` chunks and documents set to `eval: false` are. A file pulled in with `child=` or `knitr::read_chunk()` is found relative to the document and linted under its own path; one named by a path that is not a quoted string, or not found, is a gap. A threshold finding (a rule or message containing "threshold", such as `R002` or `magic-threshold`) is info, not a block, when every number on its line (text after `#` is not read; a sign must match, so `-1` is not `1`) appears in a Choice cell of a plan row that names that script, or in any Choice cell when no row names it; this holds for notebook cells too. The `## Lint` section lists remaining findings, every `ANALYSIS_OK` waiver, and each finding a waiver suppressed with its reason (a second run with waivers off); an R waiver with no reason that suppresses a finding blocks. The linters' paths come from `.mycelium-extra/tools.json` when init recorded them, else `PATH`. If a linter is missing, say how to install it (`pip install scilintr`, `install.packages("scilintr")`) or how to record its path (`sh <skill-dir>/../../hooks/py.sh - --tools --scilintr PATH --rscript PATH < <init skill-dir>/scripts/gate_init.py`, in a repository that already has the gate on); never treat an unchecked language as clean.

It also checks the reason on each `default:` in the frozen plan's Source column, with plan-review's `scripts/default_reasons.py` (loaded from the plugin root). A row with no reason, a reason under three words, or only an empty phrase such as `standard` is an advisory `info` finding that names the row; it does not change the status. If that script is missing or fails, the check is a gap.

It also checks claims: each `<!-- claims -->` block in the analysis doc (`<NAME>.md`, Mycelium's analysis doc), in a Markdown file on the `Outputs:` line, or in a document passed with `--claims <path>` (repeatable). Each block line names a value and the output cell it came from, `value | file column [row]`, with the file relative to the analysis folder or the repository. `row` is the first-column label; a table with more than one row needs it, so a common value such as `0.05` never verifies against some row of a column. `rows` as the column is the table's data-row count, and a JSON output takes a dotted path (`qc.n`, `qc.kept.1`). A value may start with `<`, `>`, `<=` or `>=`, and end with `%` (also tried against a fraction, reported as via transform). A value agrees when the cell, rounded half-up, half-even, or truncated to the value's last digit, equals it. The `## Claims` section counts each document's verdicts. A claim the cell contradicts, or one read from an output an explore run wrote, blocks; a claim whose file, column or row cannot be found, a file over `--hash-mb`, or a block line that does not parse is a gap. Numbers in the block's section (heading to heading) that no claim covers are listed as `info`: the block, not the prose, is the checked record.

It also reads citations: each DOI (`10.<4-9 digits>/<suffix>`), `PMID: <n>` and `arXiv: <id>` in the documents it checks for claims, one entry per identifier, plus each reference-shaped line under a `References` heading that carries no identifier (`no identifier`: listed, never resolvable). Offline, which is the default, an identifier is `not checked (offline)` and is a gap: verify never shows a citation as resolved that it did not resolve. `report <hash> --resolve-citations [--contact <email>]` queries Crossref, NCBI E-utilities and arXiv with stdlib `urllib`, one request per identifier with a wait between them, and compares the returned title and first author with the citation line: `resolved` when both appear in it, `mismatch` when they do not, `unresolved` when the service has no such record, `not checked (request failed)` when the request never reached a service (no network, a timeout, an error other than 404). The `## Citations` section counts each verdict. A mismatch or an unresolved identifier blocks; a reference with no identifier is info; a failed request is a gap. A resolved citation shows that the identifier exists and that its title and first author appear in the text, not that the paper supports the sentence citing it. The contact address, which Crossref and NCBI both ask for, is sent only when you pass it.

The report opens with `# Verify plan <hash>: <status>` and five rows: `Ran as planned`, `Numbers match`, `Code checks`, `Not checked` and `Next`. Each starts `yes`, `no` or `partly` with its reason, or `n/a` when the plan gave the check nothing to judge (for example no `<!-- claims -->` block), so a row is never `yes` while a problem is open. Quote these five rows to the user first, as printed, then the details below them. In the file `write` saves, `Next` says the provenance is saved.

The report ends with `Verify status:` and one of these values:
- `CONFORMS`
- `CONFORMS_WITH_GAPS`: something the records cannot show, such as a required validation check not established or a recovery whose equivalence is not established, a run with no receipt, an unrecorded exit status, an output not tied to a run, code scilintr could not check, or a citation identifier not checked (offline by default, or a request that failed).
  The gate takes a run's exit status from the hook event (Claude Code), the shell result's exit code (OpenCode's `metadata.exit`, recorded as `exit_source: response`; none, as for a background task or a tool error, is `unknown`), or nothing (Codex, below). On Claude Code, `PostToolUse` fires only after a command succeeds, so its receipt records exit 0 (`"exit_source": "event"`; the row reads `ran (exit 0 from hook event)`), and `PostToolUseFailure` gives the code from the `Exit code N` line, or `failed` or `interrupted` when there is none. A receipt with exit status `unknown` (a run started in the background, a payload without an event name) or null (from an older gate) is a gap, never a success, so a plan whose only evidence is such a run gets `CONFORMS_WITH_GAPS`. An `sbatch` receipt's exit status is the submit's; the job's state and `ExitCode` come from `sacct` (a submission is not a completion): `COMPLETED` with a nonzero `ExitCode` blocks, and a pending, running, unknown or partly finished array job is a gap.
- `DOES_NOT_CONFORM`: at least one of:
  - a failed run (a nonzero exit, a failure with no exit code, or an interrupted run) or Slurm job
  - a planned script edited after its run. The finding adds whether an approval covers the current version: a plan pinned it, it ran under a plan approved after the file was last modified (by file time), it ran only under a plan approved before that, or it has not run under any plan. The status stays `DOES_NOT_CONFORM` in every case; name the plan to check instead when one covers it
  - a required validation check whose result says it failed
  - a pinned input that changed since the approval
  - a scilintr finding that is neither fixed nor waived (a threshold finding the plan approved is info), or an R waiver with no reason that suppresses one
  - a file named exactly on the `Outputs:` line that was written before the approval (older files inside a named folder or glob are earlier runs' outputs, so they are only counted)
  - an incomplete Snakemake job
  - a claims-block value that the output cell it names contradicts, or that an explore run's output holds
  - a citation whose identifier has no record at the service, or whose record's title and first author do not appear in the citation text

The report also has a `## Validation` section when the approved plan declares `<!-- validation-bindings -->`, a `## Plan evidence` section when it records a `<!-- plan-evidence -->` block, and a `## Recovery` section when a step has more than one attempt. Read all three as evidence about the plan's own checks and the run history, not as a judgement of the science:
- Plan evidence re-runs each command the block records, through an allowlist guard: read-only programs only, no output redirection, no substitution, 10 seconds each and 60 for the block. A row reads `still true` (the output is byte-for-byte what the plan recorded, after trailing whitespace), `changed` (a gap, naming the first differing line) or `not checked` (a gap, naming why: a writing command, exit 2 or more, a timeout, the budget). `still true` says the output is unchanged, not that the claim it supports is right.
- Each check gets one outcome. `passed` needs a matched run of the check's invocation that created or changed its evidence file, pinned test files still as approved, and a result that says passed (a data-contract result passes with exit 0 and no block; warnings are kept). `failed` on a required check blocks; `not run`, `changed` (a pinned expectation edited or missing after approval), `unattributable` (a result the gate did not see the attempt write, or one modified afterwards) and `unsupported` (not a result `verify` can read) on a required check are gaps worded "not established": the expectation is not counted as met, and the plan is never `CONFORMS`. An optional check is an info line. `defined_by` is shown as the plan declared it, "not verified".
- Recovery lists every attempt of a step in order with what changed. A failed attempt followed by an equivalent retry (same command, or only flags the plan's `exact-execution` step calls operational) is info. A success after a changed command, script, engine config file or folder is a gap, "equivalence not established", and the earlier failure stays in the history. Do not describe it as recovered; say what changed and leave the choice to the user. A run of an instance with `exact-execution` that matched no declared step is a gap, "outside the exact reportable contract".

A script the gate re-pinned after an edit (the plan's working scope) and then ran is a gap: "ran at <time> as edited since approval; no approval froze that version", with `freeze <hash>` as the way out; the report also lists the re-pins as info. After a freeze the rerun belongs to the new instance and the gap is gone.

A plan re-approved with the same text and the same pins keeps one approval instance and its earlier runs; the report says so. Re-approved with other pins, it is a new instance: `report` checks the newest one by default (`--instance <id>` picks an earlier one), runs under another instance are listed as history and do not establish the freeze, and no run under the checked instance is a gap.

The Scope block also carries a **Qualification** (`qualified` or `not qualified`) with a short evidence table (authorization, completion, code and input identity, lineage, required validation, claim linkage: each `established`, `not established` with its reason, or `not applicable`) and one limitation line. It is separate from the verify status and is not a scientific judgement or a score. Quote the table as printed and name the limitation; never say a run is "reportable" or "verified" from the status line alone. `report --require-reportable` exits 3 when the run is not qualified (`write --require-reportable` saves the record first), and ordinary `report` is unchanged: `report` and `write` exit 0 whatever the status, `write` also prints a `Qualification:` line after `Verify status:`, and a `verify:` error (or `py.sh` finding no Python 3.9 or later) exits 1. The budgets are `--hash-mb` (default 2000) and `--seconds` (default 120); `--repo`, `--sacct`, `--scilintr` and `--rscript` override where it looks. A numeric claim can match its cell while its output's producer is unresolved: report both facts. Coverage counts under `## Claims` list prose numbers as listed, not checked; a claim on a registered `numbers.json` value shows the file's content, not which run wrote it. A Validation cell that is only prose, with no binding, is one info line (nothing checks it). Plans that name a `run.sh` or Snakefile get a `## Rerun evidence` section: declared, rerun attempted and rerun reproduced are separate facts, and verify never launches a rerun.

Before the tables the report has a `## Scope` block: which approval instance was checked, how many runs had a matched, unmatched, ambiguous or legacy launch, and how many outputs have a supported producer. Runs credited to the plan with no checked launch (Post without a matching Pre), ambiguous launches and attempts that never reported back are gaps; receipts from before launch matching are one info line.

A compound shell command's overall exit status cannot establish that each named step executed. Such receipts keep the overall status separately: an overall failure blocks, while each step's unknown execution is a gap. Malformed receipt or Snakemake records are skipped and reported as gaps, so damaged history cannot establish conformity. Header-only tables and duplicate column labels leave claims unverified; claims or percentage transforms outside the supported numeric range also leave explicit gaps.

## 3. Report to the user

- Start with the five summary rows. Give the status, the planned-scripts table, and each `block` and `gap` finding with what it means for the results. Keep the `info` lines short.
- Never paste the plan, or its `Plan status:` line, into the reply. The gate would offer the reply as a new plan to approve.
- For each `block`, name the fix and leave the choice to the user. Typical fixes:
  - re-run the step under the plan
  - re-check a changed input and approve a new plan
  - drop an output written before the approval
- Do not fix anything in this skill.
- For a decision trace, quote the labels as printed. A row that reads `no executable check bound`, `not checked`, `cannot map` or `unlinked` is a gap, not a pass; never say a choice was implemented or verified from a trace, and name its closing line: scientific correctness is not determined and imported helpers are not traced.
- A gap is not a failure. Say what it hides. For example, an output not tied to a run is often a run Claude Code moved to the background. An output written by a run of another plan is reported once per producing run and folder, naming the run's script; the Outputs table (and `write`'s `outputs-<hash>.tsv`) lists every file.
- For a claim mismatch, show the line, the claimed and the observed value, and the cell. Do not edit the document, the output, or the claims block: the user decides which is wrong, and a wrong output means a re-run under a new plan (grill). A verified claim means the text matches its cell, not that the analysis is right.

End the summary with three lines, and put in each one only what the report supports:

- **Established:** what the receipts and outputs do show — which planned steps ran under the approved plan, and which quoted numbers match their cells.
- **Still uncertain:** every gap, unknown or non-integer exit, unverified claim and unbound choice that remains, named as the report names it.
- **Next insight:** the one check, input or re-run that would close the largest gap, or the choice the user now has to make.

A line no check supports is not a summary: never move a gap into **Established**, and never offer a **Next insight** that is an analysis you would run without a plan.

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

(This confirmation is the agent's instruction, not a gate rule, so `write` runs whenever the agent runs it, unless `.mycelium-extra/gate.json` sets `confirm_writes` to true. Then first run `sh <skill-dir>/../../hooks/py.sh <skill-dir>/../../hooks/confirm_write.py prepare --kind verify-write --target <folder>`, show the user the `confirm write <id>` line it prints, and run `write` only after they type it: the gate denies it before.)


```bash
sh <skill-dir>/../../hooks/py.sh - --plugin-root <skill-dir>/../.. write <hash> --analysis-dir <folder> < <skill-dir>/scripts/verify.py
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
- Give the review command, which checks the code against the frozen plan, when a finding or result is unresolved or the user asks for a deeper review. Do not prescribe it again after an unchanged final run whose code was already reviewed before the freeze; follow the user's instructions and the project's conventions.

  ```
  /mycelium:review <folder> — check the code against the approved plan in <folder>/provenance/plan-<hash>.md
  ```

- End with one line: the status and the next action.

## Stale sweep

When the user asks what is stale or out of date, sweep every verified plan, read-only:

```bash
sh <skill-dir>/../../hooks/py.sh - --plugin-root <skill-dir>/../.. stale [--content] [--json] < <skill-dir>/scripts/verify.py
```

It reads the committed `provenance/receipts-<hash>.jsonl` and `outputs-<hash>.tsv` (found through git, so ignored folders are skipped), and needs no gate. For each stale plan it lists scripts edited or deleted since they ran, pinned inputs that changed, and outputs rewritten or deleted since verify recorded them, plus the session IDs of its runs. By default outputs are compared by size and time and the result says `metadata checked`; with `--content` each output is hashed against the SHA256 verify saved, and a file or budget it did not reach is `content not checked`. Say which check was run.

- In a Mycelium project, run each stale plan's `findings:` command, which searches `.living/findings/` for its session IDs and `plan <hash>` (the gate suggests `<session-id>; plan <hash>` as a ledger's Run/Session cell), to name the findings that rest on a stale plan. A finding's ledger may cite a run ID instead; if nothing matches, say the link is unknown, not that no finding is at risk.
- Suggest, per stale plan: re-verify it (`verify <hash>`), or re-plan the re-run with grill. Write nothing.

## Files a correction affects

When the user says an expectation or test file was wrong, find the saved plans that pinned it, read-only:

```bash
sh <skill-dir>/../../hooks/py.sh - --plugin-root <skill-dir>/../.. refs <path> [--sha SHA256] [--json] < <skill-dir>/scripts/verify.py
```

Ask for the old file's SHA256 (`git log`/`git show` or the saved `validation-<hash>.json`); without it every path match is only `possible`. Report each line as printed: `definite` means a pinned file had that SHA256, `possible` means same path with another or unchecked SHA256, or named in the plan text. Say that "no recorded reference" is not proof the file was unused, and that bundles with no validation record were not searched. Write nothing, and never edit an old receipt or finding; the user decides whether to rerun, amend or keep the result with a limitation.

When the user asks for status or an overview, show one table, read-only:

```bash
sh <skill-dir>/../../hooks/py.sh - --plugin-root <skill-dir>/../.. status [--json] < <skill-dir>/scripts/verify.py
```

One row per plan the gate approved (local, this clone only) or verify recorded (committed `provenance/`): the analysis folder (the provenance folder, else guessed from the plan table), runs, the verify status from `PROVENANCE.md` with the bundle's state appended (for example `CONFORMS (complete)`), or `not verified`, `stale` changes, the lint verify recorded (`N finding(s)`, `M approved threshold(s)` for threshold findings the plan approved, `clean`, `gap: <language> not checked`, `not run`, or `not recorded`; scilintr is not re-run), and the folder's entry in any `ANALYSIS_MANIFEST.md`: `listed: <first word of its status>`, `listed`, or `not listed`. A `not listed` analysis skipped Mycelium's manifest step. Show the table as printed, then suggest at most one next step, such as verifying the newest unverified plan. Write nothing.

`explore [--session ID | --all] [--json]` lists explore runs of gated code for grill's "promote explore runs" (see the grill skill); it only reads. It lists this session's runs, taking the session from `$CLAUDE_CODE_SESSION_ID` or `--session`; where neither is set (Codex, OpenCode) it says "no session ID found, so every session is shown" and lists the last 7 days of every session. It keeps every attempt of a command, failed ones too, with its code version (script sha256), exit and scope. Promotion needs an approved rerun with fresh output identity: `report` marks an output written inside an explore attempt and not re-observed under a matched approved attempt `not re-run under approval`, and never relabels it. An explore run never validates a check or owns an output.


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
sh <skill-dir>/../../hooks/py.sh - --plugin-root <skill-dir>/../.. diff <old-hash> <new-hash> < <skill-dir>/scripts/verify.py
```

It reads each plan from the approvals, or, for one shown but not yet approved, from the gate's pending plans, and compares them whole, with whitespace collapsed and nothing shortened: the objective; the table row by row (keyed by the ID column, `#`, `id`, `no`, `no.` or the first), reporting changed, added and removed rows, dropped columns and a changed row order; the `Inputs:` and `Outputs:` lines; the raw text of the `<!-- validation-bindings -->` and `<!-- exact-execution -->` blocks (compared, not interpreted); and the runs the table allows (scope). A row whose ID is used twice or missing is reported as "cannot compare", never silently overwritten. A changed objective or Choice cell is flagged as a possible scientific change; whether it is one is the user's call, so name it and let them decide. It reports exact equality of what the plans say, not that the science is unchanged, and a whitespace-only edit is no change. Write nothing; the revision itself belongs in the analysis folder's `TRACKER.md`.

## Multiplicity

When the user asks what was tried before a result (which tests, models, or thresholds, how many runs, how many plan revisions), show the record for one approved plan, read-only:

```bash
sh <skill-dir>/../../hooks/py.sh - --plugin-root <skill-dir>/../.. multiplicity <hash> [--json] < <skill-dir>/scripts/verify.py
```

A counts line, then one timeline, oldest first: each earlier approved plan that names one of this plan's scripts or `Outputs:` paths (a revision), with its changed Choice cells; each run of those scripts or in the analysis folder, as an explore run, a run under an earlier plan, or a run under this plan, with its command and exit status; and this plan, marked `approved (selected)`. It stops at this plan's last run. A run whose script differs from the version this plan last ran is marked `other code version`. Counts come from receipts and approvals only; a run whose approvals were not read is counted as a gap. Receipts do not record which files a run wrote, and a value changed inside a script shows only as another code version. Show the table as printed and judge nothing: which run is the real one, and whether the tries need a correction, is the user's call. Write nothing.

## Runs

When the user asks which runs a results folder holds, or whether the runs this analysis cites are still good, list them, read-only:

```bash
sh <skill-dir>/../../hooks/py.sh - --plugin-root <skill-dir>/../.. runs [RESULTS_DIR] [--json] < <skill-dir>/scripts/verify.py
```

Without `RESULTS_DIR` it uses `results/` in the newest approval's analysis folder. A run is a `run_<YYYYMMDD>_<slug>` folder (iterations end `_vNN`) with a label `RUN.txt` inside it, or, for a frozen run, a sibling `<run>.RUN.txt`. The table shows run, version, kind, status, updated (the newest file inside, not the folder), id (a content id of the file names and sizes), and why. `results/current` is shown as a pointer. Findings are gaps or info: an unlabelled run, a frozen-label sibling, a malformed label (with its line), `superseded_by` or `reads` naming a run that does not exist, and a state word in a run name (`final`, `complete`, `smoke`, `latest`, `current`, `review`). Several runs of one slug and kind that all say `current` give a suggestion, never a status. A Citations section checks each symlink in the analysis's `data/` and `code/` that points into another analysis's run: a gap when the cited run is unlabelled, superseded, failed or scratch, or the link dangles; info otherwise, and when the cited run changed after this analysis's newest approval. Show it as printed. Only the user sets a status; write nothing, and do not read the notes of a label for run names.

## Disclosure draft

When a journal, a funder or a collaborator asks what the agent did in an analysis — or before the user writes an AI-use methods paragraph themselves — draft one from the records, read-only:

```bash
sh <skill-dir>/../../hooks/py.sh - --plugin-root <skill-dir>/../.. disclose <hash> [--analysis-dir DIR] < <skill-dir>/scripts/verify.py
```

It prints plain text, one sentence per line, over the same check `report` makes (so `--instance` and the `## Citations` verdicts follow `report`'s rules; `disclose` itself takes no `--json`, has no `--trace`, and writes nothing). Each sentence names the record it came from, `[source: <path or record>]`, and covers the plugin and its version, the plan's steps and its approval and freeze history, the runs the gate recorded with their launch evidence, any re-pins, the recorded environments, the verify status and qualification, the claims checked, the citations found, the lint state, and the repository commit. Anything a record cannot show is `[BLANK: <what is missing>]` — no receipts, no claims block, no re-pin record, an unreadable plugin manifest, an unreadable commit: never fill one in from memory or from the report's prose. Present it as a draft: the user edits what they keep, deletes what they do not want to send, and fills in every `[BLANK: ...]` themselves. Say plainly that the draft states what the records show, not that the analysis is right, and that a sentence about a claim or a citation carries the same limits as `report` gives them.
