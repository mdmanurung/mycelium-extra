# Roadmap

Where mycelium-extra goes next, as tasks small enough to grill, approve, build, and ship one at a time. Each task is written so that it can be pasted into `/mycelium-extra:grill` as is: the repository builds itself with its own workflow.

This is a plan, not a promise. Tasks are dropped or reshaped when grilling shows a better design; mark them `dropped` with a one-line reason rather than deleting them.

## Guiding principles

These come from decisions already locked in this repository. A task that would break one says so in its Constraints line and needs that decision revisited first.

- **Complement Mycelium, never override it.** No writes to `.living/`, manifests, or Mycelium's files except by confirmed append where a skill already does so. Run helper scripts from stdin so Mycelium's hooks do not open a post-action cycle.
- **A gap is never clean.** A missing, timed-out, unreadable, or unparseable check is reported as a gap. Nothing passes because a checker failed.
- **The checker adjudicates; the user decides.** Skills report evidence and never loosen a contract, threshold, or claim to make something pass.
- **Friction is opt-in.** New prompts, checkpoints, and hints are off by default per repository, like `hints`.
- **Plain-text hook notices.** `systemMessage` text has no Markdown.
- **No SessionStart messages.** They compete with Mycelium's session resume (measured dead end).
- **Python 3.6 compatible, stdlib only** for hooks and skill scripts; hooks call bare `python3`.
- **One feature, two commits:** `feat(...)`/`fix(...)`, then `chore: bump version` across the three manifests.
- **Run `hooks/tests/gate_diff.py` before and after any change to `hooks/gate.py`;** only intended decisions may differ.

## Phases

| Phase | Goal | Tasks |
| --- | --- | --- |
| 0 | Land parked work | T0 |
| 1 | Make the repository shareable | A1, A3, A4, B1, B2, B3, B4 |
| 2 | Make it testable end to end | C1, A2, A5 |
| 3 | Close reproducibility gaps | E1, E1b, E2, E3, E4, E5, E6, E7, C2, C3 |
| 4 | Keep LLM output out of the record | D1, D2, D3, D5, D6 |
| 5 | Shape how researchers use the agent | D4, D7, D8, D9, A6 |
| 6 | Keep oversight honest | D10, D11, D12 |

Phases are a suggested order, not a gate; a task may start once its dependencies are done. B5 is a decision for the maintainer, not a build task, and has no phase.

## Dependencies

- A2 (CI) depends on C1 (fixture project), so CI exercises more than unit tests.
- A6 (worked example) depends on C1, so the example is a real, reproducible transcript.
- B3 depends on T0 (the pointer only goes stale once the README is split).
- C3 depends on C1 (realistic review packets to audit).
- D1 depends on C1 (fixture findings with planted mismatches).
- D2 depends on D1 (shares its extraction and report format).
- D3 depends on D1 (cites the claims summary) and on A3 (cites the plugin version).
- D4 depends on C1 (needs explore and gated receipts to test against).
- E4 depends on C1 (real-use tests run against the fixture project).
- D10, D11, D12 depend on C1 and D1; D10 also depends on D12 (a checkpoint without a way to see it being gamed is theatre).

## Task template

Every task uses these fields, under a `### <ID>: <title>` heading:

- **Why**: the problem, with evidence.
- **Scope**: what changes.
- **Out of scope**: what does not, so grilling does not grow the task.
- **Depends on**: task IDs, or none.
- **Constraints**: the principles or locked decisions that bind it.
- **Grill prompt**: paste into `/mycelium-extra:grill`.
- **Acceptance**: what must be true to call it done.
- **Tests**: what is added or run.
- **Effort**: S (under 2 h), M (half a day to a day), L (several days).
- **Status**: `todo`, `in-progress`, `done`, or `dropped: <reason>`.

## Workstreams

- [00-parked.md](00-parked.md): T0, work drafted but not landed.
- [01-packaging.md](01-packaging.md): A1 to A6, license, CI, releases, discoverability.
- [02-docs-hygiene.md](02-docs-hygiene.md): B1 to B5, documentation fixes.
- [03-robustness.md](03-robustness.md): C1 to C3, fixture project, fail-closed mode, packet redaction. C1's design: [../design/c1-fixture-project.md](../design/c1-fixture-project.md).
- [04-handoff-backlog.md](04-handoff-backlog.md): E1 to E7 and E1b, open items from the session handoff.
- [05-mindfulness-core.md](05-mindfulness-core.md): D1 to D9, keeping LLM output honest.
- [06-anti-gaming.md](06-anti-gaming.md): D10 to D12, checking that oversight stays real.

## Updating this roadmap

Change a task's Status line in the same commit that ships it. When grilling reshapes a task, edit its Scope and Acceptance to match the approved plan, so the roadmap never disagrees with what was built.
