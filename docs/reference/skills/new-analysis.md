# new-analysis

Scaffolds a new, self-contained analysis folder that plugs into Mycelium. Guide: [Plan an analysis](../../guides/plan-an-analysis.md). It is not for turning the gate on ([init](init.md)) or continuing an existing analysis (Mycelium's `analyze`).

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`).

```bash
sh <skill-dir>/../../hooks/py.sh - --dest=analysis/<name> [--steps=01_a.R,02_b.py,03_c.ipynb] [--data=PATH ...] [--code=PATH ...] [--doc-template=FILE] [--panels=Fig1a.R,...] --templates=<skill-dir>/templates [--dry-run] < <skill-dir>/scripts/new_analysis.py
```

Invoke with `/mycelium-extra:new-analysis analysis/<name>: <question>`. Write every option as `--flag=value`: the gate reads a bare `analysis/...` argument as a script being run and blocks it. Never run the script by path.

## Options

| Option | Meaning |
|---|---|
| `--dest` | Folder to create (required). In a Mycelium repository use `analysis/<name>/`, lowercase with hyphens. |
| `--steps` | Comma-separated `NN_name.R`, `.py`, `.ipynb` or `.qmd`, numbered in increasing order. A name with no extension takes `--format`. Default `01_prepare_data.R,02_train_model.py,03_explore_model.ipynb`, or the same names with the `--format` extension. |
| `--format` | `R`, `py`, `ipynb` or `qmd`: the extension of the default steps and of bare names. Default: `step_format` in `.mycelium-extra/gate.json`, else none (the mixed default above). |
| `--lang` | `r` (default, knitr) or `python` (jupyter): the language of qmd steps. |
| `--data` | File or folder to link into `data/` (repeatable). |
| `--code` | File or folder to link into `code/` (repeatable). |
| `--doc-template` | Analysis doc template. Default: Mycelium's `analysis-readme.md`, found through `.mycelium/plugin-root`, else a bundled copy. |
| `--panels` | Comma-separated manuscript panels, `<id>.R` or `<id>.py`. Adds a `code/plot_<id>` stub per panel, `config/figure_map.tsv` and `config/manuscript_checks.json` for [manuscript-audit](manuscript-audit.md). Needs a git or Mycelium repository. On an existing folder it adds only the missing manuscript files. |
| `--templates` | This skill's `templates/` folder (required when run from stdin). |
| `--dry-run` | Report what would change; write nothing. |

## What it creates

```
analysis/<name>/
  <NAME>.md  Snakefile  run.sh  run.sbatch     analysis doc; run the steps in order, locally or on SLURM
  code/      01_prepare_data.R  02_train_model.py  03_explore_model.ipynb   numbered step stubs
             plot_<panel>.R|.py                (--panels) export the plotted values, then draw from them alone
  plans/     PLAN.md  TRACKER.md               the one plan, the tracker
  config/    figure_map.tsv  manuscript_checks.json   (--panels) what manuscript-audit checks
  reports/   <name>.qmd                   Quarto report skeleton, filled by analysis-report
  data/  outputs/  logs/
```

`data/` holds symlinks only; `code/` holds the stubs and links to shared code. The analysis doc is `<NAME>.md` (folder name in UPPER_SNAKE_CASE) in a Mycelium repository, `README.md` elsewhere. Stubs stop until implemented. A panel stub writes `<run>/source_data/<panel>.tsv`, then re-reads only that table to draw `<run>/figures/<panel>.pdf`, so the released source data can redraw the panel; its toy `x`/`y` columns are placeholders, and the contract points at `outputs/current/`, which you point at the run you release. `reports/<name>.qmd` is a static Quarto report (`engine: markdown`) with a mermaid chain of the steps and one Methods and one Results tab per step; [analysis-report](analysis-report.md) fills it after a run, and Mycelium's `report` writes its LaTeX PDF beside it. Without `--panels` it refuses a non-empty folder; with it, it adds each missing manuscript file and keeps every existing file unchanged. It also refuses a missing link target and anything it would overwrite (`refused:` line, nothing written). A `WARNING: git ignores ...` line means that file would never be committed; stop and ask. It writes nothing outside the new folder except an empty `.<name>.scaffold.lock` file in its parent folder (the lock that keeps two runs from filling the same folder; delete it if you like): not `.living/`, not `analysis/ANALYSIS_MANIFEST.md` (it prints a suggested manifest entry).

## Afterwards

The agent fills the Purpose and Steps table of `<NAME>.md`, and copies an approved grill brief into `PLAN.md` and `TRACKER.md` when one exists in the conversation. `PLAN.md` records no plan hash. Each R step opens with a `scilintr stage` line; the stage is your choice. Next: [grill](grill.md) a plan naming this folder's scripts or `run.sh`, then Mycelium's `analyze`.

## Default on or off

On when invoked.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| Never overwrites; refuses non-empty folders and missing link targets | Enforced by the script |
| Reading the dry run and asking you before writing | The agent's instruction |
| Filling `PLAN.md` only from an approved brief; touching nothing outside the folder after creation | The agent's instruction |
