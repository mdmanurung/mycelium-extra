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

Do not infer a sample size, biological unit, or estimand from a code path alone. State whether each fact is user-supplied, repository evidence, or inference. Send identical factual fields to Codex and Biomni; role-specific prompts may differ. Minimize external disclosure (see Redactions below). If redaction removes a fact essential to review, mark that review incomplete rather than silently filling it in.

## Redactions and the pre-send check

Leave out of the packet: raw data; participant identifiers (participant, donor and sample IDs, including the values in the ID columns of the tables the plan names under `Inputs:`); credentials, tokens, keys and URLs that carry a password; contact details; home-directory paths and host names that name a person or an account (use repository-relative paths); unpublished full tables and count matrices; free-text clinical notes; dates that tie a record to a person; and project history the review does not need.

`redactions:` lists what was removed or replaced, one entry per item, as `- kind: <participant id | secret | contact | path | table | other>, field: <packet field>, replaced_with: <placeholder>`. Require nonempty `kind` and `field` strings; `replaced_with` is optional. The helper accepts a JSON list of objects or YAML entries with one field per line. Never write the removed value there. `[]` means nothing was removed, and is acceptable only after the check below ran and flagged nothing.

Before the packet is shown to the user for consent, run `scripts/presend_check.py` on it (see `SKILL.md`); `--json` gives the same result as one structured object, with the packet's SHA-256 and the unread or unsupported inputs named by masked name and reason. Its exit status decides what happens next:

| Exit | Meaning | Do |
|---|---|---|
| 0 | nothing flagged, and exactly one well-formed `redactions:` line | Say the check is pattern-based and a clean result is not evidence that nothing sensitive remains. |
| 2 | flagged, and `redactions:` lists what was removed | Show the flags and the redactions to the user, who decides whether to send. |
| 3 | flagged with empty/malformed redactions; no single `redactions:` line (even with nothing flagged, so write `redactions: []`); or missing/truncated input coverage | Do not send. Remove or replace each flagged value and record it, or tell the user why it must stay. |
| 1, or a failed run | the check did not run (exit 1 with `mycelium-extra needs Python 3.9 or later` on stderr is `py.sh` finding no suitable Python: set `MYCELIUM_EXTRA_PYTHON`) | Say so. Never report it as clean. |

The check reads the packet, and the tables named under `Inputs:` when given `--repo`, and prints each flag with its line, kind and a masked value. Its patterns are listed at the top of the script, and so are the things it cannot catch (a secret with no recognisable shape, a name or a diagnosis in free text, an identifier in a table the plan does not name). It does not stop a reviewer from reading files outside the packet; for Codex see [codex-review.md](codex-review.md).

## Payload and attachment boundary

What a reviewer receives is exactly the files `review_packet.py verify` prints, plus the skill's own fixed role prompt and response format:

- `packet.txt`: the packet, byte for byte as scanned. `presend_check.py` and the manifest record its SHA-256, so an edit after the scan or after consent changes the hash and `verify` refuses.
- `workspace/<repo-relative path>`: each explicitly selected code or document attachment, copied at `prepare`. Only the allowlisted types (`ALLOWED_EXT` in the script), under 1 MB each, and never from `data/`, `.git/`, `.mycelium-extra/` or `.ssh/`. A symlink that resolves outside the project or into those directories is refused. The workspace is data-free by construction: it holds only what was selected, not the repository.
- Nothing else. An unlisted file in the packet folder is reported and refused. Biomni receives the packet text only and no files. Codex is rooted in the workspace copy, not the repository (see [codex-review.md](codex-review.md)).

The digest is the SHA-256 of `manifest.json`, which records the packet's hash and each attachment's path, size and hash. The user's prompt `send packet <digest12>` is the consent. The approval gate records it as `.mycelium-extra/review-consent/<digest>.json` (`schema` `mycelium-extra.review-consent.v1`, `digest`, `session_id`, `ts`, `prompt`); the scripts only read it, and never write one. Without that record `verify` refuses. Read-only access to the original repository still exposes whatever can be read there; this boundary covers only what the supported send route is given. It is a cooperative mechanism, not a sandbox, and it does not cover other transports.

## Common reviewer response

Paste this format into the message each reviewer receives: neither reviewer can read this file (Codex runs rooted in the data-free workspace copy; Biomni runs remotely). The two role-specific forms may include extra sections, but normalize each issue to:

```yaml
reviewer: codex             # or biomni
status: complete            # complete | pending | unavailable | invalid
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

Use `status: unavailable` with a reason when a reviewer cannot be reached, cannot be safely invoked, or was not sent because `verify` refused. Use `status: pending` for a launched review that has not finished. Use `status: invalid` when output cannot be attributed to the intended reviewer, lacks enough structure to recover issues, or claims work the reviewer did not do. An empty `issues` list is meaningful only with `status: complete`. Do not transform absence into agreement.

The Source column is provenance, not permission. Grill's sources are `repo:`, `user`, and `default:`; a reviewer is not a source of authority. In a later revised plan, a recommendation the user accepted is sourced as `user (accepted review: codex)` or `user (accepted review: biomni; PMID ...)`, keeping the supporting repository citation or retrievable scientific reference. The approval gate ignores Source cells; only the rest of the approved plan table can authorize gated runs.

## Material objection classification

An issue is **material** when accepting or rejecting it would change a consequential choice in the plan. Material issues are ranked, not counted, and each carries four fields plus one status, whether the reviewer supplied them in this shape or not (recover them from the reviewer's prose, and say when a field could not be recovered):

```yaml
- id: C1
  affected_choice: "the step and the consequential choice it would change"
  evidence: "repo path/line, packet field, or traceable primary source"
  inferential_consequence: "what the result would mean if the concern holds, in plain scientific terms"
  discriminating_check: "the observation, test, or artifact that would settle it"
  status: unresolved            # substantiated | refuted | unresolved | out_of_scope
```

Statuses, applied by the lead host with evidence, never by vote or severity:

- `substantiated` — the evidence supports the concern and the discriminating check is available.
- `refuted` — the plan or the repository already answers it; cite what refutes it, with the path or line.
- `unresolved` — the concern stands and the discriminating check cannot settle it before execution.
- `out_of_scope` — it concerns a choice this plan does not make (a later milestone, a different deliverable). Name where it belongs instead of arguing it.

Non-material issues — wording, style, optional improvements — stay in the reviewer's own list and are never promoted to cruxes.

The synthesis leads with the strongest `unresolved` crux: the material objection with the largest inferential consequence that the check cannot settle. Exactly one. Then list the rest. When every material objection is `refuted` or `out_of_scope`, say `no substantiated material concern` in the summary line — that is a statement about the objections raised, never about the plan's correctness, and it does not replace any reviewer's status.
