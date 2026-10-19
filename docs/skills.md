# Skill reference

Start with [Usage tiers](usage.md) to choose a workflow. This page is a lookup
for individual tools; you do not need to learn them all.

Commands below use Claude Code syntax. In Codex, replace `/mycelium-extra:`
with `$mycelium-extra:`. In OpenCode, use the same `/mycelium-extra:` commands
(`@grill` also works) and send `approve plan <hash>` the same way; the plugin
adapter handles it. See [Host compatibility](installation.md#host-compatibility).

## Common prompts

| Need | Command |
|---|---|
| Make a plan | `/mycelium-extra:grill <your question>` |
| Enable execution checks | `/mycelium-extra:init` |
| Check a completed run | `/mycelium-extra:verify <hash>` |
| Create an analysis folder | `/mycelium-extra:new-analysis analysis/<name>: <question>` |
| Resume in a fresh session | `/mycelium-extra:handoff` |
| Say which analysis this session works on | type `focus <folder>` |
| See what changed against the approved plan | `/mycelium-extra:track-changes` |
| Park a passing idea | `/mycelium-extra:idea <idea>` |
| Choose the next idea | `/mycelium-extra:idea-triage` |

## grill

Reads project evidence and turns your question into a sourced, numbered plan.
It asks only consequential questions you own, at most five after the opening
question. It calls `decision-status` and `data-contract-check` when needed.
It writes nothing and runs no analysis.

To be better informed before you approve, ask for the evidence lookup in a
question (a librarian-style dossier: what was searched, what was found, what
was not, the alternatives, and the decision left to you). Say `socratic` to get
one neutral probe per question ("what result would make you drop this?"); your
answer becomes the row's check. After the plan is shown, type `explain row N`
or `challenge row N` for a short, read-only answer. None of these approves,
edits, or counts toward the five questions.

The brief ends with `READY`, `READY_WITH_ASSUMPTIONS`, or `DECISION_REQUIRED`.
Its `Inputs:` line identifies files the gate will pin. With the gate enabled,
use the displayed `approve plan <hash>` message to authorize covered runs.
See [Approving a plan](approval-gate.md#approving-a-plan).

## init

Turns on the approval gate for the current repository. Writes
`.mycelium-extra/gate.json` and adds `.mycelium-extra/` to `.gitignore`;
leaves an existing gate unchanged. Default paths are `analysis/**` and `nbs/**`.
See [Gate settings](approval-gate.md#settings) to change coverage.
`init` shows the effective config with every `gate.json` key at its real default.

Flags of the script (`gate_init.py`, run through `hooks/py.sh` from stdin; the skill does this for you):

- `--paths GLOB ...`, `--commands CMD ...`, `--hours N`: write those values into a new `gate.json` instead of the defaults.
- `--dry-run`: say what would be created and change nothing.
- `--tools [--scilintr PATH] [--rscript PATH]`: record where the linters are (`.mycelium-extra/tools.json`).
- `--diagnose`: read-only report of the effective config (invalid values flagged), hook registrations, Mycelium version, which optional tools are present, and the last receipt and gate error.

## verify

Checks an approved plan against receipts, pinned inputs, outputs, lint, and
explicit claims. It never re-runs the analysis. Requires the approval gate
for a current plan's report; `verify stale`, `status` and `runs` can read saved
provenance without it. Other subcommands (`list`, `diff`, `multiplicity`,
`explore`, `disclose`, `--resolve-citations` and `--require-reportable`) are described in
[Verification reference](verification.md); `stale`, `status`, `diff` and `runs` are in
[Advanced features](advanced.md#verify-features).

### What the report shows

Planned scripts and their run evidence, changed inputs, output attribution,
lint findings, and whether declared claims match saved output cells.
See [Report details](verification.md#what-the-report-shows).

### Status

`CONFORMS` means the checked record agrees; `CONFORMS_WITH_GAPS` means evidence
is missing; `DOES_NOT_CONFORM` means a blocking mismatch or failure was found.
A missing check never counts as clean. See [Status details](verification.md#status).

### What it writes

After confirmation, saves the frozen plan, receipts, output inventory, lint,
environment records where available, and report under `<analysis>/provenance/`.
See [Provenance files](verification.md#what-it-writes).

## new-analysis

Creates a new folder with numbered step stubs, a Snakefile, `run.sh`, an analysis
doc, one `PLAN.md`, one `TRACKER.md`, and data/output/log/report locations.
Refuses non-empty folders and missing link targets; stubs stop until implemented.

Uses `<NAME>.md` in Mycelium projects and `README.md` elsewhere. Writes only the
new folder; Mycelium's `analyze` handles manifest and memory updates.
See [Full project workflow](usage.md#tier-4-full-project-workflow).

## plan-review

Challenges a grill draft before approval. In Claude Code or OpenCode, the host
assembles a minimal packet for separate Codex engineering and Biomni biomedical critiques.
Before anything leaves the machine it runs a pre-send check and asks you to type `send packet <digest>`; Biomni uses cloud credits. The check and the consent mechanics are in [Advanced features](advanced.md#plan-review-packets-and-consent). Missing reviewers are reported unavailable.

It also runs `scripts/default_reasons.py` on the plan table: it names each row whose `default:` has no reason, a reason under three words, or only an empty phrase. It is advisory and does not judge whether a reason is correct; `verify` runs the same check on the frozen plan.

Writes nothing and approves nothing (apart from the prepared packet folder the send
route needs). Material revisions need a new approval.
In Codex, this skill supplies the engineering critique only.
See [Host compatibility](installation.md#host-compatibility) for reviewer requirements.

## decision-status

Resolves which past Mycelium decision applies. Explicit supersession wins,
then matching scope; contested choices go to you. After confirmation, appends
a resolution to `.living/decisions.md` without editing old entries.
Usually called by `grill` when a plan depends on prior decisions.

## data-contract-check

Compares a plan's assumptions with CSV/TSV sample tables or H5AD `obs`.
Writes nothing. The nine check kinds:

| Kind | What it checks |
|---|---|
| `schema` | the named columns exist |
| `cohort` | required levels present, row counts, no missing values in named columns |
| `unit_of_replication` | units per group and per group-by-within cell |
| `pairing` | every unit observed at every `within` level |
| `batch_confounding` | contrast fully nested in batch, or levels sharing no batch |
| `unique_key` | the named columns are nonempty and their combination is unique |
| `sample_alignment` | the table's sample keys match a declared sample sheet |
| `identifiers` | identifiers are unique and found in a declared namespace file |
| `h5ad_layer` | properties of an `.h5ad` matrix (non-negative, integer-valued, maximum) |

`--result-json PATH` also writes a machine-readable result (`mycelium-extra.contract_result.v1`).
Contract syntax is in the skill's `SKILL.md`. H5AD needs h5py; a missing dependency
is a gap. Never loosens the contract to make a failed check pass without agreement.
Usually called by `grill` when sample assumptions matter.

## focus

Typed commands, answered by the gate: `focus <folder>` (under `analysis/` or `nbs/`, or your
`gated_paths`), `focus status`, `focus switch <folder>`, `focus end`, and `focus <folder> plan <hash>` to
note which approved plan states the original intent. A focus belongs to one session,
is advisory (no run, approval or pin follows from it), and is never restored in a new
session. `/mycelium-extra:focus` explains it and lists the folders. See
[Focus and track changes](focus-and-track-changes.md).

## track-changes

Read-only. Shows, for one analysis, plan changes between the original and current
approved plans, scripts edited since each approval (with diffs), the gate's run
records, declared outputs older than the code, and, from a Claude Code transcript,
direct edits to other analyses. Prints a short card and writes `brief.md` and an
offline `report.html` under `.mycelium-extra/track-changes/`. Approves, freezes and
runs nothing; lists what it did not observe. `--no-write` prints the card and writes no
files; `--explain <item_id>` shows the evidence for one card item. See
[Focus and track changes](focus-and-track-changes.md).

## handoff

Writes a short root `HANDOFF.md` with the goal, current state, locked decisions,
dead ends, code pointers, and one exact next action. Replaces the previous
handoff and ends with a resume prompt. A grill plan still waiting for approval is
carried word for word: `HANDOFF.md` points to the gate's stored copy (or holds the
whole brief when there is none), and the new session prints it unchanged for a
fresh approval card. Does not commit or change `.living/`.

## idea

Parks a passing idea without a question, so the main work keeps its flow. Writes
`todo/<slug>.md` and one `todo/TODO_REGISTRY.md` row (priority `idea`, status
`open`) in Mycelium's todo format, then replies with one line. Uses your words as
written. Writes only under `todo/`: no code runs, and a plan waiting for approval
stays approvable. If the registry write fails, rerun the same command with `--recover` instead of `--text-file`: it finishes the pending capture without creating a second item. Mycelium's own `todo-idea` mode asks up to six questions first;
`idea` is the no-question path into the same registry.

## idea-triage

Ranks the open ideas in `todo/` so you can choose the next one. Each idea gets a
pitch, two impact ratings, the number of things that must go right, its riskiest
assumption (1 to 5) with months to test, a search of existing findings, and red
flags; the top idea gets a cheapest go/no-go test. It shows a ranked table with a
`park all` option and waits. After you pick, it records the triage in the item file
and marks the pick `in-progress`; it offers `grill` but does not start it. Based on
Fischbach and Walsh (2024), *Cell*.

## harden

Turns one Mycelium learning's concrete mitigation candidate into a test in the
repository's existing test setup. Demonstrates failure on a minimal reproduction
and a pass on current code. After confirmation, marks the learning's mitigation
as structural and records the test path. Leaves analysis code unchanged.
