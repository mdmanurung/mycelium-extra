# Design: claim-vs-artifact checking for `verify`

**Status:** draft for grilling · **Target:** `skills/verify` · **Schema:** `mycelium-extra.claims.v1`

## 1. Purpose

`verify <hash>` today answers: *did the approved plan's runs write the plan's outputs?*
The claims stage answers the next question: *do the numbers in the report match the
numbers in those outputs?*

The failure mode it catches is transcription: an agent (or a human) reads
`de_results.csv`, then writes "padj = 0.032" in the report when the table says 0.041.
This is the most common way LLM-generated text corrupts the scientific record, and it
is fully checkable with deterministic code.

Non-goals for v1: recomputing statistics, checking figures, checking claims with no
number in them ("markedly higher"), checking h5ad internals.

## 2. Pipeline

Three stdlib-only stages, Python 3.6-compatible, living in
`skills/verify/scripts/claims.py`, invoked from `verify.py`:

```
report (.md) ──► EXTRACT ──► claims[]        (value, kind, qualifier, context, line)
plan outputs ──► LOCATE  ──► artifact index  (value, file, column, row label, line)
receipts
                     │
                     ▼
                  MATCH  ──► per-claim verdict: VERIFIED / MISMATCH / UNVERIFIED / EXCLUDED
```

Entry points:

- `verify <hash>` runs the claims stage automatically when the plan's `Outputs:` line
  includes a Markdown report.
