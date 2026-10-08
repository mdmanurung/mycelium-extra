# Verification reference

Use this page when you need to interpret a `verify` report or record provenance.
For the everyday workflow, start with [Usage tiers](usage.md#tier-3-verify-reportable-work).


A finished job is only the beginning of checking an analysis. Did every planned step run? Did an input change? Does the number in the write-up match the saved table? After execution, `verify <hash>` compares the approved plan with the records that can answer those questions.

It uses the gate's own table parser, so the scripts covered by verification are the same ones covered by approval. It reads the record without re-running the analysis. In Codex 0.160.0, missing hook exit metadata remains a gap even when the command appeared to finish successfully.

**In this section:** [What the report shows](#what-the-report-shows) · [Status](#status) · [What it writes](#what-it-writes) · [Stale plans](#stale-plans) · [Overview of all plans](#overview-of-all-plans)

## What the report shows

- **Each planned script** (a path in the plan table with a script extension, a `Snakefile` name, or a `#!` line; another file it names, such as a log to read or a README, is not one): ran, failed, no receipt, edited or deleted since it ran, or only passed to other code. A lint or parse call (`Rscript -e 'lintr::lint()' x.R`) or another tool's script read from stdin gets the path but does not run it, so it is not counted as a run. Steps run inside a `run.sh` or Snakemake wrapper are matched through Snakemake's per-output records, and Slurm jobs through `sacct`.
- **Other runs:** explore runs, runs under another plan, and scripts in the analysis folder that ran but are not in the plan table.
- **Pinned inputs** that changed since the approval.
- **Outputs:** the files on the plan's `Outputs:` line, when each was written, and which run likely wrote it. A `{a,b}` list is expanded and a `<name>` placeholder read as `*`; a word starting with `…` names no path and is a gap (the approval card flags it too). A file named exactly that was written before the approval blocks. Older files inside a named folder or glob are earlier runs' outputs, so they are counted, not checked.
- **Unreceipted runs:** scripts that Mycelium's lineage saw run in the window but the gate did not, such as scratchpad scripts.
- **Lint:** scilintr on the analysis folder's code, as Mycelium's analyze skill requires, with every `ANALYSIS_OK` waiver listed.
  - Python goes through the scilintr CLI. R goes through `scilintr::lint_project()` on a copy of the R code, since scilintr 0.1.1's `main()` lints only its first argument and always exits 0.
  - Jupyter notebooks' code cells are linted too, with magics commented out. A finding is cited as `<notebook>.ipynb[code cell N]:<line>`.
  - The `{r}` and `{python}` chunks of `.qmd` and `.Rmd` files are linted as well, cited by the document's own line.
- **Claims:** each `<!-- claims -->` block in the analysis doc, a Markdown output, or a `--claims` document names a value and the output cell it came from (`8 | outputs/summary.tsv n_hits`, `0.0162 | outputs/de_results.tsv padj SIGLEC1`). A value is checked against its cell after rounding. A table with more than one row needs a row label, so a common value cannot match some row by chance. Other numbers near the block are listed, not checked.
- **Fact tags, as info:** per tag, how many facts in the frozen plan's Evidence and in the analysis doc's Key Findings carry `[human-stated]`, `[agent-derived: <path>]`, or `[agent-asserted: <source>]`. It flags an untagged fact, an `agent-derived` one without its path, and an `agent-asserted` one without a source. A list with no tag at all (a plan from before 0.9.35) gets one line. The status does not change.

## Status

It ends with `Verify status: CONFORMS`, `CONFORMS_WITH_GAPS`, or `DOES_NOT_CONFORM`.

- **Blocks:** a failed run, an edited script, a changed input, an output older than the approval, an incomplete Snakemake job, a scilintr finding neither fixed nor waived, a claim its cell contradicts, or a claim read from an explore run's output.
- **Gaps:** things the records cannot show. These include code scilintr could not check: scilintr not installed, timed out, or with unreadable output, or a script or notebook whose code does not parse, under the Python verify runs on or under R (which scilintr would silently pass). An output is tied to a run by time alone, so attribution only ever produces gaps.

## What it writes

After you confirm, `verify` writes `<analysis>/provenance/`:

- the frozen plan;
- its receipts (ones that only passed a planned path to other code are kept, marked `not_a_run`);
- an outputs table with each file's size, full sha256, and likely run;
- the scilintr output and waivers (`lint-<hash>.txt`);
- the package list of any conda env a run used that no `conda-lock.yml` pins (`env-<hash>.txt`, read from the env's `conda-meta`; an env changed since the run is a gap);
- the pip packages in such an env that conda did not install, locked or not (`pip-<hash>.txt`, in requirements format);
- the report, and a `PROVENANCE.md` index.

Commit it with the analysis. It never writes `PLAN.md`, `TRACKER.md`, or `specification.md`, so the analysis keeps one plan file. It then names the review command, `/mycelium:review <folder> — check the code against the approved plan in <folder>/provenance/plan-<hash>.md`.

## Stale plans

`verify stale` sweeps every verified plan. It lists the ones whose scripts, pinned inputs, or outputs changed since their provenance was written. For each, it gives a ready `rg` command that finds the findings resting on it in `.living/findings/`, by session ID or plan hash.

After a planned run in a Mycelium repository, the gate suggests writing the finding's Evidence Ledger Run/Session cell as `<session-id>; plan <hash>`, and ending its Result cell with `[agent-derived: <output path>]`. Mycelium reads only the ledger's date cell.

`verify stale` reads only committed provenance, so it works without the gate on any clone. Outputs are compared by size and time, not hashed.

## Overview of all plans

`verify status` is an on-request overview, with one row per approved or verified plan. Each row shows:

- its analysis folder, runs, verify status, and staleness;
- the lint verify recorded (a missing or unreadable linter shows as a gap, never `clean`);
- the folder's `ANALYSIS_MANIFEST.md` entry: `listed: <first status word>`, `listed`, or `not listed`. It reads Mycelium's YAML `status:`, `**Status**:` lines, and a table's Status cell.

No hook runs it.

One limit: an output is tied to a run by time, since receipts do not record which files a run wrote.
