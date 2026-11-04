# The analysis layout

One layout for every analysis folder, shared by all the skills. Each skill reads and writes the places named here and nothing else, through `hooks/analysis_paths.py`, so a reader opens the analysis `README.md` and reaches every artifact from there, and `verify` can check every run.

This page is the contract. A skill that needs a path cites this page rather than inventing one. Decided 2026-11-04 (`docs/roadmap/18-analysis-layout.md`).

## The tree

```
analysis/<name>/
├── README.md             the analysis doc: aim, steps table, key findings, Outputs table (the index)
├── Snakefile  run.sh  run.sbatch
├── code/      01_prepare.R  02_fit.R  03_show.R  plot_<panel>.R  theme.R  theme.py  <shared-code links>
├── data/      <links only>  SOURCES.md
├── plans/     PLAN.md (the draft)  TRACKER.md
├── config/    figure_map.tsv  manuscript_checks.json      (manuscript work only)
├── reports/   README.md  <name>.qmd  <name>.html  report.scss  report-dark.scss  site/
├── logs/                 SLURM output only (`run.sbatch`); step logs live in the run
├── outputs/
│   ├── run_<YYYYMMDD>_<slug>[_vNN]/
│   │   ├── RUN.txt
│   │   ├── 01_prepare.tsv  02_fit.parquet          step outputs, NN_ prefix
│   │   ├── figures/  source_data/  tables/         NN_<name>.png|tsv, one stem per figure
│   │   ├── numbers.json  logs/
│   └── current -> run_...
└── provenance/   plan-<hash>.md  receipts-<hash>.jsonl  outputs-<hash>.tsv  verify-<hash>.md  PROVENANCE.md
```

In a Mycelium repository the analysis doc is `<NAME>.md` (the folder name in upper case, `-` as `_`); elsewhere it is `README.md`. `analysis_paths.find_doc` returns whichever exists.

## Rules

1. **A run is a folder.** `outputs/run_<YYYYMMDD>_<slug>/`, with `_vNN` for a later iteration of the same slug. `run.sh` creates it and writes `RUN.txt`; Snakemake writes every step output, log and benchmark inside it. A run folder is never overwritten: a run whose status is `running` or `failed` may be resumed, any other status is refused with a `_vNN` suggestion, and a folder with no `RUN.txt` is refused until someone adds one.
2. **`current` is the only link.** `outputs/current` points at the released run and stays inside the repository; a link to scratch storage is a gap for every check that reads it. The resolver skips runs of kind `scratch` when it has to guess the newest run.
3. **One stem, three places.** A figure `figures/NN_x.png`, its plotted values `source_data/NN_x.tsv` and any summary `tables/NN_x.tsv` share the stem of the step that made them. A figure with no source-data table is a gap: the report lists it under Open items and `verify` under `Not checked`.
4. **`outputs/` holds runs and `current`, nothing else.** Files directly under `outputs/` are the old flat layout; the resolver reads them and names the layout `flat`, so no analysis is migrated. `results/` is read before `outputs/` when it exists, and `RESULTS_DIR` overrides both (`verify runs`).
5. **The Outputs table in the analysis doc is the index.** `analysis-report` appends its rendered report, and `verify write` appends its record. Skills append rows; nobody rewrites the table. A person sets `current`.
6. **`provenance/` stays flat** with hash-named files, read through git by `verify stale` and `verify runs`.
7. **`.snakemake/` stays at the analysis root**, one per analysis; `verify` reads its conda envs there.
8. **Not a record:** `.mycelium-extra/artifacts/<name>.html` (the evaluation page) and a run's `logs/`.
9. **`numbers.json`:** the resolver reads `<run>/numbers.json` first and the flat `outputs/numbers.json` that Mycelium's `register_value` writes second. The clash is Mycelium's to settle; this plugin reads both.

## `RUN.txt`

Written by `run.sh` at launch (`run`, `kind`, `why`, `plan`, `labeled`, `status: running`); `run.sh` sets `done` or `failed` at exit; a person sets `current`, `side` or `superseded`. `verify runs` lists it, `track-changes` watches the `status` line, `handoff` quotes it.

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

Written by the scaffold; `analysis-report` updates the run cell after a render.

```
# Reports

| File | What it is | From run | Owner |
|---|---|---|---|
| `<name>.qmd` | the record | `run_20261104_baseline` | analysis-report |
| `<name>.html` | its render, 2026-11-04 | same | quarto render |
| `report.scss`, `report-dark.scss` | theme, DESIGN.md tokens | — | you |
| `site/` | step pages (qmd steps only) | — | Snakefile |

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
| run.sh, Snakemake | `code/`, `data/` | the run folder, `RUN.txt` |
| verify | receipts, the run, `provenance/` | `provenance/`, one row in the Outputs table |
| analysis-report | the run through `current`, `numbers.json`, `figures/`, `source_data/`, `tables/` | `reports/<name>.qmd`, the run cell in `reports/README.md`, one row in the Outputs table |
| analysis-report artifact | the filled `.qmd`, `numbers.json`, the figures | `.mycelium-extra/artifacts/<name>.html`, one line in `TRACKER.md` |
| plot-first | `figures/` of the current run, `provenance/outputs-<hash>.tsv` | nothing |
| track-changes | `plans/`, `code/`, `reports/*.qmd`, `outputs/*/RUN.txt` | `.mycelium-extra/track-changes/` |
| handoff | the doc, `current`, `RUN.txt`, `plans/` | `HANDOFF.md` |
| manuscript-audit, data-contract-check | `config/`, `outputs/current/` | nothing |

Mycelium's own files (`.living/`, `analysis/ANALYSIS_MANIFEST.md`, `todo/`) are read where present and never written by this plugin.
