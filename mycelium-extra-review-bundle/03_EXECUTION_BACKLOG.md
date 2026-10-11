# Mycelium Extra — Canonical Execution Backlog (revised 2026-10-06, scope-aligned)

Second revision. The first made the plan executable; this one aligns it with the aims of Mycelium and Mycelium Extra
(`00_EVALUATION.md`, "Second pass"). Original IDs are kept and never renumbered; new work takes the next unused number.

## Numbering convention

| Type | Format | Example |
|---|---|---|
| Milestone | `M#` | `M3` |
| Task | `M#-T##` | `M3-T06` |
| Gate | `M#-GATE` | `M3-GATE` |
| Existing defect | existing ID | `DC-09`, `V-20` |

Existing roadmap IDs (`C3`, `D2`, ...) appear in parentheses and in the crosswalk in `00_EVALUATION.md`.

## Columns

- **Effort**: **S** < 2 h, **M** half a day to a day, **L** several days (4 d). Single maintainer.
- **State**: `active`; `cond` (starts only if the named condition holds); `parked` (keeps its ID; reactivation
  evidence in `05`); `parked: research track` (belongs to Track R below); `parked: publish decision`; `dropped`;
  `merged → X`; `maintainer` (needs the repository owner).

## The scope filter (`G13` in `02`) — every task passes it

1. Is it plan, approve, or check-the-execution-record work (or scaffolding)? Otherwise it belongs to Mycelium, Track R, or nowhere.
2. Does Mycelium already do it? Then **consume Mycelium's record** and build only the link to the plan and approval.
3. Does it still work in a plain repository? There it is a **fallback**, reported as weaker evidence or a gap.
4. Is the need shown in the user's own repositories (about 10 sibling Mycelium repos) or the fixture?

## Binding constraints on every task

Python 3.6 and stdlib only for hooks and skill scripts (an optional reader such as `h5py` is detected; its absence
is a **gap**); friction is opt-in; complement Mycelium and never override it (no writes to `.living/` except
confirmed appends); no SessionStart messages; plain-text hook notices; one feature = `feat`/`fix` commit +
`chore: bump version` across the three manifests; `hooks/tests/gate_diff.py` before and after any `gate.py` change;
each task goes through `/mycelium-extra:grill` and an approved plan.

---

# M0 — Foundation

**Question:** Are scope, guarantees, host capabilities and the division of labour with Mycelium explicit?

| ID | Task | Depends on | Effort | State |
|---|---|---|---|---|
| **M0-T01** | Say in the status output and `docs/verification.md` that conformance is not scientific correctness (statuses exist at `docs/verification.md:29`) | — | S | active |
| **M0-T02** | One-page threat model, consolidating `docs/approval-gate.md:103,109` plus the protects / does-not-protect lists | — | S | active |
| **M0-T03** | Host-capability table (Claude Code vs Codex) from existing docs | — | S | active |
| **M0-T04** | Decide B5 and repair `HANDOFF.md` (header says d4391b0 / 0.9.42; repo is 72119ef / 0.9.43) | — | S | active |
| **M0-T05** | Stale-handoff check | M0-T04 | — | merged → `M7-T10` |
| **M0-T06** | Protect `main`, require CI (GitHub setting; needs a push) | — | S | maintainer |
| **M0-T07** | Schema-versioning convention; hand-written validators (no `jsonschema`). Includes the migration note formerly `M9-T07`. | — | S | active |
| **M0-T08** | Mycelium version check in `init`, notice only (roadmap A5). Mycelium 0.7.2 is installed; 0.6.0 is also cached. | — | S | active |
| **M0-T09** | Add non-goals and a **consume, don't rebuild** list to `docs/mycelium-integration.md`: Mycelium owns memory, run lineage, report values, review tripwires and ingest provenance; Extra reads them. | — | S | active |

