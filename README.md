# Mycelium Extra

A standalone plugin for planning analysis work before it runs. It works alongside [Mycelium](https://github.com/arjunrajlaboratory/mycelium) but does not fork, modify, or require it.

It has nine skills and one hook set:

| Part | What it does | Writes |
|---|---|---|
| `grill` | Turns a proposed task into a sourced, numbered plan | Nothing |
| `plan-review` | Challenges a grill plan with independent Codex engineering and Biomni biomedical reviews before approval | Nothing |
| `decision-status` | Settles which past decision binds a task | Appends to `.living/decisions.md`, after you confirm |
| `data-contract-check` | Tests a plan's sample-table assumptions | Nothing |
| `init` | Turns on the approval gate in a repository | `.mycelium-extra/gate.json`, `.gitignore` |
| `new-analysis` | Creates a new analysis folder: numbered steps, a Snakefile, Mycelium's analysis doc, one plan, one tracker | The new folder only |
| `verify` | Checks an approved plan against what ran, then records provenance | `<analysis>/provenance/`, after you confirm |
| `handoff` | Writes a short handoff so a fresh session can continue | `HANDOFF.md` at the project root |
| `harden` | Ships a Mycelium learning's mitigation candidate as a real test | One test file; one `.living/learnings.md` entry, after you confirm |
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

- **Plugin:** this folder includes `.codex-plugin/plugin.json` and `skills/*/SKILL.md`, ready to add to a Codex plugin marketplace. After installing, invoke `$mycelium-extra:<skill>`. The Codex manifest disables the Claude-only approval-gate hooks, so Codex does not load them from `hooks/hooks.json`. In Codex, `plan-review` provides the engineering critique only; Claude Code leads the two-reviewer synthesis.
- **Standalone skill:** copy one `skills/<skill>/` folder to your personal Codex skills location and invoke it as `$grill`. Namespacing then depends on how you installed it.

The approval gate, `init`, and `verify` are Claude Code only.

## Quick start

A typical analysis task, in order:

1. **Once per repository:** `/mycelium-extra:init` turns on the approval gate.
2. **Plan:** `/mycelium-extra:grill <your task>`. Answer its questions (at most five).
3. **Optional review:** before approval, invoke `/mycelium-extra:plan-review` in Claude Code for separate Codex and Biomni critiques. It recommends amendments but does not edit or approve the plan.
4. **Approve:** after any requested revision, use the new plan's `approve plan <hash>` line.
5. **Run and verify:** execute through your normal workflow (`/mycelium:analyze` in a Mycelium project), then use `/mycelium-extra:verify <hash>`.
6. **Optional run plan:** for a reportable, long, or HPC run, grill again once the code is written and linted. The run plan lists the Snakefile, `run.sh`, and step scripts on its `Inputs:` line so the gate freezes them, and shows a dry run (`bash run.sh -n`, under the first plan's approval) and tool versions. `verify diff <old> <new>` shows what changed before you approve it. See `skills/grill/references/run-plans.md`.

Common prompts:

| Goal | Prompt |
|---|---|
| Plan a task from repo evidence | `/mycelium-extra:grill Redo monocyte pathway analysis across trials; inspect the repo before asking me anything.` |
| Challenge a draft before approval | `/mycelium-extra:plan-review Review the current grill plan with Codex and Biomni.` |
| Settle conflicting past decisions | `/mycelium-extra:decision-status Which batch-correction decision binds the integration rerun?` |
| Check the sample table before running | `/mycelium-extra:data-contract-check Check the approved plan's cohort, pairing, and batch assumptions against the sample table.` |
| Turn on the gate | `/mycelium-extra:init` |
| Start a new analysis folder | `/mycelium-extra:new-analysis analysis/gdt-seminmf-dream: does semi-NMF program usage differ by arm? Link data/anndatas/gdt.h5ad.` |
| Check a run against its plan | `/mycelium-extra:verify 99ddfd42` |
| Turn a learning into a test | `/mycelium-extra:harden` |
| Continue in a fresh session | `/mycelium-extra:handoff`, then `/clear` and paste the resume line it prints |
| Get next-command suggestions | `hints on` (and `hints off`) |
| Run a quick test without a plan | Type `allow explore`; type `stop explore` when done. |
| Make explore runs reportable | Say "promote explore runs"; approve the re-run plan grill drafts. |

`grill` calls `decision-status` and `data-contract-check` itself when a plan depends on them, so you rarely need to invoke those directly.

## Skills

### plan-review

Run this after grill and before approving a changed plan. Claude Code assembles one minimal, sourced packet and asks Codex for an engineering critique and a connected Phylo Biomni MCP for a biomedical critique. It shows you the packet and sends it only after you agree, since it leaves the machine. Biomni has no lookup-only tool, so its review is one consult-only Biomni task: no file uploads, run in Biomni's cloud at the cost of your Biomni credits, and treated as advice, never as a project result. If a reviewer is missing, fails, or is unsafe to invoke, it is reported unavailable. Claude keeps agreement, disagreement, and its reasons for accepting or rejecting recommendations visible. The skill edits no files, records no run receipts, and does not add an approval. A revised plan requires normal approval. Invoking the skill in Codex returns the Codex critique only, since Codex cannot be its own independent second reviewer or Claude adjudicator.

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

### verify

After an approved plan has run, `verify <hash>` compares the plan with the gate's receipts. It reuses the gate's own table parser, so a plan covers exactly the scripts it let through. Its report shows:

- Each planned script: ran, failed, no receipt, edited or deleted since it ran, or only passed to other code. A lint or parse call (`Rscript -e 'lintr::lint()' x.R`) or another tool's script read from stdin gets the path but does not run it, so it is not counted as a run. Steps run inside a `run.sh` or Snakemake wrapper are matched through Snakemake's per-output records, and Slurm jobs through `sacct`.
- Explore runs, runs under another plan, and scripts in the analysis folder that ran but are not in the plan table.
- Pinned inputs that changed since the approval.
- The files on the plan's `Outputs:` line: when each was written and which run likely wrote it. A file named exactly that was written before the approval blocks. Older files inside a named folder or glob are earlier runs' outputs, so they are counted, not checked.
- Scripts that Mycelium's lineage saw run in the window but the gate did not, such as scratchpad scripts.
- scilintr on the analysis folder's code (Python and R CLIs), as Mycelium's analyze skill requires, with every `ANALYSIS_OK` waiver listed. Jupyter notebooks' code cells are linted too, with magics commented out; a finding is cited as `<notebook>.ipynb[code cell N]:<line>`. The `{r}` and `{python}` chunks of `.qmd` and `.Rmd` files are linted as well, cited by the document's own line.

It ends with `Verify status: CONFORMS`, `CONFORMS_WITH_GAPS`, or `DOES_NOT_CONFORM`.

- **Blocks:** a failed run, an edited script, a changed input, an output older than the approval, an incomplete Snakemake job, or a scilintr finding neither fixed nor waived.
- **Gaps:** things the records cannot show, including code scilintr could not check (not installed, timed out, unreadable output, or a script or notebook whose code does not parse under the Python verify runs on, which scilintr would silently pass). An output is tied to a run by time alone, so attribution only ever produces gaps.

After you confirm, `verify` writes `<analysis>/provenance/`: the frozen plan, its receipts (ones that only passed a planned path to other code are kept, marked `not_a_run`), an outputs table with each file's size, full sha256, and likely run, the scilintr output and waivers (`lint-<hash>.txt`), the package list of any conda env a run used that no `conda-lock.yml` pins (`env-<hash>.txt`, read from the env's `conda-meta`; an env changed since the run is a gap), the report, and a `PROVENANCE.md` index. Commit it with the analysis. It never writes `PLAN.md`, `TRACKER.md`, or `specification.md`, so the analysis keeps one plan file. It then names the review command, `/mycelium:review <folder> — check the code against the approved plan in <folder>/provenance/plan-<hash>.md`.

`verify stale` sweeps every verified plan and lists the ones whose scripts, pinned inputs, or outputs changed since their provenance was written, with a ready `rg` command that finds the findings resting on each one in `.living/findings/` by session ID or plan hash. After a planned run in a Mycelium repository, the gate suggests writing the finding's Evidence Ledger Run/Session cell as `<session-id>; plan <hash>`; Mycelium reads only the ledger's date cell. It reads only committed provenance, so it works without the gate on any clone; outputs are compared by size and time, not hashed.

`verify status` is an on-request overview: one row per approved or verified plan, with its analysis folder, runs, verify status, staleness, the lint verify recorded (a missing or unreadable linter shows as a gap, never `clean`), and the folder's `ANALYSIS_MANIFEST.md` entry (`listed: <first status word>`, `listed`, or `not listed`). It reads Mycelium's YAML `status:`, `**Status**:` lines, and a table's Status cell. No hook runs it.

verify was first run on real receipts on 2026-10-02 (42 receipts, three plans, Rscript, sbatch, and Snakemake runs). Four bugs it showed are fixed. One limit remains: an output is tied to a run by time, and a planned script that is only a Snakemake rule's input (not its step script) is still counted as run in that rule.

### new-analysis

It creates the folder a new analysis lives in. It uses Mycelium's own pieces and adds only what Mycelium lacks.

```
analysis/<name>/
├── 01_prepare_data.R  02_train_model.py  03_explore_model.ipynb
├── Snakefile      # runs the steps in number order
├── run.sh         # Mycelium's entry point; calls snakemake
├── <NAME>.md      # Mycelium's analysis doc, plus a Steps table
├── PLAN.md        # the one plan for this analysis
├── TRACKER.md     # status of each plan item, and a dated log
├── data/  code/   # symlinks to data and shared code
├── outputs/       # flat; file names start with the step number
├── logs/          # Snakemake and SLURM logs, executed notebooks
└── reports/       # Mycelium's report skill
```

- **Steps.** The numbered steps sit at the folder root, so their order is visible at a glance. Each one is a stub that:
  - states its input and output
  - sets a seed
  - stops with an error until you write it
- **`<NAME>.md`.**
  - It comes from Mycelium's `analysis-readme.md` template, found through `.mycelium/plugin-root`, or from a bundled copy.
  - `/mycelium:analyze` reads it, Mycelium's post-action hook updates it, and `validate_structure.py` checks that it exists.
  - Results go in its Key Findings section, citing `outputs/` files and `.living/findings` IDs.
  - Outside a Mycelium repository the doc is `README.md`.
- **`PLAN.md`.** It uses the grill brief's headings, so an approved brief goes straight in. Revise it in place; never start a second plan file.
- **Snakefile.** It runs from the analysis folder, so every path is relative to it. The interpreters default to `Rscript`, `python`, and `jupyter` on PATH; override them with `--config`.
- **Safety.**
  - It refuses a non-empty folder, bad step names, and missing link targets.
  - It never overwrites.
  - It warns when git would ignore a file it creates. In scale, for example, `analysis/*/docs/` and `analysis/*/results/` are ignored.
- **Mycelium's files.** It writes nothing to `.living/` or the manifests. It prints a suggested `ANALYSIS_MANIFEST.md` entry. `/mycelium:analyze <name>` then continues the folder as an existing analysis and records it.

The robust-analysis protocols save figures to subfolders such as `outputs/figures/diagnostic/`. A flat `outputs/` holds only after you record it as a repo-local convention, which Mycelium applies before domain and core conventions.

### handoff

`handoff` writes `HANDOFF.md` at the project root so you can `/clear` and continue in a fresh session without carrying the old context. It records the goal, the exact next action, current state, decisions you locked in, dead ends not to redo, and a few `path:line` pointers to read first. It overwrites the previous handoff, keeps only what still holds, and stays under about 80 lines: it points to code and commits instead of copying them. It ends with a one-line resume prompt (`Read HANDOFF.md, then ...`).

In a Mycelium project it links to `.mycelium/last-session.md` and `.living/` entries rather than copying them, and never writes to Mycelium's files. It does not commit the handoff or change `.gitignore`.

### harden

`harden` turns one Mycelium learning into a test. It lists learnings still marked `ambient-awareness` whose `structural_mitigation_candidate` names a concrete check (at most five, newest first), and you pick one. It writes the test in the repository's own test setup, never under the gate's gated paths and never in analysis code, and shows two runs: the test must fail on a minimal reproduction of the original problem and pass on the current code. If it cannot fail, it guards nothing and the learning stays as it was. After you confirm, it sets that entry's `mitigation_type` to `structural` and notes the test path on its candidate line. Mycelium's `detect_recurrence.py` flags candidates; `harden` ships them.

### Approval gate

Claude Code hooks in `hooks/` enforce grill's rule that nothing runs until you approve. The gate is off unless you turn it on per repository with `/mycelium-extra:init`, or by hand:

1. Create `.mycelium-extra/gate.json`. `{}` uses the defaults.
2. Add `.mycelium-extra/` to `.gitignore`. It holds short-lived execution state, not project knowledge.

`init` checks whether the default paths exist and asks which folders to gate if they don't. It never changes a gate that is already on; after that, edit `gate.json` by hand.

**Approving a plan.** When a reply ends with `Plan status: READY` or `READY_WITH_ASSUMPTIONS`, the Stop hook hashes the plan and shows `approve plan <hash>`. The notice also lists which gated scripts, folders, and commands the plan would let run. Type exactly that (a trailing `.` is fine) to record the approval in `.mycelium-extra/approvals/`. A bare `approve plan` lists pending hashes and approves nothing.

**What is gated.** Before each Bash call, the gate denies a gated run unless an approval from the last `approval_hours` (default 24) names it. Approvals are never deleted, so `verify` can check old plans. If reading them takes longer than 5 s, the gate blocks the run and says why instead of letting it through unchecked. Two kinds of run are gated:

- Scripts under `gated_paths` (default `analysis/**`, `nbs/**`). This covers running them by interpreter, directly, via stdin (`python3 - < analysis/x.py`), `-c "$(cat …)"`, `-m`, after `cd`, or under `conda run`, `srun`, `timeout`, and similar wrappers. The plan table must name the script's path, or an enclosing folder at least two levels deep (`nbs/cytof_exvivo/`), as a path token.
- Commands in `gated_commands` (default `sbatch`, `snakemake`, `nextflow`). The plan table must contain the command word. Payloads of `bash -c` and `sbatch --wrap` are checked as commands too.

A dry run (`snakemake -n`, `bash run.sh -n`) is gated like any run: a Snakefile is Python, and Snakemake runs its top-level code and input functions while building the job list.

Only the plan table counts. A path or command word in the brief's prose, its Evidence, a Source column, or a `repo:` citation approves nothing, so a plan that cites a script as evidence does not approve running it. A plan with no table approves nothing, and the approval notice says so.

Reading gated files (`cat`, `rg`, `git`) is never gated.

**Pinned inputs.** A grill brief has an `Inputs:` line naming, by repository path, the files the plan rests on: the sample table, config or params files, a lockfile, or a folder of raw files. When the Stop hook shows `approve plan <hash>`, it also fingerprints those files and lists them.

- A file gets a sha256 while the per-hook budget lasts: `pin_hash_mb` bytes (default 200) and `pin_seconds` seconds (default 5) in `gate.json`. After that it gets size and mtime.
- A folder gets a fingerprint of its file names, sizes, and mtimes, up to 5,000 files. Contents are not read. A folder the time limit cuts off is named as not pinned.
- If the time limit cuts off the check before a run, the run goes ahead and the gate names the inputs it did not re-check.
- A path outside the repository is named in the notice and not pinned. Symlinks inside the repository are followed.
- Showing the same plan again re-pins it, and the notice names any file that changed since the plan was last shown.
- A plan with no `Inputs:` line pins nothing, and the notice says so.

Approving copies the pins into the approval. Before a covered run, the gate fingerprints the pins of the newest approval that covers it (so an older plan that pinned less cannot let a run through after a newer plan's pins changed) and blocks the run if one changed, naming the file with its old and new fingerprint. Re-check the input (for example, re-run the data-contract check), show the plan again, and approve it. Explore runs skip this check.

**Run receipts.** After each gated Bash call, a PostToolUse hook appends one line per run to `.mycelium-extra/receipts.jsonl` (schema `mycelium-extra.receipt.v1`). A receipt holds:

- The approved plans that cover the run and their pins, or none. `pins_checked` is false for explore runs, which skip the pin check.
- Git HEAD, whether tracked files have uncommitted changes, and whether each recorded file is committed, modified, untracked, or ignored.
- The script's fingerprint (or the sha256 of an `sbatch --wrap` payload), and its `module load`, `conda activate`, and `#SBATCH` lines.
- Lockfiles (`renv.lock`, `pixi.lock`, `environment.yml`, and similar) in the repository root, the working directory, and the script's folder.
- The environment the hook itself runs in (`hook_env`), and any `conda run -n` environment in the command (`command_env`).
- For `sbatch`, the job ID. For snakemake and nextflow, the Snakefile or pipeline, config and params fingerprints, report and trace paths, the nextflow run name, and a pointer to the engine's own record (`.snakemake/metadata`, `.nextflow/history`).
- The exit status when Claude Code reports one, and the key names of its Bash result (`response_keys`).

**Mycelium's post-action protocol.** Mycelium's own hooks detect only python, R, and jupyter runs. In a repository with `.living/`, after a receipted run Mycelium does not detect (`bash run.sh`, snakemake, sbatch, nextflow, and other runners), the receipt hook tells the agent once that the protocol did not fire, and to follow it (learnings, decisions, findings, manifest, analysis doc) when the run finishes. It is a reminder; Mycelium's Stop hook still does not see these runs.

Receipts stay in `.mycelium-extra/`, which is gitignored, so they do not trip Mycelium's Stop hook. `verify` copies a plan's receipts into the analysis folder after you confirm.

**Exploratory runs.** Type `allow explore` to let runs prefixed with `MYCELIUM_EXTRA_EXPLORE=1` through for this session; type `stop explore` to end it. Without the grant the prefix is denied, so the agent cannot exempt itself. Each explore run is logged, and the Stop hook lists those runs as not reportable. To make them reportable, say "promote explore runs": grill lists this session's explore runs (`verify explore`, prefix removed, scripts edited since flagged) and drafts a normal plan that re-runs them, for the usual approval. Explore outputs are never promoted to results. After each one, the receipt hook tells the agent the run is not reportable, so a learning or finding it records from the run (for example under Mycelium's post-action protocol) is labeled `Exploratory run (not reportable)`. Output files carry no label.

**Command hints.** Type `hints on` to get a one-line suggestion of the command to run next; `hints off` stops them. The setting lasts for the repository until you turn it off. Hints need the gate (`init`), since the gate's hooks carry them.

- When you send a prompt that matches a task type, the agent is told which command fits and names it in one line, asking before it switches. Rules, first match wins: wrap up or new session → `handoff`; new analysis folder → `new-analysis`; which decision binds → `decision-status`; sample table → `data-contract-check`; brainstorm → `/mycelium:ideas`; ingest → `/mycelium:ingest`; report or write-up → `/mycelium:report`; review or audit → `/mycelium:review`; analysis words with no active approval → `grill`. The `/mycelium:*` rules apply only where `.living/` exists. Prompts that start with `/` or name `mycelium` get no hint.
- When a turn ends, you alone see (the agent does not, so it costs no tokens): `verify <hash>` once a gated run under that plan has a receipt this session, and `handoff` once the context passes 120k tokens. Each shows once per session.
- Hints match keywords, so some miss or misfire.

**Limits.**

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

## Relation to Mycelium

- `grill` makes no edits. It never writes `.living/`, manifests, todo, or analysis files. It never runs repository scripts by path, because that would start Mycelium's post-action cycle. Its data checks use inline read-only probes.
- `decision-status` writes to `.living/decisions.md` only after you confirm a resolution, and only by appending. Its parser runs from stdin (`python3 - ... < decision_threads.py`), which the Mycelium 0.6.0 and 0.7.2 hooks do not treat as a post-action run.
- `data-contract-check` is read-only and runs the same way. Its contract stays outside the repository until you approve the plan.
- `new-analysis` writes only inside the new folder. Its script also runs from stdin. The folder uses Mycelium's layout (`<NAME>.md`, `outputs/`, `reports/`, `run.sh`) plus a plan, a tracker, a Snakefile, and `data/` and `code/` links, so `/mycelium:analyze` continues it as an existing analysis rather than building a second skeleton.
- After you approve a plan, run it through your normal workflow. In a Mycelium project that is `/mycelium:analyze` (`$mycelium:analyze` in Codex), which logs the brief's "Decisions to record" through Mycelium's lifecycle.
- `verify` reads Mycelium's lineage but never writes `.living/`. Its report is read-only. Its `write` step runs from stdin and writes only `<analysis>/provenance/`. Those new files make Mycelium's Stop hook ask for a `.living/` update, where you record the verify status through Mycelium's normal logging.
- `/mycelium:review grill` reviews an existing analysis or diff; `grill` plans before execution. Use both.

## Development

Tests: `python3 skills/<skill>/tests/test_*.py` and `python3 hooks/tests/test_gate.py`. Before changing `hooks/gate.py`, also run `python3 hooks/tests/gate_diff.py`: it sends the same events to the committed gate and the working tree and must report every case identical, except the decisions you meant to change. Hooks call bare `python3`, which is 3.6 on some HPC systems, so keep every script 3.6-compatible; the gate tests compile them all under `python3.6` when it is installed. Bump `version` in `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, and `.claude-plugin/marketplace.json` together, so `claude plugin update` picks up the change.
