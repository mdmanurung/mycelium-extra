# research-note

Sends one sourced question to a background agent that writes one cited Markdown note while you keep working. The note reports what papers, docs, source code and release notes say. It reports nothing about your own data.

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`). Adapted from Matt Pocock's research skill (MIT).

```bash
<skill-dir>/../../hooks/mxpy - <note> [--ids] < <skill-dir>/scripts/check_note.py
```

The script checks a finished note against the format and exits 0 or 1. `--ids` also lists each DOI, PMID and arXiv id.

## Steps

| Step | Done when |
|---|---|
| Frame | One question line and the target path exist. A question about your data is refused and sent to `grill`. |
| Pin | Each package, genome and annotation release in the question has a version from the active environment, or `unknown`. |
| Launch | A background agent runs from the brief in `references/agent-brief.md`. |
| Check | `check_note.py` exits 0, and every reference has a citation verdict. |
| Report | You have the two-line answer, the path, the unresolved references and any decision. |

## The note

Sections in order: Question, Answer (two lines at most), Evidence, Not established, Next step, References. A `Pinned:` line under the title lists the versions and releases the answer holds for. The Evidence table has the columns Claim, Source, Quote or value, Confidence. Every Source cell names a reference id and a location, or is `unsupported: no source` with confidence `low`. Each reference line carries a version, release, year or date.

Where it goes: `analysis/<name>/plans/research/<slug>.md` for a question about one analysis, else the repo's existing notes folder (`notes/`, `docs/notes/`, `research/`), else `notes/research/`. The skill says which.

Primary sources are the paper's methods and supplement, the package's source and docs for the installed version, the release notes of the genome or annotation, and the dataset's own record. Blog posts and other write-ups are leads. The agent uses web search and the PubMed, Europe PMC, bioRxiv and UniProt tools when they are connected.

## Citation check

With an approved plan hash, `verify report <hash> --claims <note> --resolve-citations` resolves each identifier against Crossref, NCBI and arXiv. Its verdicts are `resolved`, `mismatch`, `unresolved`, `no identifier` and `not checked`. A resolved citation shows the record exists and that its title and first author appear on the reference line. It does not show that the paper supports the claim. With no plan hash, the skill lists the ids with `--ids` and looks each up through the PubMed or Europe PMC tools. A check that did not run is a gap.

## Reads and writes

The agent reads the web, the bio tools, the installed package sources and, for context, the analysis folder. It makes read-only version queries (`pip show`, `packageVersion`). It writes only the note. It does not run analysis code, load data, edit code, change a plan, or write to `.living/` or `todo/`.

## Decisions

A fact that implies a different impactful choice (a filter, normalisation, model, threshold or reference release) reaches you as `Decision for the user` in Next step. It is never applied. A finding enters `.living/` only after you confirm it through [decision-status](decision-status.md).

## Default on or off

Off until you invoke it. It adds no hook, no prompt text and no SessionStart output.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| Note shape: sections, no empty cell, defined reference ids, pinned references | Enforced by `check_note.py`, run by the skill |
| Citation resolution | Enforced by `verify` when a plan hash exists |
| That a quote is real and supports the claim | The agent's instruction; you spot-check |
| No analysis, no plan edits, no writes to `.living/` | The agent's instruction; the gate still guards gated paths |

See [verify](verify.md) for the citation check and [decision-status](decision-status.md) for recording a confirmed finding.
