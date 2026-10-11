> **Superseded in part.** Sections 3 and 27 treat an LLM error-reduction benchmark as the project's main experiment.
> After the scope-alignment pass (`00_EVALUATION.md`) that study is optional research (Track R in `03`); the package's own
> claim is evaluated by the grill-coverage eval and the execution-chain fixture. The rest of this assessment stands.

# Mycelium Extra — Comprehensive Assessment

## Executive assessment

Mycelium Extra is already substantially more than a collection of prompts or convenience functions. It is an experimental **oversight and provenance layer for LLM-assisted computational research**, particularly bioinformatics.

Its strongest contribution is the workflow:

```text
research question
    ↓
repository-informed plan
    ↓
explicit analytical decisions
    ↓
human approval
    ↓
cooperative execution controls
    ↓
execution receipts
    ↓
verification
    ↓
provenance
```

The project is unusually disciplined about limitations. It distinguishes gaps from successful checks, separates exploratory work from reportable analyses, keeps known misses executable in tests, and generally avoids claiming that execution verification proves scientific correctness.

The current positioning is appropriately restrained:

> **Plan an analysis. Approve what runs. Check the execution record.**

The central unresolved problem is therefore not that Mycelium Extra fails to prove scientific truth. The central problem is:

> **The project has accumulated substantially more evidence that its oversight machinery behaves as designed than evidence that the machinery actually makes LLM-assisted scientific analysis better.**

That should now dominate development.

A defensible current characterization is:

> **Mycelium Extra is a sophisticated experimental oversight, planning, and provenance framework for cooperative LLM-assisted computational research. Its procedural safeguards are increasingly strong, but its effect on the scientific reliability of LLM-generated analyses has not yet been empirically demonstrated.**

---

# 1. Current strengths

## 1.1 Repository-grounded planning

`grill` is one of the package's strongest components. It:

- asks for the scientific question first;
- retrieves previous project decisions and findings;
- distinguishes evidence from assumptions;
- makes consequential analytical choices explicit;
- asks only consequential questions;
- records the source of decisions;
- prepares a plan before execution.

This directly targets a common LLM failure mode: moving too quickly from a vague request to executable code.

## 1.2 Analysis-decision checklist

The planning framework explicitly covers high-value scientific choices including:

- estimand;
- unit of replication;
- pairing;
- exclusions;
- matrix/data state;
- identifiers and reference build;
- QC;
- normalization;
- batch versus biology;
- annotation;
- model;
- covariates;
- multiplicity;
- leakage;
- validation;
- outputs.

This is already a useful scientific-planning ontology.

## 1.3 Explicit LLM failure catalogue

The repository explicitly tracks failure classes and whether each has:

- an implemented guard;
- a partial guard;
- a planned guard;
- no guard.

That is preferable to implicit claims of broad protection.

## 1.4 Data contracts

`data-contract-check` already provides useful checks for:

- expected columns;
- required levels;
- row counts;
- missing values;
- uniqueness of biological units;
- repeated-measure completeness;
- batch/condition confounding;
- graded imbalance;
- H5AD `obs`.

The rule that a **gap never becomes a pass** should be preserved.

## 1.5 Explicit approval

The plan-hash approval mechanism creates a real distinction between:

> the agent proposed this

and:

> the researcher approved this exact plan.

That is valuable.

## 1.6 Input pinning

The gate detects changes to approved inputs. This addresses silent input drift, a common reproducibility problem.

## 1.7 Explore versus reportable work

Exploratory work is recorded as non-reportable and cannot simply be promoted to a final result. Promotion requires a re-run under an approved plan.

This is a useful lightweight defense against analytical forking and selective promotion.

## 1.8 Execution receipts

Receipts capture substantial operational context, including combinations of:

- plan;
- host;
- command;
- script;
- hashes;
- git state;
- conda;
- pip;
- SLURM;
- workflow metadata;
- exit information where available.

## 1.9 Verification

`verify` checks much more than file existence. It includes coverage of:

- planned scripts versus receipts;
- input changes;
- code changes;
- output state;
- lint;
- explicit claims;
- provenance;
- stale analyses;
- multiplicity history;
- explore history.

## 1.10 Claims checking

Explicit claims blocks allow reported values to be linked to specific output cells. This directly addresses numerical transcription errors.

## 1.11 Multiplicity history

The package can expose repeated analyses, changed thresholds/models, and exploratory runs. This is particularly relevant in LLM-assisted work because analytical experimentation is very cheap.

## 1.12 Decision resolution

`decision-status` avoids the unsafe rule that the newest decision automatically supersedes all earlier decisions. Explicit supersession and scope matching are better.

