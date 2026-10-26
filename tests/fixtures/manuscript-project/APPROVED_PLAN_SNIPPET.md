# Approved-plan binding sample and decision boundaries (fixture)

This is a **sample of what an approved binding looks like**, not an approval.
Adapt it to a real project and obtain researcher approval before running
anything. The wording follows the bundle's `VALIDATION_BINDING_EXAMPLE.md` and
this repository's existing `validation-bindings` format.

## Sample validation binding

```text
<!-- validation-bindings {"version": 1, "checks": [
  {
    "id": "M-FIG-001",
    "plan_row": "3",
    "required": true,
    "defined_by": "researcher-approved",
    "test_paths": [
      "skills/manuscript-audit/scripts/manuscript_audit.py",
      "config/manuscript_checks.json"
    ],
    "invocation": [
      "python3", "skills/manuscript-audit/scripts/manuscript_audit.py",
      "--root", ".", "--config", "config/manuscript_checks.json",
      "--result-json", "outputs/manuscript_audit.json"
    ],
    "evidence_path": "outputs/manuscript_audit.json"
  }
]} -->
```

The `test_paths` above name the checker inside this repository. In a research
project the plugin is not part of the repository, so copy the checker into the
project (for example `analysis/paper/tests/manuscript_audit.py`) and bind that
copy; `tests/e2e/manuscript_scenario.py` builds a worked example
(see `docs/design/2026-10-26-manuscript-native-verify.md`).

Before approval: confirm the plan row exists, the script is inside a covered
gated scope, the contract file exists, and the declared values were not chosen
after inspecting the desired result. After running: `verify <hash>` reports
whether the required check ran and what it showed. `CONFORMS` is not proof the
science is correct.

## Decision boundaries

- Researcher (human): approving the declared columns, keys and invariants;
  interpreting what a pass or failure means for the manuscript; any change to
  the scientific model.
- Agent (proposed, needs approval): constructing the figure/table map, drafting
  the contract JSON, running the read-only validator.
- Deterministic tool: declared-column presence, key uniqueness, declared
  numeric types and ratio invariants, file availability. Everything else is a
  gap or a human judgement, never a pass.

## CI route

For public small example data, run the validator in CI without the interactive
gate (CI cannot access private inputs, so a CI pass covers only what CI can
read):

```yaml
- name: Manuscript artifact checks
  run: |
    python3 skills/manuscript-audit/scripts/manuscript_audit.py \
      --root . --config config/manuscript_checks.json \
      --result-json outputs/manuscript_audit.json
```

Exit 0 passes, 2 blocks the job, 3 is a gap to investigate, 1 is a usage error.
