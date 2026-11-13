---
name: research-note
disable-model-invocation: true
description: "Delegate a sourced question to a background agent that writes one cited note while you keep working. Use for method, package, annotation or dataset facts; not for analysing your data."
---

# Mycelium Extra: Research note

Hand the reading to a background agent. It checks one question against primary sources and writes one cited Markdown note. You keep working. Adapted from Matt Pocock's research skill (MIT).

The note answers from papers, docs, source code and release notes. It says nothing about what the user's own data show: such a claim stays `unsupported: no inspected figure`.

## 1. Frame the question

- Write the question in one sentence and name the decision it feeds. If the user gave a topic, turn it into a question and show it. Done when one question line exists.
- A question about the user's data or a result is analysis work. Say so and stop; point to `grill` (a plan) or `diagnose-result` when present.
- Pick the slug (`<topic>-<year>`) and the folder: `analysis/<name>/plans/research/` for a question about one analysis; otherwise the notes folder the repo already has (look for `notes/`, `docs/notes/`, `research/`); if none exists, `notes/research/`. Say the path. Done when the path is printed.

## 2. Pin versions

Read what the active environment has, with read-only queries: `pip show <pkg>`, `Rscript -e 'packageVersion("<pkg>")'`, `conda list <pkg>`; the genome and annotation release from the analysis doc or `data/SOURCES.md`. Do not load data or run analysis code. A package that is not installed is `not installed`. Done when each pin in the question has a version or `unknown`.

## 3. Launch the agent

Start one background agent from the brief in `references/agent-brief.md`. Fill in the question, the pins, the target path and the analysis folder. Done when the agent runs and the user has the target path. Then return to the user's work.

## 4. Check the note

When the agent finishes, run the format check:

```bash
sh <skill-dir>/../../hooks/py.sh - <note> < <skill-dir>/scripts/check_note.py
```

Then check the citations. With an approved plan hash, `verify` resolves every DOI, PMID and arXiv id in the note against Crossref, NCBI and arXiv. Read only its `## Citations` section:

```bash
sh <skill-dir>/../../hooks/py.sh - --plugin-root <skill-dir>/../.. report <hash> --claims <note> --resolve-citations < <skill-dir>/../verify/scripts/verify.py
```

With no plan hash, run `check_note.py <note> --ids` and look up each id with the PubMed or Europe PMC tools. Compare title and first author. Done when every reference is `resolved`, `mismatch`, `unresolved`, `no identifier` or `not checked`. A check that did not run is a gap, never a pass.

## 5. Report to the user

Give the two-line answer, the note path, the format result and each unresolved or mismatched reference. List every `unsupported: no source` row. Done when the user can tell what to trust.

- A fact that implies a different impactful choice (a filter, normalisation, model, threshold, reference release) goes to the user as a decision with the evidence beside it. Do not apply it and do not edit the plan.
- A finding enters `.living/` only when the user confirms it and `decision-status` writes it. This skill never writes there.
- If the gate blocks the note's write, report that. Do not route around it.

Detail: `references/note-format.md` (the format and an example), `references/sources.md` (what counts as a source, which tool for which question). The agent reads both.
