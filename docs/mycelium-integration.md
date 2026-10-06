# Mycelium: credits and boundaries

[Back to README](../README.md)

An analysis benefits from the decisions and experience already stored in its
project. [Mycelium](https://github.com/arjunrajlaboratory/mycelium) provides that
memory; Mycelium Extra uses it to plan the next task and check its execution.
The two plugins share project context while keeping their responsibilities
clear: Mycelium maintains the living repository, and Mycelium Extra connects a
proposed plan to the runs and outputs that follow.

Mycelium Extra builds on Mycelium's MIT-licensed templates and conventions
(Copyright (c) 2024 Mycelium Contributors). This page records that reuse and
the boundaries between the plugins. The file paths and comparison below use
Mycelium 0.7.2 as their documented baseline, rather than describing every
behavior of newer releases.

**On this page:** [What Mycelium covers and what this plugin adds](#what-mycelium-covers-and-what-this-plugin-adds) · [What is taken from Mycelium](#what-is-taken-from-mycelium) · [Other credits](#other-credits) · [Boundaries](#boundaries)

## What Mycelium covers and what this plugin adds

| Need | In Mycelium 0.7.2 | Mycelium Extra |
|---|---|---|
| Stop a run that has no agreed plan | Not covered: `hooks/hooks.json` registers SessionStart, PostToolUse, and Stop hooks, none of which run before a command. | The approval gate, a PreToolUse hook that denies a gated run until you approve a plan naming it. |
| Question the choices behind an analysis | `review` grill mode (`skills/core/references/review/grill-mode.md`) interviews you about an analysis that already exists. | `grill` asks before anything runs and returns a plan in which every choice is sourced. |
| Know which inputs a plan rests on | Not covered. | The plan's `Inputs:` line; the gate pins those files and blocks a run if one changed. |
| Record what ran | Data lineage for python, R, and jupyter runs (`skills/core/hooks/mycelium-data-tracker.sh`, written to `.living/log/data-lineage/`). | A receipt per gated run, tied to the approved plan, including `run.sh`, snakemake, sbatch, and nextflow runs, with exit status and environment. `verify` reads Mycelium's lineage as a second source. |
| Check the work against the plan | `analyze` requires scilintr after code changes; `review` checks code and statistics. | `verify` compares the approved plan with the receipts, lints the code with scilintr, checks reported numbers against their output cells, and writes `provenance/`. |
| Act on accumulated memory | Learnings name a `structural_mitigation_candidate`; `skills/core/scripts/detect_recurrence.py` flags recurring ones. Decisions accumulate in `.living/decisions.md`. | `harden` ships a candidate as a test; `decision-status` settles which of several decisions binds a task. |

## What is taken from Mycelium

**Copied file**

- `skills/new-analysis/templates/analysis-readme.md` is copied unchanged from Mycelium's `skills/core/templates/analysis-readme.md`, under Mycelium's MIT license ([MYCELIUM_LICENSE](../skills/new-analysis/templates/MYCELIUM_LICENSE)). It is used only when the repository's own Mycelium install cannot be found.

**Ideas**

- **Grilling.** `grill` applies the questioning of Mycelium's `review` grill mode before the work instead of after it. The two are meant to be used together: `grill` before a run, `/mycelium:review grill` on the finished analysis.
- **Memory as evidence.** `grill` searches `.living/`, the manifests, and analysis docs before it asks you anything, in the lookup order of `skills/grill/references/mycelium.md`.
- **Scientific linting.** `verify` runs scilintr and lists every `ANALYSIS_OK` waiver, because `analyze` makes linting with scilintr non-negotiable (`skills/core/references/scilintr-guide.md`).
- **Mitigation candidates.** `harden` acts on learnings still marked `mitigation_type: ambient-awareness` and sets them to `structural` once a test lands, as Mycelium's learning template (`skills/core/templates/learning-entry.md`) asks.

**File formats followed**

- The analysis folder layout (`<NAME>.md`, `outputs/`, `reports/`, `run.sh`) from `skills/core/references/folder-structure.md`, so `/mycelium:analyze` continues a `new-analysis` folder as an existing analysis. `validate_structure.py` checks that its `<NAME>.md` exists.
- `.mycelium/plugin-root`, through which `new-analysis` finds Mycelium's own template.
- `.living/decisions.md` entries. `decision-status` appends a `Resolution:` entry with the ordinary decision fields plus `Status`, `Supersedes`, `Scope`, `Revisit when`, and `Resolved-by`; Mycelium's scripts read the extra fields as body text.
- The Evidence Ledger of a finding (`skills/core/templates/findings-entry.md`). The gate suggests writing its Run/Session cell as `<session-id>; plan <hash>`.
- `ANALYSIS_MANIFEST.md`. `new-analysis` prints a suggested entry, and `verify status` reads each folder's entry.
- `.mycelium/last-session.md`, which `handoff` links to instead of copying.
- Repo-local conventions, which Mycelium applies before domain and core conventions. A flat `outputs/` holds only once you record it as one.
- The post-action protocol (`skills/core/hooks/mycelium-post-action.sh`). Mycelium detects only python, R, and jupyter runs, so after other runs the gate reminds the agent to follow the protocol.

## Other credits

- `data-contract-check` reports each mismatch in the shape of ClawBio's contract alerts: expected, observed, and evidence lines.
- [scilintr](https://github.com/arjunrajlaboratory/scilintr) does the linting `verify` reports; this plugin only calls it.

## Boundaries

Mycelium Extra complements Mycelium without overriding it. Concretely:

- `grill` makes no edits. It never writes `.living/`, manifests, todo, or analysis files. It never runs repository scripts by path, because that would start Mycelium's post-action cycle. Its data checks use inline read-only probes.
- `decision-status` writes to `.living/decisions.md` only after you confirm a resolution, and only by appending. Its parser runs from stdin (`python3 - ... < decision_threads.py`), which the Mycelium 0.6.0 and 0.7.2 hooks do not treat as a post-action run.
- `data-contract-check` is read-only and runs the same way. Its contract stays outside the repository until you approve the plan.
- `new-analysis` writes only inside the new folder. Its script also runs from stdin. The folder uses Mycelium's layout plus a plan, a tracker, a Snakefile, and `data/` and `code/` links, so `/mycelium:analyze` continues it rather than building a second skeleton.
- After you approve a plan, run it through your normal workflow. In a Mycelium project that is `/mycelium:analyze` (`$mycelium:analyze` in Codex), which logs the brief's "Decisions to record" through Mycelium's lifecycle.
- `verify` reads Mycelium's lineage but never writes `.living/`. Its report is read-only. Its `write` step runs from stdin and writes only `<analysis>/provenance/`. Those new files make Mycelium's Stop hook ask for a `.living/` update, where you record the verify status through Mycelium's normal logging.
- `harden` changes one `.living/learnings.md` entry, after you confirm.
- No SessionStart message: it would compete with Mycelium's session resume.
