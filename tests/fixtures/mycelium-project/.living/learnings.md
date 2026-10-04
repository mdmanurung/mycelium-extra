# Learnings

### [2026-04-05] Spreadsheet round-trip renamed MARCHF1 to 1-Mar

**Category**: gotcha

**What happened**: The counts table was opened and saved in a spreadsheet program, which turned
the gene symbol MARCHF1 into the date 1-Mar and SEPTIN7 into 7-Sep.

**Why it matters**: Renamed genes drop out of joins silently and vanish from the results.

**Resolution**: The table was regenerated from the pipeline output.

**Tags**: data, gene-symbols

**mitigation_type**: ambient-awareness

**structural_mitigation_candidate**: In `analysis/vaccine-response/scripts/02_paired_test.py`, assert that no value in the `gene` column of `data/processed/vaccine-cohort/counts.tsv` matches the date pattern `^[0-9]{1,2}-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$`.

### [2026-06-02] Sample join went wrong once

**Category**: failure

**What happened**: A table join dropped rows in an early draft.

**Why it matters**: Fewer samples than planned.

**Resolution**: Fixed by hand.

**Tags**: joins

**mitigation_type**: ambient-awareness

**structural_mitigation_candidate**: be careful with joins
