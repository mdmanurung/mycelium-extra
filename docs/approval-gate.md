# Approval gate

[Back to README](../README.md)

**On this page:** [Approving a plan](#approving-a-plan) · [What is gated](#what-is-gated) · [Pinned inputs](#pinned-inputs) · [Run receipts](#run-receipts) · [Mycelium's post-action protocol](#myceliums-post-action-protocol) · [Exploratory runs](#exploratory-runs) · [Command hints](#command-hints) · [Settings](#settings) · [Limits](#limits)

A plan is useful only if the run still follows it. The approval gate checks covered analysis commands before execution, so an agent cannot start a new run just because a previous conversation discussed it. You decide what is approved, and the gate keeps a record of the runs that follow.

For example, a plan might cover `analysis/response/02_model.R` using a particular sample table. Approving it allows that run for the configured window. If a pinned sample table changes, the gate asks for a checked, revised plan before the covered run proceeds.

The gate works through Claude Code and Codex hooks. Turn it on for a repository with `/mycelium-extra:init` (Claude Code) or `$mycelium-extra:init` (Codex). To configure it by hand:

1. Create `.mycelium-extra/gate.json`. `{}` uses the defaults.
2. Add `.mycelium-extra/` to `.gitignore`. It holds short-lived execution state, not project knowledge.

`init` checks whether the default paths exist and asks which folders to gate if they don't. It never changes a gate that is already on; after that, edit `gate.json` by hand.

## Approving a plan

When a reply ends with `Plan status: READY` or `READY_WITH_ASSUMPTIONS`, the Stop hook hashes the plan and shows `approve plan <hash>`. The notice also lists which gated scripts, folders, and commands the plan would let run. Type exactly that (a trailing `.` is fine) to record the approval in `.mycelium-extra/approvals/`. A bare `approve plan` lists pending hashes and approves nothing.

Approve in the same session that presented the plan. If you move to a new session, present the plan there first; a pending hash from another session does not grant approval.

## What is gated

Before each shell call (both hosts expose it to hooks as `Bash`), the gate denies a gated run unless an approval from the last `approval_hours` (default 24) names it. Approvals are never deleted, so `verify` can check old plans. If reading them takes longer than 5 s, the gate blocks the run and says why instead of letting it through unchecked. Two kinds of run are gated:

- Scripts under `gated_paths` (default `analysis/**`, `nbs/**`). This covers running them by interpreter, directly, via stdin (`python3 - < analysis/x.py`), `-c "$(cat …)"`, `-m`, after `cd`, or under `conda run`, `srun`, `timeout`, and similar wrappers. The plan table must name the script's path, or an enclosing folder at least two levels deep (`nbs/cytof_exvivo/`), as a path token.
- Commands in `gated_commands` (default `sbatch`, `snakemake`, `nextflow`). The plan table must contain the command word. Payloads of `bash -c` and `sbatch --wrap` are checked as commands too.

A dry run (`snakemake -n`, `bash run.sh -n`) is gated like any run: a Snakefile is Python, and Snakemake runs its top-level code and input functions while building the job list.

Only the plan table counts. A path or command word in the brief's prose, its Evidence, a Source column, or a `repo:` citation approves nothing, so a plan that cites a script as evidence does not approve running it. A plan with no table approves nothing, and the approval notice says so.

Reading gated files (`cat`, `rg`, `git`) is never gated.

## Pinned inputs

An approval refers to the inputs you checked, as well as the steps you intend to run. Pinning connects the plan to those files so a changed sample table or configuration does not silently inherit the old approval.

A grill brief has an `Inputs:` line naming, by repository path, the files the plan rests on: the sample table, config or params files, a lockfile, or a folder of raw files. When the Stop hook shows `approve plan <hash>`, it also fingerprints those files and lists them.

- A file gets a sha256 while the per-hook budget lasts: `pin_hash_mb` bytes (default 200) and `pin_seconds` seconds (default 5) in `gate.json`. After that it gets size and mtime.
- A folder gets a fingerprint of its file names, sizes, and mtimes, up to 5,000 files. Contents are not read. A folder the time limit cuts off is named as not pinned.
- If the time limit cuts off the check before a run, the run goes ahead and the gate names the inputs it did not re-check.
- A path outside the repository is named in the notice and not pinned. Symlinks inside the repository are followed.
- Showing the same plan again re-pins it, and the notice names any file that changed since the plan was last shown.
- A plan with no `Inputs:` line pins nothing, and the notice says so.

Approving copies the pins into the approval. Before a covered run, the gate fingerprints the pins of the newest approval that covers it. An older plan that pinned less therefore cannot let a run through after a newer plan's pins changed. The gate blocks the run if one changed, naming the file with its old and new fingerprint. Re-check the input (for example, re-run the data-contract check), show the plan again, and approve it. Explore runs skip this check.

## Run receipts

Receipts provide the execution record that `verify` reads later. After a covered shell call completes and its post hook fires, the gate appends one line per run to `.mycelium-extra/receipts.jsonl` (schema `mycelium-extra.receipt.v1`). A receipt holds:

- The approved plans that cover the run and their pins, or none. `pins_checked` is false for explore runs, which skip the pin check.
- Git HEAD, whether tracked files have uncommitted changes, and whether each recorded file is committed, modified, untracked, or ignored.
- The script's fingerprint (or the sha256 of an `sbatch --wrap` payload), and its `module load`, `conda activate`, and `#SBATCH` lines.
- Lockfiles (`renv.lock`, `pixi.lock`, `environment.yml`, and similar) in the repository root, the working directory, and the script's folder.
- The environment the hook itself runs in (`hook_env`), and any `conda run -n` environment in the command (`command_env`).
- For `sbatch`, the job ID. For snakemake and nextflow, the Snakefile or pipeline, config and params fingerprints, report and trace paths, the nextflow run name, and a pointer to the engine's own record (`.snakemake/metadata`, `.nextflow/history`).
- The exit status and where it came from (`exit_source`), and the key names of the Bash result (`response_keys`). The hook is registered for both `PostToolUse` and `PostToolUseFailure` (matcher Bash). Claude Code fires `PostToolUse` only after a command succeeds, so that receipt records 0 with `exit_source` `event`; a command started with `run_in_background` has only started, so it is `unknown` (`background`). A failed command fires `PostToolUseFailure`: the receipt records N from the error's first line `Exit code N` (`exit_source` `error`), `failed` when there is no such line (the shell did not start, or a timeout), or `interrupted`. An exit code in the tool result itself always wins (`exit_source` `response`). Only the error's first line is kept (`error_line`, at most 200 characters), never the command's output. A payload without an event name is `unknown`.
- For `sbatch --wrap`, the payload's scripts resolved against `-D`/`--chdir` (`paths`), and that folder (`job_cwd`).

Receipts stay in `.mycelium-extra/`, which is gitignored, so they do not trip Mycelium's Stop hook. `verify` copies a plan's receipts into the analysis folder after you confirm.

Codex uses its own post hook and marks receipts with `host: codex`. In CLI 0.160.0, the hook provides command output without exit metadata. Its receipt therefore records `unknown`, and verification reports a gap. The gate never treats a line printed by the command as proof of its exit status.

## Mycelium's post-action protocol

Mycelium's own hooks detect only python, R, and jupyter runs. In a repository with `.living/`, a receipted run can be one Mycelium does not detect: `bash run.sh`, snakemake, sbatch, nextflow, and other runners. After such a run, the receipt hook tells the agent once that the protocol did not fire. It asks the agent to follow it (learnings, decisions, findings, manifest, analysis doc) when the run finishes. It is a reminder; Mycelium's Stop hook still does not see these runs.

## Exploratory runs

Sometimes you need a quick experiment before you can write the final plan. Exploration gives you that space while keeping the experiment distinct from the runs you will report.

Type `allow explore` to let runs prefixed with `MYCELIUM_EXTRA_EXPLORE=1` through for this session; type `stop explore` to end it. Without the grant the prefix is denied, so the agent cannot exempt itself. Each explore run is logged, and the Stop hook lists those runs as not reportable. To make them reportable, say "promote explore runs": grill lists this session's explore runs (`verify explore`, prefix removed, scripts edited since flagged) and drafts a normal plan that re-runs them, for the usual approval. Explore outputs are never promoted to results. After each one, the receipt hook tells the agent the run is not reportable, so a learning or finding it records from the run (for example under Mycelium's post-action protocol) is labeled `Exploratory run (not reportable)`. Output files carry no label.

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
| `pin_hash_mb` | `200` | Bytes of pinned inputs (in MB) hashed per hook before falling back to size and mtime. |
| `pin_seconds` | `5` | Seconds the pin check may take per hook. |