Maintainer actions: A1 confirm MIT (name settled: "Mikhael Manurung"); A3 tags from `v0.9.16`
(`mycelium-extra-improvements/notes/docs.md:24`; hashes there stop at 0.9.30); A4 `gh repo edit`
(`mycelium-extra-improvements/APPLY.md:79`). A3 and A4 need a push, which the user does only on request. The staging
folder's `IMPLEMENTATION-MAP.md` is superseded by this backlog.

---

# M1 — Execution Integrity

**Question:** Can Extra say which run produced which output, using Mycelium's record where it exists?

Order of evidence for lineage: (1) **Mycelium's data-lineage record** (`.living/log/data-lineage/<session>.json`: per
run, script, inputs and outputs with SHA-256, exit; python, R and jupyter only; written at session Stop); (2) Extra's
own before/after fingerprints of plan-declared outputs, for what Mycelium skips (`sbatch`, `snakemake`, `nextflow`,
plain shell) and for repositories without Mycelium; (3) timing, reported `weak`.

## Run identity

| ID | Task | Depends on | Effort | State |
|---|---|---|---|---|
| **M1-T18** | **Spike (two parts).** (a) Which fields in each host's `PreToolUse` / `PostToolUse` payloads key one command across both events? `hooks/gate.py` uses no tool-call ID today. Settle `backgroundTaskId` and failure-event hint noise (`mycelium-extra-improvements/notes/e3v2.md`). (b) Map Mycelium's lineage event fields to Extra's receipt fields and find a join key; check how verify behaves when the lineage file is not yet written (session still open) — that state is a gap. | — | S | active |
| **M1-T01** | Define `run_id` (links an Extra receipt to a Mycelium lineage event when one exists) | M0-T07, M1-T18 | S | active |
| **M1-T02** | Add `run_id` to new receipts | M1-T01 | M | active |
| **M1-T03** | Group related execution events by run | M1-T02 | M | active |
| **M1-T04** | Legacy receipts stay readable; no `run_id` = `legacy`, never strong evidence | M1-T02 | S | active |

## Output lineage

| ID | Task | Depends on | Effort | State |
|---|---|---|---|---|
| **M1-T05** | Lineage model: `attributed (mycelium)`, `attributed (extra)`, `unresolved`; no guessing state | M1-T01 | S | active |
| **M1-T06** | Read Mycelium lineage first; fingerprint plan-declared outputs before and after a run only where Mycelium has no record | M1-T05 | M | active |
| **M1-T07** | Workflow-native lineage | M1-T05 | M | parked: no Snakefile in sibling repos (checked 2026-10-05) |
| **M1-T08** | Timing attribution fallback only, `weak` | M1-T05 | S | active |
| **M1-T09** | Fix `V-20`, foreground runs. Background and `sbatch` outputs are `unresolved` until `M6-T08`–`T10`; verify says so. | M1-T06, M1-T08 | M | active |

Invariant: `attributed`, or `unresolved → gap`. Never `wrong attribution → clean verification`.

## Generic output integrity

Check first whether Mycelium's `analyze` "validation requirements" already cover declared outputs; extend
`data-contract-check` only for what they do not. No new checker skill.

| ID | Task | Depends on | Effort | State |
|---|---|---|---|---|
| **M1-T10** | Output declaration in a plan's `Outputs:` entry (required columns, minimum rows, unique key); first a check of Mycelium's validation requirements | M0-T07 | S | active |
| **M1-T11** | Run the existing table checks on declared outputs | M1-T10 | M | active |
| **M1-T12** | Report output integrity in `verify` | M1-T11 | M | active |
| **M1-T13** | Fix `V-02b` where expectations are declared | M1-T12 | S | active |

## Execution modes

Names for the existing usage tiers; no new concept.

| ID | Task | Depends on | Effort | State |
|---|---|---|---|---|
| **M1-T14** | Map `explore` / `approved` / `reportable` onto tiers 1–3 and say what each guarantees | M0-T01 | S | active |
| **M1-T15** | List what a reportable run requires and have `verify` check it | M1-T02, M1-T09, M1-T12 | M | active |
| **M1-T16** | Strong input identity in reportable mode (grep what pinning records today first) | M1-T15 | M | active |
| **M1-T17** | Unmet requirements are gaps or blocks; includes C2, an opt-in `on_error: "deny"` | M1-T15 | M | active |

