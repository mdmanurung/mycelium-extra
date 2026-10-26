# Approval gate

The gate checks covered analysis commands before they run, so an agent cannot start a new run because an earlier chat discussed it. You decide what is approved; the gate records the runs that follow. It catches execution mistakes and shows gaps. It is **not a security boundary**, and the "ask first" steps in skills are instructions to the agent, not rules the gate enforces.

Turn it on per repository with `/mycelium-extra:init` (Codex: `$mycelium-extra:init`). By hand: create `.mycelium-extra/gate.json` (`{}` uses the defaults) and add `.mycelium-extra/` to `.gitignore`. It holds short-lived execution state, not project knowledge. `init` never changes a gate that is already on.

**Full detail** for every section below, including card fields, receipt fields and edge cases, is in the [complete gate reference](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/approval-gate-full.md).

![Covered execution needs a matching approval in the session. Changed pinned inputs block. Ordinary script edits re-pin with a notice. Exploration needs its own typed grant. More exact execution contracts can add constraints.](figures/gate-checks.svg)

These are distinct checks, not alternative scientific verdicts. The full reference explains exact-execution contracts, time limits, unsupported tools and error policy.

## Approving a plan

When a reply ends with `Plan status: READY` or `READY_WITH_ASSUMPTIONS`, the Stop hook hashes the plan and shows a **card**: the question, each choice and who decided it (`[you]`, `[repo: ...]`, `[default: reason]*`), the checks, what changed since the last approval, and exactly what the plan lets run. Check the science on the card, then type:

```text
approve plan <hash>
```

- Only the exact words count. `approve it` is an ordinary prompt.
- Bare `approve` works only when exactly one card is waiting and it is the one shown last. Otherwise nothing is approved and the reply lists the pending hashes.
- Amendment and freeze cards use their own verbs (`approve amendment`, `approve freeze`); the reply names the right one.
- `card <hash> full`, `card <hash> checks` and `card <hash> diff` show the rest.
- An approval grants execution only in the session that gave it. To continue in a new session, show the plan there first (`handoff` points at its stored text) and approve the hash on the new card.

## What is gated

Before each shell call, the gate denies a gated run unless an approval from the last `approval_hours` (default 24) names it. Two kinds of run are gated:

- **Scripts** under `gated_paths` (default `analysis/**`, `nbs/**`), however they are started: by interpreter, directly, through `conda run`, `uv run`, `env`, `srun`, `timeout`, and similar wrappers.
- **Commands** in `gated_commands` (default `sbatch`, `snakemake`, `nextflow`). A dry run is gated too, because a Snakefile is Python.

Only the plan table's **Step** column grants a run. A path in a Choice, Validation or Source cell, in prose, or in a citation approves nothing. Name each script by its project-relative path, or an enclosing folder at least two levels deep. Write paths literally: a `$VAR`, `$(...)` or loop variable cannot be resolved and is denied. Reading files (`cat`, `rg`, `git`) is never gated.

## Pinned inputs

An approval covers the inputs you checked, not only the steps. A grill brief's `Inputs:` line names the files the plan rests on (sample table, config, lockfile, raw-file folder). When the card is shown they are fingerprinted: a sha256 within the budget (`pin_hash_mb`, `pin_seconds`), else size and mtime; a folder gets a listing fingerprint. Before a covered run the gate compares them. If one changed, the run is blocked, naming the file and both fingerprints: re-check the input, show the plan again and approve it. A plan with no `Inputs:` line pins nothing, and says so.

The card also compares what the plan declares. If an `Outputs:` entry names the same path as an `Inputs:` entry (also after resolving `..` or a link), the compact card shows `Data writes  input/output overlap: HIGH 1`, and the full card names both paths. An output folder or pattern that could cover an input is `REVIEW`; an output inside an input folder is information on the full card only. This is a note on the plan you are about to approve. It changes no allow or deny decision, reads no file, and adds no step: approve as usual, or fix the declarations first. It compares declared names only, so a plan with no `Outputs:` line, or one that uses a shell variable, gets no comparison, and no comparison does not mean a script cannot overwrite the input.

## Pinned scripts

An approval is a working scope, and it also records the code you approved. You and the agent can keep editing the scripts the plan lists: the gate does not block an edit, it **re-pins** the script and names the lines and numbers that changed. `verify` reports a reportable run of code no approval froze as a gap. Turn this off with `"pin_scripts": false`.

### Freeze

`freeze <hash>` is your one code review before a reportable run. It shows each changed script with its diff, scripts first pinned after approval, which steps to rerun, and which declared outputs are stale. `approve` writes a new approval whose pins are the code you reviewed. Rerun the plan, then `verify`.

### Amendment cards

A plan that only adds scripts to an earlier approval gets a change-only card. Anything else (a changed row, a new input, a folder or command grant) gets the whole card.

## Run receipts

After a covered call completes, the gate appends one line to `.mycelium-extra/receipts.jsonl`: the plans that allowed it, the script fingerprint, git state, lockfiles, environment lines, exit status and its source, outputs that changed, and the job ID for `sbatch`. `verify` reads them. Exit status comes from the host's hook event; Codex 0.160.0 gives none, so it is `unknown` and verification reports a gap. A job ID records a submission, not its outcome.

## Exploratory runs

Quick experiments belong apart from reportable runs. Type `allow explore` to let runs prefixed `MYCELIUM_EXTRA_EXPLORE=1` through for this session, and `stop explore` to end it. Without your grant the prefix is denied. Explore runs are logged and listed as not reportable, and their outputs are never promoted to results: to make them reportable, ask `grill` to promote them into a normal plan and approve a rerun.

`allow explore <plan hash>` is the scoped form: runs on that plan's own analysis paths need no new approval, however often you fix and rerun; a run outside them is denied.

## Settings

`.mycelium-extra/gate.json` takes these keys. A missing key uses its default.

| Key | Default | Meaning |
|---|---|---|
| `gated_paths` | `["analysis/**", "nbs/**"]` | Scripts under these globs need an approved plan naming them |
| `gated_commands` | `["sbatch", "snakemake", "nextflow"]` | Commands that need an approved plan containing the command word |
| `approval_hours` | `24` | How long an approval covers runs |
| `on_error` | `"allow"` | What a PreToolUse hook does when the gate itself breaks; `"deny"` blocks every call it could not check |

Optional keys, the `.mycelium-extra/` file layout, lint-on-write, command hints and Mycelium's post-action reminder are in the [complete reference](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/approval-gate-full.md#settings).

## Limits

- It catches mistakes; an agent set on bypassing it through Bash can do so.
- It reads the words of a shell command. Runs through `make`, an unlisted `bash script.sh`, or a shell expansion it cannot resolve are not traced.
- Tools other than Bash and the file-edit tools, such as MCP notebook execution, bypass both the gate and the lineage.
- A script edited after approval is re-pinned with a notice, not blocked: a covered run can execute code newer than the code you approved. `freeze` and `verify` show what changed.
- Size-and-mtime and folder fingerprints miss an edit that keeps both.
- An internal gate error fails open and says so, unless `on_error` is `"deny"`.
- A hook the host kills at its timeout (10 s for a tool call, 30 s at Stop) returns no decision: Claude Code and Codex allow the call and say nothing, whatever `on_error` says; only the OpenCode adapter applies `on_error` to a timeout. A slow network filesystem is the usual cause.

The full list is in [what it does not guarantee](concepts/not-guaranteed.md).
