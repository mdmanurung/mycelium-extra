# Data manifest

### vaccine-cohort
```yaml
name: vaccine-cohort
type: simulation
source: SIMULATED by tests/fixtures/make_fixture_data.py (mycelium-extra); not real data
date_acquired: 2026-09-01
format: TSV (2 files)
rows: 25 libraries (sample_metadata.tsv); 60 genes (counts.tsv)
columns: 8 (sample_metadata.tsv); 26 (counts.tsv)
size: "12 KB"
raw_path: data/raw/vaccine-cohort/
processed_path: data/processed/vaccine-cohort/
metadata_path: data/metadata/vaccine-cohort/
status: processed
known_issues:
  - D03_day28 was re-sequenced; the copy D03_day28_rerun has preferred_acquisition=FALSE
access_restrictions: none
tags: [rnaseq, vaccine, paired, SIMULATED]
```

SIMULATED. Twelve donors (six vaccine, six placebo), each sampled at day 0 and day 28, plus one
re-sequenced library. Counts are gene-level integers for 60 genes.
