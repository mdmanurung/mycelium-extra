# Documentation hygiene

[Back to roadmap](README.md)

Small corrections found while restructuring the README.

### B1: Remove a project-specific reference

- **Why:** the new-analysis section says "In scale, for example, `analysis/*/docs/` and `analysis/*/results/` are ignored." "scale" is a private repository; the sentence means nothing to other readers.
- **Scope:** rewrite the sentence generically ("for example, a repository that ignores `analysis/*/results/`").
- **Out of scope:** the warning behaviour itself.
- **Depends on:** none (do it inside T0 if T0 lands first).
- **Constraints:** none.
- **Grill prompt:** not needed; a one-line docs edit.
- **Acceptance:** `rg -n "In scale" README.md docs/` finds nothing.
- **Tests:** none.
- **Effort:** S.
- **Status:** done, inside T0. The acceptance `rg` still matches the quotation in this entry; it finds nothing else under README.md or docs/.

### B2: Move the development log out of the user docs

- **Why:** the verify section says "verify was first run on real receipts on 2026-10-02 (42 receipts, three plans, …). Four bugs it showed are fixed." That is project history, not user documentation.
- **Scope:** move the sentence to the changelog (A3), keeping the remaining known limit in the verify docs.
- **Out of scope:** none.
- **Depends on:** A3.
- **Constraints:** the limit (outputs tied to runs by time) must stay in the user docs.
- **Grill prompt:** not needed.
- **Acceptance:** the user docs keep the limit and drop the dated history; the changelog has the history.
- **Tests:** none.
- **Effort:** S.
- **Status:** todo.

### B3: Fix the HANDOFF pointer after the README split

- **Why:** HANDOFF.md's "Read first" points to `README.md:236` for the development, test, and version-bump rules. After T0 those rules live in `docs/development.md`.
- **Scope:** update the pointer, or let the next `/mycelium-extra:handoff` regenerate it.
- **Out of scope:** the rest of HANDOFF.md.
- **Depends on:** T0.
- **Constraints:** the maintainer has decided HANDOFF.md stays as is for now (see B5); this changes only the stale line.
- **Grill prompt:** not needed.
- **Acceptance:** every `path:line` pointer in HANDOFF.md resolves to the text it describes.
- **Tests:** none.
- **Effort:** S.
- **Status:** done. The pointer is now `docs/development.md:5`. The two other `path:line` pointers in HANDOFF.md are outside this repository (`_engine.py:125` in scilintr, `mycelium-health.sh:482` in the installed Mycelium) and were left as they are.

### B4: Say up front that plan-review sends data off the machine

- **Why:** `plan-review` sends a packet to Codex and to Biomni, which runs in Biomni's cloud at the cost of your Biomni credits. The skill asks for consent at run time, but the README's summary table only says it "writes nothing", which is accurate but not the whole story.
- **Scope:** add "Sends a reviewed packet to Codex and Biomni, after you agree" to plan-review's row in the summary table, or a footnote.
- **Out of scope:** changing plan-review's consent behaviour.
- **Depends on:** none.
- **Constraints:** none.
- **Grill prompt:** not needed.
- **Acceptance:** a reader of the summary table alone knows which skill sends data elsewhere.
- **Tests:** none.
- **Effort:** S.
- **Status:** done. plan-review's Writes cell in the README summary table now reads "Nothing; sends a review packet to Codex and to Biomni's cloud, after you agree".

### B5: Decide whether HANDOFF.md stays committed

- **Why:** the `handoff` skill "does not commit the handoff", but the root HANDOFF.md is now committed. Its "Locked decisions" and "Dead ends" sections are lasting project knowledge; its dated status header is session state that goes stale.
- **Scope:** a decision for the maintainer, not a build task. Options: (a) keep it committed as is; (b) move the lasting sections to `docs/decisions.md` and gitignore HANDOFF.md; (c) keep it committed but have `handoff` mark the session-state section as such.
- **Out of scope:** changing how `handoff` writes the file, unless option (c) is chosen.
- **Depends on:** none.
- **Constraints:** the locked decision that handoffs go to root `HANDOFF.md` (not `.mycelium/last-session.md`) holds under every option.
- **Grill prompt:** if (b) or (c) is chosen: `/mycelium-extra:grill Move the lasting parts of HANDOFF.md (locked decisions, dead ends) into docs/decisions.md and gitignore HANDOFF.md; make sure the handoff skill's behaviour and docs still match.`
- **Acceptance:** the chosen option is recorded here with its date.
- **Tests:** none.
- **Effort:** S.
- **Status:** todo (maintainer decision; currently left as is).
