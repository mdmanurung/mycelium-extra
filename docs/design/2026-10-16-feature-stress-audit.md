# Feature stress audit, 2026-10-16

Status: local audit complete, with the qualification gaps below. Software checks establish the observed
behavior below; they do not establish scientific validity or universal agent
compliance. The checkout exposes **11 skills**, including **8 verify actions**.

## Starting state and ownership

Starting and current base HEAD: `384e6394b71cdae6ab983f0b10fa8d4f5e65c900`.
Six files were already modified: `docs/design/c1-fixture-project.md`,
`hooks/gate.py`, `hooks/tests/test_gate.py`, `skills/verify/scripts/verify.py`,
`skills/verify/tests/test_verify.py`, and `tests/e2e/defects.py`.
Their original bytes, hashes and patch are preserved in
`/tmp/mycelium-audit-20261016/root/original/`, `baseline.json`, and `baseline.patch`.
The existing run-limit implementation was retained.

During the audit, concurrent changes added the 0.9.71 version/changelog entries,
run-limit documentation and roadmap status. Those changes were preserved and are
not attributed to this audit. No version bump, commit, push, publication, real
scheduler submission, paid reviewer call, or personal host-configuration change
was performed by the audit.

The user requested parallel agents. Ownership was gate/hooks, verification/e2e,
and the other ten skills; the coordinator handled integration, draft recovery,
compatibility, native discovery and this report. A verification worker then
independently reviewed the gate and checkpoint fixes without editing them.

## Feature coverage matrix

**Passed** means an observed executable check at the stated layer. **Partial**
means executable helpers or contracts passed but agent behavior or a real host
journey remains unobserved. **Draft** is not release qualification.

| Feature | Checks and evidence | Result |
|---|---|---|
| grill | 10 reference/contract tests; decision coverage, defaults, run-plan freeze, read-only boundary | Partial: actual reasoning, question caps and readiness judgments not qualified |
| init | 19 tests: idempotence, nested roots, coverage, ignore handling, tool discovery, compatibility, invalid hours/config | Passed helper and gate integration |
| new-analysis | 17 tests: mixed steps, ordinary/Mycelium trees, links, overwrite refusal, generated code and quoted paths | Passed scaffold; real R stub tested; workflow engine simulated |
| plan-review | Default-reason, packet-role and pre-send tests; quoted paths, BOM, identifiers, secrets, missing-table gaps | Partial: helpers passed; no external review/adjudication |
| data-contract-check | 32 tests: schema, cohorts/counts, replication/crossover, pairing, batch nesting/imbalance, filters, malformed contracts, H5AD obs | Passed all 32 in an existing h5py environment; 7 H5AD skips in standard matrix |
| decision-status | 10 parser tests: dates/fields, tags, fenced examples, invalid regex | Partial: parser passed; contested resolution and confirmed append remain agent contracts |
| verify list/report/write | Runs, code/input changes, outputs, claims, lint/waivers, conda/pip, repeat provenance writes | Passed deterministic helper/e2e checks; saved bundles are not transactional |
| verify stale/status | Committed provenance, edited/deleted inputs/code/outputs, manifests, lint coverage | Passed synthetic integration |
| verify diff/multiplicity/explore | Pending/approved revisions, choices, prior tries, sessions, code versions | Passed synthetic records; history is limited to retained evidence |
| handoff | Contract review plus gate tests executing its pending-plan commands and fresh-session approval rules | Partial: complete agent reconstruction in a fresh native session unobserved |
| idea | Pending approval preserved; actual Mycelium 0.7.2 helper with duplicate titles | Partial: helper keeps both File-keyed rows; agent capture and concurrent slug allocation unobserved |
| idea-triage | Rubric, unknown ratings, missing files, park-all, selection and File-keyed updates | Partial: contract/helper reviewed; live ranking/choice flow unobserved |
| harden | Candidate eligibility, failing reproduction/passing current behavior, narrow confirmed learning update | Partial: procedural review; no real learning was selected or changed |
| Approval/cards | Session/hash/expiry, Step-only grants and legacy records, diffs/digests, exact grants, spaced literal paths | Passed hook tests; native Claude plan/card/approval observed with local scripted API |
| Input/script pins | Mutation, first-run pins, notebook code, folders/budgets, corrupt ledgers | Passed deterministic tests; directory/mtime fingerprints retain documented limits |
| Receipts/wrappers | Environments/Git, success/failure/unknown, compound/background calls, scheduler IDs | Passed adapters and native Claude simple-run receipt; real scheduler not submitted |
| Lint lifecycle | Approval/write/pre-run/pre-stop, both languages, notebooks/documents, waivers, budgets, concurrent writes | Passed deterministic suite plus actual Python scilintr and R4_51 checks on all three interpreters |
| Exploration/hints | Explicit session grant/revoke, non-reportable runs, promotion into a fresh plan, routing and reminders | Passed hook/helper tests; complete agent-led promotion remains partial |
| Error/state protection | Invalid approval denial, alias writes, internal allow/deny, unavailable tools, unreadable state | Passed direct/launcher tests; shell interpretation remains heuristic |
| Claude integration | Manifests and real CLI hook dispatch, denial, plan presentation, approval, execution, success receipt | Passed native control flow against a loopback scripted API; agent judgment and terminal rendering unqualified |
| Codex integration | Disposable install, app-server discovery, 11 skills, 5 hook entries across 4 event types, cache hashes | Discovery passed; hooks remain untrusted in disposable state, so native execution dispatch unobserved |
| Mycelium integration | Fixture decisions/manifests/lineage, actual File-keyed registry helper, actual diary adapter | Passed named helper/fixture checks; full installed-plugin lifecycle not qualified |
| Capacity draft | 15 new tests shared with diary: allowance boundaries/staleness, sticky pause/fresh resume, ownership, checkpoints, process recovery | Draft: deterministic checks passed; real allowance APIs and unregistered lifecycle events unqualified |
| Diary draft | Edited draft preservation, human-review guard, append/idempotence; actual installed Mycelium registry adapter | Draft: checks passed; full human editing/host lifecycle not qualified |
| Package/docs | Interpreter/locale matrix, fixtures, generated example, versions, links, Sphinx | Passed executable checks; gate-diff deliberately reports approved behavior changes |

