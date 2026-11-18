# Literature policy

How the note agent finds papers. It applies when the question needs papers, not package docs or source code. The agent runs every search itself and never hands retrieval to another agent.

Idea from OpenResearch orx-lit-review (MIT, alphaXiv): scale effort to difficulty, fix one window, dedupe in order, rank wide then read few. Nothing here is copied from it.

## Backends

| Backend | Tool | Use it for | Limit |
|---|---|---|---|
| PubMed | `search_articles`, `get_article_metadata`, `get_full_text_article` | Biomedical and life-science journal papers. Ids are PMIDs. | Full text only when PubMed Central has it. |
| bioRxiv | `search_preprints`, `get_preprint` | Recent biology preprints. | Search takes a date range and a category, no keywords. Filter the returned titles and abstracts yourself. |
| Consensus | `search` | A plain-language question across all fields. | Batch at most 3 calls. Pass year filters only for the fixed window. It returns abstracts, not full text. |

A backend that is missing or fails is named in `## Not established`. Continue with the rest. Web search is a fallback only when these return nothing useful.

## Steps

1. **Rate difficulty from 1 to 10.** This sets the number of follow-up rounds: 1 to 3 gets 0, 4 to 7 gets 1, 8 to 10 gets 2. The budget is a cap, not a target. Write the rating and the reason in the retrieval log.
2. **Fix one window.** Use the window the user gave in the brief. When none was given, write `Window: none`. Never invent a cutoff to favour newer work. Every call, first round and follow-up, uses the same window. Never widen it mid-search.
3. **Run the first round.** Build each query from the user's own words. Never guess what an acronym stands for. Query only the backends that fit the topic.
4. **Dedupe in this order.** Match the id first (PMID, bioRxiv or arXiv id), then the DOI, then the title after lowercasing and stripping punctuation. Keep the journal record when a preprint and its paper both appear.
5. **Stop or follow up.** If the candidates cover the question, stop. Otherwise spend a round on one concrete gap: a missing method, benchmark, organism or title phrase. A round that only rephrases an earlier query is not allowed. Calls for the same gap count as one round.
6. **Rank 5 to 15 candidates.** Rank by fit to the question. Prefer fewer strong papers to padding. Do not compare citation counts across backends.
7. **Read 3 to 5.** Open the full text, or the abstract when full text is unavailable. Say which in the Source cell (`S2 abstract`, `S2 Methods`).
8. **Write the note.** Quote only text you read. Copy each id from a tool result. Never write an id, title or quote from memory.

## The retrieval log

The note ends with `## Retrieval log`, after `## References`. It records what the tools returned, so a reader can check that each cited paper was found and not recalled.

```markdown
## Retrieval log

Window: none
Difficulty: 5 (two methods compared), 1 follow-up round

- PubMed search_articles "<query>": 12 results; kept PMID 31178118, PMID 31178119
- Consensus search "<query>": 10 results; kept doi:10.1016/j.cell.2019.05.031
- Round 2, gap "<gap>", bioRxiv search_preprints: 8 results; kept doi:10.1101/2020.01.01.123456
```

Every DOI, PMID and arXiv id on a `References` line must appear in this log. `scripts/check_note.py` enforces it and also requires the `Window:` line. A reference with only a URL or file path (docs, source code) needs no log entry.

## Do not

- Cite an id the tools did not return.
- Quote a passage you did not open.
- Change the window or the priority after the first call.
- Pad the ranked list to reach 15.
