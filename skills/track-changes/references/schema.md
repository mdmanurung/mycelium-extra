# track-changes snapshot, `mycelium-extra.track-changes.v1`

`snapshot.json` is a disposable, regenerable view. It is not an authoritative record and nothing reads it back as state. Item ids are a hash of (kind, subject, evidence keys), so they do not change when the snapshot is regenerated later.

## Top level

| Field | Meaning |
|---|---|
| `analysis_path` | The folder this report is about (a focus, or `--analysis`). |
| `objective` | `{text, source}` quoted from the analysis doc; `text` is null when the doc states none. |
| `focus` | `{active_at_snapshot, focus_id, started_at}`. A focus gives context only. |
| `baselines` | `original_plan`, `current_plan`, `current_instance`, `relation` (`explicit`, `single_candidate`, `none`). A plan is a candidate only when its table names a path inside the folder. |
| `coverage` | What was and was not read: `focus_events`, `approvals`, `snapshots`, `receipts`, `claude_transcript` (`not_requested`, `available`, `partial`, `unavailable`), `limitations[]`, `not_observed[]`. |
| `counts` | Items per bucket. |
| `items`, `evidence`, `timeline` | See below. |

## Item

`bucket` is for filtering only: `attention` (a researcher should look), `authorized` (differs from the original but is frozen into the current approval), `routine`.

Independent axes, never one badge:

| Axis | Values | Constraint |
|---|---|---|
| `difference` | `observed`, `unavailable` | A changed number is an observed edit, not a changed conclusion. `unavailable` means no baseline was kept. |
| `focus_relation` | `within_path`, `outside_path`, `unknown` | Out of the folder is not out of scope. |
| `semantic_relation` | `unassessed` | No automated science verdict exists. |
| `authorization_relation` | `covered_current`, `not_established`, `not_applicable` | Whether the current approval pins or authorizes it. |
| `historical` | `different_original`, `no_baseline`, `not_applicable` | Differs from the original plan or code. Can be true together with `covered_current`. |
| `consequence` | `potential`, `unknown`, `not_assessed` | There is no `observed` consequence: this tool measures none. |
| `attribution` | `direct_tool`, `contextual`, `unattributed`, `not_applicable` | `direct_tool` is a direct editor call in the transcript; `contextual` came from a subagent. Shell edits are never attributed. |
| `currency` | `older_than_change`, `unknown`, `not_checked` | A file time never shows that code produced an output. |

Text fields: `summary`, `observed`, `potential`, `unknown`, `baseline`, `current`, `authorization`, `context`, `next[]` (drafts only), `limitations[]`. `diff` is `[["add"|"del"|"ctx", line]]`, bounded and redacted.

## Evidence and timeline

`evidence[]`: `{id, source, ref, detail, ts}` pointing at the record behind a statement (approval, pin, script, receipt, re-pin, transcript edit). `timeline[]`: `{ts, when, kind, text, ref}`; order is not causation, consent or authorship.

## Not stored

Prompt text, command text and arguments, transcript content, whole source files, and strings that look like keys, tokens or passwords (replaced by `[redacted]`, and counted in `coverage.limitations`).
