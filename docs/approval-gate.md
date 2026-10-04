# Approval gate

[Back to README](../README.md)

Claude Code hooks in `hooks/` enforce grill's rule that nothing runs until you approve. The gate is off unless you turn it on per repository with `/mycelium-extra:init`, or by hand:

1. Create `.mycelium-extra/gate.json`. `{}` uses the defaults.
2. Add `.mycelium-extra/` to `.gitignore`. It holds short-lived execution state, not project knowledge.

`init` checks whether the default paths exist and asks which folders to gate if they don't. It never changes a gate that is already on; after that, edit `gate.json` by hand.

## Approving a plan

When a reply ends with `Plan status: READY` or `READY_WITH_ASSUMPTIONS`, the Stop hook hashes the plan and shows `approve plan <hash>`. The notice also lists which gated scripts, folders, and commands the plan would let run. Type exactly that (a trailing `.` is fine) to record the approval in `.mycelium-extra/approvals/`. A bare `approve plan` lists pending hashes and approves nothing.

## What is gated

Before each Bash call, the gate denies a gated run unless an approval from the last `approval_hours` (default 24) names it. Approvals are never deleted, so `verify` can check old plans. If reading them takes longer than 5 s, the gate blocks the run and says why instead of letting it through unchecked. Two kinds of run are gated:

- Scripts under `gated_paths` (default `analysis/**`, `nbs/**`). This covers running them by interpreter, directly, via stdin (`python3 - < analysis/x.py`), `-c "$(cat …)"`, `-m`, after `cd`, or under `conda run`, `srun`, `timeout`, and similar wrappers. The plan table must name the script's path, or an enclosing folder at least two levels deep (`nbs/cytof_exvivo/`), as a path token.
- Commands in `gated_commands` (default `sbatch`, `snakemake`, `nextflow`). The plan table must contain the command word. Payloads of `bash -c` and `sbatch --wrap` are checked as commands too.

A dry run (`snakemake -n`, `bash run.sh -n`) is gated like any run: a Snakefile is Python, and Snakemake runs its top-level code and input functions while building the job list.

Only the plan table counts. A path or command word in the brief's prose, its Evidence, a Source column, or a `repo:` citation approves nothing, so a plan that cites a script as evidence does not approve running it. A plan with no table approves nothing, and the approval notice says so.

Reading gated files (`cat`, `rg`, `git`) is never gated.

## Pinned inputs

A grill brief has an `Inputs:` line naming, by repository path, the files the plan rests on: the sample table, config or params files, a lockfile, or a folder of raw files. When the Stop hook shows `approve plan <hash>`, it also fingerprints those files and lists them.

- A file gets a sha256 while the per-hook budget lasts: `pin_hash_mb` bytes (default 200) and `pin_seconds` seconds (default 5) in `gate.json`. After that it gets size and mtime.
- A folder gets a fingerprint of its file names, sizes, and mtimes, up to 5,000 files. Contents are not read. A folder the time limit cuts off is named as not pinned.
- If the time limit cuts off the check before a run, the run goes ahead and the gate names the inputs it did not re-check.
- A path outside the repository is named in the notice and not pinned. Symlinks inside the repository are followed.
- Showing the same plan again re-pins it, and the notice names any file that changed since the plan was last shown.
- A plan with no `Inputs:` line pins nothing, and the notice says so.

