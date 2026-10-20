# Mycelium Extra

## Introduction

**Plan an analysis. Approve what runs. Check the execution record.**

Mycelium Extra reads your repository, helps you make a sourced plan, and can
check covered runs against that plan. The approval gate catches execution
mistakes: a covered run that was never approved is denied, and anything it could
not check is shown as a gap, never as a pass. It is not a security boundary: the
"ask first" steps in the skills are instructions to the agent, not rules the gate
enforces. It works in Claude Code, Codex, and OpenCode,
alongside
[Mycelium](https://github.com/arjunrajlaboratory/mycelium) or in an ordinary repository.

The skills, from planning to hand-off:

- `grill` turns your question into a sourced plan. It can search for evidence
  like a librarian, ask one neutral Socratic question per decision you own, and
  answer `explain row N` or `challenge row N`, all read-only.
- `init` and `approve plan <hash>` turn on execution checks, input pins, and run receipts.
- `verify` checks what ran against the approved plan and writes provenance after you confirm.
- `focus` and `track-changes` say which analysis a session works on and show what changed against the approved plan.
- `new-analysis`, `plan-review`, `handoff`, `harden`, `idea`, `idea-triage`,
  `decision-status` and `data-contract-check` cover structure, review, continuity, and checks.

Five of these are built around Mycelium's files: `decision-status` and `harden`
read `.living/` memory and stop when it is absent; `idea` and `idea-triage` read
and write the `todo/` registry in Mycelium's format (they create it when it is
absent); `new-analysis` writes Mycelium's analysis doc (a bundled copy serves a
plain repository). The other skills work in an ordinary repository; with no
`.living/`, `grill`, `plan-review`, `verify` and `track-changes` have less to
read and say so.

## Installation

Pick your host; full steps, updates, and requirements (Python 3.9 or later) are in
[Installation](docs/installation.md).

```bash
# Claude Code
claude plugin marketplace add mdmanurung/mycelium-extra
claude plugin install mycelium-extra@mycelium-extra

# Codex (CLI 0.160.0 or later; enable and trust the plugin hooks afterwards)
codex plugin marketplace add mdmanurung/mycelium-extra
codex plugin add mycelium-extra@mycelium-extra
```

