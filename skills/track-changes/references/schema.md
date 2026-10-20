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

## Analysis Journal v1

`--journal --json` prints **only** `mycelium-extra.analysis-journal.v1`,
independent of UI expansion, search and paging. The generated snapshot.json
retains the ordinary comparison with an additional `journal` member. Ordinary
mode and its independent difference/authorization/attribution/unknown axes keep
their meaning. Historical endpoint selection for the Review comparison is the
earliest available approval when `--original` is absent; this is a display
baseline, never a judgement of original intent. Journal history includes
intermediate plans, rather than only that pair.

The journal holds analysis_path, objective, refreshed_at, snapshot_digest,
events, source coverage, checkpoint catalog, notes, note_observations,
collection (loaded/omitted/limit) and limitations. No durable record cap applies.
UI lists page by 30 and display exact loaded, matching, collapsed and omitted
counts; search covers every loaded event across periods.

Each event has a full `journal:<kind>:<sha256>` id, kind, source_identity,
source_digest, references (plan, instance, attempt, session when available),
summary, detail, limitations, attribution and independent axes. IDs hash the
analysis path, source namespace/native identity and full canonical source-record
digest. Canonical JSON is ASCII-escaped, sorted-key, compact JSON without NaN.
Native attempt, instance and focus IDs are namespaced; a legacy record without
an ID uses its complete record digest. Exact local/committed copies merge;
`not_a_run` is an export annotation excluded from receipt identity. Two variants
of one logical source retain distinct full IDs and an explicit conflict limit.
Sharing a script alone establishes no ownership; matched plan context, declared
focus-only context and multi-analysis attribution stay distinct.

`occurred_at` is a recorded source timestamp, or null. `timestamp_basis` names
that basis. `observed_at` stays null until a saved observation supplies a date;
no scan invents a first detection date. `refreshed_at` and report generated_at
are observation freshness only. Handoffs supply their saved observation time;
verification computation time is not separately attested. File mtime is never
an attested edit/production time. Equal timestamps give no causal ordering.

Coverage states are available, partial, absent, malformed, interrupted,
unsupported or not inspected. They describe inspected **source groups**, not
scientific quality or complete history. Legacy Markdown verification is partial
and is not parsed into a new verdict. A pending/mismatching publication is
interrupted and contributes no new verification observation. Earlier saved
projections remain available. No scheduler, transcript, network or verification
process is called. The UI's persistent indicator retains missing completion,
incomplete sources and saved-context freshness even outside the selected period.

## Checkpoints and notes

`--journal --save-checkpoint` writes
`<analysis>/journal/checkpoints/<full-semantic-digest>.json` plus `.save.lock`.
It requires journal mode and conflicts with `--no-write` and `--explain` before
any mutation. Use `--journal --no-write` for repository-state-free collection
(no cache, recovery or lock creation). Ordinary report paths are unchanged.

`mycelium-extra.analysis-checkpoint.v1` contains schema, digest, saved_at,
payload, original source_references and per-event observation_times. The digest payload is schema,
analysis_path, objective, canonical event projections, notes and their current
observations, fixed limitations
and inspected source coverage excluding the checkpoint catalog. Event projections
exclude observed_at, source locations and present-day original-evidence
availability. Scan/save clocks, catalog changes, imported checkpoint documents
and the act of saving do not enter identity. Imported checkpoints merge their
observations; they are never nested. Digests and event identities are validated
on read. Unchanged explicit saves reuse the first file and saved_at. The existing
short lock plus complete atomic write serializes create-if-absent saves. Different
semantic payloads retain both files. A correction is a new record; it never
rewrites an earlier checkpoint. Commit checkpoints to retain history when
same-plan public provenance files are replaced or ignored local state is lost.
Compact embedded verification projections survive loss of original files;
original-evidence availability is shown separately. These are editable repository
observations, not tamper-proof attestations or a certification of completeness.

`--note RELATIVE_PATH[#ANCHOR]` is repeatable and requires journal mode. Paths
are relative to the repository root, must name Markdown and remain contained
after symlink resolution. Absolute paths, parent traversal, backslashes, control
characters and URI schemes are refused. Anchors remain inert reference text;
there is no note parser/editor. A digest records the note bytes; changed/missing
notes are displayed without changing the saved reference. Notes never authorize
execution. The report uses copyable paths, with no editor-command or executable
links. Explicit new references may record an absent note; that absence is visible.

The default period is observations absent from the latest saved checkpoint;
otherwise the latest recorded focus session's time window (unknown times remain
included); otherwise clearly labelled available history. All history is an
explicit alternative. A checkpoint is an observed-record baseline, not a promise
that every event after its save time was collected.
