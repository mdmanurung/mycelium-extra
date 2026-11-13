# Agent brief

Pass this text to the background agent, with the braces filled in. The agent has no other context.

---

Research one question and write one Markdown note.

Question: {question}
Decision it feeds: {decision}
Pinned versions: {pins}
Write the note to: {path}
Analysis folder (read-only context, may be none): {analysis}

Read first: `{skill-dir}/references/note-format.md` and `{skill-dir}/references/sources.md`.

Do this:
1. Find the primary source that owns each claim (sources.md says what counts). Open it and read the passage. Quote or copy the value. A secondary write-up is a lead: follow it to the source, or leave the claim `unsupported: no source`.
2. Write the note in the format of note-format.md. Every Evidence row cites a reference id defined in References. Every reference carries a version, release, year or date.
3. Run `{skill-dir}/../../hooks/mxpy - {path} < {skill-dir}/scripts/check_note.py` and fix the note until it exits 0.
4. Return only the note path and the two-line answer.

Rules:
- Cite only what you opened. Never write a reference, quote or number from memory. If a lookup fails, say so in "What is NOT established".
- Do not run analysis code, load the user's data, edit code, or edit any plan. Read-only version queries (`pip show`, `packageVersion`) are fine.
- Write nothing except the note. Do not touch `.living/`, `todo/`, `plans/PLAN.md` or `plans/TRACKER.md`.
- If a fact implies a different impactful choice (a filter, normalisation, model, threshold, reference release), do not apply it. Put it in "Next step" as `Decision for the user: <choice>, because <fact> (S<n>)`.
- A claim about the user's own results is out of scope. Write `unsupported: no inspected figure`.
- Use web search and the bio tools (PubMed, bioRxiv, Europe PMC, UniProt) when available. If a tool is missing, say which, and continue with the rest.
