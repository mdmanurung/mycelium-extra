# Grilling style for this skill

Adapted from Matt Pocock's grilling skill (MIT). Applies to every question this skill asks.

- Map the open points as a tree: each unsettled term or decision may unblock others.
- The frontier is every point whose prerequisites are settled. Ask the whole frontier in one round, numbered, then wait.
- Give a recommended answer with each question, worded so "yes" accepts it. Example: "Q2. Do we call the person `donor` and the genotype-based assignment `genotype donor`? Recommended: yes."
- Facts are yours to find. Column names, dictionary entries, counts of a word in the doc or code come from a sub-agent or from `scripts/check_terms.py`, never from the user. Do not wait for the sub-agent to ask the other questions; only questions downstream of the fact wait.
- Decisions are the user's. A term meaning that changes a headline estimate, ranking, selection or conclusion is an impactful choice: it needs its own row in an approved plan and is never a default.
- Done when every branch is a settled term or decision, or a recorded unknown. Write an unknown into the doc's open questions with the `[NEXT]` tag. Do not act on the result until the user agrees.
- This grilling is not the `grill` plan step. It sharpens language; it approves nothing and runs nothing.
