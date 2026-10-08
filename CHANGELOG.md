# Changelog

All notable changes to mycelium-extra are listed here, newest first. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are the `version` in the three plugin manifests. Entries from 0.9.16 to 0.9.29 were rebuilt from `git log`.

## [0.9.60] - 2026-10-08

### Fixed

- A brace group with no comma on an `Outputs:` line (Snakemake's `results/{sample}.tsv`) was read as the literal path `results/sample.tsv`, which looked real on the approval card and would be a false "does not exist" gap in `verify`. It is now read as `*`, like `<sample>`. None of the 97 approved plans in `scale` and `bmv_pilot_cytof_integration` has the form. A Snakemake regex wildcard (`{sample,[A-Z]+}`) has a comma and is still split. `gate_diff` 163/163 identical.

## [0.9.59] - 2026-10-08

### Fixed

- `Outputs:` shorthand was read literally: `flashier_{hsc,gdt}_{fit,summary}.rds` became the fragments `flashier_` and `.rds`, and `…_meta.csv` became `_meta.csv`, each a false "does not exist" gap in `verify` and a fragment on the approval card's Writes line. The gate and `verify` now share one reader (`gate.read_outputs`): `{a,b}` lists are expanded (at most 200 paths a word), a `<name>` placeholder is read as `*`, globs stay whole on the card, and a word starting with `…` or `...` is set aside. The card adds "Shorthand, not read: …; name the full path", and `verify` gives one gap per such word. Grill now asks for full paths or `{a,b}` lists. Checked on 97 approved plans from `scale` and `bmv_pilot_cytof_integration`: 6 `verify` reports change, no status changes; the fragment gaps are gone, and in 3 plans the real files are now found and attributed. Folderless names in prose (`_dream_priors.csv` in 93f5d9f2) are still gaps. The card's Writes line changes on 14 plans, 8 of them only because globs are no longer split. `gate_diff` 163/163 identical. (B2)

## [0.9.58] - 2026-10-08

### Fixed

- `verify` counted every existing file the plan table names as a planned script. A log a step only reads (`logs/fit.log`) was then matched in the Snakemake rule that writes it and blocked as "edited after its Snakemake run"; a README or a Slurm `.out`/`.err` gave a "no run under this plan" gap. A planned script is now a path with a script extension, a `Snakefile` name, or a `#!` first line, so `.sbatch` jobs and `Snakefile.*` stay scripts; another named file is neither a script nor a folder. Checked on 95 approved plans from `scale` and `bmv_pilot_cytof_integration`: 8 reports change, by removals only (13 script rows, 11 gaps, 1 block, in scale 781c90d4); no status changes; the 10 plans naming `.sbatch` or `Snakefile.*` files are byte-identical. (B3)

## [0.9.57] - 2026-10-08

### Changed

- Only a plan table's Step column grants a run. A path or command word in a Choice or Validation cell no longer approves it, so a script named as a check or a choice cannot slip through approval. A table with no Step column in its header (or no header) grants from every cell but Source, as before. The card's "In prose only, not authorised" line is now "Outside the Step column, not authorised" and also lists scripts named only in Choice or Validation cells. `verify` keeps reading every cell but Source (`plan_table(..., every_cell=True)`), so its reports on older plans do not change. Checked on 95 approved plans from `scale` and `bmv_pilot_cytof_integration`: all have a Step header; 5 (approved 2026-10-01 to 10-03, past the approval window) would lose a grant, each from a Choice cell; `verify report` on those 5 is byte-identical before and after. Grill now says to name every run in its Step cell.

## [0.9.56] - 2026-10-08

### Fixed

- The 150-word brief limit (0.9.54) could squeeze out lines the gate and `verify` read. Now the `Inputs:`, `Outputs:`, `Facts:` and `Plan status:` lines and the failure-mode guards do not count and are never cut, and Evidence bullets that name a failure, a flag or an unverified fact are always kept (the card quotes them). Evidence reads "one bullet per fact you keep".

## [0.9.55] - 2026-10-08

### Changed

- The approval card adapts to its length. Past 35 lines it shows a digest: each step on one line (step, first sentence of the choice, who decided), the check only where a default decided, Reads and Writes as counts, and no diff. Baseline, changed-script warning, flagged Evidence and the full grant list stay. `card <hash> checks`, `card <hash> diff` and `card <hash> full` show the rest; the hook blocks that prompt and answers it, so the agent never sees it. Step cells no longer show an interpreter's absolute path (`/…/envs/R4_51/bin/Rscript` reads `Rscript`), and paths inside the project read root-relative. Checked on 86 approved plans from `scale` and `bmv_pilot_cytof_integration`: 54 became digests, the median card fell from 40 to 31 lines and the longest from 83 to 43 (its 12 grants stay in full), the grant list is identical to the full card's on every digest, and no card under the limit changed length. Nothing authorised changes.

## [0.9.54] - 2026-10-08

### Changed

- `grill` writes a brief of at most 150 words (was 200–500), plus the plan table and the quoted question, which do not count. One short line per section; Evidence keeps only the facts the plan's choices rest on, and the user asks for more if needed.

## [0.9.53] - 2026-10-08

### Changed

- `handoff` keeps a grill plan that is waiting for approval word for word. Before, it summarised the plan into `HANDOFF.md`'s 80 lines, so after `/clear` the table, choices, checks and labeled defaults were lost, and the old hash approved nothing in the new session. Now the skill finds the plan the gate stored at Stop (by content, so a parallel session cannot swap it), writes a `## Pending plan` pointer with the hash and a command that prints it, and the resume prompt has the new session print it unchanged. The gate then shows a fresh card on current pins in that session; the same text gives the same hash, and a different hash tells the user the reprint changed the plan. Without the gate, the whole brief goes into `HANDOFF.md` and does not count toward the line limit. Approval stays per session; the gate is unchanged. A gate test runs the skill's own two commands: the gate allows both, and the reprinted plan is approvable only in the session that showed it.

## [0.9.52] - 2026-10-06

### Added

- The approval card warns when Mycelium shares the repository (`.living/` exists, inside a git repository) but `.mycelium-extra/` is not git-ignored: Mycelium's stop check counts `git status`, so the gate's receipts would look like session changes. The line sits under the card's first line, on both the new and the old card, and says to add `.mycelium-extra/` to `.gitignore`. It never blocks. Nothing else changes: the 56 approved plans of `scale` and `bmv_pilot_cytof_integration` render byte-identically, since both repositories already ignore the folder. Found while checking that Extra and Mycelium's hooks do not interfere (both plugins' hooks run in parallel on one repository, and the gate allowed every `.living/` and `.mycelium/` write Mycelium's protocol asks for).

## [0.9.51] - 2026-10-06

### Changed

- On the approval card, the diff of changed scripts moves from the top to the bottom. The "Scripts changed since last approved" summary stays near the top; up to 30 diff lines (then "… and N more diff lines") now follow the Reads and Writes lines under "Diff of changed scripts", just above `approve plan`, so the question, goal, steps and grants come first. Nothing authorised changes, and the card for a plan without Step and Choice or Validation columns is byte-identical. Checked on 56 approved plans from `scale` and `bmv_pilot_cytof_integration`: the same lines on every card (plus the one heading), `approve plan` last, the `Question` line at line 10 (median) instead of 41, and a maximum of 81 lines instead of 80.

## [0.9.50] - 2026-10-06

### Changed

- `verify` names the script behind outputs it cannot tie to the approved plan's own runs, and reports them once per producing run and folder. Before, each file got its own "likely written by" line, and the line named only the first 80 characters of the command, so a long interpreter path hid the script. Now a run whose command is cut before its script reads "(script `path`)", and 2 or more such files in one folder give one gap: "N files in `folder` were likely written by <run>: `a`, `b`, `c` and N more" (outputs tied to no run group by folder the same way). One file keeps the old text. Status, `block` findings and the Outputs table are unchanged. Checked on 56 plans from `scale` and `bmv_pilot_cytof_integration`, old code against new on the same repos: outputs, status and every other finding identical (apart from the added script note); 9,883 per-file lines became 466 grouped lines covering 9,826 files plus 57 single files.

## [0.9.49] - 2026-10-06

### Changed

- The approval card opens with what is new since the newest earlier approval that covers or writes the same paths, of any age (not only the last 24 hours): each pinned script and input as `SAME`, `CHANGED` or `NEW`, taken from the earlier plan's pins or, for plans approved before script pins existed, from the receipts of its runs, plus whether the objective and each step row are unchanged. With no earlier plan it says "no baseline" and why instead of implying nothing changed. Re-showing a plan that was already approved compares it with that approval. Checked on 55 approved plans (each rendered with only the approvals before it): 40 found a baseline, 15 said "no baseline", none failed; median 39 lines, maximum 75 when several scripts changed.

## [0.9.48] - 2026-10-06

### Changed

- The approval card describes the plan instead of listing its files. For a plan whose table has a Step column and a Choice or Validation column it shows the question, the goal, the `default:` steps to confirm, each step with its choice, who decided it and its check, the Evidence lines that name a failure or a flag, and `CAN RUN (in full)`: every gated script, folder and command the table lets through, never collapsed or capped. Inputs and outputs become counts under a shared folder, a repeated path prefix is written once, steps the agent marks `(done)` read "agent says: done", and scripts the plan names only in prose are listed as not authorised. Text quoted from the plan has control characters, markup and the phrase "approve plan" removed. A plan without those columns keeps the old card. `grill` now asks for plain-language Choice and Validation cells. Checked on 55 approved plans from `scale` and `bmv_pilot_cytof_integration`: the card's grants equal the gate's own for every plan, with a median of 36 lines (maximum 49).

## [0.9.47] - 2026-10-06

### Changed

- When `verify` finds a script edited after its run, the finding now says whether an approval covers the script's current version: a plan pinned it, it ran under a plan approved after the file was last modified (by file time), it ran only under a plan approved before that, or it has not run under any plan. The status stays `DOES_NOT_CONFORM` in every case. On `scale` and `bmv_pilot_cytof_integration` none of the blocks was covered, so an edit made between a plan's approval and its run now reads as an unapproved change instead of looking superseded (M8-T03, defect `V-27`). A Snakemake-run script's finding is unchanged, since no fingerprint of it is recorded.

## [0.9.46] - 2026-10-06

### Fixed

- A plan table may name a script by its absolute path or its root-relative path; the gate and `verify` now treat an absolute path inside the project as the same script as its relative form. Before, `verify status` and `verify report` crashed with `Can't mix absolute and relative paths` when one plan used both forms, and a plan naming a script only by absolute path did not approve running it by relative path. A path outside the project still approves nothing. `grill` now asks for plan paths relative to the project root. Found by running `verify` on `bmv_pilot_cytof_integration` (M8-T03, defect `V-26`).

## [0.9.45] - 2026-10-06

### Changed

- The approval gate pins each approved script's content and blocks a gated run whose script changed since approval, so an agent cannot edit an approved script and re-run it without you. Scripts the plan table names are pinned when the plan is shown; any other covered script, such as one written later, is pinned at its first run. A notebook is pinned by its code cells, so running it does not count as a change. The approval card shows what changed as a diff of up to 30 lines. On by default; set `"pin_scripts": false` in `gate.json` to turn it off. Only the script a command runs is checked, not files it sources or imports.

## [0.9.44] - 2026-10-06

### Changed

- `grill` opens its first question with a one- or two-sentence reminder of what the task is, restating only what the invocation, the handoff, or you already said. It still drafts no goal, claim, or result for you to react to.

## [0.9.43] - 2026-10-06

### Added

- Codex approval hooks: plan registration, approval, pinned-input checks,
  exploratory grants, state protection for `apply_patch`, and run receipts.
  Receipts identify the Codex host. Missing exit metadata stays `unknown`;
  Codex 0.160.0 sends output without exit codes, so verification reports a gap.
- Sphinx documentation built from the existing Markdown, with search,
  Mermaid diagrams, installation and host compatibility instructions, and
  a GitHub Pages workflow that checks pull requests before deployment from main.

## [0.9.42] - 2026-10-05

### Fixed

- `verify`'s `.qmd`/`.Rmd` chunk lint handles four cases it missed (roadmap E5). An `engine=` chunk option now picks the language: `{r engine="bash"}` is skipped like `{bash}` instead of linted as R, and `engine="python"` is linted as Python. A file pulled in with `child=` (or Quarto's `#| child:`) or `knitr::read_chunk()` is found relative to the document and linted under its own path, also outside the analysis folder; a path that is not a quoted string, or that is not found, is a gap. A document set to `eval: false` is linted, as `eval=FALSE` chunks already were.

