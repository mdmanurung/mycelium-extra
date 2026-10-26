# Statistical reporting conventions — visible decisions, not mandated methods

- State the exact scientific question and *unit of inference*: independent donor, donor × visit, sample, batch, patient, tissue section, etc. Count individual cells only when they truly are independent experimental units, not as a convenient way to inflate N.
- For pseudobulk: state raw counts, aggregation unit, feature filtering, size factors/precision weights, model and contrast sign. In paired/repeated-measure studies declare within-person covariance and partial/missing pairs.
- For cell composition: state numerator, denominator, missing categories, zero/pseudocount treatment, compositional interpretation and low-count sensitivity.
- Declare fixed/random effects, nuisance confounders, batch/condition identifiability, independent replication, model diagnostics and multiplicity family. Note absent controls or inability to estimate a contrast.
- For inferred factor scores (EBMF/NMF/MOFA): state training data, number/family of factors, projection normalization, feature alignment, uncertainty limitations and whether regression treats estimated scores as observed variables. Do not present an unmeasured uncertainty correction.
- Separate sample-aware association, prediction and causal inference; don't let a plot imply significance. Sensitivity checks must be pre-specified or transparently exploratory.
- Researchers decide models; convention checkers only flag incompatibilities with the **approved** declared model and objectively testable representations.
