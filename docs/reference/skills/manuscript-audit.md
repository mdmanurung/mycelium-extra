# manuscript-audit

Read-only, source-grounded audit of a manuscript repository's data products, figure/table lineage, reproducible entry points and publication artifacts. It traces panels from inputs through the plotting script to the exact source-data file, and reports evidence-linked findings. It is not `grill`, `verify`, `data-contract-check` or `harden`, adds no hook or gate, and never runs an analysis on its own.

## Synopsis

```bash
python3 skills/manuscript-audit/scripts/manuscript_audit.py --root . --config config/manuscript_checks.json [--result-json PATH]
```

The audit itself is a skill the agent performs by reading the repository; the script is the optional deterministic part, run only as a separate user-approved command.

## Evidence classes

Every finding carries exactly one label:

| Class | Meaning |
|---|---|
| `confirmed-by-source` | Static observation read from code or data at the recorded commit |
| `test-executed` | The deterministic validator actually ran in this session and produced the cited result |
| `missing/unavailable` | The file, column or record needed could not be read or does not exist; never a pass |
| `risk/needs-data`, `preference` | Probable consequence plus a discriminating test, or a researcher-owned choice |

## The validator

A stdlib-only checker (Python 3.9+) over a declared contract (`mycelium-extra.manuscript_checks.v1`): for each figure, that the declared plotting columns exist in the declared source-data table; for each table, key uniqueness, declared numeric types, and optional numerator/denominator/fraction ratio invariants; plus availability of every declared file. Each figure declares `outputs`; an empty list marks a source-only declaration, reported as such. An unknown key at any level is a gap, so a misspelled check never silently drops out. Counts must be plain digits (`5`, not `5.0`, `+5` or `1e2`), a `tolerance` must be a JSON number, and messages name rows and columns, never cell or key values. It does not infer every plotting aesthetic, validate statistical inference, or authenticate producer execution.

Exit codes: 0 = declared checks passed, 1 = usage error (nothing was judged), 2 = a declared invariant failed, 3 = a gap (malformed or unavailable — never a pass). `--result-json` writes `mycelium-extra.contract_result.v1` to a path relative to `--root`. An absolute path, a path that leaves the project, or one that would overwrite the contract or a declared input is refused with exit 1 and nothing written. The result is read by [verify](verify.md) like any other contract result: pass requires exit 0 with no blocked check, and a gap is "not run".

## What it does not do

- It does not plan (use [grill](grill.md)), check execution records (use [verify](verify.md)), test sample-design assumptions (use [data-contract-check](data-contract-check.md)), or harden recurring failures (use [harden](harden.md)).
- It does not activate a convention pack. The opt-in `manuscript-reproducibility` pack is guidance grill may read when it is installed and registered; its presence is not a validation result. See [Gaps and passes](../../concepts/gaps-and-passes.md).
- A pass never means the science is correct or that a figure reproduces the paper end to end.
