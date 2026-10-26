# The brief: section rules, tags, and what the gate and verify read

`SKILL.md` section 4 lists the brief's sections in order. This file holds the rules for each: what qualifies, how to tag and cite, how the approval card quotes a row, and which markers the gate and `verify` parse. Nothing here parses `SKILL.md`; the hooks read the brief the agent writes, so the markers below are the contract.

## Length

At most 150 words, and scale down further for a simple task. Outside the limit, and never cut to meet it: the plan table, the quoted question, the `Inputs:`, `Outputs:`, `Facts:` and `Plan status:` lines, a `<!-- plan-evidence -->` block, and the guards [llm-failure-modes.md](llm-failure-modes.md) asks for. The gate pins and `verify` checks from those parts. Use one short line per section. Keep only the Evidence bullets the plan's choices rest on, and always one that names a failure, a flag, or an unverified fact: the approval card quotes those. The user asks for more if they need it.

## Quoted question

The first lines are the user's section-0 answer, verbatim:

```
> Question (user's words): "<answer>"
> Hoped-for claim: "<answer>"
```

If the user declined, write `> Question: not stated (the user declined).` instead. The gate reads the `> Question` line for the approval card.

## Objective

The question and, for scientific work, the estimand or contrast. `verify` reads the Objective line into the provenance record.

## Evidence

One bullet per fact you keep. Each ends in a tag saying how it was established:

- `[human-stated]`: the user said it.
- `[agent-derived: <artifact path>]`: read from a file, output, or probe.
- `[agent-asserted: <source>]`: from your own knowledge; `[agent-asserted: none]` when you have no source.

End the list with one count line, for example `Facts: 4 agent-derived, 1 human-stated, 1 agent-asserted (1 unsourced).` The tag ends the bullet, and `Facts:` starts a line: the gate and `verify` match both by position.

Cite file paths with sections or lines. For decisions and learnings, cite the heading title and line, never a bare positional `L-N` or `D-N`; finding IDs (`F-NNN`) are stable and can be cited with their topic file.

## Inputs

One line, `Inputs: <path>, <path>`, naming by repository path the files the plan's validity rests on: the sample table, config or params files, a lockfile, or a folder of raw files. Scripts and outputs stay out, except in a run plan, which also lists the code it freezes for a reportable run once that code is written: follow [run-plans.md](run-plans.md) when the user wants every command known and frozen at approval. Where the approval gate is enabled, it pins these files when it shows the approval hash and blocks a launch if one changes first. Write `Inputs: none` when nothing qualifies.

## Outputs

One line, `Outputs: <path>, <path>`, naming by repository path the files or folders the plan's runs will write: result tables, figures, `numbers.json`, or this run's own output folder (such as `results/run_20261001_dream/`, rather than a glob over every run's folder). Write each path in full: a `{a,b}` list is read, a `{sample}` wildcard is read as `*`, and a `…_x.csv` shorthand names no path and is flagged. `verify` checks that each was written after the approval by a run of this plan. Write `Outputs: none` when the plan writes nothing.

Before writing the line, look for each path. If one already exists, or a script skips its step when the output exists, a rerun may leave the old file in place and `verify` then reports it as not written. Name a fresh run folder instead, or ask the user and write `(overwrite)` after that path; the gate reads only the path.

## Plan table

A numbered table, the only table in the brief (Evidence stays as bullets, and the plan-evidence block is JSON in a comment, because the gate reads every table row beside the plan as a plan row). Columns: Step, Choice, Source, Validation.

- **Step**: name by repository path, relative to the project root, every script, notebook, or pipeline the plan will run, including a wrapper the run goes through (such as the analysis's `run.sh`) and any figure or report script, and name `sbatch`, `snakemake`, or `nextflow` when the plan launches them. The approval gate reads only this column: a path in a Choice or Validation cell, in prose, in Evidence, or in a `repo:` citation approves nothing, so a run named only there is denied. Mark a step already done with `(done)`.
- **Choice**: one decision, in plain scientific terms with the numbers that would show it is right (for example `A_t pd counts 37 CLR / 29 asin`), at most about 150 characters. Name runs in Step, never here.
- **Source**: `repo: <path>`, `user`, or `default: <reason>`; the reason is one short phrase, and `plan-review` flags an empty one.
- **Validation**: one check.

The approval card quotes these four cells for the user to check the science. It shows each step top down with bullets for its choice and who decided it, the assumption behind a `default:`, and its check, and it cuts long lines (`hooks/gate.py` quotes a cell at up to 200 characters and a card line at 250). So one decision, assumption, or check per row, each in its own step's row rather than in prose.

Without run blocks, a path in the table is a broad grant (any arguments), and the card says so.

## Run blocks (optional)

For a reportable run: an `<!-- exact-execution {...} -->` block that freezes the arguments of chosen steps, and a `<!-- validation-bindings {...} -->` block that pins the test and expectation files of an acceptance check the user approves. Syntax in [run-plans.md](run-plans.md). Add one only where a result depends on it, not for every sentence of the plan; an exploratory test you wrote while developing is not an approved expectation, and `defined_by` is a claim the gate records, not proof.

## Plan evidence (optional)

A `<!-- plan-evidence {...} -->` block that records, for each fact the plan rests on, the read-only command that showed it and its verbatim output. Syntax in [plan-evidence.md](plan-evidence.md). Add one whenever at least two Evidence bullets rest on a file read, so `verify` can re-run the commands and report drift instead of trusting a paraphrase; skip it when the plan read nothing. It is JSON in a comment, never a table.

## Assumptions and risk

Each `default` row in one line, then the key failure mode and how the plan detects it.

## Parked

Deferred items, each with a return condition.

## Decisions to record

User answers and defaults the executing workflow should log (for example to `.living/decisions.md`) once work begins.

## Next action

Approve or edit the plan, then the execution route: in a Mycelium repository, Mycelium's analyze skill (`/mycelium:analyze` in Claude Code, `$mycelium:analyze` in Codex); otherwise the repository's normal workflow.

## Status line

The final message ends with the status on its own line, exactly `Plan status: READY`, `Plan status: READY_WITH_ASSUMPTIONS`, or `Plan status: DECISION_REQUIRED`. The gate takes the last such line, hashes the message, and shows `approve plan <hash>`.

## Worked examples

- [tests/e2e/plans/baseline_plan.md](../../../tests/e2e/plans/baseline_plan.md): Objective, `Inputs:`, `Outputs:`, the table with a `repo:` and a `default:` row, and the status line.
- [docs/examples/E05-documented-folder-does-not-exist.md](../../../docs/examples/E05-documented-folder-does-not-exist.md): the quoted question, hoped-for claim, tagged Evidence and `Facts:` line.
