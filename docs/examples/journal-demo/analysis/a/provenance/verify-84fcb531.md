Written 2026-10-21 00:00 by mycelium-extra verify.

# Verify plan 84fcb531: CONFORMS_WITH_GAPS

Ran as planned  no: 1 of 2 steps ran to completion; not completed: analysis/a/scripts/01_fit.py (no receipt)  
Numbers match   n/a: no `<!-- claims -->` block names an output cell  
Code checks     not checked: Python  
Not checked     2 Validation cell(s) are prose; 4 open gap(s), first: Saved provenance bundle is legacy; no checksummed completio…; whe…  
Next            close the first gap: Saved provenance bundle is legacy; no checksummed completion established.  

Approved 2026-10-21 00:00 - analysis folder `analysis/a` - 1 run(s) under this plan - not a git repository

## Scope

- Checked against approval instance f4f5bc001b240862: 1 run(s) under it - launch evidence 1 matched, 0 unmatched, 0 ambiguous, 0 legacy (launch link not recorded).
- Qualification: **not qualified** (not established: completion, no open gap); separate from the verify status below, and not a scientific judgement.

| Evidence | State | Basis |
|---|---|---|
| authorization | established | 1 of 1 run(s) are matched launches under approval instance f4f5bc001b240862 |
| completion | not established | `analysis/a/scripts/01_fit.py` (no receipt) |
| code and input identity | established | 1 script(s) and input(s) unchanged, compared by content hash |
| lineage | not applicable | the plan declares no output (`Outputs: none`) |
| required validation | not applicable | the plan binds no check (its Validation cells are prose) |
| claim linkage | not applicable | no checked claim |
| no blocking finding | established | no finding blocks this plan |
| no open gap | not established | 4 gap finding(s) open, listed under Findings |

- Limitation: completion not established: let each planned step finish with exit 0 (a submitted batch job must reach COMPLETED), then report again. 2 of 8 dimensions are not established. 4 gap finding(s) open.

## Planned scripts

| Script | Status | Last run | Notes |
|---|---|---|---|
| `analysis/a/job.sh` | ran | 2026-10-21 00:00 | wrapper |
| `analysis/a/scripts/01_fit.py` | no receipt | ? |  |

## Outputs

No output files found for: none.

## Lint

0 `ANALYSIS_OK` waiver(s).

## Claims

No document with a `<!-- claims -->` block.

## Citations

- none found (a citation needs a DOI, a `PMID:` number or an `arXiv:` number to be checked).

## Findings

- **gap**: Saved provenance bundle is legacy; no checksummed completion established.
- **gap**: `analysis/a/job.sh` is a wrapper, and no Snakemake records show which steps ran inside it.
- **gap**: `analysis/a/scripts/01_fit.py`: no run under this plan was recorded.
- **gap**: scilintr (Python) not checked: `/nonexistent/scilintr` not found. Install it (`pip install scilintr`) and re-verify, or record its path with the init skill (`--tools --scilintr PATH`).
- **info**: Run under another plan: `python analysis/a/scripts/01_fit.py` at 2026-10-21 00:00 (under plan c9f9973e).
- **info**: Run under another plan: `python analysis/a/scripts/01_fit.py` at 2026-10-21 00:00 (under plan c9f9973e).
- **info**: Run under another plan: `python analysis/a/scripts/01_fit.py` at 2026-10-21 00:00 (under plan c9f9973e).
- **info**: Run under another plan: `python analysis/a/scripts/01_fit.py` at 2026-10-21 00:00 (under plan c9f9973e).
- **info**: Run under another plan: `python analysis/a/scripts/01_fit.py` at 2026-10-21 00:00 (under plan c9f9973e).
- **info**: Run under another plan: `python analysis/a/scripts/01_fit.py` at 2026-10-21 00:00 (under plan c9f9973e).
- **info**: Run under another plan: `python analysis/a/scripts/01_fit.py` at 2026-10-21 00:00 (under plan c9f9973e).
- **info**: Run under another plan: `python analysis/a/scripts/01_fit.py` at 2026-10-21 00:00 (under plan c9f9973e).
- **info**: Run under another plan: `python analysis/a/scripts/01_fit.py` at 2026-10-21 00:00 (under plan c9f9973e).
- **info**: Run under another plan: `python analysis/a/scripts/01_fit.py` at 2026-10-21 00:00 (under plan c9f9973e).
- **info**: Run under another plan: `python analysis/a/scripts/01_fit.py` at 2026-10-21 00:00 (under plan c9f9973e).
- **info**: Run under another plan: `python analysis/a/scripts/01_fit.py` at 2026-10-21 00:00 (under plan c9f9973e).
- **info**: Run under another plan: `python analysis/a/scripts/01_fit.py` at 2026-10-21 00:00 (under plan c9f9973e).
- **info**: Run under another plan: `python analysis/a/scripts/01_fit.py` at 2026-10-21 00:00 (under plan c9f9973e).
- **info**: Run under another plan: `python analysis/a/scripts/01_fit.py` at 2026-10-21 00:00 (under plan c9f9973e).
- **info**: Run under another plan: `python analysis/a/scripts/01_fit.py` at 2026-10-21 00:00 (under plan c9f9973e).
- **info**: Run under another plan: `python analysis/a/scripts/01_fit.py` at 2026-10-21 00:00 (under plan c9f9973e).
- **info**: Run under another plan: `python analysis/a/scripts/01_fit.py` at 2026-10-21 00:00 (under plan c9f9973e).
- **info**: Run under another plan: `python analysis/a/scripts/01_fit.py` at 2026-10-21 00:00 (under plan c9f9973e).
- **info**: No DOI, PMID or arXiv ID in the checked document(s).
- **info**: 2 Validation cells are prose only; nothing checks them.

## Not visible to verify

- A receipt's time is when the gate's hook fired. A run Claude Code moved to the background writes its outputs after that, so such outputs show as not tied to a run.
- Mycelium's lineage covers finished Mycelium sessions only.
- Code run through MCP notebook tools (`nb_*_execute`) bypasses both the gate and the lineage.
- A run of a planned script proves it ran, not that it implements the plan's choices; that is what the review step checks.
- Claims are checked only where a document's `<!-- claims -->` block names the output cell; other numbers in the text are listed, not checked, and a verified claim matches its cell, not the truth.
- A resolved citation shows that the identifier exists and that its title and first author appear in the citation text; it does not show that the paper supports the sentence citing it.
- With `snakemake --use-conda`, a rule's env is read only from a literal `conda:` path in the Snakefile or its literal `include:` files, matched to a built env under `.snakemake/conda/` by the env file's bytes; any other rule env is a gap. The folder layout was checked against one real run (Snakemake 9.27.0 with conda 24.9.2 (one real run, 2026-10-20)); other Snakemake or conda versions are not validated.
- Pip packages are read from the conda env's site-packages: one uninstalled after the run is not seen, and `pip install --user` packages under `~/.local` are not read.

Verify status: CONFORMS_WITH_GAPS
