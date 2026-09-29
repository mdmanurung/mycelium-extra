# Mycelium repository lookup

Use this reference once `.living/` is detected. The project's files are the contract; this skill does not depend on Mycelium's scripts, hooks, or plugin path. Checked against Mycelium 0.7.2. Follow the project's own guidance where its structure differs.

## Detect

- `.living/` present means a Mycelium repository; Mycelium's hooks use the same test.
- `MYCELIUM.md` is optional. Older or migrated repositories may have only the `<!-- MYCELIUM:BEGIN -->` block in `CLAUDE.md` or `AGENTS.md`, or no guidance file at all.
- Missing manifests, `INDEX.md`, or `findings/` are normal partial states. Do not treat them as errors, and suggest migration only if the gap blocks the task.

## Selective sequence

Read only the entries connected to the task.

1. **Guidance.** `MYCELIUM.md`, or the Mycelium block in `CLAUDE.md`/`AGENTS.md`; failing both, whatever instruction files exist, since they often carry the project's scientific rules and environment notes. Older files may cite Mycelium helpers by a repo-relative `skills/core/scripts/...` path; that path lives in the plugin, not the repository. When continuing prior work, the session handoff `.mycelium/last-session.md` (per-session copies live under `.mycelium/run/<host>/<session-id>/`).
2. **Index.** `.living/INDEX.md`: quick-reference table, tag clusters, most recent entries, and a by-tag list. The index can lag or undercount (see "Find entries"), so check it: filter heading lines by date prefix for each month since the index's "Last audit" date, for example `rg -n '^#{2,3} \[?2026-09' .living/decisions.md .living/learnings.md`, and list undated headings with `rg -n '^#{2,3} [^\[0-9]'`. Scan those titles. Do not rely on file order or on `tail`: entries may be appended, prepended, or undated. Recent unindexed entries are often the most relevant.
3. **Manifests.** `analysis/ANALYSIS_MANIFEST.md`, `data/DATA_MANIFEST.md`, `algorithms/ALGORITHM_MANIFEST.md`, `reference_material/REFERENCE_MANIFEST.md`, `todo/TODO_REGISTRY.md`.
4. **Analysis and data.** `analysis/<name>/<UPPER_SNAKE_CASE>.md`, `specification.md` if present, `run.sh`/`run.py`, the scripts and config that actually produced outputs, `outputs/numbers.json`, `analysis_labels.yml`. For exclusions and provenance: `data/metadata/<dataset>/` (`schema.yaml`, `provenance.md`).
5. **Memory.** Relevant entries in `.living/decisions.md` and `.living/learnings.md`; `.living/findings/FINDINGS_REGISTRY.md` and topic files `.living/findings/<topic>.md`. Prior reviews in `.living/outputs/reviews/`: their "Key decisions" and "Questions for the analyst" sections are direct evidence for grilling.
6. **Conventions.** `.living/conventions.md` (repo-local overrides), `.living/conventions/ACTIVE_CONVENTIONS.yaml`, then `analysis-conventions.md` of active packs only. Presence is not activation. Precedence: repo-local > domain > core. `.living/generated-conventions/` holds crystallized drafts, which are not active. `.living/skills/` holds project-local skills.
7. **Cross-project knowledge**, only when the task is transferable: `~/.mycelium/knowledge/<domain>.md` (an entry with `Status: unreviewed` is not established), and a parent directory's `.living/findings/INDEX.md` if the project sits in a meta-project.
8. **Logs.** `.living/log/LOG_REGISTRY.md` or one session log, only when earlier sources leave a consequential gap.

## Find entries