## 1.13 Hardening recurring lessons

`harden` attempts to convert project-specific recurring mistakes into regression tests. The basic idea is strong: move from "remember this" to "test this".

## 1.14 Multi-host support

Claude Code and Codex support has become substantive, and host limitations are explicitly acknowledged rather than hidden.

## 1.15 Testing discipline

The repository has stronger testing than most research software projects:

- unit tests;
- end-to-end fixtures;
- planted defects;
- known misses;
- ablation tests;
- multiple Python versions;
- link checks;
- gate differential tests;
- live-host checks;
- docs CI.

The known-miss philosophy is particularly important.

---

# 2. Known misses that matter

The current adversarial suite includes cases where the overall system can still fail to identify a real problem.

Important examples:

| Defect | Failure |
|---|---|
| `DC-08` | reversed contrast |
| `DC-09` | sample/column misalignment |
| `DC-10` | corrupted gene identifiers |
| `DC-11` | inappropriate normalization/data-state mismatch |
| `V-02b` | partial output hidden behind successful shell status |
| `V-20` | output attributed to the wrong run |

These should remain executable regression targets.

The existence of known-miss tests is a strength.

The fact that some incorrect analyses can still receive a clean conformance result is a weakness.

Both statements are true.

---

# 3. Most important unresolved problem: no empirical LLM benchmark

The package's core scientific intervention occurs before execution:

```text
scientific question
      ↓
     LLM
      ↓
repository retrieval
      ↓
interpretation
      ↓
scientific reasoning
      ↓
questions
      ↓
analysis decisions
      ↓
plan
```

Current deterministic tests mostly validate later machinery:

```text
prepared plan
    ↓
approval parser
    ↓
gate
    ↓
execution
    ↓
receipt
    ↓
verify
```

This leaves the package's primary claim unevaluated.

The project needs a benchmark comparing conditions such as:

```text
model alone
model + repository
model + Mycelium
model + Mycelium Extra
model + Mycelium + Extra
```

across repeated runs and realistic scientific traps.

The benchmark should measure:

- critical scientific errors;
- major/minor errors;
- correct estimand;
- correct biological unit;
- correct contrast;
- correct matrix state;
- leakage;
- inappropriate normalization;
- sample mismatch;
- unsupported assumptions;
- hallucinated columns/files;
- necessary versus unnecessary questions;
- user interactions;
- token/tool burden.

This should become the project's main scientific experiment.

---

# 4. Scientific meaning remains mostly prose

The human-readable Markdown plan is a strength and should remain.

The problem is that high-value scientific intent is still often represented only as prose.

Examples:

```text
positive effect means day28 - baseline
```

may coexist with code computing:

```text
baseline - day28
```

Likewise:

- sample alignment;
- biological unit;
- matrix state;
- reference level;
- normalization expectations;

can be described correctly without being enforced.

The solution should **not** be a universal analysis DSL.

The preferred architecture is:

```text
human-readable scientific plan
            +
small machine-readable scientific contract
```

Initial contract scope should remain narrow:

- biological unit;
- pairing;
- contrast;
- sample key/alignment;
- matrix state;
- reference level;
- links to output integrity expectations.

Unknown fields must remain unknown rather than being invented to satisfy the schema.

---

# 5. Output lineage remains a core provenance weakness

`V-20` is especially important because it falls directly within the package's declared provenance role.

Temporal proximity or mtime-based attribution can assign an output to the wrong run.

The invariant should become:

> Mycelium Extra must never confidently attribute an output to the wrong run.

Allowed states:

```text
output generated by run X
```

or:

```text
lineage unresolved
```

Not allowed:

```text
wrong run inferred from timing → clean verification
```

Preferred mechanisms:

1. first-class run IDs;
2. workflow-native lineage;
3. before/after output fingerprints;
4. run-specific namespaces where practical;
5. timing only as an explicitly weak fallback.

---

# 6. Partial process success is not analytical completion

`V-02b` demonstrates that:

```bash
python script.py || true
```

can leave a partial output while the outer shell succeeds.

This requires a generic output-integrity mechanism separate from scientific contracts.

Example:

```yaml
path: outputs/de.tsv
required: true
checks:
  required_columns:
    - gene
    - log2fc
    - padj
  minimum_rows: 100
  unique:
    - gene
```

A zero process exit should not imply analytical completion when declared output integrity checks fail.

---

# 7. Reportable mode should be stronger than ordinary analysis

Introduce explicit execution modes:

```text
explore
standard
reportable
```

A reportable run should require stronger evidence, including:

