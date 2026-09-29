# Mycelium repository lookup

Use this reference only after detecting a Mycelium repository. Its project files are the contract; the companion skill does not depend on Mycelium's private scripts, hooks, or plugin path. Follow `MYCELIUM.md` if the project's structure differs.

## Selective sequence

1. `MYCELIUM.md` for local protocol and restrictions; `.living/INDEX.md` for relevant tags and entry IDs. If the index is missing or stale, search relevant `.living/` files directly; do not assume indexed counts are complete.
2. Relevant area manifests: `analysis/ANALYSIS_MANIFEST.md`, `data/DATA_MANIFEST.md`, `algorithms/ALGORITHM_MANIFEST.md`, `reference_material/REFERENCE_MANIFEST.md`, `todo/TODO_REGISTRY.md`. Read only those connected to the request.
3. Current analysis folder documentation and code/config that actually generated outputs; inspect metadata/provenance and sample exclusions as needed.
4. Relevant `.living/decisions.md`, `learnings.md`, `findings/FINDINGS_REGISTRY.md` and topic ledgers. Entries may be provisional, historical, or superseded.
5. `.living/conventions.md`, `.living/conventions/ACTIVE_CONVENTIONS.yaml`, and applicable convention packs. Check which conventions are active; their presence alone is not activation.
6. Use `.living/log/LOG_REGISTRY.md` or a relevant session log only when the earlier sources leave a consequential gap.

Use `rg -n` with task-specific terms and entry IDs; keep searches scoped to likely directories. Mycelium's optional recall script may speed up targeted lookup if the project documents it and the installed script exists, but direct file reads must remain sufficient. Never make its internal location a requirement.

## Interpret evidence

| Source | Establishes | Does not establish |
| --- | --- | --- |
| Manifest | Registered assets and documented status | That an output is correct or fresh |
| Decision | Past rationale or intent | That later work followed it |
| Learning | Observed caveat or lesson | An active mandate |
| Finding ledger | Reported scientific result and provenance | Generalizability beyond its evidence |
| Convention | Applicable guidance when active | That implementation complies |
| Code/output | An implemented path or generated artifact | The endorsed scientific rationale |

Track explicit supersession and task applicability. When dates conflict or are absent, inspect nearby commit history or current docs only if resolution matters. Prefer a short quoted path and your inference over an unsupported statement of authority.
