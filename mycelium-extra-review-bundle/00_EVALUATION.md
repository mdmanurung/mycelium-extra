# Evaluation of the review bundle and what was revised (2026-10-06, two passes)

Pass 1 made the plan executable (findings 1–16 below). Pass 2 (section "Second pass") aligned it with the aims of
Mycelium and Mycelium Extra. Where they differ, pass 2 wins.

Method: read all seven files; checked the claims against the repository at `72119ef` (v0.9.43) and the staging
folder `mycelium-extra-improvements/`; revised `03`–`06`, `02` and the README. `01_ASSESSMENT.md` is kept unchanged.
The original bundle is backed up outside the repository. `docs/roadmap/` and git were not touched.

## Verdict

The diagnosis is right and stays. The plan as written was not executable by one maintainer and had seven defects.

**What stays:** the central question (does Extra reduce critical analysis errors, at what cost); the six known
misses as regression targets (`V-20`, `V-02b`, `DC-08`–`DC-11` all exist in `tests/e2e/defects.py` as
`known_miss=True`); "a gap never becomes a pass"; a small scientific contract instead of a DSL; fixing the
`V-20` attribution invariant; parking D10–D12; no hard-security claims; export-not-replace for provenance;
external users before schema freeze.

**Size after pass 2:** about 51 person-days of active work (about 2.5 months full-time) plus about 3.5 days parked
for a publish decision. The optional research track is about 70 days and is outside the plan. After pass 1 it was
~100 active days.

## Findings and changes