---

# M2 — Evaluate Extra's Own Claims

**Question:** Does grill surface the consequential choices before code runs, and does the gate-plus-verify chain report
honestly what ran? (Not: does Extra reduce scientific errors; that is Track R.)

Two evaluations. The **execution chain** is already tested by the C1 fixture and defect catalog. The **plan stage** is
what has no test: an LLM step.

| ID | Task | Depends on | Effort | State |
|---|---|---|---|---|
| **M2-T01** | Evaluation directory beside `tests/e2e/` | — | S | active |
| **M2-T02** | Plan-scenario schema: request, repository state, hidden list of required choices | M2-T01 | S | active |
| **M2-T04** | Taxonomy: missed consequential choice, unsourced default, unnecessary question, invented fact | M2-T02 | S | active |
| **M2-T05** | Burden metrics: questions asked, turns, plan length | M2-T02 | S | active |
| **M2-T06** | Five plan-stage scenarios (pseudoreplication, paired design, contrast direction, batch–treatment confounding, reference/sample mismatch) | M2-T02, M2-T04 | M | active |
| **M2-T07** | A lab colleague reviews the hidden lists | M2-T06 | M | active |
| **M2-T18** | **Grill-coverage eval:** run grill on each scenario (scripted user answers, headless host, model and plugin version recorded), score coverage of required choices, sourcing and questions asked. Baseline = the current release. | M2-T07, M2-T05 | M | active |
| **M2-T19** | Add defect cases found in sibling repos to the C1 catalog (known-miss until fixed) | — | M | active |
| **M2-T12** | Failure analysis; feeds `M3` | M2-T18 | M | active |
| **M2-T03** | Scoring-rubric schema for the multi-condition study | M2-T01 | S | parked: research track |
| **M2-T08**–**T11** | Conditions A–D, repeated runs | M2-T07 | M | parked: research track |
| **M2-T13**–**T17** | Study harness, pre-registration, blind double grading, sealed held-out set, current-version pilot | M2-T07 | L | parked: research track |

---

# M3 — Scientific Semantics (as plan content and input checks)

**Question:** Can the choices that matter most be stated in the plan and checked mechanically on the input side?

The "contract" is a structured **Choice block in grill's plan**, not a separate schema layer. Designed from failures
seen in `M2-T12` and the defect catalog. Unknown stays unknown.

| ID | Task | Depends on | Effort | State |
|---|---|---|---|---|
| **M3-T01** | Choose the fields: biological unit, pairing, contrast, sample key, matrix state, reference level | M2-T12 | M | active |
| **M3-T02** | Block format and hand-written validator | M3-T01, M0-T07 | S | active |
| **M3-T03** | grill writes the block | M3-T02 | M | active |
| **M3-T04** | The block freezes with the approved plan | M3-T03 | S | active |
| **M3-T05** | `data-contract-check` reads the block's fields | M3-T03 | S | active |
| **M3-T06** | Sample-key alignment check (same key, same order across matrix and metadata, or a declared mapping) | M3-T02 | M | active |
| **M3-T07** | Fix `DC-09` | M3-T06 | M | active |
| **M3-T08** | Block fields for numerator, denominator, `positive_means` | M3-T02 | S | active |
| **M3-T09** | Synthetic sign-direction spike | M3-T08 | — | merged → `M3-T17` |
| **M3-T10** | `DC-08`: where an output column or claim declares a direction, check it against the data; otherwise list it `HUMAN_REVIEW_REQUIRED` | M3-T08 | S | active |
| **M3-T17** | **Direction tripwire.** The plan carries a direction tripwire specification that Mycelium's `review` tripwires (known-answer / metamorphic, "audit" mode) can run. Spike first: where does review write tripwire results? Verify reports whether a tripwire ran (not run = gap). Extra writes no tripwire code. | M3-T08 | M | active |
| **M3-T11** | Identifier checks in `data-contract-check` (duplicates, empties, date-like gene symbols, mixed ID systems, Ensembl versions). No dependency; quick win. | — | M | active |
| **M3-T12** | Fix `DC-10` | M3-T11 | S | active |
| **M3-T13** | Matrix-state field and check in `data-contract-check`, including AnnData `X` and layers (`h5py` optional; absent = gap) | M3-T02 | M | active |
| **M3-T14** | Matrix-state check hooks (absorbs the former AnnData inspector, `M5-T03`/`T04`) | M3-T13 | M | active |
| **M3-T15** | Improve `DC-11` detection | M3-T14 | M | active |
| **M3-T16** | Plans reference `M1-T10` output declarations instead of restating them | M1-T10, M3-T02 | S | active |

