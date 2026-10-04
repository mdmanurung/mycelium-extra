# HANDOFF backlog

[Back to roadmap](README.md)

Open items carried in `HANDOFF.md`, turned into tasks. They are ordered by how often they are likely to bite in real use. When a task ships, remove its item from `HANDOFF.md` in the same commit.

### E1: Record pip packages in conda envs and Snakemake rule envs

- **Why:** the environment record reads the active conda env from `conda-meta`. Packages installed with `pip` inside that env do not appear there, and Snakemake runs with `--use-conda` build per-rule envs that are never recorded. In bioinformatics both are common, so a verified run can rest on package versions the provenance does not show.
- **Scope:** read pip-installed distributions from the env's `site-packages/*.dist-info` (and `*.egg-info`) metadata; for Snakemake, read each rule's `conda:` YAML path from the Snakefile or `.snakemake/conda/` and record the env file's hash and, if built, its `conda-meta` contents. Report an env that cannot be read as a gap.
- **Out of scope:** running `conda list --explicit`, `pip freeze`, or any other subprocess (a recorded dead end); container images.
- **Depends on:** none.
- **Constraints:** file reads only, stdlib only. Keep the existing `conda-meta` reader as the source for conda packages; add pip as a second, labelled source so a package present in both is visible as such.
- **Grill prompt:** `/mycelium-extra:grill Extend the environment record to include pip packages installed inside the conda env and the per-rule envs Snakemake builds with --use-conda, by reading files only. Find where conda-meta is read now and how verify reports an unreadable env, then plan the smallest extension.`
- **Acceptance:** on an env with one pip-only package, the record lists it with source `pip`; on a Snakemake fixture with a rule env, the env file hash appears; an unreadable env is a gap, not silence.
- **Tests:** unit tests with a synthetic env folder (conda-meta JSON plus dist-info) and a synthetic `.snakemake/conda/` tree.
- **Effort:** M. HANDOFF.md estimates the pip half at about 20 minutes; the Snakemake rule envs are the larger half and can ship as a second commit.
- **Status:** todo.

### E2: Gate false positives on state-folder mentions

- **Why:** the gate blocks commands that touch `.mycelium-extra/`. Three known cases block harmless commands: a bare folder literal inside `os.path.join(x, '.mycelium-extra')`; a backtick-quoted folder name inside a `sed -i` or `echo` argument; and a Python heredoc using 3.8+ syntax, which fails `ast.parse` on Python 3.6 and drops to the any-mention rule. Each false positive teaches the user to approve without reading.
- **Scope:** fix each case in the gate's parsing, and for the heredoc case try parsing with the running interpreter first and, on a syntax error, fall back to a token-level scan before the any-mention rule.
- **Out of scope:** loosening the rule for real writes into the state folder; supporting shells other than the Bash the gate already parses.
- **Depends on:** none.
- **Constraints:** run `hooks/tests/gate_diff.py` before and after; the only decision changes allowed are the three listed cases. Every new allow must have a matching test that a real write in the same shape is still denied.
- **Grill prompt:** `/mycelium-extra:grill Fix the three gate false positives listed in HANDOFF.md (os.path.join literal, backtick-quoted name in a sed or echo argument, 3.8+ heredoc on Python 3.6). For each, show the current decision path in gate.py, the change, and the paired test that a real write in the same shape still blocks. Run gate_diff.py before and after.`
- **Acceptance:** the three commands pass; their write-shaped twins still block; `gate_diff.py` shows exactly the three expected changes.
- **Tests:** six cases in `hooks/tests/test_gate.py` (three allows, three twins).
- **Effort:** M.
- **Status:** done. A literal that only reaches a `.write()` call's content through path-building calls (`os.path.join`, `os.getcwd`) is text; `sed -i`'s script word is not a file; Python a runner's interpreter cannot parse is scanned by its string tokens (comments ignored) before the any-mention rule, which still applies to R and perl. On Python 3.8+ the heredoc case already passed.

### E3: Close receipt gaps

