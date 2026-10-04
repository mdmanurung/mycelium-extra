# Skills

[Back to README](../README.md)

`grill` calls `decision-status` and `data-contract-check` itself when a plan depends on them, so you rarely need to invoke those directly.

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

## grill

`grill` reads the repository before it asks you anything. In a Mycelium project (any repository with `.living/`), it reads `MYCELIUM.md` or the Mycelium block in `CLAUDE.md`/`AGENTS.md`, `.living/INDEX.md`, relevant memory entries, manifests, analysis docs, and code. Elsewhere it reads the project's own docs and code.

It then tests the goal, evidence, assumptions, alternatives, failure modes, and validation. For bioinformatics or statistical work it also walks a list of analysis decisions (unit of replication, matrix state, references, QC, batch, multiplicity, and more), so none stays implicit.

It asks only questions that you own and that could change the plan: one per message, at most five. It ends with `READY`, `READY_WITH_ASSUMPTIONS`, or one `DECISION_REQUIRED` item, plus a numbered plan. Each consequential choice in the plan cites its source: repository evidence, your answer, or a labeled default. An `Inputs:` line names the files the plan rests on, which the approval gate pins. Nothing runs until you approve or edit the plan.

## plan-review

Run this after grill and before approving a changed plan. Claude Code assembles one minimal, sourced packet and asks Codex for an engineering critique and a connected Phylo Biomni MCP for a biomedical critique. It shows you the packet and sends it only after you agree, since it leaves the machine. Biomni has no lookup-only tool, so its review is one consult-only Biomni task: no file uploads, run in Biomni's cloud at the cost of your Biomni credits, and treated as advice, never as a project result. If a reviewer is missing, fails, or is unsafe to invoke, it is reported unavailable. Claude keeps agreement, disagreement, and its reasons for accepting or rejecting recommendations visible. The skill edits no files, records no run receipts, and does not add an approval. A revised plan requires normal approval. Invoking the skill in Codex returns the Codex critique only, since Codex cannot be its own independent second reviewer or Claude adjudicator.

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

## init

`init` turns on the approval gate in a repository. It writes `.mycelium-extra/gate.json` and adds `.mycelium-extra/` to `.gitignore`. See [Approval gate](approval-gate.md) for what it checks, how to turn the gate on by hand, and what the gate then enforces.

## verify

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

## new-analysis

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

- **Steps.** The numbered steps sit at the folder root, so their order is visible at a glance. Each one is a stub that states its input and output, sets a seed, and stops with an error until you write it.
- **`<NAME>.md`.** It comes from Mycelium's `analysis-readme.md` template, found through `.mycelium/plugin-root`, or from a bundled copy. `/mycelium:analyze` reads it, Mycelium's post-action hook updates it, and `validate_structure.py` checks that it exists. Results go in its Key Findings section, citing `outputs/` files and `.living/findings` IDs. Outside a Mycelium repository the doc is `README.md`.
- **`PLAN.md`.** It uses the grill brief's headings, so an approved brief goes straight in. Revise it in place; never start a second plan file.
- **Snakefile.** It runs from the analysis folder, so every path is relative to it. The interpreters default to `Rscript`, `python`, and `jupyter` on PATH; override them with `--config`.
- **Safety.** It refuses a non-empty folder, bad step names, and missing link targets. It never overwrites. It warns when git would ignore a file it creates, for example in a repository that ignores `analysis/*/results/`.
- **Mycelium's files.** It writes nothing to `.living/` or the manifests. It prints a suggested `ANALYSIS_MANIFEST.md` entry. `/mycelium:analyze <name>` then continues the folder as an existing analysis and records it.

The robust-analysis protocols save figures to subfolders such as `outputs/figures/diagnostic/`. A flat `outputs/` holds only after you record it as a repo-local convention, which Mycelium applies before domain and core conventions.

## handoff

`handoff` writes `HANDOFF.md` at the project root so you can `/clear` and continue in a fresh session without carrying the old context. It records the goal, the exact next action, current state, decisions you locked in, dead ends not to redo, and a few `path:line` pointers to read first. It overwrites the previous handoff, keeps only what still holds, and stays under about 80 lines: it points to code and commits instead of copying them. It ends with a one-line resume prompt (`Read HANDOFF.md, then ...`).

In a Mycelium project it links to `.mycelium/last-session.md` and `.living/` entries rather than copying them, and never writes to Mycelium's files. It does not commit the handoff or change `.gitignore`.

## harden

`harden` turns one Mycelium learning into a test. It lists learnings still marked `ambient-awareness` whose `structural_mitigation_candidate` names a concrete check (at most five, newest first), and you pick one. It writes the test in the repository's own test setup, never under the gate's gated paths and never in analysis code, and shows two runs: the test must fail on a minimal reproduction of the original problem and pass on the current code. If it cannot fail, it guards nothing and the learning stays as it was. After you confirm, it sets that entry's `mitigation_type` to `structural` and notes the test path on its candidate line. Mycelium's `detect_recurrence.py` flags candidates; `harden` ships them.
