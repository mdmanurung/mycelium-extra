---
name: glossary
disable-model-invocation: true
description: Sharpen an analysis's terms while grilling, keep its GLOSSARY.md, and log each exploratory loop in ITERATIONS.md when there is no clear metric.
---

# Mycelium Extra: Glossary

Two jobs for one analysis folder: fix the words (`analysis/<name>/GLOSSARY.md`) and log exploratory loops (`analysis/<name>/plans/ITERATIONS.md`). Adapted from Matt Pocock's grill-with-docs skill (MIT).

This skill approves nothing and runs no analysis. It writes only those two files. It never writes `.living/` itself, never creates `docs/adr/`, and never edits `data/**/DATA_DICTIONARY.md`.

## 1. Ask in rounds

Follow `references/grilling-rounds.md`: numbered questions over the whole frontier, a recommended answer on each that "yes" accepts, facts found by you or a sub-agent and never asked of the user, done when every branch is a settled term, a decision or a recorded unknown.

## 2. Sharpen the language

Read `GLOSSARY.md` if it exists, the data dictionary (`data/**/DATA_DICTIONARY.md`) and the column names of the tables in play. Then:

- **Challenge a conflict.** When the user's word clashes with the glossary, the dictionary or a column name, say so at once. "The glossary says `batch` is a library-prep day. The table `donors.tsv` has a `batch` column that looks like a sequencing run. Which do you mean?"
- **Sharpen a fuzzy word.** Offer one precise term. "You say sample. Do you mean a donor, a library or a time point?"
- **Invent edge cases.** Make them concrete and analysis-shaped: "Donor D3 gave blood twice. Is that one donor with two time points, or two donors? Which does the test count?" "A cell carries genotype donor A and hashtag B. Which donor is it?"
- **Update inline.** The moment a term resolves, write it to `GLOSSARY.md` in the format of `references/glossary-format.md`. Create the file with `templates/GLOSSARY.md` when the first term resolves, not before. No implementation details in a definition.
- **Check the user's code against the words.** When the user says how something works, check the analysis doc, `code/` comments and table headers agree. Surface a contradiction as a question.

A term that changes a headline estimate, ranking, selection or conclusion depending on its meaning (for example, which donors count as replicates) is an impactful choice. Stop and ask. It needs its own row in an approved plan (`/mycelium-extra:grill`). Do not settle it by writing the glossary.

To see drift, run (read-only, from stdin):

```bash
<skill-dir>/../../hooks/mxpy - --analysis analysis/<name> < <skill-dir>/scripts/check_terms.py
```

It lists each term, how often it appears, and every `_Avoid_` word found in the analysis doc, `code/` comments and table headers. Exit 0: none found. Exit 1: drift, or an `_Avoid_` word that is also a defined term. Exit 2: it could not run, which is a gap and never a pass. `--json` gives raw output. Show the user the hits and ask; do not rewrite their prose or code.

## 3. Decisions

Keep a decision out of the glossary. A decision is worth keeping when both hold:

1. An alternative would change a headline estimate, ranking, selection or conclusion (the lab's impactful-choice rule).
2. It is a real trade-off and would surprise a reader who lacks the context.

Offer it to the user in one line. After they confirm, record it through `/mycelium-extra:decision-status` and its confirm step, in the user's words. Never append to `.living/decisions.md` any other way and never create `docs/adr/`.

A rejected alternative with a load-bearing reason (it was tried and failed, or it would break a stated rule) is a dead end. Offer to record it the same way, as an entry whose status is `rejected for cause` with the reason. Dead ends stop the next session re-trying it.

## 4. Log an exploratory loop

Use this when the work is exploratory and no metric judges it. Read `references/iteration-log.md`, then:

1. Create `plans/ITERATIONS.md` from `templates/ITERATIONS.md` if it is missing. Never edit an earlier entry; add to the next one.
2. Draft one entry with the user: the question; `[SHAPE]`; `[PLOT]` with the path of each saved figure you or the user opened (none: `unsupported: no inspected figure`); `[FINDING]` with a claim level (description, association, prediction, causation, mechanism), never above what the design supports; what would change their mind, as an observable pattern written before the next look; the result of the previous loop's test; and `[NEXT]`.
3. Offer the stopping rule: the conclusion did not change across two consecutive loops, or the next loop cannot change a decision. The user decides.
4. There is no metric field, on purpose. A number would make loops look more settled than they are.

A step the loop needs (a new filter, normalisation or threshold) is an impactful choice if an alternative would change the result. Stop and ask for a plan row.

## Boundaries

- Writes: `analysis/<name>/GLOSSARY.md` and `analysis/<name>/plans/ITERATIONS.md`, nothing else. The gate may treat `analysis/**` as gated; if a write is denied, tell the user and stop.
- Reads: the analysis doc, `code/`, tables, the data dictionary.
- Does not edit `grill`, `new-analysis` or the `where` card. A scaffold may copy the two templates; this skill does not do it for them.