| # | Finding | Change |
|---|---|---|
| 1 | **Open roadmap items missing.** C2, A5, A6, D3, B5, A1/A3/A4 were not mapped; D3 was filed under "defer large disclosure machinery" although it reads existing records only. | Crosswalk below. C2 merged into `M1-T17`; A5 = `M0-T08`; A6 = `M7-T15`; D3 = `M7-T16`; B5 merged into `M0-T04`; maintainer actions listed. |
| 2 | *(partly superseded by pass 2: the pilot is now the grill-coverage eval)* **Contradicted its own filter.** G1 says evidence before breadth, yet `M4` waited for `M1-GATE`, and the first real evidence of effect was months away. Run IDs and lineage do not change the plan quality the benchmark scores. | Added a **pilot**: conditions A–D on the *current* version (`M2-T17`) with a pre-registered go/no-go (`M2-GATE`). `M4` now needs `M2-GATE` + `M3-GATE` only; M1 features are recorded in the frozen configuration. |
| 3 | *(moved to Track R by pass 2)* **Benchmark under-specified.** Grill is interactive and approval needs a human, so a harness needs a scripted user, headless runs, pinned model and plugin versions, and a cost cap. No pre-registration, grading protocol, repeat counts or blinding. | `M2-T13` (harness), `M2-T14` (pre-registration), `M2-T15` (blind grading, ≥20% double-graded), repeat counts fixed. |
| 4 | *(kept in reduced form: design and judging scenarios stay separate)* **Circular benchmark.** Three of the first five scenarios are the known misses that `M3` then fixes; external authorship came only at `M8`. | `M2-T16` seals a held-out third and gets ≥2 externally authored scenarios early; M3 designs against the rest. |
| 5 | ~~**Five conditions, one impossible.**~~ **Withdrawn in pass 2.** The claim that "Extra alone" is unsupported was wrong: `docs/mycelium-integration.md:5-7` says Extra works in an ordinary repository. | The conditions move to Track R, where an Extra-only condition is allowed. |
| 6 | **Tasks already partly built, described as new.** `plan-review` already shows the packet and sends after agreement (`SKILL.md:25`); the threat-model wording exists at `docs/approval-gate.md:103,109`; the three states of the proposed explore/standard/reportable scheme already exist as usage tiers; `data-contract-check` already has the table checks proposed for output integrity. | `M0-T01/T02/T03` become consolidation (S each); `M1-T14` maps onto existing tiers (no fourth concept, G8); output integrity extends `data-contract-check`; `M7-T03/T04` become "make it deterministic and enforced". |
| 7 | **Binding principles absent.** Python 3.6 stdlib only; opt-in friction; complement Mycelium; no SessionStart messages; plain-text notices; two-commit rule; `gate_diff` before and after gate changes. `M5-T05/T06` need R, `M5-T03` needs `h5py`. | Added `G11` and a constraints block in `03`; optional readers report a **gap** when absent. |
| 8 | **Wrong priority for privacy.** `plan-review` sends data to OpenAI and Phylo today. HANDOFF ranks C3 first by impact; the bundle put it in M7 and only said it "can be pulled earlier". | `M7-T01`–`T04` have no dependencies and head Lane P of the queue. |
| 9 | **Run ID design skipped a precondition.** `hooks/gate.py` uses no tool-call ID today; whether each host's `PreToolUse` and `PostToolUse` payloads share one is unknown. Background and `sbatch` runs finish after `PostToolUse`, so foreground lineage cannot fix them. | `M1-T18` spike first; `M1-T09` scoped to foreground runs, background and HPC outputs stay `unresolved` until `M6-T08`–`T10`. |
| 10 | **`DC-08` cannot be fixed as framed.** Detecting a reversed contrast in arbitrary code is not mechanical. | Narrowed to: contract declares `positive_means`; declared-direction claims are checked against data; everything else is `HUMAN_REVIEW_REQUIRED`. A spike (`M3-T09`) decides whether a synthetic sign test is feasible. `M9-GATE` wording changed from "materially controlled" accordingly. |
| 11 | **Work with no demonstrated demand** broke the bundle's own reactivation rule: Snakemake envs (no Snakefile in any of 9 sibling repos), citation resolution (0 of 10 cite DOIs), containers, GPU, remote inputs, VCF/BED/BAM inspectors, Seurat/SCE by default, workflow-native lineage. | Parked with the evidence that would reactivate them (`05`). |
| 12 | **Internally inconsistent items.** Receipt hash chaining (`M6-T12`) contradicts "not a security boundary"; PROV and BioCompute "evaluate" tasks are decisions with no trigger; `M0-T05` adds a check on a file whose fix is derived state (G7). | `M6-T12`, `T14`, `T15` dropped; `M0-T05` merged into `doctor` (`M7-T10`). |
| 13 | **UX built before users; routing can shadow Mycelium.** | Pass 2: routing skills (`M7-T11`–`T13`) dropped; `M8-T09` observes lab colleagues first. |
| 14 | **Branch protection gated everything.** `M0-T06` needs a push; the repository stays local until the user asks. It sat inside `M0-GATE`, which gated `M2`. | `M0-T06` is `maintainer`, outside `M0-GATE`; `M2` has no gate dependency. |
| 15 | **Ablations.** Seven ablations × 15 scenarios × 5 repeats before knowing there is an effect. | Run only if `M4-T13` finds one; ordered; one dropped as already covered by condition B vs C. |
| 16 | **No effort or cost.** The roadmap template requires S/M/L. | Added to every task; totals above. |

## Crosswalk: every open item in the repository's roadmap

| Roadmap item | Disposition |
|---|---|
| A1 license | `maintainer` (confirm MIT; name settled) |
| A2 CI | done (green run 37356671605 per HANDOFF); not in the bundle |
| A3 tags | `maintainer` (commands in `mycelium-extra-improvements/notes/docs.md:24`) |
| A4 description, topics | `maintainer` (command in `APPLY.md:79`) |
| A5 Mycelium version check | `M0-T08` |
| A6 worked example | `M7-T15` |
| B5 HANDOFF decision | merged into `M0-T04` |
| C2 fail-closed gate | merged into `M1-T17` |
| C3 redaction audit | `M7-T01`–`T05` (moved first) |
| D2 citations | `M7-T06`, `T07`: parked |
| D3 disclose | `M7-T16` |
| D10, D11, D12 | parked (`05`); in `docs/roadmap/06-anti-gaming.md` mark `parked: <reason>` when adopted |
| E1b Snakemake rule envs | `M6-T01`: parked |
| Staging `IMPLEMENTATION-MAP.md` | superseded; its open items are the rows above; its "decide missing exit status" and "land the series" items are already done (HANDOFF locked decisions) |
| Staging `notes/*` open questions | `backgroundTaskId` and failure-event hint noise → folded into `M1-T18` |

