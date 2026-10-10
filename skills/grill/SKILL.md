---
name: grill
description: Read-only, pre-execution planning for a proposed research, bioinformatics, analysis, or software task. Asks for the user's question in their own words, then searches the repository's accumulated knowledge (Mycelium `.living/` memory, manifests, analysis docs, code), asks only consequential questions the user must answer, and returns a step-by-step plan in which every consequential choice is sourced, then waits for approval before anything runs. Use when the user invokes mycelium-extra grill, or asks to scope, plan, or pressure-test an analysis or task before executing it, especially in a Mycelium project. Not for reviewing finished code, diffs, or completed analyses (use Mycelium's review skill or its grill mode) and not for open-ended, unbounded interviews. Also use it when the user asks to promote explore runs into a plan for a reportable re-run.
---

# Mycelium Extra: Grill

Turn a proposed task into a sourced, step-by-step plan before anything runs. Ask for the user's question first, retrieve, decide what the evidence supports, ask the user only what remains, then stop and wait for approval. Make no edits during this skill.

## 0. Ask for the question first

Before reading any file or data, and before proposing anything, ask the user in one free-text message, opening with a one- or two-sentence reminder of what the task is (restate only what the invocation, the handoff, or the user has already said, with no goal, claim, or result drafted for them), for the question in their own words and the claim they hope to make (for a software task, the goal and the result they hope for). Offer no drafted options or examples: a drafted answer anchors the user to it. If the invocation already states either part in the user's own words, quote it and ask only for the missing part; if it states both, skip the question. This question does not count toward the cap in section 3. If the user declines, go on.

## 1. Retrieve before asking

- Locate the project root and obey its instructions (`CLAUDE.md`, `AGENTS.md`, and similar).
- A repository uses Mycelium when `.living/` exists. `MYCELIUM.md` is optional: many Mycelium repositories carry only a Mycelium block in `CLAUDE.md` or `AGENTS.md`, or no guidance file at all. Partial structure is normal. Follow [references/mycelium.md](references/mycelium.md) for the lookup order, entry-ID caveats, and fallbacks.
- In another repository, use its instructions, README, docs, tests, config, and code. With no repository, use the user's supplied context and mark missing evidence.
- Search narrowly with `rg` and read excerpts; do not load whole memory histories or large data. Before stating that something is absent, run a targeted search for it.
- Check whether findings, outputs, or a prior analysis already answer the task. If they do, say so first, cite them, and make reuse versus re-run an explicit choice in the plan.
- Probe safely. Prefer file reads and `rg` (a file's header line often answers a column question). If a data property must be checked (columns, layers, dimensions, sample counts), use a brief inline read-only probe (`python3 -c`, `Rscript -e`, or heredoc stdin) that writes nothing, run with the interpreter or environment the repository documents (for example `conda run -n <env> python -c ...`). If the probe fails, do not debug it: mark the property unverified and make checking it the plan's first validation step. For sample-table properties the plan's validity rests on (cohort levels and counts, unit of replication, pairing, batch versus contrast), use the data-contract-check skill (process-substitution form only, so no file is written) instead of ad hoc probes; a blocking alert becomes a plan edit or a `DECISION_REQUIRED`. Never run a repository script, notebook, or pipeline by path during grilling: in a Mycelium repository that opens the post-action cycle, and the Stop hook then blocks until `.living/` is updated. If a Mycelium hook demands post-action updates anyway, tell the user which command tripped it and follow the hook.

## 2. Reconstruct and challenge

Keep a compact internal evidence map: claim, source/path, date or commit if material, status (`intended`, `implemented`, `observed`, `proposed`), applicability, and confidence. Distinguish current user intent from repository evidence and from your inference. A file's existence does not prove its outputs are current; a past decision does not prove the current implementation follows it.

Test only relevant axes: goal, evidence/data, assumptions, meaningful alternatives, failure modes, and validation. For scientific work, distinguish exploration, prediction, and causal or mechanistic inference, and identify the unit of analysis and obvious leakage or confounding risks. For any bioinformatics or statistical analysis, walk [references/analysis-decisions.md](references/analysis-decisions.md): every applicable decision point must appear in the plan with a source, and none may stay implicit. Then walk [references/llm-failure-modes.md](references/llm-failure-modes.md): for every applicable failure mode, the plan names a guard with a source, and never claims a `planned:` check already runs. The lists set coverage, not reading depth. A standing repository contract (for example scientific rules in `AGENTS.md` or an active convention) is valid `repo` evidence, and a point that cannot be sourced cheaply becomes a labeled default with a validation step.

Challenge a premise directly when the repository contradicts it. When a prior decision or finding rejects the design the user asked for, do not silently override either side: present the evidence, recommend the repository's position or a reconciled design, and ask if the user owns the trade-off. Do not manufacture objections or expand the scope into an exhaustive audit.

Resolve apparent conflicts by checking authority, recency, **applicability**, and whether a source explicitly supersedes another. Implementation describes what ran; conventions and decisions may describe what should run. When two or more decision entries cover a choice the plan depends on, settle them with the decision-status skill's parser and resolution rules, but write nothing: a resolution the user confirms goes in the brief's "Decisions to record".

## 3. Source every decision; gate every question

Resolve each consequential decision by the first rule that applies:

1. Repository or other available evidence settles it: cite it (`repo: <path>`).
2. A defensible technical choice exists within the project's constraints, and it does not settle something the user owns (the scientific question, the estimand, or an accepted trade-off): choose it and label it (`default: <reason>`).
3. Plausible answers would change the scientific question, data, method, interpretation, deliverable, or next action, and the user owns the choice: ask (`user`).
4. Otherwise drop it, or park it with a return condition if a later stage needs it.

Ask one question per message, the most consequential first, stating the evidence you found and a recommended default. Beyond the opening question, ask zero questions if nothing qualifies. Cap: **five questions per grill**. The cap is a circuit breaker, not a target. At the cap, turn remaining user-owned points into labeled defaults in the plan; the approval step is where the user overrides them. Do not restart a question tree or evade the cap by subdividing a question. If the user says "good enough," stop and write the plan.

## 4. Converge, brief, and wait

After each answer, check: **would plausible answers to any remaining user-owned unknown change the plan?** If not, stop. End with one status. Each status describes the plan; none grants permission to execute.

- `READY`: every consequential decision is sourced from the repository or the user.
- `READY_WITH_ASSUMPTIONS`: the plan is stable, and some decisions rest on labeled, reversible defaults the user can override at approval without re-planning.
- `DECISION_REQUIRED`: one user-owned choice leads to materially different plans (estimand, data, or deliverable), and no default is defensible without the user's intent. Give the options, a recommendation, and the consequence of each. Do not pretend the question cap resolves a blocker.

Write a brief of at most 150 words. The plan table, the quoted question, the `Inputs:`, `Outputs:`, `Facts:` and `Plan status:` lines, and the guards [references/llm-failure-modes.md](references/llm-failure-modes.md) asks for do not count, and are never cut to meet the limit: the gate pins and verify checks from them. Use one short line per section, and keep only the Evidence bullets the plan's choices rest on, but never drop one that names a failure, a flag, or an unverified fact (the approval card quotes those); the user asks for more if they need it. Scale down further for simple tasks. Open it with the user's answer from section 0, quoted verbatim:

```
> Question (user's words): "<answer>"
> Hoped-for claim: "<answer>"
```

If the user declined, write `> Question: not stated (the user declined).` instead.

- **Objective**: the question and, for scientific work, the estimand or contrast.
- **Evidence**: one bullet per fact you keep, ending in a tag saying how it was established: `[human-stated]` (the user said it), `[agent-derived: <artifact path>]` (read from a file, output, or probe), or `[agent-asserted: <source>]` (from your own knowledge; `[agent-asserted: none]` when you have no source). End the list with one count line, for example `Facts: 4 agent-derived, 1 human-stated, 1 agent-asserted (1 unsourced).` Cite file paths with sections or lines. For decisions and learnings, cite the heading title and line, not a bare positional `L-N` or `D-N`; finding IDs (`F-NNN`) are stable and can be cited with their topic file.
- **Inputs**: one line, `Inputs: <path>, <path>`, naming by repository path the files the plan's validity rests on: the sample table, config or params files, a lockfile, or a folder of raw files. Not scripts or outputs, except in a run plan, which also lists the code it freezes for a reportable run once that code is written: follow [references/run-plans.md](references/run-plans.md) when the user wants every command known and frozen at approval. Where the approval gate is enabled, it pins these files when it shows the approval hash and blocks a launch if one changes first. Write `Inputs: none` when nothing qualifies.
- **Outputs**: one line, `Outputs: <path>, <path>`, naming by repository path the files or folders the plan's runs will write: result tables, figures, `numbers.json`, or this run's own output folder (such as `results/run_20261001_dream/`, not a glob over every run's folder). Write each path in full; a `{a,b}` list is read and a `{sample}` wildcard is read as `*`, but a `…_x.csv` shorthand names no path and is flagged. mycelium-extra's verify checks that each was written after the approval by a run of this plan. Write `Outputs: none` when the plan writes nothing.
- **Plan**: a numbered table, the only table in the brief (keep Evidence as bullets). Each row gives the step, its consequential choice, the source (`repo: <path>`, `user`, or `default: <reason>`), and the validation check. In the step column, name by repository path, relative to the project root, every script, notebook, or pipeline the plan will run, including a wrapper the run goes through (such as the analysis's `run.sh`) and any figure or report script, and name `sbatch`, `snakemake`, or `nextflow` when the plan launches them. The approval gate reads only this table's Step column: a path in a Choice or Validation cell, prose, Evidence, or a `repo:` citation approves nothing, so a run named only there is denied. The approval card quotes the Step, Choice, Source and Validation cells for the user to check the science, so write the Choice and Validation cells in plain scientific terms with the numbers that would show it is right (for example `A_t pd counts 37 CLR / 29 asin`), and name every run in its Step cell, not in Choice. The card shows each step top down with bullets for its choice and who decided it, the assumption behind a `default:`, and its check, and cuts any line over 250 characters, so keep the Choice to one decision of at most about 150 characters, the `default:` reason to one short phrase, and the Validation to one check, and put each decision, assumption or check in its own step's row rather than in prose. Mark a step already done with `(done)`.
- **Assumptions and risk**: each `default` row in one line, then the key failure mode and how the plan detects it.
- **Parked**: deferred items, each with a return condition.
- **Decisions to record**: user answers and defaults the executing workflow should log (for example to `.living/decisions.md`) once work begins.
- **Next action**: approve or edit the plan, then the execution route: in a Mycelium repository, Mycelium's analyze skill (`/mycelium:analyze` in Claude Code, `$mycelium:analyze` in Codex); otherwise the repository's normal workflow.

Put the brief and the plan table in your final message, and end it with the status on its own line, exactly `Plan status: READY`, `Plan status: READY_WITH_ASSUMPTIONS`, or `Plan status: DECISION_REQUIRED`. Name every script, notebook, or pipeline the plan will run by its repository path, in the plan table. Where the mycelium-extra approval gate is enabled (`.mycelium-extra/gate.json`), its hook hashes that message and shows the user `approve plan <hash>`; never print or guess a hash yourself, and never add the gate's explore prefix to a command unless the user asks for an exploratory run.

Then stop. In this turn, do not execute, create analysis folders, or write to `.living/`, manifests, todo, or analysis files. Execution starts only after the user approves or edits the plan, and it follows the repository's normal lifecycle, carrying the approved plan and the decisions to record. Name other skills rather than assuming they can be invoked programmatically.

## Promote explore runs

When the user asks to promote explore runs (make them reportable, plan a re-run of what was explored), list them read-only:

```bash
python3 - --plugin-root <skill-dir>/../.. explore [--all] < <skill-dir>/../verify/scripts/verify.py
```

It lists this session's explore runs of gated code (`--all`: every session, last 7 days), one per distinct command with the `MYCELIUM_EXTRA_EXPLORE=1` prefix removed, the paths each ran, its exit status, conda env, and whether its script changed since. Then grill as usual (sections 0 to 4): the plan table names each script, wrapper, and command to re-run, without the prefix; ask the user which runs to keep when that is not clear. Explore outputs are not results, so the plan re-runs everything and its `Outputs:` line names fresh paths. Use [references/run-plans.md](references/run-plans.md) when the user wants the code frozen. Explore runs of inline code (`python -c`) are not listed; add them by hand if they matter.
