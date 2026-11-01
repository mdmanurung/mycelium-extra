# 16 · Outside skills: Pocock, Codex and ericmjl (2026-11-01)

[Back to roadmap](README.md)

Objective: take what fits from `mattpocock-skills` 1.3.1, the Codex skills in `~/.agents/skills/` (many from `ericmjl/skills`) and `ericmjl/cookiecutter-python-project`, without overriding Mycelium or lucid-coder. Each item lands on an existing Extra file or adds one user-invoked skill.

Statuses: `todo`, `in progress`, `built`, `done`, `parked`, `dropped: <reason>`, `blocked: <question for the user>`.

## Part A: 0.20.0

| ID | Item | Source | Touches | Status |
|---|---|---|---|---|
| A1 | `questionnaire` skill; grill parks third-party questions as `answer from <role>` | Pocock `to-questionnaire` (item 5 of the 0.17.0 review) | `skills/questionnaire/`, `skills/grill/SKILL.md`, `references/brief-format.md` | done |
| A2 | Rewrite guard: list headings before a whole-file write, diff after; track-changes reports dropped report sections | Codex `audit-before-rewrite` (a bundle was lost and rebuilt in 0.14.4) | `skills/analysis-report/`, `skills/new-analysis/`, `skills/track-changes/` | done |
| A3 | Oracle and mutation test rules for contributors | Codex `grader-mutation-evidence` | `docs/development.md` | done |

## Part B: 0.21.0

| ID | Item | Source | Touches | Status |
|---|---|---|---|---|
| B1 | Default environment: new-analysis writes `lucid-coder.yaml`'s `env.r` and `env.python` into the Snakefile; grill adds an `Environment:` evidence line; `init --diagnose` reports the pointer | user request; lucid-coder `align` step 4 | `skills/new-analysis/`, `skills/grill/`, `skills/init/` | todo |
| B2 | `repo-setup` skill: Mycelium init plus gate for an analysis repository, or `cookiecutter-python-project` for a package; then `/lucid-coder:align` | ericmjl cookiecutter; lucid-coder `align` step 6 names this skill | `skills/repo-setup/` | todo |
| B3 | marimo steps (`NN_name.marimo.py`) in new-analysis and analysis-report | `marimo-notebook-patterns` | `skills/new-analysis/`, `skills/analysis-report/` | todo |
| B4 | Exploring one plot at a time, de-risk runs as their own explore row, plots only from logged values | `scientific-eda`, `ml-experimentation` | `skills/plot-first/`, `skills/grill/references/` | todo |
| B5 | Figure rules Extra lacks (takeaway caption, one accent, direct labels, rendered-image review); `evident-charts` checker when installed | `data-visualization-master`, `evident-charts` | `skills/plot-first/`, `skills/analysis-report/` | todo |

## Parked: no failure in real use yet

Return condition for each: a real session shows the failure it guards against. Grill that one item alone.

| Item | Source | Would land on |
|---|---|---|
| Session retrospective that proposes a check, shipped by `harden` | Pocock `retro` | `skills/harden/` |
| Build a tight pass/fail loop before debugging | Pocock `diagnosing-bugs` | one line in `references/polya-heuristics.md`; Mycelium's analyze owns debugging |
| Audit docs for destructive instructions nobody guards | Codex `doc-safety-audit` | `docs/development.md` |

## Dropped

| Item | Reason |
|---|---|
| `.out-of-scope/` folder (Pocock item 4) | dropped: grill's Parked section with a return condition covers it |
| `tdd`, `codebase-design`, `triage`, `wayfinder`, `to-spec`, `to-tickets`, `implement`, `pr` | dropped: they assume a software issue tracker; the audience is researchers |
| `research` | dropped: covered by `references/evidence-assistance.md` |
| `domain-modeling`, `wait-what` | dropped: they need a GLOSSARY Mycelium does not define |
| `agents-md-improver` | dropped: Mycelium owns the project CLAUDE.md; the environment goal is met by B1 |
| `awesome-marimo-notebook`, `marimo` umbrella, WASM export | dropped: publication explainers and routing only |
| PEP723 + `uv run` rule, WebP plots (`scientific-eda`) | dropped: the gate already matches `conda run`/`uv run`; PNG stays for Quarto HTML |
