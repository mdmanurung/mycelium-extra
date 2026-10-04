# vaccine-cohort data dictionary (SIMULATED)

## sample_metadata.tsv (one row per library)

| Column | Meaning |
|--------|---------|
| `sample_id` | library ID, `<donor>_<visit>`; a re-sequenced library adds `_rerun` |
| `donor` | donor ID, D01 to D12 |
| `arm` | `vaccine` or `placebo` |
| `visit` | `day0` or `day28` |
| `run_id` | sequencing run (the lab calls it seq batch) |
| `lane` | flow-cell lane, L1 or L2 |
| `preferred_acquisition` | `TRUE` for the library to analyse, `FALSE` for a superseded copy |
| `rin` | RNA integrity number |

## counts.tsv

Rows are genes (`gene`, HGNC symbol); the other columns are `sample_id`s, in an order that
differs from `sample_metadata.tsv`. Join by `sample_id`, never by position.
