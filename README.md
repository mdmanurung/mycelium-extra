# Mycelium Extra

**Plan an analysis. Approve what runs. Check the execution record.**

Mycelium Extra reads your repository, helps you make a sourced plan, and can
check covered runs against that plan. Works in Claude Code, Codex, and OpenCode,
alongside
[Mycelium](https://github.com/arjunrajlaboratory/mycelium) or in an ordinary repository.

## Start here

1. [Install for your host](docs/installation.md).
2. [Choose a usage tier](docs/usage.md). Start with `grill` for planning, or
   add `init` for your first gated run.
3. Open the [documentation website](https://mdmanurung.github.io/mycelium-extra/)
   for guides and reference.

## Usage tiers

Each tier adds to the previous one; use only what your task needs.

| Tier | Tools | What you get |
|---|---|---|
| 1. Plan | `grill` | A sourced plan; no analysis runs or file writes |
| 2. Run with approval | Add `init` and `approve plan <hash>` | Covered execution checks, input pins, receipts |
| 3. Verify reportable work | Add a pinned run plan and `verify` | Checks against the approved plan; provenance after confirmation |
| 4. Full project workflow | Add scaffolding, independent review, handoff, hardening, Mycelium | Structure, continuity, and checks for recurring mistakes |

See [Usage tiers](docs/usage.md) for commands and examples, or the
[full analysis workflow diagram](docs/usage.md#full-analysis-workflow). `grill` calls
`decision-status` and `data-contract-check` when needed.

## Quick start

Commands below use Claude Code syntax. In Codex, replace `/mycelium-extra:`
with `$mycelium-extra:` and enable/trust the plugin hooks first. In OpenCode,
run the same `/mycelium-extra:grill` commands (mentioning `@grill` also works);
see [Installation](docs/installation.md#opencode).

```text
/mycelium-extra:init                         # once per repository
/mycelium-extra:grill <your analysis question>
approve                                      # or approve plan <hash>
```

Bare `approve` works when the plan shown last is the only one waiting; otherwise
it approves nothing and lists the hashes.

See [a worked example](docs/example.md) for the real output of each step. [A day with Mycelium Extra](docs/day.md) walks through a full working day.

Run the approved steps through your normal workflow, then invoke
`/mycelium-extra:verify <hash>`. Edit the plan's scripts freely: the gate re-pins each edit with a notice. Before a reportable run, type
`freeze <hash>` to review the code once and approve it; for HPC work, a
[run plan](skills/grill/references/run-plans.md) also freezes the exact commands.
Codex CLI 0.160.0 receipts lack exit metadata; verification reports that gap.
Independent Codex + Biomni review is led from Claude Code or OpenCode; in
Codex, `plan-review` provides the engineering critique only.

## Documentation

- [Installation](docs/installation.md) and [usage tiers](docs/usage.md): begin here.
- [Skill reference](docs/skills.md), [approval gate](docs/approval-gate.md),
  and [verification](docs/verification.md): look up details when needed.
- [Advanced features](docs/advanced.md): optional settings and subcommands
  that Tiers 1 to 3 do not need.
- [Focus and track changes](docs/focus-and-track-changes.md): say which analysis
  a session works on, and see what changed against the approved plan.
- [Mycelium integration](docs/mycelium-integration.md): credits and boundaries.
- [Development](docs/development.md): tests, changelog, roadmap, and design notes.

## License and credits

MIT, see [LICENSE](LICENSE). The bundled analysis template retains Mycelium's
MIT notice in [MYCELIUM_LICENSE](skills/new-analysis/templates/MYCELIUM_LICENSE).
See [Mycelium integration](docs/mycelium-integration.md) for reused ideas and formats.
