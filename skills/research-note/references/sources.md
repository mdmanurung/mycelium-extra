# Sources

A **primary source** owns the claim. A **lead** points to one. Follow every lead to its source; if you cannot, the claim is `unsupported: no source`.

| Question about | Primary source | Lead only |
|---|---|---|
| A method or statistic | The paper's methods and supplement; a statistical text; the method's original paper | Blog posts, tutorials, forum answers, Q&A sites |
| What a package does | Its source and docs for the installed version (`pip show`, `packageVersion`); the changelog entry for that version | A newer docs page, a vignette for another version |
| A genome or annotation | The release notes and the file's own header or README for the pinned release (GENCODE, Ensembl, RefSeq) | A genome browser screenshot, a gene page for the current release |
| A dataset | Its accession record, data dictionary and the paper's data availability section | A re-analysis, a database mirror |
| A gene or protein fact | The curated record with its release or date (UniProt, Ensembl, HPA) | A review that quotes it |
| A reagent or panel | The vendor's datasheet for the lot or version; the paper's supplement | A forum post |

## Tools

- Papers: PubMed, Europe PMC and bioRxiv tools first, then web search. Read the abstract and the passage you cite. A preprint is `medium` at best, and its References line says preprint.
- Code and docs: fetch the page or file for the pinned version. A docs URL that says `stable` or `latest` is not a pin: find the versioned page, or note the date read.
- Records: UniProt, Ensembl, Open Targets and similar tools. Copy the value and the record's release or date.

## Do not

- Cite a DOI, PMID or title you did not open.
- State a number you did not see in the source.
- Treat agreement among secondary write-ups as a primary source.
