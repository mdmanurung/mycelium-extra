# Installation and host compatibility

Install Mycelium Extra once, then choose which projects should use its approval
gate. The same planning skills are available in Claude Code and Codex. If your
project already uses Mycelium, the plugin reads its decisions and conventions;
in an ordinary repository, it starts with your existing documentation and code.

You can begin with a question such as:

> "Plan the next analysis using this project's sample table and previous decisions."

Install for your host, then [choose a usage tier](usage.md). Planning with
`grill` needs no gate setup; turn on the gate when you want covered execution checks.

## Claude Code

Add the marketplace and install the plugin:

```bash
claude plugin marketplace add mdmanurung/mycelium-extra
claude plugin install mycelium-extra@mycelium-extra
```

This makes the plugin's skills available as `/mycelium-extra:<skill>` commands.
Restart Claude Code, then invoke `/mycelium-extra:grill <task>`.
For a project-local install, run the install command in that project with
`--scope local`. For a local checkout, pass its absolute path to
`claude plugin marketplace add`, or try it without installing:

```bash
claude --plugin-dir /absolute/path/to/mycelium-extra
```

Update both the marketplace and plugin, then start a new session:

```bash
claude plugin marketplace update mycelium-extra
claude plugin update mycelium-extra@mycelium-extra
```

Claude caches plugins by their manifest version. Editing an installed checkout
without changing its version does not refresh the cached plugin; use
`--plugin-dir` to test local changes.

## Codex

Use Codex CLI 0.160.0 or later (`codex --version`, `codex plugin --help`):

```bash
codex plugin marketplace add mdmanurung/mycelium-extra
codex plugin add mycelium-extra@mycelium-extra
```

This installs the shared skills under the `mycelium-extra` namespace.
For local development, replace the marketplace source with
`/absolute/path/to/mycelium-extra`. Open `/hooks` in the Codex CLI, trust all
four Mycelium Extra hooks, fully exit Codex, and start a new task. Then invoke
`$mycelium-extra:grill <task>`. The same skill folders are used by both hosts.

`/hooks` is a CLI command. The desktop app does not provide this trust step.

Refresh the marketplace and reinstall the plugin, then start a new session:

```bash
codex plugin marketplace upgrade mycelium-extra
codex plugin add mycelium-extra@mycelium-extra
```

Revisit `/hooks` after an upgrade: the installed plugin path and its trust
record can change. Trust the current hooks and restart before relying on them.

## Your first analysis

Follow [Tier 2: Run with approval](usage.md#tier-2-run-with-approval): initialize
the gate, plan, approve the displayed hash, and run. For reportable work, add
[Tier 3: Verify reportable work](usage.md#tier-3-verify-reportable-work).

Only planning? Start with [Tier 1](usage.md#tier-1-plan); no `init` needed.

## Requirements

- The approval gate and helper scripts use Python 3.6 or later.
- Scientific checks need the tools for the files you use: R and R scilintr,
  Python scilintr, or h5py for H5AD inspection. A missing tool is reported as
  a gap rather than a successful check.
- Independent plan review needs a Codex CLI and a connected Biomni MCP in the
  Claude Code session. Missing reviewers are reported unavailable. Review
  packets leave the machine only after the user agrees.

## Host compatibility

| Feature | Claude Code | Codex CLI 0.160.0+ |
|---|---|---|
| Planning, data contracts, decision status, scaffolding, handoff, harden | Supported | Supported |
| Independent plan review | Leads Codex + Biomni synthesis | Engineering critique only |
| Init, approval gate, pinned inputs, exploration | Supported | Supported with enabled/trusted hooks |
| Run receipts and verification | Success/failure hook events provide status | Records receipts; absent exit metadata is a verification gap |
| Gate state protection | Shell commands and file-edit tools | Shell commands and `apply_patch`, including move destinations |

Codex 0.160.0's post hook supplies the command's output without an exit code.
The gate records `unknown`; it never infers success from that event or parses
command output as an exit status. Missing receipts remain missing. Upgrading
does not reconstruct older runs. Standalone skill copies provide no hooks.

The Codex payload contract was checked against its
[0.160.0 shell hook implementation](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/core/src/tools/handlers/unified_exec.rs)
and [post-tool response implementation](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/core/src/tools/context.rs).

## Troubleshooting

If skills are missing, confirm that the plugin is enabled and restart the host.
If a hook names a missing versioned cache path, refresh the installation and
restart. Do not repair the error by embedding another cache path in a project.

If analysis runs are unexpectedly blocked, inspect the pending plan and approve
its displayed hash. If pinned inputs changed, check them and present a revised
plan. See [Approval gate](approval-gate.md) for exploration and gate settings.

For verification gaps, read the report's missing evidence or tool rather than
re-running the analysis immediately. See [Skills](skills.md#verify).

## References

The [Claude Code manifest reference](https://code.claude.com/docs/en/plugins-reference)
describes plugin paths and validation. Codex install commands above were checked
against `codex-cli 0.160.0`'s local command help.