- approved/frozen plan;
- run ID;
- strong input identity;
- frozen code identity;
- complete execution evidence;
- declared outputs;
- deterministic or explicitly unresolved lineage;
- environment evidence;
- verification.

Weak evidence must remain visible rather than silently downgraded.

---

# 8. The gate is not a security boundary

The gate is valuable as a cooperative execution-control layer.

It should not be described as hard isolation.

A formal threat model should explicitly distinguish protection against:

- accidental agent deviation;
- unapproved execution;
- input drift;
- stale code;
- unrecorded exploration;
- incomplete provenance;

from non-protection against:

- malicious bypass;
- user tampering;
- compromised host;
- root/admin modifications;
- unobserved MCP/GUI actions;
- manual execution outside the observed environment.

---

# 9. Bioinformatics object-state validation remains shallow

H5AD `obs` inspection is useful but insufficient for many common single-cell errors.

Important state surfaces include:

```text
X
layers
raw
var
assays
feature IDs
reference build
```

Common failures include:

- scaled data used for DE;
- integrated values used for DE;
- wrong layer;
- counts unavailable;
- duplicated identifiers;
- mixed identifier types;
- wrong assay;
- batch-corrected values used as inferential input.

A separate read-only `data-state-inspect` layer should answer:

> What object/representation actually exists, and does it match the approved plan?

Priority adapters:

1. AnnData;
2. Seurat;
3. SingleCellExperiment / SummarizedExperiment;
4. VCF;
5. BED/GTF/GFF;
6. BAM/CRAM headers.

The goal is not to become an analysis library.

---

# 10. Identifier integrity should become first-class

High-value checks include:

- duplicate sample IDs;
- duplicate feature IDs;
- empty IDs;
- Excel-like gene-symbol corruption;
- mixed identifier systems;
- versioned/unversioned Ensembl mixing;
- chromosome naming inconsistencies;
- species/build incompatibility.

These checks are relatively cheap and address common bioinformatics failure modes.

---

# 11. Claims verification is useful but necessarily incomplete

Current explicit numerical claims are valuable.

However, unmarked prose remains outside strong machine verification.

Future claim classes could include:

```text
quantitative
direction
count
presence/absence
interpretation
```

Interpretive claims should remain:

```text
HUMAN_REVIEW_REQUIRED
```

rather than being artificially promoted to "verified".

Figure provenance should initially focus on lineage:

```text
figure
→ generating script
→ run ID
→ source tables
```

not automated image interpretation.

---

# 12. Citation checking should verify existence, not scientific support

Future DOI/PMID/arXiv resolution can check:

- identifier resolves;
- title;
- first author;
- year.

But these must remain separate states:

```text
reference exists
```

versus:

```text
reference supports claim
```

The second requires scientific judgment.

---

# 13. Independent model review is not independent scientific validation

Multiple LLMs can share correlated failure modes.

`plan-review` may improve error detection, but model agreement must not be described as independent scientific validation without evidence.

The review mechanism itself should eventually be benchmarked:

- true positive critiques;
- false positives;
- missed problems;
- harmful suggested changes.

---

# 14. External-review privacy is not yet mature enough

Before external model review is promoted heavily, add:

```text
packet generation
      ↓
deterministic secret/identifier scan
      ↓
preview
      ↓
explicit user approval
      ↓
external reviewer
```

Pattern-based scanning must not be represented as proof that no sensitive information remains.

The package should record what left the machine and under which approval.

---

# 15. Environment provenance remains incomplete

Current conda/pip capture is good but should eventually include:

- Snakemake per-rule environments;
- container image digests;
- R/Bioconductor/renv;
- GPU/CUDA where relevant;
- reference FASTA;
- GTF/GFF;
- gene-set/reference database versions.

In computational biology, reference-data identity can be as important as software identity.

---

# 16. Remote and HPC provenance need dedicated handling

Remote inputs may include:

- URLs;
- APIs;
- S3 objects;
- SQL/database queries.

They need identities such as:

- URI;
- version;
- ETag;
- query;
- retrieval time;
- checksum.

For HPC, submission-time provenance is not always enough. An optional in-job receipt should capture the actual compute-node environment and reconcile it with the submission receipt.

---

# 17. Provenance is currently mostly proprietary

Internal custom formats are acceptable.

Longer term, export rather than replacement is preferred:

```text
internal provenance
      ↓
RO-Crate export
      ↓
optional W3C PROV / BioCompute if demanded
```

Do not design export standards before the internal run/contract/provenance model stabilizes.

---

# 18. Real-world breadth is insufficient

The current vaccine-response fixture is useful but cannot establish generality.

