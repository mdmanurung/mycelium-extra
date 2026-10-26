# Manuscript reproducibility conventions — core routing

**Authority:** Opt-in repository convention after installation in `.living/conventions/` and registration in `.living/conventions/ACTIVE_CONVENTIONS.yaml`. These guidelines are not evidence that any check ran. Repository-local `.living/conventions.md` overrides task-applicable domain packs, per Mycelium Extra's existing routing. The pack is **not** a method selector or security boundary. Scientific design remains the researcher's responsibility.

## Minimum reader-facing requirements (all manuscript types)

1. **Traceable questions/figures.** README provides a figure + table → producing script → source-data path map. Explicitly identify panels not reproducible from public inputs and why.
2. **Readable science.** Keep biological design, model formula, unit of inference, estimand, exclusions, reference/annotation versions, contrasts and multiple-testing family visible in the analysis source or approved plan; use a notebook/Rmd if it improves clarity.
3. **Distinct data products.** Label pseudobulk *raw summed counts*, normalized/log-scale expression, cell composition with denominator/zero policy, inferred factor scores, estimated coefficients and plotted source data. Never silently substitute scales. See `scientific-data-products.md`.
4. **Figure source data.** Publish all actual aesthetics (axes, colors, sizes, facet/category labels, uncertainty values, annotation panel values), plus units, source path and rendering command. See `figures-and-source-data.md`.
5. **Small reproducible entry points.** Figure rendering should not refit computationally expensive models if stable intermediate results suffice. Record environment versions and data locations; private inputs may be access-controlled, but unavailability must be explicit.
6. **Check honestly.** Cite exact executed red/green validation results. A lint/check pass proves only the specific declared invariant; neither model appropriateness nor biological validity follows from it. No 'pass' for missing evidence.

## One of three source-derived working styles

- **Small R methods manuscript:** `run_analysis.R` (or equivalent) + Rmd reports + `pub_figures.Rmd` + `renv.lock`. Model on GTestimate-Paper; avoid mandatory workflow engines.
- **Multicohort R/Python paper:** stage-grouped analyses by scientific question/modality + small R/Python reusable functions + figure-specific scripts and source tables, indexed by README. Exemplars: dreamlet, ALTRA, AIFI multiple-myeloma, ImmGen-T, single_cell_aging.
- **Large atlas:** numbered acquisition/QC/integration/annotation/reference-mapping stages, resource-aware CLI/HPC processing, measured batch integration quality, versioned expert labeling, and publication figure layer. Exemplars: Haniffa CNS, AIFI healthy PBMC and Sound Life.

## How to adopt with Mycelium Extra

During `grill`, retrieve only task-applicable parts of this pack and the active single-cell science pack. Identify design versus publication-code questions separately. In `new-analysis`, use existing steps and optional manuscript profile: do not force publication bookkeeping into early exploration. At publication freeze, let an approved check run and bind its observed output with existing `validation-bindings` before `verify`. For recurring mistakes, use `harden` to prove a regression test fails on the bad fixture and passes on the corrected case. Do not modify hook dispatch or create a second approval step.

## Guidance depth and enforcement

**Exploration:** explain and suggest, do not block for missing paper deliverables.

**Analysis finalisation:** request explicit decisions for unknown biological units, contrast sign, composition denominator and source-data scope; fail known numeric/identity inconsistencies.

**Publication freeze:** run reviewer-approved validators/CI for objective claims (files, identities, scales and exports). Missing evidence is a gap, not a success; exceptions should be documented rather than fabricated.

**Not covered:** statistical power, model appropriateness, annotation biology, corrected false-discovery rate, producer authenticity, or final biological interpretation.
