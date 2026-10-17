# Approval gate

[Choose a usage tier](usage.md)

**On this page:** [Approving a plan](#approving-a-plan) · [What is gated](#what-is-gated) · [Pinned inputs](#pinned-inputs) · [Pinned scripts](#pinned-scripts) · [Validation bindings](#validation-bindings) · [Exact execution](#exact-execution) · [Review consent](#review-consent) · [Run receipts](#run-receipts) · [Mycelium's post-action protocol](#myceliums-post-action-protocol) · [Exploratory runs](#exploratory-runs) · [Lint on write](#lint-on-write) · [Command hints](#command-hints) · [Settings](#settings) · [Limits](#limits)

A plan is useful only if the run still follows it. The approval gate checks covered analysis commands before execution, so an agent cannot start a new run just because a previous conversation discussed it. You decide what is approved, and the gate keeps a record of the runs that follow.

For example, a plan might cover `analysis/response/02_model.R` using a particular sample table. Approving it allows that run for the configured window. If a pinned sample table changes, the gate asks for a checked, revised plan before the covered run proceeds.

The gate works through Claude Code and Codex hooks. Turn it on for a repository with `/mycelium-extra:init` (Claude Code) or `$mycelium-extra:init` (Codex). To configure it by hand:

1. Create `.mycelium-extra/gate.json`. `{}` uses the defaults.
2. Add `.mycelium-extra/` to `.gitignore`. It holds short-lived execution state, not project knowledge.

`init` checks whether the default paths exist and asks which folders to gate if they don't. It never changes a gate that is already on; after that, edit `gate.json` by hand.

## Approving a plan

When a reply ends with `Plan status: READY` or `READY_WITH_ASSUMPTIONS`, the Stop hook hashes the plan and shows `approve plan <hash>`. The notice is a card you can check the science on. For a plan whose table has a Step column and a Choice or Validation column, it shows:

- what is new since the newest earlier approval that covers or writes the same paths, of any age: scripts as `SAME`, `CHANGED` or `NEW` by fingerprint (from the plan's pins, else the receipts of its runs; `NEW` means that plan recorded nothing for the script), inputs the same way (with any removed input), and whether the objective and each step row are exactly the same, compared cell by cell before anything is shortened for display: rows added, changed or removed, steps reordered, outputs and the runs allowed added or removed, and any `validation-bindings` or `exact-execution` comment block changed, all by comparing text. It reports equality or difference of what the plan declares, never that the science is unchanged, and rows whose ID (or, without an ID column, step text) repeats are reported as "cannot compare"; with no such plan the card says "no baseline" and why, never an empty "nothing changed";
- the question (verbatim, or "none in the plan"), the goal from the plan's Objective, the `default:` steps to confirm, and the Facts count line;
- a top-down `Sequence`: each step as `↓ 2 fit.R*` (the program and file name, no directories; `*` where a default decided; "agent says: done" for a step the agent marks `(done)`, since the hook does not verify it), with bullets under it: `choice` and who decided it (`[you]`, `[repo: ...]`), `assumed` (the reason, for a `default:` step), and the `check`, quoted from the table; beyond 15 steps the rest are left to the plan above;
- a `lint` bullet under each step that names code (`.py`, `.R`, `.ipynb`, `.qmd`, `.Rmd`) that exists: `clean`, `2 open (R002, R011)`, or `not checked (...)`. It is scilintr's verdict from the same run `verify` does, shown on the card only; it never blocks approval, and `verify` still blocks on a finding left unfixed or unwaived. The digest card shows it only when something is open or unchecked. Set `"card_lint": false` in `gate.json` to leave it off, or record the linters' paths with `gate_init.py --tools` (see [Verification](verification.md)); each language's linter gets 8 s here, and the Stop hook's timeout is 30 s;
- the Evidence bullets that name a failure or a flag;
- `CAN RUN (in full)`: every gated script, folder (everything gated below it) and command (any invocation) the plan table lets through, never collapsed, with a shared path prefix written once as `P`. The heading says `broad grant: any arguments`: a path or command in the table lets a run through whatever arguments it has. A plan that declares an [exact-execution](#exact-execution) block adds one `exact: row N: <argv>` line per frozen step, and the heading then reads `exact where listed below, otherwise broad grant: any arguments`;
- one line per declared [validation binding](#validation-bindings), when the plan has the block: check id, plan row, `required`, `declared by` whom, how many test files were pinned, and whether the check's command is gated and named in the table. A block that does not pass is shown as errors instead of a card, and the plan cannot be approved until it is fixed;
- what it reads (pinned inputs) and writes, and any script the plan mentions only in prose, which approves nothing.

When that card would run past 35 lines, it shows a digest instead: the same Sequence with the first sentence of each choice, and the `assumed` and `check` bullets only for steps a default decided, Reads and Writes as counts, and no diff. The baseline, the changed-script warning, flagged Evidence, `CAN RUN (in full)` and a `Shorthand, not read` line (an `Outputs:` word starting with `…` names no path) stay as on the full card. Type `card <hash> checks`, `card <hash> diff` or `card <hash> full` to see the rest; the hook answers that prompt itself, so the agent never sees it. (Checked in Claude Code's hook contract; whether Codex shows a blocked prompt's reason is not yet verified.) On both cards, an interpreter's absolute path in a step shows as its program name, and a path inside the project as its root-relative form.

No card line is longer than 250 characters, except a `CAN RUN` grant and a script-diff line, which are never cut.

Text quoted from the plan has control characters, markup and the phrase "approve plan" removed. The card shows what the gate allows; it does not check the choices or the checks. Any other plan keeps the older card: runs allowed, inputs, scripts, outputs. Type exactly that (a trailing `.` is fine) to record the approval in `.mycelium-extra/approvals/`. A bare `approve plan` lists pending hashes and approves nothing. The text is saved when the plan is shown, but the hash can be approved only once its pins and card are prepared; if preparation was interrupted the hash is listed as `(preparing)`, approval is refused, and showing the plan again prepares it. A pending plan saved by 0.9.44 to 0.9.70 has no such field and counts as prepared only if it holds its `scripts` record, which those versions wrote last; an older one stays approvable.

Execution grants are restricted to the approving session. Approvals without a recorded session remain readable historical evidence, but require a new card and approval before execution. Approve in the same session that presented the plan. If you move to a new session, present the plan there first; a pending hash from another session does not grant approval. When the context fills up while a plan waits, `/mycelium-extra:handoff` points `HANDOFF.md` at the plan's stored text, and the new session prints it unchanged. Approve the hash on the new card: it matches the old one when the text is unchanged.

### Approval instances

Approving writes an immutable record, `.mycelium-extra/approval-instances/<hash>/<instance_id>.json` (schema `mycelium-extra.approval-instance.v1`): the plan's full sha256, the pins and script pins, whether preparation finished (`prepared`: `complete`, or `legacy-no-ready` for a pending entry from before the `ready` field), and a list of `limitations` (a legacy preparation, inputs pinned only by size and time, a folder pinned by listing). When the plan has them, the instance also holds `validation` and `execution` (the checked blocks, with each check's pinned files and definition hash), and the approval file carries the same two keys; a plan without the blocks writes neither, so its instance id is unchanged. `approvals/<hash>.json` stays the file the gate reads and gains `instance_id`. The id hashes the frozen content, not the time or session, so approving the same freeze again reuses the same instance, and approving the same prose with different pins writes a second instance and keeps the first. A launch records the instance it ran under, so a run that started before a reapproval keeps naming the older freeze. Approvals without `instance_id` are legacy: one implicit instance, history before it unknown.

## What is gated

Before each shell call (both hosts expose it to hooks as `Bash`), the gate denies a gated run unless an approval from the last `approval_hours` (default 24) names it. Approvals are never deleted, so `verify` can check old plans. If reading them takes longer than 5 s, the gate blocks the run and says why instead of letting it through unchecked. Two kinds of run are gated:

- Scripts under `gated_paths` (default `analysis/**`, `nbs/**`). This covers running them by interpreter, directly, via stdin (`python3 - < analysis/x.py`), `-c "$(cat …)"`, `-m`, after `cd`, or under `conda run`, `uv run`, `env`, `srun`, `timeout`, and similar wrappers, including their option values (`conda run -p DIR`, `uv run --project DIR`, `env -C DIR`), which also move the folder a following `bash -c`, `env -S` or `sbatch --wrap` payload runs in. `$PWD` and `$HOME` in such a value are resolved; any other expansion (`$X`, `$(...)`, backticks) cannot be, so a script in that command is checked against the plan both relative to the current folder and to the project root, and is denied unless a plan covers one of them (write a literal path instead); a command that runs no script stays allowed. A wrapper named by path (`/usr/bin/env`, `~/miniforge3/bin/conda run`) is read like the bare name. The plan table must name the script's path, or an enclosing folder at least two levels deep (`nbs/cytof_exvivo/`), as a path token. Write it relative to the project root: an absolute path inside the project counts as its root-relative form, and one outside the project approves nothing.
- Commands in `gated_commands` (default `sbatch`, `snakemake`, `nextflow`). The plan table must contain the command word. Payloads of `bash -c` and `sbatch --wrap` are checked as commands too; an `sbatch --wrap` that runs a gated script needs one approved plan that names both `sbatch` and the script, as its receipt does.

A dry run (`snakemake -n`, `bash run.sh -n`) is gated like any run: a Snakefile is Python, and Snakemake runs its top-level code and input functions while building the job list.

Only the plan table's Step column counts. A path or command word in a Choice, Validation or Source cell, the brief's prose, its Evidence, or a `repo:` citation approves nothing, so a plan that cites a script as evidence does not approve running it. A plan with no table approves nothing, and the approval notice says so. A table whose header has no Step column (or no header) grants from every cell but Source, as before 0.9.57. The card lists scripts named outside the Step column as "not authorised". `verify` still reads every cell but Source when it asks what a plan named, so its record of older plans is unchanged.

Reading gated files (`cat`, `rg`, `git`) is never gated.

An existing script path containing spaces can be quoted or backticked in the
Step cell. Its complete path is granted and pinned; its fragments grant nothing.

A malformed approval record or first-run script-pin ledger blocks covered runs
with an invalid-state notice. Restore the record or move the damaged approval
aside and present the plan again; a damaged record never supplies authorization.
This differs from an internal gate error governed by `on_error`.

## Pinned inputs

An approval refers to the inputs you checked, as well as the steps you intend to run. Pinning connects the plan to those files so a changed sample table or configuration does not silently inherit the old approval.

A grill brief has an `Inputs:` line naming, by repository path, the files the plan rests on: the sample table, config or params files, a lockfile, or a folder of raw files. When the Stop hook shows `approve plan <hash>`, it also fingerprints those files and lists them.

Paths are read as written, never evaluated: a path in backticks or single or double quotes may hold spaces, apostrophes and commas, and a plain path is read as before. An entry the gate cannot read as one literal path (a `$VAR` or `$(command)`, a glob or brace pattern, a quote left open, a quoted list, or an `Outputs:` brace expansion cut at 200 paths) is not pinned and not read as pieces; the card names it on an `Inputs not read` or `Outputs not read` line, so name each file instead (in quotes if its name has a space).

- A file gets a sha256 while the per-hook budget lasts: `pin_hash_mb` bytes (default 200) and `pin_seconds` seconds (default 5) in `gate.json`. After that it gets size and mtime.
- A folder gets a fingerprint of its file names, sizes, and mtimes, up to 5,000 files. Contents are not read. A folder the time limit cuts off is named as not pinned.
- If the time limit cuts off the check before a run, the run goes ahead and the gate names the inputs it did not re-check.
- A path outside the repository is named in the notice and not pinned. Symlinks inside the repository are followed.
- Showing the same plan again re-pins it, and the notice names any file that changed since the plan was last shown.
- A plan with no `Inputs:` line pins nothing, and the notice says so.

Approving copies the pins into the approval. Before a covered run, the gate fingerprints the pins of the newest approval that covers it. An older plan that pinned less therefore cannot let a run through after a newer plan's pins changed. The gate blocks the run if one changed, naming the file with its old and new fingerprint. Re-check the input (for example, re-run the data-contract check), show the plan again, and approve it. Explore runs skip this check.

## Run limit

One approval can cover many runs of the same scripts, and after enough re-runs the plan you approved may no longer describe what runs. Set `"max_runs_per_approval": 3` (any whole number of 1 or more) in `gate.json`, and the fourth gated run is denied with the number of runs so far and what differs from the first of them: the commit, uncommitted changes, and each script's content (shown even with `pin_scripts` off). Present the plan again; `approve plan <hash>` restarts the count.

- The count comes from the run receipts since the approval, so it matches `verify`: explore runs do not count, a `command -v` lookup is not a run, a failed run is, and a denied run leaves no receipt. A run is counted when its receipt arrives, so runs still in flight, or two runs in one command, can overshoot by that many. A Slurm job counts when it is submitted.
- The approval file is not changed. `verify list` and `verify status` show `(limit N reached (M since approval))` next to the run count, derived from the same receipts.
- An invalid value is ignored with a notice. Unset means no limit and no change in behaviour.

## Approval latency and comprehension checkpoint

Every `approve plan <hash>` appends one line to `.mycelium-extra/approvals.jsonl`: the hash, session, when the plan was shown and approved (`shown_ts`, `approved_ts`), the seconds between them (`latency_s`), the number of step rows in the plan table (`plan_rows`) and its length in characters (`plan_chars`). It is a log for you to read later: it is never shown in a notice, on the card or by `verify`, it never blocks or slows an approval, a failed write does not stop the approval, and the approval file is unchanged. A plan shown again restarts the clock.

Set `"checkpoint_steps": 8` (a whole number of 1 or more) in `gate.json` and a plan table with more than 8 step rows is not approved at the first `approve plan <hash>`. The reply asks one question made from the table, not by a model: which step number makes a quoted Choice (the row is picked from the hash, so asking again gives the same question). Answer with `approve plan <hash> <number>`. A wrong number shows that row (step, Choice, Source) and asks again; nothing is denied and the pending plan does not change. A right number approves as usual. A plan without Choice cells is asked which step names its first script or path; a plan with neither is approved without a question. Re-approving an unchanged plan asks again. The log line then carries `checkpoint` with `asked`, `passed` and `wrong_attempts`.

- Unset or `0` is off, and then `approve plan <hash> <number>` is not an approval, as before. An invalid value is ignored with a notice.

## Pinned scripts

An approval also refers to the code you approved. A script that changes after approval cannot run until you re-approve it, so an agent cannot edit an approved script and re-run it unseen.

- When a plan is shown, the gate fingerprints each existing script (`.py`, `.R`, `.sh`, `.ipynb`, `Snakefile`, and similar) that the plan table names, up to 500. The card lists them under "Scripts pinned".
- Any other script the plan covers, such as one under a folder it names or one that did not exist then (analyze writes code after plan approval), is pinned at its first covered run. The first version is not blocked; edits after it are, and showing the plan again lists them on the card.
- Before a covered run, the gate compares the script it runs with the pin of the newest covering approval. A difference blocks the run, naming the script, both hashes, and the lines added and removed.
- Present the plan again to review it. The card then shows "Scripts changed since last approved" near the top, and up to 30 lines of the diff under "Diff of changed scripts" just above the `approve plan` line (the grants and the question stay on screen first), and `approve plan <hash>` pins the new version. Approving the same plan again re-baselines its first-run pins.
- The gate keeps a copy of each pinned script up to 256 KB in `.mycelium-extra/scripts/` to show the diff. A larger script is pinned and its change shows hashes only.
- Any byte change counts, including whitespace and comments. For a notebook only the code cells count, since running it rewrites its outputs. Explore runs skip the check, like input pins.
- Turn it off with `"pin_scripts": false` in `gate.json`.

Only the script a command runs is checked. A file it sources or imports, and the scripts a Snakefile rule runs, are not; list them on the plan's `Inputs:` line to pin them (a run plan from grill freezes the code that way).

## Validation bindings

An optional comment block in the plan text names the acceptance checks the researcher approves, so that a result can later be tied to the check that produced it and a changed expectation cannot keep the authority of the approved one:

```text
<!-- validation-bindings {"version": 1, "checks": [
  {"id": "V1", "plan_row": "3", "required": true, "defined_by": "researcher-approved",
   "test_paths": ["analysis/x/tests/expected_rows.tsv"],
   "invocation": ["python", "analysis/x/tests/check_rows.py"],
   "evidence_path": "analysis/x/outputs/check_rows.json"}]} -->
```

The block is optional; a plan without it is approved and run as before. The gate reads it in the Stop hook, before the plan can become ready:

- Every field except `required` (default `true`) must be present, and unknown keys, an unknown `version`, duplicate ids, a `plan_row` that is not a row of the plan table (or repeats there), an unsafe path (absolute outside the repository, `..` escaping it, a symlink out, `~`, a `$` substitution, the gate's own state folder), a `test_paths` file that does not exist, and malformed JSON are errors. The card then lists the errors and the plan is not approvable: `approve plan <hash>` replies that nothing was approved and to fix the block. Showing the corrected plan (a new hash) prepares it again.
- `test_paths` are the files that define the check: the test, its fixtures and its expected values. Each is pinned by sha256 in the prepared plan, the approval record and the approval instance (`validation`: per check its fields, `files` `{path: sha256}` and a `definition_sha256` over them), so approving the plan freezes the expectation, not just the check's name. `invocation` is the command (an argv list, or a string split like a shell would) that runs it, from the repository root. `evidence_path` is where the run writes its result; it must be a safe path but need not exist yet, and it is never pinned, since the check rewrites it.
- `defined_by` (`agent-proposed`, `researcher-approved` or `independent`) is recorded and shown as "declared by"; the gate cannot verify who wrote the check.
- While an approval with bindings covers a run, the gate denies the run when any pinned file has changed or is missing, naming the check and the file. A changed expectation invalidates the old acceptance evidence: the plan must be shown and approved again, which pins the new bytes. Editing any other file, or the evidence file, changes nothing.
- A launch whose command equals a check's `invocation` (same argv, run from the repository root) records `validation_check` with the check id in its launch entry and receipt, so `verify` can tie a result to the check that produced it. The gate does not run the check, and a pass file that merely exists proves nothing.

The check's command has to be seen by the gate to be recorded. A test under `tests/` is outside the default gated paths (`analysis/**`, `nbs/**`), so a run of it is not gated, has no launch record and no `validation_check`. Either keep the test under a gated path (for example `analysis/x/tests/`), where the plan table must also name it, or add its folder to `gated_paths` in `gate.json` yourself; the gate never widens its own scope. The card says which case applies to each check: `not gated`, `gated but not named in the plan table`, or `gated, named in the plan table`.

## Exact execution

By default a path or command in the plan table is a broad grant: any arguments pass. For a reportable step that is too loose, since a changed `--model`, contrast or threshold is a different computation under the same approval. An optional block freezes the command of chosen steps:

```text
<!-- exact-execution {"version": 1, "steps": [
  {"row": "2", "argv": ["python", "analysis/x/fit.py", "--model", "mixed", "--threads", "4"],
   "cwd": ".", "env": {}, "operational": ["--threads"]}]} -->
```

- `row` is a row of the plan table, `argv` the command from the program on (wrappers such as `conda run`, `srun` or `timeout` and leading `VAR=value` words are not part of it), `cwd` the repository-relative folder (default `.`), `env` the inline variables it may carry, `operational` the flags that may differ. A `$` or backtick in `argv`, an unknown key or version, an unknown row and an unsafe path are errors, as for bindings. The block narrows a grant and never widens one: the step's script must still be named in the table.
- A step is about a run when its argv names a script the run launches (or, for a gated command such as `snakemake`, its program). Such a run must equal a declared argv in the declared folder: same program name, same arguments in the same order (`./` ignored), except the operational flags, whose value may differ and which may be added or removed. `> file` redirections are ignored; `< file` is not. Otherwise the run is denied with the declared and the actual command.
- A flag listed as operational is read as taking a separate value only when the step writes it with one (`--threads 4`) or with `=`; to add one the step does not show, write `--flag=value`, so that a boolean flag cannot swallow a positional argument.
- A shell substitution (`$X`, `$(...)`, backticks) in the launched command, or a folder that is an unresolved expansion (`env -C "$WORK"`), cannot satisfy an exact step and is denied. Inline variables must be declared in `env` with the same value; variables set elsewhere in the shell are not visible to the gate.
- The three kinds of change are different actions. An **operational retry** (cores, memory, queue, a log path) may differ only in the listed flags and needs nothing. A **frozen-code re-freeze** (the script changed) is the existing pinned-script path: the plan is shown and approved again. A **changed analytical argument or intent** (another model, filter, contrast, threshold, seed or input) goes back to the researcher, who approves a revised plan.
- A run no step is about keeps its broad grant (`exact_match: false` in its launch entry and receipt). A run held to a step records `exact_match: true` and `exact_step` (the row). A mismatch is denied, so no launch entry exists for it.

The match is on the launched words, not on what the script does with them: it does not read a params file named in the arguments (pin it under `Inputs:`), and it cannot see wrappers' own options (`command_env` records a `conda run` environment). It is a freeze of the command line for the runs the gate can see, not of the science.

## Review consent

`review_packet.py` (see [plan-review](../skills/plan-review/SKILL.md)) prepares an immutable review packet and, before anything is sent, checks that the user consented to exactly those bytes. Only the gate writes that consent: when the user's prompt is exactly `send packet <12 to 64 hex characters of the digest>` (case and surrounding whitespace ignored; nothing before, after or around it), the prompt hook finds the one prepared packet folder under `.mycelium-extra/review-packets/` whose digest starts with that prefix and which has its manifest, writes `.mycelium-extra/review-consent/<digest>.json` (schema `mycelium-extra.review-consent.v1`: `digest`, `session_id`, `ts` and the literal `prompt`), and answers with the digest and the next step, `review_packet.py verify`. An ambiguous prefix, an unknown digest or a prompt embedded in longer text records nothing (the first two answer why; the last is an ordinary prompt). An agent cannot make the user type it, and `review_packet.py` never writes consent. This is a cooperative control, not a sandbox: an agent with unrestricted shell access can still send other bytes.

## Run receipts

Receipts provide the execution record that `verify` reads later. After a covered shell call completes and its post hook fires, the gate appends one line per run to `.mycelium-extra/receipts.jsonl` (schema `mycelium-extra.receipt.v1`). A receipt holds:

- The approved plans that cover the run and their pins, or none. `pins_checked` is false for explore runs, which skip the pin check. The plans are the ones that allowed the launch: the pre-run hook saves them under `.mycelium-extra/launches/` (removed when the call reports back), so an approval that expires or is replaced during the call is still credited. Each run's record is keyed by its command text and paths, so the same text run in two folders of one call is credited to its own plan. A call with no such record is credited from the approvals active when it reports back: the plans are then context only. `launch_match` says how the receipt was tied to its launch: `matched` when this call's launch record names the run, otherwise `unmatched` (for example a post hook with no pre hook). `pins_checked` is true only for `matched` receipts, so a plan that merely covers an unmatched run never counts as a checked launch. A receipt without `launch_match` predates this field: its launch link was not recorded. A call with no call id is matched by session and command; a second identical launch while the first is still unreported makes that key `ambiguous`: both attempts are stored, each Post is `ambiguous` with `attempt_candidates`, and none counts as a checked launch (the gate never guesses). A second Post for a call id that already reported is `unmatched` with a `launch_note` saying so. Each launch record carries `attempt_id` (random), `call_id`, `started` and `cwd`, and each matched receipt repeats `attempt_id` and `call_id`; a record not taken within 24 h moves to `.mycelium-extra/launches/abandoned/` as an incomplete attempt instead of being deleted. Launch records and receipts without these fields are legacy and are never read as matched.
- Output observation. At launch the gate records, for the credited plan's declared `Outputs:`, each literal path and each one-level glob match (at most 200 files; `**` patterns and directory trees are never scanned) as `outputs_before` `{path: [size, mtime_ns]}` in the launch entry (`null` for a path that does not exist yet). The receipt then carries `outputs_observation` and, when observed, `outputs_changed` `{created, changed, deleted}` (a changed size or mtime counts as changed; an untouched file is not listed). `outputs_observation` is `observed`, or `skipped: <reason>`: no declared outputs, cap reached, a `**` pattern, an unmatched or ambiguous launch, a compound shell call, or a job submission (the job writes after the call returns). A change between launch and report is an observation, not proof that this run wrote the file: a concurrent writer is indistinguishable.
- `validation_check`, `exact_match`, `exact_step`, when the launch recorded them: the id of the [validation binding](#validation-bindings) whose invocation this command is, and whether an [exact-execution](#exact-execution) step held it (`true` with the matched row, `false` when no step was about it; absent when the plan has no block).
- `approval_instance`: the id of the approval instance the credited plan had when the run launched (see below), `null` for an approval from before instances.
- `limitations`, when present: a run allowed although its folder could not be resolved (a wrapper option such as `env -C "$X"`) carries `cwd unresolved: <expression>`, in its launch entry and its receipt, and the post message adds one coverage line. The run was matched by reading the folder as the outer folder or the repo root.
- Git HEAD, whether tracked files have uncommitted changes, and whether each recorded file is committed, modified, untracked, or ignored.
- The script's fingerprint (or the sha256 of an `sbatch --wrap` payload), and its `module load`, `conda activate`, and `#SBATCH` lines.
- Lockfiles (`renv.lock`, `pixi.lock`, `environment.yml`, and similar) in the repository root, the working directory, and the script's folder.
- The environment the hook itself runs in (`hook_env`), and any `conda run -n` environment in the command (`command_env`).
- For `sbatch`, the job ID. For snakemake and nextflow, the Snakefile or pipeline, config and params fingerprints, report and trace paths, the nextflow run name, and a pointer to the engine's own record (`.snakemake/metadata`, `.nextflow/history`).
- The exit status and where it came from (`exit_source`), and the key names of the Bash result (`response_keys`). The hook is registered for both `PostToolUse` and `PostToolUseFailure` (matcher Bash). Claude Code fires `PostToolUse` only after a command succeeds, so that receipt records 0 with `exit_source` `event`; a command started with `run_in_background` has only started, so it is `unknown` (`background`). A failed command fires `PostToolUseFailure`: the receipt records N from the error's first line `Exit code N` (`exit_source` `error`), `failed` when there is no such line (the shell did not start, or a timeout), or `interrupted`. An exit code in the tool result itself always wins (`exit_source` `response`). Only the error's first line is kept (`error_line`, at most 200 characters), never the command's output. A payload without an event name is `unknown`.
- For `sbatch --wrap`, the payload's scripts resolved against `-D`/`--chdir` (`paths`), and that folder (`job_cwd`).

Receipts stay in `.mycelium-extra/`, which is gitignored, so they do not trip Mycelium's Stop hook. `verify` copies a plan's receipts into the analysis folder after you confirm.

For a compound shell call (`a.py; b.py`, `a.py && b.py`, or a compound shell
wrapper), the shell's exit status does not establish whether each step ran or
succeeded. Receipts keep `command_exit_status` and `command_exit_source`, mark
individual outcomes unknown, and leave scheduler output unattributed. Verification
reports those unknown outcomes as gaps and a failed aggregate command as a block.
Run steps in separate shell calls when each needs its own attributable receipt.

Codex uses its own post hook and marks receipts with `host: codex`. In CLI 0.160.0, the hook provides command output without exit metadata. Its receipt therefore records `unknown`, and verification reports a gap. The gate never treats a line printed by the command as proof of its exit status.

## Mycelium's post-action protocol

Mycelium's own hooks detect only python, R, and jupyter runs. In a repository with `.living/`, a receipted run can be one Mycelium does not detect: `bash run.sh`, snakemake, sbatch, nextflow, and other runners. After such a run, the receipt hook tells the agent once that the protocol did not fire. It asks the agent to follow it (learnings, decisions, findings, manifest, analysis doc) when the run finishes. It is a reminder; Mycelium's Stop hook still does not see these runs.

## Exploratory runs

Sometimes you need a quick experiment before you can write the final plan. Exploration gives you that space while keeping the experiment distinct from the runs you will report.

Type `allow explore` to let runs prefixed with `MYCELIUM_EXTRA_EXPLORE=1` through for this session; type `stop explore` to end it. Without the grant the prefix is denied, so the agent cannot exempt itself. Each explore run is logged, and the Stop hook lists those runs as not reportable. To make them reportable, say "promote explore runs": grill lists this session's explore runs (`verify explore`, prefix removed, scripts edited since flagged) and drafts a normal plan that re-runs them, for the usual approval. Explore outputs are never promoted to results. After each one, the receipt hook tells the agent the run is not reportable, so a learning or finding it records from the run (for example under Mycelium's post-action protocol) is labeled `Exploratory run (not reportable)`. Output files carry no label.

## Lint on write

Mycelium's `analyze` skill tells the agent to run scilintr after every code write. That is an instruction, and nothing checks that it was followed. With a gate on, a PostToolUse hook on `Write`, `Edit`, `MultiEdit` and `NotebookEdit` (Claude Code) and `apply_patch` (Codex) does it for the agent.

- It lints the files just written (up to five per patch), if they are under `gated_paths` and are code (`.py`, `.R`, `.ipynb`, `.qmd`, `.Rmd`), with the linters `init --tools` recorded. Each subprocess has an 8 s limit; both languages and their waiver checks share a 16 s subprocess budget under the 20 s hook limit. Files beyond the five-file limit are reported as unchecked. One call covers a whole patch; R may also report cross-file rules among those files. The plan card and `verify` check the wider analysis.
- Open findings go to the agent as context, once per change: the same findings after the next edit are not repeated, and they return if they were fixed and then reappear. Waived findings are not listed; an R waiver with no reason is. Finding text is stripped of control characters and cut at 240 characters.
- It never blocks. When scilintr could not check something (not installed, timed out, unreadable output, an internal lint error, or a script that does not parse under the hook's Python, which on some clusters is older than the linter's), the agent is told once per session that this is not a clean result, and the file's earlier findings are kept. `verify` reports the same as a gap.
- Each script's findings are kept in its own file under `.mycelium-extra/pending/`, so parallel writes to different scripts do not overwrite each other. Unchecked notices use separate markers so simultaneous writes report the same gap once.
- When a turn ends, you see one line naming the scripts written this session that still have open findings, once per change. The agent does not see it. A script edited after its lint (for example by `sed` through Bash) is left out, because nothing is known about it.

- **Before a run (opt-in).** `"lint_before_run": "warn"` tells you and the agent, when a gated run starts, that a script it uses still has the findings lint-on-write recorded; `"block"` denies the run until they are fixed or waived. It applies to explore runs too. It reads the records of any session and adds no lint run. A script the hook never linted, or edited since its lint (for example by `sed` through Bash), is unknown and not listed, so this narrows `verify`, never replaces it. Any other value is ignored with a notice.

- **Before the turn ends (opt-in).** `"lint_before_stop": true` blocks the Stop once per change when scripts the agent wrote this session still have open findings, with the findings as the reason, so the agent can fix or waive them in the same turn. The host's `stop_hook_active` flag stops it from blocking twice in a row. It needs `lint_on_write`. Without it, only the user-only Stop line above is shown.

`verify` still decides: it blocks on any finding left unfixed and unwaived.

## Command hints

Type `hints on` to get a one-line suggestion of the command to run next; `hints off` stops them. The setting lasts for the repository until you turn it off. Hints need the gate (`init`), since the gate's hooks carry them.

- When you send a prompt that matches a task type, the agent is told which command fits and names it in one line, asking before it switches. Rules, first match wins: wrap up or new session → `handoff`; new analysis folder → `new-analysis`; which decision binds → `decision-status`; sample table → `data-contract-check`; brainstorm → `/mycelium:ideas`; ingest → `/mycelium:ingest`; report or write-up → `/mycelium:report`; review or audit → `/mycelium:review`; analysis words with no active approval → `grill`. The `/mycelium:*` rules apply only where `.living/` exists. Prompts that start with `/` or name `mycelium` get no hint.
- When a turn ends, you alone see these (the agent does not, so they cost no tokens): `verify <hash>` once a gated run under that plan has a receipt this session, and `handoff` once the context passes 120k tokens. Each shows once per session.
- Hints match keywords, so some miss or misfire.

## Settings

`.mycelium-extra/gate.json` takes these keys. A missing key uses its default, and `{}` uses them all. `init` sets only `gated_paths`, `gated_commands`, and `approval_hours`; edit the file by hand for the rest.

| Key | Default | Meaning |
|---|---|---|
| `gated_paths` | `["analysis/**", "nbs/**"]` | Scripts under these globs need an approved plan naming them. |
| `gated_commands` | `["sbatch", "snakemake", "nextflow"]` | Commands that need an approved plan containing the command word. |
| `approval_hours` | `24` | How long an approval covers runs. Approvals are never deleted. |
| `max_runs_per_approval` | unset | A whole number of 1 or more. After that many runs under one approval, the next gated run is denied until you re-approve the plan. See [Run limit](#run-limit). |
| `checkpoint_steps` | unset | A whole number of 1 or more. A plan with more step rows asks one question about its table before approval. See [Approval latency and comprehension checkpoint](#approval-latency-and-comprehension-checkpoint). |
| `pin_hash_mb` | `200` | Bytes of pinned inputs (in MB) hashed per hook before falling back to size and mtime. |
| `pin_seconds` | `5` | Seconds the pin check may take per hook. |
| `card_lint` | `true` | Lint the planned code when a plan is presented and show the result on the card. `false` turns it off. |
| `lint_on_write` | `true` | Lint each gated script as it is written and tell the agent the open findings; the user sees what is left when the turn ends. `false` turns it off. |
| `lint_before_run` | `false` | `"warn"` or `"block"`: before a gated run, tell about or deny a script whose findings lint-on-write recorded and that has not been edited since. See [Lint on write](#lint-on-write). |
| `lint_before_stop` | `false` | `true` blocks the Stop once per change while scripts written this session have open findings. See [Lint on write](#lint-on-write). |
| `pin_scripts` | `true` | Block a run whose script changed since it was approved or first run. `false` turns it off. |
| `on_error` | `"allow"` | What a PreToolUse hook does when the gate itself breaks. `"deny"` blocks every tool call the gate could not check, including when `gate.py` cannot load; any other value is ignored with a notice. |

Two switches are not keys. `hints on` and `hints off` create and remove `.mycelium-extra/hints.json`. `allow explore` and `stop explore` apply to one session.

## Limits

The gate catches execution mistakes; it is not a security boundary or a judgment of scientific validity. Use its record to understand what happened, including what it could not check.

- The gate denies the agent's Write/Edit calls into `.mycelium-extra/` and Codex `apply_patch` targets, including move destinations. For Bash, it checks where a command writes: redirect targets, and the targets of `rm`, `cp`, `mv`, `tee`, `sed -i`, `find -delete`, and similar. A command that only mentions the folder passes, such as a learning about the gate appended to `.living/learnings.md`. An interpreter's code cannot be traced, so a runner is denied when it gets a path in the folder, or when its own code (`-c`, a heredoc, or a script written by a heredoc earlier in the command) names the folder and writes anything. In Python code, the folder counts only in a path string or a shell-command string that writes it; prose and multi-line strings are text being written elsewhere. A variable set to a literal in the same command is expanded before the check.
- Inline code (`python -c`, `Rscript -e`) counts as a gated run when it names a gated script (`.py`, `.R`, ...), or any gated path when it changes `sys.path`, the working directory, or `.libPaths()`. A read-only probe of gated data passes.
- It passes a command by staying silent and never auto-allows, so your own permission prompts still apply.
- On an internal error it fails open and says so, unless `gate.json` sets `"on_error": "deny"`: then every tool call it could not check is denied until the error is fixed or the key is set back to `"allow"`. Each error is appended to `.mycelium-extra/gate-errors.jsonl` when it can be written, with its `event`, `decision`, `host`, `session_id` and `call_id` (each `null` when the event could not be decoded); when the log cannot be written no record is made and the message says so. Only tool calls are blocked; prompt, stop and post hooks report the error and carry on. A `gate.json` that cannot be read cannot opt in, and a host that never runs the hook cannot be controlled by it.
- It catches mistakes; it is not security. An agent set on bypassing it through Bash can do so.
- `defined_by` in a validation binding is the plan's own claim. The gate pins the check's files and notes whether their bytes changed; it does not know who wrote the expectation, run the check or judge the expectation. An exact step freezes the launched command line, not what the script does with it.
- Size-and-mtime and folder fingerprints miss an edit that keeps both (for example `cp -p` or `rsync -t`). The notice says which fingerprint each input got.
- A receipt records the environment a job declares, not the one it resolved. `hook_env` is the host hook's environment, not the job's.
- A job ID records a submission, not its outcome. Check `sacct` or the job log.
- The exit status is inferred from which hook event fired, not read from the command. `verify` reports a nonzero, `failed`, or `interrupted` run as a failure, and an `unknown` status (or an empty one in older receipts) as a gap.
- `verify` credits a script to a Snakemake rule only when the rule runs it: the expanded `shell:` command, or the `script:`/`notebook:` path in the rule's `code` record. A rule input is not a run. The `script:` path is matched against Snakemake's working directory, so a Snakefile in another folder (`-s other/Snakefile`) is not matched, and Snakemake 9 releases that record only `shell:` commands leave a `script:` rule's script with `no receipt`.
- Codex needs enabled/trusted hooks and CLI 0.160.0 or later. Its 0.160.0 post hook omits exit metadata, so run status is `unknown` and verification reports a gap. A hook that never dispatches leaves no receipt. See [Host compatibility](installation.md#host-compatibility).

## Capacity and diary candidate (not yet release qualified)

Capacity remains opt-in. `enabled: false` disables capacity hooks and quota-record writes; approval checks continue independently. SessionStart records recovery state silently. The shipped manifests do not register these hooks: `hooks/capacity-hooks.json` holds the candidate registrations (SessionStart, SubagentStart/Stop, PreCompact and SessionEnd, plus a PreToolUse matcher for all tools so assignment calls cannot create new workers during wind-down or pause) to merge in once native lifecycle qualification passes. SubagentStart is advisory, so enforcement occurs at PreToolUse before assignment.

Below 80% usage is normal; 80–90% permits only finishing the current bounded unit without new assignments. At 90%, or when either reading is unavailable/stale, new work pauses. Only explicit `capacity resume` with fresh readings below 80% clears the pause. Missing initial usage remains unknown; checkpoint, diary, status and shutdown recovery remain available. Claude's existing status-line command is preserved. Its quota percentages and reset timestamps are host supplied ([status-line reference](https://code.claude.com/docs/en/statusline)). Host event contracts are documented by [Claude](https://code.claude.com/docs/en/hooks) and [Codex](https://learn.chatgpt.com/docs/hooks).

Checkpoints retain prior checkout snapshots when the checkout changes. Worker closeout messages are unverified assistant notes, never verified completion. Repeated finalization preserves completed-unit records and edited diary drafts. Corrupt state is retained as a recovery gap. Recovery queries existing process/job state and never relaunches a job. A reviewed diary save is idempotent for the same content.
