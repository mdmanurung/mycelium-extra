# new-analysis

Scaffolds a new, self-contained analysis folder that plugs into Mycelium. Guide: [Plan an analysis](../../guides/plan-an-analysis.md). It is not for turning the gate on ([init](init.md)) or continuing an existing analysis (Mycelium's `analyze`).

## Synopsis

```bash
sh <skill-dir>/../../hooks/py.sh - --dest=analysis/<name> [--steps=01_a.R,02_b.py,03_c.ipynb] [--data=PATH ...] [--code=PATH ...] [--doc-template=FILE] --templates=<skill-dir>/templates [--dry-run] < <skill-dir>/scripts/new_analysis.py
```

Invoke with `/mycelium-extra:new-analysis analysis/<name>: <question>`. Write every option as `--flag=value`: the gate reads a bare `analysis/...` argument as a script being run and blocks it. Never run the script by path.

## Options

| Option | Meaning |
|---|---|
| `--dest` | Folder to create (required). In a Mycelium repository use `analysis/<name>/`, lowercase with hyphens. |
| `--steps` | Comma-separated `NN_name.R`, `.py` or `.ipynb`, numbered in increasing order. Default `01_prepare_data.R,02_train_model.py,03_explore_model.ipynb`. |
| `--data` | File or folder to link into `data/` (repeatable). |
| `--code` | File or folder to link into `code/` (repeatable). |
| `--doc-template` | Analysis doc template. Default: Mycelium's `analysis-readme.md`, found through `.mycelium/plugin-root`, else a bundled copy. |
| `--templates` | This skill's `templates/` folder (required when run from stdin). |
| `--dry-run` | Report what would change; write nothing. |

## What it creates

```
analysis/<name>/
  01_prepare_data.R  02_train_model.py  03_explore_model.ipynb   numbered step stubs
  Snakefile  run.sh                                              runs the steps in order
  <NAME>.md  PLAN.md  TRACKER.md                                 analysis doc, the one plan, the tracker
  data/  code/  outputs/  logs/  reports/
```

`data/` and `code/` hold symlinks only. The analysis doc is `<NAME>.md` (folder name in UPPER_SNAKE_CASE) in a Mycelium repository, `README.md` elsewhere. Stubs stop until implemented. It refuses a non-empty folder, a missing link target, and anything it would overwrite (`refused:` line, nothing written). A `WARNING: git ignores ...` line means that file would never be committed; stop and ask. It writes nothing outside the new folder except an empty `.<name>.scaffold.lock` file in its parent folder (the lock that keeps two runs from filling the same folder; delete it if you like): not `.living/`, not `analysis/ANALYSIS_MANIFEST.md` (it prints a suggested manifest entry).

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
