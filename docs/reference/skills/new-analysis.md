# new-analysis

Scaffolds a new, self-contained analysis folder that plugs into Mycelium. Guide: [Plan an analysis](../../guides/plan-an-analysis.md). It is not for turning the gate on ([init](init.md)) or continuing an existing analysis (Mycelium's `analyze`).

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`).

```bash
sh <skill-dir>/../../hooks/py.sh - --dest=analysis/<name> [--steps=01_a.R,02_b.py,03_c.ipynb] [--data=PATH ...] [--code=PATH ...] [--doc-template=FILE] [--panels=Fig1a.R,...] [--wrapper=NN_name:skill-name ...] --templates=<skill-dir>/templates [--dry-run] < <skill-dir>/scripts/new_analysis.py
```

Invoke with `/mycelium-extra:new-analysis analysis/<name>: <question>`. Write every option as `--flag=value`: the gate reads a bare `analysis/...` argument as a script being run and blocks it. Never run the script by path.

## Options

| Option | Meaning |
|---|---|
| `--dest` | Folder to create (required). In a Mycelium repository use `analysis/<name>/`, lowercase with hyphens. |
| `--steps` | Comma-separated `NN_name.R`, `.py`, `.ipynb`, `.qmd` or `.marimo.py`, numbered in increasing order. A name with no extension takes `--format`. Default `01_prepare.R,02_fit.R,03_show.R`, or the same names with the `--format` extension. |
| `--format` | `R`, `py`, `ipynb`, `qmd` or `marimo`: the extension of the default steps and of bare names. Default: `step_format` in `.mycelium-extra/gate.json`, else none (the mixed default above). |
| `--lang` | `r` (default, knitr) or `python` (jupyter): the language of qmd steps. |
| `--data` | File or folder to link into `data/` (repeatable). |
| `--code` | File or folder to link into `code/` (repeatable). |
| `--doc-template` | Analysis doc template. Default: Mycelium's `analysis-readme.md`, found through `.mycelium/plugin-root`, else a bundled copy. |
| `--panels` | Comma-separated manuscript panels, `<id>.R` or `<id>.py`. Adds a `code/plot_<id>` stub per panel, `config/figure_map.tsv` and `config/manuscript_checks.json` for [manuscript-audit](manuscript-audit.md). Needs a git or Mycelium repository. On an existing folder it adds only the missing manuscript files. |
| `--wrapper` | `NN_name:skill-name`, repeatable. Adds `code/NN_name.sh`, a stub that runs a pipeline skill's script through `${CLAUDE_PLUGIN_ROOT}/skills/<skill>/...` and writes only `outputs/NN_name/`, plus a plan row and a tracker row. It is not in the Snakefile. The number and name must not repeat a step's. New scaffolds only. |
| `--templates` | This skill's `templates/` folder (required when run from stdin). |
| `--dry-run` | Report what would change; write nothing. |
| `--migrate` | Move an existing run-folder analysis (`--dest`) to step folders. See [Migrating a run-folder analysis](#migrating-a-run-folder-analysis). |
| `--apply` | With `--migrate`: install the `.new` files and keep the originals as `*.pre-0.27`. |
| `--seed` | With `--migrate`: `step=run,step=run`. Copy each step's declared outputs from `outputs/<run>/`. |

## What it creates

```
analysis/<name>/
  <NAME>.md  Snakefile  run.sh  run.sbatch     analysis doc (README.md outside Mycelium); `bash run.sh` runs the steps and logs changes
  code/      01_prepare.R  02_fit.R  03_show.R   numbered step stubs; 03_show writes figures/ and source_data/
             theme.R  theme.py                  the theme (your learned rule, else theme_pubr), PALETTE, save_panel()
             NN_name.sh                        (--wrapper) calls a pipeline skill's script
             plot_<panel>.R|.py                (--panels) export the plotted values, then draw from them alone
  plans/     PLAN.md  TRACKER.md               the one plan, the tracker
  config/    figure_map.tsv  manuscript_checks.json   (--panels) what manuscript-audit checks
  reports/   README.md  <name>.qmd         file index; Quarto report skeleton, filled by analysis-report
  data/      <links>  SOURCES.md           one row per --data link
  outputs/   <step stem>/                  one folder per script, e.g. 01_prepare/; a rerun overwrites it
  logs/      CHANGES.md  .code-hashes.tsv  SLURM output; CHANGES.md has one entry per run
```

The layout is [analysis-layout](../../concepts/analysis-layout.md). Each script writes to `outputs/<script stem>/` and a rerun overwrites that folder. A qmd step renders its HTML there too (`outputs/05_figures/05_figures.html`). Notebooks and figure scripts get `STEP_DIR` (their own folder) and `OUTPUTS` (the `outputs/` root). `run.sh` takes no slug and writes no `RUN.txt`; after a real run it appends the changed `code/` files and the rewritten step folders to `logs/CHANGES.md`. Run folders of older analyses stay readable.

A `NN_name.marimo.py` step (or `--format=marimo`) is a marimo notebook in lucid-coder's notebook layout, run headless by the Snakefile as a Python script.

The Snakefile runs R and Python with the interpreters `lucid-coder.yaml` names at the repository root (`env.r`, `env.python`, and `jupyter` beside that `python`), each only if the file exists; without the file it uses the names on PATH, and the script prints which. The pixi form that `/lucid-coder:align` writes has only `manager`, `name` and `prefix`. The interpreters are then `<prefix>/bin/Rscript` and `<prefix>/bin/python`, and a pixi env with no prefix is looked up in `.pixi/envs/<name>`. If the env lacks one, the name on PATH stays and the script suggests `pixi run -e <name> bash run.sh`. `init --diagnose` shows the same pointer. `init --tools` falls back to the env's Rscript and `scilintr` when no flag or environment variable names one.

Every stub opens with Purpose, Run, Inputs and Outputs, has a `# Parameters ---` block and 80-column dividers, and writes session info last. The R stubs name their `stopifnot`. Stubs still stop on purpose.

`data/` holds symlinks only; `code/` holds the stubs and links to shared code. The analysis doc is `<NAME>.md` (folder name in UPPER_SNAKE_CASE) in a Mycelium repository, `README.md` elsewhere. Stubs stop until implemented. A panel stub writes `<run>/source_data/<panel>.tsv`, then re-reads only that table to draw `<run>/figures/<panel>.pdf`, so the released source data can redraw the panel; its toy `donor`/`label`/`y` columns are placeholders, and the contract points at `outputs/panels/`. `reports/<name>.qmd` is a static Quarto report (`engine: markdown`) with a mermaid chain of the steps and one Methods and one Results tab per step; [analysis-report](analysis-report.md) fills it after a run, and Mycelium's `report` writes its LaTeX PDF beside it. Without `--panels` it refuses a non-empty folder; with it, it adds each missing manuscript file and keeps every existing file unchanged. It also refuses a missing link target and anything it would overwrite (`refused:` line, nothing written). A `WARNING: git ignores ...` line means that file would never be committed; stop and ask. It writes nothing outside the new folder except an empty `.<name>.scaffold.lock` file in its parent folder (the lock that keeps two runs from filling the same folder; delete it if you like): not `.living/`, not `analysis/ANALYSIS_MANIFEST.md` (it prints a suggested manifest entry).

### The theme

`theme.R` and `theme.py` take the theme from your learned rules. The script runs `node <lucid-coder>/scripts/rules.js list --status active --json` (found through `~/.claude/plugins/installed_plugins.json`; read only). When an active `fig.theme` rule scoped to the stub's language holds a `theme_set(...)` call, that call goes into the file, the package it names is loaded, and the script prints `theme from learned rule <id>`. A call with `;`, a backtick, `system(` or similar is not written. Otherwise `theme.R` sets `ggpubr::theme_pubr(base_size = 8)`, `theme.py` uses plotnine's `theme_classic(base_size=8)`, and a note says why. The lookup fails open: no lucid-coder, no `node`, a run over 5 seconds, bad JSON or no rule each give the fallback and never an error.

The analysis doc's Steps section tells Mycelium's agent that scripts live in `code/` and each writes only `outputs/<its stem>/`.

## Migrating a run-folder analysis

`--migrate` moves an analysis whose `Snakefile` sets `RUN`, `OUT` and `BASE` and whose results sit in `outputs/run_<date>_<slug>/` to the step-folder layout. Run it with `--dest=<existing analysis>`. It never edits a file in place, never edits `code/` and never deletes a run folder.

By default it writes only new files next to the originals and prints a diff of `Snakefile` against `Snakefile.new`:

| File | Content |
|---|---|
| `Snakefile.new` | The rewritten workflow. |
| `run.sh.new`, `run.sbatch.new` | The current templates. |
| `_quarto.yml.new` | The current template, when the folder has `_quarto.yml` or a qmd step. |
| `MIGRATE.md` | Rules rewritten, unmapped paths, a `file:line` checklist of cross-step reads in `code/`, suggested `.gitignore` lines, the mixed-layout warning. |

The rewrite is mechanical:

- The `RUN`/`OUT`/`BASE` block and the `run` config requirement go. Interpreters, threads, resources, SLURM settings and wildcard constraints stay as written.
- A step folder is `outputs/<stem>/`, with the stem taken from the rule's `script=` input. `{OUT}/<path>` becomes `outputs/<stem>/<path>`. A results folder that carries the step number, such as `01b_scar` for the script `01b_scar-denoise`, becomes the step folder.
- Logs and benchmarks go to `outputs/<stem>/logs/`.
- `{BASE}/<name>` and `{OUT}/<name>` in an input map to the rule that declares the file, else to the one rule whose script has the same step number as the file name.
- `RUN_DIR={OUT:q}` becomes `STEP_DIR=outputs/<stem> OUTPUTS=outputs`. A qmd step gets the scaffold's render command and its page at `outputs/<stem>/<stem>.html`, not under `reports/site/`.
- A path that maps to no rule, and a bare `{BASE}` or `{OUT}` argument, keep a `# MIGRATE: check` comment and are listed in `MIGRATE.md`.

Read the diff and `MIGRATE.md`, fix each marked line in `Snakefile.new`, edit `code/` and `.gitignore` yourself, then run again with `--apply`. Under the scaffold's lock, each original is renamed to `*.pre-0.27` and the new file takes its place. An edited `Snakefile.new` is installed as it stands. It refuses when a `*.pre-0.27` file exists.

`--seed` copies the files each rule declares as outputs out of a run folder into the step folder. It copies, never moves, and skips a file that exists. It writes `outputs/.layout` and a `migrated` entry in `logs/CHANGES.md`. It needs `--apply` in the same call, or an earlier apply. No single run holds every step of an older analysis, so name the run for each step: `--seed=01=run_20261111_baseline,06=run_20261112_gatecheck`.

Once step folders exist, the resolver lists them first and the old run folders after. A downstream analysis that points at an old run folder keeps working, because it uses that path directly. `logs/.code-hashes.tsv` is absent after a migration, so the first `run.sh` entry lists every file in `code/` as new.

It refuses a folder with no `Snakefile`, a folder that already has `outputs/.layout`, and a symlinked `code/` or `outputs/`.

## Before it writes

The agent asks for the aim, and the claim you hope to make, in your own words, unless the invocation states them. It shows your words beside a tidier restatement. It checks the aim's assumptions against the repository by reading files: a prior analysis that already answers it, the named data, overloaded terms. It asks at most three questions the repository cannot settle, then waits for you to confirm or edit the aim.

## Afterwards

The agent writes your words and your hoped-for claim, tagged `[human-stated]`, and the confirmed aim into the Purpose of `<NAME>.md` and fills its Steps table. It copies an approved grill brief into `PLAN.md` and `TRACKER.md` when one exists in the conversation. `PLAN.md` records no plan hash. Each R step opens with a `scilintr stage` line; the stage is your choice. Next: [grill](grill.md) a plan naming this folder's scripts or `run.sh`, then Mycelium's `analyze`.

## Default on or off

On when invoked.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| Never overwrites; refuses non-empty folders and missing link targets | Enforced by the script |
| Restating and checking the aim, and waiting for you to confirm it | The agent's instruction |
| Reading the dry run and asking you before writing | The agent's instruction |
| Filling `PLAN.md` only from an approved brief; touching nothing outside the folder after creation | The agent's instruction |
