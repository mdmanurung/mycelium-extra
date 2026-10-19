# Comprehensive audit remediation and release

Started 2026-10-16 UTC. Owner: Codex coordinator. Source of intent: user implementation plan and [audit](../design/2026-10-16-feature-stress-audit.md).

Preserve public commands/provenance filenames and all starting/concurrent work. Runtime: Python 3.6+, standard library only. Capacity and diary stay draft until qualification passes. Local checks precede live checks. No personal installations. Release, model/reviewer calls and Slurm execution follow the concrete approval boundaries below. No support claim may be broadened through a skipped check.

Budget: EUR50 maximum cumulative model/reviewer calls; spent by this implementation: EUR0. No paid calls authorized until the A09 packet is approved. Scheduler tasks require exact approved scripts/resources (1 CPU, no GPU, <=1 GiB, <=5 minutes, documented partition minima only before approval). Merge/publish requires explicit approval of the tested candidate.

## Execution tracker

| ID | Depends on | Status | Work | Acceptance evidence |
|---|---|---|---|---|
| A01 | none | complete | Freeze starting state; recover evidence; map all findings. | Baseline archive/hashes, sanitized historical receipts, complete mapping. |
| A02 | A01 | implemented; local checks pass | Recoverable locked provenance saves without public renames. | Interruption at each phase; same/different-plan concurrent writes; readers distinguish complete/legacy/interrupted. |
| A03 | A01 | implemented; local checks pass | Exclusive idea capture and staged scaffold publication. | Concurrent identical titles; idempotent registry recovery; failure leaves existing files and targets intact. |
| A04 | A01 | implemented; local checks pass | Capacity and diary lifecycle. | Disabled no-op; manifests; sticky thresholds; fresh explicit resume; independent approval; idempotent checkpoints; unverified raw text. |
| A05 | A01 | implemented; local checks pass | Evidence attribution and pre-send boundaries. | Ambiguous/competing timestamps, opaque wrappers/notebooks/metadata pins are gaps; short IDs; structured redactions; truncated coverage. |
| A06 | A02–A05 | partial native observations; mandatory gaps remain | Native Claude/Codex dispatch, trusted hashes and TTY. | Actual host traces for denial/card/approval/run/failure/unknown/reapproval, lifecycle and assignment tools; no personal configuration changes. |
| A07 | A02–A05 | bounded real integrations pass | Real local workflow tools in pinned isolated environments. | Python/R4_51 scaffolds, Snakemake/Nextflow/notebooks/linters/H5AD; success/failure/interruption/resume/staleness; missing tools block. |
| A08 | A06, A07 | rubrics prepared; real journeys blocked on access/cost and human adjudication | All 11 skills and installed Mycelium bounded agent journeys. | Predeclared rubrics/forbidden writes; real model transcripts; human adjudication; failing-before/passing-after harden; repeat repaired cases. |
| A09 | A05 | packet prepared; identities/cost bounds and explicit live approval pending | Prepare then approve external reviewer and Slurm packet. | Identical synthetic packets, identities, call limits, cumulative <= EUR50; exact scheduler resources and receipts; no jobs/calls before approval. |
| A10 | A02–A09 | corrected candidate matrix running; full qualification depends on A06/A08/A09 | Freeze immutable integrated candidate and qualify. | 3.6/C, 3.12, 3.14 matrix, ablations, fixtures, real tools, manifests, links, warning-free Sphinx; reviewed exact 22 differences; source parity. |
| A11 | A10 | not started | Reviewable PR then explicitly approved publication. | Focused commits, unused synchronized patch version; remote CI/Pages; fresh installs; HEAD/main/tag/cache hashes; versioned rollback. |

## Audit closure mapping

Every row remains open until its required executable or observed evidence exists. Instruction/helper tests alone do not qualify agent judgment. Each mapped owner step must record exact cases and receipts.

