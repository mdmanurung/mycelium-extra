# Scientific convention retrieval during `grill`

This is **part of existing read-only grill**, not a separate skill, permission, validator, or approval mechanism. Consult it after the user's question/claim has been stated and project evidence has been retrieved. A convention gives conditional scientific guidance; it does not demonstrate that data, code, or results satisfy it.

## 1. Detect activation before reading scientific details

1. In a Mycelium repository (identified by `.living/`), consult `.living/conventions.md` (local overrides), `.living/conventions/ACTIVE_CONVENTIONS.yaml` (registration), and the `analysis-conventions.md` hub of relevant **active** packs.
2. Interpret an active entry's `path` relative to the repository root, confirm it is inside `.living/conventions/`, and that the directory and hub exist. A network catalog, an installed Python/R package, an unregistered folder, or a draft in `.living/generated-conventions/` does **not** activate the pack.
3. For a non-Mycelium repository use only scientific guidance in its existing instruction files and available project evidence. Do not imply that a Mycelium pack is installed.
4. Apply precedence local `.living/conventions.md` > task-applicable active domain pack > core. When two domain packs conflict, do not silently choose one: compare relevance, explicitly recorded overrides, version and cited support; surface unresolved scientific differences.
5. A repository may contain an older pack. Cite the **installed** guide and version, never assume the version of a public upstream catalog.

## 2. Task-to-guide routing: read selectively

First classify the scientific **question**, independent experimental unit, data type, design, and claim (descriptive, association, prediction, causal/mechanistic). Then read the single-cell hub and up to **three** relevant specialized guides below. Read additional guides only when a consequential decision genuinely depends on them; do not load the entire pack by default.

| Scientific task | Specialized guides in active `single-cell-analysis` |
| --- | --- |
| Experimental design, pairing, dataset / counts layer | `design-and-data-contract.md`; `replicate-aware-inference.md` |
| Cell QC and exclusions | `automatic-qc-scautoqc.md`; `preprocessing-and-annotation.md` |
| Donor-level differential expression / repeated measures | `replicate-aware-inference.md`; `variance-dreamlet.md` |
| Cell-type proportions / differential abundance | `composition-crumblr.md`; `replicate-aware-inference.md` |
| Batch correction and integration | `integration-and-annotation.md`; `integration-scib.md` |
| Perturbations and responses | `perturbation-conventions.md`; `design-and-data-contract.md` |
| TF or pathway activity | `pathway-decoupler.md`; `replicate-aware-inference.md` |
| Cell–cell communication | `communication-liana.md`; `design-and-data-contract.md` |
| Multicellular factorization | `multicellular-mofacellular.md`; `design-and-data-contract.md` |
| GPU acceleration / R–Python exchange | `gpu-and-interoperability.md`; `reproducibility-and-parity.md` |
| Existing approved method / proposed method change | `stability-and-method-policy.md`; `method-policy.json` |

Treat package names (dreamlet, crumblr, LIANA+, scIB, decoupler, MOFAcellulaR, anndataR, RAPIDS) as **candidates or resources**, not a reason to run a method. Prefer the estimand, design, required input and disqualifiers over software popularity. If a listed guide is missing in an older installed pack, report the gap and use the relevant available evidence; do not fabricate its text.

## 3. Scientifically challenge the plan

For each **applicable consequential rule**, distinguish:

- **Rule and authority:** `repo: .living/conventions/.../file.md` plus a section/heading, with any overriding `.living/conventions.md` entry; otherwise `default: <reason>`, user choice, or an independently verified external source. An external article is never itself `repo` evidence.
- **Evidence of applicability:** sample metadata, counts layer, number of independent donors/samples, time points, donor nesting, batch/condition cross-tab, labels, controls, assay or network versions. State `unverified` until a read-only check establishes it.
- **Choice and serious alternative:** what method is appropriate *if* the assumptions hold; what would change the choice. Do not make the method decision from a keyword match.
- **Failure / stop condition:** e.g. complete condition/batch aliasing, donor pseudoreplication, uncertain assay state, inadequate controls, unidentifiable contrast, severe integration-driven biology loss.
- **Discriminating validation:** an actionable test or inspection with observable outcome and sample-level unit, included in the plan table as a future step rather than falsely labelled executed.

For existing approved work, inspect applicable approved Plan A / Plan B, actual project decisions, and any `scientific-contract.json` / `method-lock.json`. Their presence is not approval: check links to accepted intent and continued applicability before recommending reuse. Reuse an applicable approved scientific choice; propose an **amendment and renewed approval** for a consequential methodological change. A pack update by itself never changes an approved estimand or method. Do not create or update any files during grill.

## 4. Output without changing grill's contract

- Incorporate relevant scientific choices into the **existing** Plan rows, their `Source` (`repo` / `user` / `default`) and falsifiable `Validation` cells. If a crucial property is unknown, make its check the first step or mark `DECISION_REQUIRED` when the user owns the unresolved choice.
- Preserve the user's-own-words opening, read-only probes, maximum five consequential questions, concise brief, three existing `Plan status:` outcomes, and waiting for user approval.
- Never assume the existing approval gate enforces scientific validity. Planned validation checks are **not implemented guards** until executable tests are separately shipped, invoked, and their evidence verified.
- Do not execute notebooks/pipelines, write `.living/`, install packages, send project data to external services, or independently launch an external research request. The existing `evidence-assistance.md` consent rules apply unchanged.

## 5. Two adversarial exemplars

**Expression:** "Treatment increases IFN-response genes in stimulated PBMCs." Check donor pairing, raw counts, independent biological replicates, design matrix rank, and treatment/batch aliasing **before** proposing donor-aware pseudobulk/dreamlet. A per-cell test without donor-aware inference must not be presented as donor-level proof. A failed design check means descriptive claims or a redesigned experiment, not silent model substitution.

**Composition:** "Myeloid cells increase after vaccination." Check per-donor numerator, denominator and cell-type annotation stability. Route to sample-level composition, with crumblr as a candidate when assumptions/data support it. dreamlet gene DE and cell-type counts answer different estimands. Report uncertainty and an appropriate low-count/denominator sensitivity check.

## 6. Methods with no active pack (plugin reference, lower priority)

After the repository's own conventions, and only when the question is a longitudinal or repeated-measures analysis, or a Bayesian model, and no active pack covers it, read at most one short guide: [methods/longitudinal.md](methods/longitudinal.md) or [methods/bayesian.md](methods/bayesian.md). Cite it as `plugin reference: methods/<name>.md`, never as `repo:`. It does not activate a pack, replace the `single-cell-analysis` guides above, add a question, or show that any check ran. Where it and an active pack differ, follow the pack and say what differs.

For single-cell work with no active pack, [methods/single-cell.md](methods/single-cell.md) points back to the activation and routing rules above. It adds no method policy; an active pack remains the source for its scientific guidance.