---

# M4 — Fixture Evaluation of a Frozen Release

**Question:** After M3, does the released plugin do better on the plan-stage scenarios and still pass the execution chain?

| ID | Task | Depends on | Effort | State |
|---|---|---|---|---|
| **M4-T01** | Freeze the release under test (plugin version, model IDs, scenario set) | M3-GATE | S | active |
| **M4-T13** | Re-run the grill-coverage eval (`M2-T18`) before vs after M3, on the scenarios M3 was not designed against | M4-T01 | M | active |
| **M4-T14** | Record workflow burden: questions, turns, plan length | M4-T13 | S | active |
| **M4-T15** | Short note: what improved, what did not, what grill still misses | M4-T13, M4-T14 | S | active |
| **M4-T02**–**T12** | Multi-condition comparison, ≥15 scenarios, repeats, ablations, plan-review contribution | M4-T01 | L | parked: research track |

---

# M5 — Data-state checks (no inspector framework)

Inspecting data state is an input check inside `data-contract-check`, grown only when a sibling repo needs it.

| ID | Task | Depends on | Effort | State |
|---|---|---|---|---|
| **M5-T01** | Inspector interface | — | — | dropped: no framework; checks live in `data-contract-check` |
| **M5-T02** | Connect inspectors to contracts | — | — | dropped: as above |
| **M5-T03** | AnnData inspector | — | — | merged → `M3-T13` |
| **M5-T04** | AnnData contract checks | — | — | merged → `M3-T14` |
| **M5-T05**–**T11**, **T16** | Seurat, SCE, VCF, BED/GTF, BAM/CRAM inspectors; reference schema; compatibility checks; genomics fixture | — | M | parked: until a sibling repo cannot be served |
| **M5-T12**–**T15**, **T17** | Bulk, scRNA, longitudinal, cytometry, survival fixture families | M2-GATE | M | parked: add a family when a sibling-repo defect needs one (`M2-T19`) |

---

# M6 — Reproducibility and Provenance

**Question:** Can a reportable run be reconstructed, using Mycelium's records where they exist?

| ID | Task | Depends on | Effort | State |
|---|---|---|---|---|
| **M6-T01** | Snakemake per-rule environments (E1b) | M1-GATE | M | parked: no Snakefile in sibling repos |
| **M6-T02** | Container image digests | M1-GATE | M | parked |
| **M6-T03** | R / Bioconductor / renv metadata | M1-GATE | M | active |
| **M6-T04** | GPU / CUDA metadata | M1-GATE | S | parked |
| **M6-T05** | Compare pinned inputs with Mycelium's ingest checksums (`data/DATA_MANIFEST.md`, `data/metadata/*/provenance.md`); a mismatch or missing entry is a finding or gap | M1-GATE | M | active |
| **M6-T06**, **T07** | Remote-input and database provenance | M1-GATE | M | parked |
| **M6-T08** | Optional compute-job wrapper (the `sbatch` case Mycelium does not track; closes `V-20` for HPC) | M1-T01 | L | active |
| **M6-T09** | In-job receipt | M6-T08 | M | active |
| **M6-T10** | Reconcile submission and in-job receipts | M6-T09 | M | active |
| **M6-T11** | Add a schema field to `PROVENANCE.md`; no separate manifest format | M0-T07, M6-T05 | S | active |
| **M6-T12** | Receipt hash chaining | M6-T11 | M | dropped: the gate is not a security boundary |
| **M6-T13** | RO-Crate export | M6-T11 | M | parked: publish decision |
| **M6-T14**, **T15** | W3C PROV, BioCompute export | M6-T13 | M | dropped |