- Entries are headings in `learnings.md` and `decisions.md`. The current format is `### [YYYY-MM-DD] Title`, but older repositories mix in `## [YYYY-MM-DD] Title`, `### YYYY-MM-DD: Title`, and undated `### L-114: Title`. `conventions.md` uses `## ` sections. The `**Tags**:` line sits in the entry body, usually near its end; a tag hit belongs to the nearest heading above it.
- Mycelium's index counts only `### ` headings in these files. In a repository with `## ` entries, `INDEX.md` silently omits them, so search the files, not just the index.
- The `L-N` and `D-N` IDs in `INDEX.md` are positional: N is the heading's order when the index was generated. They are not written in the files, so `rg 'L-42'` usually finds nothing, and some headings carry older ID text that no longer matches. Search by title or tag instead, for example `rg -n '^#{2,3} .*<term>' .living/decisions.md` or `rg -n '^\*\*Tags\*\*:.*<tag>' .living/`.
- Findings differ: topic files use `## F-NNN: Claim` headings, and `FINDINGS_REGISTRY.md` is a table keyed by the same IDs. `F-NNN` is written in the file and stable, so `rg -n 'F-036' .living/findings/` works.
- In the brief, cite a decision or learning by heading title and line number, and a finding by `F-NNN` and topic file.
- Optional helper: `python3 "$(cat .mycelium/plugin-root)/skills/core/scripts/recall_lessons.py" --living-dir .living/ --tag <tag>` (also `--id`, `--since`). Try it at most once. The pointer may be missing or point at an old install, and the script needs Python 3.7 or newer. On any error, fall back to direct reads; do not debug or repair Mycelium during grilling.

## Stay hook-safe

Checked against the 0.6.0 and 0.7.2 hook detectors:

| Action | Mycelium effect |
| --- | --- |
| Reading files, `rg`, `head` | Logged only; no enforcement |
| `python3 -c`, `Rscript -e`, heredoc on stdin, including under `conda run`/`mamba run`/`pixi run`/`uv run` | Does not open the post-action cycle |
| `python path/script.py`, `Rscript path/script.R`, `jupyter nbconvert`/`execute`, with or without an environment wrapper | Opens the post-action cycle; Stop blocks until `.living/` is updated |

Run probes with the interpreter or environment named in `AGENTS.md`, `CLAUDE.md`, or `ENVIRONMENTS_INSTALLATIONS.md`; the system `python3` often lacks the project's packages. Calling the documented interpreter by absolute path (for example `<env>/bin/Rscript -e ...`) is equally hook-safe and works when `conda` is not on `PATH`. For large objects, read headers or use backed/lazy reads; never load a multi-GB object fully.

Inline probes can still leave hook-side lineage or log-registry records. So the read-only promise means the agent makes no edits, not that the session leaves no trace. Probes must never write files.

## Interpret evidence

| Source | Establishes | Does not establish |
| --- | --- | --- |
| Manifest | Registered assets and documented status | That an output is correct or fresh |
| Decision | Past rationale or intent | That later work followed it |
| Learning | Observed caveat or lesson | An active mandate |
| Finding ledger | Reported scientific result and provenance | Generalizability beyond its evidence |
| Convention | Applicable guidance when active | That implementation complies |
| Prior review | Issues and open questions raised at review time | That they were fixed or answered since |
| Global knowledge entry | A transferable pattern from another project | That it applies here, or is validated if `unreviewed` |
| Session handoff | Where the last session stopped | Current state; verify against files and git |
| Code/output | An implemented path or generated artifact | The endorsed scientific rationale |

Track explicit supersession (for example "supersedes", "invalidated", "ADDENDUM" headings) and task applicability. When dates conflict or are absent, inspect nearby commit history or current docs only if the resolution matters. Prefer a short quoted path and your stated inference over an unsupported claim of authority.

## Hand off

- **Execution:** Mycelium's analyze skill (`/mycelium:analyze` in Claude Code, `$mycelium:analyze` in Codex). It reads manifests, creates `analysis/<name>/` with its `UPPER_SNAKE_CASE.md` doc, routes to active conventions, and runs the post-action protocol. The approved plan belongs in that doc, and the brief's "Decisions to record" reach `.living/decisions.md` through that protocol.
- **Neighbours:** interrogating an existing analysis or diff is `/mycelium:review grill`; a full parallel review is `/mycelium:review`. This skill is the pre-execution counterpart and does not replace either.
