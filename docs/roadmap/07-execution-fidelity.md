# 07 · Execution fidelity (implementation tracker)

Objective: fewer consequential AI deviations falsely presented as acceptable, without making ordinary research unnecessarily cumbersome.

This is the single tracker for the source-verified roadmap of 2026-10-16 (audited at `0dc43f0`, 0.9.72; kept locally as `plans/mycelium_extra_refined_review_and_roadmap_2026-10-16.md`, not in the repository). Change sets are `C01`–`C13`, findings `F01`–`F11`; historical `M*-T*` IDs are cross-references only. The deleted review bundles are not recreated or edited. Statuses: **done** (implemented, regression evidence named), **partial**, **todo**, **superseded** (a better current implementation, with evidence), **blocked** (needs access or a decision named in the row).

## Starting state

- Start: `db2c9f7` on `main`, version 0.9.74, six commits ahead of `origin/main` (`0dc43f0`, 0.9.72), unpushed. An agent was fixing the three 0.9.72 known limits (dynamic wrapper cwd, split `sbatch --wrap` approval, legacy `ready`) on `fix/approval-gaps`; that work is folded into C01 and C04 below.
- Since the audited revision: D10 latency log and opt-in checkpoint (0.9.73, user decision 2026-10-16), `verify runs` lister and citation check (0.9.74), H1 closed as covered and E1b parked (docs).
- All eleven Appendix A probes were rerun on `db2c9f7` (Python 3.12, upstream Mycelium `8f8b167`) and all eleven still reproduce: F01 `CONFORMS` with a timing producer; F02 `pins_checked: true` without Pre; F03 `steps: 1 same`; F04 one approval file with new pins; F05 second take finds no record; F06 and F07 `CONFORMS`; F08 earlier failure not shown; F09 not denied; F10 pins `data/cohort`; F11 Extra passes, Mycelium blocks.
- Codex 0.160 sends `tool_use_id` in its PreToolUse input (`codex-rs/hooks/src/events/pre_tool_use.rs`), so a missing call id is an edge case (older hosts, synthetic callers), not the normal Codex path.

## Field contract

Fixed before the gate and verify lanes start, so both sides code against the same records. New fields are additive; a record without them is **legacy** and is read with the weaker meaning stated here, never upgraded.

| Record | Fields added | Meaning and legacy rule |
|---|---|---|
| Approval instance (new file `approval-instances/<hash>/<instance_id>.json`) | `schema` `mycelium-extra.approval-instance.v1`, `instance_id` (16 hex of sha256 over the canonical instance body), `hash` (short plan hash), `plan_sha256` (full), `approved_at`, `session_id`, `pins`, `scripts`, `validation` (C06 bindings, or absent), `execution` (C07 exact declarations, or absent), `limitations` (list of strings), `prepared` (`complete` or `legacy-no-ready`) | Immutable; never rewritten. `approvals/<hash>.json` stays the compatibility view of the newest instance and gains `instance_id`. An approval file without `instance_id` is legacy: one implicit instance, history before it unknown. |
| Launch record (`launches/<key>.json`) | `attempt_id`, `call_id` (host id or null), `started`, `cwd`, per segment entry `instance_ids` `{hash: instance_id}`, `outputs_before` `{path: [size, mtime_ns]}` for declared outputs (bounded), `limitations` | Keyed by call id; without one, by session and command, and a second identical launch before the first completes marks both `ambiguous`. A launch record not taken within the expiry window is moved to `launches/abandoned/`, not deleted. |
| Receipt | `attempt_id`, `call_id`, `launch_match` (`matched`, `unmatched`, `ambiguous`), `approval_instance`, `outputs_changed`, `outputs_observation` (`observed` or `skipped: <reason>`) | `pins_checked` is true only when `launch_match` is `matched`. Unmatched and ambiguous receipts may still name a covering plan as context, but they are not checked launches. A receipt without `launch_match` is legacy: shown as "launch link not recorded", never as matched. |
| Gate error (`gate-errors.jsonl`) | `event`, `decision`, `host`, `session_id`, `call_id` when decodable | Verify reports an error inside the plan's observation window (approval to now, same session or unknown session) as a gap; errors outside the window are ignored. |
| Output evidence (verify result rows) | `producer_attempt`, `evidence_method` (`attempt-observed`, `workflow-record`, `timing-only`, `none`), `strength` (`supported`, `candidate`, `unresolved`), `candidates`, `reason` | Only `supported` fills the producer. `attempt-observed` needs a matched attempt that saw the declared output change between Pre and Post and no overlapping attempt that could have written it. Timing alone is at most a candidate and is always a gap. |
| Validation binding (plan text) | `<!-- validation-bindings {...} -->`: `version` 1, `checks` [{`id`, `plan_row`, `required`, `defined_by` (`agent-proposed`, `researcher-approved`, `independent`), `test_paths`, `invocation`, `evidence_path`}] | Frozen by plan approval; referenced files pinned in the instance. A result counts only if `evidence_path` changed inside a matched attempt of `invocation` under that instance, with the pinned test files unchanged. Otherwise not run, changed or unattributable. `defined_by` is recorded, not proven. |
| Exact execution (plan text) | `<!-- exact-execution {...} -->`: `version` 1, `steps` [{`row`, `argv`, `cwd`, `env`, `operational`}] | Optional, for reportable runs only. A covered invocation must match a declared argv and cwd, except flags listed in `operational`. Plans without it keep broad path and command grants, and the card says so. |
| Review consent (`review-consent/<digest>.json`) | `schema` `mycelium-extra.review-consent.v1`, `digest`, `session_id`, `ts`, `prompt` | Written only by the gate's prompt hook when the user types `send packet <digest prefix>`. `review_packet.py verify` refuses without it. |