## Reproduced defects repaired

| Area | Before | After |
|---|---|---|
| Compound/background receipts | Final shell exit credited to failed, skipped or merely launched steps; one job ID copied to multiple submissions | Per-step execution unknown; aggregate status retained; aggregate failure blocks verification; job output not misattributed |
| Gate state aliases | Bash could write gate state through a symlink without spelling the state directory | Existing targets resolved; state writes denied while ordinary reads/pipes remain allowed |
| Spaced script paths | Explicit quoted paths were denied or parsed into unintended fragments | Existing literal paths are granted/pinned whole; fragments grant nothing |
| Corrupt approvals/pins | Nonobjects, damaged JSON, nested fingerprints and impossible dates could invoke generic fail-open behavior or crash inventories | Controlled invalid-state denial/error; supported legacy records retained |
| Claim tables/numbers | Header-only tables and extreme numbers crashed; duplicate columns could falsely verify | Ambiguous/missing cells and unsupported numbers are explicit gaps or finite contradictions; other claims still checked |
| Damaged execution evidence | Malformed receipts/workflow metadata could disappear silently or crash checks | Report records incomplete-history/workflow gaps; malformed approvals produce explicit errors |
| Data contracts | Empty/no-op checks could pass; string false enabled crossover; wrong types crashed or coerced | Meaningful assumptions and exact shapes/types required; duplicate headers are unreadable-table gaps |
| Initialization | Nonfinite hours and nonobject persisted state crashed or looked successful | Clear nonzero usage/state errors; existing gate remains untouched |
| Generated analysis code | Quotes/backslashes in data paths broke generated Python/Snakefile strings | Generated strings use escaped literals; R/Python/notebook stubs and links checked |
| Review pre-send | Quoted input paths/BOM headers hid identifiers; missing tables omitted from coverage | Correct path/header reads and explicit unchecked-table notices; pattern-based limits retained |
| Ideas | Same-title registry upserts replaced another idea despite different files | Capture and triage key by exact File cell; actual helper retains both rows |
| Decisions | Nested/short fences created fake decision entries; bad regex crashed | Matching fence delimiter/length tracked; invalid regex produces usage error |
| Recovery checkpoints | Missing/malformed input reported saved; corrupt existing record overwritten | Refuse before writing and retain recovery evidence |
| Coherence/test oracles | Host wording claimed Claude-only support; idea said no code while using helpers; differential harness compared unequal dependencies | Host-neutral wording, analysis-code boundary, File-keyed triage/park-all rules, equivalent helper layouts and warning normalization |

Every code repair has a failing-before regression or reproduction followed by a
passing check. Instruction-only changes have contract/helper evidence, not an
invented native behavioral pass. Full worker reports and commands are in
`/tmp/mycelium-audit-20261016/{gate,verify,skills}/REPORT.md`.

## Validation receipts

- Frozen full matrix: **555 tests discovered per interpreter, 12 skipped**, on
  Python 3.6.8 / `LC_ALL=C`, Python 3.12.15, and Python 3.14.5. All test files pass.
  This includes 79 end-to-end tests (2 optional skips), fixture data, generated
  example, frontmatter and version checks. Source hashes remained unchanged
  throughout the matrix.
- The final background/timestamp review changed only `hooks/gate.py` and its
  test file after that snapshot. Final full gate reruns are recorded separately
  below; other runtime files match the frozen matrix. The complete final gate
  suite passes **255 tests (2 optional skips)** on each interpreter. Replacing
  the earlier 253 gate tests gives **557 discovered / 545 passed / 12 skipped**
  per interpreter across the qualified suites.
- All **4 guard ablations** bite on each interpreter: removing a guard makes its
  intended defect case fail. They are independent from simply asserting the
  implementation's output.
- Differential gate comparison: **145/167 identical** on all matrix versions.
  The exit status is deliberately 1. The **22 intended changes** are four new
  boundary decisions (state alias, whole spaced path, forbidden fragment grant,
  corrupt approval) plus 18 conservative compound-receipt differences. No
  unexpected difference was observed. Identical-source harness check: 167/167.
