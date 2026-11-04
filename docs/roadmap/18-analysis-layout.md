# 18 · Analysis layout (2026-11-04)

[Back to roadmap](README.md)

Objective: give every analysis folder one layout that all skills read and write (run folders, `current`, `RUN.txt`, theme templates, an Outputs index, one set of status words) and route the skills to each other. Plan approved 2026-11-04; built for `0.24.0`. The contract is [the analysis layout](../concepts/analysis-layout.md).

Statuses: `todo`, `in progress`, `built`, `done`, `parked`, `dropped: <reason>`, `blocked: <question for the user>`.

| ID | Item | Source | Touches | Status |
|---|---|---|---|---|
| D0 | The contract page: tree, rules, `RUN.txt`, status words | plan review of 2026-11-04 | `docs/concepts/analysis-layout.md` | in progress |
| D1 | Resolver `current_run`, `runs`, `numbers`, `figures`, `tables`; flat fallback named `flat`; honours `RESULTS_DIR` | D0 | `hooks/analysis_paths.py` | in progress |
| D2 | Run-folder Snakefile and `run.sh`; default steps; `reports/README.md`, `data/SOURCES.md`; `theme.R` and `theme.py` with `theme_pubr(base_size = 8)` | D0, decisions 2 to 6, 12, 13 | `skills/new-analysis/` | in progress |
| D3 | Report, plot-first, verify `runs` and handoff read the run through the resolver | D1 | `skills/analysis-report/`, `skills/plot-first/`, `skills/verify/scripts/verify.py`, `skills/handoff/SKILL.md` | in progress |
| D4 | `verify write` appends its row to the Outputs table; track-changes reports a `RUN.txt` status change | D0 index rule | `skills/verify/scripts/verify.py`, `skills/track-changes/scripts/track_changes.py` | in progress |
| D5 | Outputs line in the brief names the run folder, never a flat file | gate pins named outputs | `skills/grill/references/brief-format.md` | in progress |
| D6 | Docs: commands, walkthrough, installation host rows, this tracker, changelog | D0 | `docs/`, `CHANGELOG.md` | in progress |
| D7 | Shared helpers `find_doc`, `repo_root`, `read`, `fill`, `sha256` used by verify, plot-first, focus and analysis-report | integration review | `hooks/analysis_paths.py` and callers | in progress |
| D8 | Status words (`pass / gap / fail / stale / not verified`) on every surface a person reads; role-tagged questionnaire answers | decision 10 | artifact page, viewer, `skills/questionnaire/SKILL.md` | in progress |
| D9 | Routing: grill to decision-status and plan-review; verify and track-changes point at each other; handoff and new-analysis fixes | integration review | `skills/grill/SKILL.md`, `skills/verify/SKILL.md`, `skills/track-changes/SKILL.md` | in progress |

Open with Mycelium: `register_value` writes one `outputs/numbers.json` per analysis, so a rerun overwrites the numbers a report cites. This plugin reads `<run>/numbers.json` first and the flat file second; the question is the user's to send.