## Change sets

| ID | Requirement (roadmap section 4) | Files | Depends on | Status | Evidence | Limits / blocker |
|---|---|---|---|---|---|---|
| C01 | Truthful observation: `pins_checked` from a matched launch; gate errors carry identity and are read by verify; unresolved wrapper cwd is diagnosed, not silently ungated; timing-only ownership is a graded gap; scope near the top of the report; docs | `hooks/gate.py`, `hooks/gate_run.py`, `skills/verify/scripts/verify.py`, `docs/verification.md`, `skills/verify/SKILL.md` | none | todo | | Timing grade ships with the C05 observation so ordinary direct runs keep a supported producer |
| C02 | Complete approval differences before display truncation; removed and reordered rows; ID column; verify `plan_rows`/`plan_changes`/`diff_plans` | `hooks/gate.py`, `skills/verify/scripts/verify.py`, `skills/grill/references/run-plans.md` | none | todo | | |
| C03 | Literal quoted input and output paths with diagnostics; strict table reader backported from Mycelium; compatibility corpus | `hooks/gate.py`, `skills/data-contract-check/**`, `tests/test_contract_compatibility.py` | none | partial: reader done; gate paths in progress | reader: `93e87b7`, `e5ecffd`; `TableReaderTest` (7 of 10 fail on the old reader: ragged row, empty extra field, unterminated quote, invalid UTF-8, unsupported extension, blank header, strict H5AD decode), `tests/test_contract_compatibility.py` (15 cases, same block/pass as Mycelium `8f8b167`) | duplicate non-blank headers stay a gap in Extra where Mycelium blocks (documented in the corpus); the corpus covers reading only, not the diverged checks |
| C04 | Immutable approval instances; attempt ids; ambiguity without call id; abandoned attempts kept; `sbatch --wrap` as one contract; legacy readiness qualified; `note_first_runs` lock; unique snapshot temp names; verify and provenance read both | `hooks/gate.py`, `skills/verify/scripts/verify.py`, `hooks/provenance.py` | C01, C03 | todo | | |
| C05 | Producer from qualified evidence: before/after observation of declared outputs; graded `wrapper_receipt`; upstream lineage consumed with its limits; bundle keeps evidence method; Slurm completion separate from submission | `hooks/gate.py`, `skills/verify/scripts/verify.py` | C01, C04 | todo | | Mycelium lineage is static; never treated as producer proof |
| C06 | Approved validation bindings linked to executed results; `hooks/validation.py`; contract result records; covered `V-02b` variant | `hooks/validation.py` (new), `hooks/gate.py`, `skills/verify/scripts/verify.py`, `skills/data-contract-check/**`, `skills/grill/**`, `skills/new-analysis/templates/PLAN.md`, `tests/e2e/**` | C03–C05 | todo | | No test execution inside verify |
| C07 | Recovery history visible; exact execution declarations for reportable steps; operational overrides; docs and tracker template | `skills/verify/scripts/verify.py`, `hooks/gate.py`, `skills/grill/references/run-plans.md`, `docs/approval-gate.md`, `skills/new-analysis/templates/TRACKER.md` | C04, C06 | todo | | |
| C08 | Declared scientific checks the fixture justifies: DC-08 contrast, DC-09 sample alignment, DC-10 identifiers, DC-11 layer, forbidden covariate | `skills/data-contract-check/**`, `skills/grill/references/*.md`, `tests/e2e/defects.py` | C03, C06 | todo | | Uninstrumented originals stay known misses |
| C09 | Bounded exploration scoped to an approved plan; protected contract changes surfaced; promotion needs a fresh approved run | `hooks/gate.py`, `skills/verify/scripts/verify.py`, `skills/grill/SKILL.md`, `docs/usage.md` | C04, C07 | todo | | Advisory boundaries labelled advisory |
| C10 | Reportable qualification separate from status; `--require-reportable`; short evidence table; content staleness; claims coverage; `gate_init --diagnose`; rerun declared versus performed | `skills/verify/scripts/verify.py`, `skills/init/scripts/gate_init.py`, `docs/verification.md`, `skills/grill/references/run-plans.md` | C04–C08 | partial: `--diagnose` done | `--diagnose`: `d8272d5` (9 tests; read-only checked by file listing and mtimes) | diagnose mirrors the gate's config rules instead of importing them, so the two can drift | No composite trust score |
| C11 | Review consent bound to packet bytes: digest, `review_packet.py`, gate consent prompt, docs | `skills/plan-review/**`, `hooks/gate.py`, `docs/design/c3-plan-review-redaction-audit.md` | none | partial: packet and verify done; gate consent prompt todo | `23db3dd`: `presend_check.py --json` with packet sha256; `review_packet.py` prepare/preview/verify; `test_review_packet.py` 14 tests (edited packet, changed attachment, other digest, no consent, stale consent refuse; identical packet passes) | until the gate writes consent, `verify` always refuses | Cooperative, not a sandbox |
| C12 | Evaluation of false reassurance and burden: scenarios, keys outside agent-visible fixtures, rubric, deterministic scorer, F01–F11 e2e boundary cases, native journeys | `tests/eval/**`, `tests/e2e/**`, `docs/plans/2026-10-16-live-validation/**` | baseline none | partial: scaffold done; F01–F11 e2e cases todo | `7252784`: 14 scenarios (7 development, 7 held-out), keys separate, rubric, `score.py`, `tests/test_eval_score.py` 25 tests on synthetic adjudications only; journeys J15–J18 and host checks H01–H09 marked NOT RUN | held-out workspace variants and the workspace harness not yet written | Real runs and human adjudication blocked (below) |
| C13 | Documentation and backlog reconciliation | `docs/usage.md`, `docs/mycelium-integration.md`, `skills/verify/SKILL.md`, `skills/grill/references/run-plans.md`, this file, `docs/roadmap/README.md`, `06-anti-gaming.md`, `docs/development.md`, `docs/plans/*`, release files | each change set | todo | | |

