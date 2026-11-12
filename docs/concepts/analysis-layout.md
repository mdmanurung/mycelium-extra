# The analysis layout

One layout for every analysis folder, shared by all the skills. Each skill reads and writes the places named here and nothing else, through `hooks/analysis_paths.py`, so a reader opens the analysis `README.md` and reaches every artifact from there, and `verify` can check every run.

This page is the contract. A skill that needs a path cites this page rather than inventing one. Decided 2026-11-04, changed to overwrite-in-place on 2026-11-12 (`docs/roadmap/18-analysis-layout.md`).

## The tree

```
analysis/<name>/
├── README.md             the analysis doc: aim, steps table, key findings, Outputs table (the index)
├── Snakefile  run.sh  run.sbatch
├── code/      01_prepare.R  02_fit.R  03_show.R  plot_<panel>.R  theme.R  theme.py  <shared-code links>
├── data/      <links only>  SOURCES.md
├── plans/     PLAN.md (the draft)  TRACKER.md
├── config/    figure_map.tsv  manuscript_checks.json      (manuscript work only)
├── reports/   README.md  <name>.qmd  <name>.html  report.scss  report-dark.scss
├── logs/
│   ├── CHANGES.md        one entry per run.sh run: code files changed, step folders rewritten
│   ├── .code-hashes.tsv  state for CHANGES.md: last logged sha256 of each code/ file
│   └── slurm-*.out       SLURM output (`run.sbatch`)
├── outputs/
│   ├── 01_prepare/       01_prepare.tsv  logs/01_prepare.log
│   ├── 02_fit/           02_fit.parquet  tables/02_fit.tsv
│   ├── 03_show/          figures/03_show.png  source_data/03_show.tsv
│   ├── 04_report/        04_report.html  (a qmd step renders here)
│   └── numbers.json      Mycelium's register_value
└── provenance/   plan-<hash>.md  receipts-<hash>.jsonl  outputs-<hash>.tsv  verify-<hash>.md  PROVENANCE.md
```

In a Mycelium repository the analysis doc is `<NAME>.md` (the folder name in upper case, `-` as `_`); elsewhere it is `README.md`. `analysis_paths.find_doc` returns whichever exists.

## Rules

