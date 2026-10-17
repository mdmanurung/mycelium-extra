# Usage tiers

**Start with Tier 1 if you only need a plan. Use Tier 2 for your first run.**
Each tier adds to the previous one. These are workflow choices, not settings
or pricing levels. Install the [plugin for your host](installation.md) first.

| Tier | Use it when | Add these tools |
|---|---|---|
| 1. Plan | You want to clarify a question before writing or running code | `grill` |
| 2. Run with approval | You want execution checked against your plan | `init` once, then approval |
| 3. Verify reportable work | You will use the outputs in a finding or report | `verify`, a pinned run plan |
| 4. Full project workflow | You need structure, independent review, and continuity | `new-analysis`, `plan-review`, `handoff`, `idea`, `idea-triage`, `harden`; Mycelium integration |

Examples use Claude Code's `/mycelium-extra:` prefix. In Codex, use
`$mycelium-extra:` instead. In OpenCode, mention a skill by name (for example
`@grill`), and send the same `approve plan <hash>` message; the plugin adapter
drives the gate (see [Host compatibility](installation.md#host-compatibility)).

## Tier 1: Plan

One tool: **`grill`**.

```text
/mycelium-extra:grill Plan a paired treatment-response analysis. Read the sample table and existing decisions first.
```

Answer the questions that affect the plan, then read its steps, assumptions,
and input files. Planning writes nothing and runs no analysis. When needed,
`grill` calls `decision-status` and `data-contract-check` itself; you do not
need to memorize those commands.

This tier needs no gate setup. Planning alone provides no execution receipts
or enforcement. If the repository already has a gate, its rules still apply.

## Tier 2: Run with approval

Add **`init` once per repository**, with plugin hooks enabled.

1. Invoke `/mycelium-extra:init`. Check that it covers your analysis paths.
2. Invoke `/mycelium-extra:grill <your task>`. Read the plan and `Inputs:` line.
3. Send the exact displayed `approve plan <hash>` message in the same session.
4. Run the approved steps through your usual workflow. In a Mycelium project,
   use `/mycelium:analyze <name>`.

The gate checks covered commands, blocks changed pinned inputs, and records
receipts when the post hooks fire. A revised plan needs its current hash approved.
Default gated paths are `analysis/**` and `nbs/**`; default gated commands
include `snakemake`, `sbatch`, and `nextflow`.

For setup problems, see [Installation](installation.md#troubleshooting).
For coverage, exploration, or custom settings, see [Approval gate](approval-gate.md).

## Tier 3: Verify reportable work

Add **`verify`**. For a reportable, long, or HPC run, also freeze the finished code
in a run plan before executing it.

1. Once code is written and linted, review it **before** freezing it. Ask
   Mycelium's `review` for the principal methodological and code review (in an
   ordinary repository, use your own review), and run the executable checks you
   select, such as the project's tests or `data-contract-check`. Fix what they
   find; every code edit belongs before the freeze.
2. Ask `grill` for a run plan. It revises the existing `PLAN.md`, lists scripts,
   Snakefile, and `run.sh` under `Inputs:`, and shows a dry run under the first
   plan's approval.
3. Read the revised plan and approve its displayed hash. Run the covered steps.
4. Invoke `/mycelium-extra:verify <hash>` for that run plan.
5. Read the failures and gaps. Confirm if you want the check saved under
   `<analysis>/provenance/`, then commit it with the analysis. Ask for another
   review only when `verify` leaves failures or gaps unresolved, a result needs
   a closer look, or you want a deeper review; the review before the freeze
   covered the code that ran, so repeating it after an unchanged run adds little.

| Result | Meaning |
|---|---|
| `CONFORMS` | The checked record agrees with the approved plan |
| `CONFORMS_WITH_GAPS` | Some evidence or checks are missing |
| `DOES_NOT_CONFORM` | A blocking mismatch or failure was found |

Verification checks records without re-running the analysis. Declared
`<!-- claims -->` blocks connect reported numbers to specific output cells;
a matching number does not establish scientific validity.

Codex CLI 0.160.0 receipts omit exit metadata, so run status remains a gap.
An `sbatch` receipt records submission; job outcome needs `sacct` or job logs.
See [Verification reference](verification.md) for report details and
[Run plans](../skills/grill/references/run-plans.md) for freezing code.

## Tier 4: Full project workflow

Add tools **when the project needs them**; there is no requirement to invoke
all eleven skills for every analysis.

| Need | Tool | When to use it |
|---|---|---|
| Predictable analysis structure | `new-analysis` | Before implementing a new analysis; creates stubs, workflow, plan, and tracker |
| Independent challenge | `plan-review` | Optional, after `grill` and before the first approval; revised plans return to `grill` |
| Continuity between sessions | `handoff` | Before starting a fresh session |
| Keep flow when an idea strikes | `idea` | Any time; one line, no questions |
| Choose what to work on next | `idea-triage` | Between analyses, when several ideas are waiting |
| Prevent a recurring mistake | `harden` | When a Mycelium learning names a concrete test candidate |
| Project memory, execution, code review, reports | Mycelium | Use its normal lifecycle around Extra's planning and verification; review the code before the final freeze |

`plan-review` is Claude-led for separate Codex and Biomni reviews. It requires
consent to send the packet outside the machine; Biomni uses cloud credits.
In Codex, it provides only the engineering critique. Review never approves a run.
`decision-status` and `harden` use Mycelium's learning/decision records;
ordinary repositories can still plan, gate, verify, scaffold, and hand off.

## Full analysis workflow

This shows a reportable analysis using Extra with Mycelium. **Solid arrows
show the main path; dotted arrows show optional steps or revisions.** In an
ordinary repository, use your own implementation, review, and reporting tools
in place of the `mycelium:*` commands.

```mermaid
flowchart TD
    accTitle: Full data analysis workflow with Mycelium Extra
    accDescr: Set up inputs, plan and approve, implement, review and freeze code, run, verify, review again only if triggered, report, and record project memory.
    subgraph prepare["1. Set up and plan"]
        question["Analysis question + available data"]
        setup["Install Extra; enable hooks; init once per repository"]
        inputs["mycelium:ingest or your usual data setup<br/>Register inputs and inspect the sample table"]
        folder["Use an existing analysis folder<br/>or create one with new-analysis"]
        plan["grill: read project evidence and draft a plan<br/>decision-status + data-contract-check when needed"]
        approval["You approve the displayed plan hash"]
        question --> setup --> inputs --> folder --> plan --> approval
    end

    subgraph execute["2. Implement, review, and run"]
        code["mycelium:analyze or your own tools<br/>Implement preparation, models, and plots; lint and test"]
        review["mycelium:review or your own review, before the freeze<br/>Methods and code against the approved plan; run selected checks"]
        freeze["grill: revise PLAN.md into a run plan<br/>Pin code + data; show dry run and tool versions"]
        runapproval["You approve the run plan's displayed hash"]
        run["Run preparation, models, diagnostics, and figures<br/>Use your normal runner; gate checks inputs and records receipts"]
        code --> review --> freeze --> runapproval --> run
    end

    subgraph finish["3. Check and report"]
        verify["verify: compare plan, receipts, outputs, lint, and claims<br/>Read CONFORMS, CONFORMS_WITH_GAPS, or DOES_NOT_CONFORM"]
        provenance["Confirm saving the check<br/>Commit analysis + provenance with its recorded status"]
        recheck["Targeted review, only if triggered<br/>Unresolved failures or gaps, a surprising result, or a deeper review you ask for"]
        report["mycelium:report<br/>Write findings and figures with output-backed claims"]
        memory["Mycelium's normal memory updates<br/>Record findings, decisions, learnings, and verification status"]
        verify -->|"after reading failures and gaps"| provenance --> report --> memory
        provenance -.->|"if triggered"| recheck -.-> report
    end

    approval --> code
    runapproval -.->|"frozen code or data changes: revise and reapprove"| freeze
    review -.->|"findings: fix the code and review again"| code
    run --> verify
    verify -.->|"work needs correction: revise the plan and repeat affected steps"| plan
    plan -.->|"optional, before approval"| independent["plan-review: independent critique<br/>Claude leads Codex + Biomni; review grants no approval"]
    independent -.->|"recommendations to consider"| plan
    code -.->|"pause at any stage"| handoff["handoff: capture current state and the next action"]
    memory -.->|"a learning has a concrete test candidate"| harden["harden: demonstrate a failing reproduction<br/>and a passing regression test"]
```

The first approval covers implementation and test runs; the second freezes
finished code for the reportable run. Once a script has run under an approval,
an edit to it needs that plan approved again (see [Pinned scripts](approval-gate.md#pinned-scripts)),
so use `allow explore` for a debugging loop. Dry runs still need approval. Use one
`PLAN.md`, revised in place, and record revisions in `TRACKER.md`.

Verification reports missing evidence separately from failures; saving provenance
does not turn a gap or failure into a pass. It checks the execution record, while
code review assesses methods and interpretation, which is why the principal review
comes before the freeze and verification does not replace it. If the final report introduces
new or changed claims, run `verify` again with that document included before
sharing it. See [Verification reference](verification.md#what-the-report-shows).

### Two checkpoints

Both are your approval of a displayed plan hash. They approve different things,
and the gate checks only part of each.

| | Scientific intent approval | Final execution freeze |
|---|---|---|
| You approve | The question, the choices and their sources, the steps, and the inputs | The finished code and data exactly as they will run |
| When | After `grill`, before implementation | After implementation, lint, review, and checks, before the reportable run |
| Checked mechanically today | The approved hash is tied to the plan text; covered commands are denied until it is approved; `Inputs:` files are pinned when the hash is shown; a script is pinned at its first covered run; receipts are recorded | Files listed under `Inputs:` (scripts, Snakefile, `run.sh`, data) are pinned when the hash is shown, and a launch after any of them changes is blocked until the revised plan is approved; receipts are recorded |
| Instructional only | That each choice is sourced and the plan complete (`grill`); that independent critique happened (`plan-review`) | That the code is finished and lint-clean, that the principal review and selected checks ran and their findings were fixed, and that the dry run and tool versions are in the plan (`grill`'s run-plan instructions) |

The gate does not check that a review happened or that a test passed, and no test
or review result is tied to an approval. After the run, `verify` compares the
execution record with the plan; it does not re-run tests or review the methods.
See [Approval gate](approval-gate.md#pinned-scripts) and the
[run-plan reference](../skills/grill/references/run-plans.md).

Debugging inside an approved scope needs no second interview. After the first
checkpoint, `allow explore <plan hash>` lets the agent fix and re-run code on the
plan's own analysis paths with the exploration prefix, as often as needed, without
a new approval; a run outside those paths is denied and you decide. Changing a
pinned test or expectation, or running a frozen step with other arguments, is
reported to you, and the reportable run then needs the second checkpoint again.
Plain `allow explore` stays the broader, session-wide grant. See
[Exploratory runs](approval-gate.md#exploratory-runs).

`handoff` can be used at any pause. `harden` is for a specific recurring mistake,
not a mandatory finishing step. See [Skill reference](skills.md) for each tool's
writes and [Mycelium integration](mycelium-integration.md) for ownership.
