---
name: new-analysis
description: Scaffold a new, self-contained analysis folder that plugs into Mycelium. It has numbered step stubs (R, Python, notebook) at the folder root, a Snakefile that runs them in order, a run.sh entry point, Mycelium's own analysis doc (`<NAME>.md`) with a Steps table, one PLAN.md and one TRACKER.md, and `data/` and `code/` symlink folders plus `outputs/`, `logs/`, and `reports/`. Use when the user invokes mycelium-extra new-analysis, or asks to create, start, scaffold, set up, or initialize a new analysis folder or subfolder. Writes only inside the new folder and never overwrites. Not for turning on the approval gate (use init), and not for continuing an existing analysis (use Mycelium's analyze).
---

# Mycelium Extra: New analysis

Create the folder a new analysis lives in. Use Mycelium's own pieces wherever they exist: its analysis doc template, `outputs/`, `reports/`, and the `run.sh` entry point. Add only what Mycelium lacks: numbered steps run by a Snakefile, a single plan, a tracker, and symlinked `data/` and `code/`.

```
analysis/<name>/
├── 01_prepare_data.R  02_train_model.py  03_explore_model.ipynb
├── Snakefile      run.sh
├── <NAME>.md      PLAN.md      TRACKER.md
└── data/  code/  outputs/  logs/  reports/
```

## 1. Gather

Take these from the user's message. Ask only if the destination is missing.

- **Destination.**
  - In a Mycelium repository (`.living/` exists), use `analysis/<name>/`.
  - Mycelium names analyses in lowercase-with-hyphens and adds `-v2` for a new iteration of the same question.
  - Another path, such as `nbs/<group>/<NN_name>/`, works too. Mycelium then finds the folder only through a manifest pointer.
- **Steps.** Use the user's list, or default to `01_prepare_data.R,02_train_model.py,03_explore_model.ipynb`.
  - Each step is `NN_name.R`, `NN_name.py`, or `NN_name.ipynb`, numbered in increasing order.
  - Use R or Python scripts for work that needs no interaction, scripts for heavy jobs, and notebooks for exploration.
- **Links.**
  - `--data=` for each file or folder the analysis reads. Prefer entries under the repository's `data/`.
  - `--code=` for shared code, such as `algorithms/<name>/`, `src/`, or `R/`.
  - The folders hold symlinks only. Mycelium's rule is to reference earlier work by path, never copy it.
- **Scope.** One sentence on the question the analysis answers.

## 2. Dry run, then create

Run from the repository root, from stdin:

```bash
python3 - --dest=analysis/<name> [--steps=01_a.R,02_b.py,03_c.ipynb] [--data=PATH ...] [--code=PATH ...] \
  --templates=<skill-dir>/templates --dry-run < <skill-dir>/scripts/new_analysis.py
```

- Write every option as `--flag=value`. The approval gate reads a bare `analysis/...` argument as a script being run, and blocks it.
- Never run the script by path. That opens Mycelium's post-action cycle. If a Mycelium hook asks for `.living/` updates anyway, tell the user which command triggered it and follow the hook.
- Read every line the dry run prints:
  - A `refused:` line means nothing was written. Fix the input.
  - A `WARNING: git ignores ...` line means that file would never be committed. Stop and ask the user. In scale, for example, `analysis/*/docs/` and `analysis/*/results/` are ignored, which is why this layout avoids those names.
  - A `note:` line is information only.
- Then run the same command without `--dry-run`.

The analysis doc comes from Mycelium's `skills/core/templates/analysis-readme.md`. The script finds it through `.mycelium/plugin-root`, or uses a bundled copy, or uses the file you pass with `--doc-template=`. In a Mycelium repository the doc is named `<NAME>.md` (the folder name in UPPER_SNAKE_CASE, as Mycelium's `validate_structure.py` expects). Elsewhere it is `README.md`.

## 3. Fill

Use Edit; the files already exist.

- **`<NAME>.md`.** Write the Purpose from the scope, and the "Does" column of the Steps table.
- **`PLAN.md` and `TRACKER.md`.** If this conversation holds an approved mycelium-extra grill brief for this analysis, copy it in:
  - Into `PLAN.md`: its Objective, Evidence, Inputs, Plan table, Assumptions and risk, Parked, and Decisions to record.
  - Into `TRACKER.md`: one row per plan row, using the same IDs.
- If there is no approved brief, leave the headings for the user or for a later grill.
- Do not write `.living/`, `analysis/ANALYSIS_MANIFEST.md`, or anything outside the new folder.

## 4. Where things go (tell the user once)

- **`<NAME>.md`** is Mycelium's entry point.
  - It holds the purpose, status, datasets, steps, open questions, and outputs.
  - **Key Findings** is where results go: each bullet gives the claim, the `outputs/` file behind it, and its `.living/findings` ID once crystallized.
  - `/mycelium:analyze` reads this file, and its post-action hook updates it.
- **`PLAN.md`** is the one plan. Revise it in place and log each change in `TRACKER.md`. Never start a second plan file.
- **`TRACKER.md`** holds each item's status and a dated log. Project-wide todos stay in `todo/`.
- **Numbered steps** sit at the folder root, so the order is visible at a glance. A new step needs four things:
  - the next number
  - a Snakefile rule
  - a Steps row in `<NAME>.md`
  - a `TRACKER.md` row
- **`outputs/`** is flat, and each file name starts with the step's number (`02_model.rds`).
  - Mycelium's `register_value` writes `outputs/numbers.json` there.
  - The robust-analysis protocols name subfolders such as `outputs/figures/diagnostic/`. Keeping `outputs/` flat, with `diag_` and `supp_` prefixes instead, holds only once it is recorded as a repo-local convention in `.living/conventions.md`. Mycelium applies repo-local conventions before domain and core ones.
- **`logs/`** holds Snakemake and SLURM logs, benchmarks, and executed notebook copies.
- **`reports/`** belongs to Mycelium's report skill.

## 5. Report and hand off

- List what was created, which template the doc came from, and any warnings.
- Next steps for the user:
  1. Plan the work with `/mycelium-extra:grill`. A plan whose table names this folder's scripts or its `run.sh` lets the approval gate pass them.
  2. Run `/mycelium:analyze <name>`. It continues the existing folder, adds the manifest entry (the script printed a suggested one), and records decisions. That includes the flat-`outputs/` convention, if the user wants it.
- Offer to commit the new folder.