- `verify claims <report.md>` runs it standalone (read-only; no plan needed, artifacts
  taken from the analysis folder's `outputs/`).

Writes nothing during checking. On `verify <hash>`, the claims report is copied into
`<analysis>/provenance/` only with the rest of the provenance bundle, after the user
confirms — same rule as the existing `write()` step.

## 3. EXTRACT: quantitative claims from report text

### 3.1 Pre-processing

Reuse the blanking machinery from `chunk_code()`: blank fenced code blocks, inline
code spans, link targets, and HTML comments before scanning, so findings cite the
document's own line numbers. Markdown pipe tables are **not** blanked — they are
parsed separately (§3.4).

### 3.2 Number grammar

```python
NUM = r'[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][+-]?\d+)?'
```

Typed patterns, tried in order; first match wins:

| Kind      | Pattern sketch                                              | Example                        |
|-----------|-------------------------------------------------------------|--------------------------------|
| p-value   | `(p|padj|fdr|q(-value)?)\s*([<≤>=~≈])\s*NUM`                | `padj = 0.032`, `p < 0.001`    |
| percent   | `NUM\s*(%|percent)`                                         | `34%`, `12.5 percent`          |
| fold      | `NUM\s*[- ]?(fold|x)\b`, `log2\s*\(?fc\)?\s*=\s*NUM`        | `2.3-fold`, `log2FC = 1.2`     |
| count     | `n\s*=\s*NUM`, `NUM\s+(samples|cells|genes|reads|donors…)`  | `n = 48`, `1,204 genes`        |
| interval  | `NUM\s*[–,-]\s*NUM` near `CI`/`range`                       | `95% CI 0.8–1.2`               |
| effect    | `(hr|or|beta|r|r²|auc)\s*[=of]\s*NUM`                       | `HR = 0.72`                    |
| generic   | `WORDISH\s*(=|of|was|is)\s*NUM` (low confidence)            | `the mean was 4.1`             |

Each claim records: raw string, float value, qualifier (`eq`, `lt`, `gt`, `approx`),
kind, scale hint (`raw`, `percent`, `log2`, `neglog10`), decimal places of the raw
string, context tokens (sentence ± 1), line number, source (`prose` or `table`), and
confidence (`typed` or `generic`).

### 3.3 Exclusions (precision guardrails)

A number is EXCLUDED, not a claim, when any of these hold:

- preceded within a few characters by `Figure`, `Fig.`, `Table`, `Section`, `Step`,
  or inside `[...]` (citations);
- matches a year (`19xx`, `20xx`), an accession (`GSE\d+`, `ENSG\d+`, `rs\d+`),
  a genomic coordinate (`\d+:\d+`), or a version string (`\d+\.\d+(\.\d+)?` near a
  tool name or leading `v`);
- part of a date, DOI, or URL fragment;
- inside the report's own `Inputs:`/`Outputs:` provenance block, if present.

Exclusions are counted in the summary but not listed, to keep the report short.

### 3.4 Markdown tables as first-class claims

A pipe table in a report is usually a transcription of an artifact table, so it gets
the strongest check: parse it, and if any artifact table shares ≥ 50% of its header
cells, do a cell-wise diff (row-matched by first-column label where possible). Every
differing numeric cell is a MISMATCH with exact coordinates. This is the
highest-precision check in the stage and should run even when prose checking is
disabled.

### 3.5 Optional authored claims block

A report may carry an explicit claims block — HTML-comment fenced, e.g.
`<!-- claims: ... -->` with one `kind value context` per line, or a `claims.json`
sidecar. The agent writing the report is encouraged (via the skill's instructions) to
declare its load-bearing claims there. Authored claims are checked first-class with
full context; regex-extracted claims are best-effort. This keeps verification
adversarial in the right direction: the author asserts, the deterministic checker
adjudicates. An LLM is never used to extract claims from its own prose — that would
be circular for exactly the claims that matter most.

## 4. LOCATE: the artifact index

Artifacts come from the plan's receipts (files written by the plan's runs), filtered
to checkable types: `.csv`, `.tsv`, `.json`, `.txt`, `.log`. Budgets follow the gate's
philosophy (`claims_max_file_mb`, `claims_max_cells`, `claims_seconds` in
`gate.json`; a budget cut names what it skipped, and a skipped artifact is a gap,
never clean).

- **Tables** (`csv` module, delimiter-sniffed): every numeric cell is indexed with
  file path, column header, row index, and row label (first-column value).
- **JSON**: flattened to dotted paths → values.
- **Text/logs**: scanned with the same number grammar, indexed by line.

Index record: `(value, decimals, file, column, row_label, line)`.

## 5. MATCH: verdicts

### 5.1 Candidate generation

A claim value is compared against artifact values under scale-equivalence transforms,
because reports and tables legitimately use different conventions:

| Claim says      | Artifact may store | Transform tested |
|-----------------|--------------------|------------------|
| `34%`           | `0.34`             | ÷100             |
| `2.3-fold`      | `1.2` (log2FC)     | log2             |
| `p = 1e-4`      | `4.0` (−log10 p)   | −log10           |
| `0.032`         | `3.2e-2`           | identity         |

Transform matches are reported as a distinct, weaker class of VERIFIED
(`verified-transform`) so the provenance shows the convention hop.

### 5.2 Equality semantics

- **Exact/rounding:** the artifact value, rounded to the claim's decimal places
  (accepting both half-up and half-even), equals the claim value. The claim is
  treated as a rounding of the artifact — tolerance is half a unit in the last
  place, not a fixed epsilon.
- **Inequality:** `p < 0.001` is VERIFIED if the located artifact value satisfies the
  inequality, MISMATCH if a context-locked value violates it.

### 5.3 Context scoring

Candidates are ranked by token overlap between the claim's context and the artifact
coordinate tokens (file stem, column header, row label). Example: claim context
`padj, monocytes, il7r` vs. artifact `de_results_monocytes.csv : padj : row IL7R`.

- Context score ≥ high threshold + value agrees → **VERIFIED**
- Context score ≥ high threshold + value disagrees → **MISMATCH** (the payload:
  expected vs. observed, with file:column:row)
- No candidate above threshold → **UNVERIFIED**
- **Common-value guard:** claims whose value is in a frequent-value stoplist
  (`0, 1, 2, 100, 0.05, 0.01, …`) need a higher context score to verify; otherwise
  they are UNVERIFIED. Spuriously "verifying" `0.05` against any table's padj column
  is the worst failure this stage can produce.

### 5.4 Explore-artifact contamination flag

If a claim matches no reportable artifact but **does** match a value in an
explore-run output (the receipts already record explore runs), the verdict is
`verified-explore-only`. This is the mechanical catch for explore-shopping leaking
into reports — the number is real, but it is not reportable. Counted separately and
always surfaced.

## 6. Output

Human-readable, in the style of data-contract-check's alerts — one line per claim,
expected/observed/evidence for mismatches:

```
claims: reports/week3.md — 41 verified (3 via transform), 2 mismatch, 17 unverified, 63 excluded
  MISMATCH  L42  "padj = 0.032 (IL7R, monocytes)"
             expected 0.032, observed 0.041
             evidence: outputs/de_results_monocytes.csv, column padj, row IL7R
  MISMATCH  L57  table row "NK cells", column "log2FC": expected 1.8, observed 1.3
             evidence: outputs/program_usage.csv (header match 5/6)
  EXPLORE   L88  "AUC = 0.91" matches only explore-run output tmp/explore_3/auc.txt
```

Machine-readable: `claims_report.json`, schema `mycelium-extra.claims.v1`:

```json
{
  "schema": "mycelium-extra.claims.v1",
  "report": "reports/week3.md",
  "plan": "99ddfd42",
  "summary": {"verified": 41, "verified_transform": 3, "mismatch": 2,
              "unverified": 17, "explore_only": 1, "excluded": 63},
  "claims": [{"line": 42, "raw": "padj = 0.032", "kind": "pvalue",
              "qualifier": "eq", "class": "mismatch",
              "evidence": {"file": "outputs/de_results_monocytes.csv",
                           "column": "padj", "row": "IL7R",
                           "expected": 0.032, "observed": 0.041}}]
}
```

## 7. Verify semantics

Consistent with the locked decision that a missing or unparseable check is a gap,
never clean:

- Any **MISMATCH** → verify fails. The report asserts something the artifacts
  contradict; the user must fix the report or the artifact and re-run verify.
- **UNVERIFIED** claims are listed as gaps. They do not fail verify, but a report
  whose authored claims block (§3.5) is mostly unverified fails — the author said
  these were load-bearing.
- **verified-explore-only** fails verify: a non-reportable number in a reportable
  document is exactly what the explore mechanism exists to prevent.
- Budget-truncated extraction or indexing → the stage reports itself partial, which
  is a gap, never clean.
- The checker never edits the report. It never loosens a threshold to make a claim
  pass.

## 8. Limits (to document honestly)

- **Recall ceiling.** Claims without numbers, claims about figures, and claims that
  are derived statistics (a mean of two table cells, a delta between groups) will
  mostly be UNVERIFIED. The stage catches transcription errors; it does not recompute
  the analysis. v2 may recompute simple derivations.
- **False VERIFIED is the dangerous direction.** The common-value guard and context
  thresholds bias toward UNVERIFIED over VERIFIED. A verified claim means "consistent
  with a located artifact value in a matching context," not "correct."
- **Rounding conventions.** Half-up vs. half-even both accepted; a claim rounded
  *truncated* (0.0329 → 0.032) also passes, which is accepted as within-spirit.
- **Report tables copied by hand** with reordered rows are matched by row label where
  possible; unmatchable rows degrade to per-cell UNVERIFIED, not MISMATCH.
- **Numbers from outside the plan** (a value quoted from a paper) are UNVERIFIED by
  design; the authored claims block lets the author mark such claims `external` to
  exclude them from the gap count.
- Python 3.6: no dataclasses (use namedtuple), no `statistics.quantiles`, dict order
  relied on only as CPython implementation detail.

## 9. Tests

`skills/verify/tests/test_claims.py`, fixture-driven, run by name like the others:

1. Exact, rounding, and inequality matches in prose.
2. Each transform class (percent, log2, −log10) reported as `verified-transform`.
3. MISMATCH with locked context; near-miss context stays UNVERIFIED.
4. Common-value guard: bare `0.05` does not verify against an arbitrary padj column.
5. Stoplist: versions, citations, accessions, years, figure refs excluded.
6. Markdown table diff: header match, row-label match, reordered rows, cell mismatch.
7. Explore-only contamination flagged from a fixture receipt.
8. Authored claims block: checked first-class; mostly-unverified block fails verify.
9. Budget truncation reported as partial/gap.
10. All fixtures compile and run under python3.6 when available.

No gate change, so `gate_diff.py` is unaffected; run it anyway per convention.

## 10. Rollout

- **v1** (this design): prose scalars + report-table diff against CSV/TSV/JSON,
  explore-contamination flag, authored claims block.
- **v1.1:** `verify` summary line gains the claims counts; `handoff` mentions open
  mismatches.
- **v2 candidates:** recompute simple derived statistics; check figure claims against
  plot data files; h5ad-backed claims via the data-contract-check reader; optional
  cross-check of tool-version claims against receipt environments.
