# grill

Read-only planning before anything runs. Asks for your question in your words, searches what the repository already knows, asks only what you must decide, and returns a plan in which each consequential choice is sourced. Then it stops and waits. Guide: [Plan an analysis](../../guides/plan-an-analysis.md).

## Synopsis

`/mycelium-extra:grill <the task, as you would say it>` (Codex: `$mycelium-extra:grill`). There is no script and no flags. It also runs when you ask to scope, plan or pressure-test a task, or to promote explore runs into a plan.

## What you type, and what it does

| You type or ask | Meaning |
|---|---|
| the task | The skill first asks, in one free-text message, for your question and the claim you hope to make. It offers no drafted answers. If you decline, it goes on and records that. |
| `explain row N` | Ordinary prompt (the hook does not act on it), available any time after the plan is shown. The agent answers in at most six lines: what the step does, the choice and its source, the assumption, one alternative, and what the check would show. Read-only. |
| `explain plan` | The same prompt widened to the whole table in row order: each step, what it assumes about the rows it consumes, one alternative, and what its check would show, quoting the plan's recorded evidence verbatim. It closes with the two or three rows to check first. Read-only. |
| `challenge row N` | Same, for the strongest reason that row could be wrong and the cheapest check that would settle it; or `no strong objection found`. Read-only; a real plan change ends in an amendment draft, never an edit. |
| `socratic`, "walk me through it", "help me decide", "quiz me" | Socratic mode: one neutral probe inside each question that is yours to answer. Your answer becomes that row's Validation cell, tagged `[human-stated]`. Off unless you ask; ends on "stop socratic"; keeps no state. Reference: `skills/grill/references/socratic.md`. |
| "promote explore runs" | Lists this session's explore runs (`verify explore`, read-only) and drafts a normal plan that re-runs them without the explore prefix, with fresh `Outputs:` paths. Explore outputs are never relabelled as results. |
| "good enough" | Stops asking and writes the plan. |
| `allow explore <hash>` | Not a grill command; it is a [gate command](../gate.md#typed-commands) you type to explore inside an approved plan's scope. |

## Reads

Project instructions (`CLAUDE.md`, `AGENTS.md`); in a Mycelium repository, `.living/` decisions, learnings, findings and manifests (lookup order in `references/mycelium.md`); analysis docs, code, config; `.mycelium-extra/track-changes/<analysis>/brief.md` when the task revises an approved plan. It may run brief read-only probes (`python3 -c`, `Rscript -e`) that write nothing. For sample-table properties it uses [data-contract-check](data-contract-check.md) in its no-file form. It never runs a repository script, notebook or pipeline by path.

The librarian dossier (`references/evidence-assistance.md`) may look for evidence on a methodological question when you add it as an option: offline sources first; an external lookup only with your consent in that turn and with no project data in the query; retrieved text is treated as untrusted; no invented citations.

## Writes

Nothing. The plan is the final message. In that turn it does not execute, create analysis folders, or write to `.living/`, manifests, todo or analysis files. Decisions you confirm are listed under "Decisions to record" for the executing workflow.

## The question cap and the status line

At most five questions per grill, one per message, most consequential first, each with the evidence found and a recommended default. The opening question about your own words does not count. At the cap, the remaining user-owned points become labelled defaults that you can override at approval.

The final message ends with exactly one of:

| Status | Meaning |
|---|---|
| `Plan status: READY` | every consequential decision is sourced from the repository or from you |
| `Plan status: READY_WITH_ASSUMPTIONS` | stable plan; some choices rest on labelled, reversible defaults |
| `Plan status: DECISION_REQUIRED` | one choice of yours leads to materially different plans; options and a recommendation are given. No approval card appears. |

A status describes the plan. None grants permission to run.

## The brief and what the gate reads

| Part | Notes |
|---|---|
| quoted question and hoped-for claim | verbatim from you, or `> Question: not stated (the user declined).` |
| Objective, Evidence | each Evidence bullet ends in `[human-stated]`, `[agent-derived: <path>]` or `[agent-asserted: <source>]`; a `Facts:` count line follows |
| `Inputs:` | files the plan's validity rests on; the gate pins them when it shows the hash |
| `Outputs:` | files the runs will write; `verify` checks each was written after the approval by a run of this plan |
| plan table | the only table; columns for step, choice, source (`repo: <path>`, `user`, `default: <reason>`) and validation check |
| optional `<!-- exact-execution -->`, `<!-- validation-bindings -->` blocks | for reportable runs; syntax in `references/run-plans.md` and [Advanced features](../../advanced.md) |
| optional `<!-- plan-evidence -->` block | read-only commands and their verbatim output, one entry per fact the plan rests on; `verify` re-runs them and reports drift; syntax in `references/plan-evidence.md` |
| Assumptions and risk, Parked, Decisions to record, Next action | brief, at most 150 words outside the protected parts |

The gate reads only the plan table's Step column to decide what a plan lets through. A script named only in a Choice or Validation cell, in prose, or in Evidence approves nothing.

## Default on or off

On when invoked. Nothing in the gate depends on grill having run: any message that ends with a `Plan status:` line of `READY` or `READY_WITH_ASSUMPTIONS` gets a card.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| Approving a plan | Enforced: only your typed `approve plan <hash>` ([Gate](../gate.md#typed-commands)) |
| The hash | Enforced: the Stop hook computes and shows it. The agent must never print or guess one. |
| Read-only, no edits, no execution during grill | The agent's instruction |
| The five-question cap | The agent's instruction |
| Offline-first, same-turn consent, untrusted retrieved text | The agent's instruction; the gate's `PreToolUse` matcher does not see web or MCP tools |

## Related

[verify](verify.md) checks the run against the approved plan. [track-changes](track-changes.md) shows drift from it. [plan-review](plan-review.md) adds independent reviewers before you approve.