Roadmap items already done (C1, D1, D4–D9, E1–E8, B1–B4, T0) have no bundle task. The bundle's `M1`–`M3` tasks build
*on* them (for example `M1-T10` extends `data-contract-check`; `M7-T08` extends D1's claims block).

## Second pass: scope alignment

Pass 1 still treated Extra as a research methodology. Checked against the two projects' stated aims, it overreached.

**Mycelium** (v0.7.2, `README.md`): "gives every analytical project a memory": decisions, findings, run lineage with
SHA-256 (`.living/log/data-lineage/<session>.json`), report values (`register_value` → `numbers.json` → scitexlintr),
review tripwires (known-answer, metamorphic), ingest provenance, and routing by intent.
**Extra** (`README.md:3`, `docs/mycelium-integration.md`): "Plan an analysis. Approve what runs. Check the execution
record." It adds only what Mycelium lacks, and is "not a judgment of scientific validity" (`docs/approval-gate.md:102`).

Pass 1 planned to rebuild lineage, claim classes, a sign test and routing inside Extra, plus a public-release
programme and an error-reduction benchmark outside Extra's claim.

User decisions (2026-10-06): (1) shrink the benchmark to Extra's own claims; the error-reduction study is optional
research. (2) Consume Mycelium's mechanisms when present; Extra's own is a fallback, reported as weaker evidence.
(3) Target a single researcher and their own lab repositories; no public release until chosen.

Filter applied to every task (`G13`): plan/approve/check work? Does Mycelium already do it (consume its record)? Works
in a plain repository as a fallback? Need shown in the user's repositories or the fixture?

| Area | Pass 1 | Pass 2 |
|---|---|---|
| Core question | does Extra reduce scientific errors | does Extra surface the choices, run only approved plans, report honestly (low friction) |
| Evaluation | 4 conditions, ≥15 scenarios, ablations, external authors | grill-coverage eval on 5 plan scenarios + the existing fixture chain; study moved to Track R |
| Lineage / `V-20` | Extra's own fingerprints | Mycelium's data-lineage first; Extra's own for `sbatch`, workflow managers, plain repos |
| Report numbers / claims | claim classes in Extra | Mycelium's `register_value` pipeline; Extra adds a `direction` kind |
| `DC-08` sign test | synthetic sign test | direction tripwire spec in the plan, run by Mycelium's `review` |
| Contract | separate schema layer | Choice block inside grill's plan |
| Inspectors (M5) | framework + 6 adapters | checks inside `data-contract-check`; rest parked |
| Reference checksums | Extra records them | verify compares pinned inputs with Mycelium's ingest checksums |
| Figure lineage, routing skills | planned | dropped (Mycelium covers / routes) |
| M8 users | external recruitment | lab colleagues and ≥3 sibling repos |
| M9 release | schema freeze, DOI, policy | parked until a publish decision |

New tasks: `M0-T09` (consume list in `docs/mycelium-integration.md`), `M2-T18` (grill-coverage eval), `M2-T19` (sibling
defects into the C1 catalog), `M3-T17` (direction tripwire spec). `M1-T18` now also maps Mycelium's lineage fields.

Limits of what is consumed (stated in `02`, `G13`): Mycelium's lineage covers python, R and jupyter only, and is written
when the session stops, so verify inside the same session may find it absent; absent is a gap.

## Decision still open

**Review record** (`M7-T05`): `plan-review` writes no durable record of what it sent. Recording it changes a
first-version decision. Left `cond: user decision`.

Resolved by pass 2: numbering (the bundle's `M#-T##` IDs stay a layer over the roadmap, with the crosswalk above),
routing skills (dropped), benchmark budget (the study is Track R, so no cap is needed now).
