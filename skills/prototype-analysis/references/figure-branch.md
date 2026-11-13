# FIGURE branch

Question: what should this panel look like? Read this when SKILL.md step 1 picked FIGURE.

## Build

1. **One plotted table.** Build the data frame the panel would plot, once. All variants read the same table. Print its columns, row count and number of donors. A variant that needs a derived table (per-donor difference, heatmap matrix) derives it from this one in code and prints it, so nobody can drop a row by hand.
2. **Three radically different variants.** Different geometry or summary, never colour or font tweaks. Draw from these families and name each variant by its geometry:
   - paired lines, one per donor, joined across conditions
   - per-donor difference (one dot per donor) with a zero line and a named interval
   - distribution (violin, ridge or box) with donor points over it
   - heatmap with donors as rows
   - slope or change plot with the aspect set so slopes bank near 45 degrees
   If two drafts look alike, redo one with another family.
3. **Lab figure rules.** Each donor is a point over a named summary (state SD, SE or CI). Bars start at 0. Axes carry units. Source the theme from `code/theme.R` (or `code/theme.py`) when present, else `ggpubr::theme_pubr(base_size = 8)`. Width 89 mm.
4. **Same facts.** Every variant shows all donors and all rows of the table. Print `n donors` and `n rows` per variant: they must equal the table's, and a donor with a missing pair stays visible as a gap. Variants share one axis rule for the same quantity (same limits, or all free and said so on the sheet).
5. **Render.** Save `prototype_<panel>_A.png`, `_B.png`, `_C.png` at 300 dpi, plus one contact sheet `prototype_<panel>_sheet.png` with the three side by side and a letter on each.

Done when the four PNGs exist, you opened the contact sheet, and the printed `n donors` and `n rows` match across variants and the table.

## Hand over

Show the contact sheet. State in one line what each variant lets the reader see best and what it hides. Ask the user to pick one, or to name what to take from each.

The pick is the user's. The winner becomes a plan row: a figure step with its script under `analysis/`, its source-data table and its caption. The prototype code is not that script.
