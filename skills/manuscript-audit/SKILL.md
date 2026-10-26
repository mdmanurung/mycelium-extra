---
name: manuscript-audit
description: Audit a manuscript repository read-only, tracing each figure or table from inputs through its script to the source-data file. Use for source-data, figure-lineage or publication-readiness reviews; not for planning (grill), run records (verify) or sample design (data-contract-check).
---

# Mycelium Extra: manuscript-audit

This skill is a **read-only review**. It is not `grill`, `verify`, `data-contract-check` or `harden`, and must not override those skills or their approval semantics. It adds no hook, gate, or authorization path.

## 1. Establish the repository and policy scope

Read README, `AGENTS.md`/`CLAUDE.md` and, in a Mycelium project, `.living/conventions.md` and `.living/conventions/ACTIVE_CONVENTIONS.yaml`; read only the relevant **installed and registered** `manuscript-reproducibility` and domain guides. A downloaded or unregistered pack is **not active**; say so rather than implying activation. Respect repo-local scientific decisions over general pack suggestions. Record the inspected commit SHA and the analysis/citation scope.

## 2. Inspect actual code, not only filenames

Find the paper's figure/table map or construct an **explicitly proposed** one. Read representative full scripts/notebook code cells to trace two panels end to end: inputs → transformations → statistical result → figure script → exact plot source → panel file. Inspect scientifically consequential operations: replicate unit, raw counts vs normalized data, denominators, contrasts, model formula/heterogeneity, batch confounding, annotation edits and factor-score feature matching. Do not guess unavailable private datasets or treat a source file's presence as evidence it was executed.

## 3. Findings with evidence classes

Label every finding with exactly one evidence class, and keep the labels honest:

- `confirmed-by-source` — static observation: a fact read from the code or data at the recorded commit, with file path and exact expression/line. A concern raised by a code pattern is not a confirmed error in the paper's conclusions.
- `test-executed` — an executed check: the deterministic validator below actually ran in this session and produced the cited result. A check that was only proposed or planned is never this class.
- `missing/unavailable` — data unavailable: the file, column or record needed could not be read or does not exist. Never a pass.
- `risk/needs-data` and `preference` — probable consequence plus a discriminating test, or a stylistic choice owned by the researcher. Interpretation of what a finding means for the manuscript is the researcher's decision, not the agent's.

Record both positive reproducibility features and issues, with severity and owner (agent/human).

## 4. Optional deterministic checks, never disguised as background verification

For actual execution, offer a separate user-approved command:

```bash
python3 <skill-dir>/scripts/manuscript_audit.py --root . --config config/manuscript_checks.json --result-json outputs/manuscript_audit.json
```

Exit 0 = declared checks passed, 1 = usage error (nothing was judged), 2 = a declared invariant failed, 3 = gap (malformed or unavailable — never a pass). The tool checks ONLY declared figure-source columns, declared small keyed tables with count/fraction invariants, and file availability. It does not infer every plotting aesthetic, validate statistical inference, or authenticate producer execution; its result JSON (`mycelium-extra.contract_result.v1`) is read by `verify` like any other contract result. A planned check is not a performed check.

For sample design and batch/pairing use `/mycelium-extra:data-contract-check` rather than reimplementing. For expected-vs-executed model-field agreement use `skills/verify/scripts/method_fidelity.py` (which does not authenticate arbitrary fits). For recurring validated failures use `/mycelium-extra:harden`; require deliberate failing and passing fixtures before claiming structural mitigation.

## 5. Output format

Return a concise evidence table: finding ID, evidence class, verified source, potential consequence, suggested test, and whether that test actually ran. Include a figure/table map and a `Not established` section listing failed data retrieval or execution. Classify each proposed intervention as `convention`, `skill advice`, `deterministic check`, or `human scientific decision`. Offer an implementation brief with adoption levels (exploration, finalising, publication). Do not write files without explicit authorisation and, where installed, gate review. Never claim an installed plugin or activated convention pack unless repository activation is confirmed.

## 6. Host and privacy boundaries

A read-only audit grants no permission to run notebooks, send data or model training to a service, change `.living/`, or approve execution. Avoid quoting donor identifiers or controlled datasets in an audit report. Hooks, where installed, are an observation/consent guard for covered tools, not a general sandbox or correctness proof.
