---
name: repo-setup
disable-model-invocation: true
description: Set up a new repository in one pass, as a Mycelium analysis repo or a Python package, then the lucid-coder style and environment pointer.
---

# Mycelium Extra: Repository setup

Set up a repository by running the generators that already exist, in order, and say what each one writes. This skill has no script and no templates. Show each command and wait for a yes before running it. Stop at the first step that fails, and report what was done.

## 1. Ask the kind, once

Take it from the user's message when it is clear; otherwise ask one question.

- **Analysis repository**: data, numbered analyses, findings and reports. Mycelium lays it out.
- **Python package**: a library or CLI with `src/`, tests and docs. `ericmjl/cookiecutter-python-project` lays it out.

Also note the folder, and an analysis name if the user gave one.

## 2. Lay out the repository

**Analysis repository.**

1. If the folder is not a git repository, show `git init` and run it on yes.
2. Run Mycelium's init: `/mycelium:core init`. Mycelium owns `.living/`, `MYCELIUM.md`, `CLAUDE.md`, `AGENTS.md`, `data/` and `analysis/`; this skill writes none of them.
3. Turn on the approval gate with `/mycelium-extra:init`.

**Python package.** Before running, say four things: it needs network access and `cookiecutter` (`pip install cookiecutter` or `pixi global install cookiecutter`); it asks for `project_name` and `short_description`; it reads your name and email from `git config` and your GitHub user from `gh`; and its post-generation hook runs `git init`, installs the pixi environment and pre-commit hooks, and makes a first commit. On yes:

```bash
cookiecutter gh:ericmjl/cookiecutter-python-project
```

Then `cd` into the new folder for the next steps. The result has `pixi.toml`, `pyproject.toml`, `src/<package>/`, `tests/`, `docs/` (MkDocs) and `.pre-commit-config.yaml`. Run `/mycelium-extra:init` only if the user will run analyses in this repository too.

## 3. Style and environment

1. With lucid-coder installed, run `/lucid-coder:align`. It copies the formatter configs one file at a time and writes `lucid-coder.yaml`, which names the conda, pixi or uv environment and its `Rscript` and `python`. For a package, the environment is the pixi env: activate it with `pixi shell` before align fills the paths. `new-analysis` and `grill` read that file, so every later session knows which interpreter to run. Without lucid-coder, say that `lucid-coder.yaml` is missing and that the Snakefile will use `Rscript` and `python` from PATH.
2. If the user named a default step format (`R`, `py`, `ipynb`, `qmd`, `marimo`), write `step_format` into `.mycelium-extra/gate.json` with an Edit after showing the change.
3. If the user named an analysis, run `/mycelium-extra:new-analysis analysis/<name>: <question>`.

## 4. Report

List what each step wrote and which steps were skipped and why. End with the next commands for the kind:

- Analysis repository: `bash analysis/<name>/run.sh -n` (when an analysis exists), then `/mycelium-extra:grill <question>`.
- Python package: `pixi run test`, then `pixi run lint`.

<!-- ponytail: no Extra-owned analysis-repo template; Mycelium's init lays one out. Add a cookiecutter under templates/ only if init leaves a gap that recurs. -->
