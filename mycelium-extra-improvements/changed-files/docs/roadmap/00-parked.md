# Parked work

[Back to roadmap](README.md)

Work already drafted outside the repository, waiting to land.

### T0: Split the README into a landing page plus docs/

- **Why:** the README is about 31 KB. A new user meets the receipt schema and the gate's Bash parsing rules before learning what the plugin is for.
- **Scope:** README.md keeps the intro, the summary table, the workflow diagram, Installation, and Quick start, plus a Documentation section. Four new files: `docs/skills.md` (all skill references and the common-prompts table), `docs/approval-gate.md` (approving, gating, pinned inputs, receipts, explore runs, hints, and the full Limits), `docs/mycelium-integration.md`, `docs/development.md`. Prose is condensed; no behaviour, default, path, or limit is dropped.
- **Out of scope:** HANDOFF.md, the B items, any change to skill or hook behaviour.
- **Depends on:** none.
- **Constraints:** none from locked decisions. The Limits list stays complete: it is the plugin's statement of what it does not do.
- **Grill prompt:** `/mycelium-extra:grill Split README.md into a short landing page plus docs/skills.md, docs/approval-gate.md, docs/mycelium-integration.md, and docs/development.md. Start from the drafted files, rebase them onto the current README (it has gained a workflow diagram since the draft), and check that every default, command, path, and limit in the old README appears in the new files.`
- **Acceptance:** the landing page is under about 120 lines and lets a new user install and run the quick start without opening docs/. The Mermaid workflow diagram stays on the landing page. A token check (every gate.json key, schema name, status string, and default value in the old README is found in the new files) passes. Every relative link resolves. The diff touches only README.md and docs/.
- **Tests:** a token-coverage and link check, run once before committing. Optionally keep it as `docs/tests/test_docs_links.py` for CI (A2).
- **Effort:** S.
- **Status:** done. The draft was rebased onto 3a11123, so the workflow diagram stays on the landing page, and B1 is folded in. A content check (every heading, table cell, code line, sentence, and inline-code token of the old README found in README.md or docs/*.md) passes except for the B1 sentence, and every relative link resolves. `docs/skills.md` adds a short `init` entry pointing to `docs/approval-gate.md`, which documents it.
