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

lucid-coder integration: B1 reads its `lucid-coder.yaml`, B2 runs its `align`, B3 follows its notebook layout, B4 and B5 defer to its `sc-*` and `figure-style` skills. lucid-coder's `align` step 6 still calls this skill `repo-template`; rename it there to `repo-setup`.

| ID | Item | Source | Touches | Status |
|---|---|---|---|---|
| B1 | Default environment: new-analysis writes `lucid-coder.yaml`'s `env.r` and `env.python` into the Snakefile; grill adds an `Environment:` evidence line; `init --diagnose` reports the pointer | user request; lucid-coder `align` step 4 | `skills/new-analysis/`, `skills/grill/`, `skills/init/` | done |
| B2 | `repo-setup` skill: Mycelium init plus gate for an analysis repository, or `cookiecutter-python-project` for a package; then `/lucid-coder:align` | ericmjl cookiecutter; lucid-coder `align` step 6 names this skill | `skills/repo-setup/` | done |
| B3 | marimo steps (`NN_name.marimo.py`) in new-analysis and analysis-report | `marimo-notebook-patterns` | `skills/new-analysis/`, `skills/analysis-report/` | done |
| B4 | Exploring one plot at a time, de-risk runs as their own explore row, plots only from logged values | `scientific-eda`, `ml-experimentation` | `skills/plot-first/`, `skills/grill/references/` | done |
| B5 | Figure rules Extra lacks (takeaway caption, preliminary marks, no colour-only encoding, rendered-image review); taste rules defer to lucid-coder `figure-style`. `evident-charts`' `check_chart.py` is not called: it executes the plotting script (a gated run) and covers matplotlib only | `data-visualization-master`, `evident-charts` | `skills/plot-first/`, `skills/analysis-report/` | done |

## Part C: 0.22.0, package development (2026-11-02)

The user widened the audience to bioinformatics package development, so three of the drops below are re-scoped: grill takes `domain-modeling`'s glossary and ADR rules, `tdd`'s seams and independent expectations, and `grilling`'s facts-are-mine rule, as thin glue. The Pocock skills stay installed and own the loops; no skill is added. The five-question cap stays (0.17.0).

| ID | Item | Source | Touches | Status |
|---|---|---|---|---|
| C1 | Glossary: grill reads `GLOSSARY.md`, challenges overloaded terms, lists Terms to record | Pocock `domain-modeling`, `grill-with-docs` | `skills/grill/` | done |
| C2 | ADRs under `docs/adr/` outside Mycelium repositories, only past the three tests | Pocock `domain-modeling` | `skills/grill/references/brief-format.md` | done |
| C3 | Package plan rows: seam, failing test first, independent expected value, bioinformatics test cases | Pocock `tdd` | `skills/grill/references/package-plans.md` | done |
| C4 | Facts-are-mine rule, frontier check with a `Frontier:` line, auto-go under `/goal` or `gate off` | Pocock `grilling`; user request | `skills/grill/SKILL.md` | done |
| C5 | `dev_packages` in gate.json: receipts record a working-copy package's commit | user request | `hooks/gate.py`, `skills/init/`, `skills/verify/` | done |

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
| `codebase-design`, `triage`, `wayfinder`, `to-spec`, `to-tickets`, `implement`, `pr` | dropped: they assume a software issue tracker; `tdd` re-scoped as C3 |
| `research` | dropped: covered by `references/evidence-assistance.md` |
| `wait-what` | dropped: it needs a GLOSSARY Mycelium does not define; `domain-modeling` re-scoped as C1 and C2 |
| `agents-md-improver` | dropped: Mycelium owns the project CLAUDE.md; the environment goal is met by B1 |
| `awesome-marimo-notebook`, `marimo` umbrella, WASM export | dropped: publication explainers and routing only |
| PEP723 + `uv run` rule, WebP plots (`scientific-eda`) | dropped: the gate already matches `conda run`/`uv run`; PNG stays for Quarto HTML |
