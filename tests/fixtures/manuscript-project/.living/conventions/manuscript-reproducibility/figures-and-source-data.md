# Manuscript panels, source-data and evidence

Use a reader's figure/table map with fields `figure_or_table,script,input_statistical_result,source_data,output,status,limitations`. Naming is flexible; a stable ID is not.

**For each panel**: the executable script's expected inputs and output files; physical size and vector/raster output settings; named semantic color mapping; axes, units and transformations; exact source table with every plotted numeric and categorical aesthetic including x/y, color, fill, size, facets, uncertainty limits and labels. The figure should be renderable from the exported source table without refitting heavy models. Store full precision in source data.

**Review**: verify script exists and the table includes every variable actually consumed by plot calls. Inspect the plot visually for clipping, label mapping, sign, group/stratum mix-ups and units. Compare numerical values with the statistics output. A validator that checks only an author-supplied list of fields does *not* prove this list is complete: review plotting source code separately.

**Examples grounding this convention:**
- ImmGen-T standalone `script/Figure5.R` + `analysis/Figure5.Rmd` and README panel map; docs include pre-rendered images (building docs alone is not proof of re-rendering).
- GTestimate `notebooks/pub_figures.Rmd` reloads saved ggplot objects and exports physical-size PDFs.
- single_cell_aging README maps figures and supplementary tables to notebooks.
- IHA Figure 1F source-data export omits a plotted numeric variable; the code observation is demonstrated, downstream paper impact unverified.

Document exceptions: controlled-access datasets, unsupported platforms, external collaborator panels, unreproducible legacy versions and expensive training steps. Never label an exported PNG alone as full source-data reproducibility.