- **Why:** four known cases produce wrong or missing receipts. `sbatch --chdir` with `--wrap` resolves paths against the hook's working directory, not the job's; a Snakemake rule input is counted as a run; a Bash `tool_response` carries no exit status and only `PostToolUse` (which fires on success) is registered, so a failed run leaves no receipt and a successful one has no recorded status; Codex runs produce no receipts at all. Verify then reports "conforms" or "gap" on a wrong record.
- **Scope:** resolve `--chdir` for `sbatch --wrap`; stop counting Snakemake rule inputs as runs (count the rule's `shell:`/`script:` target instead); take the exit status from the hook event (register `PostToolUseFailure` for Bash beside `PostToolUse`: `PostToolUse` fires only after success, so it records 0 with `exit_source: event`, except a `run_in_background` start; `PostToolUseFailure` records N from its `Exit code N` first line, else `failed`, or `interrupted`; an explicit exit code in the response wins; a payload with no event name, or a background start, is `unknown`), keep only the error's first line (at most 200 characters), and make verify report a failed or interrupted run as a failure and `unknown` (or an older null) as a gap; document that Codex runs are unreceipted (documentation only: the Codex manifest loads no hooks, so under Codex there are no approvals or receipts for verify to read, and no record of the host, so verify cannot tell a Codex-approved plan apart).
- **Out of scope:** building a Codex receipt path (needs Codex hook support; revisit when it exists); parsing Slurm job logs.
- **Depends on:** none (C1 makes the verify side testable end to end).
- **Constraints:** `gate_diff.py` before and after. A missing exit status must never be read as success.
- **Grill prompt:** `/mycelium-extra:grill Close the four receipt gaps in HANDOFF.md: sbatch --chdir with --wrap, Snakemake rule inputs counted as runs, Bash responses without an exit status, and unreceipted Codex runs. For each, say whether the fix is in the gate, in verify, or a documented limitation, and show the verify output before and after.`
- **Acceptance:** a `--chdir` job's receipt names the right script path; a rule input no longer appears as a run; a successful Claude Code run records exit 0 from the event and conforms; a failed run leaves a receipt with its exit code (or `failed`/`interrupted`) and verify reports the failure; a run whose status cannot be known shows as `unknown` and verify reports a gap; the verify skill and gate docs state that runs under Codex are not receipted.
- **Tests:** gate tests for the first three cases, including each hook payload shape (success, background, `Exit code N`, a bare failure message, an interrupt, no event name); verify tests for an event-inferred 0 (`CONFORMS`), a failure receipt (`DOES_NOT_CONFORM`), and the `unknown` status (gap and resulting `CONFORMS_WITH_GAPS`). No Codex test: (d) is documentation only.
- **Effort:** M.
- **Status:** done: (a), (b), (c) and (d), and `gate_diff.py` scenarios for the E2 commands with their write twins and for each hook event shape.

### E4: Test features not yet used in real work

- **Why:** several shipped features have unit tests but no record of use on a real project: hints, harden, verify `stale`/`status`/`explore`, the R scilintr CLI path, R-kernel notebooks, and R chunks in `.Rmd`. Bugs in them will surface at the worst moment, in someone's real analysis.
- **Scope:** one scripted pass of each feature on the C1 fixture (extended with an R notebook and an `.Rmd`), recording expected versus observed output; a bug issue for each mismatch; a "tested in use" note per feature in `HANDOFF.md`.
- **Out of scope:** fixing the bugs found (each becomes its own task); new features.
- **Depends on:** C1.
- **Constraints:** hints stay off by default; harden still ships test files only; remaining scilintr findings still block verify; a missing or unparseable check is still a gap.
- **Grill prompt:** `/mycelium-extra:grill Plan a scripted exercise of each untested feature listed in HANDOFF.md on the fixture project (hints, harden, verify stale/status/explore, R scilintr CLI, R-kernel notebooks, .Rmd R chunks). For each, write the expected output before running, then record what happened. Do not fix anything in this task.`
- **Acceptance:** every listed feature has an expected-versus-observed record; every mismatch has an issue.
- **Tests:** the scripted pass is added to `tests/test_end_to_end.py` where the output is deterministic.
- **Effort:** M.
- **Status:** todo.

### E5: Parked chunk-lint cases

- **Why:** the R-chunk extraction for `.Rmd` and `.qmd` misses four known cases: a document-level `execute: eval: false`, `child=` documents, `knitr::read_chunk`, and `{r engine=...}` chunks. The first makes lint check code that never runs; the others make it skip code that does. HANDOFF.md parks them until a real repository uses them, so check for one before starting.
- **Scope:** handle document-level `eval: false` (skip, and say so); follow `child=` paths relative to the document; report `read_chunk` and non-R engines as a gap with the chunk label.
- **Out of scope:** executing knitr; resolving chunk options set in R code at render time.
- **Depends on:** none.
- **Constraints:** an unhandled case is a gap, never clean.
- **Grill prompt:** `/mycelium-extra:grill Handle the four parked chunk-lint cases from HANDOFF.md (document-level eval false, child documents, knitr::read_chunk, engine= chunks). Show the current extraction code, and decide for each whether to handle it or report it as a gap.`
- **Acceptance:** one fixture document per case produces the planned result (skipped with a notice, followed, or reported as a gap).
- **Tests:** four fixture documents and matching unit tests next to the existing chunk-extraction tests.
- **Effort:** S.
- **Status:** todo.