Approving copies the pins into the approval. Before a covered run, the gate fingerprints the pins of the newest approval that covers it (so an older plan that pinned less cannot let a run through after a newer plan's pins changed) and blocks the run if one changed, naming the file with its old and new fingerprint. Re-check the input (for example, re-run the data-contract check), show the plan again, and approve it. Explore runs skip this check.

## Run receipts

After each gated Bash call, a PostToolUse hook appends one line per run to `.mycelium-extra/receipts.jsonl` (schema `mycelium-extra.receipt.v1`). A receipt holds:

- The approved plans that cover the run and their pins, or none. `pins_checked` is false for explore runs, which skip the pin check.
- Git HEAD, whether tracked files have uncommitted changes, and whether each recorded file is committed, modified, untracked, or ignored.
- The script's fingerprint (or the sha256 of an `sbatch --wrap` payload), and its `module load`, `conda activate`, and `#SBATCH` lines.
- Lockfiles (`renv.lock`, `pixi.lock`, `environment.yml`, and similar) in the repository root, the working directory, and the script's folder.
- The environment the hook itself runs in (`hook_env`), and any `conda run -n` environment in the command (`command_env`).
- For `sbatch`, the job ID. For snakemake and nextflow, the Snakefile or pipeline, config and params fingerprints, report and trace paths, the nextflow run name, and a pointer to the engine's own record (`.snakemake/metadata`, `.nextflow/history`).
- The exit status when Claude Code reports one, and the key names of its Bash result (`response_keys`).

Receipts stay in `.mycelium-extra/`, which is gitignored, so they do not trip Mycelium's Stop hook. `verify` copies a plan's receipts into the analysis folder after you confirm.

## Mycelium's post-action protocol

Mycelium's own hooks detect only python, R, and jupyter runs. In a repository with `.living/`, after a receipted run Mycelium does not detect (`bash run.sh`, snakemake, sbatch, nextflow, and other runners), the receipt hook tells the agent once that the protocol did not fire, and to follow it (learnings, decisions, findings, manifest, analysis doc) when the run finishes. It is a reminder; Mycelium's Stop hook still does not see these runs.

## Exploratory runs

Type `allow explore` to let runs prefixed with `MYCELIUM_EXTRA_EXPLORE=1` through for this session; type `stop explore` to end it. Without the grant the prefix is denied, so the agent cannot exempt itself. Each explore run is logged, and the Stop hook lists those runs as not reportable. To make them reportable, say "promote explore runs": grill lists this session's explore runs (`verify explore`, prefix removed, scripts edited since flagged) and drafts a normal plan that re-runs them, for the usual approval. Explore outputs are never promoted to results. After each one, the receipt hook tells the agent the run is not reportable, so a learning or finding it records from the run (for example under Mycelium's post-action protocol) is labeled `Exploratory run (not reportable)`. Output files carry no label.

## Command hints

Type `hints on` to get a one-line suggestion of the command to run next; `hints off` stops them. The setting lasts for the repository until you turn it off. Hints need the gate (`init`), since the gate's hooks carry them.

- When you send a prompt that matches a task type, the agent is told which command fits and names it in one line, asking before it switches. Rules, first match wins: wrap up or new session → `handoff`; new analysis folder → `new-analysis`; which decision binds → `decision-status`; sample table → `data-contract-check`; brainstorm → `/mycelium:ideas`; ingest → `/mycelium:ingest`; report or write-up → `/mycelium:report`; review or audit → `/mycelium:review`; analysis words with no active approval → `grill`. The `/mycelium:*` rules apply only where `.living/` exists. Prompts that start with `/` or name `mycelium` get no hint.
- When a turn ends, you alone see (the agent does not, so it costs no tokens): `verify <hash>` once a gated run under that plan has a receipt this session, and `handoff` once the context passes 120k tokens. Each shows once per session.
- Hints match keywords, so some miss or misfire.

## Limits

- The gate denies the agent's Write/Edit calls into `.mycelium-extra/`. For Bash, it checks where a command writes: redirect targets, and the targets of `rm`, `cp`, `mv`, `tee`, `sed -i`, `find -delete`, and similar. A command that only mentions the folder passes, such as a learning about the gate appended to `.living/learnings.md`. An interpreter's code cannot be traced, so a runner is denied when it gets a path in the folder, or when its own code (`-c`, a heredoc, or a script written by a heredoc earlier in the command) names the folder and writes anything. In Python code, the folder counts only in a path string or a shell-command string that writes it; prose and multi-line strings are text being written elsewhere. A variable set to a literal in the same command is expanded before the check.
- Inline code (`python -c`, `Rscript -e`) counts as a gated run when it names a gated script (`.py`, `.R`, ...), or any gated path when it changes `sys.path`, the working directory, or `.libPaths()`. A read-only probe of gated data passes.
- It passes a command by staying silent and never auto-allows, so your own permission prompts still apply.
- On an internal error it fails open and says so.
- It catches mistakes; it is not security. An agent set on bypassing it through Bash can do so.
- Size-and-mtime and folder fingerprints miss an edit that keeps both (for example `cp -p` or `rsync -t`). The notice says which fingerprint each input got.
- A receipt records the environment a job declares, not the one it resolved. `hook_env` is Claude Code's environment, not the job's.
- A job ID records a submission, not its outcome. Check `sacct` or the job log.
- The shape of Claude Code's Bash result is not documented, so `exit_status` can be empty. Whether the receipt hook fires after a failed command is unverified.
- Claude Code only; there is no Codex port yet.
