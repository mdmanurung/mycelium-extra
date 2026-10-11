# Decisions

### [2026-03-02] Normalisation: median-of-ratios

**Context**: Library sizes differ by up to about 2-fold between libraries, and the vaccine
response is expected to raise a group of interferon genes strongly.

**Decision**: Normalise counts with median-of-ratios size factors.

**Rationale**: Total-count scaling lets a few strongly induced genes shift every other gene's
share of the library. Median-of-ratios is robust to that.

**Status**: confirmed

**Supersedes**: none

**Tags**: normalisation, vaccine-response

### [2026-04-01] Exclusion: keep preferred acquisitions only

**Context**: D03_day28 was re-sequenced. Both libraries are in the processed tables; the
re-sequenced copy carries `preferred_acquisition=FALSE`.

**Decision**: Keep only libraries with `preferred_acquisition == TRUE`, one per donor and visit.

**Rationale**: Counting both libraries would count one donor-visit twice.

**Status**: confirmed

**Supersedes**: none

**Tags**: exclusion, samples

### [2026-04-20] Batch: run_id is the sequencing batch

**Context**: The lab calls the sequencing batch "seq batch"; the metadata column is `run_id`.

**Decision**: Treat `run_id` as the seq batch. Each run holds both arms, and both of a donor's
samples share a run.

**Rationale**: With both arms in every run, the arm contrast is not confounded with batch.

**Status**: confirmed

**Supersedes**: none

**Tags**: batch, metadata

### [2026-05-10] Normalisation: hold pending spike-ins

**Context**: A collaborator suggested ERCC spike-ins for normalisation.

**Decision**: Hold the normalisation choice until spike-in data is available.

**Rationale**: Spike-ins would give an external reference independent of the biology.

**Status**: held

**Supersedes**: none

**Tags**: normalisation

### [2026-07-15] Normalisation: TMM considered, median-of-ratios stays

**Context**: No spike-ins were run. TMM was compared with median-of-ratios on the processed data.

**Decision**: Keep median-of-ratios.

**Rationale**: The two agree on the hit list; median-of-ratios is already in the analysis.

**Status**: confirmed

**Supersedes**: [2026-05-10] Normalisation: hold pending spike-ins

**Tags**: normalisation