1. **A script owns one folder.** The step `code/NN_name.R` writes to `outputs/NN_name/` and nowhere else. A rerun overwrites that folder; old outputs are not kept. Code in `code/` is edited in place, with no versioned copies, and `logs/CHANGES.md` records what changed. Step folders are the `NN_` or `NNa_` names (two digits, an optional letter, an underscore). A qmd step renders its HTML into its own folder, `outputs/NN_name/NN_name.html`. Notebooks, qmd pages and figure scripts get two environment variables: `STEP_DIR` (the step's own folder) and `OUTPUTS` (the `outputs/` root, to read earlier steps). `RUN_DIR` is retired for new analyses.
2. **`current` is optional.** A new analysis has no run to release, because `outputs/` is the current state. An `outputs/current` link still wins when it exists and stays inside the repository; a link to scratch storage is a gap for every check that reads it. For old run folders the resolver skips runs of kind `scratch` when it has to guess the newest run.
3. **One stem, three places.** A figure `figures/NN_x.png`, its plotted values `source_data/NN_x.tsv` and any summary `tables/NN_x.tsv` share the stem of the step that made them, and sit inside that step's folder. A figure with no source-data table is a gap: the report lists it under Open items and `verify` under `Not checked`.
4. **`outputs/` holds step folders and `numbers.json`.** The resolver names this layout `steps` and gathers `figures/`, `source_data/` and `tables/` over all step folders. Old layouts are still read unchanged: `run_<YYYYMMDD>_<slug>` folders (see Legacy run folders) and files directly under `outputs/` (named `flat`). No analysis is migrated. When step folders and old run folders sit side by side, the steps entry comes first. `results/` is read before `outputs/` when it exists, and `RESULTS_DIR` overrides both (`verify runs`).
5. **The Outputs table in the analysis doc is the index.** `analysis-report` appends its rendered report, and `verify write` appends its record. Skills append rows; nobody rewrites the table.
6. **`provenance/` stays flat** with hash-named files, read through git by `verify stale` and `verify runs`. A rerun changes the files a record hashed, so the record reads `stale`. That is the signal to verify again.
7. **`.snakemake/` stays at the analysis root**, one per analysis; `verify` reads its conda envs there.
8. **Not a record:** `.mycelium-extra/artifacts/<name>.html` (the evaluation page) and a step's `logs/`.
9. **`numbers.json`:** Mycelium's `register_value` writes `outputs/numbers.json`, and the resolver reads it. On an old run folder the resolver reads `<run>/numbers.json` first. The clash is Mycelium's to settle; this plugin reads both.

## `logs/CHANGES.md`

`run.sh` appends one entry after each real run (a dry run, `-n`, logs nothing). The entry has a level-2 heading, then the changes. The heading is `## <YYYY-MM-DD HH:MM> <git short hash>[ dirty] <ok|failed>`. The body lists each `code/` file whose sha256 differs from `logs/.code-hashes.tsv` (with `git diff --stat` for it when it is tracked), then each `outputs/<stem>/` folder written during the run. `run.sh` then rewrites `.code-hashes.tsv`. Entries are appended, never edited.

```
## 2026-11-12 14:05 d582fa5 dirty ok

Code changed:
- code/02_fit.R (2 files changed, 6 insertions(+), 2 deletions(-))

Outputs rewritten:
- outputs/02_fit/
- outputs/03_show/
```

`track-changes` watches this file, `verify runs` and `analysis-report` show the newest heading, and `handoff` quotes it. `analysis_paths.change_log(folder)` returns its path and `last_change(folder)` returns the newest heading line.

## Legacy run folders

Analyses made before `0.25.0` keep their `outputs/run_<YYYYMMDD>_<slug>[_vNN]/` folders, and the resolver still reads them unchanged. Each holds a `RUN.txt` that `run.sh` wrote at launch (`run`, `kind`, `why`, `plan`, `labeled`, `status: running`) and set to `done` or `failed` at exit. A person sets `current`, `side` or `superseded`. `verify runs` lists it, `track-changes` watches the `status` line, `handoff` quotes it. New analyses do not write run folders or `RUN.txt`.

```
# run
run: run_20261104_baseline
kind: analysis            # analysis | figures | scratch
status: current           # running | done | current | side | superseded | failed | scratch

# origin
why: paired titre change day 0 to 28, 8 donors
plan: 596f0693
labeled: 2026-11-04 by run.sh

# links
superseded_by:
reads:
version:
notes: rerun of the 20261030 run with the corrected donor table
```

Lines are `key: value`; blank lines and `#` lines are skipped; an inline ` #` comment is stripped. `version` (a free label) and `reads` (run names this run read) are optional keys. `kind` outside `analysis | figures | scratch` is a verify gap. `superseded_by` is set only when a person confirms it.

## `reports/README.md`

Written by the scaffold; `analysis-report` updates the run cell after a render. A qmd step's page is in its own step folder, so the table has no site row.

```
# Reports

| File | What it is | From run | Owner |
|---|---|---|---|
| `<name>.qmd` | the record | `outputs/` (steps), or a legacy run name | analysis-report |
| `<name>.html` | its render, 2026-11-04 | same | quarto render |
| `report.scss`, `report-dark.scss` | theme, DESIGN.md tokens | — | you |

The Artifact evaluation page lives in `.mycelium-extra/artifacts/` and is not a record.
```

## `data/SOURCES.md`

Written by the scaffold, one row per link in `data/`; the plan column is filled when a grill plan that names the file is approved.

```
# Data sources

| Link | Target | DATA_MANIFEST | Pinned by plan |
|---|---|---|---|
| `counts.tsv` | `data/raw/counts.tsv` | raw-counts-v3 | 596f0693 |
| `donors.csv` | `data/meta/donors.csv` | not listed | 596f0693 |
```

## Status words

Surfaces a person reads say the same five words. `verify` keeps its machine words in its reports and provenance files, because tests and `verify stale` parse them.

| Person reads | `verify` status | Contract check (`manuscript-audit`, `data-contract-check`) | `track-changes` bucket (JSON `v1` name) | Meaning |
|---|---|---|---|---|
| pass | `CONFORMS` | `pass` | `pass` (`authorized`) | checked, and it held |
| gap | `CONFORMS_WITH_GAPS` | `gap`, `warn` | `gap` (`attention`) | could not be checked, or evidence is missing; never a pass |
| fail | `DOES_NOT_CONFORM` | `block` | `gap` (`attention`) with a failed check | checked, and it did not hold |
| stale | a `stale` finding | — | `gap` (`attention`) with a changed pin | the file changed after the run or the approval |
| not verified | no `provenance/` entry | — | — | nothing has checked it |
| routine | — | — | `routine` | not a verdict: read-only or outside the plan |

`plot-first` writes `unsupported: no inspected figure` for a conclusion with no figure; that is a `gap` on every surface.

## Who reads and writes what

| Skill | Reads | Writes |
|---|---|---|
| new-analysis | — | the tree, `plans/`, `reports/README.md`, `data/SOURCES.md`, `code/theme.*` |
| grill | the analysis doc, `plans/PLAN.md`, `data/` | nothing (the gate pins `data/` links at approval) |
| run.sh, Snakemake | `code/`, `data/` | `outputs/<stem>/` per step, `logs/CHANGES.md`, `logs/.code-hashes.tsv` |
| verify | receipts, the step folders, `logs/CHANGES.md`, `provenance/` | `provenance/`, one row in the Outputs table |
| analysis-report | the step folders (or `current`), `numbers.json`, `figures/`, `source_data/`, `tables/`, the last `CHANGES.md` entry | `reports/<name>.qmd`, the run cell in `reports/README.md`, one row in the Outputs table |
| analysis-report artifact | the filled `.qmd`, `numbers.json`, the figures | `.mycelium-extra/artifacts/<name>.html`, one line in `TRACKER.md` |
| plot-first | `outputs/*/figures/` (or the current run's `figures/`), `provenance/outputs-<hash>.tsv` | nothing |
| track-changes | `plans/`, `code/`, `reports/*.qmd`, `logs/CHANGES.md`, `outputs/*/RUN.txt` (legacy) | `.mycelium-extra/track-changes/` |
| handoff | the doc, `logs/CHANGES.md`, `current` and `RUN.txt` (legacy), `plans/` | `HANDOFF.md` |
| manuscript-audit, data-contract-check | `config/`, `outputs/` (or `outputs/current/`) | nothing |

Mycelium's own files (`.living/`, `analysis/ANALYSIS_MANIFEST.md`, `todo/`) are read where present and never written by this plugin.
