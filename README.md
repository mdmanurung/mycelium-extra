# Mycelium Extra

A standalone plugin for planning analysis work before it runs. It works alongside [Mycelium](https://github.com/arjunrajlaboratory/mycelium) but does not fork, modify, or require it.

It has three skills and one hook set:

| Part | What it does | Writes |
|---|---|---|
| `grill` | Turns a proposed task into a sourced, numbered plan | Nothing |
| `decision-status` | Settles which past decision binds a task | Appends to `.living/decisions.md`, after you confirm |
| `data-contract-check` | Tests a plan's sample-table assumptions | Nothing |
| Approval gate | Blocks analysis runs until you approve the plan | `.mycelium-extra/` only |

## grill

`grill` reads the repository before it asks you anything. In a Mycelium project (any repository with `.living/`), it reads `MYCELIUM.md` or the Mycelium block in `CLAUDE.md`/`AGENTS.md`, `.living/INDEX.md`, relevant memory entries, manifests, analysis docs, and code. Elsewhere it reads the project's own docs and code.

It then tests the goal, evidence, assumptions, alternatives, failure modes, and validation. For bioinformatics or statistical work it also walks a list of analysis decisions (unit of replication, matrix state, references, QC, batch, multiplicity, and more), so none stays implicit.

It asks only questions that you own and that could change the plan: one per message, at most five. It ends with `READY`, `READY_WITH_ASSUMPTIONS`, or one `DECISION_REQUIRED` item, plus a numbered plan. Each consequential choice in the plan cites its source: repository evidence, your answer, or a labeled default. Nothing runs until you approve or edit the plan.

## decision-status

Use it when `.living/decisions.md` holds several entries on the same choice, for example a method that was confirmed, then held, then shelved.

- A small read-only parser lists the entries the task touches, oldest first. It shows their raw `Status`, `Supersedes`, `Scope`, and `Revisit when` lines and any status words in headings. It never infers which entry is current.
- An explicit supersession wins. Next comes the entry whose scope matches the task. Anything else is contested and goes to you, at most three questions per session.
- Once you confirm an answer, it appends a `Resolution:` entry so the question does not come back. It never edits existing entries.

The new entry uses the ordinary decision fields plus `Status`, `Supersedes`, `Scope`, `Revisit when`, and `Resolved-by`. Mycelium 0.7.2's scripts do not parse `Status` in `decisions.md`, so they read these fields as plain body text.

## data-contract-check

It checks a plan's assumptions about the sample table before anything runs. The assumptions go into a small JSON contract:

- required columns
- cohort levels and row counts
- one row per unit per cell
- complete pairing across timepoints
- batch versus contrast nesting

A stdlib checker reports each mismatch with expected, observed, and evidence lines, in the shape of ClawBio's contract alerts. The checker, not the contract, decides what blocks: any failure of these kinds blocks. The skill never loosens a contract to make it pass without your agreement. v1 reads CSV/TSV tables; it does not yet check h5ad internals.

## Approval gate

Claude Code hooks in `hooks/` enforce grill's rule that nothing runs until you approve. The gate is off unless you turn it on per repository:

1. Create `.mycelium-extra/gate.json`. `{}` uses the defaults.
2. Add `.mycelium-extra/` to `.gitignore`. It holds short-lived execution state, not project knowledge.

**Approving a plan.** When a reply ends with `Plan status: READY` or `READY_WITH_ASSUMPTIONS`, the Stop hook hashes the plan and shows `approve plan <hash>`. Type exactly that (a trailing `.` is fine) to record the approval in `.mycelium-extra/approvals/`. A bare `approve plan` lists pending hashes and approves nothing.

**What is gated.** Before each Bash call, the gate denies a gated run unless an approval from the last `approval_hours` (default 24) names it. Two kinds of run are gated:

- Scripts under `gated_paths` (default `analysis/**`, `nbs/**`). This covers running them by interpreter, directly, via stdin (`python3 - < analysis/x.py`), `-c "$(cat …)"`, `-m`, after `cd`, or under `conda run`, `srun`, `timeout`, and similar wrappers. The plan must name the script's path, or an enclosing folder at least two levels deep (`nbs/cytof_exvivo/`), as a path token.
- Commands in `gated_commands` (default `sbatch`, `snakemake`, `nextflow`). The plan must contain the command word. Payloads of `bash -c` and `sbatch --wrap` are checked as commands too.

Reading gated files (`cat`, `rg`, `git`) is never gated.

**Exploratory runs.** Type `allow explore` to let runs prefixed with `MYCELIUM_EXTRA_EXPLORE=1` through for this session; type `stop explore` to end it. Without the grant the prefix is denied, so the agent cannot exempt itself. Each explore run is logged, and the Stop hook lists those runs as not reportable. Only the log marks them; their output files carry no label.

**Limits.**

- The gate denies the agent's Write/Edit calls into `.mycelium-extra/` and Bash commands that visibly modify it.
- It passes a command by staying silent and never auto-allows, so your own permission prompts still apply.
- On an internal error it fails open and says so.
- It catches mistakes; it is not security. An agent set on bypassing it through Bash can do so.
- Claude Code only; there is no Codex port yet.

## Use

- **Claude Code, one session:** run `claude --plugin-dir /absolute/path/to/mycelium-extra` from the project you want to examine.
- **Claude Code, installed:** run `claude plugin marketplace add /absolute/path/to/mycelium-extra`, then `claude plugin install mycelium-extra@mycelium-extra` from the project (add `--scope local` to enable it for that project only). Hooks load when a session starts.
- **Codex plugin:** this folder includes `.codex-plugin/plugin.json` and `skills/*/SKILL.md`, ready to add to a Codex plugin marketplace. After installing, invoke `$mycelium-extra:<skill>`.
- **Codex standalone skill:** copy one `skills/<skill>/` folder to your personal Codex skills location and invoke it as `$grill`. Namespacing then depends on how you installed it.

In Claude Code, invoke `/mycelium-extra:grill`, `/mycelium-extra:decision-status`, or `/mycelium-extra:data-contract-check`, followed by your task or plan.

Example: `Grill my plan to redo monocyte pathway analysis across trials; inspect the repo before asking me anything.`

Tests: `python3 skills/<skill>/tests/test_*.py` and `python3 hooks/tests/test_gate.py`.

## Relation to Mycelium

- `grill` makes no edits. It never writes `.living/`, manifests, todo, or analysis files. It never runs repository scripts by path, because that would start Mycelium's post-action cycle. Its data checks use inline read-only probes.
- `decision-status` writes to `.living/decisions.md` only after you confirm a resolution, and only by appending. Its parser runs from stdin (`python3 - ... < decision_threads.py`), which the Mycelium 0.6.0 and 0.7.2 hooks do not treat as a post-action run.
- `data-contract-check` is read-only and runs the same way. Its contract stays outside the repository until you approve the plan.
- After you approve a plan, run it through your normal workflow. In a Mycelium project that is `/mycelium:analyze` (`$mycelium:analyze` in Codex), which logs the brief's "Decisions to record" through Mycelium's lifecycle.
- `/mycelium:review grill` reviews an existing analysis or diff; `grill` plans before execution. Use both.
