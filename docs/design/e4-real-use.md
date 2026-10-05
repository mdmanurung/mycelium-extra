# E4: features exercised on the fixture project

Record for roadmap task [E4](../roadmap/04-handoff-backlog.md#e4-test-features-not-yet-used-in-real-work), plan c15bb851 (approved 2026-10-05). Each feature below is run once on the C1 fixture (`tests/fixtures/mycelium-project/`), with real tools where this machine has them.

The **Expected** lines were written and committed before any run, from the docs that promise the behaviour. **Predicted from code** is what reading the code at `5411dee` suggests, also written before the run; where it differs from Expected, a mismatch is likely. **Observed** and **Verdict** are filled in after the run. Nothing is fixed in E4: each mismatch becomes its own roadmap task.

Verdict scale, against the package goal ("planning analysis work before it runs", complementing Mycelium and never overriding it; `README.md`, `docs/roadmap/README.md` guiding principles): **serves** the goal, **drifts** from it, or **unclear**.

Real tools on this machine: R 4.5.3 with scilintr 0.1.1 in the `cellbouncer` conda env; h5py 3.10 and anndata 0.8.0 in the `scanpy` env (Python 3.8). No Python scilintr is installed, so the Python lint path stays faked.

## 1. hints

- **Expected** (`docs/approval-gate.md` "Command hints"; roadmap principle "friction is opt-in"): off until the user types `hints on`. Then a request that fits a skill gets one line naming it, the Stop hook suggests `/mycelium-extra:verify <hash>` once per plan per session after a gated run, and `hints off` stops both. Hints never invoke a skill.
- **Predicted from code** (`hooks/gate.py` `on_prompt`, `prompt_hint`, `stop_hints`): `hints on` writes `.mycelium-extra/hints.json` and prints "command hints on for this repository". Prompts starting with `/` or containing "mycelium" get no hint. "analysis", "differential", "re-run" and similar get `/mycelium-extra:grill` only while no approval is active. "review", "report", "ingest" and "ideas" route to Mycelium's skills only when `.living/` exists. The verify hint is shown once per plan per session (`pending/<session>.hints.json`). No differences from Expected.
- **Observed:** as expected, every line (`RealUse.test_hints`). Off by default: no hint. After `hints on`, "re-run the differential analysis" gives "this fits /mycelium-extra:grill" and "review the code" gives "/mycelium:review". A prompt with "mycelium" or a leading `/` gets none, and neither does the grill hint while a plan is approved. After a gated run, the Stop hook gives "next, `/mycelium-extra:verify 84bb5fce`" once, then nothing. After `hints off`, nothing.
- **Verdict:** serves. Opt-in. It names the next planning or verify step and hands review, report, ingest and ideas to Mycelium's own skills, never replacing them.

## 2. harden on DC-10

- **Expected** (`skills/harden/SKILL.md`): in the fixture, harden finds the learning "Spreadsheet round-trip renamed MARCHF1 to 1-Mar" and skips the vague one. It writes a test outside the gated paths that fails on a reproduction (`1-Mar` in the `gene` column) and passes on the baseline counts. After confirmation, it changes only that entry's `mitigation_type` and candidate line. DC-10 then has a guard.
- **Predicted from code:** harden has no script; the model follows `SKILL.md`. Exercised by hand on a scratch copy of the fixture, not in e2e (C1 excludes model behaviour). The test it writes should catch DC-10 as soon as it runs. Nothing in verify or the gate runs it, so DC-10 stays a known miss for the chain unless someone runs the test.
- **Observed:** run by hand on a scratch copy, following `SKILL.md`. Step 1 finds the two candidates and skips "be careful with joins" as vague. The fixture has no test setup, so the test goes to `tests/test_gene_symbols_not_dates.py` (stdlib, outside `analysis/**` and `nbs/**`). It fails on a reproduction (`1-Mar`, exit 1), passes on the baseline counts (exit 0), and fails on DC-10 (`1-Mar, 7-Sep`, exit 1). The record step (editing the learning after the user confirms) was not run: it needs a user and a real `.living/`. One mismatch: the candidate reads "In `analysis/vaccine-response/scripts/02_paired_test.py`, assert ...", which places the check in analysis code. `SKILL.md` says never to edit analysis code, but not whether to skip such a candidate or move its assertion into a test. Here the assertion was moved; another run could skip it and ship nothing. Task E8.
- **Verdict:** serves. It turns a remembered gotcha into a check without touching analysis code. As predicted, DC-10 stays a known miss for the chain: nothing in the gate or verify runs the shipped test (locked: harden ships test files only).

## 3. verify explore

- **Expected** (`skills/grill/SKILL.md` "Promote explore runs"; `docs/skills.md`): after `allow explore` and a gated run with the `MYCELIUM_EXTRA_EXPLORE=1` prefix, `verify explore` lists one entry per distinct command, without the prefix. Each entry shows the paths it ran, its exit status, its conda env, and whether its script changed since. `--all` covers every session from the last 7 days. The Stop hook says the runs are not reportable.
- **Predicted from code** (`verify.py` `explore_runs`, `render_explore`): matches Expected. Editing the script after the run adds "script `<path>` edited since this run". A run with no recorded exit shows "exit not recorded" for `null`; for the newer `"unknown"` value it prints `exit unknown`.
- **Observed:** as expected (`RealUse.test_verify_explore`). Two explore runs of `01_select_samples.py` list once, without the prefix, as "(2 runs), exit 0". After the edit, "script ... edited since this run" appears. The Stop hook said "2 exploratory run(s) this session are not reportable". Two small mismatches (task E7). A run of a script that never existed (`missing.py`, exit 2) lists as "script ... deleted since this run". The Stop notice lists each run separately rather than once per command. Also: `verify explore` with no `--session` reads `$CLAUDE_CODE_SESSION_ID`, so inside the harness it picked up the host session. That is correct in real use and a harness detail, not a mismatch.
- **Verdict:** serves. It keeps exploration visible and not reportable, and turns it into the material for a grill plan.

## 4. verify multiplicity

- **Expected** (`skills/verify/SKILL.md` "Multiplicity"; roadmap D4): for a plan approved after an earlier revision and some explore runs, a counts line ("N earlier plan revision(s), N explore run(s) before the approval, ...") followed by one chronological `When | What | Detail | Exit` table.
- **Predicted from code** (`verify.py` `multiplicity`, `render_multiplicity`): matches Expected. An earlier plan is a revision only when it shares a gated script or an `Outputs:` path.
- **Observed:** already exercised end to end by V-24 (`tests/e2e/defects.py`, added with D4), which passes. Not duplicated here.
- **Verdict:** serves. It shows what was tried before the plan was settled, from records only.

## 5. verify stale and status after an edit

- **Expected** (`docs/skills.md`; the baseline already covers the clean case, `tests/test_end_to_end.py` steps 8-9): after a verified plan's script is edited, `verify stale` names the plan and the edited script and ends "1 of 1 verified plans stale.". `verify status` shows the plan's row with `Stale` = "1 change(s)".
- **Predicted from code** (`stale_plan`, `status`): matches Expected.
- **Observed:** as expected (`BaselineChain.test_stale_and_status_after_an_edit`). `stale` prints "## Plan 84bb5fce - `analysis/vaccine-response`", "script `.../02_paired_test.py` edited since it ran at ...", sessions, a findings `rg` line, and "1 of 1 verified plans stale.". In `status`, the Stale column reads "1 change(s)".
- **Verdict:** serves.

## 6. R scilintr, the real CLI

- **Expected** (roadmap constraint "remaining scilintr findings still block verify"; `docs/skills.md` Gaps): verify runs `Rscript -e 'scilintr::main()' <files>`. A finding in R code blocks verify. Clean R code gives "scilintr: N R file(s) clean." A crash or unreadable output is a gap.
- **Predicted from code:** likely mismatches, from reading scilintr 0.1.1's `main()`:
  - `main()` reads only `args[1]`, as a project root for `lint_project()`. verify passes one path per file, so only the first file would be linted.
  - `main()` returns `invisible(1L)` on findings but never calls `quit(status = 1)`. `Rscript -e` then exits 0. verify's rule (exit 1 with findings = block, exit 0 without = clean, anything else = gap) would turn a real R finding into a gap, not a block.
- **Observed:** worse than predicted: a false clean, not a gap. A direct probe of `Rscript -e 'scilintr::main()'`:
  - On one file with two findings: "scilintr: no findings", exit 0.
  - On a clean file followed by that file: the same.
  - On a folder: both findings, printed as `path:1 [R030/warning] ...`, still exit 0.
  verify passes files, so it gets "no findings" with exit 0 and reports "3 R file(s) clean". Under `MX_E2E_REAL_TOOLS=1`, an R016 line planted in `03_summary.R`, a `report.Rmd` chunk, and an R notebook gave "Verify status: CONFORMS". The folder format would not parse either (`LINT_LINE` needs a column). Task E6. Held by `RealUse.test_r_findings_block_with_scilintr_0_1_1` (a fake with 0.1.1's behaviour, runs everywhere) and `test_r_findings_block_with_real_scilintr` (real tools only), both `expectedFailure`. Separately, with real R on PATH the baseline chain runs `03_summary.R` for real and its output matches `expected/baseline.json`.
- **Verdict:** serves the goal by design, but it does not work with scilintr 0.1.1. It breaks the principle "a gap is never clean" for all R code.

## 7. R-kernel notebook

- **Expected** (`docs/skills.md`: verify lints the analysis's code, notebooks included): an R-kernel `.ipynb` the plan runs has its code cells linted as R, with findings cited as `<notebook>[code cell N]:<line>`.
- **Predicted from code** (`notebook_code`, `code_files`): cells are extracted as R when `kernelspec.language` or `language_info.name` is `r`, then sent through the R path in section 6, with the same likely mismatches. `code_files` walks only the analysis folder, so a notebook under `nbs/` that the plan runs is not linted. Only its run is checked. The fixture's new notebook sits under `nbs/` (gated `nbs/**`) to show this.
- **Observed:** verify's side works (`RealUse.test_r_code_reaches_r_lint`, with a fake R linter that flags R016 in what it is given). A copy of `nbs/r_explore.ipynb` inside the analysis folder has its cells extracted as R, and its finding is cited as `` `analysis/vaccine-response/notebooks/r_explore.ipynb[code cell 1]:3` [R016] ``. With real scilintr the finding is lost (section 6, E6). Not exercised: a plan that runs `nbs/r_explore.ipynb` itself. That needs Jupyter with an R kernel, and only `rnotebook` (R 4.1, no scilintr) has IRkernel. The prediction that such a notebook is not linted stays unverified (parked below).
- **Verdict:** serves. It works up to the R CLI.

## 8. `.Rmd` R chunks

- **Expected** (`docs/skills.md`): the R chunks of `analysis/vaccine-response/reports/report.Rmd` are linted as R. Findings keep the document's line numbers.
- **Predicted from code** (`chunk_code`): `{r}` chunks extracted with other lines blank, so line numbers match. E5's four cases (`eval: false`, `child=`, `read_chunk`, `engine=`) stay unhandled. The extracted code goes to a scratch `.R` file, so the R CLI issues in section 6 apply.
- **Observed:** as expected on verify's side (same case). The planted chunk line is cited as `` `analysis/vaccine-response/reports/report.Rmd:9` [R016] ``, the document's own line number. With real scilintr it is lost (E6).
- **Verdict:** serves. It works up to the R CLI.

## 9. h5ad in data-contract-check

- **Expected** (`skills/data-contract-check/SKILL.md`): with h5py installed, a contract against an `.h5ad` reads its `obs` and gives the same PASS/WARN/BLOCK lines as the same table in TSV, except that a unit check counts cells. Without h5py, every check is a GAP (exit 3), never a pass.
- **Predicted from code** (`read_h5ad_obs`): reads both the anndata ≥ 0.8 encoding (`encoding-type` groups) and 0.7's `__categories`. A file written by anndata 0.8.0 from `sample_metadata.tsv` should match the TSV result line for line, apart from the index column name (`_index`).
- **Observed:** as expected. The baseline contract was run on `sample_metadata.tsv` and on `.h5ad` files built from it (all columns categorical, `rin` float, X a 25 x 1 zero matrix). The outputs were identical line for line for both anndata 0.8.0 (scanpy env) and anndata 0.7.8 (scAR env, `__categories` encoding): 5 PASS, exit 0. Under system Python 3.6 without h5py: 5 GAP, "h5py cannot be imported ...", exit 3.
- **Verdict:** serves. It brings the sample-table check to single-cell projects without loosening it.

## Deviations from the plan

- Step 5: the real Rscript is passed as `MX_E2E_RSCRIPT`, not by putting the `cellbouncer` env's `bin/` first on PATH. That folder holds its own `python3`, which would replace the bare `python3` the hooks call. The baseline chain's real-R run used a folder holding only an `Rscript` link.
- Step 6: the h5ad check was run directly from stdin under each env's Python, not through `tests/test_end_to_end.py`. The harness runs skills with bare `python3` (3.6, no h5py), so an e2e case would only ever see the gap. The unit tests in `test_data_contract_check.py` cover the h5ad reader where h5py exists.

## Mismatches and new tasks

| Feature | Mismatch | Task |
|---|---|---|
| R scilintr (6), and through it R notebooks (7) and `.Rmd` chunks (8) | R code with findings is reported clean | [E6](../roadmap/04-handoff-backlog.md#e6-r-lint-reports-clean-code-it-never-linted) |
| verify explore (3) | "deleted since this run" for a script that never existed; Stop notice not merged per command | [E7](../roadmap/04-handoff-backlog.md#e7-explore-listing-wording) |
| harden (2) | `SKILL.md` does not say what to do with a candidate placed in analysis code | [E8](../roadmap/04-handoff-backlog.md#e8-harden-candidates-placed-in-analysis-code) |

Parked: a plan that runs a notebook under `nbs/` (outside the analysis folder). Return when an R kernel and scilintr share an env, or when E6 is fixed.

No feature drifted from the package goal. All nine plan, check, or record work before or around a run, and each hands Mycelium's work back to Mycelium's skills.
