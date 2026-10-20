# Approval gate

[Choose a usage tier](usage.md)

**On this page:** [Approving a plan](#approving-a-plan) · [What is gated](#what-is-gated) · [Pinned inputs](#pinned-inputs) · [Optional features](#optional-features) · [Pinned scripts](#pinned-scripts) · [Run receipts](#run-receipts) · [Mycelium's post-action protocol](#myceliums-post-action-protocol) · [Exploratory runs](#exploratory-runs) · [Lint on write](#lint-on-write) · [Command hints](#command-hints) · [Settings](#settings) · [Limits](#limits)

The approval gate checks covered analysis commands before they run, so an agent can't start a new run just because an earlier conversation discussed it. You decide what is approved, and the gate records the runs that follow. It catches execution mistakes and shows gaps. It is not a security boundary. The confirmation steps in the skills (`verify write`, `decision-status`, `harden`, `idea-triage`, `new-analysis`) are instructions to the agent: they ask first, but nothing enforces it.

For example, a plan might cover `analysis/response/02_model.R` using a particular sample table. Approving it allows that run for the configured window. If a pinned sample table changes, the gate asks for a checked, revised plan before the covered run proceeds.

The gate works through Claude Code and Codex hooks, or the OpenCode plugin adapter (qualified on 2.0.32). Turn it on for a repository with `/mycelium-extra:init` (Claude Code or OpenCode) or `$mycelium-extra:init` (Codex). To configure it by hand:

1. Create `.mycelium-extra/gate.json`. `{}` uses the defaults.
2. Add `.mycelium-extra/` to `.gitignore`. It holds short-lived execution state, not project knowledge.

`init` checks whether the default paths exist and asks which folders to gate if they don't. It never changes a gate that is already on, so edit `gate.json` by hand from then on.

## Approving a plan

When a reply ends with `Plan status: READY` or `READY_WITH_ASSUMPTIONS`, the Stop hook hashes the plan and shows `approve plan <hash>`. `approve amendment <hash>` and `approve freeze <hash>` are what the amendment and freeze cards ask for, and each verb works only on its own kind of card: `approve plan` on an amendment or freeze card (or the reverse) approves nothing, and the reply names the verb to use in one sentence. Plain `approve` with a hash works on any card. Plain `approve` (or `approve plan` without a hash) approves only when exactly one card in the session is waiting and it is the one shown last. With none waiting, two or more waiting, or an older card as the one waiting, nothing is approved and the reply lists the pending hashes (marked `(preparing)` or `(invalid block)` where that applies). Only the exact words count: `approve it` or `ok, approve` is an ordinary prompt and gets no reply. The hash may be given without the word "plan" (`approve 1a2b3c4d`), and case and a trailing `.` or `!` are ignored. The notice is a card you can check the science on. For a plan whose table has a Step column and a Choice or Validation column, it shows:

The compact card reads top to bottom as the science first:

- a header with the hash and the number of steps. Directly under it, when a script or input differs from the newest earlier approval, the `Scripts changed since last approved` lines with their size of change;
- `Question`: the question verbatim (or the plan's Objective as `Goal` when the plan has no question; `none in the plan` when it has neither);
- `Choices`: each step's number and its choice (the step's program and file name when the choice is empty; cut at 160 characters), then who decided it: `[you]`, `[repo: ...]`, or `[default: reason]*` where a default decided, and `(agent says: done)` for a step the agent marks `(done)`, since the hook does not verify it. `Defaults to confirm: step N` follows when any default decided. Beyond 15 steps the rest are left to the plan above;
- `Checks`: the plan's checks, joined, each cut at 80 characters (`card <hash> checks` has them whole);
- unless `"card_coverage": false` is set (on by default since the feature shipped as opt-in; see [Other `gate.json` settings](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/advanced.md#other-gatejson-settings)): a `Coverage` row, and under it a `Not established before running` block when an input or script is `missing` or `not pinned: ...` (the file was absent or its fingerprint could not be taken, so nothing was pinned to compare a later run against). It lists at most three such files, then `(+N more: card <hash> full)`, and is left out when there are none. It lists only what the gate can see in the plan and its pins, so an absent block means none of these was found, not that the plan is covered. The compact card of an amendment shows no block (its full card does);
- `Since`: what is new since the newest earlier approval that covers or writes the same paths, of any age: scripts as `SAME`, `CHANGED` or `NEW` by fingerprint (from the plan's pins, else the receipts of its runs; `NEW` means that plan recorded nothing for the script), inputs the same way (with any removed input), and whether the objective and each step row are exactly the same, compared cell by cell before anything is shortened for display: rows added, changed or removed, steps reordered, outputs and the runs allowed added or removed, and any `validation-bindings` or `exact-execution` comment block changed, all by comparing text. It reports equality or difference of what the plan declares, never that the science is unchanged, and rows whose ID (or, without an ID column, step text) repeats are reported as "cannot compare"; with no such plan the card says "no baseline" and why, never an empty "nothing changed";
- `Runs`: for a plan whose table lets through only named scripts or files: how many, how many are pinned, `any arguments` (a path in the table lets a run through whatever arguments it has), and how many pinned inputs it reads and outputs it writes. A plan that lets through a folder (everything gated below it) or a command (any invocation), or that declares an [exact-execution](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/advanced.md#exact-execution) block, gets the whole `CAN RUN (in full)` list instead, never collapsed, with a shared path prefix written once as `P`; its heading says `broad grant: any arguments`, or `exact where listed below, otherwise broad grant: any arguments` with one `exact: row N: <argv>` line per frozen step;
- a `lint` line, from scilintr's verdict on the planned code that exists (`.py`, `.R`, `.ipynb`, `.qmd`, `.Rmd`): `lint: clean`, or per step `2 open (R002, R011)` or `not checked (...)`, with `; N approved threshold(s)` where a Choice cell of the plan states the number. It is the same run `verify` does, shown on the card only; it never blocks approval, and `verify` still blocks on a finding left unfixed or unwaived (a threshold finding whose numbers are all stated in an approved Choice cell is info, see [Verification](verification.md)). Set `"card_lint": false` in `gate.json` to leave it off, or record the linters' paths with `gate_init.py --tools` (see [Verification](verification.md)); each language's linter gets 8 s here, and the Stop hook's timeout is 30 s;
- what could surprise you, only when present: the Evidence bullets that name a failure or a flag, a `Shorthand, not read` line (an `Outputs:` word starting with `…` names no path), inputs or outputs that could not be read as paths, anything outside the repository or outside the Step column (named in the plan only, so not authorised), one line per declared [validation binding](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/advanced.md#validation-bindings), and the not-in-.gitignore warning. A validation block that does not pass is shown as errors instead of a card, and the plan cannot be approved until it is fixed;
- when scripts changed, the count of diff lines and `card <hash> diff`; then `More: card <hash> full` and the last line, `▶ approve  (or approve plan <hash>)`.

Type `card <hash> full`, `card <hash> checks` or `card <hash> diff` to see the rest. The full card has the question and goal, the Facts count line, the `Sequence` (each step with its `choice`, `assumed` reason, `check` and `lint` bullets), every `CAN RUN (in full)` line, the pinned inputs and the outputs by name, and the diff of changed scripts. With `card_coverage` on (the default), the full card also has the `Not established before running` section: every input and script whose pin is weaker than a content hash, each with its method (`missing`, `not pinned: ...`, `size+mtime` when a file was over the `pin_hash_mb` budget, `folder listing`), one line for Validation prose when the plan has no `validation-bindings` block (a `none` or `n/a` cell is not listed here, though the `Coverage` row still counts any non-empty cell as prose only), and `Out of scope here: whether the science is right, and runs the gate's hooks do not see`. If that section cannot be worked out it says `not computed (<error>)` and the plan stays approvable. Example from the hook, for a plan whose `Inputs:` line names `data/metadata.tsv`, which does not exist yet:

```text
Not established before running
  - input data/metadata.tsv (missing)
  - Validation on row 1 is prose: no validation-bindings check is bound to it
  Out of scope here: whether the science is right, and runs the gate's hooks do not see
```

The hook answers that prompt itself, so on Claude Code the agent never sees it. (Checked in Claude Code's hook contract; whether Codex shows a blocked prompt's reason is not yet verified.) On OpenCode the adapter replaces the prompt with the reply and tells the agent to pass it on and do nothing else, so the card reaches you through the agent. On both cards, an interpreter's absolute path in a step shows as its program name, and a path inside the project as its root-relative form.

No card line is longer than 250 characters, except a `CAN RUN` grant and a script-diff line, which are never cut.

Text quoted from the plan has control characters and markup removed, and the phrase "approve plan" written as `approve-plan`. The card shows what the gate allows; it does not check the choices or the checks. Any other plan keeps the older card: runs allowed, inputs, scripts, outputs. Type exactly that (a trailing `.` is fine) to record the approval in `.mycelium-extra/approvals/`. The text is saved when the plan is shown, but the hash can be approved only once its pins and card are prepared; if preparation was interrupted the hash is listed as `(preparing)`, approval is refused, and showing the plan again prepares it. A pending plan saved by 0.9.44 to 0.9.70 has no such field and counts as prepared only if it holds its `scripts` record, which those versions wrote last; an older one stays approvable.

An approval grants execution only in the session that gave it. Approvals without a recorded session stay readable as history, but you need a new card and approval before they run anything. Approve in the session that presented the plan. If you move to a new session, present the plan there first; a pending hash from another session grants nothing. When the context fills up while a plan waits, `/mycelium-extra:handoff` points `HANDOFF.md` at the plan's stored text, and the new session prints it unchanged. Approve the hash on the new card: it matches the old one when the text is unchanged.

## What is gated

Before each shell call (all three hosts reach the gate with it as `Bash`; OpenCode's `shell` tool is mapped), the gate denies a gated run unless an approval from the last `approval_hours` (default 24) names it. Approvals are never deleted, so `verify` can check old plans. If reading them takes longer than 5 s, the gate blocks the run and says why instead of letting it through unchecked. Two kinds of run are gated:

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

An approval covers the inputs you checked as well as the steps you plan to run. Pinning ties the plan to those files, so a changed sample table or config can't silently inherit the old approval.

A grill brief has an `Inputs:` line naming, by repository path, the files the plan rests on: the sample table, config or params files, a lockfile, or a folder of raw files. When the Stop hook shows `approve plan <hash>`, it also fingerprints those files and lists them.

Paths are read as written, never evaluated: a path in backticks or single or double quotes may hold spaces, apostrophes and commas, and a plain path is read as before. An entry the gate cannot read as one literal path (a `$VAR` or `$(command)`, a glob or brace pattern, a quote left open, a quoted list, or an `Outputs:` brace expansion cut at 200 paths) is not pinned and not read as pieces; the card names it on an `Inputs not read` or `Outputs not read` line, so name each file instead (in quotes if its name has a space).

- A file gets a sha256 while the per-hook budget lasts: `pin_hash_mb` bytes (default 200) and `pin_seconds` seconds (default 5) in `gate.json`. After that it gets size and mtime.
- A folder gets a fingerprint of its file names, sizes, and mtimes, up to 5,000 files. Contents are not read. A folder the time limit cuts off is named as not pinned.
- If the time limit cuts off the check before a run, the run goes ahead and the gate names the inputs it did not re-check.
- A path outside the repository is named in the notice and not pinned. Symlinks inside the repository are followed.
- Showing the same plan again re-pins it, and the notice names any file that changed since the plan was last shown.
- A plan with no `Inputs:` line pins nothing, and the notice says so.

Approving copies the pins into the approval. Before a covered run, the gate fingerprints the pins of the newest approval that covers it. An older plan that pinned less therefore cannot let a run through after a newer plan's pins changed. The gate blocks the run if one changed, naming the file with its old and new fingerprint. Re-check the input (for example, re-run the data-contract check), show the plan again, and approve it. Explore runs skip this check.

## Optional features

Most researchers never need these, so they live on the [Advanced features](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/advanced.md) page: [approval instances](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/advanced.md#approval-instances) (the immutable record each approval writes), the [run limit](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/advanced.md#run-limit), the [approval latency log, deny log and comprehension checkpoint](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/advanced.md#approval-latency-and-comprehension-checkpoint), [validation bindings](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/advanced.md#validation-bindings), [exact execution](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/advanced.md#exact-execution), and [review packets and consent](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/advanced.md#plan-review-packets-and-consent).

## Pinned scripts

An approval is a working scope, and it also records the code you approved. You and the agent can keep editing the scripts the plan lists. The gate doesn't block an edit. It re-pins the script and says so, and `verify` reports a reportable run of code no approval froze as a gap.

- When a plan is shown, the gate fingerprints each existing script (`.py`, `.R`, `.sh`, `.ipynb`, `Snakefile`, and similar) that the plan table names, up to 500. The card lists them under "Scripts pinned".
- Any other script the plan covers, such as one under a folder it names or one that did not exist then (analyze writes code after plan approval), is pinned at its first covered run.
- Before a covered run, the gate compares the script it runs with the pin of the newest covering approval. When the script was edited, the run goes ahead and the gate re-pins it: the new pin is appended to `.mycelium-extra/repins/<hash>.jsonl`, and the approval and its instance are not rewritten.
- The notice, shown to you and to the agent, names the script, the lines added and removed and, when numbers moved between the removed and the added lines, which ones (`numbers changed: dropped 0.05 · new 0.01, 1 (not in the plan)`). A number is "in the plan" when a Choice or Step cell of a plan row naming the script holds it. The agent is told the plan row is not edited for it. Comment-only lines are skipped; numbers inside strings and indexes still count, so the line is a prompt to look, not a verdict.
- A script pinned only by size and time, or larger than 256 KB, has no kept copy: the notice says "diff not kept" and does not check numbers.
- Showing the plan again still lists "Scripts changed since last approved" with a diff, measured against the approved version, so the card shows what you have not seen. Approving the plan again re-baselines the pins; earlier re-pins stay in the journal as history.
- The gate keeps a copy of each pinned or re-pinned script up to 256 KB in `.mycelium-extra/scripts/` to show diffs.
- Any byte change counts, including whitespace and comments. For a notebook only the code cells count, since running it rewrites its outputs. Explore runs skip the check, like input pins.
- Turn it off with `"pin_scripts": false` in `gate.json`.

Changed inputs, changed validation or exact-execution files and the run limit still block until the plan is shown and approved again.

### Amendment cards

A plan that only adds to an earlier approval shows a change-only card: `Adds` (the new scripts), `Row` (each new plan row with its choice, who decided it and its check), `Reads`, `Writes`, `Grant` and `Unchanged`, ending in `▶ approve amendment <hash>` (a bare `approve` works when it is the one card waiting). The card appears only when every earlier row, the objective, the question, the pinned inputs, the validation and exact-execution blocks and every existing script are unchanged, and the only new grants are scripts or files. Anything else (a changed or removed row, a new input, a folder or command grant) gives the whole card, so the delta view never hides a change. It approves the amended plan's own hash and text; the earlier approval is not touched. `card <hash> full` shows the whole card.

### Freeze

`freeze <hash>` is the one review of code before a reportable run. Type it yourself; the hook answers it, so the agent never sees the card. It compares each script now with the one the approval pinned and shows:

- every changed script with its size of change, how often the gate re-pinned it and its diff (40 lines per script, 200 in all; a script with no kept copy says "diff not kept"), then the numbers that moved and whether the plan's rows hold them;
- scripts first pinned after the approval (run under a folder grant, say) as new;
- `Rerun`: the step that names a changed script and every later step, since the gate cannot see which step reads which output; `Stale`: the plan's declared outputs, which may be out of date until the rerun;
- `Runs` under this approval so far and `Gaps now`: the gaps and blocks `verify report` finds now apart from unfrozen code and the linter, or "not computed" when that takes over 4 s.

`approve` (or `approve freeze <hash>`) then writes a new approval record and instance whose script pins are the code you reviewed. Run the plan again, then `verify`: the rerun belongs to the new instance, and earlier runs are history. A freeze refuses, in one sentence, when the hash has no approval, nothing changed, an input or a validation file changed (show the plan again; a freeze covers scripts only), or a script changed after the card was shown (send `freeze <hash>` again). Edits after a freeze re-pin with a notice, as before it.

Only the script a command runs is checked. A file it sources or imports, and the scripts a Snakefile rule runs, are not; list them on the plan's `Inputs:` line to pin them (a run plan from grill freezes the code that way).

## Validation bindings

Optional, and moved to [Advanced features](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/advanced.md#validation-bindings).

## Exact execution

Optional, and moved to [Advanced features](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/advanced.md#exact-execution).

## Run receipts

Receipts are the execution record that `verify` reads later. After a covered shell call completes and its post hook fires, the gate appends one line per run to `.mycelium-extra/receipts.jsonl` (schema `mycelium-extra.receipt.v1`). A receipt holds:

- The approved plans that cover the run and their pins, or none. `pins_checked` is false for explore runs, which skip the pin check. The plans are the ones that allowed the launch: the pre-run hook saves them under `.mycelium-extra/launches/` (removed when the call reports back), so an approval that expires or is replaced during the call is still credited. Each run's record is keyed by its command text and paths, so the same text run in two folders of one call is credited to its own plan. A call with no such record is credited from the approvals active when it reports back: the plans are then context only. `launch_match` says how the receipt was tied to its launch: `matched` when this call's launch record names the run, otherwise `unmatched` (for example a post hook with no pre hook). `pins_checked` is true only for `matched` receipts, so a plan that merely covers an unmatched run never counts as a checked launch. A receipt without `launch_match` predates this field: its launch link was not recorded. A call with no call id is matched by session and command; a second identical launch while the first is still unreported makes that key `ambiguous`: both attempts are stored, each Post is `ambiguous` with `attempt_candidates`, and none counts as a checked launch (the gate never guesses). A second Post for a call id that already reported is `unmatched` with a `launch_note` saying so. Each launch record carries `attempt_id` (random), `call_id`, `started` and `cwd`, and each matched receipt repeats `attempt_id` and `call_id`; a record not taken within 24 h moves to `.mycelium-extra/launches/abandoned/` as an incomplete attempt instead of being deleted. Launch records and receipts without these fields are legacy and are never read as matched. When the session had a `focus` open at launch, the launch record keeps its `focus_id` and `focus_folder` and a matched receipt repeats them; a focus opened or switched after the launch is never written into that receipt, and an unmatched receipt carries none (see [Focus and track changes](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/focus-and-track-changes.md)).
- Output observation. At launch the gate records, for the credited plan's declared `Outputs:`, each literal path and each one-level glob match, with a declared folder (or a matching folder) expanded to the files inside it, recursively (at most 200 files in all, and over that the observation is skipped, never listed partially; `**` patterns and directory trees are never scanned) as `outputs_before` `{path: [size, mtime_ns]}` in the launch entry (`null` for a path that does not exist yet). The receipt then carries `outputs_observation` and, when observed, `outputs_changed` `{created, changed, deleted}` (a changed size or mtime counts as changed; an untouched file is not listed). `outputs_observation` is `observed`, or `skipped: <reason>`: no declared outputs, cap reached, a `**` pattern, an unmatched or ambiguous launch, a compound shell call, or a job submission (the job writes after the call returns). A change between launch and report is an observation, not proof that this run wrote the file: a concurrent writer is indistinguishable.
- `validation_check`, `exact_match`, `exact_step`, when the launch recorded them: the id of the [validation binding](#validation-bindings) whose invocation this command is, and whether an [exact-execution](#exact-execution) step held it (`true` with the matched row, `false` when no step was about it; absent when the plan has no block).
- `started`: the launch's start time for a matched launch (`null` when unmatched, ambiguous or legacy), so overlapping attempts can be detected.
- `approval_instance`: the id of the approval instance the credited plan had when the run launched (see [Approval instances](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/advanced.md#approval-instances)), `null` for an approval from before instances.
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

OpenCode uses the plugin adapter under `opencode/`, configured through the `plugins` setting ([Installation](installation.md#opencode)). Receipts are marked `host: opencode` and carry the shell tool's exit code (the adapter maps the result's `metadata.exit`); a result without one records `unknown`, and verification reports a gap. The 2.0.32 server event stream is service-wide, so the adapter keeps only its own location's events for the stop check. Qualified on 2.0.32; see the [development notes](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/development.md).

## Mycelium's post-action protocol

Mycelium's own hooks detect only python, R, and jupyter runs. In a repository with `.living/`, a receipted run can be one Mycelium does not detect: `bash run.sh`, snakemake, sbatch, nextflow, and other runners. After such a run, the receipt hook tells the agent once that the protocol did not fire. It asks the agent to follow it (learnings, decisions, findings, manifest, analysis doc) when the run finishes. It is a reminder; Mycelium's Stop hook still does not see these runs.

## Exploratory runs

Need a quick experiment before you can write the final plan? Exploration gives you that space and keeps the experiment apart from the runs you will report.

Type `allow explore` to let runs prefixed with `MYCELIUM_EXTRA_EXPLORE=1` through for this session; type `stop explore` to end it. Without the grant the prefix is denied, so the agent cannot exempt itself. Each explore run is logged, and the Stop hook lists those runs as not reportable. To make them reportable, say "promote explore runs": grill lists this session's explore runs (`verify explore`, prefix removed, scripts edited since flagged) and drafts a normal plan that re-runs them, for the usual approval. Explore outputs are never promoted to results. After each one, the receipt hook tells the agent the run is not reportable, so a learning or finding it records from the run (for example under Mycelium's post-action protocol) is labeled `Exploratory run (not reportable)`. Output files carry no label.

**Scoped and session-wide grants.** `allow explore` alone is the broader, session-wide development authorization: any gated path may run with the prefix, and nothing is checked beyond the logging above. `allow explore <8-hex plan hash>` is the scoped form. The hash must be an active approval of this session (otherwise the gate replies and grants nothing). The grant stores that approval's instance id, the analysis paths and commands its plan table grants, and the plan's declared protected items: the pinned test and expectation files of its `validation-bindings`, and the steps of its `exact-execution` block. It lasts for the session; `stop explore` removes it, and approval expiry after the grant does not.

What a scoped grant enforces is path-and-declared-file based, and advisory beyond that. The gate does not infer scientific drift from a code change.

- An explore run that touches a gated path (or command) outside the plan's analysis paths is denied, naming the path. The user decides: approve a plan that names it, or type `allow explore` for the session-wide grant.
- Runs inside the paths need no new approval and no new prompt, however often the code is fixed and re-run.
- A protected test or expectation file whose hash differs from the approval, an edit of one, an explore run of a check's declared invocation, or an explore run that differs from a frozen exact step is reported to you and the agent, not denied: the protected contract changed, so reportable runs will need re-approval.
- Receipts and `explore.log` lines under a scoped grant carry `explore_scope` (the approval instance id), the attempt id, and the fingerprints of the scripts the run used, so failed tries stay visible. An explore receipt never has `pins_checked: true` and never records a `validation_check`: exploration does not satisfy validation or own outputs.

Promotion is unchanged and never a relabel. A reportable result needs an approved rerun of the plan (shown again and approved if a protected file or step changed), writing fresh outputs; explore outputs are not renamed or reclassified as results.

## Lint on write

Mycelium's `analyze` skill tells the agent to run scilintr after every code write, but nothing checks that it did. With a gate on, a PostToolUse hook on `Write`, `Edit`, `MultiEdit` and `NotebookEdit` (Claude Code), `apply_patch` (Codex) and `edit`, `write` and `patch` (OpenCode) does it for the agent.

- It lints the files just written (up to five per patch), if they are under `gated_paths` and are code (`.py`, `.R`, `.ipynb`, `.qmd`, `.Rmd`), with the linters `init --tools` recorded. Each subprocess has an 8 s limit; both languages and their waiver checks share a 16 s subprocess budget under the 20 s hook limit. Files beyond the five-file limit are reported as unchecked. One call covers a whole patch; R may also report cross-file rules among those files. The plan card and `verify` check the wider analysis.
- Open findings go to the agent as context, once per change: the same findings after the next edit are not repeated, and they return if they were fixed and then reappear. Waived findings are not listed; an R waiver with no reason is. Finding text is stripped of control characters and cut at 240 characters.
- It never blocks. When scilintr could not check something (not installed, timed out, unreadable output, an internal lint error, or a script that does not parse under the hook's Python, which on some clusters is older than the linter's), the agent is told once per session that this is not a clean result, and the file's earlier findings are kept. `verify` reports the same as a gap.
- Each script's findings are kept in its own file under `.mycelium-extra/pending/`, so parallel writes to different scripts do not overwrite each other. Unchecked notices use separate markers so simultaneous writes report the same gap once.
- When a turn ends, you see one line naming the scripts written this session that still have open findings, once per change. The agent does not see it on Claude Code; on OpenCode it is posted as a synthetic message in the session, and whether the model reads it has not been checked. A script edited after its lint (for example by `sed` through Bash) is left out, because nothing is known about it.

- **Before a run (opt-in).** `"lint_before_run": "warn"` tells you and the agent, when a gated run starts, that a script it uses still has the findings lint-on-write recorded; `"block"` denies the run until they are fixed or waived. It applies to explore runs too. It reads the records of any session and adds no lint run. A script the hook never linted, or edited since its lint (for example by `sed` through Bash), is unknown and not listed, so this narrows `verify`, never replaces it. Any other value is ignored with a notice.

- **Before the turn ends (opt-in).** `"lint_before_stop": true` blocks the Stop once per change when scripts the agent wrote this session still have open findings, with the findings as the reason, so the agent can fix or waive them in the same turn. The host's `stop_hook_active` flag stops it from blocking twice in a row; OpenCode sends no such flag, so there the once-per-change marker is the only guard. It needs `lint_on_write`. Without it, only the user-only Stop line above is shown.

`verify` still decides: it blocks on any finding left unfixed and unwaived, except a threshold finding (`magic-threshold`, `R002`) whose line holds only numbers, with the same sign, that a Choice cell of a plan row naming that script states (any row's Choice, when no row names the script). That one is info. The reason lines of `lint_before_run` and `lint_before_stop` say the same.

## Command hints

Type `hints on` for a one-line suggestion of the command to run next, and `hints off` to stop them. The setting lasts for the repository until you turn it off. Hints need the gate (`init`), since the gate's hooks carry them.

- When you send a prompt that matches a task type, the agent is told which command fits and names it in one line, asking before it switches. Rules, first match wins: wrap up or new session → `handoff`; new analysis folder → `new-analysis`; which decision binds → `decision-status`; sample table → `data-contract-check`; brainstorm → `/mycelium:ideas`; ingest → `/mycelium:ingest`; report or write-up → `/mycelium:report`; review or audit → `/mycelium:review`; analysis words with no active approval → `grill`. The `/mycelium:*` rules apply only where `.living/` exists. Prompts that start with `/` or name `mycelium` get no hint.
- When a turn ends, you alone see these on Claude Code (the agent does not, so they cost no tokens; OpenCode posts them as synthetic session messages, see above): `verify <hash>` once a gated run under that plan has a receipt this session, and `handoff` once the context passes 120k tokens. Each shows once per session.
- Hints match keywords, so some miss or misfire.

## Settings

`.mycelium-extra/gate.json` takes these keys. A missing key uses its default, and `{}` uses them all. `init` sets only `gated_paths`, `gated_commands`, and `approval_hours`; edit the file by hand for the rest.

| Key | Default | Meaning |
|---|---|---|
| `gated_paths` | `["analysis/**", "nbs/**"]` | Scripts under these globs need an approved plan naming them. |
| `gated_commands` | `["sbatch", "snakemake", "nextflow"]` | Commands that need an approved plan containing the command word. |
| `approval_hours` | `24` | How long an approval covers runs. Approvals are never deleted. |
| `on_error` | `"allow"` | What a PreToolUse hook does when the gate itself breaks. `"deny"` blocks every tool call the gate could not check, including when `gate.py` cannot load; any other value is ignored with a notice. |

The optional keys (`max_runs_per_approval`, `checkpoint_steps`, `pin_hash_mb`, `pin_seconds`, `card_coverage`, `card_lint`, `focus_notices`, `lint_on_write`, `lint_before_run`, `lint_before_stop` and `pin_scripts`) are listed under [Other `gate.json` settings](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/advanced.md#other-gatejson-settings).

Two switches are not keys. `hints on` and `hints off` create and remove `.mycelium-extra/hints.json`. `allow explore [<plan hash>]` and `stop explore` apply to one session.

### What `.mycelium-extra/` holds

Everything is gitignored and local to the clone. The `.jsonl` logs and `explore.log` only grow: nothing trims them. `verify` reads `receipts.jsonl` and `gate-errors.jsonl`; `explore.log` feeds the Stop notice that lists explore runs; `approvals.jsonl` and `denies.jsonl` are for you.

| Path | Holds |
|---|---|
| `gate.json` | The settings above. |
| `approvals/<hash>.json`, `approval-instances/<hash>/` | The approved plans and their frozen content ([Approval instances](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/advanced.md#approval-instances)). Never deleted. |
| `pending/` | Plans shown, per session (text, pins, card), and the lint records of scripts written. |
| `script-pins/`, `repins/`, `scripts/` | First-run script pins, the append-only re-pin journal (`repins/<hash>.jsonl`: time, script, new pin, old hash, session, lines added and removed) and the stored copies used for diffs. |
| `launches/` | One record per gated launch until its call reports back; `launches/abandoned/` keeps those never taken. |
| `explore-grants/` | The session's `allow explore` grant. |
| `receipts.jsonl` | Run receipts, read by `verify`. |
| `explore.log` | One line per explore run. |
| `approvals.jsonl` | Approval latency log; written, never read back. |
| `denies.jsonl` | Denied tool calls; written, never read back. |
| `gate-errors.jsonl` | Internal gate errors. |
| `review-packets/`, `review-consent/` | Prepared review packets and the consent the gate wrote for them. |
| `hints.json`, `tools.json`, `locks/` | The hints switch, the linter paths `init --tools` recorded, and write locks. |

## Limits

The gate catches execution mistakes. It is not a security boundary or a judgment of scientific validity. Use its record to see what happened, including what it could not check.

- The gate denies the agent's Write/Edit calls into `.mycelium-extra/` and the `apply_patch` targets of Codex (and OpenCode's `patch`, `edit` and `write`, mapped to the same tools), including move destinations. For Bash, it checks where a command writes: redirect targets, and the targets of `rm`, `cp`, `mv`, `tee`, `sed -i`, `find -delete`, and similar. The code of a shell is read whatever the spelling of its flags (`bash -c`, `-lc`, `-ec`, `-ce`, `bash -c -l CMD`, `env bash -lc`, `/bin/bash -lc`; `sh`, `zsh`, `dash`, `ksh`, `fish`, `csh`, `tcsh`). A command that only mentions the folder passes, such as a learning about the gate appended to `.living/learnings.md`. An interpreter's code cannot be traced, so a runner is denied when it gets a path in the folder, or when its own code (`-c`, a heredoc, or a script written by a heredoc earlier in the command) names the folder and writes anything. In Python code, the folder counts only in a path string or a shell-command string that writes it; prose and multi-line strings are text being written elsewhere. A variable set to a literal in the same command is expanded before the check.
- Deleting the state folder through a folder that holds it is denied for `rm -r*`, `mv`, `find -delete` (with no `-name` or `-path` test), `rsync --delete` (unless the folder is excluded), `git clean -x`/`-X` and `git stash -a`/`--all` (unless a pathspec or `-e` leaves the folder out; a dry run passes). Other ways to remove it are not seen: `git clean -fd` or `git stash -u` while the folder is untracked and not ignored, a script that deletes it, a variable or glob the gate cannot resolve. A gate whose `gate.json` is gone is off and says nothing; `verify` then reports the plan's runs as unrecorded (a gap, never a clean pass).
- Inline code (`python -c`, `Rscript -e`) counts as a gated run when it names a gated script (`.py`, `.R`, ...), or any gated path when it changes `sys.path`, the working directory, or `.libPaths()`. A read-only probe of gated data passes.
- It passes a command by staying silent and never auto-allows, so your own permission prompts still apply.
- It needs Python 3.9 or later. Hooks start through `hooks/py.sh`, which picks the newest `python3.N` on `PATH` (3.14 down to 3.9), else `python3`; set `MYCELIUM_EXTRA_PYTHON` to name one. A registration from before 0.9.76 runs `python3` directly: `gate_run.py` first hands the event to `py.sh` once, and only if that finds nothing newer does it report "mycelium-extra needs Python 3.9 or later" and follow `on_error`.
- On an internal error it fails open and says so, unless `gate.json` sets `"on_error": "deny"`: then every tool call it could not check is denied until the error is fixed or the key is set back to `"allow"`. Each error is appended to `.mycelium-extra/gate-errors.jsonl` when it can be written, with its `event`, `decision`, `host`, `session_id` and `call_id` (each `null` when the event could not be decoded); when the log cannot be written no record is made and the message says so. Only tool calls are blocked; prompt, stop and post hooks report the error and carry on. A `gate.json` that cannot be read cannot opt in, and a host that never runs the hook cannot be controlled by it.
- The gate reads the words of a shell command. A runner whose script is a shell expansion (`python3 $f`, `python3 $(ls ...)`, a loop variable, a variable set earlier), and a `cd` or `pushd` into one, is unresolved: it is denied unless a plan covers the literal text, so write script paths literally. The bodies of `for`, `while` and `if`, `pushd`, and `apptainer`, `singularity`, `docker` and `podman` `exec`/`run` are read as the command they hold. These are not traced: `make` and other build tools outside `gated_commands`, `bash script.sh` or `./run.sh` outside `gated_paths` (what a script runs inside is not read), `runpy`, `ipython`, `pypy`, `xargs python3`, `find -exec`, `eval` of a variable, and a script written in an earlier call and then run. Such a run is not denied and leaves no receipt, so `verify` reports it only when it can see its outputs.
- Tools other than Bash and the file-edit tools are not gated: code run through an MCP notebook tool (`nb_*_execute`) or any other tool the gate does not match bypasses both the gate and the lineage.
- Edits to a script the plan lists are re-pinned with a notice, not blocked, so a covered run can execute code newer than the code you approved. The approval is for the plan and its pins as shown; `freeze` and `verify` show what changed, and a reportable run of code no approval froze is a gap.
- It catches mistakes; it is not security. An agent set on bypassing it through Bash can do so.
- `defined_by` in a validation binding is the plan's own claim. The gate pins the check's files and notes whether their bytes changed; it does not know who wrote the expectation, run the check or judge the expectation. An exact step freezes the launched command line, not what the script does with it.
- Size-and-mtime and folder fingerprints miss an edit that keeps both (for example `cp -p` or `rsync -t`). The notice says which fingerprint each input got.
- A receipt records the environment a job declares, not the one it resolved. `hook_env` is the host hook's environment, not the job's.
- A job ID records a submission, not its outcome. Check `sacct` or the job log.
- The exit status is inferred from which hook event fired, not read from the command. `verify` reports a nonzero, `failed`, or `interrupted` run as a failure, and an `unknown` status (or an empty one in older receipts) as a gap.
- `verify` credits a script to a Snakemake rule only when the rule runs it: the expanded `shell:` command, or the `script:`/`notebook:` path in the rule's `code` record. A rule input is not a run. The `script:` path is matched against Snakemake's working directory, so a Snakefile in another folder (`-s other/Snakefile`) is not matched, and Snakemake 9 releases that record only `shell:` commands leave a `script:` rule's script with `no receipt`.
- Codex needs enabled/trusted hooks and CLI 0.160.0 or later. Its 0.160.0 post hook omits exit metadata, so run status is `unknown` and verification reports a gap. A hook that never dispatches leaves no receipt. See [Host compatibility](installation.md#host-compatibility).
- OpenCode needs the plugin directory in `plugins`; the adapter is inert without `.mycelium-extra/gate.json`. See [Host compatibility](installation.md#host-compatibility).
