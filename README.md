# Mycelium Extra

A standalone companion plugin for pre-execution planning. `grill` is read-only; `decision-status` appends to `.living/decisions.md` only after you confirm. It does not fork, modify, or require [Mycelium](https://github.com/arjunrajlaboratory/mycelium).

`grill` checks a proposed task against the repository's existing knowledge and code before asking anything. In a Mycelium project (any repository with `.living/`), it reads the Mycelium guidance (`MYCELIUM.md`, or the Mycelium block in `CLAUDE.md`/`AGENTS.md`), `.living/INDEX.md`, relevant memory entries, manifests, analysis docs, and implementation. In an ordinary repository it uses the project's own documentation and code.

It tests the goal, evidence, assumptions, alternatives, failure modes, and validation, and for bioinformatics or statistical work it walks a list of analysis decision points (unit of replication, matrix state, references, QC, batch, multiplicity, and more) so that none is left implicit. It asks only user-owned questions that could change the plan, one per message, at most five. It ends with `READY`, `READY_WITH_ASSUMPTIONS`, or one `DECISION_REQUIRED` item and a brief containing a numbered plan in which every consequential choice is sourced: repository evidence, a user answer, or a labeled default. Nothing runs until you approve or edit that plan.

`decision-status` settles which past decision binds a task when `.living/decisions.md` holds several entries on the same choice, for example a method that was confirmed, another held, then shelved. A small read-only parser lists only the entries the task touches, oldest first, with their raw `Status`/`Supersedes`/`Scope`/`Revisit when` lines and heading status words. It never infers that an entry is current. An explicit supersession wins, then the entry whose scope matches the task; anything else is contested and goes to you, at most three questions per session. Once you confirm an answer, it appends a `Resolution:` entry with those fields, so the same question does not come back. It never edits existing entries. The entry uses the ordinary decision fields plus `Status`, `Supersedes`, `Scope`, `Revisit when`, and `Resolved-by`; Mycelium 0.7.2's scripts do not parse `Status` in `decisions.md`, so they treat these as plain body text.

`data-contract-check` tests a plan's assumptions about its sample table before anything runs. The plan's assumptions go into a small JSON contract: required columns, cohort levels and row counts, one row per unit per cell, complete pairing across timepoints, and batch versus contrast nesting. A stdlib checker reports each mismatch with expected, observed, and evidence lines, in the shape of ClawBio's contract alerts. The checker, not the contract, decides what blocks: any failure of these kinds blocks, and the skill never loosens a contract to make it pass without your agreement. v1 reads CSV/TSV tables; h5ad internals are not checked yet.

## Use

- Claude Code, local session: run `claude --plugin-dir /absolute/path/to/mycelium-extra` from the project you want to examine. Invoke `/mycelium-extra:grill`, `/mycelium-extra:decision-status`, or `/mycelium-extra:data-contract-check`, followed by your task or plan.
- Codex plugin distribution: this folder includes `.codex-plugin/plugin.json` and `skills/*/SKILL.md`, ready to add to a Codex plugin marketplace. After installing the plugin, invoke `$mycelium-extra:<skill>`.
- Codex standalone skill: copy one `skills/<skill>/` folder to your personal Codex skills location and invoke it as `$grill`; namespacing then depends on your installation route.

Example: `Grill my plan to redo monocyte pathway analysis across trials; inspect the repo before asking me anything.`

## Relation to Mycelium

- `grill` makes no edits: it never writes `.living/`, manifests, todo, or analysis files, and it never runs repository scripts by path, which would open Mycelium's post-action cycle. Data checks use inline read-only probes.
- `decision-status` writes to `.living/decisions.md` only after you confirm a resolution in the conversation, and only by appending a new entry. Its parser runs from stdin (`python3 - ... < decision_threads.py`), which Mycelium 0.6.0 and 0.7.2 hooks do not treat as a post-action run. `data-contract-check` is read-only and runs the same way; its contract lives outside the repository until the plan is approved. Tests: `python3 skills/<skill>/tests/test_*.py`.
- After you approve the plan, execute through your normal workflow. In a Mycelium project that is `/mycelium:analyze` (`$mycelium:analyze` in Codex), which logs the brief's "Decisions to record" through Mycelium's lifecycle.
- `/mycelium:review grill` interrogates an existing analysis or diff; this skill plans before execution. They complement each other.