## [0.9.41] - 2026-10-05

### Changed

- `harden` says what to do with a candidate that places its check in analysis code (roadmap E8): it still qualifies when the check reads a file, is shown with "(check moves to a test)", and its assertion goes into a test that reads the same file, leaving the script untouched. A check on a value only the running script holds is skipped with the reason, since it belongs to a grill plan and a re-run.

## [0.9.40] - 2026-10-05

### Fixed

- `verify explore` says "script `<path>` not found when this ran" for an explore run of a script that did not exist, instead of "deleted since this run" (roadmap E7). The Stop hook's explore notice now names each command once, with a run count, as `verify explore` does; the leading count is still the number of runs.

## [0.9.39] - 2026-10-05

### Fixed

- `verify` no longer reports R code clean that scilintr never linted (roadmap E6). scilintr 0.1.1's `main()` reads only its first argument, as a project root, prints findings without a column, and always exits 0, so every R script, R notebook and `.Rmd` chunk verify passed it came back "clean". verify now copies the R code to one folder and runs `scilintr::lint_project()` on it through its own `Rscript -e` expression, which prints each finding in the format verify reads and exits 1 on findings. Cross-file R rules now run (scripts keep their repository paths in the copy, so `source()` between them resolves), and `.r` files are linted. Each R file is parsed first, and one that does not parse, or that verify cannot read, is a gap: lintr reports a parse error as a finding, but a nearby `ANALYSIS_OK` waiver drops it.

