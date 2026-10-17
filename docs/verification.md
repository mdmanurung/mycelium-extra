# Verification reference

Use this page when you need to interpret a `verify` report or record provenance.
For the everyday workflow, start with [Usage tiers](usage.md#tier-3-verify-reportable-work).


A finished job is only the beginning of checking an analysis. Did every planned step run? Did an input change? Does the number in the write-up match the saved table? After execution, `verify <hash>` compares the approved plan with the records that can answer those questions.

It uses the gate's own table parser, so the scripts covered by verification are the same ones covered by approval. It reads the record without re-running the analysis. In Codex 0.160.0, missing hook exit metadata remains a gap even when the command appeared to finish successfully.

Damaged receipt lines or workflow metadata are reported as evidence gaps, rather
than silently discarded as a complete history. Malformed approval records produce
an explicit error. A compound shell command does not prove each named step ran:
individual outcomes remain gaps, while a failed aggregate command blocks.
Claim tables with duplicate column headers or no data rows are unverified;
unrepresentable numeric values are also gaps, never verified by accident.

**In this section:** [What the report shows](#what-the-report-shows) · [Validation](#validation) · [Recovery](#recovery) · [Status](#status) · [Qualification](#qualification) · [Rerun evidence](#rerun-evidence) · [What it writes](#what-it-writes) · [Stale plans](#stale-plans) · [Overview of all plans](#overview-of-all-plans)

## What the report shows

- **Each planned script** (a path in the plan table with a script extension, a `Snakefile` name, or a `#!` line; another file it names, such as a log to read or a README, is not one): ran, failed, no receipt, edited or deleted since it ran, or only passed to other code. A lint or parse call (`Rscript -e 'lintr::lint()' x.R`) or another tool's script read from stdin gets the path but does not run it, so it is not counted as a run. Steps run inside a `run.sh` or Snakemake wrapper are matched through Snakemake's per-output records, and Slurm jobs through `sacct`. A job counts as a run of a planned script when its receipt names the script or when the `sbatch` line Slurm recorded (SubmitLine, with `$dir` expanded) does. A job that names no planned script and did not complete is a gap, and so is a job ID recorded for different `sbatch` commands.
- **Command and folder runs:** a run credited to the plan that no script row covers (an approved `snakemake` or `sbatch` command, a script run through a granted folder) is checked the same way: a failed run blocks, one with no exit status is a gap, a compound command (`cd x && snakemake`) is a gap whose own failure blocks, and a Slurm submission that exited 0 is judged by its job's state in `sacct`, as a script row is. A later run of the same step supersedes an earlier one, where a step is the command's kind, working folder and the script, Snakefile or job script it names, so a retry with other options counts (a Snakemake run naming none is the Snakefile in its folder; any other command with none is keyed by its command line). The supersession decides the step's outcome only: every attempt stays visible under [Recovery](#recovery). A folder whose scripts the plan table grants is a gap when neither a run of a script in it nor a command run from it was recorded.
- **Exploration history:** `verify explore` lists every attempt of an explore command, failed ones included, with its code version (the script's sha256), exit and scope (the approval instance of `allow explore <hash>`, or the session-wide grant). An explore run never validates a check and never owns an output. An output written inside an explore attempt and not re-observed under a matched approved attempt is `not re-run under approval`: promotion needs an approved rerun with fresh output identity, and the explore output is never relabelled. The gate records no output hash for explore runs, so "same content" is judged by the file's write time falling inside the explore attempt.
- **Other runs:** explore runs, runs under another plan, and scripts in the analysis folder that ran but are not in the plan table.
- **Pinned inputs** that changed since the approval.
- **Outputs:** the files on the plan's `Outputs:` line, when each was written, and how well the records name the run that wrote it ([Output producers](#output-producers)): only a `supported` producer fills the By column; otherwise it reads `unresolved` with its candidates beside it. A `{a,b}` list is expanded, and a `<name>` placeholder or a comma-less `{name}` (a Snakemake wildcard) is read as `*`; a word starting with `…` names no path and is a gap (the approval card flags it too). A file named exactly that was written before the approval blocks. Older files inside a named folder or glob are earlier runs' outputs, so they are counted, not checked.
- **Launch evidence:** a run is a *checked launch* only when the gate saw both its Pre and its Post and matched them (`launch_match: matched`). Runs credited to the plan whose Post had no matching Pre are a gap (`no checked launch: Post without matching Pre`), grouped by reason; identical launches without a call id are a gap too (`ambiguous launch`). Receipts written before launch matching (no `launch_match`) are read as before and counted in one info line, never as matched. An attempt that started and never reported back (the gate moves it to `launches/abandoned/`) is a gap naming its start time: what it ran or wrote is not known. A late Post for an expired launch shows both as an unmatched receipt and as an abandoned attempt.
- **Approval instances:** each approval of a plan writes an immutable instance (`approval-instances/<hash>/<id>.json`: the plan hash, pins, scripts, preparation and limitations), and `approvals/<hash>.json` points to the newest. `report` checks that instance by default; `--instance <id or unique prefix>` checks an earlier one against its own pins and approval time (`report` only: a saved bundle is keyed by the plan hash, so `write` records the current instance). Runs launched under another instance (or one that records none) are shown as history and cannot establish the freeze being checked; none under it is a gap. Approving the same plan with the same pins reuses its instance. An approval with no instance id is legacy: read as one freeze, with an info line.
- **Validation:** the plan's approved acceptance checks (`<!-- validation-bindings -->`), each reconciled with the result of its matched run ([Validation](#validation)).
- **Recovery:** a step with more than one attempt under this approval lists every attempt, and a success that follows a failure is judged as an equivalent retry or as unestablished ([Recovery](#recovery)).
- **Exact execution:** when the approved plan declares `<!-- exact-execution -->`, a run of that approval the gate did not match to a declared step is a gap: it is outside the exact reportable contract, so its command was not frozen.
- **Unreceipted runs:** scripts that Mycelium's lineage saw run in the window but the gate did not, such as scratchpad scripts.
- **Gate errors:** a hook that failed open (`gate-errors.jsonl`) did not check or record what it saw. An error between the approval and the verification, from a session that approved or ran the plan or from one the record does not name, is a gap naming its time and event: observation is incomplete there. It is a bounded statement, not a claim that a particular action went unobserved. An error before the approval, or from a different session, is ignored. A journal that cannot be read, or has a malformed line, is a gap too: observation history unavailable.
- **Lint:** scilintr on the analysis folder's code, as Mycelium's analyze skill requires, with every `ANALYSIS_OK` waiver listed and tied to the finding it suppressed.
  - Where the linters are: `python3 - --tools [--scilintr PATH] [--rscript PATH] < skills/init/scripts/gate_init.py` checks each one works (the Python CLI on an empty file, `packageVersion("scilintr")` through the Rscript) and records the paths in `.mycelium-extra/tools.json`, which `verify` and the approval card read. It works on a gate that is already on and leaves `gate.json` alone. Without it, `scilintr` and `Rscript` are looked up on PATH, and a missing one is a gap; `--scilintr` and `--rscript` on `verify` override the record.
  - Waivers: a second run with waivers off lists each finding a waiver suppressed, with the waiver's `file:line` and reason, in the report and under `# Waived findings` in `lint-<hash>.txt`. R's scilintr accepts `ANALYSIS_OK[x]:` with nothing after it (Python's needs a reason), so an R waiver with no reason, on the line or the next comment line, that suppresses a finding blocks. If the second run fails, the report says the waived findings were not listed; the status does not change.
  - Python goes through the scilintr CLI. R goes through `scilintr::lint_project()` on a copy of the R code, since scilintr 0.1.1's `main()` lints only its first argument and always exits 0.
  - Jupyter notebooks' code cells are linted too, with magics commented out. A finding is cited as `<notebook>.ipynb[code cell N]:<line>`.
  - The `{r}` and `{python}` chunks of `.qmd` and `.Rmd` files are linted as well, cited by the document's own line.
- **Claims:** each `<!-- claims -->` block in the analysis doc, a Markdown output, or a `--claims` document names a value and the output cell it came from (`8 | outputs/summary.tsv n_hits`, `0.0162 | outputs/de_results.tsv padj SIGLEC1`). A value is checked against its cell after rounding. A non-finite cell, such as NaN or infinity, is an unverified gap with its value and location. A table with more than one row needs a row label, so a common value cannot match some row by chance. Other numbers near the block are listed, not checked. Under the counts a `Coverage` line gives the blocks found, the claim lines (and how many did not parse), the cells actually read and compared, how many matched, mismatched or stayed unverified, and the prose numbers listed but not checked: a prose number is never counted as checked. A claim that cites a Mycelium `numbers.json` fragment is still compared with its cell, but `register_value` upserts across runs, so a match shows the file's current content, not which run wrote that key; an info line says so. Run attribution comes from the file's producer in the Outputs table, not from the number.
- **Prose Validation cells, as info:** when the plan table has a Validation column, each row whose cell holds prose and that no `validation-bindings` check covers is counted in one line (`N Validation cells are prose only; nothing checks them`). It is not a gap: the plan never asked for a check, and the line does not say the prose is wrong.
- **Fact tags, as info:** per tag, how many facts in the frozen plan's Evidence and in the analysis doc's Key Findings carry `[human-stated]`, `[agent-derived: <path>]`, or `[agent-asserted: <source>]`. It flags an untagged fact, an `agent-derived` one without its path, and an `agent-asserted` one without a source. A list with no tag at all (a plan from before 0.9.35) gets one line. The status does not change.

## Output producers

Each output row carries `producer_attempt`, `evidence_method`, `strength`, `candidates` and `reason` (all in `report --json`; the table shows method, strength and candidates beside the By column).

| Method | What it rests on | Strength |
|---|---|---|
| `attempt-observed` | A matched receipt of this plan whose `outputs_changed` lists the output: the gate saw the file created or changed between the run's Pre and Post. No other attempt that overlaps it in time (any plan, explore runs, running Slurm jobs, launches that never reported back) could have written it. A sibling run of the same plan that watched this very path and did not see it change does not count as a rival. | `supported`; `unresolved` with every overlapping attempt listed when one exists |
| `workflow-record` | Snakemake's per-output record names the rule, and a wrapper run that fits the record in time is the join. | `candidate`; `unresolved` when two wrapper runs fit |
| `timing-only` | The file's time against the receipts' times: no observation (a receipt from an older gate, a run whose Post had no Pre, or an output the run's attempt did not see change). | at most `candidate`, and always a gap, even when a single run is within five seconds; `unresolved` for competing writers |
| `lineage-record` | Mycelium's lineage lists the output as a static output of an action that is joined to one matched attempt: by an explicit attempt or call id on the action (upstream writes none at the pinned revision), or by inference when the session id, the command (a whole command or one `&&`/`;`/`\|` segment), the script and the action's time all match exactly one matched attempt. The report says the join is inferred. Not used: `io_detection` other than `static`/`static+repository`, a nonzero exit, a path that was missing when recorded, a hash that differs from the file now, a file time outside the joined attempt, an attempt that watched the declared outputs and did not see this one change, or no unique attempt. Lineage can confirm an `attempt-observed` producer (`lineage agrees`) or name a second producer, which makes the output `unresolved` (two producers). | at most `candidate`, never `supported`; a static path and a hash read from disk (upstream fills missing hashes later) are not proof that this invocation wrote the file |
| `none` | No recorded run. | `unresolved` |

Extraction warnings (the action's `lineage_warnings` and the manifest's `extraction_warnings` for it) are shown beside the lineage line. Mycelium's session id is its own date-counter unless it fell back to the host's, so an inferred join is usually possible only in the fallback case; a manifest is written at Stop, so during an active session there is none and nothing changes. A malformed manifest or action is skipped, as before.

What this does not prove: an observed change shows the file changed during that run, not that the run's code wrote it; an unrelated process writing in the same seconds is seen only as an overlapping attempt when it was itself recorded. A folder on the `Outputs:` line is watched as a folder (the gate sees it change, not which file), so name files or a one-level glob to get `supported`. A receipt records when the run ended, and when the gate recorded it, when it started; without a start, a run that overlapped it is seen only if it ended within the clock tolerance.

## Validation

A plan may declare acceptance checks in a `<!-- validation-bindings -->` block: per check an `id`, the `plan_row`, whether it is `required`, who defined it (`defined_by`), the pinned `test_paths` (a test or expectation file), the `invocation` that runs it and the `evidence_path` it writes. Approval freezes the block and pins the files. `verify` runs nothing; it reads the instance's record, the receipts and the evidence file, and gives each check one outcome:

| Outcome | What it means | Required check | Optional check |
|---|---|---|---|
| passed | A matched run of the invocation under this approval instance created or changed the evidence file, nothing touched it afterwards, the pinned files are still as approved, and the file says it passed. A data-contract result (`mycelium-extra.contract_result.v1`) passes with exit 0 and no block; its warnings are kept and shown (`passed with N warning(s)`). | no finding | no finding |
| failed | The check command exited nonzero, or the result says failed (a data-contract result with exit 2, naming the blocking checks with their expected and observed values). | **block** | info |
| not run | No matched run of the invocation under this instance (a run under an earlier instance does not carry over; the line says so), or a data-contract result whose checks could not run (exit 3, or exit 1 for an unusable contract), even when the runner passed the checker's nonzero exit code on. | gap | info |
| changed | A pinned test or expectation file differs from approval or is missing, or a data-contract result was produced from a contract that is not a pinned file. An expectation edited after approval does not keep its authority. | gap | info |
| unattributable | The evidence file is not tied to the matched attempt: the gate did not observe outputs, the attempt did not create or change the file (it was written by the agent outside the run), or it was modified after the attempt. A result written by hand, or a stale one, cannot pass. | gap | info |
| stale | The check passed, but a later attempt under the instance (not a check's) changed a declared output, or ran without its outputs being observed, so the result no longer speaks for the outputs. Run the check again. | gap | info |
| unsupported | The file is not JSON or has no `status` of passed or failed, a data-contract result's `checks` or `contract` is malformed, or the exit status was not recorded. | gap | info |

A check command that exits nonzero is a failed run and blocks like any failed run, whatever its result says; a runner that should leave the judgement to the result file exits 0. **Not established** is the gap wording for a required check: the plan's expectation is not counted as met, and a report with such a gap is never `CONFORMS`. It is not a failure; it says the records cannot show the check passed. `defined_by` (`agent-proposed`, `researcher-approved`, `independent`) is shown as the plan declared it, with "not verified": a label is not proof of who wrote the check, and approval binds the named expectation, not its scientific truth. The evidence file must be one of the plan's declared outputs (or inside a declared output folder) for the gate to observe it being written.

`write` adds `validation-<hash>.json` to the bundle: the frozen binding (with each file's sha256 and the definition's sha256), every check's outcome, reason and attempt, and the evidence file's path and sha256. A bundle without it is from a plan with no binding, or from an older verify, and reads as before.

## Recovery

A step is what [Command and folder runs](#what-the-report-shows) groups: the command's kind, folder and the script it names. When one has more than one attempt under the checked approval instance, the `## Recovery` section lists every attempt in order with its time, command and outcome, and what changed from the attempt before it: the argument words added or removed, inline environment variables, the folder, the script's content, an engine config file. A changed pinned input between attempts of one approval instance is not seen: the receipts carry the approval's pins, not the file's state at the attempt. The earlier receipts are never dropped; only the step's outcome is that of its latest attempt.

- **Recovered: equivalent retry (info).** An earlier attempt failed and the latest succeeded with the same command, or one that differs only in flags the plan's `exact-execution` step lists as `operational`, with the same code and inputs. A transient failure does not block.
- **Recovered with a changed command: equivalence not established (gap).** The success changed an argument that is not operational, for example `--model original` to `--model alternative`. The earlier failure stays visible and the success does not stand for the approved computation until the researcher says so. A plan without `exact-execution` has no operational flags, so any changed word counts.
- **Recovered after changed code or inputs: equivalence not established (gap).** The command words match, but the script, an engine config file or the folder differs between the failed attempt and the success.
- A step whose latest attempt failed is the block it was; a step with several successful attempts (`--part a`, then `--part b`) is listed without a finding.

An instance that declares `exact-execution` also reports each run the gate did not match to a declared step (`exact_match` not true on its receipt; a validation check's own run is matched by its invocation) as a gap, "outside the exact reportable contract". A plan without the block keeps its broad grants and the report says nothing about exact execution.

## Status

It ends with `Verify status: CONFORMS`, `CONFORMS_WITH_GAPS`, or `DOES_NOT_CONFORM`.

- **Blocks:** a failed run, a required validation check that failed, an edited script, a changed input, an output older than the approval, an incomplete Snakemake job, a scilintr finding neither fixed nor waived, a claim its cell contradicts, or a claim read from an explore run's output.
- **Gaps:** things the records cannot show. A required validation check that is not run, changed, unattributable or unsupported is a gap (not established). A success after a failed attempt with a changed command, script, engine config file or folder is a gap (equivalence not established). These include code scilintr could not check: scilintr not installed, timed out, or with unreadable output, or a script or notebook whose code does not parse, under the Python verify runs on or under R (which scilintr would silently pass). An output whose producer is not `supported` (timing only, a candidate, competing or overlapping writers) is a gap, and so is a run with no checked launch or an attempt that never reported back. An output written before the approval, or by an explore run, is the block it always was.

## Qualification

Separate from the three status names, `report` computes whether this approval instance's records are complete enough to report from. It is not a scientific judgement and not a score: each dimension is `established`, `not established` (with its reason) or `not applicable`, and the run is `qualified` only when every applicable dimension is established. It is under `qualification` in `--json`, and as a short table and one limitation line in the report's Scope block.

| Dimension | Established when | Not applicable when |
|---|---|---|
| authorization | at least one run, every run credited to this instance is a matched launch (none unmatched, ambiguous or legacy), the approval has an instance id, and there is no gate error in the window, attempt without a completion record, or run outside a declared exact execution | never |
| completion | every planned step's latest attempt completed: an integer exit 0, and for a Slurm submission a job that `sacct` shows `COMPLETED` (a job only submitted, running or pending, or a background start, is not a completion) | never |
| code and input identity | every script that ran and every pinned input is unchanged and was compared by content hash. A fingerprint that is size and time only reads `metadata only` and is not counted as strong | never |
| lineage | every declared output exists and has a `supported` producer (a matched attempt saw it change, and no overlapping attempt could have written it) | `Outputs: none` |
| required validation | every check marked `required` passed | the plan binds no check, or none is required |
| claim linkage | each claim cell matched and the output it cites has a supported producer | no claims block |
| no blocking finding | no finding in the report is a `block` (a failed run, an open scilintr finding, a contradicted claim, a changed pinned input and so on): a run that fails verification is never reportable | never |
| no open gap | no finding in the report is a `gap` (for example a recovery with a changed command, a run outside the plan table, a skipped receipt line, scilintr not run, an incomplete provenance bundle): a gap is evidence that could not be established | never |

A matching number with an unresolved producer shows both facts: the claim is `verified` against its cell, and claim linkage and lineage are `not established`. So a `qualified` run is always `CONFORMS`; the reverse does not hold (a `CONFORMS` run can still lack, say, supported producers for claims). The limitation line names the first dimension not established, its next action, and the number of open gaps. Lineage with a folder or glob `Outputs:` line is not established when no file under it was written under this approval. An approval instance prepared before readiness was recorded (`legacy-no-ready`) leaves authorization not established; the instance's other limitations (an input pinned by size and time only) are info lines. A failure under an earlier approval instance stays named in the info line about other instances, with its command and exit.

`--require-reportable` (on `report` and `write`) exits 3 and names each dimension that is not established, on stderr, when the run is not qualified. Without it nothing changes: the exit code and the three status names are as before, so ordinary `report` stays useful during development. `write` saves the record first and exits 3 afterwards, so a failed or gapped run is recorded as it is; saving provenance does not change its status. `status` reads the saved report back into a `Reportable` column (`qualified`, `not qualified`, `not recorded` for an older bundle).

## Rerun evidence

When the plan table names an entry point (a `run.sh` or a Snakefile), the report keeps three facts apart and never launches a run:

- **entry point declared**: the plan names it.
- **rerun attempted**: a matched run of it that began after verify saved the outputs table (`provenance/outputs-<hash>.tsv`). A run before the first `write` is the original run, not a rerun.
- **rerun reproduced specified artifacts**: the rerun exited 0, its attempt saw every output named with a saved SHA256 created or rewritten, and each file's content hash now equals the hash saved before the attempt. Anything less is "reproduction not established" with the reason. A table written after the rerun cannot show reproduction, and a re-saved table loses the earlier baseline.

Whether a frozen entry point can be rerun without the agent is the researcher's to try. Verify only reads what a rerun left behind.

## What it writes

After you confirm, `verify` writes `<analysis>/provenance/`:

- the frozen plan;
- its receipts (ones that only passed a planned path to other code are kept, marked `not_a_run`);
- an outputs table with each file's size, full sha256, the run named (only when its producer is `supported`), and the evidence behind it: `producer_attempt`, `evidence_method`, `strength` and the approval instance checked (`legacy` for an approval with no instance). A table without those last four columns is from an older verify, when the producer was chosen by time alone: read it as legacy. The receipts file keeps each run's `attempt_id`, `launch_match` and `approval_instance`;
- when the plan has a validation binding, `validation-<hash>.json` (the frozen binding, each check's outcome and the raw evidence's path and sha256);
- the scilintr output and waivers (`lint-<hash>.txt`);
- the package list of any conda env a run used that no `conda-lock.yml` pins (`env-<hash>.txt`, read from the env's `conda-meta`; an env changed since the run is a gap);
- the pip packages in such an env that conda did not install, locked or not (`pip-<hash>.txt`, in requirements format);
- the report, and a `PROVENANCE.md` index.

Commit it with the analysis. It never writes `PLAN.md`, `TRACKER.md`, or `specification.md`, so the analysis keeps one plan file. It then names the review command, `/mycelium:review <folder> — check the code against the approved plan in <folder>/provenance/plan-<hash>.md`.

## Plan differences

`verify diff <old> <new>` compares two plans whole, with whitespace collapsed and nothing shortened, so a change after a long shared prefix is still seen. It lists a changed objective; changed, added and removed table rows (keyed by the ID column: `#`, `id`, `no`, `no.`, else the first); dropped columns; a changed row order; changed `Inputs:` and `Outputs:` lines; the raw `<!-- validation-bindings -->` and `<!-- exact-execution -->` blocks, compared as text and not interpreted; and the runs the plan table allows. Rows whose ID is duplicated or missing are "cannot compare". The result is exact equality of what the plans say, not a judgement that the science is unchanged, and a formatting-only edit reports no change.

## Stale plans

`verify stale` sweeps every verified plan. It lists the ones whose scripts, pinned inputs, or outputs changed since their provenance was written. For each, it gives a ready `rg` command that finds the findings resting on it in `.living/findings/`, by session ID or plan hash.

After a planned run in a Mycelium repository, the gate suggests writing the finding's Evidence Ledger Run/Session cell as `<session-id>; plan <hash>`, and ending its Result cell with `[agent-derived: <output path>]`. Mycelium reads only the ledger's date cell.

`verify stale` reads only committed provenance, so it works without the gate on any clone. By default outputs are compared by size and time, and the result says `metadata checked`: a same-size file with its old modification time looks unchanged. `verify stale --content` instead hashes each output and compares it with the SHA256 verify saved (in `outputs-<hash>.tsv`), so such a change is caught and a file merely touched is not reported. A file with no saved SHA256, or one the `--hash-mb` or `--seconds` budget did not reach, is `content not checked` and keeps the size and time check; the summary counts both. A notebook output is hashed as the raw file (its executed results), not as its code cells, which are the right identity for the code that ran. Bundles written before this change recorded a notebook's code-cell hash, so those entries can read as changed until the next `write`.

## Overview of all plans

`verify status` is an on-request overview, with one row per approved or verified plan. Each row shows:

- its analysis folder, runs, verify status, and staleness (size and time only; use `stale --content` for content);
- whether the saved report was `qualified` for reporting (the `Reportable` column);
- the lint verify recorded (a missing or unreadable linter shows as a gap, never `clean`);
- the folder's `ANALYSIS_MANIFEST.md` entry: `listed: <first status word>`, `listed`, or `not listed`. It reads Mycelium's YAML `status:`, `**Status**:` lines, and a table's Status cell.
- with `max_runs_per_approval` set in `gate.json`, whether a plan has reached it: the run count then reads `N (limit L reached (M since approval))`.

No hook runs it.

One limit: only a run the gate saw from Pre to Post, with the output named by file or one-level glob, can be observed writing it; any other output is tied to a run by time alone and stays a gap.

## Runs and citations

`verify runs [RESULTS_DIR]` lists the `run_<YYYYMMDD>_<slug>` folders of a results folder with the status each run's label (`RUN.txt`, or a sibling `<run>.RUN.txt` for a frozen run) gives it, plus `updated` (newest file inside) and a content `id`. It also lists gaps in the labels and, in a Citations section, the `data/` and `code/` symlinks that cite a run of another analysis, with that run's status. It never writes, never sets a status, and only suggests a supersession; it is not part of `verify check` or `status`.

## Recoverable provenance publication

`write` serializes writers per analysis and stages a complete bundle beside the public files. It retains the previous bytes in `provenance/.transactions/`, writes a pending transaction before replacing members, writes `complete-<hash>.json` with member SHA256s, and updates `PROVENANCE.md` last. Keep these internal transaction files until the save and any recovery have been reviewed. Public plan/receipt/output/lint/report filenames are unchanged.

Under the same lock, the next `write` finalizes a fully matching publication or restores the previous snapshot before saving again. An unexpected edit or damaged backup stops recovery and retains evidence. Do not remove a pending marker to make a report look complete. `report`, `stale`, and `status` distinguish complete, legacy (no checksummed record), and interrupted/damaged bundles. Legacy files are read without automatic rewriting; the next confirmed save retains their prior bytes.

Timestamp-compatible outputs with competing writers, and outputs with an overlapping attempt, remain attribution gaps. A Slurm job is judged by its state and its exit code: `COMPLETED` with an `ExitCode` other than `0:0` blocks, an unreadable code is a gap, and a pending, running, unknown or partly finished array job is a gap. A metadata-only input or script fingerprint does not verify content. Shell/wrapper and notebook-tool visibility remains bounded by the recorded receipts.
