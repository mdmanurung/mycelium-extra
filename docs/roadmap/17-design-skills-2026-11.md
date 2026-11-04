# 17 · Design skills and outside lessons (2026-11-04)

[Back to roadmap](README.md)

Objective: use five user-level design skills (impeccable, hallmark 2.0, design-taste-frontend, diagram-design, doc-coauthoring) and three blader repos (taskmaster, adversarial-execution, baton) on the plugin's own outputs, without touching the gate or Mycelium's files. Shipped as 0.23.0.

Statuses: `todo`, `in progress`, `built`, `done`, `parked`, `dropped: <reason>`, `blocked: <question for the user>`.

| ID | Item | Source | Touches | Status |
|---|---|---|---|---|
| B4 | One `DESIGN.md` at the repo root: hex tokens light and dark, picked from three rendered options (B colours and pills, A system fonts); applied to the viewer, a Quarto theme and the figure script; `tests/test_design_tokens.py` keeps the copies equal | impeccable `document` | `DESIGN.md`, `skills/track-changes/assets/viewer.css`, `skills/new-analysis/templates/report*.scss`, `docs/scenario/make_figures.py` | done |
| B1 | `handoff test`: a cold reader gets a staged copy of `HANDOFF.md` or a filled report and lists the gaps; offered in one line, never run unasked; an instruction, not a sandbox | doc-coauthoring stage 3 | `skills/grill/references/cold-reader.md`, `skills/handoff/SKILL.md`, `skills/analysis-report/SKILL.md` | done |
| C1 | `Assumed, not run` line in the handoff State block | baton | `skills/handoff/SKILL.md` | done |
| C2 | `lean (not a decision)` on each handoff open item | baton | `skills/handoff/SKILL.md` | done |
| B2 | 36 hand-written docs diagrams restyled from the tokens, dark mode kept, no node cut; profile committed at `docs/design/diagram-profile.md` | diagram-design | `docs/figures/*.svg`, `.diagram-design` | done |
| B3 | Audit of the journal and track-changes viewer: 30 findings; 22 fixed (status pills, empty and error states, long paths, focus, contrast, keyboard tabs, landmarks, event pills), 5 parked, 1 dropped, screenshots stale | impeccable `audit`, `harden` | `skills/track-changes/AUDIT-2026-11.md`, `assets/*`, `scripts/*` | done |
| B5 | `tests/slop_lint.py`: 16 static rules from taste, hallmark and DESIGN.md, run on the generated pages | taste `rules.mjs`, hallmark `sloplint-render.mjs` | `tests/slop_lint.py`, `tests/test_slop_lint.py` | done |
| B6 | `analysis-report artifact <folder>`: a one-off evaluation page built from the filled report, written to `.mycelium-extra/artifacts/`, checked by `artifact_check.py` (page contract, banner, every number in the report), published only after the user agrees; Quarto stays the record | user decision 2026-11-04 after a spike | `skills/analysis-report/` | built; first real run pending |
| C3 | `plan-review results` mode: reviewers assume the result did not answer the approved question | adversarial-execution | `skills/plan-review/` | parked: until a verify-clean run answers the wrong question |

Rejected with a reason: taskmaster's stop-blocking loop (its prompt forbids asking the user, and its installer rewrites `~/.claude/settings.json`); adversarial-execution's unbounded two-model loop (friction by default; BIP1-01 declined bounded cycles); baton's dated `.baton/` files (`HANDOFF.md` is overwritten by design); impeccable's PostToolUse hooks (friction stays opt-in).

Not checked in a browser (this node has none): the diagrams in dark mode, the viewer's pills and focus rings, phone width. A private contact sheet exists for the user to look at. The three PNG screenshots under `docs/examples/` show the pre-0.23.0 viewer.

Next: `docs/roadmap/18-analysis-layout.md` (0.24.0, plan approved 2026-11-04).