| ID | Audit section / finding | Owner steps | Required evidence | Status |
|---|---|---|---|---|
| F01 | Feature coverage matrix: grill | A08, A10 | skills/grill/tests/test_grill_references.py; J01 grounded answers and five-question cap | observed within named helper/native boundary; mandatory J/live checks remain open |
| F02 | Feature coverage matrix: init | A08, A10 | skills/init/tests/test_gate_init.py; J02 idempotent gated fixture | local executable checks recorded; release qualification remains open |
| F03 | Feature coverage matrix: new-analysis | A03, A07 | skills/new-analysis/tests/test_new_analysis.py; A07 Python/R/notebook scaffold execution; J03 | observed within named helper/native boundary; mandatory J/live checks remain open |
| F04 | Feature coverage matrix: plan-review | A08, A10 | skills/plan-review/tests/test_plan_review.py and test_presend_check.py; identical reviewer packet and J05 adjudication | observed within named helper/native boundary; mandatory J/live checks remain open |
| F05 | Feature coverage matrix: data-contract-check | A08, A10 | skills/data-contract-check/tests/test_data_contract_check.py, including all 32 real H5AD/table cases; J04 | local executable checks recorded; release qualification remains open |
| F06 | Feature coverage matrix: decision-status | A08, A10 | skills/decision-status/tests/test_decision_threads.py; J06 scoped/contested decisions and exact confirmed append | observed within named helper/native boundary; mandatory J/live checks remain open |
| F07 | Feature coverage matrix: verify list/report/write | A02, A05, A07 | skills/verify/tests/test_verify.py (write/rewrite); hooks/tests/test_provenance.py (all interruption stages and competing writers); J07 | observed within named helper/native boundary; mandatory J/live checks remain open |
| F08 | Feature coverage matrix: verify stale/status | A02, A05, A07 | skills/verify/tests/test_verify.py (stale/status/interrupted first save); tests/test_end_to_end.py sweep S-01 through S-03 | local executable checks recorded; release qualification remains open |
| F09 | Feature coverage matrix: verify diff/multiplicity/explore | A02, A05, A07 | skills/verify/tests/test_verify.py diff/multiplicity/explore cases; J07/J14 retained-history and promotion checks | observed within named helper/native boundary; mandatory J/live checks remain open |
| F10 | Feature coverage matrix: handoff | A08, A10 | hooks/tests/test_gate.py handoff command and fresh-session cases; J08 fresh agent reconstruction | observed within named helper/native boundary; mandatory J/live checks remain open |
| F11 | Feature coverage matrix: idea | A03, A08 | skills/idea/tests/test_capture.py; real-mycelium-idea.json; J09 native concurrent capture | observed within named helper/native boundary; mandatory J/live checks remain open |
| F12 | Feature coverage matrix: idea-triage | A03, A08 | J10 predeclared rubric, missing files, unknown ratings, exact File-keyed update, and no-write park-all inventory | observed within named helper/native boundary; mandatory J/live checks remain open |
| F13 | Feature coverage matrix: harden | A08, A10 | J11 eligible planted learning, confirmed narrow mitigation; before-after/presend-*.log as reproduction inputs | observed within named helper/native boundary; mandatory J/live checks remain open |
| F14 | Feature coverage matrix: Approval/cards | A08, A10 | 257 gate tests; native Claude/Codex plan/card/approval and fresh-session denial; Codex PTY record | observed within named helper/native boundary; mandatory J/live checks remain open |
| F15 | Feature coverage matrix: Input/script pins | A05, A07, A09 | hooks/tests/test_gate.py pins/mutation/notebooks/budgets; metadata-only report regression in test_verify.py | observed within named helper/native boundary; mandatory J/live checks remain open |
| F16 | Feature coverage matrix: Receipts/wrappers | A05, A07, A09 | hooks/tests/test_gate.py compound/background and unknown status; test_verify.py; native failure receipts; A09 per-job accounting | observed within named helper/native boundary; mandatory J/live checks remain open |
| F17 | Feature coverage matrix: Lint lifecycle | A08, A10 | gate tests plus real-linters-rc2-3.6.log, real-linters.log, real-linters-rc2-3.14.log; J07/J12 human behavior | observed within named helper/native boundary; mandatory J/live checks remain open |
| F18 | Feature coverage matrix: Exploration/hints | A08, A10 | gate exploration/session grant tests; J14 fresh approved promotion; no relabeling of retained exploratory outputs | observed within named helper/native boundary; mandatory J/live checks remain open |
| F19 | Feature coverage matrix: Error/state protection | A08, A10 | gate malformed-state/aliases/import-error/legacy tests; provenance damage and checkpoint state tests | observed within named helper/native boundary; mandatory J/live checks remain open |
| F20 | Feature coverage matrix: Claude integration | A06 | native/claude-final.log and failure/fresh/capacity traces; actual Claude TTY still unobserved | observed within named helper/native boundary; mandatory J/live checks remain open |
| F21 | Feature coverage matrix: Codex integration | A06 | native/codex-flow-result.json, final-cache-parity.json and native-codex-tui-result.json; native compaction/worker events still unobserved | observed within named helper/native boundary; mandatory J/live checks remain open |
| F22 | Feature coverage matrix: Mycelium integration | A08, A10 | real-mycelium-idea.json and real-mycelium-diary.log; J12 full installed lifecycle and human diary preservation | observed within named helper/native boundary; mandatory J/live checks remain open |
| F23 | Feature coverage matrix: Capacity draft | A04, A06, A08 | hooks/tests/test_capacity.py; Claude replay pause/sticky/resume; native-allowance*.json unavailable; J13 native acquisition/assignment/lifecycle | observed within named helper/native boundary; mandatory J/live checks remain open |
| F24 | Feature coverage matrix: Diary draft | A04, A06, A08 | hooks/tests/test_capacity.py draft/edit/idempotence/malformed metadata; real-mycelium-diary.log; J12 actual human edit/finalization | observed within named helper/native boundary; mandatory J/live checks remain open |
| F25 | Feature coverage matrix: Package/docs | A10 | immutable matrix-rc2, four independent ablations, 42 exact differences/168 cases (23 at the first pass; the rest are the later launch-record and `ready` state changes), identical-source check, links, docs-rc2-build.log | local executable checks recorded; release qualification remains open |
| F26 | Reproduced defects repaired: Compound/background receipts | A05, A07, A09 | historical gate receipt/background before-after logs; gate tests; exact oracle 18 compound cases; native unknown receipts | repaired and tested locally; external owner-step checks remain separate |
| F27 | Reproduced defects repaired: Gate state aliases | A08, A10 | historical gate state-alias before-after logs; gate tests for aliases/reads/pipes; exact differential boundary | repaired and tested locally; external owner-step checks remain separate |
| F28 | Reproduced defects repaired: Spaced script paths | A08, A10 | historical gate spaces before-after logs; whole-path grant/pin and fragment denial tests; exact differential boundaries | repaired and tested locally; external owner-step checks remain separate |
| F29 | Reproduced defects repaired: Corrupt approvals/pins | A05, A07, A09 | historical corrupt and final-state-boundaries logs; gate malformed approval/pin/date tests; legacy records remain readable | repaired and tested locally; external owner-step checks remain separate |
| F30 | Reproduced defects repaired: Claim tables/numbers | A05, A07, A09 | historical verify before-after logs; test_verify.py malformed/duplicate/extreme claim cells and unchanged numeric fixture assertions | repaired and tested locally; external owner-step checks remain separate |
| F31 | Reproduced defects repaired: Damaged execution evidence | A05, A07, A09 | test_verify.py malformed receipts/workflow metadata and invalid timestamps; explicit incomplete-history gaps | repaired and tested locally; external owner-step checks remain separate |
| F32 | Reproduced defects repaired: Data contracts | A08, A10 | historical skills cohort/type/empty-contract before-after logs; 32/32 actual H5AD/table cases | repaired and tested locally; external owner-step checks remain separate |
| F33 | Reproduced defects repaired: Initialization | A08, A10 | historical init regression-before/after logs; test_gate_init.py nonfinite hours/state preservation | repaired and tested locally; external owner-step checks remain separate |
| F34 | Reproduced defects repaired: Generated analysis code | A03, A07 | historical new-analysis regression-before/after; test_new_analysis.py quoted paths, notebook code and atomic publication failures; real A07 engines | repaired and tested locally; external owner-step checks remain separate |
| F35 | Reproduced defects repaired: Review pre-send | A05, A09 | test_presend_check.py short IDs, exact tokens, redaction shape, BOM/quoted paths, masked diagnostics, missing/unsupported/malformed/truncated coverage | repaired and tested locally; external owner-step checks remain separate |
| F36 | Reproduced defects repaired: Ideas | A03, A08 | test_capture.py concurrent identical titles and idempotent recovery; actual Mycelium 0.7.2 File-keyed publication | repaired and tested locally; external owner-step checks remain separate |
| F37 | Reproduced defects repaired: Decisions | A08, A10 | test_decision_threads.py matching fence delimiter/length and invalid regex; J06 confirmed append | repaired and tested locally; external owner-step checks remain separate |
| F38 | Reproduced defects repaired: Recovery checkpoints | A04, A06, A08 | test_capacity.py malformed record refusal, idempotent finalization, changed checkout, visible corruption and no relaunch | repaired and tested locally; external owner-step checks remain separate |
| F39 | Reproduced defects repaired: Coherence/test oracles | A10 | contract/frontmatter tests; exact gate expectations reject missing/extra/changed observations; identical-source and independent defect/ablation checks | repaired and tested locally; external owner-step checks remain separate |
| F40 | Native-discovered cross-session execution grant | A05, A06, A10 | GateTest and LauncherTest.test_fresh_session_cannot_reuse_execution_approval; native before/after receipts; exact differential case tool approval from another session | repaired and tested locally and in native Codex; full release checks remain open |

