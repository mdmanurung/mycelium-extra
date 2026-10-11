# Mycelium Extra — Parked Work and Non-Goals

This file exists to prevent roadmap drift.

Items here should not re-enter active development without new evidence or a concrete use case.

---

# Parked existing roadmap work

## D10 — Approval latency / comprehension checks

**Status:** parked.

Reason:

- measures proxies for attention rather than scientific correctness;
- lower priority than known scientific and provenance failures;
- revisit only if external-user studies show habitual meaningless approval.

## D11 — Approval reuse limits

**Status:** parked.

Reason:

- input/code fingerprints already catch much of the meaningful drift;
- no demonstrated high-frequency failure requiring this mechanism.

## D12 — Seeded fake discrepancies / vigilance dashboard

**Status:** parked indefinitely.

Reason:

- deliberately injecting incorrect oversight output may undermine trust;
- benefit remains speculative;
- should not be built without strong human-factors evidence.

## Vigilance dashboards

**Status:** parked.

Reason:

- no demonstrated need;
- high risk of governance theatre.

---

## Parked because the need is not shown (each keeps its ID)

| ID | Item | Why parked | Reactivate when |
|---|---|---|---|
| `M1-T07` | Workflow-native lineage | none of 9 sibling repos has a Snakefile (checked 2026-10-05) | a workflow-manager pipeline runs under verify |
| `M6-T01` | Snakemake per-rule environments (E1b) | same | same |
| `M6-T02` | Container image digests | no container use shown | a project runs analyses in a container |
| `M6-T04` | GPU / CUDA metadata | no GPU analysis shown | a reportable GPU run appears |
| `M6-T06`, `T07` | Remote-input and database provenance | no demonstrated failure | a reportable analysis reads a remote source |
| `M7-T06`, `T07` | Citation resolution (D2) | 0 of 10 sibling repos cite DOIs | a repository cites DOIs, or a fabricated reference is found |
| `M5-T05`–`T11`, `T16` | Seurat, SCE, VCF, BED/GTF, BAM/CRAM inspectors, reference schema, genomics fixture | no use shown; no inspector framework | a sibling-repo defect needs one; then add it as a check in `data-contract-check` |
| `M5-T12`–`T15`, `T17` | Extra fixture families | one fixture suffices for the execution chain | a sibling-repo defect (`M2-T19`) needs one |

## Parked: publish decision

`M9-T01`–`T06`, `T08`–`T12` (schema freezes, `CITATION.cff`, `CONTRIBUTING.md`, support policy, release integrity,
DOI) and `M6-T13` (RO-Crate). Reactivate when the user decides to publish Extra.

## Parked: research track (Track R in `03`)

`M2-T03`, `M2-T08`–`T11`, `M2-T13`–`T17`, `M4-T02`–`T12`, `M8-T07`, `M8-T08`: the multi-condition study of whether
Extra reduces critical scientific-analysis errors. Reactivate when the user decides to run that study. It is outside the
package's own claim and is not a gate for anything.

## Dropped

| ID | Item | Reason |
|---|---|---|
| `M5-T01`, `T02` | Inspector framework and interface | Data-state checks live in `data-contract-check`; no framework |
| `M6-T12` | Receipt hash chaining | The gate is not a security boundary; an unsigned chain written by the same process resists nothing it is meant to |
| `M6-T14`, `T15` | W3C PROV, BioCompute export | No requirement stated |
| `M7-T09` | Figure lineage | Mycelium's lineage already covers script outputs |
| `M7-T11`–`T13` | `PLAN`/`RUN`/`CHECK` routing skills | Mycelium already routes by intent; usage tiers are the simplification |

## Merged

`M0-T05` → `M7-T10`; `M3-T09` → `M3-T17`; `M5-T03`, `T04` → `M3-T13`, `T14`; `M9-T07` → `M0-T07`.

---

# Explicit non-goals

## Rebuilding what Mycelium does

Memory (decisions, learnings, findings), run lineage, report-value checking, review tripwires and ingest provenance
belong to Mycelium. Extra reads them and adds the link to the plan and approval. Extra's own mechanism is a fallback
for plain repositories and for what Mycelium does not track (`sbatch`, workflow managers).

## Verifying scientific correctness

Extra checks that approved plans ran and the record is honest. Correctness remains Mycelium's `review` and the
researcher. Interpretive claims stay `HUMAN_REVIEW_REQUIRED`.

## Routing skills that shadow Mycelium's

No `PLAN`/`RUN`/`CHECK` skills. Simplify wording and tiers instead.

## A public v1 before a publish decision

Extra stays 0.x; one researcher and their own lab repositories are the audience.

## Universal analysis DSL

The plan's Choice block covers a few high-value choices only.

## Hard security sandbox

Extra is a cooperative execution-control and provenance layer (`docs/approval-gate.md:102`). Isolation belongs to
dedicated sandbox or container systems.

## Support for every biological file format

Add a format when a sibling-repo defect needs it.

## More reviewer LLMs by default

Model plurality is not independent scientific reasoning. Measure plan-review's value (Track R) before adding reviewers.

## Replacing internal provenance with an external standard

Exporters only, and only after a publish decision.

---

# Decision rule for reactivating parked work

A parked item returns only if one of these is true:

1. the user's own repositories or lab colleagues show the problem repeatedly (`M8`);
2. a sibling-repo defect or grill-coverage failure shows it (`M2-T18`, `M2-T19`);
3. a real deployment requirement demands it, or the user decides to publish or to run Track R;
4. a serious reproducible failure cannot be addressed by a simpler existing mechanism, including Mycelium's.

Do not reactivate items because they are interesting or theoretically elegant.

---

# Development filter (the scope filter, `G13`)

Before adding any new feature, ask:

1. Is it plan, approve, or check-the-execution-record work (or scaffolding)? If not, it belongs to Mycelium or Track R.
2. Does Mycelium already do it? Then consume Mycelium's record and build only the link.
3. Does it still work in a plain repository, as a fallback with weaker evidence or a gap?
4. What observed failure in the user's repositories or the fixture does it address, and can success be tested?
5. Does it reduce or increase user cognitive load?

Core project claim:

> Extra surfaces the consequential choices before code runs, lets only approved plans run, and reports honestly what ran
> against the plan, at low friction.

If a feature does not support that claim, strengthen the provenance behind it, or reduce workflow burden, defer it.
