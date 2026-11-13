# Note format

One file. Sections in this order. `scripts/check_note.py` checks the shape; it cannot check that a quote is real.

| Part | Rule |
|---|---|
| `# Title` | The question as a short title. |
| `Pinned:` line | Versions and releases the answer holds for: package versions from the active environment, genome and annotation release, dataset accession and date. `none: <reason>` only when the question needs none. |
| `## Question` | One sentence. |
| `## Answer` | At most two lines. A reader who stops here has the answer and its limit. |
| `## Evidence` | A table with the columns `Claim`, `Source`, `Quote or value`, `Confidence`. No empty cell. |
| `## Not established` | What the sources do not settle: other versions, claims with no source, lookups that failed. |
| `## Next step` | The one thing to do with this. A fact that implies a different impactful choice is written `Decision for the user: <choice>, because <fact> (S<n>)`. |
| `## References` | One line per source, starting `S1`, `S2`. Each has the author or package, the title, a version, release, year or date, and a DOI, PMID, arXiv id, URL or file path. |

## Evidence rules

- Source cell: a reference id plus the location inside it (`S1 Methods, "Cell isolation"`, `S2 source, R/fit.R:112`, `S3 supplement table S4`). Or exactly `unsupported: no source`.
- An unsupported row has confidence `low`. The claim stays in the table so the reader sees what was not backed.
- Confidence is `high`, `medium` or `low`. High means the source states it in so many words for the pinned version. Medium means you read it from code or a table. Low means inferred or unsupported.
- Put the title, first author and identifier of a paper on its References line. `verify` resolves a citation by comparing the service's title and first author with that line.
- A claim about the user's data is not a row. If the question is about a result, the note says `unsupported: no inspected figure`.

## Example

```markdown
# Does seurat_v3 HVG selection drop zero-count genes

Pinned: scanpy 1.10.3 (active env, 2026-11-13)

## Question

Does `sc.pp.highly_variable_genes(flavor="seurat_v3")` drop zero-count genes first?

## Answer

No. Zero-count genes get variance 0 and rank last.
Filter first if the plan needs a fixed gene count.

## Evidence

| Claim | Source | Quote or value | Confidence |
|---|---|---|---|
| Expects raw counts | S1 docstring | "expects raw count data" | high |
| Zero-count genes rank last | S1 source, `_highly_variable_genes_seurat_v3` | variance 0 | medium |

## Not established

Other scanpy versions.

## Next step

Decision for the user: filter genes before HVG? It changes the selected features (S1).

## References

- S1 scanpy 1.10.3 documentation and source, `highly_variable_genes`, https://scanpy.readthedocs.io/en/1.10.3/, read 2026-11-13.
```