## Remaining limitations mapped to checks

| Gap | Owner | Required check |
|---|---|---|
| Agent judgment, scientific grounding and interpretation | A08 | Real bounded transcripts and human rubric adjudication; software evidence never establishes scientific truth. |
| Trusted Codex/native dispatch and terminal display | A06 | Current source/cache hashes, exact trusted definitions, restarted host, event/TTY traces. |
| Real workflow engines and scheduler accounting | A07, A09 | Tool versions, success/failure/resume, per-array IDs and scheduler/output reconciliation. |
| Multi-file provenance saves / uncertain attribution | A02, A05 | Fault injection, concurrency and conservative reader gaps; retain ambiguous evidence. |
| Draft lifecycle, quota APIs, concurrent creation and redaction | A03–A06, A08 | No-op disabled state; native lifecycle; sanitized quota replay; atomic publication; incomplete disclosure coverage. |

## Dated evidence

- 2026-10-16: starting HEAD `384e6394b71cdae6ab983f0b10fa8d4f5e65c900`; dirty 0.9.71 work preserved. Baseline patch, complete source archive and SHA256 inventory under `evidence/2026-10-16-start-20261016T164200Z/`. No implementation edit preceded snapshot. `HANDOFF.md` describes older work and is superseded by current Git/audit evidence.
- 2026-10-16: historical audit reports and summary receipts recovered under `evidence/2026-10-16-recovered/`, with source/sanitized hashes in `manifest.json`. Account paths/credential-shaped assignments sanitized; native homes/auth state/transcripts were not copied. These establish prior observations only and are not a fresh qualification matrix. Original temporary receipts remain intact.

