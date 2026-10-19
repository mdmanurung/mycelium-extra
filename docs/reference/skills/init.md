# init

Turns the approval gate on in a repository. Guide: [Approve and run](../../guides/approve-and-run.md).

## Synopsis

```bash
sh <skill-dir>/../../hooks/py.sh - [--root DIR] [--paths GLOB ...] [--commands CMD ...] [--hours N] [--dry-run] < <skill-dir>/scripts/gate_init.py
sh <skill-dir>/../../hooks/py.sh - --tools [--scilintr PATH] [--rscript PATH] < <skill-dir>/scripts/gate_init.py
sh <skill-dir>/../../hooks/py.sh - --diagnose [--root DIR] [--plugin-root DIR] < <skill-dir>/scripts/gate_init.py
```

Invoke with `/mycelium-extra:init` (Claude Code, OpenCode) or `$mycelium-extra:init` (Codex). Run the script from stdin, never by path.

## Options

| Option | Meaning |
|---|---|
| `--root DIR` | Repository to gate. Default: the git top level of the current folder. |
| `--paths GLOB ...` | Value of `gated_paths`. Default `analysis/** nbs/**`. |
| `--commands CMD ...` | Value of `gated_commands`. Default `sbatch snakemake nextflow`. |
| `--hours N` | Value of `approval_hours`. Default 24. Must be finite and positive. |
| `--dry-run` | Report what would change; write nothing. |
| `--tools` | Also record where `scilintr` and an `Rscript` whose R has scilintr are, in `tools.json`. Looks at `--scilintr` / `$MX_SCILINTR`, `--rscript` / `$MX_RSCRIPT`, then `PATH`, and checks that each works. |
| `--scilintr PATH`, `--rscript PATH` | With `--tools`: the tool's path. |
| `--diagnose` | Read-only report. Cannot be combined with an option that writes. |
| `--plugin-root DIR` | With `--diagnose` only: this plugin's folder. Default: `$CLAUDE_PLUGIN_ROOT`, `$PLUGIN_ROOT`, or beside the script. |

## Reads

The repository's top-level folders (to warn when the default gated paths do not exist); `.gitignore`; `.mycelium/plugin-root` for the Mycelium version. `--diagnose` also reads `gate.json`, `hooks/hooks.json`, `hooks/codex.json`, `tools.json`, the newest line of `receipts.jsonl` and of `gate-errors.jsonl`, and checks which of h5py, scilintr, Rscript and sacct are present (presence only; nothing is run).

## Writes

| What | Where | When |
|---|---|---|
| `gate.json` | `.mycelium-extra/gate.json` | once; `{}` when you pass no options |
| ignore line | `.gitignore` gains `.mycelium-extra/` | when not already ignored |
| `tools.json` | `.mycelium-extra/tools.json` | with `--tools` |

`--diagnose` and `--dry-run` write nothing. The script never commits. When a gate is already on (here or in a parent folder), the script prints `already gated`, the effective config and a note that nothing changed, and exits 0 (1 if that `gate.json` is unreadable); with `--tools` it still records the tools.

## Defaults and switching off

Not on until invoked. There is no "off" command: delete `.mycelium-extra/gate.json` to turn the gate off for that repository. Its records stay in `.mycelium-extra/`; `verify` then reports the runs of a plan as unrecorded, which is a gap and never a clean pass.

## What `--diagnose` reports

Effective config (defaults merged with `gate.json`, invalid values flagged, unknown keys named), the events registered in `hooks.json` and `codex.json` (the OpenCode adapter is not checked), the Mycelium version and whether it is one mycelium-extra was tested with (0.6.0, 0.7.2), tool presence, the newest receipt's host and exit status, and the last gate error. Its closing note applies: a registration or a `gate.json` does not prove your host has enabled or trusted the hooks. Check `/hooks` in Codex or Claude Code and restart the session.

## Confirmation

| Step | Kind |
|---|---|
| Never overwrite an existing `gate.json` | Enforced by the script |
| Asking which folders to gate when the defaults do not exist | The agent's instruction |
| Never installing packages without asking (`--tools`) | The agent's instruction |

## Notes

- A gate found in a parent folder applies to a nested repository too.
- After `init`, the gate is live on the next tool call in any session that loaded and enabled the plugin's hooks at start. A session started before installation needs a restart. OpenCode needs the `opencode/` plugin directory in `plugins` ([Installation](../../installation.md)).
- Every key is explained in [gate.json](../gate-json.md).
