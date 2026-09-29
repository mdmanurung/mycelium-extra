# Mycelium Extra

A standalone companion plugin for bounded, repository-aware questioning. It does not fork, modify, or require [Mycelium](https://github.com/arjunrajlaboratory/mycelium). In a Mycelium project, `grill` reads `MYCELIUM.md`, `.living/INDEX.md`, relevant project memory, manifests, and implementation. In an ordinary repository it uses the project's own documentation and code.

The skill challenges the goal, evidence, assumptions, alternatives, failure modes, and validation. It asks only user-owned questions that could change the next consequential action. Its default ceiling is two rounds and five questions; it normally ends earlier with `READY`, `READY_WITH_ASSUMPTIONS`, or one `DECISION_REQUIRED` item. It is read-only during grilling.

## Use

- Claude Code, local session: extract the ZIP and run `claude --plugin-dir /absolute/path/to/mycelium-extra` from the project you want to examine. Invoke `/mycelium-extra:grill`, followed by your task or plan.
- Codex plugin distribution: this folder includes `.codex-plugin/plugin.json` and `skills/grill/SKILL.md`, ready to add to a Codex plugin marketplace. After installing the plugin, invoke `$mycelium-extra:grill`.
- Codex standalone skill: the skill also works without plugin distribution. Copy `skills/grill/` to your personal Codex skills location and invoke it as `$grill`; namespacing then depends on your installation route.

Example: `Grill my plan to redo monocyte pathway analysis across trials; inspect the repo before asking me anything.`

The skill does not invoke Mycelium skills as APIs or write project memory. If you decide to execute the resulting brief, use your normal project workflow so consequential changes follow Mycelium's lifecycle.
