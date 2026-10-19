# Decisions

Decisions that still bind, each with its reason. This is the lasting part of the session handoffs: `HANDOFF.md` stays session state (gitignored), and a decision moves here once it holds beyond one session. Principles that shape every task are in the [roadmap](roadmap/README.md#guiding-principles); this page holds the choices made on top of them. Dates are when the decision was recorded. To change one, say so and add a new dated line; do not edit the old one.

## Process

- **Rebase-only merges, no merge commits, no force-push** (recorded 2026-10-19). Keeps one readable history and the pushed branch stable for the installed plugin.
- **Keep the repository local; push and tag only on request** (2026-10-19). The installed plugin follows `origin/main`, so a push is a release.
- **Work in a worktree; never edit `hooks/` in the main tree** (2026-10-19). Real sessions run hooks from that tree, so a half-edited hook runs in someone's analysis.
- **One feature, two commits**: the change, then a version bump across the manifests (roadmap guiding principles).
- **`gate_diff` before and after any change to `hooks/gate.py`**; only intended decisions may differ (roadmap guiding principles).

## Product

- **Handoffs go to the root `HANDOFF.md`, not `.mycelium/last-session.md`** (roadmap `02-docs-hygiene.md`, handoff item). Mycelium owns the second file.
- **`HANDOFF.md` is gitignored session state** (2026-10-16, roadmap `02-docs-hygiene.md`). Its dated status goes stale; lasting decisions live on this page.
- **`on_error: deny` is opt-in**; the default stays fail-open (0.9.66). A gate that blocks on its own failure is friction a user must choose.
- **Approval latency is logged only**, never scored or shown; the checkpoint question is off by default (2026-10-16, D10). Scoring approvals would turn them into a performance.
- **Snakemake per-rule conda envs are not read (E1b)** (2026-10-16). No real `--use-conda` pipeline exists to check the env-folder format; a reader built on a synthetic fixture that says "recorded" is worse than the stated `LIMITS` line. Reopen when one runs under `verify`.
- **Focus and track-changes: strict focus blocking, an AI explanation pass and the usability study stay out of scope** (2026-10-19). M4's `--explain` is a bounded text block from the report's own records, not a model call. M3 (launch-time `focus_id` in receipts, opt-in notices) was parked behind the usage measurement; the status is in [the tracker](roadmap/10-focus-track-changes.md).
- **C12 live validation, the EUR50 budget gate and the live Socratic study (M5b) stay out of scope** (2026-10-19). Paid calls and human adjudication need an approved packet; `docs/plans/2026-10-16-live-validation/packet.json` stays `NOT APPROVED`.

## Dead ends: do not redo

- **OpenCode v2 has no `--pure`, `--dir` or `agent list`.** Isolate with `XDG_CONFIG_HOME=<run>/config` plus `--standalone`, and pick the worktree by cwd. Without `--standalone`, `XDG_CONFIG_HOME` isolates nothing (shared background service).
- **`--model opencode/<free>` under the global config still resolves to a paid model** and fails on quota; the tier plugin is what picks the model.
- **A deny-all-only custom agent fails** with "OpenCode's free tier can only be used from within OpenCode"; keep explicit `read` and `edit` allows.
- **A launcher reading `$AGENT` breaks** (`AGENT=1` is exported); use a distinct variable.
- **A local Sphinx build may be impossible** (the wrapper interpreter has no `sphinx`); CI runs the docs build. Report a missing local build as a gap, not a pass.
- **No SessionStart messages**: they compete with Mycelium's session resume (measured dead end; roadmap guiding principles).
