---
name: grill
description: Read-only planning: turn a research, analysis, or software task into a sourced step-by-step plan and wait for approval before anything runs. Use to scope, plan, pressure-test, or promote explore runs; not for reviewing finished code or results (use Mycelium's review).
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
- When the task revises an approved plan, read the `track-changes` review brief (what changed against the approved intent) instead of re-deriving the changes, and treat its Unknown lines as open. It sits at `.mycelium-extra/track-changes/<analysis path with `/` written as `__`>/brief.md`: a folder name two analyses share gets a `-<hash>` suffix, and `track-changes` prints the folder it wrote. Check its second line, `Snapshot <time> · original plan <hash> · current plan <hash>`: use it only when `current plan` is the plan you are revising and the snapshot time is later than that plan's approval; otherwise it predates the plan, so run `track-changes` again before relying on it.
- Check whether findings, outputs, or a prior analysis already answer the task. If they do, say so first, cite them, and make reuse versus re-run an explicit choice in the plan.
- Probe safely. Prefer file reads and `rg` (a file's header line often answers a column question). If a data property must be checked (columns, layers, dimensions, sample counts), use a brief inline read-only probe (`python3 -c`, `Rscript -e`, or heredoc stdin) that writes nothing, run with the interpreter or environment the repository documents (for example `conda run -n <env> python -c ...`). If the probe fails, do not debug it: mark the property unverified and make checking it the plan's first validation step. For sample-table properties the plan's validity rests on (cohort levels and counts, unit of replication, pairing, batch versus contrast), use the data-contract-check skill (process-substitution form only, so no file is written) instead of ad hoc probes; a blocking alert becomes a plan edit or a `DECISION_REQUIRED`. When the plan rests on a metadata table nobody has opened, you may also offer its optional descriptive profile (`data-contract-check --profile-only`): it describes, it is not a check, and no expectation may be taken from it. Never run a repository script, notebook, or pipeline by path during grilling: in a Mycelium repository that opens the post-action cycle, and the Stop hook then blocks until `.living/` is updated. If a Mycelium hook demands post-action updates anyway, tell the user which command tripped it and follow the hook.

## 2. Reconstruct and challenge

For analysis work, read [../plot-first/SKILL.md](../plot-first/SKILL.md). Make plots the primary interpretive outputs. Carry each question's figure path, source data, and visual check into the existing plan; use tables only with a stated fallback reason. This remains read-only and adds no interview questions.

For scientific and statistical work, use [references/scientific-conventions.md](references/scientific-conventions.md) **after** obtaining the user's question and retrieving project evidence. Identify only *activated* domain guidance, selectively read its relevant sections, and carry consequential scientific rules, exceptions, sources, and falsifiable checks into the existing plan. Never mistake a convention for proof that a dataset or implementation satisfies it. This adds no interview questions, approval authority, execution, or external retrieval.

Keep a compact internal evidence map: claim, source/path, date or commit if material, status (`intended`, `implemented`, `observed`, `proposed`), applicability, and confidence. Distinguish current user intent from repository evidence and from your inference. A file's existence does not prove its outputs are current; a past decision does not prove the current implementation follows it.

Test only relevant axes: goal, evidence/data, assumptions, meaningful alternatives, failure modes, and validation. When the plan is blocked — a decision point that will not resolve from the repository, or a claim whose discriminating check cannot yet be written — work it with [references/polya-heuristics.md](references/polya-heuristics.md), which backward-chains claim to estimand to replication unit to check and applies five selective heuristics; it adds plan rows, never questions. For scientific work, distinguish exploration, prediction, and causal or mechanistic inference, and identify the unit of analysis and obvious leakage or confounding risks. For any bioinformatics or statistical analysis, walk [references/analysis-decisions.md](references/analysis-decisions.md): every applicable decision point must appear in the plan with a source, and none may stay implicit. Then walk [references/llm-failure-modes.md](references/llm-failure-modes.md): for every applicable failure mode, the plan names a guard with a source, and never claims a `planned:` check already runs. The lists set coverage, not reading depth. A standing repository contract (for example scientific rules in `AGENTS.md` or an active convention) is valid `repo` evidence, and a point that cannot be sourced cheaply becomes a labeled default with a validation step.

Challenge a premise directly when the repository contradicts it. When a prior decision or finding rejects the design the user asked for, do not silently override either side: present the evidence, recommend the repository's position or a reconciled design, and ask if the user owns the trade-off. Do not manufacture objections or expand the scope into an exhaustive audit.

Resolve apparent conflicts by checking authority, recency, **applicability**, and whether a source explicitly supersedes another. Implementation describes what ran; conventions and decisions may describe what should run. When two or more decision entries cover a choice the plan depends on, settle them with the decision-status skill's parser and resolution rules, but write nothing: a resolution the user confirms goes in the brief's "Decisions to record".

## 3. Source every decision; gate every question

Resolve each consequential decision by the first rule that applies:

1. Repository or other available evidence settles it: cite it (`repo: <path>`).
2. A defensible technical choice exists within the project's constraints, and it does not settle something the user owns (the scientific question, the estimand, or an accepted trade-off): choose it and label it (`default: <reason>`).
3. Plausible answers would change the scientific question, data, method, interpretation, deliverable, or next action, and the user owns the choice: ask (`user`). When such a methodological question has no repository evidence, the question may add an evidence lookup as one option; follow [references/evidence-assistance.md](references/evidence-assistance.md). When the user asks for Socratic mode, or types `explain row N`, `explain plan` or `challenge row N`, follow [references/socratic.md](references/socratic.md); all are read-only and off by default.
4. Otherwise drop it, or park it with a return condition if a later stage needs it.

Ask in **rounds**. A round holds every `user` question whose prerequisites are already settled, most consequential first; a question whose answer depends on another question still open waits for the next round. Number them `Q1`, `Q2`, ... and give each: the evidence you found, the options, and a `Recommended:` line worded so that "yes" accepts it. The user answers by number. After the answers, recompute the frontier and ask the next round; stop when no user-owned unknown would change the plan. Beyond the opening question, ask zero questions if nothing qualifies. Cap: **five questions per grill**, counted across rounds, not per round. The cap is a circuit breaker, not a target. At the cap, turn remaining user-owned points into labeled defaults in the plan; the approval step is where the user overrides them. Do not restart a question tree or evade the cap by subdividing a question. If the user says "good enough," stop and write the plan. If the user says "one question at a time," ask one per message for the rest of the grill.

A round looks like this (one probe per question when Socratic mode is on, placed after the evidence):

```
**Q1. <title>**
Evidence: <what the repository says, with paths>
Options: (a) ... (b) ...
Recommended: (a), because <reason>

**Q2. <title>**
...
```

## 4. Converge, brief, and wait

After each answer, check: **would plausible answers to any remaining user-owned unknown change the plan?** If not, stop. End with one status. Each status describes the plan; none grants permission to execute.

- `READY`: every consequential decision is sourced from the repository or the user.
- `READY_WITH_ASSUMPTIONS`: the plan is stable, and some decisions rest on labeled, reversible defaults the user can override at approval without re-planning.
- `DECISION_REQUIRED`: one user-owned choice leads to materially different plans (estimand, data, or deliverable), and no default is defensible without the user's intent. Give the options, a recommendation, and the consequence of each. Do not pretend the question cap resolves a blocker.

Write a brief of at most 150 words. The plan table, the quoted question, the `Inputs:`, `Outputs:`, `Facts:` and `Plan status:` lines, a `<!-- plan-evidence -->` block, and the guards [references/llm-failure-modes.md](references/llm-failure-modes.md) asks for do not count, and are never cut to meet the limit: the gate pins and verify checks from them. Open it with the user's answer from section 0, quoted verbatim:

```
> Question (user's words): "<answer>"
> Hoped-for claim: "<answer>"
```

If the user declined, write `> Question: not stated (the user declined).` instead.

Then the sections below, in order. The rules for each (what qualifies, how to cite, how the approval card quotes a row, what the gate and verify read) are in [references/brief-format.md](references/brief-format.md); follow it when writing the brief.

- **Objective**: the question and, for scientific work, the estimand or contrast.
- **Evidence**: one bullet per fact you keep, each ending in a tag saying how it was established: `[human-stated]`, `[agent-derived: <artifact path>]`, or `[agent-asserted: <source>]` (`[agent-asserted: none]` with no source), then one count line, for example `Facts: 4 agent-derived, 1 human-stated, 1 agent-asserted (1 unsourced).` Keep the bullets the plan's choices rest on, and always one that names a failure, a flag, or an unverified fact: the approval card quotes those.
- **Inputs**: one line, `Inputs: <path>, <path>`, the files the plan's validity rests on (`Inputs: none` when nothing qualifies). The gate pins them at approval. A run plan also lists the code it freezes: [references/run-plans.md](references/run-plans.md).
- **Outputs**: one line, `Outputs: <path>, <path>`, the files or folders the plan's runs will write, each path in full (`Outputs: none` when the plan writes nothing). Verify checks each was written by a run of this plan.
- **Plan**: a numbered table, the only table in the brief, one row per step: Step, Choice, Source (`repo: <path>`, `user`, or `default: <reason>`), Validation. The Step cell names by repository path every script, notebook, pipeline, wrapper and launcher (`sbatch`, `snakemake`, `nextflow`) the plan runs: the gate grants runs from this column alone. Choice and Validation are one decision and one check in plain scientific terms; the card quotes them. Mark a finished step `(done)`.
- **Run blocks (optional)**: `<!-- exact-execution {...} -->` and `<!-- validation-bindings {...} -->` for a reportable run, per [references/run-plans.md](references/run-plans.md).
- **Plan evidence (optional)**: a `<!-- plan-evidence {...} -->` block per [references/plan-evidence.md](references/plan-evidence.md), whenever at least two Evidence bullets rest on a file read; JSON in a comment, never a table.
- **Assumptions and risk**: each `default` row in one line, then the key failure mode and how the plan detects it.
- **Parked**: deferred items, each with a return condition.
- **Decisions to record**: user answers and defaults the executing workflow should log once work begins.
- **Next action**: approve or edit the plan, then the execution route: Mycelium's analyze skill in a Mycelium repository, otherwise the repository's normal workflow.

Put the brief and the plan table in your final message, and end it with the status on its own line, exactly `Plan status: READY`, `Plan status: READY_WITH_ASSUMPTIONS`, or `Plan status: DECISION_REQUIRED`. Where the mycelium-extra approval gate is enabled (`.mycelium-extra/gate.json`), its hook hashes that message and shows the user `approve plan <hash>`; never print or guess a hash yourself, and never add the gate's explore prefix to a command unless the user asks for an exploratory run.

Then stop. In this turn, do not execute, create analysis folders, or write to `.living/`, manifests, todo, or analysis files. Execution starts only after the user approves or edits the plan, and it follows the repository's normal lifecycle, carrying the approved plan and the decisions to record. Name other skills rather than assuming they can be invoked programmatically.

## Resume, debug, freeze

Use the same skill for all three; there is no second questionnaire. Resuming or debugging an approved plan: restate the user's already stated question and claim (section 0), and ask only about a choice that is consequential and still unresolved; do not re-ask what the approved plan, a decision entry, or the user has settled. Debugging inside the approved scope needs no new plan: the user can type `allow explore <plan hash>` for exploration bounded to that plan's analysis paths. Freezing: when a protected test or expectation, or a frozen step's arguments, must change, or the user wants a reportable run, write the revised run plan (see [references/run-plans.md](references/run-plans.md)) with fresh `Outputs:` paths for approval. Explore outputs are never relabelled as results.

## Promote explore runs

When the user asks to promote explore runs (make them reportable, plan a re-run of what was explored), list them read-only:

```bash
sh <skill-dir>/../../hooks/py.sh - --plugin-root <skill-dir>/../.. explore [--session ID | --all] < <skill-dir>/../verify/scripts/verify.py
```

It lists this session's explore runs of gated code (the session comes from `$CLAUDE_CODE_SESSION_ID`, or `--session ID`; where neither is set, as in Codex and OpenCode, it lists every session of the last 7 days, as `--all` does), one per distinct command with the `MYCELIUM_EXTRA_EXPLORE=1` prefix removed, the paths each ran, its exit status, conda env, and whether its script changed since. Then grill as usual (sections 0 to 4): the plan table names each script, wrapper, and command to re-run, without the prefix; ask the user which runs to keep when that is not clear. Explore outputs are not results, so the plan re-runs everything and its `Outputs:` line names fresh paths. Promotion needs an approved rerun with fresh output identity: `verify` reports an output written by an explore attempt and not re-observed under a matched approved attempt as `not re-run under approval`, never relabelled. The listing also shows each attempt (failed ones too) with its code version and scope. Use [references/run-plans.md](references/run-plans.md) when the user wants the code frozen. Explore runs of inline code (`python -c`) are not listed; add them by hand if they matter.
