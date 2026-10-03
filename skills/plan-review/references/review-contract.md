# Plan-review contract

## Canonical packet

Create one packet for both reviewers. Preserve the complete plan table and the source of every consequential choice. A compact YAML shape is:

```yaml
objective: "..."
estimand: "..."                 # or unknown with reason
study_design:
  cohorts: "..."
  longitudinal_structure: "..."
  interventions: "..."
  controls: "..."
data:
  biological_unit: "..."
  observation_unit: "..."
  sample_sizes: "..."
  modalities: "..."
  batches: "..."
known_decisions: []              # claim, source path/heading, applicability
known_findings: []               # claim, source path, status
constraints: []
proposed_plan: "complete grill brief and plan table"
assumptions: []
validation: []
unknowns: []
redactions: []
```

Do not infer a sample size, biological unit, or estimand from a code path alone. State whether each fact is user-supplied, repository evidence, or inference. Send identical factual fields to Codex and Biomni; role-specific prompts may differ. Minimize external disclosure: no raw data, participant identifiers, secrets, or unnecessary project history. If redaction removes a fact essential to review, mark that review incomplete rather than silently filling it in.

## Common reviewer response

Paste this format into the message each reviewer receives: neither reviewer can read this file (Codex runs rooted in the target repository; Biomni runs remotely). The two role-specific forms may include extra sections, but normalize each issue to:

```yaml
reviewer: codex             # or biomni
status: complete            # complete | unavailable | invalid
issues:
  - id: C1                  # preserve original reviewer ID
    severity: major         # major | minor
    domain: implementation  # or science, statistics, data, validation
    concern: "..."
    evidence: "repo path/line, packet field, or traceable primary source"
    consequence: "..."
    recommendation: "..."
    references: []          # PMID, DOI, stable primary citation when relevant
    uncertainty: "..."
questions: []
confidence_notes: []
```

Use `status: unavailable` with a reason when a reviewer cannot be reached or cannot be safely invoked. Use `status: invalid` when output cannot be attributed to the intended reviewer, lacks enough structure to recover issues, or claims work the reviewer did not do. An empty `issues` list is meaningful only with `status: complete`. Do not transform absence into agreement.

The Source column is provenance, not permission. Grill's sources are `repo:`, `user`, and `default:`; a reviewer is not a source of authority. In a later revised plan, a recommendation the user accepted is sourced as `user (accepted review: codex)` or `user (accepted review: biomni; PMID ...)`, keeping the supporting repository citation or retrievable scientific reference. The approval gate ignores Source cells; only the rest of the approved plan table can authorize gated runs.
