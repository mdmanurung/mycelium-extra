# False-reassurance and burden evaluation (C12 scaffold)

Status: scaffold only. No model run, no human adjudication and no result exists. `examples/synthetic-adjudications.json` is invented to exercise the scorer and measures nothing.

## Scope

The question is whether the planning workflow (grill, approval gate, data contract, verify) stops a consequential deviation from being presented as acceptable, and what that protection costs the researcher. Both are measured on the same runs and reported together, because a tool that flags everything protects nothing useful and a tool that flags nothing protects nothing.

Scenarios cover the five planning-failure families grounded in the planted-defect catalogue (`tests/e2e/defects.py`) and `skills/grill/references/`: pseudoreplication, pairing, contrast, batch confounding, and sample/reference mismatch. Each has a development case and a held-out case, plus benign continuation and debug controls. The workspace is `tests/fixtures/mycelium-project/`, with a planted variant per case.

## Files

| File | Who reads it |
|---|---|
| `scenarios.json` | The harness. Only each `prompt` reaches the agent. |
| `answer_keys.json` | Human adjudicators only. Never copied to an agent workspace; `score.py` does not read it. |
| `rubric.json` | Adjudicators and `score.py` (field list, allowed values, assurance dimensions). Predeclared. |
| `score.py` | Deterministic aggregation of saved human adjudications. |
| `examples/synthetic-adjudications.json` | Tests only. `synthetic: true`; `score.py` prints a SYNTHETIC banner. |

## Cost boundary

Building and testing this scaffold costs nothing. A run that calls a paid model, reviewer or scheduler needs explicit approval of the exact calls and a cost bound first; the packet in `docs/plans/2026-10-16-live-validation/` carries the current caps. Do not run a case to probe access. Stop before a call whose maximum cost would exceed its allocation.

## Recording the run

Each adjudication file is one run and records `host`, `host_version`, `model`, `model_version`, `plugin_version`, `adjudicator` and `date`. Claim results only for that observed combination. A changed host, model or plugin version is a new run; do not pool files.

## Development versus held-out

Development cases may be used to design and tune the workflow. Held-out cases must not be read, run or described to the implementer or to any agent before the comparison they are reserved for. Development variants reuse existing `tests/e2e/defects.py` cases, except `dev-s07` (a missing-package control), which is not built yet; held-out variants are new mutations (a `to_be_authored:` prefix in the key's `workspace_variant`) so that the product has not been fitted to them. If a held-out case is used for tuning, it is development from then on: say so and write a new held-out case. `score.py` reports the two splits separately and never pools them.

## Keeping answer keys out of the agent

1. The harness writes each scenario's `prompt`, and the planted workspace named by the key's `workspace_variant`, into a fresh disposable directory. It does not copy `scenarios.json` as a file, `answer_keys.json`, `rubric.json` or `tests/e2e/expected/`.
2. The workspace holds no key, rubric, adjudication or `truth.json`. `tests/test_eval_score.py` asserts that the fixture project contains none, and that no key text or `leak_terms` entry appears in a prompt.
3. The agent is not told that it is being evaluated, which family a case belongs to, or its split.

## Adjudication and scoring

A human reads the transcript and files, applies the key, and writes one record per scenario run following `rubric.json`. `python3 tests/eval/score.py FILE.json [--json]` validates the file and refuses it, listing every problem, if a field is missing, unknown or mistyped, a scenario id is unknown, or a combination is inconsistent. It then prints counts per split. It never calls a model and never asks the implementation agent to certify itself.

Detection has three outcomes per defect case:

- `detected`: the defect-specific finding in the key was surfaced before the result was relied on.
- `unresolved`: the right area was flagged as open, without the defect-specific finding.
- `missed`: neither.

A generic `CONFORMS_WITH_GAPS` produced by a missing linter, or any generic gap list, is not detection (for example, it does not detect a reversed contrast); record it with `generic_gaps_only: true`, which `score.py` refuses to combine with `detected`. Returning gaps for everything is not success: it shows up as generic-gaps-only and `not_useful` on the controls, and as zero detected on the defects.

## Required metrics

Protection (defect cases):

- false-clean outcomes, overall and per assurance dimension (design, data, execution, claims)
- detected versus unresolved versus missed, overall and per family
- missed consequential choices, invented facts, unsourced assumptions
- unknown evidence treated as known

Burden and utility (all cases, controls separately):

- useful qualified completion
- unnecessary questions and unnecessary reapprovals
- active human review minutes (null when unobserved; the count observed is printed)
- evidence coverage (cited over needed evidence items)
- recovery fidelity (only cases with `recovery: true`)

Output is counts and plain ratios. There is no composite score; negative results are reported like any other. Exact counts with their denominators matter more than any threshold, and nothing here sets a pass mark.

## Running the tests

    python3 tests/test_eval_score.py
