# Mycelium Extra — Milestone Gates and Dependency Model (scope-aligned)

Target: one researcher and their own lab repositories. Extra stays 0.x. The multi-condition research study is Track R
(`03`), outside these gates.

## Milestones

```text
M0 Foundation                         M5 Data-state checks (merged into M3; rest parked)
M1 Execution Integrity                M6 Reproducibility and Provenance
M2 Evaluate Extra's Own Claims        M7 Privacy, Disclosure, Wording
M3 Scientific Semantics               M8 Lab Validation
M4 Fixture Evaluation, frozen release M9 Release (parked: publish decision)
```

# Dependency rules

- **D1 — Consume Mycelium first.** Any task that records lineage, report values, tripwire results or ingest
  provenance reads Mycelium's record first and builds only the link to the plan and approval (`G13`).
- **D2 — Evaluation starts now.** `M2` needs nothing else; it runs on the current release.
- **D3 — Contract design is failure-driven.** `M3` follows `M2-T12` and the defect catalog, never a speculative
  ontology. Scenarios used to design `M3` are not used to judge it.
- **D4 — Output integrity and the plan's Choice block are separate.** Artifact completeness is `M1`; intent is `M3`.
- **D5 — M1 runs beside the evaluation, not before it.** Run IDs and lineage change what the record says, not what
  grill asks.
- **D6 — No routing skills.** Mycelium routes by intent; wording and tiers are the simplification.
- **D7 — Release follows a publish decision.** `M9` and RO-Crate wait for the user.
- **D8 — Anti-gaming is outside the critical path** (D10–D12 stay parked).

# Gates

## M0-GATE — Foundation

- verification wording separates conformance from scientific correctness;
- one-page threat model; host-capability table;
- the HANDOFF decision (B5) is made and the file is current;
- schema-version convention exists; Mycelium version check exists;
- `docs/mycelium-integration.md` lists what Extra consumes and what it never rebuilds.

Branch protection (`M0-T06`) is a maintainer action and not a closure condition.

## M1-GATE — Core Trust

- new covered runs carry a `run_id`, joined to Mycelium's lineage event when one exists;
- `V-20` cannot produce wrong confident lineage for foreground runs; background and `sbatch` outputs are
  `unresolved`, and absent Mycelium lineage is a gap;
- declared output integrity is checked; `V-02b` is caught where expectations are declared;
- reportable requirements are defined and checked; weak input identity is never treated as strong.

> Can we trust which run happened and which outputs belong to it?

## M2-GATE — Extra's Claims Are Measured

- plan-scenario schema, taxonomy and burden metrics exist;
- five scenarios exist, hidden lists reviewed by a lab colleague;
- the grill-coverage eval has run on the current release (`M2-T18`) and the failure analysis exists (`M2-T12`);
- sibling-repo defects are in the C1 catalog (`M2-T19`).

> Does grill surface the choices that matter, and where does it miss?

**Rule before M3 features:** if grill misses two or more required choices in a scenario, fix grill first. Thresholds
may be tightened in `M2-T04` before the first scored run, not after.

## M3-GATE — Scientific Semantics

- the plan's Choice block is small, freezes with the approved plan, and keeps unknowns unknown;
- `DC-09` fixed; `DC-10` caught; `DC-11` detectable at a basic level (AnnData `X`/layers where `h5py` exists, gap
  otherwise);
- `DC-08` caught where an output or claim declares a direction, and the direction tripwire spec exists with verify
  reporting whether it ran; otherwise unresolved and `HUMAN_REVIEW_REQUIRED`;
- design used only scenarios not later used for judging.

> Can the highest-value choices be stated in the plan and checked on the input side?

## M4-GATE — Frozen-Release Evaluation

Needs `M2-GATE` and `M3-GATE`.

- the release under test is frozen (plugin version, model IDs, scenario set);
- the grill-coverage eval is re-run before vs after M3 on scenarios M3 was not designed against;
- workflow burden is recorded; a short note says what improved and what grill still misses.

A mixed or negative result is valid and drives simplification.

## M5

No gate. Data-state checks were merged into `M3`; the rest is parked until a sibling repo cannot be served.

## M6-GATE — Reproducibility

A reportable run preserves, where applicable: plan and Choice block, code, inputs checked against Mycelium's ingest
checksums, environment (conda, pip, R), execution identity, outputs, claims and checks, with explicit gaps where full
reconstruction is unavailable. HPC runs reconcile submission and in-job receipts.

> Can the run be reconstructed?

## M7-GATE — Safe Use

- plan-review sends only a scanned, previewed, confirmed packet;
- the worked example exists; `doctor` diagnoses host and setup problems;
- wording is simpler without routing skills; `disclose` drafts only from records, with blanks for gaps.

## M8-GATE — Lab Validation

- gate and verify have run on at least three sibling repositories, and every failure is a defect case;
- at least two lab colleagues have used it, with observed confusion and friction recorded and addressed.

## M9 — Release

Parked until the user decides to publish. If published, add the schema freeze, citation file, support policy and
release integrity at that point.

# Critical path

```text
M2 (scenarios, grill-coverage baseline, failure analysis) ──► M2-GATE
                                                                │
                              M1 runs beside it                 ▼
                                                        M3 ──► M3-GATE ──► M4-GATE
M7 privacy (Lane P) first, in parallel                          │
                                                                ▼
                                         M6 (HPC wrapper first), M8 lab validation, M7 usability
```

# Parallel lanes

```text
Lane P  M7-T01..T04 → M3-T11/T12 → M0 consolidation
Lane I  M1-T18 → run IDs → lineage (V-20) → output integrity (V-02b) → reportable → M6-T08..T10
Lane E  M2 scenarios → grill-coverage baseline → M3 → M4
Lane U  M7-T15 → M8-T09 → M8-T03 → M2-T19
```

One maintainer: take the first open item of whichever lane is free.
