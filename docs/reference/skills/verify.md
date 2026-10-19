# verify

Checks one approved plan against the gate's record of what ran, and records the result as provenance once you agree. It only reads records. It never re-runs anything and never edits receipts or approvals. Guide: [Verify and record provenance](../../guides/verify-and-provenance.md).

## Synopsis

```bash
sh <skill-dir>/../../hooks/py.sh - --plugin-root <skill-dir>/../.. <action> [args] [options] < <skill-dir>/scripts/verify.py
```

Run from inside the repository, from stdin. Invoke with `/mycelium-extra:verify`. Never put the state folder's name on the command line; the script finds it.

## Subcommands

`<action>` is one of eleven values. "Gate" says whether it needs `.mycelium-extra/gate.json`.

| Action | Arguments | Meaning | Writes | Gate |
|---|---|---|---|---|
| `list` | none | approved plans, newest first | no | yes |
| `report` | `<hash>` | the five summary rows, then scope, findings, lint, claims, citations, validation, recovery | no | yes |
| `report` | `<hash> --trace [ROW]` | a decision trace instead: one line per plan row, or one row's declared script, attempts, bound checks and outputs. Hash first. Refused with `--json`, `write` and other actions. | no | yes |
| `write` | `<hash> --analysis-dir DIR` | save the frozen plan, receipts and the check into `DIR/provenance/` | yes | yes |
| `disclose` | `<hash> [--analysis-dir DIR]` | a draft AI-use methods paragraph, one sentence per line with `[source: ...]` and `[BLANK: ...]` for what no record shows. No `--json`. | no | yes |
| `diff` | `<old-hash> <new-hash>` | what changed between two plans: objective, rows, inputs, outputs, validation and exact-execution blocks, scope | no | yes |
| `multiplicity` | `<hash>` | what was tried before the plan was settled: earlier plans, runs, explore runs | no | yes |
| `explore` | `[--session ID \| --all]` | explore runs of gated code. Default: this session (`$CLAUDE_CODE_SESSION_ID`); with no session id, the last 7 days of every session. | no | yes |
| `stale` | `[--content]` | scripts, inputs and outputs out of date for every verified plan; reads committed `provenance/` | no | no |
| `status` | none | one table: plans approved or verified, runs, status, stale, lint, manifest listing | no | no |
| `runs` | `[RESULTS_DIR]` | labelled run folders of a results folder (`run_<YYYYMMDD>_<slug>`, `_vNN`, `RUN.txt`) | no | no |
| `refs` | `<path> [--sha SHA256]` | which saved plans pinned a file; `definite` when the SHA256 matches, `possible` otherwise | no | no |

`status` and `runs` read committed provenance, so they work on a clone with no gate. With no hash, list the plans and ask which one.

## Options

| Option | Applies to | Meaning |
|---|---|---|
| `--plugin-root DIR` | all (required) | this plugin's folder |
| `--repo DIR` | all | repository to read (default `.`) |
| `--analysis-dir DIR` | `report`, `write`, `disclose` | the analysis folder; guessed from the plan's scripts when omitted |
| `--instance ID` | `report`, `write` | check this approval instance (16 hex or a unique prefix) instead of the newest |
| `--json` | most | raw result. Not with `--trace` or `disclose`. `write` ignores it. |
| `--claims PATH` | `report`, `write` | also check this document's `<!-- claims -->` blocks (repeatable) |
| `--resolve-citations` | `report`, `write`, `disclose` | look up each DOI, PMID and arXiv ID on Crossref, NCBI and arXiv. Offline is the default and is a gap. |
| `--contact EMAIL` | with `--resolve-citations` | address sent to Crossref and NCBI; sent only if you pass it |
| `--require-reportable` | `report`, `write` | exit 3 when the run is not qualified (`write` saves the record first) |
| `--trace [ROW]` | `report` | the decision trace (above) |
| `--session ID`, `--all` | `explore` | which sessions' runs |
| `--content` | `stale` | hash each output against the SHA256 `verify` saved (default: size and time) |
| `--sha SHA256` | `refs` | the file's old SHA256 (at least 8 hex) |
| `--sacct PATH` | all | `sacct` command for Slurm job state (default `sacct`) |
| `--scilintr PATH`, `--rscript PATH` | `report`, `write` | linters; default: `tools.json`, else `PATH` |
| `--hash-mb N` | all | megabytes to hash (default 2000) |
| `--seconds N` | all | seconds budget (default 120) |