Independent fixture families should eventually include:

```text
bulk RNA-seq
single-cell
longitudinal
cytometry
genomics
survival
```

Real repositories should also be tested, especially messy mature projects containing:

- stale notebooks;
- inconsistent naming;
- multiple cohorts;
- partially documented transformations;
- HPC workflows;
- historical analytical decisions.

---

# 19. External-user validation is essential

The package author being able to use the system is not enough.

External bioinformaticians should be observed using:

```text
installation
planning
approval
execution
verification
```

Measure:

- confusion;
- false confidence;
- ignored warnings;
- unnecessary friction;
- workflow abandonment;
- misunderstood status semantics.

Real failures should become regression tests or benchmark scenarios.

---

# 20. Visible workflow complexity is too high

The package contains many internally coherent concepts, but ordinary users should not need to understand all of them.

Target user mental model:

```text
PLAN → RUN → CHECK
```

Internal skills such as:

- `decision-status`;
- `data-contract-check`;
- multiplicity views;
- stale checks;

should increasingly be routed automatically.

---

# 21. Persistent state can itself become stale

The root `HANDOFF.md` already demonstrates that operational memory can accumulate and fall behind the repository.

The correct principle is:

> HANDOFF is current state, not historical archive.

History belongs in:

- git;
- changelog;
- roadmap;
- decision ledger.

Prefer derived state over another persistent file.

---

# 22. Maintainability risk is increasing

The central gate and verify machinery have accumulated substantial behavior.

Do not refactor merely because files are large.

Refactor when:

- behavior has stable tests;
- module boundaries are explicit;
- schemas are stable enough.

Likely future boundaries:

```text
command parsing
plan parsing
approval state
fingerprinting
receipts
run lineage
environment capture
workflow adapters
claims
lint
report rendering
```

---

# 23. Anti-gaming work is currently lower priority

The following should remain parked unless real user studies demonstrate a need:

- approval latency;
- comprehension quizzes;
- approval reuse counts;
- seeded fake verification errors;
- vigilance dashboards.

Especially avoid deliberately introducing false verification outputs without strong evidence that the benefit outweighs the trust cost.

---

# 24. Research-software maturity

Before v1, add or formalize:

- protected `main`;
- required CI;
- `CITATION.cff`;
- `CONTRIBUTING.md`;
- compatibility policy;
- schema migration policy;
- release policy;
- authenticated release tags/checksums where appropriate.

v1 should mean stable guarantees, not high feature count.

---

# 25. Strongest current contributions

The genuinely distinctive core is the combination of:

1. repository-grounded pre-analysis planning;
2. explicit analytical-decision checklist;
3. LLM-failure-mode catalogue;
4. data contracts;
5. human plan-hash approval;
6. frozen reportable-run concept;
7. explore/reportable separation;
8. execution receipts;
9. input/code pinning;
10. execution-record verification;
11. output-backed claims;
12. multiplicity history;
13. stale-analysis detection;
14. Mycelium integration without replacing project memory.

The combination matters more than any single feature.

---

# 26. Weakest current areas

The largest remaining deficiencies are:

1. no demonstrated improvement in actual LLM scientific reasoning;
2. no broad LLM benchmark;
3. scientific meaning remains mostly prose;
4. some major analytical errors remain human-review-only;
5. output/run attribution can be heuristic;
6. partial execution can masquerade as success;
7. bioinformatics object-state inspection is narrow;
8. real-world analytical diversity is limited;
9. external-review redaction remains incomplete;
10. environment/reference/container provenance is incomplete;
11. provenance is largely proprietary;
12. workflow complexity is high;
13. persistent operational state can become stale;
14. host guarantees differ;
15. some agent actions remain outside hook coverage;
16. research-software governance is not yet v1-level;
17. speculative anti-gaming could distract from higher-value work.

---

# 27. Final development conclusion

Mycelium Extra currently has enough breadth.

The next stage should not be dominated by new skills.

It should be dominated by:

1. deterministic run/output provenance;
2. stronger reportable-mode guarantees;
3. a small executable scientific contract;
4. a controlled LLM scientific-analysis benchmark;
5. evidence identifying which interventions actually reduce scientific errors.

The most important future result would be empirical evidence of the form:

> Across predefined bioinformatics tasks containing realistic analytical traps, agents using Mycelium Extra make materially fewer critical scientific errors than the same agents without it, while imposing an acceptable additional workflow burden.

If that result is positive, the package becomes more than a useful personal workflow: it becomes an empirically supported methodology for supervising scientific coding agents.

If the result is negative or mixed, the package should become smaller rather than defend unnecessary complexity.
