# Package completion, 2026-10-25

The active build tasks shipped in 0.16.0, which is cut, tagged and pushed. The completion pass below adds a local, unreleased guide; live-study tasks remain open.

## Completed work

- [x] Newplans A1/A2/A4/B1 are on main (`015b9b6`, `e759059`, `acc21ef`). Reconciled their stale worktree statuses.
- [x] A3 now includes freeze and amendment cards (`79757ac`), using the existing overlap renderer. The fix was tested in an isolated worktree, then fast-forwarded onto main.
- [x] Audit F2/X15 (`605b5ba`): diagnose accepts optional null limits, explains off settings, and reports oversized numeric settings as default fallbacks, matching the gate.
- [x] D12 (`9441ee6`): a labelled, opt-in `verify exercise` and `exercise reveal` rehearse C1 V-23. No project state is read or written. Personal scores and habit summaries remain deferred.
- [x] Track-changes and journal HTML examples regenerated. The portable journal scratch-project keeps its existing independent synthetic history.
- [x] Unreleased changelog now records the landed recipes, profile, scope-loss notice, method guides and completion fixes.
- [x] Roadmap summaries reconciled: E1b is already validated; focus M3/M4 are already built.
- [x] Three merged worktrees removed and their branches deleted; loose handoff artifacts archived under `plans/_DONE/handoff-archive-20261025/`.
- [x] 0.16.0 cut across the four manifests and `CHANGELOG.md` (`d810aaf`), pushed, tagged `v0.16.0`, and released. The live packet was requalified to 0.16.0 (`db32b05`) with approval bound to `manifest_sha256` (`1313328`).
- [x] GitHub detects MIT; the description and ten topics are set, including `opencode`.

## Verification

Logs are local at `/tmp/mycelium-extra-finish-20261025/`; the temporary documentation environment is there too.

| Check | Result |
|---|---|
| Python 3.12 CI-style sweep before D12 | 43 programs, 1,424 tests, 35 skips, no failures; `sweep-summary.json` lists each program |
| Updated gate suite | 493 tests, 2 skipped, passed; `gate-candidate.log` |
| Gate comparison before and after card changes | 173/173 identical both times; `gate-before.log`, `gate-after.log` |
| Init regressions | 35 tests on Python 3.9, 3.12 and 3.14 |
| Exercise regressions | 3 tests on Python 3.9, 3.12 and 3.14 |
| Ablations | 17/17 bite; `ablations.log` |
| OpenCode adapter | passed; `node.log` |

Final reruns passed:

- `verify-after-exercise.log`: 267 verify tests after the new CLI action.
- `journal-after-refresh.log`: 12 journal tests.
- `links.log`: 510 links checked, 0 broken.
- `sphinx.log`: the pinned documentation environment built HTML with `-W --keep-going`, no warnings.
- End-to-end Catalog: 5 tests; version agreement: 1 test; verify frontmatter: 2 tests.
- `git diff --check`: clean. Passing fixture tests does not establish native-host delivery or scientific validity. Skipped dependency-dependent tests remain gaps; the sweep is not a new real-analysis qualification.

## Completion pass, 2026-10-25

The request to finish remaining work reopened F8/Q6. A short [single-cell routing pointer](../../skills/grill/references/methods/single-cell.md) now defers to the existing pack activation and routing rules. It copies no method policy. The guide, its routing link and contract test are local and unreleased. The release and roadmap summaries were reconciled with the existing 0.16.0 release records.

The guide checks pass: 5 method-guide tests and 15 grill-reference tests. These static checks establish the reference contract, not native routing or scientific validity. Fresh local sweep and build logs are in `/tmp/mycelium-extra-remaining-20261025/`; no hosted CI, push, tag or release was performed during this pass. The final Python 3.12 sweep covers 44 programs and 1442 tests, with 30 skips. Two initial harness timeouts were recovered by complete extended runs; `final-summary.json` records the reconciliation. The adapter, 17 ablations, 518 links and strict Sphinx build pass.

## Still open

| Task | What is needed |
|---|---|
| C12, native-host checks, sc-conventions live M1/M3 | The approved packet, resolved provider/billing bounds, real host sessions and independent human adjudication. The packet remains NOT APPROVED; no paid calls or scheduler jobs ran. |
| R1–R3 live plan binding (M2) | A named real project, its approved plan and inspected inputs. Synthetic contracts cannot stand in for that analysis. |
| Track R / M5b and usage measurement | The planned ~2026-10-31 measurement and researcher participation. No future observations were invented. |
| Parked model benchmark | Paid provider quota and its existing run authorization; no substitute model was selected. |
| ED-1 and personal habit summaries | Deferred product ideas with unmet return conditions, not active build tasks. |

For the authoritative boundaries, see [decisions](../decisions.md), [the live-validation packet](2026-10-16-live-validation/README.md), and [the newplans tracker](../roadmap/14-newplans.md).