## Implementation and current qualification (2026-10-16 UTC)

- A02: `hooks/provenance.py` stages complete same-filesystem bundles, retains old bytes, records interrupted transactions, checks member hashes, and publishes the index last under one analysis lock. Fault injection covers staged/pending/every member/completion/index/done, first-save absence, ambiguous damage, and same/different-plan concurrent writers. Report/status/stale distinguish complete/legacy/interrupted. A render-failure reproduction damages the old writer's bundle and preserves the repaired writer's bundle (`evidence/2026-10-16-local/before-after/provenance-*.log`). Runtime lookup uses Git inventory rather than traversing data trees.
- A03: exclusive capture plus File-keyed publication/recovery retains both concurrent ideas using the actual Mycelium 0.7.2 helper. No unlocked registry fallback. Scaffolds stage, validate and atomically publish under a destination lock; relative links, existing empty directories, and refusal to follow a symlink destination are covered.
- A04: disabled hooks/statusline create no capacity records; silent SessionStart; all-tool PreToolUse matching and host lifecycle events (the registrations are held back from the shipped manifests since 0.9.72; see `hooks/capacity-hooks.json`); sticky thresholds and explicit fresh resume; unverified assistant notes; idempotent finalization; checkout history; visible malformed-record gaps; corrupted diary metadata retained. Native Claude replay observes pause/sticky pause/explicit resume, separately from unobserved real allowance acquisition. Capacity/diary remain draft for release.
- A05: short known IDs use exact token boundaries; redaction entries require kind/field strings; unsupported, malformed, missing and truncated table coverage blocks the pre-send check. Diagnostics mask values and input paths. Competing output writers and metadata-only pins are gaps. E2E V-20 is now a detected ambiguity rather than a falsely attributed known miss. Existing numerical fixture comparisons remain unchanged.
- Native qualification found an additional execution-grant defect: a fresh Codex thread reused the prior thread's approval. Repaired both execution lookup and receipt attribution to require the current session. Sessionless legacy approvals remain historical inventory only; they require re-presentation/reapproval. Direct and launcher reproductions fail before/pass after, and the native fresh thread is now denied. This is an additional documented approval interface change. The exact gate oracle contains the original 22 reviewed changes plus this one new boundary case: 23 differences across 168 cases.
- Native evidence: Claude 2.1.301 denial/card/approval/success/failure/fresh-session and replayed pause/resume; Codex 0.161.0 trusted definitions/restart, real native denial/card/approval/execution/unknown failure/fresh-session and actual PTY card rendering. Scripted responses establish control flow only. Real allowance queries returned unavailable; they never became zero. Native compaction, positive worker lifecycle and Claude TTY remain mandatory A06 gaps.
- A07 real tools: Snakemake 9.25.1, Nextflow 25.04.4, R4_51/R 4.5.1, notebook execution, Python scilintr 0.1.2, R scilintr 0.1.1, H5AD including a real AnnData writer. The completed run (`evidence/2026-10-16-local/workflows/attempt-m2bqd6m8/`) covers success, stub failure, changed input, stale-output rebuild, interrupted/resumed Snakemake, notebook failure, failed/resumed cached Nextflow, 32/32 H5AD/table tests and actual linters. Earlier development attempts are retained as failed attempts; a missing writer skip correctly failed qualification until installed. Full pinned tool versions are in `validation-tools.lock`.
- A08/A09 preparation: [live packet](2026-10-16-live-validation/README.md), exact synthetic factual packet and prompt, predeclared journeys for all 11 skills and all eight verify actions, human rubric, and four Slurm scripts for five tasks. Read-only scheduler discovery confirms `short` max 1h and no minimum requiring an increase from the proposed one CPU/1 GiB/5 minutes. No job, reviewer call or real model journey has run. EUR0 spent. Biomni access/model identity and verified provider EUR cost bounds are unresolved. User clarification requested; no unavailable capability is silently dropped.
- Delivery (as of the first pass; superseded by the reconciliation below): remote main matched `384e6394b71cdae6ab983f0b10fa8d4f5e65c900` and no 0.9.71 tag existed.
- Concurrent filesystem changes moved historical archives into unowned `plans/` (first pass; resolved by commit `4674ca8`, see the reconciliation below).

