# Mycelium Extra

A standalone companion plugin for read-only, pre-execution planning. It does not fork, modify, or require [Mycelium](https://github.com/arjunrajlaboratory/mycelium).

`grill` checks a proposed task against the repository's existing knowledge and code before asking anything. In a Mycelium project (any repository with `.living/`), it reads the Mycelium guidance (`MYCELIUM.md`, or the Mycelium block in `CLAUDE.md`/`AGENTS.md`), `.living/INDEX.md`, relevant memory entries, manifests, analysis docs, and implementation. In an ordinary repository it uses the project's own documentation and code.

It tests the goal, evidence, assumptions, alternatives, failure modes, and validation, and for bioinformatics or statistical work it walks a list of analysis decision points (unit of replication, matrix state, references, QC, batch, multiplicity, and more) so that none is left implicit. It asks only user-owned questions that could change the plan, one per message, at most five. It ends with `READY`, `READY_WITH_ASSUMPTIONS`, or one `DECISION_REQUIRED` item and a brief containing a numbered plan in which every consequential choice is sourced: repository evidence, a user answer, or a labeled default. Nothing runs until you approve or edit that plan.

## Use

- Claude Code, local session: run `claude --plugin-dir /absolute/path/to/mycelium-extra` from the project you want to examine. Invoke `/mycelium-extra:grill`, followed by your task or plan.
- Codex plugin distribution: this folder includes `.codex-plugin/plugin.json` and `skills/grill/SKILL.md`, ready to add to a Codex plugin marketplace. After installing the plugin, invoke `$mycelium-extra:grill`.
- Codex standalone skill: copy `skills/grill/` to your personal Codex skills location and invoke it as `$grill`; namespacing then depends on your installation route.

Example: `Grill my plan to redo monocyte pathway analysis across trials; inspect the repo before asking me anything.`

## Relation to Mycelium

- `grill` makes no edits: it never writes `.living/`, manifests, todo, or analysis files, and it never runs repository scripts by path, which would open Mycelium's post-action cycle. Data checks use inline read-only probes.
- After you approve the plan, execute through your normal workflow. In a Mycelium project that is `/mycelium:analyze` (`$mycelium:analyze` in Codex), which logs the brief's "Decisions to record" through Mycelium's lifecycle.
- `/mycelium:review grill` interrogates an existing analysis or diff; this skill plans before execution. They complement each other.