## [0.9.38] - 2026-10-05

### Changed

- `verify`'s skill description is about half as long (897 characters), so the skill listing no longer cuts it off, and it names the `multiplicity` and `explore` subcommands and the pip record.

## [0.9.37] - 2026-10-05

### Added

- `verify` records pip packages in a run's conda env (roadmap E1). It reads the env's `site-packages` for the Python packages conda did not install (not in any `conda-meta` record's files, or reinstalled since, so `INSTALLER` is no longer `conda`) and writes `provenance/pip-<hash>.txt`, one requirements block per env, noting a name also in `conda-meta` and a non-pip installer; a git install is written as `name @ git+<url>@<commit>`, and an editable or local-path install is commented out with its path, since `pip install -r` would look it up on an index. A `conda-lock.yml` still replaces the conda package list but no longer hides pip packages. A pip folder newer than the env's last run, or one without a readable name and version, is a gap. Fixture case V-25. The Snakemake per-rule envs are a new roadmap task, E1b.

### Changed

- With a `conda-lock.yml`, a run's conda env that verify cannot find is now a gap (its pip packages were not recorded); it was silent before.

## [0.9.36] - 2026-10-05

### Added

- `verify multiplicity <hash>` shows what was tried before a plan was settled (roadmap D4). A counts line, then one timeline, oldest first: each earlier approved plan that names one of the plan's scripts or outputs, with its changed Choice cells (so the tests, models and thresholds tried are named), each explore run and each run under an earlier plan or this one, with its command, exit status, and `other code version` when its script differs from the one this plan last ran. Counts come only from receipts and approvals; a run whose plan has no approval on file is counted as a gap, and the view judges nothing. Fixture case V-24: three explore runs and two α revisions before the approved plan.

## [0.9.35] - 2026-10-05

### Added

- `grill` asks for your question first (roadmap D8). Before reading anything, it asks in one free-text message, with no drafted options, for the question in your own words and the claim you hope to make (for a software task, the goal and the result you hope for). It skips what the request already states, the question does not count toward the five-question cap, and the brief opens with the answer quoted, or with `> Question: not stated (the user declined).`
- Provenance tags on facts (roadmap D7). Each Evidence bullet in grill's brief ends in `[human-stated]`, `[agent-derived: <path>]`, or `[agent-asserted: <source>]` (`none` without a source), followed by a `Facts:` count line. `verify` counts the tags in the frozen plan's Evidence and in the analysis doc's Key Findings and flags an untagged fact, an `agent-derived` one without its path, and an `agent-asserted` one without a source, all as info. After a planned run, the gate's notice asks for the tag at the end of a Mycelium finding's ledger Result cell, which Mycelium does not parse; the new-analysis Key Findings hint asks for it too. The fixture's Key Findings are tagged.

## [0.9.34] - 2026-10-05

### Added

- `verify` checks claims (roadmap D1). Each `<!-- claims -->` block in the analysis doc (`<NAME>.md`), in a Markdown output, or in a `--claims` document lists values with the output cell each came from (`8 | outputs/summary.tsv n_hits`). A value its cell contradicts after rounding blocks, and so does one read from an output an explore run wrote; a claim whose cell cannot be found is a gap. A table with more than one row needs a row label, so a common value such as 0.05 never verifies against some row of a column. Numbers near the block that it does not cover are listed as info. The report has a `## Claims` section, and the fixture's Key Findings carry a block (cases V-21 to V-23; V-09 now blocks).
- GitHub Actions CI (`.github/workflows/ci.yml`): every test file, the ablations, a manifest-version check and a link check, on Python 3.6 (`python:3.6-bullseye`, `LC_ALL=C`) and 3.14; pull requests also run `gate_diff.py` against their base commit. `tests/check_links.py` exits 2 when given no file and skips `@@...@@` template placeholders. Roadmap A2, pending its first run on GitHub.
- The C1 defect catalog (`tests/e2e/defects.py`): 49 planted defects across the data, gate, verify, sweep and memory layers, each run alone on a fresh copy of the fixture project, with catalog tests that tie every defect to a checklist row and fail if a tool the checklist credits catches none. Six are known misses, where every tool reports success and the results are wrong. `tests/e2e/ablate.py` disables three guards in patched copies and checks that their cases fail. Roadmap C1 is done.
- `hooks/tests/gate_diff.py` has 12 more scenarios: the three E2 commands that name the state folder only in text, each with a write twin that must still be denied, and a post event for each hook event shape (success, background start, interrupt, `Exit code N`, a bare failure, an abort). Roadmap E3 is done.

## [0.9.33] - 2026-10-05

### Fixed

- `verify` no longer counts a Snakemake rule's inputs as runs (roadmap E3b). A planned script that a rule only reads now shows `no receipt`, a gap. A rule is credited with the scripts in its expanded `shell:` command and with its `script:`/`notebook:` path, read from the record's `code`: the rule source in later 9.x releases (checked on records written by 9.27), or the string constants of the pickled code object before 9, read with `pickletools` and never unpickled. Early 9.x releases record only `shell:` commands, so a `script:` rule's script there shows `no receipt`.

## [0.9.32] - 2026-10-04

### Fixed

- Non-ASCII text no longer breaks anything on Python 3.6 with a non-UTF-8 locale (`LC_ALL=C`). Before this, the gate's Stop hook failed on any plan with an `α` or an em dash, so that plan could not be approved, and `verify write` crashed on it.
  - The gate reads each hook event as UTF-8, which is what Claude Code sends; before, 3.6 decoded it to lone surrogates.
  - Every text file the gate, `verify`, `init`, `data-contract-check`, and `new-analysis` read or write is `utf-8`. `verify` and `new-analysis` write with `surrogateescape`, so a non-ASCII analysis name or path is written as its original bytes; `new-analysis` no longer stops halfway through a scaffold.
  - `git`, `sacct`, and scilintr output is decoded as `utf-8`, with bad bytes replaced.
  - `verify`, `decision-status`, `data-contract-check`, and plan-review's `default_reasons.py` print non-ASCII to an ASCII stdout as `α` and so on, instead of crashing.

  On a UTF-8 locale nothing changes: `gate_diff.py` reports 148/148 identical under both `LC_ALL=C` and `en_US.UTF-8`. The end-to-end harness now sends events as raw UTF-8 and its plan has an `α`; a new `decision-status` test runs under an ASCII locale on any Python.
- `LICENSE` and `docs/roadmap/01-packaging.md` now spell the copyright holder "Mikhael Manurung", the name both plugin manifests already carry. `.claude-plugin/marketplace.json` names the owner `mdmanurung` and is unchanged.

## [0.9.31] - 2026-10-04

### Fixed

- `verify` and `new-analysis` no longer crash on a machine whose `python3` is 3.6 and whose locale is not UTF-8. `verify` wrote a middle dot in its report header, its `PROVENANCE.md` row, and its stale listing, which raised `UnicodeEncodeError` on an ASCII stdout; the separator is now `-`, and old `PROVENANCE.md` files still parse because the row is split on `|`. `new-analysis` read its templates with the locale's encoding and raised `UnicodeDecodeError` before writing anything; its reads and writes now name `utf-8`. `tests/test_end_to_end.py` passes as a result.

## [0.9.30] - 2026-10-04

### Added

- MIT `LICENSE`, named in both plugin manifests.
- `CHANGELOG.md`; a version bump now adds an entry here.
- Gate: the receipt hook also runs on `PostToolUseFailure`, so a failed command leaves a receipt with its exit code (`Exit code N`), `failed`, or `interrupted`; receipts gain `exit_source`, `error_line`, and `background`.
- `data-contract-check`: reads the `obs` of an `.h5ad` file through h5py (a gap without it); `batch_confounding` prints the batch-by-contrast table on every run and takes an optional `max_share` warning; exit 3 means a gap with nothing blocking.
- `plan-review` and `verify`: an advisory check that names each plan row whose `default:` has no reason, a reason under three words, or only an empty phrase such as `standard`.
- Tests: an end-to-end fixture project (`tests/fixtures/mycelium-project/`, simulated data and its generator) and a harness that replays the gate's hooks through a full grill-approve-run-verify chain.

### Changed

- `verify`: a run's exit 0 is taken from the hook event, so an ordinary run conforms; an `unknown` exit status is a gap; a run under Codex is stated to be unreceipted.
- The README is a landing page; skill, gate, Mycelium, and development details moved to `docs/`.
- The README summary table says that `plan-review` sends a packet to Codex and Biomni after you agree.

### Fixed

- Gate: a state-folder name that only reaches written text (`os.path.join(x, '.mycelium-extra')` passed to `.write()`, a `sed -i` script word) no longer denies the command; Python the running interpreter cannot parse is scanned token by token before the any-mention rule.
- Gate: `sbatch -D`/`--chdir` with `--wrap` resolves the payload's scripts against that folder, and the folder is no longer read as a gated path.
- Tests: the verify and gate tests hide the host's conda and virtualenv variables and `~/.conda`.

## [0.9.29] - 2026-10-04

### Added

- `grill`: an LLM failure-mode checklist (`skills/grill/references/llm-failure-modes.md`) with scenarios and a reference test.
- Docs: a Mermaid workflow diagram in the README, the improvement roadmap (`docs/roadmap/`), the C1 fixture-project design, and a committed `HANDOFF.md`.

## [0.9.28] - 2026-10-04

### Added

- `verify` lints the `{r}` and `{python}` chunks of `.qmd` and `.Rmd` files; findings cite the document's own line.

## [0.9.27] - 2026-10-04

### Fixed

- `verify` reports a `.py` script that does not parse as a lint gap, not clean.

## [0.9.26] - 2026-10-04

### Fixed

- Gate: code piped into a runner (`echo ... | python3`) is checked against the whole command again.

## [0.9.25] - 2026-10-04

### Fixed

- Gate: state-folder writes and inline runs are judged by what the code targets (per-segment heredocs, path strings in Python code, literal variables expanded, `-c`/`-e` gated only when it names gated code).

## [0.9.24] - 2026-10-03

### Added

- Promote explore runs: `verify explore` lists them and `grill` drafts a plan that re-runs them for approval.

## [0.9.23] - 2026-10-03

### Fixed

- Gate: the approve line has no Markdown bold, since notices are plain text.

## [0.9.22] - 2026-10-03

### Changed

- Gate: the approval notice is a card with the approve line and bulleted runs, pins, and outputs.

## [0.9.21] - 2026-10-03

### Fixed

- `verify` uses the session conda env only when a run declares no env.

## [0.9.20] - 2026-10-03

### Added

- `verify` records the packages of a run's conda env into provenance (`env-<hash>.txt`).

## [0.9.19] - 2026-10-03

### Fixed

- `new-analysis`: the notebook stub raises instead of asserting its input.

## [0.9.18] - 2026-10-03

### Added

- `verify` lints Jupyter notebook code cells.

### Fixed

- `verify status` shows an unchecked linter as a gap, not clean.

## [0.9.17] - 2026-10-03

### Added

- `verify status`: a table of plans, runs, verify status, staleness, lint, and manifest entry.

## [0.9.16] - 2026-10-03

### Added

- Ledger rows link to the approved plan; `verify stale` searches by plan hash.

### Changed

- A run plan's dry run goes under the first plan's approval; an ungated `snakemake -n` was reverted, since a Snakefile runs Python.

## 0.7.0 to 0.9.15 - 2026-09-30 to 2026-10-03

Summary: the skills, the approval gate, run receipts, pinned inputs, and `verify` were built up over these versions. There is no 0.9.13. See `git log` for details.

`verify` was first run on real receipts on 2026-10-02 (42 receipts, three plans, Rscript, sbatch, and Snakemake runs). The four bugs it showed were fixed the same day: a path only passed to other code counted as a run, Snakemake records beside planned scripts were missed, deleted scripts and code in output folders were misread, and the gate recorded a `command -v sbatch` lookup as a run.