OpenCode points its `skills` and `plugins` settings at a checkout; see
[OpenCode](docs/installation.md#opencode).

## Input Data

### Your repository

Grill reads what the project already holds: its instructions (`CLAUDE.md`,
`AGENTS.md`), README, docs, code, and, when the repository uses Mycelium,
`.living/` decisions and findings. Mycelium is optional; with no repository,
grill uses the context you give it and marks what is missing.
See [Mycelium integration](docs/mycelium-integration.md) for what is read and what is never written.

### Your question and the files it rests on

Grill first asks for your question and the claim you hope to make, in your own
words. The plan it writes names the input files the result depends on (an
`Inputs:` line). With the gate on, those files are pinned when you approve, and
a change before the run is reported.

## User Guide

Each tier adds to the previous one; use only what your task needs.

| Tier | Tools | What you get |
|---|---|---|
| 1. Plan | `grill` | A sourced plan; no analysis runs or file writes |
| 2. Run with approval | Add `init` and `approve plan <hash>` | Covered execution checks, input pins, receipts |
| 3. Verify reportable work | Add a pinned run plan and `verify` | Checks against the approved plan; provenance after confirmation |
| 4. Full project workflow | Add scaffolding, independent review, handoff, hardening, Mycelium | Structure, continuity, and checks for recurring mistakes |

Commands below use Claude Code syntax. In Codex, replace `/mycelium-extra:`
with `$mycelium-extra:`. In OpenCode, the same `/mycelium-extra:grill` commands
work (mentioning `@grill` also works).

### Plan and approve a run

```text
/mycelium-extra:init                         # once per repository
/mycelium-extra:grill <your analysis question>
approve                                      # or approve plan <hash>
```

Bare `approve` works when the plan shown last is the only one waiting; otherwise
it approves nothing and lists the hashes. Run the approved steps through your
normal workflow. Edit the plan's scripts freely: the gate re-pins each edit with a notice.

### Be better informed before you approve

Ask grill for the evidence lookup in a question: you get what was searched, what
was found and not found, the alternatives, and the decision left to you. Say
`socratic` for one neutral probe per question. After the plan is shown, type
`explain row N` or `challenge row N` for a short, read-only answer. None of these
approves, edits, or counts toward grill's five questions.

### Verify, freeze, and report

```text
/mycelium-extra:verify <hash>                # what ran against the plan; provenance after you confirm
freeze <hash>                                # review the code once before a reportable run
```

For HPC work, a [run plan](skills/grill/references/run-plans.md) also freezes the exact commands.
Codex CLI 0.160.0 receipts lack exit metadata; verification reports that gap.
Independent Codex + Biomni review is led from Claude Code or OpenCode; in
Codex, `plan-review` provides the engineering critique only.

### Stay oriented

```text
focus <folder>                               # say which analysis this session works on
/mycelium-extra:track-changes                # what changed against the approved plan
/mycelium-extra:handoff                      # resume in a fresh session
```

For historical orientation, add `--journal` to track-changes. Its overview keeps
saved conformity and qualification separate and shows coverage before the event
history. Add `--save-checkpoint` only when you explicitly want a durable
observation; commit the checkpoint with the analysis. Confirmed verify saves also
include a portable evidence-handoff JSON. See [Journal and checkpoints](docs/focus-and-track-changes.md#historical-journal-and-durable-checkpoints).

### Learn more

- **Start:** [What it is](docs/start/what-it-is.md), [Installation](docs/installation.md), and
  [your first plan](docs/start/first-plan.md). [A worked example](docs/example.md) shows the real
  output of each step, and [A day with Mycelium Extra](docs/day.md) walks through a full working day.
  [Usage tiers](docs/usage.md) has the commands and the full analysis workflow diagram.
- **Guides by task:** [plan an analysis](docs/guides/plan-an-analysis.md),
  [approve and run](docs/guides/approve-and-run.md),
  [verify and record provenance](docs/guides/verify-and-provenance.md),
  [amend, freeze, re-scope](docs/guides/amend-freeze-rescope.md),
  [stay oriented](docs/guides/stay-oriented.md), [hand off](docs/guides/hand-off.md),
  [second-model review](docs/guides/second-model-review.md),
  [harden against repeats](docs/guides/harden-against-repeats.md), and
  [with Mycelium or in a plain repo](docs/guides/with-mycelium-or-plain-repo.md).
- **Reference:** the [reference index](docs/reference/index.md), the [skill index](docs/skills.md),
  [gate decisions](docs/reference/gate.md), [`gate.json`](docs/reference/gate-json.md),
  [state files](docs/reference/state-files.md), the [approval gate](docs/approval-gate.md),
  [verification](docs/verification.md), [advanced features](docs/advanced.md),
  [focus and track changes](docs/focus-and-track-changes.md), and
  [Mycelium integration](docs/mycelium-integration.md).
- **Concepts:** [the control model](docs/concepts/control-model.md),
  [gaps and passes](docs/concepts/gaps-and-passes.md), and
  [what is not guaranteed](docs/concepts/not-guaranteed.md).
- **Development:** [Development](docs/development.md) (tests, release steps), and
  [Decisions](docs/decisions.md) (choices that still bind, and dead ends not to redo).
- The [documentation website](https://mdmanurung.github.io/mycelium-extra/).

## License

MIT, see [LICENSE](LICENSE). The bundled analysis template retains Mycelium's
MIT notice in [MYCELIUM_LICENSE](skills/new-analysis/templates/MYCELIUM_LICENSE).
See [Mycelium integration](docs/mycelium-integration.md) for reused ideas and formats.
