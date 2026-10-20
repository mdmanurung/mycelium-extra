# Changelog

All notable changes to mycelium-extra are listed here, newest first. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are the `version` in the four plugin manifests. Entries from 0.9.16 to 0.9.29 were rebuilt from `git log`.

## [Unreleased]

## [0.15.0] - 2026-10-21

### Added

- **gate:** opt-in `confirm_writes`. A skill prepares a pending write with `hooks/confirm_write.py prepare`, and the write waits for the user to type `confirm write <id>` (valid 1 hour); `verify write` is denied without it. It is skill-scoped, so Mycelium's own `.living/` writes are never stopped, and it is cooperative for harden, decision-status and idea-triage. `init --diagnose` flags an invalid `confirm_writes`.
- **track-changes:** an Analysis Journal (`--journal`) with overview, detail and evidence views, explicit portable checkpoints (`--save-checkpoint`), inert note references (`--note`), a `mycelium-extra.evidence-handoff.v1` export written by verify, and a read-only consumer example. No gate, approval or oracle semantics change.

## [0.14.4] - 2026-10-20

The gate now denies more shell spellings, so a command that ran silently before can be denied: the message says to write the path literally. `gate_diff` differs from 0.14.3 only by a `pins_unchecked` field in the stored launch record (reviewed oracle regenerated, 57 cases); no allow or deny decision changes in that comparison.

### Added

- **sc-conventions live-test tooling:** a recorded-method check (R3, `skills/verify/scripts/method_fidelity.py`), an offline M1 preparer and M3 readiness check (`tests/eval/sc_conventions.py`), and validation-recipe bindings for R1 to R3. The public scorer tests are split from the sealed-key leakage tests.
- **OpenCode adapter:** a silent exit-0 gate run is read as allow, not as a gate failure.

### Fixed

- **gate (scan):** command substitution, heredoc and piped shell input, `env VAR=/path`, `srun` options that take a value, `cd` options, line continuations, `>|` and `>&` redirects, `sed --in-place`, package-manager runners, `python -m` of a gated command, bare folder names in inline code, quoted heredoc delimiters, subshell and `popd` scope, `timeout` durations and `$'...'` paths are read. Python and R stdin stay a documented limit. A huge number in `gate.json` no longer makes the gate fail open.
- **gate (approval flow):** the last `Plan status` line of a reply governs; `card <hash>` on an invalid block says it has no full card; an amendment card with an expired or other-session baseline gets the whole card; an approval with no session id no longer says a run may follow; near-miss commands of four words or fewer get a notice; session ids that sanitise alike no longer share state.
- **gate (receipts):** a denied command leaves no explore entry; a truncated receipts tail no longer swallows the next receipt; a duplicate Post is found for a receipt over 1 MB; a truncated launch record is reported unreadable and kept; the receipt says `pins_checked: false` and lists `pins_unchecked` when the time limit skipped a pin.
- **runtime:** an event whose cwd is outside the repository still finds the gate; the state writer refuses a symlinked state file or folder, not a symlinked project root; `focus` refuses a symlink to the project root, a non-gated folder or the state folder; `hooks/py.sh` answers in the hook protocol when no interpreter exists; a non-object OpenCode `tool_input` is reported; a failed OpenCode tool call still shows the gate notice.
- **verify:** a linter that never ran is not reported as clean; a wrong `--analysis-dir` is refused; git-ignored provenance is swept; the run id changes when a file is rewritten at the same size; a `status` that contradicts `superseded_by` is a finding; a write failure is a `verify:` error; the claims coverage line states how a claim matches its cell.
- **plan-review:** `Inputs` as a bullet or in bold is read; delimiters `,;\t|` and wider ID column names are read, and a table with no ID-like column is reported; `--consent-unread-inputs` lets the user consent to an unread input on a run-plan packet.
- **track-changes:** two analyses no longer share one report folder; the item cap keeps attention items; redaction covers URL passwords, JWTs, private-key bodies and quoted secrets.
- **docs:** the README names the five skills built around Mycelium's files; `docs/reference/gate.md` states what a failed Codex call leaves in the receipts; `grill` names the track-changes brief folder and checks it is current.

## [0.14.3] - 2026-10-20

### Added

- **grill:** for scientific and statistical plans, `grill` now reads the repository's *activated* convention packs (`.living/conventions.md`, `.living/conventions/ACTIVE_CONVENTIONS.yaml`) after it has the user's question and the project evidence. It picks the relevant guides by task (design, QC, replicate-aware inference, composition, integration, perturbation, pathway activity), and carries their rules, exceptions and falsifiable checks into the plan with a source. A pack that is only in a marketplace is not active, and a convention is never treated as proof. Read-only: no new skill, permission or gate rule (`skills/grill/references/scientific-conventions.md`).

## [0.14.2] - 2026-10-20

### Fixed

- **init:** a glob-free `--paths` folder (for example `analysis`) is warned about, since it gates only the folder itself. `--diagnose` now states what the gate does with an unchecked `gated_paths` or `gated_commands` value and no longer crashes on a huge integer. A non-UTF-8 `.gitignore` no longer aborts init after `gate.json` is written.
- **new-analysis:** an analysis named `plan` or `tracker` is refused (its analysis doc was silently lost). The empty scaffold lock file in the parent folder is documented as the one write outside the new folder.
- **idea:** the slug is capped at 60 characters; a corrupt recovery record is named.
- **decision-status:** a UTF-8 BOM no longer drops the first entry; a file ending inside a code fence is a stated gap.
- **data-contract-check:** all-empty rows are not samples; an unknown key in a classic check is a usage error (exit 1, was silently ignored); errors name the real file line; `None` and `<NA>` are listed as missing values.