Two switches are not keys. `hints on` and `hints off` create and remove `.mycelium-extra/hints.json`. `allow explore` and `stop explore` apply to one session.

## Limits

The gate catches execution mistakes; it is not a security boundary or a judgment of scientific validity. Use its record to understand what happened, including what it could not check.

- The gate denies the agent's Write/Edit calls into `.mycelium-extra/` and Codex `apply_patch` targets, including move destinations. For Bash, it checks where a command writes: redirect targets, and the targets of `rm`, `cp`, `mv`, `tee`, `sed -i`, `find -delete`, and similar. A command that only mentions the folder passes, such as a learning about the gate appended to `.living/learnings.md`. An interpreter's code cannot be traced, so a runner is denied when it gets a path in the folder, or when its own code (`-c`, a heredoc, or a script written by a heredoc earlier in the command) names the folder and writes anything. In Python code, the folder counts only in a path string or a shell-command string that writes it; prose and multi-line strings are text being written elsewhere. A variable set to a literal in the same command is expanded before the check.
- Inline code (`python -c`, `Rscript -e`) counts as a gated run when it names a gated script (`.py`, `.R`, ...), or any gated path when it changes `sys.path`, the working directory, or `.libPaths()`. A read-only probe of gated data passes.
- It passes a command by staying silent and never auto-allows, so your own permission prompts still apply.
- On an internal error it fails open and says so.
- It catches mistakes; it is not security. An agent set on bypassing it through Bash can do so.
- Size-and-mtime and folder fingerprints miss an edit that keeps both (for example `cp -p` or `rsync -t`). The notice says which fingerprint each input got.
- A receipt records the environment a job declares, not the one it resolved. `hook_env` is the host hook's environment, not the job's.
- A job ID records a submission, not its outcome. Check `sacct` or the job log.
- The exit status is inferred from which hook event fired, not read from the command. `verify` reports a nonzero, `failed`, or `interrupted` run as a failure, and an `unknown` status (or an empty one in older receipts) as a gap.
- `verify` credits a script to a Snakemake rule only when the rule runs it: the expanded `shell:` command, or the `script:`/`notebook:` path in the rule's `code` record. A rule input is not a run. The `script:` path is matched against Snakemake's working directory, so a Snakefile in another folder (`-s other/Snakefile`) is not matched, and Snakemake 9 releases that record only `shell:` commands leave a `script:` rule's script with `no receipt`.
- Codex needs enabled/trusted hooks and CLI 0.160.0 or later. Its 0.160.0 post hook omits exit metadata, so run status is `unknown` and verification reports a gap. A hook that never dispatches leaves no receipt. See [Host compatibility](installation.md#host-compatibility).
