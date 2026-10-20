# 13 · Function audit (tracker)

Objective: track every finding from the two audits of 2026-10-20 to a decision: fixed, dropped with a reason, or parked with a return condition. Nothing here is fixed yet unless a Status says so.

Sources: `plans/1.0.0-review/coherence-audit.md` (hooks and skills together, human-control lens; local, gitignored) and `plans/1.0.0-review/function-audit-ultracode.md` (workflow `wf_e6d21f7c-569`: 7 read-only reviewers, 169 agents, each finding checked by two skeptics; same findings as below with the reviewers' full evidence in the workflow journal). The ultracode findings are **candidates**: two skeptic agents agreed, no human has reproduced them.

Statuses: **todo**, **in progress**, **built** (code written, not landed), **done**, **parked**, **dropped**. Add a one-line reason with `parked` and `dropped`; record the commit with `done`.

Severity is the reviewer's. Read gate findings against the README: the gate "is not a security boundary" and catches execution mistakes, so a spelling only a dodge would use is `misleads` at most; a spelling an agent uses innocently (`x=$(Rscript analysis/a.R)`, `env PYTHONPATH=/x python3 ...`) is the real concern, and at minimum needs a line in `docs/approval-gate.md`.

Suggested order (user to choose): (1) gate findings an agent hits innocently, (2) planning-skill findings that give silent wrong answers, (3) E1b follow-ups, (4) the rest. Work in a worktree, run `hooks/tests/gate_diff.py` before and after any change to `hooks/gate.py`, one feature per two commits, no push without the user's word.

## A. Coherence audit (human-control lens)

| ID | Finding | Severity | Status | Notes |
|---|---|---|---|---|
| F1 | Four writes (`verify write`, `harden`, `decision-status`, `idea-triage` status) rely on the agent asking first; nothing enforces it | misleads | todo | User decision 2026-10-20: opt-in `confirm_writes`, off by default, reusing the typed-prompt consent pattern of `send packet`. Needs a grill: how the hook recognises each write on all three hosts |
| F2 | Human-control settings (checkpoint, run cap, window) not shown anywhere at a glance | misleads | parked | User unsure (2026-10-20). Checked: `init --diagnose` already lists `approval_hours`, `checkpoint_steps`, `max_runs_per_approval` and `on_error` with values and a `(default)` tag; it prints `null` for the two opt-in guards and does not say in words that this means off. Return if the user wants a plain-language line |
| F3 | Roadmap principle said "confirmed append" but `harden`, `idea`, `idea-triage` write too | misleads | done | `7124c3f` (3 docs pages amended) |
| F4 | README says Extra works in an ordinary repository; five skills need Mycelium | cosmetic | todo | One line in the README skills list |
| F5 | Codex has no `PostToolUseFailure`; effect on receipts of a failed run not tested | cosmetic | todo | Add a Codex test or state the outcome in `docs/reference/gate.md` |
| F6 | `on_error: allow` fails open by default | cosmetic | dropped | Recorded decision (`docs/decisions.md`, 0.9.66); see also X23 |

## B. E1b real run

| ID | Item | Status | Notes |
|---|---|---|---|
| E1b-1 | Real `snakemake --use-conda` run on the HPC (Snakemake 9.27, conda 24.9.2) | done | Plan `508e8b3b`; layout is `.snakemake/conda/<hash>_/`, `<hash>_.yaml`, `<hash>_.env_setup_done`; `verify.rule_envs` reads it |
| E1b-2 | `pip_packages` lists each pip package twice (`lib/python3.1` symlink to `python3.11`) | built | Worktree branch `fix/e1b-real-env`, uncommitted; dedupes by real path; test added; 264 verify tests pass |
| E1b-3 | Wrapped `snakemake --use-conda` (for example `sh run.sh`) gave neither a record nor a gap | built | Same worktree; `wrapped_rule_env_gaps` adds a gap; test added |
| E1b-4 | `rule_envs` ignored `-d`/`--directory` | built | Same worktree; shlex parser for `-d`, `-dDIR`, `--directory[=]`, `--dir`; tests added |
| E1b-5 | Add a trimmed copy of the real folder as a fixture; relabel `synthetic_format_only` | built | Worktree: `skills/verify/tests/fixtures/snakemake-9.27-conda-24.9` (312K, no local paths), test `test_real_snakemake_9_27_folder`; key is now `layout_checked_against`; LIMITS line, `docs/verification.md`, `docs/concepts/not-guaranteed.md`, `docs/decisions.md`, backlog and CHANGELOG reworded to "one real run, other versions not validated". Untracked `analysis/e1b-conda-check/` still to remove after landing |
| E1b-6 | Land the worktree: two commits (fix, version bump), fast-forward only, no push until the user says | todo | Waiting for the user's word to commit; full suite result in the progress log |

## C. Ultracode audit: confirmed by both skeptics (40)

| ID | Area | Severity | Finding | Where | Status | Notes |
|---|---|---|---|---|---|---|
| C0 | gate-decisions | breaks | Command substitution is never read: a gated run inside $(...) or backticks is allowed | hooks/gate.py:420 | todo |  |
| C1 | gate-decisions | breaks | Heredoc, here-string and piped shell or interpreter input is not scanned in the pre-run decision | hooks/gate.py:449 | todo |  |
| C2 | gate-decisions | breaks | `env VAR=/path ...` lets the gated command through (an assignment value containing '/' is taken for the command) | hooks/gate.py:628 | todo |  |
| C3 | gate-decisions | breaks | srun options that take a value are mis-read: -q and two unknown options in a row let the run through | hooks/gate.py:108 | todo |  |
| C4 | gate-decisions | breaks | `cd` options are treated as the directory: `cd -P DIR`, `cd -- DIR`, `cd -L`, `cd -` hide the real folder | hooks/gate.py:737 | todo |  |
| C5 | gate-decisions | breaks | A backslash-newline right before the command word fuses it with a stray newline, so the run is allowed | hooks/gate.py:421 | todo |  |
| C6 | gate-decisions | breaks | Event cwd outside the repository: the hook returns before the gate loads, so a gated run by absolute or relative path and a write to the state folder are not checked | hooks/gate_run.py:20 | todo |  |
| C7 | gate-decisions | breaks | State-folder writes missed: `>\|`, `>&` redirects and `sed --in-place` | hooks/gate.py:969 | todo |  |
| C8 | gate-decisions | misleads | Package-manager runners and process launchers are not read as wrappers | hooks/gate.py:586 | todo |  |
| C9 | gate-decisions | breaks | `python -m snakemake` bypasses gated_commands | hooks/gate.py:660 | todo |  |
| C10 | gate-decisions | misleads | Inline code that changes folder into a gated folder with a bare name is not recognised, contradicting the documented rule | hooks/gate.py:537 | todo |  |
| C11 | gate-decisions | breaks | Heredoc delimiters that are not plain identifiers swallow the rest of the command, so a later gated run is allowed | hooks/gate.py:478 | todo |  |
| C12 | gate-decisions | misleads | Subshell and popd are not scoped: the folder after `(cd D && ...)` or `pushd D; popd` is wrong, so the real path is mis-resolved | hooks/gate.py:748 | todo |  |
| C13 | gate-decisions | misleads | timeout duration forms are not recognised: decimals and some suffixes drop out of the wrapper skip | hooks/gate.py:633 | todo |  |
| C14 | approval-flow | breaks | A mid-message 'Plan status: READY' makes an approvable card even when the reply ends DECISION_REQUIRED; a later READY after an early DECISION_REQUIRED gets no card | hooks/gate.py:3932 | todo |  |
| C15 | approval-flow | misleads | `card <hash>` on a plan with an invalid block answers 'plan <hash> showed its full card' | hooks/gate.py:3853 | todo |  |
| C16 | receipts-launches | misleads | explore.log records an exploratory run that was denied and never ran, and the Stop notice reports it | hooks/gate.py:3149 | todo |  |
| C17 | receipts-launches | breaks | focus 'start' or 'switch' always fails with 'Try again' when the project root path contains a symlink | hooks/stateio.py:47 | todo |  |
| C18 | receipts-launches | cosmetic | A duplicate Post for a call whose receipt is larger than 1 MB is labelled 'no launch record' instead of 'duplicate callback' | hooks/gate.py:1220 | todo |  |
| C19 | verify | misleads | disclose says 'No lint finding was open' when scilintr never ran | skills/verify/scripts/verify.py:3670 | todo |  |
| C20 | verify | misleads | status and stale hide provenance that git ignores: 'not verified' / 'No verified plans' for a plan that was written | skills/verify/scripts/verify.py:3852 | todo |  |
| C21 | verify | misleads | E1b: with -d and no -s, the default Snakefile is searched under the -d folder, but Snakemake finds it in the original cwd | skills/verify/scripts/verify.py:1361 | built | Fixed in the E1b worktree with a test (see E1b-4) |
| C22 | verify | cosmetic | E1b: `-dDIR`, `--dir`/`--direc` (argparse abbreviations) and a repeated -d are not parsed; the gap then says 'through a wrapper' for a direct run | skills/verify/scripts/verify.py:1347 | built | Fixed in the E1b worktree with a test (see E1b-4) |
| C23 | verify | misleads | E1b: a wrapped snakemake run that uses --conda-prefix (or a profile conda-prefix) leaves no built envs under .snakemake/conda and gets no gap at all | skills/verify/scripts/verify.py:1439 | built | Fixed in the E1b worktree with a test (see E1b-4) |
| C24 | planning-skills | breaks | init --paths with no glob (analysis, analysis/, ./analysis/**, "") is accepted without warning and the gate then covers nothing | skills/init/scripts/gate_init.py:113 | built | Worktree `fix/planning-skills`: `bare_folders()` warns; warns rather than rewrites |
| C25 | planning-skills | misleads | --diagnose says gate uses the default for an invalid gated_paths / gated_commands, but the gate does something else (fails open with a gate error, or reads a string character by character) | skills/init/scripts/gate_init.py:358 | built | `--diagnose` states the real effect (`UNCHECKED_EFFECT`) |
| C26 | planning-skills | misleads | A huge integer in gate.json crashes --diagnose with a traceback, and the gate itself fails open with a gate error | skills/init/scripts/gate_init.py:223 | built | Partly: `--diagnose` no longer crashes and names the effect. The gate itself still fails open: see G1 |
| C27 | planning-skills | misleads | init crashes on a non-UTF-8 .gitignore after writing gate.json, and a rerun reports 'already gated' so the ignore line is never added | skills/init/scripts/gate_init.py:92 | built | `add_ignore` reads bytes |
| C28 | planning-skills | breaks | new-analysis: a scaffold named plan or tracker in a Mycelium repo silently loses the analysis doc and still reports it as created | skills/new-analysis/scripts/new_analysis.py:319 | built | `new-analysis` refuses `PLAN.md`/`TRACKER.md` doc names before writing |
| C29 | planning-skills | misleads | new-analysis leaves a .<name>.scaffold.lock file in the parent folder, outside the new folder, contradicting 'writes nothing outside <dest>' | skills/new-analysis/scripts/new_analysis.py:342 | built | Design choice: lock file kept (removing it races a concurrent scaffold) and documented as the one exception in `new_analysis.py`, `SKILL.md`, `docs/reference/skills/new-analysis.md`; no test |
| C30 | planning-skills | breaks | idea: a first-8-words slug over about 240 bytes (for example one long token such as a sequence or URL) fails with ENAMETOOLONG, and --recover then fails forever | skills/idea/scripts/capture.py:103 | built | Slug cut to 60 characters |
| C31 | planning-skills | misleads | decision-status: a UTF-8 BOM before the first heading silently drops the first entry | skills/decision-status/scripts/decision_threads.py:60 | built | `utf-8-sig` |
| C32 | planning-skills | breaks | data-contract-check: trailing all-empty rows (Excel ',,,' lines) count as samples, so row-count checks pass wrongly | skills/data-contract-check/scripts/data_contract_check.py:130 | built | All-empty rows skipped; over-wide `,,,` rows still block |
| C33 | planning-skills | breaks | data-contract-check: a misspelled key in a classic check is silently ignored, so the assumption is dropped and the check PASSes | skills/data-contract-check/scripts/data_contract_check.py:770 | built | Unknown key in a classic check is a usage error (exit 1); existing test `test_contract_cannot_downgrade_severity` now expects exit 1 |
| C34 | planning-skills | misleads | data-contract-check: 'None' and '<NA>' are treated as missing but the docs list only empty, NA, NaN, NULL | skills/data-contract-check/scripts/data_contract_check.py:32 | built | Docs fixed (`SKILL.md` lists `None` and `<NA>`), no code change, no test |
| C35 | review-and-reports | misleads | presend_check misses participant IDs when the packet's Inputs line is not at a line start (YAML-quoted proposed_plan, bullet, bold) | skills/plan-review/scripts/presend_check.py:112 | todo |  |
| C36 | review-and-reports | misleads | A named input table whose ID column or delimiter is not recognised is silently treated as clean | skills/plan-review/scripts/presend_check.py:134 | todo |  |
| C37 | review-and-reports | misleads | prepare cannot be passed for a run-plan packet, although SKILL.md says the user can consent to an input coverage gap | skills/plan-review/scripts/review_packet.py:113 | todo |  |
| C38 | review-and-reports | misleads | Two analyses can share one track-changes output folder, so the later report overwrites the earlier | skills/track-changes/scripts/track_changes.py:690 | todo |  |
| C39 | hosts-and-runtime | misleads | OpenCode adapter drops the gate-failure and Pre-notice gap text when the tool call fails | opencode/index.js:289 | todo |  |

### Gate follow-ups raised while fixing

| ID | Item | Status | Notes |
|---|---|---|---|
| G1 | `_number` in `hooks/gate.py` (about line 176) raises `OverflowError` on a huge integer in `gate.json`, so the gate fails open (or denies under `on_error: deny`) | todo | Same one-line `try/except OverflowError` as `gate_init._number`; belongs in the gate track (C26 residual) |

## D. Ultracode audit: contested (25)

One skeptic reproduced each of these and the other did not, or called it a documented limit. Decide per row; the default is to read the evidence in the journal before fixing.

| ID | Area | Severity | Finding | Where | Status | Votes (real/severity) |
|---|---|---|---|---|---|---|
| X0 | gate-decisions | cosmetic | A `$'...'` (ANSI-C quoted) script path is mangled into a path no plan can match | hooks/gate.py:420 | todo | real/cosmetic, no/not-a-defect |
| X1 | approval-flow | misleads | An amendment card whose baseline is an expired or other-session approval revives that plan's old steps while showing only the delta and 'Unchanged ... as approved' | hooks/gate.py:2117 | todo | real/misleads, no/not-a-defect |
| X2 | approval-flow | misleads | When the event has no session_id, `approve plan` reports 'may run for 24 h' but every run is denied | hooks/gate.py:3911 | todo | real/misleads, no/not-a-defect |
| X3 | approval-flow | cosmetic | Near-miss commands are silently ignored with no notice: `approve plan <hash>` (two spaces), `approve plan`, `allow explore <7-hex>`, `allow explore`, `send packet <hash> please` | hooks/gate.py:3859 | todo | real/cosmetic, no/not-a-defect |
| X4 | approval-flow | cosmetic | Different session ids that sanitise to the same name share one pending file | hooks/gate.py:241 | todo | real/cosmetic, no/not-a-defect |
| X5 | receipts-launches | breaks | A crash-truncated receipts.jsonl tail swallows the next receipt, which the hook still reports as recorded | hooks/gate.py:245 | todo | real/misleads, no/not-a-defect |
| X6 | receipts-launches | misleads | Receipt says pins_checked: true when the pinned input was not re-checked (pin_seconds time limit) | hooks/gate.py:4311 | todo | real/misleads, no/not-a-defect |
| X7 | receipts-launches | misleads | A malformed or truncated launch record is reported as 'older than 24 h', and its content is discarded | hooks/gate.py:1239 | todo | real/misleads, no/cosmetic |
| X8 | receipts-launches | misleads | Explore grant and other per-session state share one file across session ids that differ only in special characters, or have no id | hooks/gate.py:241 | todo | real/cosmetic, no/cosmetic |
| X9 | verify | misleads | report --analysis-dir with a wrong or parent folder silently drops the claims check; a contradicted claim reads CONFORMS | skills/verify/scripts/verify.py:2473 | todo | real/misleads, no/not-a-defect |
| X10 | verify | misleads | Summary row 'Code checks' says 'lint clean' while the linter was not run | skills/verify/scripts/verify.py:3342 | todo | real/cosmetic, no/cosmetic |
| X11 | verify | misleads | verify runs: the 'content id' does not change when a file's content changes at the same size | skills/verify/scripts/verify.py:4613 | todo | real/misleads, no/not-a-defect |
| X12 | verify | misleads | runs labels: status: current with superseded_by set, and status: superseded with no superseded_by, give no finding | skills/verify/scripts/verify.py:4655 | todo | real/misleads, no/not-a-defect |
| X13 | verify | cosmetic | A claim of `8` verifies against a cell of `8.9` because truncation is accepted as agreement | skills/verify/scripts/verify.py:1567 | todo | real/cosmetic, no/not-a-defect |
| X14 | verify | cosmetic | write failures surface as Python tracebacks instead of `verify:` errors | skills/verify/scripts/verify.py:3795 | todo | real/cosmetic, no/not-a-defect |
| X15 | planning-skills | cosmetic | --diagnose flags null for max_runs_per_approval and checkpoint_steps as PROBLEM, but the gate treats null as unset with no notice | skills/init/scripts/gate_init.py:251 | parked | real/cosmetic, no/not-a-defect; Not changed: one skeptic called it not a defect; effect text printed is accurate; return if the user wants null accepted |
| X16 | planning-skills | misleads | idea: one empty or corrupt .capture-*.json (crash between mkstemp and write) makes every later capture and --recover fail | skills/idea/scripts/capture.py:103 | built | real/misleads, no/not-a-defect; Corrupt `.capture-*.json` stops with the file named; no cleanup of published records |
| X17 | planning-skills | misleads | decision-status: an unclosed or 4-space-indented ``` fence silently swallows every later entry | skills/decision-status/scripts/decision_threads.py:71 | built | real/misleads, no/not-a-defect; An unclosed fence is a stated gap on stderr; a 4-space-indented fence is still read as a fence |
| X18 | planning-skills | cosmetic | data-contract-check: malformed-row errors report the record number rather than the file line when an earlier quoted field contains a newline | skills/data-contract-check/scripts/data_contract_check.py:131 | built | real/cosmetic, no/not-a-defect; Physical line numbers |
| X19 | review-and-reports | cosmetic | focus resolve_target accepts symlinks that resolve to the project root, a non-gated folder, or the gate state folder | hooks/focus.py:105 | todo | real/cosmetic, no/not-a-defect |
| X20 | review-and-reports | cosmetic | Item cap is applied before sorting, so late-inserted attention items are dropped ahead of routine ones | skills/track-changes/scripts/track_changes.py:560 | todo | real/misleads, no/not-a-defect |
| X21 | review-and-reports | cosmetic | Secret redaction in track-changes diffs leaves URL passwords, private-key bodies, JWTs and the tail of a quoted password | skills/track-changes/scripts/track_changes.py:31 | todo | real/cosmetic, no/not-a-defect |
| X22 | review-and-reports | cosmetic | grill's instruction to read track-changes brief.md gives the wrong folder name and no freshness check | skills/grill/SKILL.md:20 | todo | real/cosmetic, no/not-a-defect |
| X23 | hosts-and-runtime | breaks | A broken interpreter makes the hook exit 127 with no JSON, so on_error deny silently fails open | hooks/py.sh:25 | todo | real/misleads, no/not-a-defect |
| X24 | hosts-and-runtime | cosmetic | OpenCode shell payload with a non-object tool_input is silently allowed as an empty command | hooks/gate_run.py:97 | todo | real/cosmetic, no/not-a-defect |

16 further candidates were rejected by both skeptics and are not tracked.

## Grill prompt for the gate track (C0 to C13)

Not started. Paste into a fresh session at the repository root. It is one grill because the findings share `hooks/gate.py` and one oracle.

```
/mycelium-extra:grill Fix the gate findings C0 to C13 in docs/roadmap/13-function-audit.md (section C, area gate-decisions, plus the heredoc and `python -m snakemake` rows). Split them first into (a) spellings an agent uses innocently, which must be denied like the plain form: command substitution `x=$(Rscript analysis/a.R)` and backticks, `env VAR=/path ...`, `srun -q`/unknown options, `cd -P DIR` and `cd -- DIR`, a backslash-newline before the command word, `python -m snakemake`, package-manager runners; and (b) spellings only a deliberate dodge would use (heredoc or here-string bodies, piped shell input, odd heredoc delimiters, `>|` and `>&` writes into the state folder), where documenting the limit in docs/approval-gate.md may be the right fix. For each (a) row show the current decision path in hooks/gate.py with line numbers, the change, and a paired test that a real run in the same shape is denied and a harmless look-alike is still allowed. Also decide the event-cwd-outside-repo case (hooks/gate_run.py:20) and the mid-message "Plan status:" card case (C14). Work in a worktree, never edit hooks/ in the main tree; run `python3.12 hooks/tests/gate_diff.py --base 267d9e244d1f50abef2d024c9632c50df1911823 --expect hooks/tests/gate_diff_expected.json` before and after, and show every decision that differs with a one-line rationale per oracle entry; do not regenerate the oracle blindly. Keep hooks/gate_run.py parseable on Python 3.6. Do not push.
```

## Progress log

- 2026-10-20 (verified): planning-skill fixes C24 to C34 and X16 to X18 built in worktree `fix/planning-skills` by two agents, then checked: all five touched suites pass, every new test fails on the old code (clean HEAD worktree plus only the new tests), and the repo-wide tests, ablations and link check pass. Not committed. 20 data-contract tests skip because h5py is not installed. E1b worktree: `verify` suite, nine repo-wide tests and ablations all pass.
- 2026-10-20 (later still): F2 answered (parked). Gate-track grill prompt drafted above. Planning-skill fixes C24 to C33 started in worktree `fix/planning-skills` by two agents; results to be recorded here.
- 2026-10-20 (later): E1b follow-ups C21 to C23 built in the worktree with tests; real folder added as a fixture; docs relabelled. `verify` suite and the repo-wide tests re-run on the worktree (result below once finished).
- 2026-10-20: both audits run; this tracker created from their results. F3 landed (`7124c3f`). E1b-2 to E1b-4 built in the worktree, not landed.

## Not covered by either audit

Live Claude Code, Codex and OpenCode sessions; Python 3.9 and 3.14; the docs build; `tests/e2e/ablate.py`; any subsystem outside the seven probed (gate decisions, approval flow, receipts and launches, `verify`, planning skills, review and report skills, host adapters).