## Findings

| ID | Change set | Fail-before evidence | Regression and control | Status |
|---|---|---|---|---|
| F01 single timing candidate credited | C01/C05 | probe on `db2c9f7`: `CONFORMS`, `by` the print-only script | | todo |
| F02 Post without Pre claims checked pins | C01 | probe: `pins_checked: true` | | todo |
| F03 change beyond 200 characters reported same | C02 | probe: `steps: 1 same, 0 new or changed` | | todo |
| F04 same-prose reapproval overwrites the only freeze | C04 | probe: one approval file, new pins | | todo |
| F05 identical calls without call id share a record | C04 | probe: second take finds none | | todo |
| F06 validation prose not enforced | C06 | probe: `CONFORMS` with 1 of 60 rows | | todo |
| F07 gate error not reconciled | C01 | probe: `CONFORMS`, no mention | | todo |
| F08 earlier failure hidden after changed retry | C07 | probe: script `ran`, failure not rendered | | todo |
| F09 frozen script accepts changed arguments | C07 | probe: not denied | | todo |
| F10 quoted input path split | C03 | probe: pins `data/cohort` | | todo |
| F11 ragged row passes Extra's checker | C03 | probe: Extra pass/pass, Mycelium block/block | `TableReaderTest` ragged-row case (fails on the old reader); valid CSV/TSV and date-like id controls | done (`93e87b7`) |

