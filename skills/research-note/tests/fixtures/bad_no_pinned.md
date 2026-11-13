# Does scanpy 1.10 filter genes before HVG selection



## Question

Does `sc.pp.highly_variable_genes` with `flavor="seurat_v3"` drop genes with zero counts first?

## Answer

It does not filter by itself; zero-count genes get no variance and rank last.
Filter first if the plan needs a fixed gene count after filtering.

## Evidence

| Claim | Source | Quote or value | Confidence |
|---|---|---|---|
| seurat_v3 expects raw counts | S1 `highly_variable_genes` docstring | "expects raw count data" | high |
| Zero-count genes rank last | S1 source, `_highly_variable_genes_seurat_v3` | variance 0 gives rank NaN | medium |
| The method works well for sparse donors | unsupported: no source | none | low |

## Not established

Behaviour on scanpy versions other than 1.10.3.

## Next step

Decision for the user: filter genes (min_cells) before HVG? It changes the selected features.

## References

- S1 scanpy 1.10.3 documentation, `scanpy.pp.highly_variable_genes`, https://scanpy.readthedocs.io/en/1.10.3/, read 2026-11-13.
- S2 Stuart T, Comprehensive integration of single-cell data. Cell 2019. doi:10.1016/j.cell.2019.05.031