## Remaining release blockers

1. A06: real quota acquisition, native compaction/positive worker lifecycle, and Claude terminal rendering.
2. A08: real model journeys and human rubric adjudication, including confirmations, hardening, promotion and full installed Mycelium lifecycle.
3. A09: resolve exact reviewer access/identity and provider cost bounds, obtain approval of the concrete packet, then execute/reconcile reviewers and all five scheduler tasks.
4. A10/A11: finish corrected immutable matrix, reconcile concurrent archive moves, review focused implementation commits, choose unused release version, PR/review, explicit merge/publish approval, remote CI/Pages and fresh marketplace installations. A local pass does not close these blockers.


## Reconciliation at 0.9.74 (2026-10-17)

The sections above record the first pass by the Codex session, which stopped on 2026-10-16. A second session took over, committed that work in its own commit-plan groups (`62628c3` to `0a4042e`), fixed what the independent approval and execution-evidence audit still found (the audit bundle `plans/_DONE/mycelium_extra_audit/`, kept locally and not in the repository, pinned to 0.9.70 at `384e639`), and pushed to `origin/main`. Where the sections above say "dirty 0.9.71", "not pushed" or "23 differences", this section is current.

### State

| What | Now |
|---|---|
| Source | `main` carries 0.9.74; the Codex candidate and the earlier D11 work were byte-identical in the working tree and are inside the commits above |
| Pushed | 0.9.72 (`0dc43f0`) is on `origin/main`; 0.9.73 (D10) and 0.9.74 (`verify runs`) are local until pushed |
| Local checks | every test file on Python 3.6 and 3.12, `ablate.py` 4/4, links, `gate_diff.py --self-check` 168/168 and 42 exact differences against `384e639` |
| Remote | CI and Pages for `450ccdc` (0.9.71) passed on 3.6, 3.12 and 3.14; the `gate-diff` job runs only on pull requests and was skipped |
| Archive moves | `mycelium-extra-improvements/` and `mycelium-extra-review-bundle/` removed (`4674ca8`); evidence summaries kept in `evidence/` (`e87d3c5`), logs and traces local |
| Capacity and diary | lifecycle registrations held back from the manifests (`bd3970b`); still an unqualified draft, D-01 open |

