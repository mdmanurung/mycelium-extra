# Installation

Install once, then choose which projects use the approval gate. All three hosts get the same skills. Planning with `grill` needs no gate setup. Then follow [your first plan](start/first-plan.md).

Needs Python 3.9 or later on every host (see [Requirements](#requirements)).

::::{tab-set}

:::{tab-item} Claude Code

```bash
claude plugin marketplace add mdmanurung/mycelium-extra
claude plugin install mycelium-extra@mycelium-extra
```

Restart Claude Code, then run `/mycelium-extra:grill <task>`.

- Project-local install: add `--scope local`.
- Try a local checkout without installing: `claude --plugin-dir /absolute/path/to/mycelium-extra`. Claude caches plugins by manifest version, so use this to test edits.
- Update: `claude plugin marketplace update mycelium-extra`, then `claude plugin update mycelium-extra@mycelium-extra`, then a new session.
:::

:::{tab-item} Codex

Needs Codex CLI 0.160.0 or later.

```bash
codex plugin marketplace add mdmanurung/mycelium-extra
codex plugin add mycelium-extra@mycelium-extra
```

Then open `/hooks`, trust every Mycelium Extra hook (five entries on four events), fully exit Codex and start a new task. Run `$mycelium-extra:grill <task>`. `/hooks` is a CLI command; the desktop app has no such trust step.

Update with `codex plugin marketplace upgrade mycelium-extra` and `codex plugin add mycelium-extra@mycelium-extra`, then trust the hooks again: the plugin path and its trust record can change.
:::

:::{tab-item} OpenCode

OpenCode V2 loads skills and plugins from configured folders, so point both at a checkout. In `~/.config/opencode/opencode.json(c)`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugins": ["/absolute/path/to/mycelium-extra/opencode"],
  "skills": ["/absolute/path/to/mycelium-extra/skills"]
}
```

Start a new session and run `/mycelium-extra:grill <task>`. To update, pull the checkout and start a new session.

- Keep each skill folder inside the checkout: skills call `../../hooks/mxpy` relative to themselves. If you copy the plugin folder, pass `{ "package": ".../opencode", "options": { "root": "/path/to/mycelium-extra" } }`.
- The plugin is inert in repositories without `.mycelium-extra/gate.json`. When the gate cannot answer, it adds a gate-error note and lets the call through, unless `gate.json` sets `"on_error": "deny"`.
- Qualified on OpenCode 2.0.32. Receipts record the shell tool's exit code; a result with none is recorded `unknown` and verification reports a gap.
:::

::::

![Claude Code uses a marketplace plugin, Codex uses its plugin plus enabled and trusted hooks, and OpenCode points skills and plugins to a checkout. Python is shared, but host capabilities differ.](figures/host-routes.svg)

Pick the matching host tab below, then check that its hooks are active. The compatibility table describes differences; shared skills do not imply identical host evidence.

## Requirements

- **Python 3.9 or later.** Skill commands run through `hooks/mxpy` (no `.sh` suffix, so Mycelium's post-action detector ignores it). Hooks run through `hooks/py.sh`, which hands over to it and uses `MYCELIUM_EXTRA_PYTHON` if set, else `python3` when it is 3.9 or later (hooks skip that probe), else the newest `python3.N` on `PATH`. On RHEL 8, `python3` is 3.6 but `python3.11` or `python3.12` usually exist. Set `MYCELIUM_EXTRA_PYTHON` to choose one.
- **Scientific checks** use the tools for the files you have: R with scilintr, Python scilintr, or h5py for H5AD. A missing tool is reported as a gap, never as a pass. On a cluster, record where they are with `gate_init.py --tools` (see [Verification](verification.md)).
- **Independent plan review** needs a Codex CLI and a connected Biomni MCP in a Claude Code or OpenCode session. Missing reviewers are reported unavailable, and a packet leaves the machine only after you agree.

## With lucid-coder

lucid-coder is optional. When it is installed, Extra uses it in five places and never edits its files:

- **Environment.** `/lucid-coder:align` writes `lucid-coder.yaml` at the repository root: the conda, pixi or uv environment and its `Rscript` and `python`. `new-analysis` uses those paths in the Snakefile, `grill` names the environment in the plan's Evidence, and `init --diagnose` shows whether the paths exist. Without the file, the Snakefile uses the names on `PATH`.
- **Setup.** `repo-setup` runs `/lucid-coder:align` after laying out the repository.
- **Step stubs.** R, Python, qmd and marimo stubs follow lucid-coder's layout: a Purpose, Run, Inputs and Outputs header, parameters first, a seed, and notebooks that read tables a script wrote.
- **Figures.** `plot-first` and `analysis-report` defer to lucid-coder's `figure-style` for theme, palette and size; Extra's integrity rules still apply.
- **Single-cell exploration.** `plot-first` points AnnData exploration at lucid-coder's `sc-qc` and `sc-embed`.

## With lucid-writer

lucid-writer is optional. It sets how prose reads and how strongly a claim is worded. Extra never edits its files, and Extra's checks work without it.

- **Report prose.** When lucid-writer is installed, `analysis-report` loads it before it writes the Answer, the Question/Approach/Conclusion text and Key Findings. Then it runs `verify report <hash> --claims reports/<name>.qmd --resolve-citations` on the report. The evidence auditor agent is offered only when you ask for it.
- **Evidence files.** lucid-writer reads `provenance/verify-<hash>.md`, `outputs-<hash>.tsv`, `PROVENANCE.md` and `outputs/numbers.json`. It reads the `status` of `manuscript-audit` (`pass`, `gap` or `block`) and never recomputes it. `tests/test_lucid_writer_contract.py` pins these names.

lucid-writer rewrites deliverables only. A format-fixed record keeps Extra's format.

| Deliverable (lucid-writer applies) | Format-fixed record (Extra's format) |
|---|---|
| Report `.qmd` prose | `HANDOFF.md` |
| Key Findings | `PLAN.md` and the grill brief |
| Manuscript text | `TRACKER.md` |
| | The `where` card |
| | Hook notices |

Extra's markers map to lucid-writer's when text moves from a record into a deliverable:

| Extra marker | lucid-writer marker |
|---|---|
| `unsupported: no inspected figure` | `[EVIDENCE NEEDED]` |
| `source data missing` | `[EVIDENCE NEEDED]` |
| `[BLANK: ...]` | `[EVIDENCE NEEDED]` |

Keep the Extra marker in the record. Use the lucid-writer marker only in the deliverable.

## With Mycelium

Mycelium is optional. Extra is tested against Mycelium 0.9.x and complements it: it writes no file under `.living/` and none of Mycelium's own files.

Mycelium 0.9.x adopted four skills that began in Extra: grill planning, decision-status, harden and data-contract-check. Extra's versions are the gated ones, because they tie to the approval gate and its plan hash. Use Extra's when you want the gate to check the result. See [Mycelium integration](mycelium-integration.md).

## Host compatibility

| Feature | Claude Code | Codex 0.160.0+ | OpenCode V2 |
|---|---|---|---|
| Skills | Supported | Supported | Supported |
| `analysis-report artifact` | Supported | Prints a note, builds nothing | Prints a note, builds nothing |
| `explore` and `--session` in `grill`, `verify` and `track-changes` | Use this session | All sessions of the last 7 days by default | All sessions of the last 7 days by default |
| `handoff test` | Fresh subagent reads the file | Prints the prompt | Prints the prompt |
| Independent plan review | Leads Codex + Biomni | Engineering critique only | Leads Codex + Biomni when both are available |
| `init`, approval gate, pinned inputs, exploration | Supported | Needs enabled and trusted hooks | Supported |
| Receipts and verification | Exit status from hook events | Exit status `unknown`: a verification gap | Exit status from the shell result |
| Gate state protection | Shell and file-edit tools | Shell and `apply_patch` | `shell`, `edit`, `write`, `patch` |

Codex's post hook gives the command's output without an exit code. The gate records `unknown` and never infers success from output. Standalone skill copies have no hooks.

## Troubleshooting

- **Skills missing:** confirm the plugin is enabled and restart the host.
- **A hook names a missing cache path:** refresh the installation and restart. Do not paste a cache path into a project.
- **A run is blocked:** read the pending plan and approve its displayed hash. If pinned inputs changed, check them and show a revised plan. See [the approval gate](approval-gate.md).
- **Verification gaps:** read the report's missing evidence before re-running anything. See [Skills](skills.md#verify).