- Real linters: **2 tests per interpreter**, direct and launcher, all pass using
  existing Python scilintr 0.1.2 and R4_51 (R 4.5.1 / scilintr 0.1.1).
- H5AD/CSV/TSV contract suite: **32/32 pass** in an existing h5py environment.
- Additional bounded contract mutations: **96 cases**, no unhandled exceptions.
- Ordinary and synthetic Mycelium scaffold integrations pass with a simulated
  Snakemake; no claim of actual workflow-rule execution.
- Actual installed Mycelium 0.7.2 diary adapter: reviewed append, duplicate-save
  idempotence and authored-field preservation pass; a prefix-only session match
  is refused and its draft retained.
- Claude Code 2.1.301 marketplace/plugin manifests validate. Native CLI against a
  local scripted Anthropic-compatible endpoint denied an unapproved run, emitted
  a plan card, accepted its hash in the same resumed session, ran the approved
  synthetic script and wrote an exit-0 receipt. API responses were scripted:
  this qualifies dispatch and control flow, not agent reasoning or TTY rendering.
- Codex CLI 0.161.0 disposable installation discovered all 11 skills and its hook
  definitions. **75 tracked plugin files match source byte-for-byte** after a
  final reinstall. Global skills outside this project include one unrelated
  frontmatter error; no Mycelium Extra discovery error was observed.
- Sphinx builds with warnings as errors. Its already-declared Mermaid extension
  was installed only under `/tmp` for the check; project dependencies and personal
  environments were not changed. Tracked Markdown links pass on all versions.

Machine-readable results and complete logs are under
`/tmp/mycelium-audit-20261016/root/`: `final-suite-summary.json`, `matrix-results.json`,
`matrix-source-changes.json`, `candidate-hashes.json`, `final-runtime-hashes.json`,
`final-gate-results.json`, `real-linters-results.json`,
`native-final-cache-check.json`, `docs-build.log`, and the native CLI transcripts.
These log directories are temporary; this report preserves the conclusions and
reproduction commands.

## Reproduction

Run the CI test-file loop with each available interpreter, keeping `python3` on
PATH aligned with that interpreter; the 3.6 leg uses `LC_ALL=C`:

```bash
for t in hooks/tests/test_*.py skills/*/tests/test_*.py tests/test_*.py; do
  python3 "$t" || exit 1
done
python3 tests/e2e/ablate.py
python3 hooks/tests/gate_diff.py
python3 tests/check_links.py $(git ls-files '*.md' ':!:mycelium-extra-improvements/**')
```

`gate_diff.py` is expected to exit 1 against the starting HEAD for the exact
intentional differences above; inspect its cases rather than suppressing the
exit or updating an oracle to match blindly. The coordinator's recorded runner
is `/tmp/mycelium-audit-20261016/root/run_matrix.py`.

For real tools, set `MX_E2E_REAL_TOOLS=1`, `MX_E2E_SCILINTR` to the installed
Python CLI and `MX_E2E_RSCRIPT` to R4_51's Rscript, then run
`GateTest.test_write_lint_with_real_scilintr` and
`LauncherTest.test_write_lint_with_real_scilintr` in `hooks/tests/test_gate.py`.
Run the full data-contract suite using an interpreter with h5py for its seven
H5AD cases. Build docs with the declared requirements and the command in
[Development](../development.md).

## Remaining risks and qualification gaps

1. Live agent compliance is partial: scientific grounding, question caps,
   confirmations, triage judgments, handoff reconstruction and learning
   hardening need separate observed interactions. No paid reviewer or private
   review packet was sent. A verified number matches its cell, not scientific truth.
2. Codex native hook dispatch and actual terminal rendering are not qualified.
   Discovery, cached source parity and launcher tests do not replace that evidence.
3. Real Slurm/Nextflow/Snakemake execution was not performed. Scheduler and
   workflow metadata checks are synthetic; actual R/Python linters and H5AD reads
   were exercised separately.
4. Provenance updates span several files and are not transactional across
   interruption or concurrent writers. Retain receipts and re-run verification
   after an interrupted save. Timestamp-based output attribution is uncertain;
   hidden dynamic shell execution, notebook MCP tools and metadata-only pins
   retain their documented limits.
5. Capacity and diary remain drafts. Allowance API compatibility, native pause
   behavior and full worker lifecycle recovery are not qualified. SessionStart,
   SubagentStart/Stop, PreCompact and SessionEnd handlers are not registered by
   the current hook manifests. Pattern-based redaction misses short IDs/free
   text and cannot guarantee de-identification. Concurrent idea slug allocation
   and scaffold mid-write rollback were not qualified.

## Final workspace state

All audit changes remain uncommitted for review, including this report and the
new capacity/diary regression file. The six starting modifications and concurrent
0.9.71 run-limit work remain present. HEAD stayed at the starting commit.
`git diff --check` and this report's relative links pass. Runtime hashes and the
source/cache comparison are recorded with the final receipts; no runtime source
changed during the final gate reruns.
