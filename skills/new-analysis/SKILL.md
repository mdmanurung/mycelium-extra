---
name: new-analysis
disable-model-invocation: true
description: Scaffold a new analysis folder that plugs into Mycelium (stubs in code/, plan and tracker in plans/, Snakefile, run.sh, run.sbatch).
---

# Mycelium Extra: New analysis

Create the folder a new analysis lives in. Use Mycelium's own pieces wherever they exist: its analysis doc template, `outputs/`, `reports/`, and the `run.sh` entry point. Add only what Mycelium lacks: numbered steps run by a Snakefile, a single plan, a tracker, a Quarto report skeleton, and symlinked `data/` and linked shared code.

```
analysis/<name>/
├── <NAME>.md      Snakefile      run.sh      run.sbatch
├── code/     01_prepare_data.R  02_train_model.py  03_explore_model.ipynb  (+ linked shared code)
├── plans/    PLAN.md  TRACKER.md
├── reports/  <name>.qmd
└── data/  outputs/  logs/
```

## 1. Gather

Take these from the user's message. Ask only if the destination is missing; the aim has its own step, section 2. Asking before writing is the agent's instruction, not a gate rule: nothing enforces it.

- **Destination.**
  - In a Mycelium repository (`.living/` exists), use `analysis/<name>/`.
  - Mycelium names analyses in lowercase-with-hyphens and adds `-v2` for a new iteration of the same question.
  - Another path, such as `nbs/<group>/<NN_name>/`, works too. Mycelium then finds the folder only through a manifest pointer.
- **Steps.** Use the user's list, or default to `01_prepare_data.R,02_train_model.py,03_explore_model.ipynb`.
  - Each step is `NN_name.R`, `.py`, `.ipynb`, `.qmd` or `.marimo.py`, numbered in increasing order.
  - Use R or Python scripts for work that needs no interaction, scripts for heavy jobs, and notebooks for exploration.
  - **Format.** `--format=R|py|ipynb|qmd|marimo` gives every default step, and every bare name in `--steps`, that extension. With no flag the script reads `step_format` in `.mycelium-extra/gate.json`; set it once there for a repository. An explicit extension in `--steps` always wins.
  - **marimo steps** (`NN_name.marimo.py`) are plain Python files: the Snakefile runs them headless with `PYTHON`, and `marimo edit` opens them. The stub keeps lucid-coder's notebook layout: a Purpose/Run/Inputs/Outputs docstring, parameters in the `with app.setup:` cell, named cells, a markdown cell before and after each code cell, and it reads the table the step before wrote rather than refitting. The script prints the `marimo export html` line for a page `analysis-report` can link; that export executes the notebook, so it is a gated run like any other.
  - **qmd steps** compute and hold their own Methods and Results prose in one file. `--lang=r|python` (default `r`) picks knitr or jupyter. The scaffold adds `_quarto.yml`, and the Snakefile runs `quarto render` on each step and writes `outputs/NN_name.rds|parquet` plus the page under `reports/site/code/`. No `reports/<name>.qmd` is written when every step is qmd: the step pages are the report.
- **Links.**
  - `--data=` for each file or folder the analysis reads. Prefer entries under the repository's `data/`.
  - `--code=` for shared code, such as `algorithms/<name>/`, `src/`, or `R/`.
  - The folders hold symlinks only. Mycelium's rule is to reference earlier work by path, never copy it.
- **Panels (manuscript only).** `--panels=Fig1a.R,Fig1b.py` when the folder makes manuscript figures.
  - Each panel gets `code/plot_<panel>`, a stub that exports the plotted values to `<run>/source_data/<panel>.tsv` and then draws the figure from that table alone.
  - It also gets a row in `config/figure_map.tsv` and an entry in `config/manuscript_checks.json`, the contract `manuscript-audit` checks. Paths are repository-relative and point at `outputs/current/`, the released run.
  - On a folder that already exists, `--panels` adds only the missing manuscript files and keeps every existing one byte for byte. Use it to retrofit a manuscript folder. Edit a scaffolded file you have since filled (`<NAME>.md`, `PLAN.md`, a report) with Edit, not a whole-file Write; `analysis-report` gives the check for when a rewrite is needed.