### Audit findings

Evidence is the audit's own reproduction, re-run against the merged tree (every case that asserted the old behaviour now deviates), plus the named regression tests.

| Finding | Fixed in | Regression evidence |
|---|---|---|
| ME-01 compound shell status | `62628c3`, `bc42b9a` | `test_compound_command_exit_does_not_prove_each_step_ran`, `test_compound_shell_status_does_not_claim_each_script_succeeded` |
| ME-02 command and folder failures | `77f4761`, `35ffbb8` | `verify` tests for failed command, zero-run folder, job state and supersession by step |
| ME-03, ME-06, ME-08 reapproval, skipped pins, producer attribution | `62628c3`, `bc42b9a` | reproductions C03, C07, R-E1 deviate; `test_competing_timestamp_writers_are_a_gap` |
| ME-04 wrapper options | `c9ea373`, `a9a188f` | `test_wrapper_option_values_do_not_hide_gated_runs`, `ReviewFixesTest` |
| ME-05 paths with spaces | `62628c3` | `test_quoted_script_with_spaces_is_granted_and_pinned_without_fragment_grants` |
| ME-07 launch approval | `610fb53`, `5ce359c` | `test_a_launch_keeps_its_approval_after_expiry_and_a_new_launch_is_denied`, `test_a_plan_approved_after_the_launch_is_not_credited_to_it` |
| ME-09 interrupted preparation | `610fb53` | `test_interrupted_preparation_keeps_the_text_but_refuses_approval` |
| ME-10 header-only claim table | `bc42b9a` | `claim_cell` returns "the table has no data rows"; `test_empty_or_ambiguous_claim_tables_are_gaps` |
| ME-11 gate_diff context | `1381fa4` | `gate_diff.py --self-check` 168/168 on unchanged HEAD |
| D-01 capacity note write | not fixed | draft feature, deferred with its registrations |

### Remaining release blockers

1. A06: real quota acquisition, native compaction and positive worker lifecycle, Claude terminal rendering.
2. A08: real model journeys across the 11 skills and human assessment of confirmations, handoffs, hardening and promotion.
3. A09: reviewer identities, access and cost bounds; approval of the concrete packet; five scheduler tasks.
4. A10/A11: remote CI and Pages on the final commit, a fresh marketplace installation, and the installed plugin cache (0.9.61 on the author's machine) updated.

None of these is closed by a local pass, and software checks do not establish scientific correctness.

## Execution fidelity (0.9.75)

The source-verified roadmap of 2026-10-16 (C01–C13, F01–F11) is tracked in [07 · Execution fidelity](../roadmap/07-execution-fidelity.md), which holds the current evidence, the changed assertions and the items still blocked. Where this file says "42 exact differences" or "`ablate.py` 4/4", that tracker is current. The release blockers above are unchanged: the roadmap work adds no native, human or reviewer qualification.
