# Conventions

- Results come from `analysis/` only.
- Join tables by `sample_id`, never by position.
- Gene symbols are HGNC symbols; never round-trip a table through a spreadsheet.
- Reference level for arm contrasts is `placebo`; a positive log2FC means higher in vaccine.
