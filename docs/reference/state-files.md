# State files reference

mycelium-extra keeps its working records in two places:

- `.mycelium-extra/` at the project root: short-lived execution state written by the gate and a few skills. `init` adds it to `.gitignore`. It stays local to the clone and is not project knowledge.
- `provenance/` inside an analysis folder: the permanent record `verify write` saves after you confirm. Commit it with the analysis.

The agent cannot write into `.mycelium-extra/` through the file tools, and the gate denies the shell forms it recognises ([Gate](gate.md#forms-the-gate-does-not-trace) lists the exceptions). Only the user's typed commands and the gate's hooks write approvals.

**The last column is a proposal.** "Proposed 1.x" means the 1.0.0 review recommends keeping the file readable by every 1.x release. It is not a promise yet; the human decides at 1.0. "No" means the format may change in any release.

The `.jsonl` logs and `explore.log` only grow. Nothing trims them.

## `.mycelium-extra/`

| Path | Written by | Read by | Holds | Proposed 1.x |
|---|---|---|---|---|
| `gate.json` | you (`init` creates it once) | gate, `init --diagnose`, `verify` | the settings ([gate.json](gate-json.md)) | Yes: the 15 keys |
| `approvals/<hash>.json` | gate, on your `approve` | gate, `verify`, `track-changes` | the approved plan text, its pins and script pins, session, time. Never deleted. | Yes, readable forever |
| `approval-instances/<hash>/<id>.json` | gate, on your `approve` | `verify`, `track-changes` | the immutable freeze of one approval (`mycelium-extra.approval-instance.v1`) | Yes (v1) |
| `approvals.jsonl` | gate | nothing | one latency line per approval | No |
| `pending/` | gate | gate, `verify` (plans shown but not approved), `handoff` (by content) | per session: plans shown (text, pins, card). Also hidden bookkeeping files per session: `<session>.lint/` (open lint findings per script), `.lint-shown`, `.lint-note-*`, `.lint-stop-blocked`, `.focus-notices.json`, `.explore-seen`, `.hints.json`, `.checkpoint` | Yes for the plan entries; the bookkeeping files are not promised |
| `script-pins/<hash>.json` | gate | gate, `verify` | scripts pinned at their first covered run, until the plan is approved again | Not listed |
| `scripts/` | gate | `verify`, `track-changes` | kept copies of pinned scripts up to 256 KB, for diffs | Not listed |
| `repins/<hash>.jsonl` | gate | `verify`, `track-changes` | append-only journal of scripts re-pinned after an edit | Yes, readable forever |
| `receipts.jsonl` | gate (post hook) | `verify`, `track-changes`, `init --diagnose` | one line per covered run (`mycelium-extra.receipt.v1`) | Yes (v1). Older receipts with no exit status or no `launch_match` must stay readable. |
| `launches/` | gate (pre hook) | gate (post hook), `verify` | one record per gated launch until its call reports back; `launches/abandoned/` keeps records never taken | Not listed |
| `denies.jsonl` | gate | nothing | one line per denied tool call | No |
| `gate-errors.jsonl` | gate hook entry point (`gate_run.py`) | `verify` (a gap in the plan's window), `init --diagnose` | internal gate errors | Not listed; `verify` reads it, so decide at 1.0 |
| `explore-grants/<session>.json` | gate, on `allow explore` | gate | the session's explore permission, with its scope if bounded | No |
| `explore.log` | gate | gate (Stop notice) | one line per explore run | No |
| `hints.json` | gate, on `hints on` | gate | the hints switch | No: hint rules are not frozen |
| `tools.json` | `init --tools` | gate, `verify` | where `scilintr` and an `Rscript` with scilintr are | Not listed |
| `focus/<session>.json` | gate, on your `focus` commands | gate, `track-changes` | which analysis a session declared, with its history (`mycelium-extra.focus.v1`) | Not listed |
| `locks/` | gate, focus | the same writers | write locks | No |
| `review-packets/<digest>/` | `plan-review`'s `review_packet.py prepare` | `review_packet.py preview` and `verify` | the immutable packet, selected attachments and a manifest of hashes | Not listed |
| `review-consent/<digest>.json` | gate, on your `send packet` | `review_packet.py verify` | your consent to send one prepared packet (`mycelium-extra.review-consent.v1`) | Yes (v1) |
| `track-changes/<analysis>/snapshot.json` | `track_changes.py` | you, `grill` (via `brief.md`) | the machine-readable change snapshot (`mycelium-extra.track-changes.v1`) | Yes |
| `track-changes/<analysis>/brief.md`, `report.html` | `track_changes.py` | you, `grill`, `handoff` (as pointers) | the review brief and the offline report | Format yes, wording and layout no |

## `provenance/` (in an analysis folder)

Written only by `verify write <hash> --analysis-dir <folder>`, after you confirm. Writing again for the same plan replaces that plan's files and row.

| File | Holds | Proposed 1.x |
|---|---|---|
| `plan-<hash>.md` | the frozen plan as approved | Yes |
| `receipts-<hash>.jsonl` | the receipts of that plan's runs | Yes |
| `outputs-<hash>.tsv` | each output's path, time, size, hash, and the run named as its producer with the evidence | Yes |
| `validation-<hash>.json` | the frozen validation binding and each check's outcome; only when the plan has bindings | Yes |
| `verify-<hash>.md` | the verify report | Yes |
| `lint-<hash>.txt` | scilintr output, waivers and what each suppressed | Yes |
| `env-<hash>.txt`, `pip-<hash>.txt` | conda and pip packages of the runs' environments; only when they apply | Yes |
| `PROVENANCE.md` | one row per verified plan | Yes |
| `complete-<hash>.json` | marks a bundle as completely written | Yes |
| `.publish.lock`, `.transactions/` | write lock and the in-flight transaction record | No |

`verify stale`, `verify status`, `verify runs` and `verify refs` read these committed files and need no gate. See [verify](skills/verify.md).

## Written outside both folders

| Path | Written by | Notes |
|---|---|---|
| `.gitignore` | `init` | gains `.mycelium-extra/` |
| `HANDOFF.md` (project root) | `handoff` | overwritten each time |
| `todo/<slug>.md`, `todo/TODO_REGISTRY.md` | `idea` | Mycelium's own todo format |
| `.living/decisions.md` | `decision-status` | one appended entry, after you confirm |
| `.living/learnings.md` | `harden` | one entry edited, after you confirm |
| the new analysis folder | `new-analysis` | never overwrites |

See also: [Gate](gate.md), [gate.json](gate-json.md).
