# Advanced features

[Back to the usage tiers](usage.md)

Everything on this page is real, supported and tested, but you do not need it for Tiers 1 to 3 of the [usage tiers](usage.md): planning, running with approval, and verifying reportable work. It was moved here from the [approval gate](approval-gate.md), [verification](verification.md) and [skill](skills.md) pages so those read as one story. Nothing was removed: every setting, subcommand and file below behaves as it did.

**On this page:** [Approval instances](#approval-instances) · [Run limit](#run-limit) · [Approval latency and comprehension checkpoint](#approval-latency-and-comprehension-checkpoint) · [Validation bindings](#validation-bindings) · [Exact execution](#exact-execution) · [Other `gate.json` settings](#other-gatejson-settings) · [Plan-review packets and consent](#plan-review-packets-and-consent) · [Validation in the report](#validation-in-the-report) · [Plan differences](#plan-differences) · [Stale plans](#stale-plans) · [Overview of all plans](#overview-of-all-plans) · [Runs and citations](#runs-and-citations)

## Gate features

### Approval instances

Approving writes an immutable record, `.mycelium-extra/approval-instances/<hash>/<instance_id>.json` (schema `mycelium-extra.approval-instance.v1`): the plan's full sha256, the pins and script pins, whether preparation finished (`prepared`: `complete`, or `legacy-no-ready` for a pending entry from before the `ready` field), and a list of `limitations` (a legacy preparation, inputs pinned only by size and time, a folder pinned by listing). When the plan has them, the instance also holds `validation` and `execution` (the checked blocks, with each check's pinned files and definition hash), and the approval file carries the same two keys; a plan without the blocks writes neither, so its instance id is unchanged. `approvals/<hash>.json` stays the file the gate reads and gains `instance_id`. The id hashes the frozen content, not the time or session, so approving the same freeze again reuses the same instance, and approving the same prose with different pins writes a second instance and keeps the first. A launch records the instance it ran under, so a run that started before a reapproval keeps naming the older freeze. Approvals without `instance_id` are legacy: one implicit instance, history before it unknown. A [freeze](approval-gate.md#freeze) writes a new instance, because its script pins differ; the instance and the approval file are never rewritten by a re-pin, which goes to `repins/<hash>.jsonl` instead.

### Run limit

One approval can cover many runs of the same scripts, and after enough re-runs the plan you approved may no longer describe what runs. Set `"max_runs_per_approval": 3` (any whole number of 1 or more) in `gate.json`, and the fourth gated run is denied with the number of runs so far and what differs from the first of them: the commit, uncommitted changes, and each script's content (shown even with `pin_scripts` off). Present the plan again; approving it (`approve` or `approve plan <hash>`) restarts the count.

- The count comes from the run receipts since the approval, so it matches `verify`: explore runs do not count, a `command -v` lookup is not a run, a failed run is, and a denied run leaves no receipt. A run is counted when its receipt arrives, so runs still in flight, or two runs in one command, can overshoot by that many. A Slurm job counts when it is submitted.
- The approval file is not changed. `verify list` and `verify status` show `(limit N reached (M since approval))` next to the run count, derived from the same receipts.
- An invalid value is ignored with a notice. Unset means no limit and no change in behaviour.

### Approval latency and comprehension checkpoint

Every approval (`approve` or `approve plan <hash>`) appends one line to `.mycelium-extra/approvals.jsonl`: the hash, session, when the plan was shown and approved (`shown_ts`, `approved_ts`), the seconds between them (`latency_s`), the number of step rows in the plan table (`plan_rows`) and its length in characters (`plan_chars`). It is a log for you to read later: it is never shown in a notice, on the card or by `verify`, it never blocks or slows an approval, a failed write does not stop the approval, and the approval file is unchanged. A plan shown again restarts the clock.

Every tool call the gate denies after checking it appends one line to `.mycelium-extra/denies.jsonl`: `ts`, `session_id`, `tool` (the name as the gate sees it: `Bash`, `Edit`, `Write`, `apply_patch`) and `reason`, the first sentence of the denial cut at 160 characters. A `deny` from `on_error` (a broken gate, or an old Python) is not logged here; it goes to `gate-errors.jsonl`. Like `approvals.jsonl`, nothing reads it back: not a notice, the card or `verify`. Count how often the gate stopped work yourself, for example `jq -r .reason .mycelium-extra/denies.jsonl | sort | uniq -c`.

Set `"checkpoint_steps": 8` (a whole number of 1 or more) in `gate.json` and a plan table with more than 8 step rows is not approved at the first `approve plan <hash>` (a bare `approve` gets the same question). The reply asks one question made from the table, not by a model: which step number makes a quoted Choice (the row is picked from the hash, so asking again gives the same question). Answer with `approve plan <hash> <number>`; the answer needs the hash. A wrong number shows that row (step, Choice, Source) and asks again; nothing is denied and the pending plan does not change. A right number approves as usual. A plan without Choice cells is asked which step names its first script or path; a plan with neither is approved without a question. Re-approving an unchanged plan asks again. The log line then carries `checkpoint` with `asked`, `passed` and `wrong_attempts`.

- Unset or `0` is off, and then `approve plan <hash> <number>` is not an approval, as before. An invalid value is ignored with a notice.

### Validation bindings

An optional comment block in the plan text names the acceptance checks the researcher approves, so that a result can later be tied to the check that produced it and a changed expectation cannot keep the authority of the approved one:

```text
<!-- validation-bindings {"version": 1, "checks": [
  {"id": "V1", "plan_row": "3", "required": true, "defined_by": "researcher-approved",
   "test_paths": ["analysis/x/tests/expected_rows.tsv"],
   "invocation": ["python", "analysis/x/tests/check_rows.py"],
   "evidence_path": "analysis/x/outputs/check_rows.json"}]} -->
```

The block is optional; a plan without it is approved and run as before. The gate reads it in the Stop hook, before the plan can become ready:

- Every field except `required` (default `true`) must be present, and unknown keys, an unknown `version`, duplicate ids, a `plan_row` that is not a row of the plan table (or repeats there), an unsafe path (absolute outside the repository, `..` escaping it, a symlink out, `~`, a `$` substitution, the gate's own state folder), a `test_paths` file that does not exist, and malformed JSON are errors. The card then lists the errors and the plan is not approvable: `approve plan <hash>` replies that nothing was approved and to fix the block. Showing the corrected plan (a new hash) prepares it again.
- `test_paths` are the files that define the check: the test, its fixtures and its expected values. Each is pinned by sha256 in the prepared plan, the approval record and the approval instance (`validation`: per check its fields, `files` `{path: sha256}` and a `definition_sha256` over them), so approving the plan freezes the expectation, not just the check's name. `invocation` is the command (an argv list, or a string split like a shell would) that runs it, from the repository root. `evidence_path` is where the run writes its result; it must be a safe path but need not exist yet, and it is never pinned, since the check rewrites it.
- `defined_by` (`agent-proposed`, `researcher-approved` or `independent`) is recorded and shown as "declared by"; the gate cannot verify who wrote the check.
- While an approval with bindings covers a run, the gate denies the run when any pinned file has changed or is missing, naming the check and the file. A changed expectation invalidates the old acceptance evidence: the plan must be shown and approved again, which pins the new bytes. Editing any other file, or the evidence file, changes nothing.
- A launch whose command equals a check's `invocation` (same argv, run from the repository root) records `validation_check` with the check id in its launch entry and receipt, so `verify` can tie a result to the check that produced it. The gate does not run the check, and a pass file that merely exists proves nothing.

The check's command has to be seen by the gate to be recorded. A test under `tests/` is outside the default gated paths (`analysis/**`, `nbs/**`), so a run of it is not gated, has no launch record and no `validation_check`. Either keep the test under a gated path (for example `analysis/x/tests/`), where the plan table must also name it, or add its folder to `gated_paths` in `gate.json` yourself; the gate never widens its own scope. The card says which case applies to each check: `not gated`, `gated but not named in the plan table`, or `gated, named in the plan table`.

### Exact execution

By default a path or command in the plan table is a broad grant: any arguments pass. For a reportable step that is too loose, since a changed `--model`, contrast or threshold is a different computation under the same approval. An optional block freezes the command of chosen steps:

```text
<!-- exact-execution {"version": 1, "steps": [
  {"row": "2", "argv": ["python", "analysis/x/fit.py", "--model", "mixed", "--threads", "4"],
   "cwd": ".", "env": {}, "operational": ["--threads"]}]} -->
```

- `row` is a row of the plan table, `argv` the command from the program on (wrappers such as `conda run`, `srun` or `timeout` and leading `VAR=value` words are not part of it), `cwd` the repository-relative folder (default `.`), `env` the inline variables it may carry, `operational` the flags that may differ. A `$` or backtick in `argv`, an unknown key or version, an unknown row and an unsafe path are errors, as for bindings. The block narrows a grant and never widens one: the step's script must still be named in the table.
- A step is about a run when its argv names a script the run launches (or, for a gated command such as `snakemake`, its program). Such a run must equal a declared argv in the declared folder: same program name, same arguments in the same order (`./` ignored), except the operational flags, whose value may differ and which may be added or removed. `> file` redirections are ignored; `< file` is not. Otherwise the run is denied with the declared and the actual command.
- A flag listed as operational is read as taking a separate value only when the step writes it with one (`--threads 4`) or with `=`; to add one the step does not show, write `--flag=value`, so that a boolean flag cannot swallow a positional argument.
- A shell substitution (`$X`, `$(...)`, backticks) in the launched command, or a folder that is an unresolved expansion (`env -C "$WORK"`), cannot satisfy an exact step and is denied. Inline variables must be declared in `env` with the same value; variables set elsewhere in the shell are not visible to the gate.
- The three kinds of change are different actions. An **operational retry** (cores, memory, queue, a log path) may differ only in the listed flags and needs nothing. A **frozen-code re-freeze** (the script changed) is the existing pinned-script path: the plan is shown and approved again. A **changed analytical argument or intent** (another model, filter, contrast, threshold, seed or input) goes back to the researcher, who approves a revised plan.
- A run no step is about keeps its broad grant (`exact_match: false` in its launch entry and receipt). A run held to a step records `exact_match: true` and `exact_step` (the row). A mismatch is denied, so no launch entry exists for it.

The match is on the launched words, not on what the script does with them: it does not read a params file named in the arguments (pin it under `Inputs:`), and it cannot see wrappers' own options (`command_env` records a `conda run` environment). It is a freeze of the command line for the runs the gate can see, not of the science.

### Other `gate.json` settings

`gated_paths`, `gated_commands`, `approval_hours` and `on_error` are in [Settings](approval-gate.md#settings). These keys are optional; a missing key uses its default.

| Key | Default | Meaning |
|---|---|---|
| `max_runs_per_approval` | unset | A whole number of 1 or more. After that many runs under one approval, the next gated run is denied until you re-approve the plan. See [Run limit](#run-limit). |
| `checkpoint_steps` | unset | A whole number of 1 or more. A plan with more step rows asks one question about its table before approval. See [Approval latency and comprehension checkpoint](#approval-latency-and-comprehension-checkpoint). |
| `pin_hash_mb` | `200` | Bytes of pinned inputs (in MB) hashed per hook before falling back to size and mtime. |
| `pin_seconds` | `5` | Seconds the pin check may take per hook. |
| `card_lint` | `true` | Lint the planned code when a plan is presented and show the result on the card. `false` turns it off. |
| `lint_on_write` | `true` | Lint each gated script as it is written and tell the agent the open findings; the user sees what is left when the turn ends. `false` turns it off. |
| `lint_before_run` | `false` | `"warn"` or `"block"`: before a gated run, tell about or deny a script whose findings lint-on-write recorded and that has not been edited since. See [Lint on write](approval-gate.md#lint-on-write). |
| `lint_before_stop` | `false` | `true` blocks the Stop once per change while scripts written this session have open findings. See [Lint on write](approval-gate.md#lint-on-write). |
| `pin_scripts` | `true` | Block a run whose script changed since it was approved or first run. `false` turns it off. |

### Plan-review packets and consent

It first runs a pattern-based pre-send check for secrets, contact details, home paths and
the participant IDs in the plan's input tables, then shows the packet and the check's output
and asks before sending it outside the machine; Biomni uses cloud credits. Flags with an
empty `redactions:` mean do not send. Nothing is sent until you type
`send packet <first 12 hex characters of the digest>` yourself: that prompt, not the
agent, records consent for the exact packet bytes. A clean check is not a clearance. Codex can read the
repository beyond the packet, so for participant-level data it runs on a data-free copy.
Missing reviewers are reported unavailable.

`review_packet.py` (see [plan-review](https://github.com/mdmanurung/mycelium-extra/blob/main/skills/plan-review/SKILL.md)) prepares an immutable review packet and, before anything is sent, checks that the user consented to exactly those bytes. Only the gate writes that consent: when the user's prompt is exactly `send packet <12 to 64 hex characters of the digest>` (case and surrounding whitespace ignored; nothing before, after or around it), the prompt hook finds the one prepared packet folder under `.mycelium-extra/review-packets/` whose digest starts with that prefix and which has its manifest, writes `.mycelium-extra/review-consent/<digest>.json` (schema `mycelium-extra.review-consent.v1`: `digest`, `session_id`, `ts` and the literal `prompt`), and answers with the digest and the next step, `review_packet.py verify`. An ambiguous prefix, an unknown digest or a prompt embedded in longer text records nothing (the first two answer why; the last is an ordinary prompt). An agent cannot make the user type it, and `review_packet.py` never writes consent. This is a cooperative control, not a sandbox: an agent with unrestricted shell access can still send other bytes.

## Verify features

### Validation in the report

A plan may declare acceptance checks in a `<!-- validation-bindings -->` block: per check an `id`, the `plan_row`, whether it is `required`, who defined it (`defined_by`), the pinned `test_paths` (a test or expectation file), the `invocation` that runs it and the `evidence_path` it writes. Approval freezes the block and pins the files. `verify` runs nothing; it reads the instance's record, the receipts and the evidence file, and gives each check one outcome:

| Outcome | What it means | Required check | Optional check |
|---|---|---|---|
| passed | A matched run of the invocation under this approval instance created or changed the evidence file, nothing touched it afterwards, the pinned files are still as approved, and the file says it passed. A data-contract result (`mycelium-extra.contract_result.v1`) passes with exit 0 and no block; its warnings are kept and shown (`passed with N warning(s)`). | no finding | no finding |
| failed | The check command exited nonzero, or the result says failed (a data-contract result with exit 2, naming the blocking checks with their expected and observed values). | **block** | info |
| not run | No matched run of the invocation under this instance (a run under an earlier instance does not carry over; the line says so), or a data-contract result whose checks could not run (exit 3, or exit 1 for an unusable contract), even when the runner passed the checker's nonzero exit code on. | gap | info |
| changed | A pinned test or expectation file differs from approval or is missing, or a data-contract result was produced from a contract that is not a pinned file. An expectation edited after approval does not keep its authority. | gap | info |
| unattributable | The evidence file is not tied to the matched attempt: the gate did not observe outputs, the attempt did not create or change the file (it was written by the agent outside the run), or it was modified after the attempt. A result written by hand, or a stale one, cannot pass. | gap | info |
| stale | The check passed, but a later attempt under the instance (not a check's) changed a declared output, or ran without its outputs being observed, so the result no longer speaks for the outputs. Run the check again. | gap | info |
| unsupported | The file is not JSON or has no `status` of passed or failed, a data-contract result's `checks` or `contract` is malformed, or the exit status was not recorded. | gap | info |

A check command that exits nonzero is a failed run and blocks like any failed run, whatever its result says; a runner that should leave the judgement to the result file exits 0. **Not established** is the gap wording for a required check: the plan's expectation is not counted as met, and a report with such a gap is never `CONFORMS`. It is not a failure; it says the records cannot show the check passed. `defined_by` (`agent-proposed`, `researcher-approved`, `independent`) is shown as the plan declared it, with "not verified": a label is not proof of who wrote the check, and approval binds the named expectation, not its scientific truth. The evidence file must be one of the plan's declared outputs (or inside a declared output folder) for the gate to observe it being written.

`write` adds `validation-<hash>.json` to the bundle: the frozen binding (with each file's sha256 and the definition's sha256), every check's outcome, reason and attempt, and the evidence file's path and sha256. A bundle without it is from a plan with no binding, or from an older verify, and reads as before.

### Plan differences

`verify diff <old> <new>` compares two plans whole, with whitespace collapsed and nothing shortened, so a change after a long shared prefix is still seen. It lists a changed objective; changed, added and removed table rows (keyed by the ID column: `#`, `id`, `no`, `no.`, else the first); dropped columns; a changed row order; changed `Inputs:` and `Outputs:` lines; the raw `<!-- validation-bindings -->` and `<!-- exact-execution -->` blocks, compared as text and not interpreted; and the runs the plan table allows. Rows whose ID is duplicated or missing are "cannot compare". The result is exact equality of what the plans say, not a judgement that the science is unchanged, and a formatting-only edit reports no change.

### Stale plans

`verify stale` sweeps every verified plan. It lists the ones whose scripts, pinned inputs, or outputs changed since their provenance was written. For each, it gives a ready `rg` command that finds the findings resting on it in `.living/findings/`, by session ID or plan hash.

After a planned run in a Mycelium repository, the gate suggests writing the finding's Evidence Ledger Run/Session cell as `<session-id>; plan <hash>`, and ending its Result cell with `[agent-derived: <output path>]`. Mycelium reads only the ledger's date cell.

`verify stale` reads only committed provenance, so it works without the gate on any clone. By default outputs are compared by size and time, and the result says `metadata checked`: a same-size file with its old modification time looks unchanged. `verify stale --content` instead hashes each output and compares it with the SHA256 verify saved (in `outputs-<hash>.tsv`), so such a change is caught and a file merely touched is not reported. A file with no saved SHA256, or one the `--hash-mb` or `--seconds` budget did not reach, is `content not checked` and keeps the size and time check; the summary counts both. A notebook output is hashed as the raw file (its executed results), not as its code cells, which are the right identity for the code that ran. Bundles written before this change recorded a notebook's code-cell hash, so those entries can read as changed until the next `write`.

### Overview of all plans

`verify status` is an on-request overview, with one row per approved or verified plan. Each row shows:

- its analysis folder, runs, verify status, and staleness (size and time only; use `stale --content` for content);
- whether the saved report was `qualified` for reporting (the `Reportable` column);
- the lint verify recorded (`N finding(s)`, `M approved threshold(s)` for threshold findings the plan approved, `clean`, `not run`, `not recorded`; a missing or unreadable linter shows as a gap, never `clean`);
- the verify status from `PROVENANCE.md` with the bundle's state appended (`CONFORMS (complete)`; `legacy producers` for a table from an older verify);
- the folder's `ANALYSIS_MANIFEST.md` entry: `listed: <first status word>`, `listed`, or `not listed`. It reads Mycelium's YAML `status:`, `**Status**:` lines, and a table's Status cell.
- with `max_runs_per_approval` set in `gate.json`, whether a plan has reached it: the run count then reads `N (limit L reached (M since approval))`.

No hook runs it.

One limit: only a run the gate saw from Pre to Post, with the output named by file or one-level glob, can be observed writing it; any other output is tied to a run by time alone and stays a gap.

### Runs and citations

`verify runs [RESULTS_DIR]` lists the `run_<YYYYMMDD>_<slug>` folders of a results folder with the status each run's label (`RUN.txt`, or a sibling `<run>.RUN.txt` for a frozen run) gives it, plus `updated` (newest file inside) and a content `id`. It also lists gaps in the labels and, in a Citations section, the `data/` and `code/` symlinks that cite a run of another analysis, with that run's status. It never writes, never sets a status, and only suggests a supersession; it is not part of `verify report` or `status`.
