---
name: setup-wizard
disable-model-invocation: true
description: Generate an interactive bash wizard that walks you through cluster setup steps only you can do. SLURM access, environments, data downloads, keys, first-time auth.
---

# Mycelium Extra: Setup wizard

Build a bash script that walks the human through setup steps the agent cannot do for them, and records what they did. The agent writes the script. The human runs it. Adapted from Matt Pocock's wizard skill (MIT).

Use it for: a SLURM account or partition request, an environment install (conda, pixi, uv), a controlled-access or large download with checksums, an API key, `lucid-coder.yaml` setup, first-time git or GitHub auth. Do not use it for a step the agent can run itself.

The wizard library is in `templates/template.sh`. It gives stage progress, confirm gates, URL opening, hidden secret entry, idempotent writes, an `sbatch` test job, a checksum check and a setup log. Author only the stages below the `STAGES` marker. Never edit the library above it. Helper names and settings: `references/helpers.md`.

## Rules the wizard keeps

- Every irreversible action sits behind `confirm`. The wizard never deletes data.
- A secret is read hidden and goes only to a mode-600 file outside the repository, or to a file git already ignores. It is never echoed or logged.
- For controlled-access data the access terms are the human's to follow. The wizard records who approved and when, and enforces nothing.
- A browser URL or a UI path you have not seen is not written down. Write "check the current page" and name what to look for.

## Process

### 1. Scope from the repo

Read before asking: `README`, `lucid-coder.yaml`, `data/SOURCES.md` or `DATA_MANIFEST*`, `Snakefile` and its profiles, `run.sbatch`, environment files (`environment.yml`, `pixi.toml`, `pyproject.toml`), `.gitignore`. Note which analysis folder owns the setup log (`analysis/<name>/logs/SETUP.md`).

Show the ordered stage list, one line per stage: what the human does, what it produces, where it is recorded. Ask the user to add, drop or reorder.

**Done when** the user confirmed the list, and each stage names (a) where the human gets what they need, (b) where the result lands (the setup log, the secrets file, nowhere), (c) whether anything is secret.

Choices that change results are not a wizard's to settle. If a stage picks an environment version, a reference build or a data release, list it as its own row, source `inherited: <path>` or `unplanned`, and get a one-line confirm. A stage the plan already covers needs no new row.

### 2. Map each stage

Write the exact journey for each stage from `references/stages.md` and from the user. Where you do not know the page, the partition name or the command, say so and ask, or write "check the current page". Never invent a menu path.

**Done when** each stage reads as steps a stranger could follow, and every unknown is a question to the user or a "check" line.

### 3. Author the wizard

Copy `templates/template.sh` to `setup/<topic>.sh` at the project root. Do not put it under `analysis/` or `nbs/`, which are gated paths. Ask the user if they want another place. Replace the example stage with one `stage` per step, in dependency order. Set `TOTAL_STAGES`. Set `SETUP_LOG` to the analysis log when the setup belongs to one analysis.

Stage pattern: open the URL or show the command, say what to copy, `ask` or `ask_secret`, then `log_setup` what was done (names and paths, never values), then `mark_done`. Start each stage with `skip_if_done`. Keep one task per stage so nothing scrolls away.

**Done when** `bash -n setup/<topic>.sh` passes, and `shellcheck` is clean when installed (say so when it is missing).

### 4. Hand off

Do not run the wizard. It blocks on a human. Trace it by reading: each captured value from step 1 lands where the stage list said, and no secret name or value reaches `log_setup` text.

Tell the user the command: `bash setup/<topic>.sh`, run from the project root on a login node. Say it is safe to stop and re-run. Say `MX_WIZARD_YES=1` is for tests only and must not be set in a real run.

Suggest, do not run, the follow-ups that fit: `/lucid-coder:align` after a `lucid-coder.yaml` stage, `/mycelium:ingest` to register downloaded data. Ask whether to commit the script or keep it scratch.

**Done when** the user has the run command and the list of follow-ups.

## Pointers

- `references/stages.md`: stage recipes for each kind of setup, with what to ask the user and what to log.
- `references/helpers.md`: the library helpers, settings and the test-only flag.