---

# M7 — Privacy, Disclosure, and Wording

## External-review privacy — start first

`skills/plan-review/SKILL.md:25` already says to show the packet and send only after the user agrees, but that is an
instruction to the agent, not an enforced step. The packet goes to OpenAI and Phylo.

| ID | Task | Depends on | Effort | State |
|---|---|---|---|---|
| **M7-T01** | Redaction audit of packet contents (roadmap C3) | — | M | active |
| **M7-T02** | Deterministic secret / identifier scan; a scan, never proof of absence | M7-T01 | M | active |
| **M7-T03** | Packet written to a file and previewed by hash, so what is shown is what is sent | M7-T02 | S | active |
| **M7-T04** | Send step refuses without a recorded confirmation of that packet hash | M7-T03 | S | active |
| **M7-T05** | Record what left the machine (the skill writes no review record today; a decision for the user) | M7-T04 | S | cond: user decision |

## Claims and disclosure

| ID | Task | Depends on | Effort | State |
|---|---|---|---|---|
| **M7-T08** | A `direction` claim kind in D1's claims block. Report numbers stay with Mycelium's `register_value` pipeline; Extra's block is the fallback and the plan link. | M3-T08 | S | active |
| **M7-T09** | Figure lineage | M1-GATE | M | dropped: Mycelium's lineage already covers script outputs; consumed through M1 |
| **M7-T16** | `disclose` skill: drafts the AI-use methods paragraph from receipts, approvals, verify and claims status; every sentence cites its record; gaps stay blank (roadmap D3) | M1-T02 | M | active |

## Citations

| ID | Task | Depends on | Effort | State |
|---|---|---|---|---|
| **M7-T06**, **T07** | DOI / PMID / arXiv resolution (D2) | — | M | parked: 0 of 10 sibling repos cite DOIs |

## Usability

| ID | Task | Depends on | Effort | State |
|---|---|---|---|---|
| **M7-T10** | `doctor`: host capabilities, Mycelium version, stale handoff, missing optional readers | M0-T03, M0-T08 | M | active |
| **M7-T15** | Worked example: a real transcript on the fixture (roadmap A6) | — | M | active |
| **M7-T11**–**T13** | Top-level `PLAN` / `RUN` / `CHECK` routing skills | — | M | dropped: Mycelium already routes by intent and the usage tiers are the simplification |
| **M7-T14** | Simplify hook and user messages (wording only; no routing) | M8-T09 | S | active |

---

# M8 — Lab Validation

**Question:** Does it work on the user's own repositories and for lab colleagues, not only the fixture?

| ID | Task | Depends on | Effort | State |
|---|---|---|---|---|
| **M8-T09** | Observe 2–3 lab colleagues on the current version, installation to verify; observation only. Needs the worked example. | M7-T15 | M | active |
| **M8-T03** | Run gate and verify on ≥3 sibling repos; every failure goes to `M2-T19` as a defect case | M1-GATE | M | active |
| **M8-T01** | Recruit lab colleagues (not public users) | — | S | active |
| **M8-T02** | Short structured session with each | M8-T01 | M | active |
| **M8-T04** | Record confusion, false confidence, friction, abandonment | M8-T02, M8-T03 | S | active |
| **M8-T05** | Technical failures → regression / known-miss tests | M8-T03 | M | active |
| **M8-T06** | Planning failures → plan-stage scenarios (`M2-T06`) | M8-T03 | M | active |
| **M8-T07**, **T08** | Externally authored hidden cases; re-run | M8-T01 | L | parked: research track |

---

# M9 — Release (deferred until a publish decision)