- **Aim.** Settled in section 2 before anything is written.

## 2. Aim: ask, restate, check

1. **Ask.** If the invocation states the question in the user's words, quote it. Otherwise ask for the aim of the analysis and the claim they hope to make from it, in their own words, in one free-text message, as grill's section 0 does: no drafted answer or example, because a draft anchors the user.
2. **Restate.** After they answer, show their words verbatim and one tidier version beside it, labelled as your restatement. The restatement keeps their meaning; it fixes wording, names the comparison and drops filler. Never write it before they answer.
3. **Check.** Test the aim's assumptions against the repository, read-only and by file reads and `rg` only (no probes, no scripts): `.living/findings` and `analysis/ANALYSIS_MANIFEST.md` for a prior analysis that already answers it, `data/DATA_MANIFEST.md` or `data/` for the named data, and `GLOSSARY.md` for overloaded terms (sample, replicate, batch). Outside Mycelium, use the README and docs. For which assumptions matter, use [../grill/references/analysis-decisions.md](../grill/references/analysis-decisions.md) (unit of analysis, contrast, exploratory versus confirmatory).
4. **Refine.** Ask only what the repository cannot settle and the user owns, in one round in grill's format (`Q1`, evidence, options, `Recommended:`), at most three questions. Grill later asks its own five; it does not re-ask what is settled here.
5. **Confirm.** Show the refined aim with the assumptions it rests on, each marked as checked (with its path), answered by the user, or unverified. The user says yes or edits it. That confirmed aim is what section 4 writes.

## 3. Dry run, then create

Run from the repository root, from stdin:

```bash
sh <skill-dir>/../../hooks/py.sh - --dest=analysis/<name> [--steps=01_a.R,02_b.py,03_c.ipynb,04_d.qmd] [--format=R|py|ipynb|qmd|marimo] [--lang=r|python] [--data=PATH ...] [--code=PATH ...] [--panels=Fig1a.R,...] \
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

## 4. Fill

Use Edit; the files already exist.

Read [../plot-first/SKILL.md](../plot-first/SKILL.md) for analysis outputs and conclusions. Carry its figure deliverables into `PLAN.md` and the analysis doc. Keep this rule in the analysis doc so `/mycelium:analyze` reads it when continuing.

- **`<NAME>.md`.** Write the Purpose from section 2: the user's words quoted verbatim and tagged `[human-stated]`, the claim they hope to make beside the aim, also `[human-stated]`, then the confirmed aim, then its assumptions with their status. Write the "Does" column of the Steps table.
- **`plans/PLAN.md` Objective.** Without an approved brief, put the confirmed aim there too.
- **`plans/PLAN.md` and `plans/TRACKER.md`.** If this conversation holds an approved mycelium-extra grill brief for this analysis, copy it in:
  - Into `PLAN.md`: its Objective, Evidence, Inputs, Plan table, Assumptions and risk, Parked, and Decisions to record.
  - Into `TRACKER.md`: one row per plan row, using the same IDs.
- If there is no approved brief, leave the headings for the user or for a later grill.
- Do not write `.living/`, `analysis/ANALYSIS_MANIFEST.md`, or anything outside the new folder (the script leaves one empty `.<name>.scaffold.lock` in the parent; that is expected).

## 5. Where things go (tell the user once)

- **`<NAME>.md`** is Mycelium's entry point.
  - It holds the purpose, status, datasets, steps, open questions, and outputs.
  - **Key Findings** is where results go: each conclusion links its inspected plot and panel, gives its `.living/findings` ID once crystallized, and ends with ``[agent-derived: `outputs/<file>`]`` naming the file behind it; `verify` counts these tags. An interpretive table needs an explicit fallback reason.
  - `/mycelium:analyze` reads this file, and its post-action hook updates it.
- **`plans/PLAN.md`** is the one plan. Revise it in place and log each change in `TRACKER.md`. Never start a second plan file.
- **`plans/TRACKER.md`** holds each item's status and a dated log. Project-wide todos stay in `todo/`.
- **Numbered steps** sit in `code/`, with helpers and checks beside them. Steps run from the analysis folder, so a helper is sourced as `code/<file>`. A new step needs four things:
  - the next number
  - a Snakefile rule
  - a Steps row in `<NAME>.md`
  - a `plans/TRACKER.md` row
- **`outputs/`** is flat, and each file name starts with the step's number (`02_model.rds`).
  - Mycelium's `register_value` writes `outputs/numbers.json` there.
  - The robust-analysis protocols name subfolders such as `outputs/figures/diagnostic/`. Keeping `outputs/` flat, with `diag_` and `supp_` prefixes instead, holds only once it is recorded as a repo-local convention in `.living/conventions.md`. Mycelium applies repo-local conventions before domain and core ones.
- **`run.sbatch`** submits `run.sh` to SLURM; its output goes to `logs/slurm-%x-%j.out`.
- **`config/` and `code/plot_<panel>`** (with `--panels`) tie each figure to its script and source data. Run a stub as `Rscript <dest>/code/plot_<panel>.R <dest>/outputs/run_<date>_<slug>`, point `outputs/current` at the run to release, fill each `figure_map.tsv` claim, and replace the stub's `x`/`y` columns in `required_columns`. Check with `manuscript-audit` (its SKILL.md says how to run the checker without opening the post-action cycle). `outputs/current` must stay inside the repository: a symlink to scratch storage makes every declared path a gap.
- **`logs/`** holds Snakemake and SLURM logs, benchmarks, and executed notebook copies.
- **qmd steps** (`--format=qmd`) are rendered by `quarto render` through `_quarto.yml` (project at the analysis folder, `execute-dir: project`, so paths match the script steps). An executing `quarto render` is a gated run like any other. Each stub follows the lucid-coder layout: Purpose/Run/Inputs/Outputs, a Parameters chunk, 80-column block dividers, session info last. Heavy fits write their table to `outputs/` in one chunk and later chunks read it, so a figure edit does not refit.
- **`reports/<name>.qmd`** is the Quarto report skeleton (script and notebook steps): Overview (with a mermaid chain of the steps), Methods and Results tabs per step, Reproducibility. `/mycelium-extra:analysis-report` fills it after a run. Mycelium's `report` skill writes its LaTeX PDF beside it as `<name>-report.tex`.

## 6. Report and hand off

- List what was created, which template the doc came from, and any warnings.
- Tell the user that each R step opens with a `scilintr stage` line: replacing it with `# STAGE: <stage>` (`blind_qc`, `selection`, `evaluation`, `library`) turns on scilintr's label and stage rules for that file. The scaffold sets no stage; that choice is the user's.
- Next steps for the user:
  1. Plan the work with `/mycelium-extra:grill`. It quotes the aim recorded in `<NAME>.md` instead of asking again. A plan whose table names this folder's scripts or its `run.sh` lets the approval gate pass them.
  2. Run `/mycelium:analyze <name>`. It continues the existing folder, adds the manifest entry (the script printed a suggested one), and records decisions. That includes the flat-`outputs/` convention, if the user wants it.
  3. For a reportable run, once the code is written and linted, grill a run plan that freezes it (grill's `references/run-plans.md`): it revises this `plans/PLAN.md` in place and shows the job list from `bash run.sh -n`, run under the first plan's approval.
- **Interpreters.** When `lucid-coder.yaml` at the repository root names `env.r` and `env.python` (written by `/lucid-coder:align`), the Snakefile's `RSCRIPT`, `PYTHON` and `JUPYTER` default to those paths, each only if the file exists; otherwise they stay the names on PATH and the script says so. `--config rscript=...` still overrides per run.
- With lucid-coder installed, `/lucid-coder:align` installs the formatter configs once per repository. Its rule 6 ("scripts compute, notebooks show") does not fit qmd steps; the user's format choice outranks it. If they want that lasting, offer `/lucid-coder:learn` once.
- Offer to commit the new folder.
