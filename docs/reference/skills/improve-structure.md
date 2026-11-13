# improve-structure

Reviews how one analysis folder, or a folder of analyses, is organised. It finds friction, shows up to five candidates on a one-off Artifact page, and hands your pick to `grill`. It never edits code and never moves outputs. Adapted from Matt Pocock's improve-codebase-architecture and codebase-design skills (MIT).

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`).

`/mycelium-extra:improve-structure` (Codex: `$mycelium-extra:improve-structure`). Name a direction (a step, a folder, a pain) or let it find the hot spots. The scan runs read-only from stdin:

```bash
sh <skill-dir>/../../hooks/py.sh - PATH [--json] [--dup-lines 8] [--long-script 300] [--long-pipe 15] < <skill-dir>/scripts/scan_structure.py
```

`PATH` is an analysis folder (it has `code/`) or a folder holding analyses. Exit 0, or 2 for a path with no analysis.

## Steps

1. **Scope by hot spots.** Your direction wins. Otherwise the code files edited most, from `git log --name-only` and the `Code changed:` lines of `logs/CHANGES.md`.
2. **Scan.** The script reports findings. Each one is a place to look, not a verdict. The agent opens the files and applies the deletion test: would deleting this module concentrate complexity or just move it?
3. **Present up to five candidates** on a private Artifact page. Each card has files, problem, proposed change in plain words, benefit in leverage, locality and testability terms, a before and after diagram, an outputs check, and a strength: Strong, Worth exploring or Speculative. No interfaces yet.
4. **Hand over.** You pick one; the skill passes it to `/mycelium-extra:grill` as the task. The change runs through an approved plan row.
5. **Keep what is worth keeping.** With your confirmation, a load-bearing rejection can go to `decision-status`, and a settled term to the `glossary` skill when present.

## What the scan finds

| Finding | Meaning |
|---|---|
| `shared_folder_read` | Reads through `dirname(...)`, `RUN_DIR`, `base_dir`, `run_dir`, `TP_BASE` or an old `run_*` folder |
| `absolute_step_path` | An absolute path into another step's `outputs/<step>/` folder |
| `fan_in` | A script reads more than two other steps' outputs |
| `duplicated_block` | 8 or more identical lines (comments, blanks and imports ignored) in two scripts |
| `long_script`, `long_pipe` | A script over 300 lines, or a pipe or chain over 15 lines |
| `heavy_notebook` | A qmd, Rmd or ipynb that fits models or writes tables |
| `no_snakefile`, `no_rule` | A numbered script that no Snakefile rule names |
| `no_check` | A step with no Validation cell in a plan table (`plans/*.md`, the analysis doc) and no `check_` or `test_` file |
| `midscript_parameter` | Two or more thresholds, counts or seeds hard-coded after the first data read |
| `knob_not_at_top` | An UPPER_SNAKE value set after the first data read |
| `plot_without_theme` | Plot code that does not source `code/theme.R` or `theme.py`, or no shared theme exists |
| `palette_repeated` | Hex colour lists in two or more scripts |
| hot spots | Code files edited at least twice, from git and `logs/CHANGES.md` |

The numeric limits are options. The pattern lists are plain regular expressions in the script and miss what only reading shows.

## Outputs stay identical, or it is a plan row

A candidate may move code only when outputs stay byte-identical. A change that could alter a headline estimate, a ranking, a selected feature or a conclusion is your choice and needs its own approved plan row. Each card says which case applies. The Validation check for a restructure is to rerun the affected steps and compare each table before and after with `diagnose-result`'s `scripts/diff_tables.py` when present, and to open both versions of each figure.

## Reads and writes

Reads `code/`, the Snakefile, `plans/`, the analysis doc, `logs/CHANGES.md` and git history. Writes nothing in the repository. The page goes to the Artifact tool.

## Default on or off

On when invoked.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| The scan script writes nothing | Enforced by the script, which has no write path |
| No edits to `analysis/**`, `nbs/**` or outputs | Enforced for gated paths by the gate; the skill's instruction otherwise |
| Outputs identical or a plan row | The agent's instruction; `verify` later checks what ran against the approved plan |
| Confirming before a decision or term is recorded | The agent's instruction |

See [grill](grill.md) for the plan, `diagnose-result` for `diff_tables.py` when present, and [decision-status](decision-status.md).
