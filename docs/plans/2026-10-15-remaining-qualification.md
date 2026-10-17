# Locale repairs, fail-closed gate, and host qualification

Date: 2026-10-15
Project: /exports/para-lipg-hpc/mdmanurung/mycelium-extra
Status: done 2026-10-15 (0.9.66, pushed b312d75); H1 native display not observed

Historical record. H1 was closed as covered by A06 on 2026-10-16; native host qualification of the newer approval and attempt records is still open and listed in [07 · Execution fidelity](../roadmap/07-execution-fidelity.md#blocked-or-deferred-with-return-condition).

## Objective
Complete the three workstreams approved after grilling: Python 3.6 C-locale qualification, C2 optional denial on internal errors, and host/interpreter/CI qualification. User approved denying every handled tool call after an internal error when `on_error` is `deny`. Default behavior remains allow. No commits, publication, external review packets, or research jobs are needed.

## Review findings

| Finding | Resolution |
|---|---|
| Existing dirty launcher imports unqualified capacity code | Snapshot all four drafts; test committed HEAD plus scoped changes in a disposable candidate. Merge only necessary launcher changes while preserving its existing draft changes. |
| Gate-only handling misses import failures | Shared independent error handling at the launcher boundary and gate entry point; test both hosts, logging failures, malformed config, and ordinary tool calls. |
| Saved locale failures may be test assumptions | Reproduce the three focused cases before editing; retain ASCII-safe report output and verify structured Unicode findings. |
| Python tests do not qualify native rendering | Exercise disposable host installations; record exact revision/hashes and observed host output. Mark unavailable checks honestly. |
| Remote CI cannot qualify unpublished edits | Read existing CI; run its matrix locally against the candidate. Do not claim remote checks for a different tree. |

## Progress summary

- [x] L1: Reproduce and repair locale failures.
- [x] G1: Implement and qualify opt-in error denial and error records.
- [x] Q1: Run full interpreter matrix, gate comparison, links, and ablations.
- [~] H1 (manifests validate with `claude plugin validate`; no native card display observed): Qualify native host discovery and card display.
- [x] I1 (draft launcher kept uncommitted with on_error merged; 181 gate tests pass on it): Integrate scoped changes, preserve drafts, and update roadmap/handoff evidence.

## Implementation steps

### L1: Locale regressions
- Status: done 2026-10-15 (0.9.66, pushed b312d75); H1 native display not observed.
- Outcome: Existing C-locale regressions pass without changing report encoding policy.
- Actions: Run GateTest and LauncherTest handoff case and VerifyTest output shorthand case on isolated HEAD; repair explicit text decoding and assertion coverage.
- Dependencies: Candidate and protected-draft snapshot.
- Affected areas: hooks/tests/test_gate.py; skills/verify/tests/test_verify.py.
- Validation: Focused tests fail before and pass after on Python 3.6 LC_ALL=C and 3.12.
- Evidence: Pending.

### G1: Error policy
- Status: not started.
- Outcome: Valid deny policy blocks every handled PreToolUse call after an internal error; absent/allow preserve behavior. Other lifecycle failures report errors without pretending a tool was blocked.
- Actions: Add independent fallback and wrapper coverage, best-effort error receipt, invalid-policy notice, settings/recovery documentation, and patch version.
- Dependencies: L1; approved denial policy.
- Affected areas: hooks/gate.py; hooks/gate_run.py; independent fallback if needed; hook tests; init skill; approval-gate docs; manifests; changelog; C2 roadmap.
- Validation: Forced handler/import failures; both hosts; log-write failure cannot bypass denial; default gate_diff unchanged.
- Evidence: Pending.

### Q1: Local package matrix
- Status: not started.
- Outcome: Current candidate qualified on available interpreters with skips explicit.
- Actions: Run CI test-file matrix serially per interpreter, all ablations and links; acquire temporary Python 3.14 if necessary.
- Dependencies: G1.
- Affected areas: Candidate and qualification logs only.
- Validation: All required commands exit zero; no unintended gate decisions change.
- Evidence: Pending.

### H1: Native hosts
- Status: closed 2026-10-16 without a further install. The Codex side was observed natively by the audit remediation (Codex 0.161.0: trusted definitions after restart, denial, card, approval, execution, unknown-exit failure, a fresh thread, and the card rendered in a pseudo-terminal; see [the remediation plan](2026-10-16-audit-remediation.md), A06) and the Claude side by [the lint-on-write record](../design/h1-native-host-lint.md). Still open there, not here: Claude terminal card rendering, real quota, compaction and the capacity worker lifecycle. No change was made to the real `~/.codex` configuration.
- Outcome: Exact candidate installation, skill discovery, and card denial-reason display observed in disposable host state.
- Actions: Inspect local host interfaces, validate manifests, install candidate in disposable state, exercise card handling without starting research work; read remote CI results.
- Dependencies: Final candidate code.
- Affected areas: Disposable host state and documentation evidence only.
- Validation: Native dispatch and visible reason at candidate hash; source/cache hashes agree. Record unavailable checks separately.
- Evidence: Pending.

### I1: Integration
- Status: not started.
- Outcome: Reviewable changes in original checkout; all original draft work retained.
- Actions: Copy tested scoped files back; merge minimal launcher delta into its saved draft; test integration; update canonical status and handoff.
- Dependencies: Q1 and H1 evidence, including explicit gaps.
- Affected areas: Scoped files, docs, roadmap, existing local handoff.
- Validation: Hash equality for scoped files and three untouched modules; original launcher draft delta retained; git diff --check; final diff review.
- Evidence: Pending.

## Decision and evidence log

- 2026-10-15: User approved blocking all handled tool calls after internal error under opt-in deny; instructed completion of remaining workstreams.

## Risks and limits

- Unreadable configuration cannot establish an opt-in deny policy; fallback must say so.
- A host that never dispatches a hook cannot be controlled by Python fallback code.
- The existing capacity/journal features remain drafts; integrating shared launcher changes does not qualify those features.

- 2026-10-15: Python 3.6/C, 3.12, 3.14 full matrix, ablations and links pass on the candidate. gate_diff 162/163 on 3.6; the one diff is a harness artifact (an unchanged HEAD gate inside a repo tree shows it too: the old side lives outside the repo and cannot load verify for card lint).
