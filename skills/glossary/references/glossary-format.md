# GLOSSARY.md format

Adapted from Matt Pocock's domain-modeling skill (MIT).

File: `analysis/<name>/GLOSSARY.md`. Create it when the first term is resolved, not before. One file per analysis. A word used the same way in every analysis belongs in the lab's own notes, not here.

```md
# <Analysis name>: glossary

<One or two sentences: what this analysis studies and which words it must keep apart.>

## Language

**Donor**:
A person who gave blood. The unit of replication; every test counts donors, not cells.
_Avoid_: patient, subject, sample

**Genotype donor**:
The donor a cell is assigned to by genotype demultiplexing, not by a hashtag label.
_Avoid_: demux donor, SNP donor

**Batch**:
A group of libraries prepared together on one day.
_Avoid_: run, plate, lane

**tp_call**:
The time-point label the sequencing core wrote in the sample sheet (D0, D7, D28).
_Avoid_: timepoint, visit
```

## Rules

- Be opinionated. Pick one word per concept and list the others under `_Avoid_`. The checker flags those words in the analysis doc, code comments and table headers.
- One or two sentences per definition. Say what the thing is, not how the code makes it.
- No implementation details: no formulas, thresholds, package names, file paths or column names as the definition. A column name may appear in a sentence only to say which column carries the term.
- Only terms specific to this analysis: donor versus genotype donor, batch versus run, singlet, `tp_call`. Skip general words (PCA, FDR, UMAP).
- Write a term as it appears in the data when the data fix its spelling (`tp_call`). Matching is case-insensitive and treats `_`, `-` and spaces as word breaks, so `Avoid: run` also flags `run_id` in a table header. Inline code and path-like words in the doc and comments are skipped.
- Group terms under subheadings only when clusters appear.
- An `_Avoid_` word must not be a defined term of its own. The checker reports that clash.
- A decision is not a term. Do not record choices, thresholds or reasons here; see the decision path in `SKILL.md`.
- A term that conflicts with `data/**/DATA_DICTIONARY.md` is not settled by editing the glossary alone. Ask which source is right, then fix the wrong one (the dictionary is a data file: tell the user, do not edit it).

## What `check_terms.py` reads

| Place | What is scanned |
|---|---|
| analysis doc (`<NAME>.md` or `README.md`) | every line, except fenced code |
| `code/` | comment text only (`#` lines and trailing `#` comments; `//` in `.js`, `.cpp`) |
| table headers | first line of `*.tsv` and `*.csv` under `outputs/` and `data/` (links followed) |

It never reads `GLOSSARY.md` itself, `.living/`, or cell values.
