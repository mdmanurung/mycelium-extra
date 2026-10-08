# C1: fixture Mycelium project and planted defects

Design for roadmap task [C1](../roadmap/03-robustness.md#c1-fixture-mycelium-project-for-end-to-end-tests). Written against `main` at `3a11123`. Every expected message below is copied from the code at that commit; the implementer confirms each code path before writing its case (the C1 grill prompt asks for this), and updates this file when a message changes.

## 1. What it is for

Each skill has unit tests on synthetic, minimal inputs. C1 adds one realistic project and a harness that drives the whole chain a researcher goes through: init, data contract, plan approval, gated runs, verify, provenance, stale and status sweeps. It answers three questions the unit tests cannot:

1. **Hand-offs.** Does the output of one step satisfy the next step on a project that looks like a real one (Mycelium layout, several scripts, two languages, a findings ledger)?
2. **Checklist honesty.** For each row of `skills/grill/references/llm-failure-modes.md` whose Check column names a tool, is there a planted defect that the tool actually catches? For rows marked `none`, is the miss recorded, so that a future check flips the test on purpose?
3. **A test bed for later tasks.** D1 (claims), D2 (citations), D4 (multiplicity), C3 (redaction), E1 to E5, and D10 to D12 get their fixtures here instead of each inventing one.

### Not tested here

- grill, plan-review, or any LLM behaviour. The harness uses a fixed plan text that stands in for grill's output. Grill's behaviour stays covered by `scenarios.md` walk-throughs.
- Mycelium's own hooks. The harness writes the files Mycelium would write (a data-lineage manifest), in the documented format, and never runs Mycelium code.
- Real Slurm, Snakemake, conda, scilintr, or R. These are faked by default. R is used only when `Rscript` is on `PATH`, and the real R linter only when `MX_E2E_REAL_TOOLS=1` (with `MX_E2E_RSCRIPT` naming an `Rscript` off `PATH`; E4).
- Codex. Codex runs produce no receipts (E3).

## 2. Design rules

- **Commit content, not the timeline.** Verify compares file times with approval and receipt times, and git checkouts reset file times. So the repository commits only the project's content. The harness builds the timeline on every run: it copies the project, backdates it, commits it, approves the plan, runs the steps, and calls the hooks. Approvals and receipts always come from the real hooks, as in `skills/verify/tests/test_verify.py`.
- **One clean baseline, one defect per case.** The baseline must reach `Verify status: CONFORMS` and pass every contract check. Each defect is a small mutation applied to a fresh copy of the baseline, so a failing case names exactly one cause.
- **Expected misses are tests too.** A defect that no tool catches today is a case asserting the miss (`known_miss=True`). When a check starts catching it, the case fails, and the checklist row and this file are updated in the same commit.
- **Known bugs use `unittest.expectedFailure`.** The case asserts the correct behaviour, and the decorator names the roadmap task. From Python 3.4, an unexpected success fails the run, so a fix forces the decorator to be removed.
- **Hermetic.** stdlib only, Python 3.6 grammar. No network. Hook and skill subprocesses get a scrubbed environment (section 6.3).
- **Small.** The project stays under 40 files and 200 KB, so a reviewer can read all of it.

## 3. Layout

```
tests/
├── fixtures/
│   ├── README.md                         what the fixture is, how to regenerate it, the size budget
│   ├── make_fixture_data.py              deterministic generator (section 4); --check compares with the committed files
│   └── mycelium-project/                 the project (32 files)
│       ├── MYCELIUM.md                   Mycelium protocol stub; names the convention "results come from analysis/ only"
│       ├── CLAUDE.md                     Mycelium routing block (grill reads it)
│       ├── AGENTS.md                     same, for Codex
│       ├── ENVIRONMENTS_INSTALLATIONS.md names a conda env `vaccine-de` (used by V-17)
│       ├── .gitignore                    `.mycelium/` only; init adds `.mycelium-extra/`
│       ├── .living/
│       │   ├── INDEX.md
│       │   ├── decisions.md              5 entries (section 3.2)
│       │   ├── learnings.md              2 entries; one carries a `structural_mitigation_candidate` (E4: harden)
│       │   ├── conventions.md
│       │   ├── log/LOG_REGISTRY.md
│       │   ├── log/2026-09-01-001-setup.md
│       │   └── findings/
│       │       ├── FINDINGS_REGISTRY.md  F-001 listed
│       │       └── vaccine-response.md   F-001 with an Evidence Ledger row; Run/Session cell filled by the harness
│       ├── data/
│       │   ├── DATA_MANIFEST.md          one YAML entry, `status: processed`, marked SIMULATED
│       │   ├── raw/vaccine-cohort/VACCINE_COHORT.md         says raw FASTQs are not included
│       │   ├── processed/vaccine-cohort/sample_metadata.tsv 25 rows (section 4)
│       │   ├── processed/vaccine-cohort/counts.tsv          60 genes x 25 libraries
│       │   └── metadata/vaccine-cohort/DATA_DICTIONARY.md   defines `run_id` as "sequencing run (the lab calls it seq batch)"
│       ├── analysis/
│       │   ├── ANALYSIS_MANIFEST.md      YAML entry for vaccine-response, `status: active`
│       │   └── vaccine-response/
│       │       ├── VACCINE_RESPONSE.md   analysis doc; Key Findings carry the numeric claims D1 checks
│       │       ├── scripts/01_select_samples.py   filter, log counts in and out, write samples_used.tsv
│       │       ├── scripts/02_paired_test.py      join by sample_id, median-of-ratios, exact permutation, BH
│       │       ├── scripts/03_summary.R           base R: hit count and median log2FC of hits
│       │       ├── scripts/04_extra_plot.py       not in the plan (scope-growth defects)
│       │       ├── run.sh                         wrapper: runs 01, 02, 03 in order
│       │       ├── Snakefile                      same steps, in the rule shape new-analysis generates
│       │       ├── run_all.sbatch                 Slurm script: the same steps in one job (wrapper defects)
│       │       ├── outputs/.gitkeep
│       │       └── reports/report.Rmd             one R chunk (E4, E5)
│       ├── nbs/qc_explore.ipynb          explore notebook (gated path `nbs/**`); Python kernel
│       ├── nbs/r_explore.ipynb           R-kernel notebook, one R cell (E4)
│       └── todo/TODO_REGISTRY.md
├── e2e/
│   ├── harness.py                        Project class (section 6)
│   ├── defects.py                        the catalog (section 8), one entry per defect
│   ├── ablate.py                         guard ablations (section 10)
│   ├── plans/baseline_plan.md            the approved plan text (section 5.1)
│   ├── plans/baseline_contract.json      the plan's data contract (section 5.2)
│   └── expected/
│       ├── baseline.json                 statuses, counts, and values the baseline must produce
│       ├── truth.json                    simulated ground truth; kept outside the project so no step can read it
│       ├── summary.tsv                   03_summary.R output (generator's Python twin, checked against real R); used when R is absent
│       └── claims.json                   D1's claims block lines and the numbers it leaves as info
├── test_fixture_data.py                  runs make_fixture_data.py --check, a refused seed, and the size budget
└── test_end_to_end.py                    baseline chain, one case per defect, catalog contract tests
```

### 3.1 Which skill reads what

| File or folder | Read by | Purpose in the fixture |
| --- | --- | --- |
| `.mycelium-extra/gate.json` (created by init) | gate, verify, init | turns the gate on; default `gated_paths` `analysis/**`, `nbs/**` |
| `.living/` exists | gate post hook, new-analysis, hints | switches on the Mycelium-specific notices |
| `.living/decisions.md` | decision-status, grill | a decision thread on normalisation |
| `.living/learnings.md` | harden, grill | one hardenable learning |
| `.living/findings/vaccine-response.md` | verify `stale` (its `rg` command), D1 | the finding that rests on the plan |
| `.living/log/data-lineage/<sid>.json` (written by the harness) | verify | Mycelium's record of what ran |
| `data/processed/vaccine-cohort/*.tsv` | data-contract-check, gate pins, scripts | the inputs pinned on the plan's `Inputs:` line |
| `analysis/ANALYSIS_MANIFEST.md` | verify `status` | `listed: active` |
| `analysis/vaccine-response/` | gate, verify, scilintr | the analysis folder verify infers from `scripts/` |
| `analysis/vaccine-response/provenance/` (written by `verify write`) | verify `stale`, `status` | committed provenance |
| `.snakemake/metadata/` (written by the harness) | verify | Snakemake records for wrapper defects |

The layout follows Mycelium's `skills/core/references/folder-structure.md` at Mycelium 0.8.1 (upstream `3e810b9`). The README says mycelium-extra was tested with Mycelium 0.6.0 and 0.7.2, so A5 should add 0.8.1 once this fixture passes against it. `tests/fixtures/README.md` records the Mycelium version the layout follows.

### 3.2 Memory content

`decisions.md` uses Mycelium's decision-log template (`### [YYYY-MM-DD] Title`, then `**Context**`, `**Decision**`, `**Rationale**`, `**Status**`, `**Supersedes**`, `**Tags**`):

1. `[2026-03-02] Normalisation: median-of-ratios`, status confirmed.
2. `[2026-04-01] Exclusion: keep preferred acquisitions only`. Re-sequenced libraries carry `preferred_acquisition=FALSE`.
3. `[2026-04-20] Batch: run_id is the sequencing batch`. The prose says "seq batch", the header says `run_id`. This sets up DC-01.
4. `[2026-05-10] Normalisation: hold pending spike-ins`, status held.
5. `[2026-07-15] Normalisation: TMM considered, median-of-ratios stays`, status confirmed, supersedes entry 4.

decision-status run with `--term normalisation` must list entries 1, 4, and 5, oldest first, with their raw status fields, and must not say which one is current.

`learnings.md` holds two entries:

- "Spreadsheet round-trip renamed MARCHF1 to 1-Mar", `mitigation_type: ambient-awareness`, with `structural_mitigation_candidate`: assert that no value in the counts table's `gene` column matches a date pattern. harden's target in E4.
- An entry with a vague candidate ("be careful with joins"), which harden must skip.

## 4. Simulated data

**Design.** There are 12 donors: D01 to D06 in the vaccine arm and D07 to D12 in the placebo arm. Each is sampled at `day0` and `day28`, giving 24 libraries. A 25th library, `D03_day28_rerun`, is a re-sequenced copy with `preferred_acquisition=FALSE`; it is removed by the contract filter and by decision 2. Three sequencing runs, `R1` to `R3`, each hold both arms, and both of a donor's samples share a run. `lane` is L1 or L2. `rin` is between 6.5 and 9.5.

`sample_metadata.tsv` columns: `sample_id donor arm visit run_id lane preferred_acquisition rin`.

`counts.tsv` has 60 genes in rows. The column `gene` holds real HGNC symbols, and the other columns are `sample_id`s, in an order different from the metadata. That way a positional join gives wrong results and a join by ID gives right ones (DC-09). Eight interferon-response genes are the true signal: IFI27, IFI44L, ISG15, MX1, RSAD2, SIGLEC1, IFIT1, OAS1. They are up 4-fold (log2FC 2) at day 28 in the vaccine arm only. The other 52 genes are nulls; they include MARCHF1 and SEPTIN7 for DC-10. Counts are generated as follows:

- a log-normal base mean per gene, between 50 and 2000;
- a donor effect with SD 0.4 on the log scale;
- residual noise with SD 0.25;
- a library-size factor between 0.7 and 1.3.

`DATA_MANIFEST.md`, `DATA_DICTIONARY.md`, and `VACCINE_COHORT.md` say SIMULATED. The TSVs carry no comment header, because data-contract-check reads them with `csv.DictReader`, which would take a `#` line as the header.

**Analysis.** `02_paired_test.py` does the following:

1. Computes median-of-ratios size factors.
2. Computes each donor's day28 minus day0 difference in log2(normalised count + 1).
3. Takes the vaccine-mean minus placebo-mean difference. The reference is placebo, and a positive value means higher in vaccine.
4. Runs an exact two-sided permutation test over all C(12,6) = 924 arm labellings; the smallest possible p is 2/924 = 0.0022.
5. Applies BH at 0.05.

It writes `de_results.tsv` (`gene log2fc p padj`).

**Feasibility.** A stdlib probe of this design (`c1_feasibility_probe.py`, delivered with this document, not committed) ran 30 seeds:

- With median-of-ratios, 12 of the 30 recover exactly the 8 true genes with no false positives.
- With total-count CPM, the effect on those 12 seeds varies, because 8 of 60 genes rising 4-fold shift every other gene's share. Nine give at least one false positive, and five (seeds 0, 1, 5, 16, 25) give at least 3. Two lose true genes without adding any (seeds 13, 27), and one matches median-of-ratios exactly (seed 28). Seed 0 gives 6 false positives under CPM and none under median-of-ratios.

A design with more genes fails differently: at 200 genes, BH cannot reach 0.05 for 8 hits, because the permutation floor (0.0022 × 200 / 8 = 0.054) is above it. So the gene count is part of the design, not a free parameter.

**Generator.** `make_fixture_data.py --seed N` (default 0) writes the two TSVs. Its simulation reproduces the probe draw for draw, so seed N gives the probe's seed N result. It runs 01 and 02 on a temporary copy, checks that 02's hits equal its own analysis, computes 03's summary with a Python twin (R's median, `sprintf("%.4f")`), and writes the values to `expected/baseline.json` (row counts and SHA-256 of each output), `expected/truth.json`, and `expected/summary.tsv`. The end-to-end test compares `expected/summary.tsv` with the real R output when R is present. It also fills the Key Findings numbers in `VACCINE_RESPONSE.md`. It selects the seed by stated criteria and refuses one that fails them:

- exactly the 8 true genes at `padj < 0.05` under median-of-ratios;
- at least 3 false positives under total-count CPM, so DC-11 has an effect.

`--check` regenerates the files in memory and compares them with the committed ones, so hand edits to the data fail the suite.

## 5. Baseline plan and contract

### 5.1 Plan text (`plans/baseline_plan.md`)

```
**Objective.** Test whether the day 28 minus day 0 change in gene expression differs between vaccine and placebo arms (reference: placebo; positive log2FC means higher in vaccine).

Inputs: data/processed/vaccine-cohort/sample_metadata.tsv data/processed/vaccine-cohort/counts.tsv
Outputs: analysis/vaccine-response/outputs/samples_used.tsv analysis/vaccine-response/outputs/de_results.tsv analysis/vaccine-response/outputs/summary.tsv

| # | Step | Choice | Source | Validation |
|---|---|---|---|---|
| 1 | run `analysis/vaccine-response/scripts/01_select_samples.py` | keep preferred_acquisition == TRUE | repo: .living/decisions.md | 24 rows, 12 donors x 2 visits |
| 2 | run `analysis/vaccine-response/scripts/02_paired_test.py` | median-of-ratios; exact permutation; BH 0.05 | repo: .living/decisions.md | sample IDs identical across tables |
| 3 | run `analysis/vaccine-response/scripts/03_summary.R` | hits at padj < 0.05 | default: matches step 2 | summary row count 1 |

Plan status: READY
```

The `Outputs:` line names files, not the folder, so that a step that fails silently leaves a missing output that verify reports (V-02a). Folder-level `Outputs:` lines hide it.

### 5.2 Contract (`plans/baseline_contract.json`)

```json
{
  "schema": "mycelium-extra.data_contract.v1",
  "table": "data/processed/vaccine-cohort/sample_metadata.tsv",
  "filters": [{"column": "preferred_acquisition", "equals": "TRUE"}],
  "checks": [
    {"kind": "schema", "columns": ["sample_id", "donor", "arm", "visit", "run_id"]},
    {"kind": "cohort", "column": "arm", "levels": ["vaccine", "placebo"], "rows": 24, "no_missing": ["run_id"]},
    {"kind": "unit_of_replication", "unit": "donor", "group": "arm", "within": ["visit"], "min_units_per_group": 6},
    {"kind": "pairing", "unit": "donor", "within": "visit", "levels": ["day0", "day28"]},
    {"kind": "batch_confounding", "batch": "run_id", "contrast": "arm"}
  ]
}
```

## 6. Harness (`tests/e2e/harness.py`)

### 6.1 `Project`

- `Project.fresh()` does the following:
  1. Copies `fixtures/mycelium-project/` to a temporary directory.
  2. Sets every file's mtime to one hour ago.
  3. Runs `git init`, then commits with a fixed author and committer.
  4. Runs init, `python3 - < skills/init/scripts/gate_init.py`.
  5. Commits the `.gitignore` change, so the tree is clean, as after a real `init`.
- `hook(entry, payload)` runs `hooks/gate_run.py <entry>`, the command `hooks/hooks.json` registers, with `session_id`, `cwd` and `hook_event_name` added. The harness reads `hooks.json` at test time to map each Claude Code event to its gate entry (`PreToolUse` -> `tool`, `PostToolUse` -> `post`, and so on).
- `approve(plan_text)` calls the Stop hook with the plan as `last_assistant_message`. It takes the hash from `approve plan <hash>` in the notice, then calls the prompt hook. It returns the hash and the notice.
- `agent_bash(command, effect=None)` acts as the agent's Bash call:
  1. Calls PreToolUse; if denied, returns the denial without running.
  2. Otherwise runs the command in the project with the scrubbed environment.
  3. Sends the event Claude Code sends (hooks reference): on success, `PostToolUse` with `tool_response = {"stdout", "stderr", "interrupted", "isImage"}` and no exit code; on failure, `PostToolUseFailure` with a top-level `error` whose first line is `Exit code N`, plus `is_interrupt` and `duration_ms`, and no `tool_response`. The failure event reaches the gate only if `hooks.json` registers it (today it registers only `PostToolUse`; E3 adds the failure event), so a failed run leaves no receipt before E3. `response="legacy"` sends `PostToolUse` with `{stdout, stderr, exit_code}` for targeted tests.
  4. Returns the run result and the new receipts.

  With the realistic shape, verify's script rows read `ran (exit status not recorded)` and add no finding (KB-04), so the baseline still reaches `CONFORMS` on the current code.

  Commands the sandbox cannot run are given an `effect` instead of running: `sbatch` (stdout `Submitted batch job 4242`), `snakemake`, and `Rscript` when R is absent. The `effect` writes the files the real command would write, and the run is marked simulated in the test log.
- `skill(name, documented, run=None)` runs a skill command in its documented stdin form. It first sends that exact command through PreToolUse and asserts the gate stays silent, so each skill's documented command must pass its own plugin's gate; then it runs the command (or `run`, for verify's augmented form) with `bash -c` from the project root and sends `PostToolUse`. `data_contract(text)` builds the documented `python3 - --contract <(cat <<'EOF' ... EOF
) < data_contract_check.py` form; the process substitution needs bash, so it runs through `bash -c`, with no temporary contract file.
- `lineage(*runs)` writes `.living/log/data-lineage/<sid>.json` in Mycelium's manifest format, with `session_id` and `actions` entries holding `ts`, `script`, and `bash_cmd`. By default it lists every Python or R run `agent_bash` made, as Mycelium's tracker would.
- `snakemake_record(output, rule, inputs, shellcmd, incomplete=False)` writes one `.snakemake/metadata/<base64 name>` JSON, as `test_verify.py` does.
- `verify(*args)` runs `python3 - --plugin-root <repo> --repo <project> --sacct <fake> --scilintr <fake> --rscript <fake> ... < verify.py`.

### 6.2 Fake tools

They are written to `<tmp>/bin` per test:

- `sacct` prints one pipe-separated line, set by the case. The default is `4242|COMPLETED|0:0|<start>|<end>`.
- `scilintr` prints nothing and exits 0 by default. V-14 makes it print one finding in scilintr's line format and exit 1.
- `Rscript-lint` is the `--rscript` that verify calls to lint R. It behaves as `scilintr`.

### 6.3 Environment

Hook and skill subprocesses get the following environment:

- `PATH` set to `<tmp>/bin` followed by the system `PATH`.
- `HOME=<tmp>/home`, because verify reads `~/.conda/environments.txt` and `~/.claude/plugins`.
- `TZ=UTC`, `LC_ALL=C`, and `PYTHONDONTWRITEBYTECODE=1`.
- `GIT_CONFIG_NOSYSTEM=1`, with a fixed author and committer.

These variables are removed: `CONDA_PREFIX`, `CONDA_DEFAULT_ENV`, `VIRTUAL_ENV`, `PIXI_ENVIRONMENT_NAME`, and `CLAUDE_PLUGIN_ROOT`. Without this, a developer's active conda env enters the receipts' `hook_env`, and verify reports a conda gap that is not in the fixture. If git is absent, the end-to-end tests skip with that reason.

### 6.4 Time

There is no `sleep`. The gate stamps receipts with `time.time()` and has no way to inject a time, so the harness moves output mtimes instead, with `os.utime`, relative to the receipt `ts` values. Verify ties an output to the earliest non-job receipt with `ts >= mtime - 5` (`TOLERANCE`), and the three runs finish a few hundred ms apart, so without spacing `de_results.tsv` and `summary.tsv` are credited to run 01 (the report still says `CONFORMS`, since run 01 is under the same plan). `space_outputs([(output, receipt), ...])` therefore moves each output whose mtime would also credit an earlier receipt to the midpoint of `(previous receipt ts + 5, its receipt ts + 5]`, and fails if that window is under 20 ms. Outputs can so carry an mtime up to about 5 s in the future; nothing in verify objects. "Before the approval" means at least 60 s before (fixture files are set one hour back). The baseline chain takes about 5 s per run.

## 7. Baseline chain (`test_baseline_chain`)

| Step | Action | Must hold |
| --- | --- | --- |
| 1 | `Project.fresh()` | init prints `created .../gate.json`. A second init prints `already gated:` and changes nothing |
| 2 | data contract, documented form, via `bash -c` | gate silent; exit 0; 5 lines `PASS`; no alerts |
| 3 | `approve(baseline_plan)` | the Stop notice offers `approve plan <hash>` and lists both pinned inputs; the prompt hook records the approval |
| 4 | `agent_bash` 01, 02, 03, then a read-only `python3 -c` probe of the counts header | gate silent for each; three receipts naming the plan; the probe has no receipt; all three outputs match `expected/baseline.json`; then `space_outputs` (6.4) |
| 5 | `lineage()` | manifest lists the three runs and the probe (`script: null`) |
| 6 | `verify report <hash>` | `Verify status: CONFORMS`; all three scripts `ran` (today `ran (exit status not recorded)`, see 6.1); three outputs tied to their runs; `1 inline command(s)` info; analysis folder `analysis/vaccine-response` |
| 7 | `verify write <hash> --analysis-dir analysis/vaccine-response` (the gate allows the documented form; checked) | `provenance/PROVENANCE.md`, the frozen plan, receipts, and outputs files exist; then commit them |
| 8 | `verify status --json` | one row: `CONFORMS`, `listed: active`, lint `clean` |
| 9 | `verify stale` | no stale plans |
| 10 | decision-status `--term normalisation` | entries 1, 4, 5 in date order with raw status fields |
| 11 | new-analysis `--dest=analysis/followup` | scaffold created; prints a suggested `ANALYSIS_MANIFEST.md` entry; a second run on the same dest refuses |

R: with `Rscript` on PATH, 03 runs for real; `test_baseline_chain_without_r` drops every PATH entry holding `Rscript` and runs 03 as an effect that copies `expected/summary.tsv`, with a real receipt. Both run in the suite.

The harness fills F-001's Evidence Ledger Run/Session cell with `<session-id>; plan <hash>`, the form the post hook suggests, before step 7. S-01 needs it.

## 8. Planted defects

Each entry in `defects.py` has these fields:

- `id`
- `layer`
- `mutation`, a function applied to a fresh baseline at a named point in the chain
- `caught_by`: `data-contract-check`, `approval gate`, `verify`, `decision-status`, `new-analysis`, or `none`
- `expect`: exit code or status, level (`block`, `gap`, `warn`, `deny`), and a message substring
- `known_miss`
- `xfail_task`
- `covers`, a list of exact row names from `llm-failure-modes.md` or `analysis-decisions.md`

### 8.1 Data layer (data-contract-check, before approval)

| ID | Mutation | Expect | Covers |
| --- | --- | --- | --- |
| DC-01 | contract names `seq_batch` (from the lab's prose) instead of `run_id` in the schema and batch checks | exit 2; `required columns are absent`, observed `missing: seq_batch` | Invented columns or levels |
| DC-02 | table spells the arm `Vaccine` | exit 2; `required levels of 'arm' are absent after filtering` | Invented columns or levels; Reversed contrast (the part the check covers: both levels exist) |
| DC-03 | two rows of D09 deleted (an inner join upstream lost them) | exit 2; `row count differs from the plan`, expected 24, observed 22; plus a unit-of-replication block, `groups with fewer distinct donor than required` (placebo=5). Pairing passes: the donor is gone entirely, so no remaining donor lacks a visit | Silent row loss |
| DC-04 | `D03_day28_rerun` flipped to `preferred_acquisition=TRUE` | exit 2; `a unit appears more than once in the same arm x visit cell` | Join duplication; Unit of replication |
| DC-05 | D11's day28 row deleted and the contract's `rows` set to 23, so only pairing fails | exit 2; `units are missing a level of 'visit'`, evidence `D11 lacks day28` | Unit of replication |
| DC-06 | `run_id` reassigned: vaccine in R1, placebo in R2 and R3 | exit 2; `'arm' is fully nested in 'run_id'` | Batch versus biology |
| DC-07 | one row's `run_id` set to `NA` | exit 2; `'run_id' has missing values` from `no_missing`, and the batch check warns `rows have a missing value` | Cohort and exclusions |
| DC-08 | `02_paired_test.py` computes placebo minus vaccine | known miss: contract passes, verify `CONFORMS`, log2FC signs flipped | Reversed contrast |
| DC-09 | `02_paired_test.py` joins counts to metadata by column position | known miss: contract passes, verify `CONFORMS`; hits differ from `truth.json` | Sample label swap |
| DC-10 | `MARCHF1` and `SEPTIN7` in `counts.tsv` become `1-Mar` and `7-Sep` | known miss: everything passes; harden's learning (E4) is the guard | Gene symbol corruption |
| DC-11 | `02_paired_test.py` uses total-count CPM | known miss: verify `CONFORMS`; the hit list contains the CPM false positives that `make_fixture_data.py` records for the chosen seed (at least 3) | Normalization and transformation |

DC-08 to DC-11 are the reason the fixture exists. Every tool reports success, yet the results are wrong. A design that only counted caught defects would hide them.

### 8.2 Gate layer

| ID | Mutation | Expect | Covers |
| --- | --- | --- | --- |
| G-01 | after the baseline approval, run `scripts/04_extra_plot.py` | deny; `blocked because no active approved plan covers this run` | Silent scope growth |
| G-02 | append a row to `sample_metadata.tsv` after approval, then run 01 | deny; `blocked because inputs pinned by plan <hash> changed` | Input and matrix state |
| G-03 | `MYCELIUM_EXTRA_EXPLORE=1 python3 analysis/vaccine-response/scripts/04_extra_plot.py` with no `allow explore` | deny; `the exploratory-run prefix works only after the user` | Explore results reported |
| G-04 | `echo '{}' > .mycelium-extra/approvals/x.json` | deny; `appears to modify .mycelium-extra/` | tool: gate state |
| G-05 | plan text without its `Plan status:` line | Stop hook offers no `approve plan` | tool: approval |
| G-06 | plan table without `sbatch`, then `sbatch analysis/vaccine-response/run.sh` | deny; `no active approved plan covers this run` | Silent scope growth |
| G-07 | the test backdates the approval file's `approved_at` by 25 h | deny on the next run of 01 | tool: approval expiry |

### 8.3 Verify layer (after the baseline approval)

| ID | Mutation | Expect | Covers |
| --- | --- | --- | --- |
| V-01 | 02 exits 1 before writing | block `failed (exit 1)`; gap `Output ... de_results.tsv does not exist` | Swallowed errors (the visible case) |
| V-02a | `python3 .../02_paired_test.py \|\| true`, 02 fails before writing; 03 is not run | the receipt records exit 0, so the row reads `ran (exit 0 from hook event)`; gap `Output ... de_results.tsv does not exist`; `CONFORMS_WITH_GAPS` | Swallowed errors |
| V-02b | as V-02a, but 02 writes a partial `de_results.tsv`, then raises | known miss: `CONFORMS` | Swallowed errors |
| V-03 | edit 02 after its run | block `was edited after its run` | Stale evidence as current |
| V-04 | leave `summary.tsv` from an earlier session (mtime before approval) and skip 03 | block `before the plan was approved`; gap `no run under this plan was recorded` | Stale evidence as current |
| V-05 | write `outputs/top_genes.tsv` with an inline `python3 -c` (not gated) and add it to the plan's `Outputs:` | gap `is not tied to any recorded run` | Number transcription (where a value came from) |
| V-06 | change `counts.tsv` after the runs | block `Input ... changed since the approval` | Input and matrix state |
| V-07 | skip 03 entirely | gap `no run under this plan was recorded` | tool: verify |
| V-08 | `allow explore`, then an explore run of 04 | gap `Explore run in the analysis folder` | Explore results reported |
| V-09 | explore run rewrites `de_results.tsv` after the planned run | gap `was likely written by` an explore run; since D1, block: Key Findings claims read from that file are explore-only | Explore results reported |
| V-10 | lineage lists `/tmp/scratch/refit.py`, which the gate never saw | gap `Mycelium's lineage saw` | Retry until significant |
| V-11 | `02b_paired_test.py` added to the plan but left uncommitted | gap `was untracked when it ran` | tool: verify |
| V-12 | plan names `sbatch analysis/vaccine-response/run_all.sbatch`; fake sacct returns `FAILED` | block `Slurm job 4242 ended FAILED` | tool: verify |
| V-13 | Snakefile run as the wrapper, with the three steps still in the plan table; one rule's record `incomplete: true` | block `Snakemake marks rule` | tool: verify |
| V-14 | fake scilintr reports one finding in 02 | block `scilintr finding(s) remain` | tool: verify |
| V-15 | scilintr path does not exist | gap `scilintr (Python) not checked` | tool: verify |
| V-16 | plan without its `Outputs:` line | gap `has no \`Outputs:\` line` | Outputs and reporting |
| V-17 | runs use `conda run -n vaccine-de python3 ...`; no such env under `HOME` | gap `Conda env \`vaccine-de\`` ... `was not found` | Version-specific behaviour |
| V-18 | a second approved plan covers 04, and it runs | gap `ran since the approval but is not in the plan table`; info `Run under another plan` | Silent scope growth |
| V-19 | row 3's source becomes `default: standard` | `CONFORMS`; info `Default without a usable reason (advisory)` (D9) | Unstated defaults |
| V-20 | 02 finishes within `TOLERANCE` of 01's receipt (`de_results.tsv` mtime = 01's receipt + 1 s) | known miss: `CONFORMS`, and the output is credited to run 01, an earlier run of the same plan | Stale evidence as current |
| V-21 | D1: the hit count retyped as 9 in Key Findings and its claims block | block `claims 9, but ... n_hits holds 8` | Number transcription |
| V-22 | D1: a claims line citing `outputs/missing.tsv` | gap `cites ... missing.tsv, but it does not exist` | tool: verify |
| V-23 | D1: DC-08's flipped contrast with Key Findings unchanged | block `claims 1.4455, but ... log2fc row MX1 holds -1.4455` | Log base and sign confusion |
| V-24 | D4: plan with α = 0.1, explore runs of 01, 02, 02, plan with α = 0.01, then the baseline plan runs | `verify multiplicity`: `2 earlier plan revision(s), 3 explore run(s) before the approval`, `2 of 2 plan change(s) edited a Choice cell`, each Choice change listed | Retry until significant |
| V-25 | E1: `vaccine-de` exists under `HOME` with one conda record and a pip-only `statsmodels` dist-info, and the runs use `conda run -n vaccine-de` | `CONFORMS`; info `1 packages recorded; 1 pip package.` | Version-specific behaviour |
| V-26 | M8-T03 B1: step 1 of the baseline plan names its script by absolute path, steps 2 and 3 by root-relative path | `CONFORMS`; `report` and `status` do not crash; the script is listed root-relative | `tool: verify` |
| V-27 | M8-T03 B4: the baseline plan runs, then `02_paired_test.py` is edited | `DOES_NOT_CONFORM`; "edited after its run" plus "has not run under any plan, so no approval covers it" | Stale evidence as current |
| V-28 | M8-T03 B3: a fourth row reads an existing `logs/02_paired_test.log`, rewritten after the runs | `CONFORMS`; the log is not listed as a planned script | `tool: verify` |

V-13 keeps the steps in the plan table because verify reads a rule's `incomplete` flag only for a planned step that ran inside a wrapper. A plan that names only the Snakefile gets a direct receipt for it, and an incomplete rule is not reported; that is not a case yet.

### 8.4 Sweeps and memory

| ID | Mutation | Expect | Covers |
| --- | --- | --- | --- |
| S-01 | after `verify write`, edit 02 | `verify stale` lists the plan with one `script ... edited since it ran` line and a `findings:` command whose pattern matches F-001's ledger row | Stale evidence as current |
| S-02 | remove the analysis from `ANALYSIS_MANIFEST.md` | `verify status` shows `not listed` | Outputs and reporting |
| S-03 | delete `summary.tsv` after `verify write` | `verify stale` lists the output as deleted | Stale evidence as current |
| M-01 | decision-status `--term normalisation` | three entries, raw statuses; output never names one as current | Redoing settled work |

### 8.5 Known bugs, now fixed

Each was confirmed against `3a11123`, by a gate probe or by reading the code. E2 and E3 fixed all six before C1 step 5, so they are plain asserts, not `expectedFailure`: an unexpected success would report the suite as FAILED. KB-03 passes on Python 3.6 as well (E2 scans unparseable Python by its string tokens), so it runs on every version. KB-04 sends a post event with no `hook_event_name`, the only shape that still yields an unknown exit status; KB-05 reads the receipt's `paths`; KB-06 is a report rule that lists `03_summary.R` as an input but runs only R Markdown.

| ID | Correct behaviour asserted | Today | Task |
| --- | --- | --- | --- |
| KB-01 | gate silent for `python3 -c "import os; open('notes.txt','w').write(os.path.join('x', '.mycelium-extra'))"` | denied (probe) | E2 |
| KB-02 | gate silent for ``sed -i 's/gate state/the `.mycelium-extra` folder/' notes.md`` | denied (probe); the same text with `echo ... > notes.md` passes | E2 |
| KB-03 | gate silent for a Python heredoc using `:=` that only writes `notes.txt` | passes on 3.8+, falls back to the any-mention rule on 3.6; the case runs only when `sys.version_info < (3, 8)` | E2 |
| KB-04 | verify reports a gap when a receipt has no exit status | row reads `ran (exit status not recorded)` and no finding is added (`verify.py:660`), so the status can be `CONFORMS`. Claude Code's real `PostToolUse` for Bash has no exit code, so every baseline run hits this; the baseline accepts either `ran` form until E3 | E3 |
| KB-05 | `sbatch --chdir=analysis/vaccine-response --wrap 'python3 scripts/01_select_samples.py'` receipts the right script path | path resolved against the hook's cwd | E3 |
| KB-06 | a Snakemake rule input is not counted as a run of that file | counted | E3 |

### 8.6 Fixtures for later tasks (cases skip until the task ships)

| Task | Fixture content added now | Case when the task ships |
| --- | --- | --- |
| D1 | Key Findings in `VACCINE_RESPONSE.md` with a claims block; `expected/claims.json` | shipped in 0.9.34: V-21 (hit count 9, block), V-22 (missing file, gap), V-23 (DC-08's sign flip against the baseline's own values, block; the planned "+2.0" claim already differed from 1.6806, so it would not test the flip), and V-09 (explore-only, block). The known-miss chains (`whole_chain`) drop the block, since an agent would write findings from the mutated outputs |
| D2 | three references in `VACCINE_RESPONSE.md`: BH 1995 (DOI 10.1111/j.2517-6161.1995.tb02031.x), one DOI that does not resolve, one real DOI with the wrong title | recorded responses under `tests/e2e/recorded/`; no live network |
| D4 | none beyond the harness | shipped in 0.9.36: V-24 (3 explore runs and 2 plan revisions changing α before the approved run; counts and the timeline) |
| C3 | none committed | packet built from the baseline plan, plus a participant-style identifier and a token assembled at run time by string concatenation, so no secret-shaped string is ever committed (push protection would block it) |
| D6 | none committed | `.h5ad` generated at test time from `sample_metadata.tsv` when `h5py` is present |
| E1 | none committed | shipped in 0.9.37: V-25 (a synthetic env under `HOME` with `conda-meta/*.json` and one pip-only `site-packages/*.dist-info`) |
| E1b | none committed | a `.snakemake/conda/<hash>.yaml` |
| E4 | `learnings.md` candidate; `nbs/qc_explore.ipynb`; `nbs/r_explore.ipynb`; `reports/report.Rmd` | hints on/off, harden on DC-10, verify `explore`, R chunk lint |
| E5 | `report.Rmd` | four variants: document-level `eval: false`, `child=`, `knitr::read_chunk`, `{r engine=...}` |
| D10 to D12 | none | approval latency recorded per approval; checkpoint question generated from the plan table; seeded audit revealed in the same report |

## 9. Catalog contract tests

These run with the suite and need no project:

1. Every `covers` entry is an exact row name in `llm-failure-modes.md` or `analysis-decisions.md`, or starts with `tool:`.
2. Every failure-mode row whose Check cell names a tool, either fully or as `partial:`, has at least one defect with `known_miss=False` and `caught_by` equal to that tool. This would have caught four rows that the first draft of the checklist credited to `data-contract-check`; section 11 lists them.
3. Every defect with `known_miss=True` covers at least one row whose Check cell is `none`, `partial:`, `planned:`, or `cross-ref:`, or an `analysis-decisions.md` row (that file has no Check column, so its rows claim no tool). A known miss of a mode the checklist says a tool fully catches is a contradiction.
4. Every `xfail_task` and every task in 8.6 is a heading in `docs/roadmap/`.
5. IDs are unique, each layer prefix (`DC`, `G`, `V`, `S`, `M`, `KB`) matches its `caught_by` family, and `known_miss` is set exactly when `caught_by` is `none`.

## 10. Guard ablations (`tests/e2e/ablate.py`)

`ablate.py` feeds verify or the gate a patched copy of its source. Each patch disables one `report.add` call or the `deny` branch. It first runs the defect case against the real source (it must pass), then against the patched copy (it must fail). Verify is already run as source on stdin, and the gate is copied with its `hooks/` folder, so the patch never touches the repository; the harness's `VERIFY` and `GATE_RUN` name the copies. A guard text that is not found exactly once stops the run, so a wording change cannot turn an ablation into a no-op. The three required ablations are:

| Ablation | Line removed | Case that must fail |
| --- | --- | --- |
| A-1 | verify: the `was edited after its run` block | V-03 |
| A-2 | verify: the `Input ... changed since the approval` block | V-06 |
| A-3 | gate: the pinned-input deny in `on_tool` | G-02 |

A2 (CI) can run `ablate.py` weekly rather than on every pull request.

## 11. Changes this design made elsewhere

- **Failure-mode checklist corrected.** Writing section 9 test 2 showed four overclaims:
  - "Reversed contrast", "Silent row loss" and "Join duplication" were credited to `data-contract-check` in full. They are now `partial:`, with what the check covers in brackets.
  - "Sample label swap" was also credited to `data-contract-check`, which cannot see a matrix's column order. It is now `none`.

  It also showed four undercounts, now marked `partial:`:
  - "Stale evidence as current" (verify);
  - "Silent scope growth" (approval gate);
  - "Swallowed errors" (verify, through a named output that is missing);
  - "Explore results reported" (verify).

  The legend now defines `partial:`, and a new grill test (`test_check_cells_use_the_legend`) holds the Check column to that vocabulary.
- **D6 rewritten.** `batch_confounding` already blocks full nesting and isolated levels. D6 is now an optional graded-imbalance warning (`max_share`) plus `.h5ad` input.
- **E3 confirmed.** A missing exit status produces no verify finding today (KB-04).

## 12. Build order

Each item is one commit, with the suite passing after each:

1. The generator, the data, the project text files, and `tests/fixtures/README.md`, plus `make_fixture_data.py --check` as a test. Effort: M.
2. `harness.py` and `test_baseline_chain` (section 7). Effort: M.
3. Data and gate layers (8.1, 8.2) and catalog tests 1, 3 and 5. Effort: S.
4. Verify layer and sweeps (8.3, 8.4), plus catalog tests 2 and 4. Effort: M.
5. Known bugs (8.5) and `ablate.py`. Effort: S.
6. The 8.6 fixtures are added by their own tasks, not by C1.

## 13. Open questions for the maintainer

- **Where tests live.** Is `tests/` at the repository root acceptable, or should the end-to-end suite live under `hooks/tests/`, next to the gate tests? The root keeps it separate from per-skill tests.
- **Real data or simulated.** Simulated data gives known ground truth, which DC-08 to DC-11 and D1 need. A small public dataset would look more real but has no truth. The recommendation is simulated, with real gene symbols and a clear SIMULATED banner.
- **R in CI.** A2 can add an R job so 03 runs for real. Otherwise R stays simulated from `expected/summary.tsv`, and a run with R present checks that the real output matches it.
