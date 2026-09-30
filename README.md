# Mycelium Extra

A standalone plugin for planning analysis work before it runs. It works alongside [Mycelium](https://github.com/arjunrajlaboratory/mycelium) but does not fork, modify, or require it.

It has four skills and one hook set:

| Part | What it does | Writes |
|---|---|---|
| `grill` | Turns a proposed task into a sourced, numbered plan | Nothing |
| `decision-status` | Settles which past decision binds a task | Appends to `.living/decisions.md`, after you confirm |
| `data-contract-check` | Tests a plan's sample-table assumptions | Nothing |
| `init` | Turns on the approval gate in a repository | `.mycelium-extra/gate.json`, `.gitignore` |
| Approval gate | Blocks analysis runs until you approve the plan, blocks them if the plan's inputs changed, and records a receipt per run | `.mycelium-extra/` only |

## Installation

### Claude Code

1. Add the marketplace, from GitHub or from a local clone:

   ```bash
   claude plugin marketplace add mdmanurung/mycelium-extra
   # or
   claude plugin marketplace add /absolute/path/to/mycelium-extra
   ```

2. Install the plugin for all your projects:

   ```bash
   claude plugin install mycelium-extra@mycelium-extra
   ```

   To enable it for one project only, run this from that project with `--scope local`.

3. Start a new Claude Code session. Skills and hooks load when a session starts.

**Update** after pulling or editing the plugin (Claude Code runs a cached copy, keyed by the `version` in `.claude-plugin/plugin.json`):

```bash
claude plugin marketplace update mycelium-extra
claude plugin update mycelium-extra@mycelium-extra
```

**Try it without installing:** run `claude --plugin-dir /absolute/path/to/mycelium-extra` from the project.

### Codex

- **Plugin:** this folder includes `.codex-plugin/plugin.json` and `skills/*/SKILL.md`, ready to add to a Codex plugin marketplace. After installing, invoke `$mycelium-extra:<skill>`.
- **Standalone skill:** copy one `skills/<skill>/` folder to your personal Codex skills location and invoke it as `$grill`. Namespacing then depends on how you installed it.

The approval gate and `init` are Claude Code only.

## Quick start

A typical analysis task, in order:

1. **Once per repository:** `/mycelium-extra:init` turns on the approval gate.
2. **Plan:** `/mycelium-extra:grill <your task>`. Answer its questions (at most five).
3. **Approve:** when the plan ends with `Plan status: READY`, type the `approve plan <hash>` line it shows.
4. **Run:** execute the plan through your normal workflow (`/mycelium:analyze` in a Mycelium project).

Common prompts:

| Goal | Prompt |
|---|---|
| Plan a task from repo evidence | `/mycelium-extra:grill Redo monocyte pathway analysis across trials; inspect the repo before asking me anything.` |
| Settle conflicting past decisions | `/mycelium-extra:decision-status Which batch-correction decision binds the integration rerun?` |
| Check the sample table before running | `/mycelium-extra:data-contract-check Check the approved plan's cohort, pairing, and batch assumptions against the sample table.` |
| Turn on the gate | `/mycelium-extra:init` |
| Run a quick test without a plan | Type `allow explore`; type `stop explore` when done. |

`grill` calls `decision-status` and `data-contract-check` itself when a plan depends on them, so you rarely need to invoke those directly.

## Skills

### grill

`grill` reads the repository before it asks you anything. In a Mycelium project (any repository with `.living/`), it reads `MYCELIUM.md` or the Mycelium block in `CLAUDE.md`/`AGENTS.md`, `.living/INDEX.md`, relevant memory entries, manifests, analysis docs, and code. Elsewhere it reads the project's own docs and code.

It then tests the goal, evidence, assumptions, alternatives, failure modes, and validation. For bioinformatics or statistical work it also walks a list of analysis decisions (unit of replication, matrix state, references, QC, batch, multiplicity, and more), so none stays implicit.

It asks only questions that you own and that could change the plan: one per message, at most five. It ends with `READY`, `READY_WITH_ASSUMPTIONS`, or one `DECISION_REQUIRED` item, plus a numbered plan. Each consequential choice in the plan cites its source: repository evidence, your answer, or a labeled default. An `Inputs:` line names the files the plan rests on, which the approval gate pins. Nothing runs until you approve or edit the plan.

### decision-status

Use it when `.living/decisions.md` holds several entries on the same choice, for example a method that was confirmed, then held, then shelved.

- A small read-only parser lists the entries the task touches, oldest first. It shows their raw `Status`, `Supersedes`, `Scope`, and `Revisit when` lines and any status words in headings. It never infers which entry is current.
- An explicit supersession wins. Next comes the entry whose scope matches the task. Anything else is contested and goes to you, at most three questions per session.
- Once you confirm an answer, it appends a `Resolution:` entry so the question does not come back. It never edits existing entries.

The new entry uses the ordinary decision fields plus `Status`, `Supersedes`, `Scope`, `Revisit when`, and `Resolved-by`. Mycelium 0.7.2's scripts do not parse `Status` in `decisions.md`, so they read these fields as plain body text.

### data-contract-check

It checks a plan's assumptions about the sample table before anything runs. The assumptions go into a small JSON contract:

- required columns
- cohort levels and row counts
- one row per unit per cell
- complete pairing across timepoints
- batch versus contrast nesting

A stdlib checker reports each mismatch with expected, observed, and evidence lines, in the shape of ClawBio's contract alerts. The checker, not the contract, decides what blocks: any failure of these kinds blocks. The skill never loosens a contract to make it pass without your agreement. v1 reads CSV/TSV tables; it does not yet check h5ad internals.

### Approval gate

Claude Code hooks in `hooks/` enforce grill's rule that nothing runs until you approve. The gate is off unless you turn it on per repository with `/mycelium-extra:init`, or by hand:

1. Create `.mycelium-extra/gate.json`. `{}` uses the defaults.
2. Add `.mycelium-extra/` to `.gitignore`. It holds short-lived execution state, not project knowledge.

`init` checks whether the default paths exist and asks which folders to gate if they don't. It never changes a gate that is already on; after that, edit `gate.json` by hand.

**Approving a plan.** When a reply ends with `Plan status: READY` or `READY_WITH_ASSUMPTIONS`, the Stop hook hashes the plan and shows `approve plan <hash>`. The notice also lists which gated scripts, folders, and commands the plan would let run. Type exactly that (a trailing `.` is fine) to record the approval in `.mycelium-extra/approvals/`. A bare `approve plan` lists pending hashes and approves nothing.

**What is gated.** Before each Bash call, the gate denies a gated run unless an approval from the last `approval_hours` (default 24) names it. Two kinds of run are gated:

- Scripts under `gated_paths` (default `analysis/**`, `nbs/**`). This covers running them by interpreter, directly, via stdin (`python3 - < analysis/x.py`), `-c "$(cat …)"`, `-m`, after `cd`, or under `conda run`, `srun`, `timeout`, and similar wrappers. The plan table must name the script's path, or an enclosing folder at least two levels deep (`nbs/cytof_exvivo/`), as a path token.
- Commands in `gated_commands` (default `sbatch`, `snakemake`, `nextflow`). The plan table must contain the command word. Payloads of `bash -c` and `sbatch --wrap` are checked as commands too.

Only the plan table counts. A path or command word in the brief's prose, its Evidence, a Source column, or a `repo:` citation approves nothing, so a plan that cites a script as evidence does not approve running it. A plan with no table approves nothing, and the approval notice says so.

Reading gated files (`cat`, `rg`, `git`) is never gated.

**Pinned inputs.** A grill brief has an `Inputs:` line naming, by repository path, the files the plan rests on: the sample table, config or params files, a lockfile, or a folder of raw files. When the Stop hook shows `approve plan <hash>`, it also fingerprints those files and lists them.

- A file gets a sha256 while the per-hook budget lasts: `pin_hash_mb` bytes (default 200) and `pin_seconds` seconds (default 5) in `gate.json`. After that it gets size and mtime.
- A folder gets a fingerprint of its file names, sizes, and mtimes, up to 5,000 files. Contents are not read. A folder the time limit cuts off is named as not pinned.
- If the time limit cuts off the check before a run, the run goes ahead and the gate names the inputs it did not re-check.
- A path outside the repository is named in the notice and not pinned. Symlinks inside the repository are followed.
- Showing the same plan again re-pins it, and the notice names any file that changed since the plan was last shown.
- A plan with no `Inputs:` line pins nothing, and the notice says so.

Approving copies the pins into the approval. Before a covered run, the gate fingerprints them again and blocks the run if one changed, naming the file with its old and new fingerprint. Re-check the input (for example, re-run the data-contract check), show the plan again, and approve it. Explore runs skip this check.

**Run receipts.** After each gated Bash call, a PostToolUse hook appends one line per run to `.mycelium-extra/receipts.jsonl` (schema `mycelium-extra.receipt.v1`). A receipt holds:

- The approved plans that cover the run and their pins, or none. `pins_checked` is false for explore runs, which skip the pin check.
- Git HEAD, whether tracked files have uncommitted changes, and whether each recorded file is committed, modified, untracked, or ignored.
- The script's fingerprint (or the sha256 of an `sbatch --wrap` payload), and its `module load`, `conda activate`, and `#SBATCH` lines.
- Lockfiles (`renv.lock`, `pixi.lock`, `environment.yml`, and similar) in the repository root, the working directory, and the script's folder.
- The environment the hook itself runs in (`hook_env`), and any `conda run -n` environment in the command (`command_env`).
- For `sbatch`, the job ID. For snakemake and nextflow, the Snakefile or pipeline, config and params fingerprints, report and trace paths, the nextflow run name, and a pointer to the engine's own record (`.snakemake/metadata`, `.nextflow/history`).
- The exit status when Claude Code reports one, and the key names of its Bash result (`response_keys`).

Receipts stay in `.mycelium-extra/`, which is gitignored, so they do not trip Mycelium's Stop hook. A planned verify step will copy verified receipts into the analysis folder after you confirm them.

**Exploratory runs.** Type `allow explore` to let runs prefixed with `MYCELIUM_EXTRA_EXPLORE=1` through for this session; type `stop explore` to end it. Without the grant the prefix is denied, so the agent cannot exempt itself. Each explore run is logged, and the Stop hook lists those runs as not reportable. After each one, the receipt hook tells the agent the run is not reportable, so a learning or finding it records from the run (for example under Mycelium's post-action protocol) is labeled `Exploratory run (not reportable)`. Output files carry no label.

**Limits.**

- The gate denies the agent's Write/Edit calls into `.mycelium-extra/`. For Bash, it checks where a command writes: redirect targets, and the targets of `rm`, `cp`, `mv`, `tee`, `sed -i`, `find -delete`, and similar. A command that only mentions the folder passes, such as a learning about the gate appended to `.living/learnings.md`. An interpreter's code cannot be traced, so a runner is denied when it gets a path in the folder, or when its code mentions the folder and writes anything.
- It passes a command by staying silent and never auto-allows, so your own permission prompts still apply.
- On an internal error it fails open and says so.
- It catches mistakes; it is not security. An agent set on bypassing it through Bash can do so.
- Size-and-mtime and folder fingerprints miss an edit that keeps both (for example `cp -p` or `rsync -t`). The notice says which fingerprint each input got.
- A receipt records the environment a job declares, not the one it resolved. `hook_env` is Claude Code's environment, not the job's.
- A job ID records a submission, not its outcome. Check `sacct` or the job log.
- The shape of Claude Code's Bash result is not documented, so `exit_status` can be empty. Whether the receipt hook fires after a failed command is unverified.
- Claude Code only; there is no Codex port yet.

## Relation to Mycelium

- `grill` makes no edits. It never writes `.living/`, manifests, todo, or analysis files. It never runs repository scripts by path, because that would start Mycelium's post-action cycle. Its data checks use inline read-only probes.
- `decision-status` writes to `.living/decisions.md` only after you confirm a resolution, and only by appending. Its parser runs from stdin (`python3 - ... < decision_threads.py`), which the Mycelium 0.6.0 and 0.7.2 hooks do not treat as a post-action run.
- `data-contract-check` is read-only and runs the same way. Its contract stays outside the repository until you approve the plan.
- After you approve a plan, run it through your normal workflow. In a Mycelium project that is `/mycelium:analyze` (`$mycelium:analyze` in Codex), which logs the brief's "Decisions to record" through Mycelium's lifecycle.
- `/mycelium:review grill` reviews an existing analysis or diff; `grill` plans before execution. Use both.

## Development

Tests: `python3 skills/<skill>/tests/test_*.py` and `python3 hooks/tests/test_gate.py`. Bump `version` in `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, and `.claude-plugin/marketplace.json` together, so `claude plugin update` picks up the change.
