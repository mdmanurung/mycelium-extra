---
name: manuscript-audit
description: Audit a manuscript repository read-only, tracing each figure or table from inputs through its script to the source-data file. Use for source-data, figure-lineage or publication-readiness reviews; not for planning (grill), run records (verify) or sample design (data-contract-check).
---

# Mycelium Extra: manuscript-audit

This skill is a **read-only review**. It is not `grill`, `verify`, `data-contract-check` or `harden`, and must not override those skills or their approval semantics. It adds no hook, gate, or authorization path.

## 1. Establish the repository and policy scope

Read README, `AGENTS.md`/`CLAUDE.md` and, in a Mycelium project, `.living/conventions.md` and `.living/conventions/ACTIVE_CONVENTIONS.yaml`; read only the relevant **installed and registered** `manuscript-reproducibility` and domain guides. A downloaded or unregistered pack is **not active**; say so rather than implying activation. Respect repo-local scientific decisions over general pack suggestions. Record the inspected commit SHA and the analysis/citation scope.

## 2. Inspect actual code, not only filenames

Find the paper's figure/table map or construct an **explicitly proposed** one. Read full scripts/notebook code cells to trace at least two panels end to end, chosen to cover the main claim and the most complex transformation (list the panels not traced under `Not established`): inputs → transformations → statistical result → figure script → exact plot source → panel file. Inspect scientifically consequential operations: replicate unit, raw counts vs normalized data, denominators, contrasts, model formula/heterogeneity, batch confounding, annotation edits and factor-score feature matching. Do not guess unavailable private datasets or treat a source file's presence as evidence it was executed.

## 3. Findings with evidence classes

Label every finding with exactly one evidence class, and keep the labels honest:

- `confirmed-by-source` — static observation: a fact read from the code or data at the recorded commit, with file path and exact expression/line. A concern raised by a code pattern is not a confirmed error in the paper's conclusions.
- `test-executed` — an executed check: the deterministic validator below actually ran in this session and produced the cited result. A check that was only proposed or planned is never this class.
- `missing/unavailable` — data unavailable: the file, column or record needed could not be read or does not exist. Never a pass.
- `risk/needs-data` and `preference` — probable consequence plus a discriminating test, or a stylistic choice owned by the researcher. Interpretation of what a finding means for the manuscript is the researcher's decision, not the agent's.

Record both positive reproducibility features and issues, with severity and owner (agent/human).

## 4. Optional deterministic checks, never disguised as background verification

The checker reads a contract, `config/manuscript_checks.json` (schema `mycelium-extra.manuscript_checks.v1`; keys and an example in [the reference page](../../docs/reference/skills/manuscript-audit.md)). `new-analysis --panels` scaffolds one; in any other repository, propose the contract to the user and write it only when they approve, like any file. Published fractions are compared at a tolerance of 1e-8 unless the table declares `tolerance`, so rounded values need one.

Two ways to run it, never a third:

- **Ad hoc, before approval**: stream the script on stdin so no file in the repository runs by path (running a script by path opens Mycelium's post-action cycle) and write no file:

  ```bash
  sh <skill-dir>/../../hooks/py.sh - --root . --config config/manuscript_checks.json < <skill-dir>/scripts/manuscript_audit.py
  ```

  Its result is a `test-executed` finding for this session only; `verify` cannot attribute it to a plan.
- **Bound to a plan**: copy the script into the project (for example `tests/manuscript_audit.py`), list the copy and the contract in a validation binding's `test_paths`, and let the approved step run that copy by path with `--result-json outputs/manuscript_audit.json`. The gate pins the copy and matches the exact argv, and `verify` reads the result like any other contract result: exit 0 with no blocked check is a pass, a gap is "not run".

Exit 0 = declared checks passed, 1 = usage error (nothing was judged), 2 = a declared invariant failed, 3 = gap (malformed or unavailable — never a pass). The tool checks ONLY that declared files exist, that declared plotting columns are present in the declared source-data table, and key uniqueness, digit-only counts, finite numerics and a numerator/denominator/fraction invariant on declared small tables. It does not infer every plotting aesthetic, validate statistical inference, or authenticate producer execution. A planned check is not a performed check.

For sample design and batch/pairing use `/mycelium-extra:data-contract-check` rather than reimplementing. For expected-vs-executed model-field agreement use `skills/verify/scripts/method_fidelity.py` (which does not authenticate arbitrary fits). For recurring validated failures use `/mycelium-extra:harden`; require deliberate failing and passing fixtures before claiming structural mitigation.

## 5. Output format

Return a concise evidence table: finding ID, evidence class, verified source, potential consequence, suggested test, and whether that test actually ran. Include a figure/table map and a `Not established` section listing failed data retrieval or execution. Classify each proposed intervention as `convention`, `skill advice`, `deterministic check`, or `human scientific decision`. Offer an implementation brief with adoption levels (exploration, finalising, publication). Do not write files without explicit authorisation and, where installed, gate review. Never claim an installed plugin or activated convention pack unless repository activation is confirmed.

## 6. Host and privacy boundaries

A read-only audit grants no permission to run notebooks, send data or model training to a service, change `.living/`, or approve execution. Avoid quoting donor identifiers or controlled datasets in an audit report. Hooks, where installed, are an observation/consent guard for covered tools, not a general sandbox or correctness proof.
