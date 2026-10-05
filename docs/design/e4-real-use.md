# E4: features exercised on the fixture project

Record for roadmap task [E4](../roadmap/04-handoff-backlog.md#e4-test-features-not-yet-used-in-real-work), plan c15bb851 (approved 2026-10-05). Each feature below is run once on the C1 fixture (`tests/fixtures/mycelium-project/`), with real tools where this machine has them.

The **Expected** lines were written and committed before any run, from the docs that promise the behaviour. **Predicted from code** is what reading the code at `5411dee` suggests, also written before the run; where it differs from Expected, a mismatch is likely. **Observed** and **Verdict** are filled in after the run. Nothing is fixed in E4: each mismatch becomes its own roadmap task.

Verdict scale, against the package goal ("planning analysis work before it runs", complementing Mycelium and never overriding it; `README.md`, `docs/roadmap/README.md` guiding principles): **serves** the goal, **drifts** from it, or **unclear**.

Real tools on this machine: R 4.5.3 with scilintr 0.1.1 in the `cellbouncer` conda env; h5py 3.10 and anndata 0.8.0 in the `scanpy` env (Python 3.8). No Python scilintr is installed, so the Python lint path stays faked.

## 1. hints

- **Expected** (`docs/approval-gate.md` "Command hints"; roadmap principle "friction is opt-in"): off until the user types `hints on`. Then a request that fits a skill gets one line naming it, the Stop hook suggests `/mycelium-extra:verify <hash>` once per plan per session after a gated run, and `hints off` stops both. Hints never invoke a skill.
- **Predicted from code** (`hooks/gate.py` `on_prompt`, `prompt_hint`, `stop_hints`): `hints on` writes `.mycelium-extra/hints.json` and prints "command hints on for this repository". Prompts starting with `/` or containing "mycelium" get no hint. "analysis", "differential", "re-run" and similar get `/mycelium-extra:grill` only while no approval is active. "review", "report", "ingest" and "ideas" route to Mycelium's skills only when `.living/` exists. The verify hint is shown once per plan per session (`pending/<session>.hints.json`). No differences from Expected.
- **Observed:** pending.
- **Verdict:** pending.

## 2. harden on DC-10

- **Expected** (`skills/harden/SKILL.md`): in the fixture, harden finds the learning "Spreadsheet round-trip renamed MARCHF1 to 1-Mar" and skips the vague one. It writes a test outside the gated paths that fails on a reproduction (`1-Mar` in the `gene` column) and passes on the baseline counts. After confirmation, it changes only that entry's `mitigation_type` and candidate line. DC-10 then has a guard.
- **Predicted from code:** harden has no script; the model follows `SKILL.md`. Exercised by hand on a scratch copy of the fixture, not in e2e (C1 excludes model behaviour). The test it writes should catch DC-10 as soon as it runs. Nothing in verify or the gate runs it, so DC-10 stays a known miss for the chain unless someone runs the test.
- **Observed:** pending.
- **Verdict:** pending.

## 3. verify explore

- **Expected** (`skills/grill/SKILL.md` "Promote explore runs"; `docs/skills.md`): after `allow explore` and a gated run with the `MYCELIUM_EXTRA_EXPLORE=1` prefix, `verify explore` lists one entry per distinct command, without the prefix. Each entry shows the paths it ran, its exit status, its conda env, and whether its script changed since. `--all` covers every session from the last 7 days. The Stop hook says the runs are not reportable.
- **Predicted from code** (`verify.py` `explore_runs`, `render_explore`): matches Expected. Editing the script after the run adds "script `<path>` edited since this run". A run with no recorded exit shows "exit not recorded" for `null`; for the newer `"unknown"` value it prints `exit unknown`.
- **Observed:** pending.
- **Verdict:** pending.

## 4. verify multiplicity

- **Expected** (`skills/verify/SKILL.md` "Multiplicity"; roadmap D4): for a plan approved after an earlier revision and some explore runs, a counts line ("N earlier plan revision(s), N explore run(s) before the approval, ...") followed by one chronological `When | What | Detail | Exit` table.
- **Predicted from code** (`verify.py` `multiplicity`, `render_multiplicity`): matches Expected. An earlier plan is a revision only when it shares a gated script or an `Outputs:` path.
- **Observed:** pending.
- **Verdict:** pending.

## 5. verify stale and status after an edit

- **Expected** (`docs/skills.md`; the baseline already covers the clean case, `tests/test_end_to_end.py` steps 8-9): after a verified plan's script is edited, `verify stale` names the plan and the edited script and ends "1 of 1 verified plans stale.". `verify status` shows the plan's row with `Stale` = "1 change(s)".
- **Predicted from code** (`stale_plan`, `status`): matches Expected.
- **Observed:** pending.
- **Verdict:** pending.

## 6. R scilintr, the real CLI

- **Expected** (roadmap constraint "remaining scilintr findings still block verify"; `docs/skills.md` Gaps): verify runs `Rscript -e 'scilintr::main()' <files>`. A finding in R code blocks verify. Clean R code gives "scilintr: N R file(s) clean." A crash or unreadable output is a gap.
- **Predicted from code:** likely mismatches, from reading scilintr 0.1.1's `main()`:
  - `main()` reads only `args[1]`, as a project root for `lint_project()`. verify passes one path per file, so only the first file would be linted.
  - `main()` returns `invisible(1L)` on findings but never calls `quit(status = 1)`. `Rscript -e` then exits 0. verify's rule (exit 1 with findings = block, exit 0 without = clean, anything else = gap) would turn a real R finding into a gap, not a block.
- **Observed:** pending.
- **Verdict:** pending.

## 7. R-kernel notebook

- **Expected** (`docs/skills.md`: verify lints the analysis's code, notebooks included): an R-kernel `.ipynb` the plan runs has its code cells linted as R, with findings cited as `<notebook>[code cell N]:<line>`.
- **Predicted from code** (`notebook_code`, `code_files`): cells are extracted as R when `kernelspec.language` or `language_info.name` is `r`, then sent through the R path in section 6, with the same likely mismatches. `code_files` walks only the analysis folder, so a notebook under `nbs/` that the plan runs is not linted. Only its run is checked. The fixture's new notebook sits under `nbs/` (gated `nbs/**`) to show this.
- **Observed:** pending.
- **Verdict:** pending.

## 8. `.Rmd` R chunks

- **Expected** (`docs/skills.md`): the R chunks of `analysis/vaccine-response/reports/report.Rmd` are linted as R. Findings keep the document's line numbers.
- **Predicted from code** (`chunk_code`): `{r}` chunks extracted with other lines blank, so line numbers match. E5's four cases (`eval: false`, `child=`, `read_chunk`, `engine=`) stay unhandled. The extracted code goes to a scratch `.R` file, so the R CLI issues in section 6 apply.
- **Observed:** pending.
- **Verdict:** pending.

## 9. h5ad in data-contract-check

- **Expected** (`skills/data-contract-check/SKILL.md`): with h5py installed, a contract against an `.h5ad` reads its `obs` and gives the same PASS/WARN/BLOCK lines as the same table in TSV, except that a unit check counts cells. Without h5py, every check is a GAP (exit 3), never a pass.
- **Predicted from code** (`read_h5ad_obs`): reads both the anndata ≥ 0.8 encoding (`encoding-type` groups) and 0.7's `__categories`. A file written by anndata 0.8.0 from `sample_metadata.tsv` should match the TSV result line for line, apart from the index column name (`_index`).
- **Observed:** pending.
- **Verdict:** pending.

## Mismatches and new tasks

Filled in after the runs.