## What a report contains

It opens with `# Verify plan <hash>: <status>` and five rows: `Ran as planned`, `Numbers match`, `Code checks`, `Not checked`, `Next`. Each starts `yes`, `no`, `partly`, or `n/a` with its reason. Then a `## Scope` block with a Qualification (`qualified` or `not qualified`), a short evidence table and one limitation line; findings graded `block`, `gap` or `info`; `## Lint`, `## Claims`, `## Citations`, and `## Validation` and `## Recovery` when they apply. It ends with `Verify status:`.

| Status | Meaning |
|---|---|
| `CONFORMS` | the records show the plan ran as approved and nothing is open |
| `CONFORMS_WITH_GAPS` | something the records cannot show: a run with no receipt, an unknown exit status, an output not tied to a run, code a linter could not check, a citation not checked, a required validation check not established |
| `DOES_NOT_CONFORM` | at least one block: a failed run, a planned script edited after its run, a failed required check, a changed pinned input, an unfixed unwaived lint finding, an `Outputs:` file written before the approval, an incomplete Snakemake job, a claim its cell contradicts, a citation that does not resolve or match |

A gap is not a failure and a pass is not a scientific judgement. Qualification is separate from status and is not a score. See [Gaps and passes](../../concepts/gaps-and-passes.md).

Exit codes: `report` and `write` exit 0 whatever the status. `--require-reportable` exits 3 when not qualified. A `verify:` error, or `py.sh` finding no Python 3.9 or later, exits 1.

## Reads

`.mycelium-extra/` approvals, approval instances, `pending/`, `receipts.jsonl`, `launches/`, `script-pins/`, `repins/`, `scripts/`, `gate-errors.jsonl`, `tools.json`; the analysis folder's code, outputs and docs; the claims blocks and citations in the analysis doc and any `--claims` document; committed `provenance/` for `stale`, `status`, `runs`, `refs`; `sacct` for Slurm jobs; the network only with `--resolve-citations`; conda `conda-meta` folders for environments. It runs scilintr on the analysis code.

## Writes

Only `write`, and only `<analysis-dir>/provenance/`: `plan-<hash>.md`, `receipts-<hash>.jsonl`, `outputs-<hash>.tsv`, `verify-<hash>.md`, `lint-<hash>.txt`, `PROVENANCE.md`, `complete-<hash>.json`; plus `validation-<hash>.json`, `env-<hash>.txt` and `pip-<hash>.txt` when they apply. Writing again for the same plan replaces its files and its row. A non-conforming result can be written too; its status is recorded with it. The script warns if git ignores the folder. See [State files](../state-files.md).

## Default on or off

On when invoked. The gate keeps the records `verify` reads whether or not you ever invoke it. In real use records exist far more often than verification does: the gate's receipts are written automatically, `write` happens only when someone asks.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| Receipts, approvals and pins that `verify` reads | Enforced: written by the gate's hooks |
| `report`, `list`, `status` and the other read-only actions never write | Enforced by the script |
| Asking you before `write` | The agent's instruction: `write` runs whenever the agent runs it, with no prompt from the gate |
| Quoting the five summary rows first, never pasting the plan or its `Plan status:` line into the reply | The agent's instruction |
| Not editing the claims block, the output or a receipt to make a check pass | The agent's instruction |

## Notes

- The agent must not paste the plan into its reply: the gate would offer it as a new plan to approve.
- Declare quotable numbers in a claims block, each naming its cell: `0.016234 | outputs/de_results.tsv padj SIGLEC1`. A value agrees when its cell, rounded to the value's last digit, equals it.
- A script the gate re-pinned after an edit and then ran is a gap; `freeze <hash>` is the way out ([Gate](../gate.md#typed-commands)).
- On Codex every receipt has exit status `unknown`, so the best status is `CONFORMS_WITH_GAPS`.
- The report lists what it cannot see: background runs, runs through MCP notebook tools, gate errors in the plan's window, and whether a script implements the plan's choices.
- Settings that affect it: [gate.json](../gate-json.md).
