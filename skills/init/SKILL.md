---
name: init
description: Turn on the mycelium-extra plan-approval gate in a repository. Creates `.mycelium-extra/gate.json` and ignores `.mycelium-extra/` in `.gitignore`, so analysis scripts and job launchers (sbatch, snakemake, nextflow) cannot run until the user approves a grill plan. Use when the user invokes mycelium-extra init, or asks to set up, enable, start, or initialize the approval gate or `gate.json` in a repository. Never changes a gate that is already on. Not for setting up Mycelium itself (use Mycelium's own init) and not for editing an existing gate's settings.
---

# Mycelium Extra: Init

Turn on the approval gate in the current repository. The gate itself is the Claude Code hooks in this plugin's `hooks/`; this skill only writes the file that switches them on.

## 1. Check where you are

- The gate runs only in Claude Code. In Codex, say so and stop.
- Run a dry run from stdin, from the repository root, so Mycelium's hooks stay closed:

  ```bash
  python3 - --dry-run < <skill-dir>/scripts/gate_init.py
  ```

  Running the script by path opens Mycelium's post-action cycle, so never do that.
- If it prints `already gated`, report the effective config and stop. Changing an existing gate is the user's call: they edit `gate.json` by hand. Do not offer to loosen it.

## 2. Pick what to gate

- The defaults gate scripts under `analysis/**` and `nbs/**`, the commands `sbatch`, `snakemake`, and `nextflow`, and approvals last 24 hours.
- If the dry run prints `WARNING: none of gated_paths exist`, the defaults would gate no scripts. List the repository's top-level folders that hold analysis scripts, and ask the user one question: which of them to gate. Do not guess.
- Otherwise use the defaults unless the user asked for something else.

## 3. Turn it on

```bash
python3 - [--paths 'scripts/**' 'workflow/**'] [--commands sbatch snakemake] [--hours 24] < <skill-dir>/scripts/gate_init.py
```

Pass only the options that differ from the defaults; with none, `gate.json` is `{}`. The script never overwrites an existing `gate.json` and never commits.

## 4. Report

- The files it created or changed (`.mycelium-extra/gate.json`, `.gitignore`) and the effective config.
- The gate is live on the next tool call in any Claude Code session that loaded this plugin at start; a session started before the plugin was installed needs a restart.
- How to use it: a grill plan that ends with `Plan status: READY` shows `approve plan <hash>`; typing that line allows the runs it names for `approval_hours`. `allow explore` lets `MYCELIUM_EXTRA_EXPLORE=1` runs through for the session.
- Offer to commit `.gitignore`; `.mycelium-extra/` itself stays untracked.