Extra stays 0.x. These wait for the user to decide to publish.

| ID | Task | Effort | State |
|---|---|---|---|
| **M9-T01**–**T06** | Freeze receipt, run, contract, output-integrity, provenance, claim schemas | S | parked: publish decision |
| **M9-T07** | Migration policy | S | merged → `M0-T07` |
| **M9-T08** | `CITATION.cff` | S | parked: publish decision |
| **M9-T09** | `CONTRIBUTING.md` | S | parked: publish decision |
| **M9-T10** | Support and compatibility policy | S | parked: publish decision |
| **M9-T11**, **T12** | Release integrity; archive / DOI | S | parked: publish decision |

---

# Track R — Research track (optional)

The question "does Extra reduce critical scientific-analysis errors compared with no Extra" is a research study, not a
package feature. It is outside the package's own claim and is **not** on the critical path. Start it only if the user
decides to run it. Plan when started: pre-register the analysis; four conditions (A model alone, B plain repository,
C Mycelium, D Mycelium + Extra); scripted-user harness with pinned model and plugin versions; blind double grading;
a sealed held-out set; externally authored scenarios; a cost cap the user sets. Extra without Mycelium is a supported
configuration (`docs/mycelium-integration.md:5-7`), so an "Extra only" condition is possible if wanted.

IDs held here: `M2-T03`, `M2-T08`–`T11`, `M2-T13`–`T17`, `M4-T02`–`T12`, `M8-T07`, `M8-T08`.

---

# Immediate execution queue

Four lanes; take the first open item of whichever is free.

**Lane P — privacy and quick wins**

| Order | ID | Task | Effort |
|---:|---|---|---|
| 1 | M7-T01–T04 | Plan-review packet: audit, scan, preview, confirmation | M+M+S+S |
| 2 | M3-T11, T12 | Identifier checks, fix DC-10 | M+S |
| 3 | M0-T01–T04, T07–T09 | Wording, threat model, host table, handoff, schema convention, version check, consume list | 7×S |

**Lane I — integrity (consume Mycelium first)**

| Order | ID | Task | Effort |
|---:|---|---|---|
| 1 | M1-T18 | Spike: host payload fields; Mycelium lineage mapping | S |
| 2 | M1-T01–T04 | Run IDs | S+M+M+S |
| 3 | M1-T05, T06, T08, T09 | Lineage, fix V-20 | S+M+S+M |
| 4 | M1-T10–T13 | Output integrity, fix V-02b | S+M+M+S |
| 5 | M1-T14–T17 | Modes, reportable requirements, C2 | S+M+M+M |

**Lane E — evaluation of Extra's own claims**

| Order | ID | Task | Effort |
|---:|---|---|---|
| 1 | M2-T01, T02, T04, T05 | Directory, schema, taxonomy, burden | 4×S |
| 2 | M2-T06, T07 | Five scenarios, colleague review | M+M |
| 3 | M2-T18, M2-T12 | Grill-coverage baseline, failure analysis | M+M |
| 4 | M3 | Plan block, DC-09, DC-08 (T10, T17), DC-11 | by task |
| 5 | M4-T01, T13–T15 | Frozen release, re-run, note | S+M+S+S |

Rule between 3 and 4: if the baseline shows grill missing ≥2 required choices in a scenario, fix grill first.

**Lane U — lab adoption (background)**

| Order | ID | Task | Effort |
|---:|---|---|---|
| 1 | M7-T15 | Worked example | M |
| 2 | M8-T09 | Observe 2–3 colleagues | M |
| 3 | M8-T03 → M2-T19 | Run on ≥3 sibling repos, add defect cases | M+M |

Later, from observed failures: M6-T03, T05, T08–T11; M7-T10, T14, T16.

---

# Future numbering rule

- New task in an existing milestone: the next unused `M#-T##`.
- Never renumber. A task that moves keeps its ID and gains `merged → X`, `parked` or `dropped`.
- A new defect keeps the defect-catalog convention and links to a remediation task.
- No ad hoc milestones.