- **verify (E1b):** the per-rule conda env record was checked against a real `snakemake --use-conda` run (Snakemake 9.27.0, conda 24.9.2). Pip packages are listed once (conda-forge's `lib/python3.1` symlink to `python3.11` doubled them, in the plain conda snapshot too). `-d`, `-dDIR` and `--directory` are honoured for `.snakemake/` while the default Snakefile is still looked for in the starting folder. A `snakemake` run wrapped in a script (`sh run.sh`) is now a gap when its folder has built envs or a Snakefile with `conda:` rules. `rule-envs-<hash>.json` carries `layout_checked_against` in place of `synthetic_format_only`.

- **init:** `--hours 0` is accepted, matching the gate's `approval_hours: 0` (every approval expires at once); negative and non-finite values are still usage errors.
- **init:** `--diagnose` now says what the gate does with each invalid value (for example `card_coverage: 1` is read as off), not only what it wants.

## [0.14.1] - 2026-10-19

Fixes from two independent reviews of 0.14.0 (one by Claude reviewers, one by OpenCode sessions; see `plans/1.0.0-review/`). The gate now denies more shell forms, so a command that ran silently before can be denied: the message says to write the path literally. `gate_diff` differs from 0.14.0 only by a `kind` field in the stored pending entry (reviewed oracle regenerated, 20 cases).

### Fixed

- **gate:** a short-option cluster containing `c` (`bash -lc`, `sh -ec`, `env bash -lc`, dash, ksh, fish, csh, tcsh) is read as inline code, so an agent can no longer write an approval record through `bash -lc 'cp ... approvals/x.json'`.
- **gate:** a runner operand containing `$`, `$(...)` or a backtick (except plugin-root variables), loop and `then`/`do` bodies, `pushd`, and `apptainer`/`singularity`/`docker`/`podman` `exec` or `run` no longer slip past unseen; `make` and `bash <script>` are documented as untraced.
- **gate:** `rm -r`, `mv`, `find -delete`, `rsync --delete` on an ancestor of `.mycelium-extra/`, `git clean -x/-X` and `git stash -a` count as state writes.
- **gate:** `.replace(` on text read from `.mycelium-extra/` is no longer denied as a write.
- **gate:** `approve plan|amendment|freeze <hash>` must match the card kind; `approval_hours`, `pin_hash_mb` and `pin_seconds` are validated with a notice naming the key.
- **verify:** a mismatched, unresolved, request-failed or offline citation past the 40th is reported (only the resolved lines stay capped); the frozen plan text is re-hashed and a mismatch blocks, and `write` refuses to save it; an emptied instance `pins` map, `--conda-prefix` runs and a missing Snakefile are gaps; "no commit yet"; an unattributable compound run is headlined "not attributable". `--json` gains `git_repo` and `plan_intact`.
- **OpenCode:** a null gate reply, a tool-reply system message or a wrong `root` shows a note on the tool result; a null reply denies under `on_error: deny`; typed `card` and `freeze` replies reach you through `ctx.session.synthetic`.
- **init:** `init` and `--diagnose` list all 15 `gate.json` keys with their real defaults and accept 0 for the numeric keys, as the gate does.
- **docs:** README and `approval-gate.md` no longer say nothing happens until you say so; five skills say their confirmation step is the agent's instruction, not a gate rule; the Socratic probes no longer anchor on a default; `handoff` shows the old file's head before overwriting; `harden` writes its test only after you confirm; skill counts, check kinds and flags are corrected; `docs/example.md` shows the Coverage row.

### Added

- A real, offline `report.html` example for `track-changes` on a synthetic analysis (`docs/examples/track-changes-report.html`), regenerated by `tests/e2e/make_track_changes_example.py`.
- Nine ablations for the consent guards (protected-state writes, exact `approve` matching, session scoping, the explore grant, `on_error`); `tests/e2e/ablate.py` now runs 17.

## [0.14.0] - 2026-10-19

The roadmap items that were parked behind the 2026-10-31 usage measurement, built at the user's request on 2026-10-19, plus grill's Socratic and librarian references. The one decision-visible change is the card: `card_coverage` is now on by default, which adds a `Coverage` line to the approval card and nothing else (`gate_diff` differs from 0.13.2 in 12 of 173 cases, each only that row; the reviewed oracle `hooks/tests/gate_diff_expected.json` is regenerated to match). Set `"card_coverage": false` to turn it off.

### Added

- **`grill` Socratic mode, `explain row N`, `challenge row N`:** `references/socratic.md`. Off by default; one neutral probe inside a question you own, whose answer becomes the row's Validation cell. Explain and challenge are read-only, spend no questions, and never approve or edit.
- **`grill` librarian dossier:** `references/evidence-assistance.md` now defines what the evidence lookup returns (what was searched, found, not found, the alternatives, and the decision left to you) and makes it available for any row after the plan is shown.
- **`track_changes.py --explain <item_id>` (M4):** a bounded five-heading evidence block for one report item, read-only, writing no files; Review Brief pointers from `grill`, `handoff` and the Mycelium integration page.
- **`focus_id` and `focus_folder` in receipts, and `focus_notices` (M3):** a matched receipt records the focus open at launch; with `"focus_notices": true` (default `false`) the Stop hook shows one plain line, once per focus and folder, for runs under another gated analysis.
- **`verify` per-rule conda envs (E1b):** reads literal `conda:` paths from the Snakefile, records each env file's hash and, when a byte-identical built env exists, its conda-meta and pip packages. **The layout is checked only on a synthetic fixture** (`synthetic_format_only: true`); an env it does not recognise is a gap.
- **`docs/decisions.md`:** the decisions that still bind and the dead ends not to redo.

### Changed

- `card_coverage` defaults to `true` (see above).
- README restructured as Introduction, Installation, Input Data, User Guide, License.
- Documentation site uses the Clarity theme (`sphinx_clarity_theme` 2.1.0 by ReadCraft, Community MIT licence; its footer attribution is kept). The Sphinx `-W` build passes locally.
- Roadmap 11 and 12: the librarian is a role inside `grill`, not an adapter; the live Socratic study (M5b) stays parked.

## [0.13.2] - 2026-10-19

The last open tasks of four roadmap waves: what the card cannot establish before a run, a decision trace for one plan row, citation resolution, and a disclosure draft for the agent's own part. Nothing here changes an allow or deny decision (`gate_diff` 173/173 identical).

### Added

- **`verify report <hash> --trace [ROW]` (DT-1):** a read-only decision trace, one line per plan row, or — with `ROW` — that row's declared script and exact command, the attempts that ran it, its bound checks' results and its supported outputs, each labelled `declared`, `observed`, `check result`, `candidate` or `unresolved`. Refused with `--json` and with `write`, and it writes nothing.
- **`verify report <hash> --resolve-citations [--contact EMAIL]` (D2):** resolves every DOI, `PMID:` and `arXiv:` identifier in the documents verify checks for claims (Crossref, NCBI E-utilities, arXiv; one request per identifier, with a wait between them) and compares the returned title and first author with the citation line. A new `## Citations` section counts the verdicts: `resolved` when both appear in the line, `mismatch` when they do not (blocks), `unresolved` when the service has no such record (blocks), `no identifier` for a reference-shaped line that carries none, `not checked (offline)` — the default, and a gap, so a citation is never shown as resolved that verify did not resolve — and `not checked (request failed)` when the request never reached a service. A resolved citation means the identifier exists and matches the text beside it, not that the paper supports the sentence.
- **`verify disclose <hash>` (D3):** a plain-text, read-only draft of an AI-use methods paragraph built from the records — plugin and version, the plan's steps, the approval and freeze history, the runs with their launch evidence, re-pins, environments, the verify status and qualification, the claims checked, the citations found, the lint state and the commit. Every sentence ends with `[source: <record>]`, and a record that is missing prints `[BLANK: <what is missing>]` instead of a guess. There is no `--json` form, and it writes nothing.
- **`gate` card coverage (M1):** the approval card lists the pins and checks the plan carries and says what they cannot establish before the run.
- **`grill` (M1):** `references/polya-heuristics.md` — a backward chain from a claim to the check that would discriminate it, and five heuristics for a plan that is blocked, plus an opt-in evidence lookup that rides inside one rule-3 question.
- **`plan-review` (M2):** a material objection carries four fields and a status, and the synthesis opens with the single strongest undecided crux (or says `no substantiated material concern`).
- **Validation recipes (VR-1):** result statuses, subprocess steps and pairing limits now match what `verify` reports, with the measurement commands in `docs/development.md`.

### Changed

- `verify report --json` gains a `citations` key; the e2e fixture catalog plants a fabricated DOI (V-33) and asserts the offline gap, so the grill failure-mode row `Invented citations` can credit the check that ships instead of naming it `planned: D2`.
- The `verify` skill carries the three-line post-report look-back (*Established / Still uncertain / Next insight*).
- Focus and track-changes M3/M4 are parked behind the 2026-10-31 usage measurement, with the trigger recorded in the tracker.

## [0.13.1] - 2026-10-19

A second review of 0.13.0 against the code. Nothing here changes an allow or deny decision (`gate_diff` 173/173 identical).

### Fixed

- **`track-changes` called a wildcard output "missing".** An `Outputs:` word such as `de_<contrast>.csv` is a pattern; it is now matched with a glob, reported under the files it finds, and a pattern that matches nothing is a coverage limit, not a missing file.
- **A malformed approval or a failed write was a Python traceback.** Both are now a message; a failed write still prints the card.
- **A legacy receipt with no exit status counted as failed**, and a receipt covering two plans could be flagged as another approval instance. The first is now unknown, and only a receipt of the current plan alone is compared.
- **Coverage said more than it knew.** It now says when more than 40 scripts were pinned, that scripts no approval pinned and no run touched are not compared, and how many transcript edits lay outside the project path. The objective text is redacted like diffs.
- **Redaction missed `"password": "x"`, `'api_key': 'x'` and `Authorization: Bearer x`.**
- **`focus status` "Runs" said an approval was active when the plan named the folder only in a Choice cell.** It now asks the gate's question: does a Step cell name a path in or above the folder.
- **A busy focus lock showed as a gate error;** it is now "could not lock the focus record". Two session ids that differ only in odd characters no longer share a file, and two folders (`analysis/a-b`, `analysis/a/b`) no longer share a report folder (`analysis__a__b`).
- **OpenCode dropped the focus line when a hint was also shown.**

### Changed

- Three tests that could not fail now can (the hint test, the read-only list test, and the viewer tests, which the Python CI legs skip for lack of Node and the OpenCode job now runs with `MX_REQUIRE_NODE=1`, so they cannot be skipped there). The OpenCode test pins 13 skills.

## [0.13.0] - 2026-10-19

Two new commands from the Focus + Track Changes spec (milestones M0 to M2). Neither changes an allow or deny decision, and a session that never types `focus` sees no difference (`gate_diff` 173/173 identical).

### Added

- **`focus`:** typed prompts (`focus analysis/X [plan <hash>]`, `focus status`, `focus switch analysis/Y`, `focus end`) say which analysis a session works on. A folder is any existing directory under a gated root (`analysis/` and `nbs/` by default, or your `gated_paths`). One small record per session in `.mycelium-extra/focus/`; changed only by the typed command, never by a CLI. Advisory: it grants no run and changes no approval, and `focus status` shows separately whether a run is authorized. While a focus is open each prompt carries one advisory line. A missing folder, a path that escapes the project, a missing session id or an unrelated plan is refused.
- **`track-changes`:** a read-only report for one analysis. Plan row changes between the original and the current approved plan, scripts edited since each approval with bounded diffs, the gate's run records, declared outputs older than the code, and direct edits to sibling analyses from an optional Claude Code transcript, for this session's focus only. Prints a short card and writes `snapshot.json`, `brief.md` and an offline `report.html` under `.mycelium-extra/track-changes/` only. Every item separates observed, potential and unknown; what was not observed is listed. Several candidate plans stop the run and ask for `--original`.
- `docs/focus-and-track-changes.md` and the tracker `docs/roadmap/10-focus-track-changes.md`.

### Not done

- Turn-end notices, draft actions and `focus_id` in launches and receipts (M3), and AI explanation and a usability study (M4).
- The viewer was run in Node against a DOM stub, not in a browser.

## [0.12.0] - 2026-10-18

Lessons from ClawBio's validation talks, taken as documentation, one fixture and two small additions. Nothing here changes an allow or deny decision, and nothing is on by default.

### Added

- **`docs/validation-recipes.md`:** three recipes (sample and key join, contrast direction, complete result table), each with its claim, expected answer, binding, deliberate failure, benign control and limit. `V-DC12` (new) shows a result table filtered after testing passing every other check and failing only `complete-table`. `tests/test_recipes.py` parses the page's binding blocks with the gate's own reader.
- **`verify refs <path> [--sha SHA256]`:** which saved plans pinned a file as a check's test or expectation, read-only and without the gate. `definite` means a pinned file had that SHA256; `possible` means the same path with another or unchecked SHA256, or a path named in the plan text. Bundles without a validation record are counted, not guessed at.
- **`card_coverage` (default `false`):** one `Coverage` row under `Checks` on the compact card: steps with a bound check, prose-only rows, exact steps, and that other steps take any arguments. `gate_diff` reports 173 of 173 cases identical with it off.
- **`docs/verification.md` "When something fails"** (who enforces each stop, rebased on re-pin and freeze) and **`docs/exercise.md`**, a six-step practice run on the fixture project.

### Not done

- `docs/example.md` still shows 0.10.2 output: regenerating it needs `scilintr` and an `Rscript` whose R has it, and this host has neither.

## [0.11.0] - 2026-10-18

Third step of the researcher-first redesign: an approval is a working scope. You and the agent edit the plan's scripts without a block, and you review the code once, at a freeze.

### Changed

- **An edit to a script the plan lists no longer blocks a run.** The gate re-pins it (`.mycelium-extra/repins/<hash>.jsonl`, append-only; the approval and its instance are never rewritten) and shows you and the agent a notice: lines added and removed, and the numbers that moved with whether a plan row holds them. This reverses the 0.9.44 block-by-default. Changed inputs, validation files, exact-execution files and the run limit still block.
- **`freeze <hash>`** shows the diff of each script since the approval, scripts first pinned since, which steps to run again, and the gaps `verify` finds now; one `approve` pins the code you reviewed as a new approval instance. It replaces the second grill before a reportable run.
- **A plan that only adds steps and scripts shows a change-only amendment card** (`approve amendment <hash>`); any other change keeps the whole card. `approve amendment` and `approve freeze` mean `approve plan`.
- `verify` reports a run of code no approval froze as a gap and lists re-pins as info; `lint_before_run` and `lint_before_stop` say what `verify` does with a finding left open.

### Docs

- `approval-gate.md` (pinned scripts, amendment cards, freeze), `day.md`, `advanced.md`, `run-plans.md` and the README follow the code. New tracker `docs/roadmap/08-working-scope.md`.

## [0.10.2] - 2026-10-17

Second step of the researcher-first redesign: the two things you read most, the approval card and the verify report, now lead with the science and the answer.

### Changed

- The approval card is compact. It shows the question (or the goal), each choice with who made it, the checks, what ran before, and one `Runs` line (scripts, pinned, `any arguments`, reads, writes), then `More: card <hash> full` and `▶ approve  (or approve plan <hash>)`. A grant broader than named scripts (a folder, a command, an exact-execution block), a changed script or input, flagged Evidence and every warning stay on it. The previous full card is `card <hash> full`; `card <hash> checks` and `card <hash> diff` are unchanged. The 35-line digest is gone, since every card is now short.
- The card's lint line counts a threshold that an approved Choice states apart from open findings (`lint: step 3: clean; 1 approved threshold(s)`).
- `verify` opens its report with the status and five rows: ran as planned, numbers match, code checks, not checked, next. Everything below is the evidence behind them; `--json` and the last line `Verify status: ...` are unchanged.

### Docs

- New "Advanced features" page: approval instances, run limit, approval latency and checkpoint, validation bindings, exact execution, review consent, the optional `gate.json` keys, and the verify subcommands for plan differences, stale plans, overview and runs moved there. Nothing was removed from the code.
- New "A day with Mycelium Extra" page.

## [0.10.1] - 2026-10-17

Less bookkeeping, one fewer step to approve, and a gate that survives a stale hook registration.

### Changed

- A bare `approve` approves the one waiting plan shown last. With none or several waiting it approves nothing and names `approve plan <hash>`.
- A lint threshold in a Choice cell that the approved plan states no longer fails `verify`; it is reported as info. The match is on the number with its sign (`-1` is not `1`), against the Choice cells of the plan rows that name the script (every row when none does), and it covers notebook code cells. Text after `#` on the line is not read. `status` shows these as `N approved threshold(s)`, apart from open findings.
- The gate keeps a deny log, `.mycelium-extra/denies.jsonl`, to measure how often it blocks.
- The capacity and diary drafts are deleted; their helpers moved to `hooks/stateio.py`.

### Fixed

- A hook registration from before 0.9.76 (`python3 gate_run.py`, kept by a directory marketplace until the plugin is updated) ran under `python3` 3.6 and failed open on every call. `gate_run.py` now hands the event to `hooks/py.sh` once before reporting an old Python.
- Docs brought in line with the code: bare `approve` and `approve plan`, OpenCode as a third host, the approved-threshold exception, `py.sh` and Python 3.9 in the skill commands, the CI jobs, and the state files the gate writes.

## [0.10.0] - 2026-10-17

OpenCode is a supported host, alongside Claude Code and Codex. Claude Code and
Codex behavior is unchanged: `gate_diff` reports every existing case identical.

### Added

- OpenCode V2 support. The shared skills load through OpenCode's `skills` setting, and `opencode/` is a plugin directory that registers one `/mycelium-extra:<skill>` command per skill folder — the same command names Claude Code uses — and runs the approval gate. The adapter maps OpenCode's prompt, tool (`shell`, `edit`, `write`, `patch`), and turn-end (`session.execution.succeeded`) events onto the shared Python gate: a deny throws, gate text is appended to tool results, and approval cards and notices arrive as synthetic messages. It is inert in repositories without `.mycelium-extra/gate.json`.
- `hooks/gate_run.py --host opencode` payload decoding, `hooks/tests/test_opencode_gate.py`, adapter tests in `opencode/tests/` under `node --test`, and the `opencode-plugin` CI job.
- OpenCode receipts carry the shell tool's exit code, read from the result's `metadata.exit` (`exit_source: response`); a result without one records `unknown` as a verification gap.
- `plan-review` gains an OpenCode lead route: the Codex CLI supplies the engineering review and the Biomni MCP the biomedical one, under the same user consent and byte-bound send rules.

### Changed

- `gate_run.py` derives an OpenCode post event's hook event name from the launcher action before normalizing, so a failed post is read as `PostToolUseFailure`.
- `tests/test_versions.py` covers `opencode/package.json` as a fourth manifest, and the OpenCode adapter's reply buffer is decoded once so a multi-byte card glyph split across chunks cannot corrupt a card.

## [0.9.76] - 2026-10-17

Python 3.9 is now the minimum; 3.6 is no longer supported.

### Changed

- Hooks and skill commands run through `hooks/py.sh`, which uses `MYCELIUM_EXTRA_PYTHON` if set (as is), else `python3` when it is 3.9 or later (skill commands only, so an activated environment keeps its packages such as h5py), else the newest `python3.N` on `PATH` (3.14 down to 3.9). On RHEL 8, where `python3` is 3.6, this finds `python3.11` or `python3.12` without setup. A skill command with no Python 3.9 or later stops with one line naming the Python found.
- With only an older Python, `hooks/gate_run.py` says so on every hook in a repository with `gate.json` and follows its `on_error`: by default the call goes through with the message, `deny` blocks every tool call. Repositories without `gate.json` stay silent.
- The gate reads `sh <plugin>/hooks/py.sh [--hook] ARGS` as `python3 ARGS`, so the launcher is no way around it (a `py.sh` under a gated path stays a gated script).
- CI: the 3.6 leg is replaced by `python:3.9-bookworm` under `LC_ALL=C`. The test that compiled every script on Python 3.6 is replaced by one that runs `gate_run.py` under `/usr/bin/python3.6` when it exists.

### Fixed

- The Sphinx build failed on two links to pages outside the site; they now point to GitHub.
- `tests/e2e/ablate.py` crashed under the C locale on Python 3.6 while reporting a failing case.

## [0.9.75] - 2026-10-17

Execution fidelity: the source-verified roadmap of 2026-10-16 (change sets C01–C13, findings F01–F11). Tracker and evidence: [docs/roadmap/07-execution-fidelity.md](docs/roadmap/07-execution-fidelity.md).

### Added

- Immutable approval instances (`approval-instances/<hash>/<instance_id>.json`); `approvals/<hash>.json` stays the newest instance's view and gains `instance_id`. Same-prose reapproval with new pins makes a second instance instead of overwriting the first (F04). `verify --instance` checks one instance; runs under an older one are history.
- Launch attempts: `attempt_id`, `call_id`, `started`, `cwd` and a before snapshot of declared outputs. Two identical launches without a call id are `ambiguous` (F05); launches never taken are kept in `launches/abandoned/`. Receipts carry `launch_match`, `approval_instance`, `outputs_changed` and `outputs_observation`.
- Two optional plan blocks, frozen by approval: `<!-- validation-bindings -->` (approved checks; their files are pinned; a changed expectation denies the launch) and `<!-- exact-execution -->` (argv and cwd of reportable steps; `operational` flags may vary; a changed analytical argument is denied, F09). Plans without them keep the broad grant, and the card says so (`CAN RUN (in full) · broad grant: any arguments`).
- verify: a Validation section judges each bound check passed, failed, not run, unsupported, changed, unattributable or stale (a later attempt changed the outputs it judged) (F06); a Recovery section shows every attempt of a step, so an earlier failure stays visible after a changed retry (F08); a Scope block and a qualification table (authorization, completion, code and input identity, lineage, required validation, claim linkage, no blocking finding, no open gap) with `--require-reportable` (exit 3 when not qualified): a qualified run is always `CONFORMS`, and a folder or glob output with nothing written, or an instance prepared before readiness was recorded, is not established; a failure under an earlier approval instance stays named; claim coverage counts; `stale --content`; rerun evidence (declared, attempted, reproduced; nothing is launched).
- Output producers are graded: `evidence_method` (`attempt-observed`, `workflow-record`, `lineage-record`, `timing-only`, `none`) and `strength`; only `supported` names a producer. Mycelium lineage can confirm or contest a producer, never establish one alone. The bundle TSV gains the two columns (older bundles read as legacy).
- verify reads `gate-errors.jsonl` inside the plan's window: an error there is a gap (F07). Gate errors now record `host`, `session_id` and `call_id`.
- data-contract-check: `sample_alignment`, `identifiers` and `h5ad_layer` kinds, `--result-json`, and a strict CSV/TSV reader backported from Mycelium: a ragged row or an unterminated quote blocks (F11).
- Scoped exploration: `allow explore <plan hash>` limits the development grant to an active approval of the session; out-of-scope gated paths are denied and protected-file changes are surfaced; `stop explore`. Explore attempts are kept with their code version and never satisfy a check or own an output.
- Review consent bound to packet bytes: `review_packet.py prepare|preview|verify`, and the gate records consent only when the user types `send packet <digest>`.
- `gate_init.py --diagnose` (read-only), an evaluation scaffold in `tests/eval/` (scorer only on saved adjudications), and e2e cases F-01 to F-11, V-DC08 to V-DC11 and V-02c with controls; ablations A-5 to A-7.

### Changed

- `pins_checked` is true only for a receipt matched to its launch; a Post without a Pre no longer claims checked pins (F02).
- Approval differences compare whole cells, removed and reordered rows and the two plan blocks before the card truncates anything (F03).
- A quoted input path with spaces is pinned whole (F10).
- A single timestamp candidate is a gap, not a producer (F01, timing-only case). Tests that credited outputs by timing now use a matched Pre, write and Post.

### Migration

New fields are additive. An approval without `instance_id`, a receipt without `launch_match` and a bundle without the producer columns are read as legacy with the weaker meaning ("launch link not recorded"), never upgraded. No state needs converting.

### Known limits

- An unobserved process that writes a declared output between a matched Pre and Post is still graded `attempt-observed`; the report says the output changed during the attempt, not that the script wrote it.
- The `note_first_runs` lock falls back to the old unlocked update on a symlinked state folder.
- A scoped explore grant outlives its approval's expiry (it is never broader than the plain grant).
- `--diagnose` mirrors the gate's config rules rather than importing them.
- Mycelium's manifest session id seldom joins with a gate attempt, so lineage often stays unused.
- On a host that sends no call id, a launch whose Post never arrives makes identical retries `ambiguous` until it is abandoned; qualification only, never a denial. Claude Code and Codex send call ids.
- Any `<!-- validation-bindings` or `<!-- exact-execution` text in a plan is parsed as the block, including a quoted example; a malformed one makes the plan unapprovable until it is fixed.
- `prepare` refuses `.env` files and types outside its code-and-document list only; a table saved as `.txt` or a secret in a `.yaml` attachment is listed by the scan, not refused.
- Not qualified here: native Claude/Codex hosts, real model journeys, human adjudication, external reviewer calls and the Python 3.14 leg.

## [0.9.74] - 2026-10-17

### Added

- `verify runs [PATH]` lists the runs in a results folder (default: `results/` of the newest approval's analysis): name, version, kind, status, last changed (the newest file inside, not the folder), a content id, and the label's `why`, read from each run's `RUN.txt` or a sibling `<run>.RUN.txt`. It writes nothing. A run without a label is a gap; a name with `final`, `complete` or similar is a note; a run that looks superseded by a later version of the same slug and kind is only suggested, never marked. A "Citations" section checks the `data/` and `code/` symlinks that point into another analysis's run: unlabelled, superseded, failed, scratch or dangling is a gap, and a run changed after the approval is noted. `check` and `status` are unchanged.

## [0.9.73] - 2026-10-17

### Added

- Approval latency log (roadmap D10). Every `approve plan <hash>` appends one line to `approvals.jsonl` in the gate state folder: the hash, session, when the plan was shown and approved, the seconds between, the plan's step rows and length. It is only recorded, never shown or acted on, and a failed write does not stop the approval.
- `"checkpoint_steps": N` in `gate.json` (off by default). For a plan with more than N step rows, `approve plan <hash>` first asks which step number makes one quoted Choice; the answer is `approve plan <hash> <number>`. The question comes from the plan table, not a model; it is the same one each time it is asked, a wrong number re-shows that row and asks again, and nothing is ever denied. A plan with no Choice cells is asked for the step that names its first script or path.

## [0.9.72] - 2026-10-16

### Changed

- The capacity and diary hook registrations (SessionStart, SubagentStart/Stop, PreCompact, SessionEnd, and the all-tools PreToolUse matcher) are no longer in `hooks/hooks.json` and `hooks/codex.json`, which are as in 0.9.70 again. The feature is an unqualified draft; the registrations are kept in `hooks/capacity-hooks.json` to merge in once native lifecycle checks pass.

### Known limits

Found by the review of the 0.9.71 audit fixes and left open on purpose; none is a regression from 0.9.70.

- `env -C "$PWD/x" python ...`: the folder is a shell expansion, so the call is recognised but not gated, and no coverage gap is shown.
- `sbatch --wrap='python x.py'` is allowed when one plan names the script and a different plan names `sbatch`; the check at launch does not require one plan to name both, though the receipt does.
- A pending plan saved by an older version, interrupted before it was prepared, still counts as approvable (entries without the `ready` field are treated as ready).
- Capacity notes: with capacity on, the gate's state protection denies a Write of capacity's own recovery note (audit finding D-01).

## [0.9.71] - 2026-10-16

### Added

- `"max_runs_per_approval": N` in `gate.json` (roadmap D11). After N gated runs under one approval, the next is denied until the plan is approved again, and the denial lists what differs from the first of them (commit, uncommitted changes, script content). Explore runs and `command -v` lookups do not count; the approval file is never changed; `verify list` and `verify status` mark an approval that reached the limit. Unset means no limit and no change in behaviour; an invalid value is ignored with a notice.

### Fixed

From the 2026-10-16 feature stress audit and the independent approval and execution-evidence audit (`ME-01` to `ME-11`); each fix has a regression test.

- A shell call that joins commands (`&&`, `||`, `;`, a pipe) no longer gives each script in it the call's overall exit status: the runs are recorded with an unknown status and `verify` reports a gap (`ME-01`).
- A failed command receipt (`snakemake`, `sbatch`, a script run through a granted folder) now blocks in `verify`, an unknown exit status is a gap, and a folder the plan grants with no recorded run is a gap; a later run of the same command supersedes an earlier failed one (`ME-02`).
- Reapproving a plan with changed inputs no longer counts the earlier runs as evidence for the new pins; a skipped pin stays a gap; an output with several timestamp-compatible writers is a gap instead of being credited to one run (`ME-03`, `ME-06`, `ME-08`).
- `conda run -p`, `uv run --project`/`--python` and `env -C <dir>` are no longer missed by the gate; known option values of `env`, `uv`, `conda` and `srun` are read before the command is classified (`ME-04`).
- Paths with spaces in `Inputs:` and in steps are pinned and approved under their real name (`ME-05`).
- A plan is approvable only after its pins, scripts and card are prepared (`ready` in the pending entry; entries without it stay approvable), so an interrupted preparation cannot approve empty pins; the approvals that let a launch through are saved with the call, so its receipt keeps its plan after the approval expires or another plan is approved meanwhile (`ME-07`, `ME-09`).
- A claim against a table with a header and no rows is an unverified gap, not a crash (`ME-10`). `gate_diff.py` compares each side with its own plugin context and checks the intended differences exactly (`ME-11`).
- Provenance files are saved as one recoverable bundle; `idea` captures and `new-analysis` scaffolds are published atomically; `data-contract-check`, `decision-status`, `init` and `plan-review` refuse malformed input instead of passing it; the draft `capacity` and diary hooks keep recovery state.

## [0.9.70] - 2026-10-16

### Added

- `plan-review` pre-send check (`scripts/presend_check.py`, roadmap C3). Before the packet is shown to the user, it flags likely secrets, contact details, home paths and the participant IDs found in the tables the plan names under `Inputs:`. Flags with an empty `redactions:` exit 3 (do not send); with `redactions:` filled in they exit 2 (the user decides); a clean result says it is pattern-based. Matched values are masked. The audit and its gap list are in `docs/design/c3-plan-review-redaction-audit.md`.

### Changed

- The `plan-review` contract defines the `redactions:` entry shape, extends the exclusion list, and says Codex can read the repository beyond the packet, so it should run on a data-free copy when the repository holds participant-level data. The check's result is part of the reviewer status.

## [0.9.69] - 2026-10-16

### Added

- `init` prints one `note:` line when the Mycelium that `.mycelium/plugin-root` points at is not 0.6.0 or 0.7.2 (the versions Extra was checked against), or when its version cannot be read. It says nothing without Mycelium and never writes Mycelium's files. The tested versions are stated in `docs/mycelium-integration.md` (roadmap A5).
- `docs/example.md`: one real session on the fixture project, from the grill prompt to the verify report. `tests/e2e/make_example.py` regenerates it and `tests/test_example.py` keeps what it quotes in step with the code. It is linked from the README (roadmap A6).

### Fixed

- The approval card no longer shows one language's lint gap on the other language's steps: a missing R linter used to mark Python steps `not checked`.

## [0.9.68] - 2026-10-16

### Added

- `"lint_before_stop": true` in `gate.json`. When a turn would end while scripts the agent wrote this session still have open lint-on-write findings, the Stop is blocked once per change with the findings as the reason, so the agent fixes or waives them in the same turn. It never blocks twice in a row (`stop_hook_active`) and needs `lint_on_write`. Off by default.

## [0.9.67] - 2026-10-16

### Added

- `"lint_before_run": "warn"` or `"block"` in `gate.json`. When a gated run starts (explore runs included), a script it uses that lint-on-write recorded with open findings, and that has not been edited since, is reported to the user and the agent (`warn`) or denies the run (`block`). It reads the records of any session and runs no linter. Off by default; any other value is ignored with a notice.

## [0.9.66] - 2026-10-15

### Added

- Lint on write. A PostToolUse hook on `Write`, `Edit`, `MultiEdit`, `NotebookEdit` and (Codex) `apply_patch` runs scilintr on the gated scripts just written, in one call per patch with an 8 s limit per subprocess and a shared 16 s subprocess budget, and gives the agent their open findings as context, once per change. It never blocks. What scilintr could not check, including a script that does not parse under the hook's Python (3.6 on some clusters), is reported once per session as not clean, never silently skipped. Files beyond the five-file patch limit are reported as unchecked. Findings are kept per script, so parallel writes to different scripts do not lose each other, and text from the linter is cleaned and cut. The Stop hook tells the user, once per change, which scripts written this session still have open findings. Off with `"lint_on_write": false`. Mycelium's "lint after every write" rule is otherwise prose.

- `"on_error": "deny"` in `gate.json` blocks every tool call the gate could not check after an internal error, including a `gate.py` that fails to load. The default stays fail-open. Errors are recorded in `.mycelium-extra/gate-errors.jsonl` when it can be written; a failed write never changes the decision. An invalid value is ignored with a notice.

### Fixed

- Python 3.6 under `LC_ALL=C`: the gate test reads the handoff skill as UTF-8, and the verify shorthand test accepts the report's backslash-escaped output.

## [0.9.65] - 2026-10-14

### Fixed

- Verify reports NaN and infinity output cells as unverified claim gaps before numeric comparison or percent conversion. Reports retain the cell value and location, and finite mismatches still block. Regression coverage includes all comparisons, percent claims, a JSON cell, planted defect V-31 and guard ablation A-4.

## [0.9.64] - 2026-10-14

### Fixed

- Quote verify's skill description so the `Subcommands:` colon parses as YAML text. A focused stdlib regression checks the quoted scalar.

## [0.9.63] - 2026-10-11

### Added

- `idea` skill: park a passing idea in one line, with no questions. It writes `todo/<slug>.md` and one `todo/TODO_REGISTRY.md` row (priority `idea`, status `open`) in Mycelium's todo format, replies with one line, and touches nothing else, so a plan waiting for approval stays approvable (tests in `test_gate.py` and `test_codex_gate.py`). It uses Mycelium's `upsert_table_row.py` when that runs, and a plain edit when it does not (the script needs Python 3.7, and system `python3` here is 3.6).
- `idea-triage` skill: ranks the open ideas in `todo/` by impact (two axes by idea type), the things that must go right, the riskiest assumption (1 to 5, months to test), and a search of existing findings; names the cheapest go/no-go test for the top idea; shows a ranked table with a `park all` option and waits for the user's choice. Rubric adapted from Fischbach and Walsh (2024), *Cell*.

## [0.9.62] - 2026-10-11

### Added

- scilintr integration, in four parts. (1) `gate_init.py --tools` finds the Python `scilintr` and an `Rscript` whose R has the package (`--scilintr`, `--rscript`, `$MX_SCILINTR`, `$MX_RSCRIPT`, then `PATH`), checks that each works, and records them in `.mycelium-extra/tools.json`; `verify` and the card read it, so a cluster where neither is on `PATH` no longer gets a lint gap on every plan. (2) The approval card adds a `- lint:` bullet under each step that names existing code (`clean`, `2 open (R002, R011)`, `not checked (...)`), from the same run `verify` does; show only, never blocking, off with `"card_lint": false`. The Stop hook timeout is 30 s. (3) `verify` runs scilintr a second time with waivers off and lists each suppressed finding with its waiver and reason in the report and `lint-<hash>.txt`; an R waiver with no reason (R's scilintr accepts one, Python's does not) that suppresses a finding blocks. (4) The R scaffold stub opens with a `scilintr stage` line telling the user how to set `# STAGE:`; it sets none.

- The approval card's step list is now a top-down `Sequence`: each step (`↓ 2 fit.R*`, `*` = a default decided) with bullets for its choice and who decided it, what a default assumed, and its check. It replaces the old `Procedure` list. No card line is longer than 250 characters, except a `CAN RUN` grant and a script-diff line, which are never cut.

## [0.9.61] - 2026-10-08

### Fixed

- A Slurm job's state reached the `verify` report only when its `sbatch` receipt named a planned script. 59 of 86 real `sbatch` receipts name none (`$dir`/`$R` paths, `--wrap` from before 0.9.x, or only the `.out`/`.err` files B3 stopped counting), so failed jobs were invisible. `verify` now also reads the job's `WorkDir` and `SubmitLine` from `sacct` (retrying without them on a Slurm older than 20.11): a job whose recorded `sbatch` line names a planned script counts as that script's run. A job that names no planned script and did not complete is a gap, and so is a job ID recorded for different `sbatch` commands (an older gate gave several `sbatch` calls in one command the first ID). Array jobs (`N_1`, `N_2`) were never found by `sacct`; their tasks are now combined, and the worst state wins. Checked on 99 approved plans from `scale` and `bmv_pilot_cytof_integration`: no status changes; 11 planned-script rows now show their job (9 COMPLETED, 2 FAILED), and 23 unmatched jobs that did not complete are new gaps. Defect V-30.

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
