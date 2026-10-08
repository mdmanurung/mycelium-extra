# Skill reference

Start with [Usage tiers](usage.md) to choose a workflow. This page is a lookup
for individual tools; you do not need to learn them all.

Commands below use Claude Code syntax. In Codex, replace `/mycelium-extra:`
with `$mycelium-extra:`. See [Host compatibility](installation.md#host-compatibility).

## Common prompts

| Need | Command |
|---|---|
| Make a plan | `/mycelium-extra:grill <your question>` |
| Enable execution checks | `/mycelium-extra:init` |
| Check a completed run | `/mycelium-extra:verify <hash>` |
| Create an analysis folder | `/mycelium-extra:new-analysis analysis/<name>: <question>` |
| Resume in a fresh session | `/mycelium-extra:handoff` |

## grill

Reads project evidence and turns your question into a sourced, numbered plan.
It asks only consequential questions you own, at most five after the opening
question. It calls `decision-status` and `data-contract-check` when needed.
It writes nothing and runs no analysis.

The brief ends with `READY`, `READY_WITH_ASSUMPTIONS`, or `DECISION_REQUIRED`.
Its `Inputs:` line identifies files the gate will pin. With the gate enabled,
use the displayed `approve plan <hash>` message to authorize covered runs.
See [Approving a plan](approval-gate.md#approving-a-plan).

## init

Turns on the approval gate for the current repository. Writes
`.mycelium-extra/gate.json` and adds `.mycelium-extra/` to `.gitignore`;
leaves an existing gate unchanged. Default paths are `analysis/**` and `nbs/**`.
See [Gate settings](approval-gate.md#settings) to change coverage.

## verify

Checks an approved plan against receipts, pinned inputs, outputs, lint, and
explicit claims. It never re-runs the analysis. Requires the approval gate
for a current plan's report; `verify stale` can read saved provenance without it.

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

### Stale plans

`verify stale` lists saved plans whose scripts, inputs, or outputs changed.
See [Staleness checks](verification.md#stale-plans).

### Overview of all plans

`verify status` shows planned, run, and verified work, with staleness and lint
coverage. See [Overview details](verification.md#overview-of-all-plans).

## new-analysis

Creates a new folder with numbered step stubs, a Snakefile, `run.sh`, an analysis
doc, one `PLAN.md`, one `TRACKER.md`, and data/output/log/report locations.
Refuses non-empty folders and missing link targets; stubs stop until implemented.

Uses `<NAME>.md` in Mycelium projects and `README.md` elsewhere. Writes only the
new folder; Mycelium's `analyze` handles manifest and memory updates.
See [Full project workflow](usage.md#tier-4-full-project-workflow).

## plan-review

Challenges a grill draft before approval. In Claude Code, Claude assembles a
minimal packet for separate Codex engineering and Biomni biomedical critiques.
It shows the packet and asks before sending it outside the machine; Biomni
uses cloud credits. Missing reviewers are reported unavailable.

Writes nothing and approves nothing. Material revisions need a new approval.
In Codex, this skill supplies the engineering critique only.
See [Host compatibility](installation.md#host-compatibility) for reviewer requirements.

## decision-status

Resolves which past Mycelium decision applies. Explicit supersession wins,
then matching scope; contested choices go to you. After confirmation, appends
a resolution to `.living/decisions.md` without editing old entries.
Usually called by `grill` when a plan depends on prior decisions.

## data-contract-check

Compares a plan's assumptions with CSV/TSV sample tables or H5AD `obs`.
Checks columns, cohort levels/counts, unique units, complete pairs, and batch
versus contrast nesting. Writes nothing. H5AD needs h5py; a missing dependency
is a gap. Never loosens the contract to make a failed check pass without agreement.
Usually called by `grill` when sample assumptions matter.

## handoff

Writes a short root `HANDOFF.md` with the goal, current state, locked decisions,
dead ends, code pointers, and one exact next action. Replaces the previous
handoff and ends with a resume prompt. A grill plan still waiting for approval is
carried word for word: `HANDOFF.md` points to the gate's stored copy (or holds the
whole brief when there is none), and the new session prints it unchanged for a
fresh approval card. Does not commit or change `.living/`.

## harden

Turns one Mycelium learning's concrete mitigation candidate into a test in the
repository's existing test setup. Demonstrates failure on a minimal reproduction
and a pass on current code. After confirmation, marks the learning's mitigation
as structural and records the test path. Leaves analysis code unchanged.
