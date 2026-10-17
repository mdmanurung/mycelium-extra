---
name: init
description: Turn on the mycelium-extra plan-approval gate in a repository. Creates `.mycelium-extra/gate.json` and ignores `.mycelium-extra/` in `.gitignore`, so analysis scripts and job launchers (sbatch, snakemake, nextflow) cannot run until the user approves a grill plan. Use when the user invokes mycelium-extra init, or asks to set up, enable, start, or initialize the approval gate or `gate.json` in a repository. Never changes a gate that is already on. Not for setting up Mycelium itself (use Mycelium's own init), not for editing an existing gate's settings, and not for creating an analysis folder (use new-analysis).
---

# Mycelium Extra: Init

Turn on the approval gate in the current repository. The gate uses this plugin's host-specific hooks in `hooks/`; this skill only writes the file that switches them on.

## 1. Check where you are

- Install the complete plugin, including hooks. In Codex, use CLI 0.160.0 or later, open `/hooks`, enable/trust the plugin hooks, and restart before relying on the gate. Standalone skills do not install hooks.
- Run a dry run from stdin, from the repository root, so Mycelium's hooks stay closed:

  ```bash
  sh <skill-dir>/../../hooks/py.sh - --dry-run < <skill-dir>/scripts/gate_init.py
  ```

  Running the script by path opens Mycelium's post-action cycle, so never do that.
- If it prints `already gated`, report the effective config and stop. Changing an existing gate is the user's call: they edit `gate.json` by hand. Do not offer to loosen it.

## 2. Pick what to gate

- The defaults gate scripts under `analysis/**` and `nbs/**`, the commands `sbatch`, `snakemake`, and `nextflow`, and approvals last 24 hours.
- If the dry run prints `WARNING: none of gated_paths exist`, the defaults would gate no scripts. List the repository's top-level folders that hold analysis scripts, and ask the user one question: which of them to gate. Do not guess.
- Otherwise use the defaults unless the user asked for something else.

## 3. Turn it on

```bash
sh <skill-dir>/../../hooks/py.sh - [--paths 'scripts/**' 'workflow/**'] [--commands sbatch snakemake] [--hours 24] < <skill-dir>/scripts/gate_init.py
```

Pass only the options that differ from the defaults; with none, `gate.json` is `{}`. The script never overwrites an existing `gate.json` and never commits.

## 3b. Find the linters (optional)

`verify` and the approval card run scilintr, and on a cluster neither `scilintr` nor an `Rscript` whose R has the `scilintr` package is usually on `PATH`. Run, from stdin as above, `sh <skill-dir>/../../hooks/py.sh - --tools < <skill-dir>/scripts/gate_init.py` (it works on a gate that is already on and leaves `gate.json` alone). It looks at `$MX_SCILINTR`, `$MX_RSCRIPT`, then `PATH`, checks that each tool works, and writes `.mycelium-extra/tools.json`. For one it cannot find, ask the user for its path (a venv's `bin/scilintr`; after `module load R`, `which Rscript`) and rerun with `--scilintr PATH` or `--rscript PATH`. Never install packages without asking.

## 3c. Diagnose (optional, read-only)

When the user asks why the gate seems off, or what this install can see, run `sh <skill-dir>/../../hooks/py.sh - --diagnose < <skill-dir>/scripts/gate_init.py` (add `--plugin-root DIR` if it cannot find the plugin's `hooks/`). It writes nothing and reports the effective config (invalid values flagged), the hook registrations in `hooks/hooks.json` and `hooks/codex.json` (and which held-back capacity registrations are absent), the Mycelium version, which of h5py, scilintr, Rscript and sacct are present, and the newest receipt's host and exit status and the last gate error. Pass its output on as printed, including its closing note: a registration or a `gate.json` does not prove the host has enabled or trusted the hooks. Do not combine it with options that write.

## 4. Report

- Any `note: Mycelium <version> is installed here...` line, passed on as printed: the Mycelium here is not one mycelium-extra was tested with. Do not act on it.
- The files it created or changed (`.mycelium-extra/gate.json`, `.gitignore`, and `tools.json` when `--tools` ran) and the effective config, and which linters were found.
- The gate is live on the next tool call in any Claude Code or Codex session that loaded and enabled this plugin's hooks at start; a session started before the plugin was installed needs a restart.
- How to use it: a grill plan that ends with `Plan status: READY` shows `approve plan <hash>`; typing that line allows the runs it names for `approval_hours`. `allow explore` lets `MYCELIUM_EXTRA_EXPLORE=1` runs through for the session.
- Offer to commit `.gitignore`; `.mycelium-extra/` itself stays untracked.