## Already implemented before this tracker (preserve)

| Roadmap statement | Current source | Evidence |
|---|---|---|
| Interrupted preparation not approvable | `on_stop` writes `ready: False` until pins, scripts and card finish; `on_prompt` refuses | `test_interrupted_preparation_keeps_the_text_but_refuses_approval`, `test_a_fully_prepared_plan_is_approvable_on_the_first_prompt` |
| Launch and receipt correlated | `write_launch`/`take_launch` keyed by call id, per segment and paths, kept after expiry | `test_a_launch_keeps_its_approval_after_expiry_and_a_new_launch_is_denied`, `ReviewFixesTest` |
| `V-20` competing writers caught | competing timestamp writers are a gap | `test_competing_timestamp_writers_are_a_gap`, e2e `V-20` |
| Command and folder failures judged, retries superseded by step | `check_receipt`, `step_key`, `judge_job` | the 0.9.71 verify tests for failed command, job state and step supersession |
| Recoverable provenance publication | `hooks/provenance.py` | `hooks/tests/test_provenance.py` |
| D11 run limit | opt-in `max_runs_per_approval` | D11 gate tests; kept optional, not in the default journey |
| D10 latency log and checkpoint | **superseded** the roadmap's "defer D10": the user approved it on 2026-10-16; latency is only logged (no scoring or display) and the checkpoint is off by default | `ApprovalLatencyTest` |

## Blocked or deferred (with return condition)

| Item | Why | Exact approval or access needed |
|---|---|---|
| Native Claude/Codex qualification of the new records | needs real host sessions; the user declined changing `~/.codex` for H1 (2026-10-16) | a disposable host install the user approves |
| Real model journeys and human adjudication (C12) | paid calls and people | approval of the packet in `docs/plans/2026-10-16-live-validation/` and named adjudicators |
| External reviewer calls (C11 qualification) | paid, sends material | the same packet approval |
| Python 3.14 leg | no interpreter on this machine | remote CI on a pushed commit |
| Publishing (push to `origin/main`) | the installed plugin follows it | the user's explicit go-ahead |
| Capacity and diary drafts, D-01 | out of scope for this roadmap | separate qualification |

## Changed assertions

Every existing test assertion changed by this work is listed here with its reason.

| Test | Change | Reason |
|---|---|---|

## Evidence log

- 2026-10-17: probes rerun on `db2c9f7` (all reproduce); upstream checkout `8f8b167` at `/exports/para-lipg-hpc/mdmanurung/mycelium-upstream-8f8b167` (outside the repository).
- 2026-10-17: merged the 0.9.72 known-limit fixes (`d03f099`): `$PWD`/`$HOME` resolved in wrapper folder options, other expansions make the folder unknown and are denied unless either reading is covered (C01); `sbatch --wrap` credited only to a plan naming both (C04); a legacy pending entry without `ready` is approvable only with `scripts` or a timestamp before 0.9.44 (C04). `OpenGapsTest`, 15 tests, 7 fail on the old gate.
