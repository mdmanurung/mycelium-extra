# Installation and host compatibility

Install Mycelium Extra once, then choose which projects should use its approval
gate. The same planning skills are available in Claude Code, Codex, and
OpenCode. If your project already uses Mycelium, the plugin reads its decisions
and conventions; in an ordinary repository, it starts with your existing
documentation and code.

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

## OpenCode

OpenCode V2 discovers skills from configured directories and loads plugins from
configured plugin directories, so point both settings at this checkout. Add to
`~/.config/opencode/opencode.json(c)`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugins": ["/absolute/path/to/mycelium-extra/opencode"],
  "skills": ["/absolute/path/to/mycelium-extra/skills"]
}
```

Start a new session and mention a skill by name:

```text
@grill Plan a paired treatment-response analysis. Read the sample table and existing decisions first.
```

OpenCode advertises each skill by its name and description; there is no
`/mycelium-extra:` prefix. Plugin loading, the adapter's event and payload
shapes, and its tool/prompt/stop behavior were checked against OpenCode 2.0.32;
a live end-to-end qualification (a real denied run, approval card, and receipt)
is still to do. The plugin is the gate's host adapter: it runs the shared
Python gate and is inert in repositories without `.mycelium-extra/gate.json`.

Keep each skill folder inside the checkout. Skills that run scripts call
`../../hooks/py.sh` relative to their own folder, so a copied or symlinked
skill folder elsewhere cannot find the hooks. The plugin resolves the checkout
from its own location the same way; if you copy the plugin directory, pass
`{ "package": ".../opencode", "options": { "root": "/path/to/mycelium-extra" } }`.
For a project-local install, add the same two entries to that project's
`opencode.json(c)`; relative paths resolve from OpenCode's working directory.

Skill IDs are the folder names (`grill`, `init`, and so on). A `skills` entry is
the highest-precedence source in OpenCode, so these generic IDs shadow
same-named skills from other sources; see the
[Skills reference](https://opencode.ai/v2/docs/skills/).

OpenCode receipts record `host: opencode`. A shell result without an exit code
records `unknown`, and verification reports a gap; the gate never infers
success from a finished command.

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

- The approval gate and helper scripts need Python 3.9 or later. They run through `hooks/py.sh`, which picks
  `python3` if it is new enough, else the newest `python3.N` on `PATH` (on RHEL 8, `python3` is 3.6 but
  `python3.11` or `python3.12` usually exist). Set `MYCELIUM_EXTRA_PYTHON` to choose one yourself. With only
  an older Python, the gate reports it on every hook and follows `on_error` in `gate.json`.
- Scientific checks need the tools for the files you use: R and R scilintr,
  Python scilintr, or h5py for H5AD inspection. A missing tool is reported as
  a gap rather than a successful check. Neither is usually on `PATH` on a cluster; record where they are
  with `gate_init.py --tools` (see [Verification](verification.md)).
- Independent plan review needs a Codex CLI and a connected Biomni MCP in the
  Claude Code session. Missing reviewers are reported unavailable. Review
  packets leave the machine only after the user agrees.

## Host compatibility

| Feature | Claude Code | Codex CLI 0.160.0+ | OpenCode V2 |
|---|---|---|---|
| Planning, data contracts, decision status, scaffolding, handoff, harden | Supported | Supported | Supported |
| Independent plan review | Leads Codex + Biomni synthesis | Engineering critique only | Not yet characterized |
| Init, approval gate, pinned inputs, exploration | Supported | Supported with enabled/trusted hooks | Supported (adapter; live qualification pending) |
| Run receipts and verification | Success/failure hook events provide status | Records receipts; absent exit metadata is a verification gap | Records receipts; exit status unknown without a result code |
| Gate state protection | Shell commands and file-edit tools | Shell commands and `apply_patch`, including move destinations | `shell`, `edit`, `write`, and `patch` tools |

OpenCode V2 runs the planning skills through the `skills` setting and the
approval gate through the `plugins` setting, both above. Live qualification of
the adapter on OpenCode 2.0.32 is pending; until it passes, cover reportable
runs with Claude Code or Codex.

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
against `codex-cli 0.160.0`'s local command help. The OpenCode section follows
the [OpenCode V2 skills guide](https://opencode.ai/v2/docs/skills/), checked on
OpenCode 2.0.32.
