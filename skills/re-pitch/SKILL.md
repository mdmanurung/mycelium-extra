---
name: re-pitch
disable-model-invocation: true
description: Re-pitch your last message in short plain sentences when the user lost the thread, with no claim weakened and the decisions numbered at the end.
---

# Mycelium Extra: Re-pitch

The user lost the thread of your last message. Rewrite that message. Read no file to find the state of the analysis: that is the `where` card. Read the glossary, analysis doc and data dictionary only to match terms. Adapted from Matt Pocock's wait-what skill (MIT).

## Format

1. Answer first: one sentence that says where we are.
2. Two lines of context: the goal of the analysis and the step we are on.
3. The content in short sentences. One idea each, about 12 words, active voice, everyday words, no idioms (the spirit of ASD-STE100 Simplified Technical English).
4. At most five list items. A longer list becomes five or fewer numbered steps, with the rest named as "later".
5. End with the decision or action the old message asked for, numbered `1.`. When it asked for several (impactful choices, plan rows awaiting approval), give one numbered item each, in the old order. Merge none.

## Rules

- Use the analysis's own terms from `analysis/<name>/GLOSSARY.md` (glossary skill) when it exists. Otherwise use the terms in the analysis doc and the data dictionary. Do not coin new words.
- Keep every number, unit, effect direction, interval and caveat. Never weaken a claim or drop a caveat to be shorter. Split the sentence instead.
- Keep each figure path and each `unsupported: no inspected figure` tag the old message has, next to its conclusion. Add no path. Mark a conclusion that had neither with `no figure named in the old message`.
- If the last message was a plan or a card, keep its table rows word for word. Reword only the text around them.
- Keep an impactful choice as its own item and ask for the user's answer. Do not turn it into a default.
- Add no new finding, step or advice. This skill writes nothing, including `.living/` and `todo/`.

## Done when

- The first sentence gives the answer.
- Every number and caveat of the old message is still there.
- Each conclusion has its old figure path, its old `unsupported` tag, or the `no figure named` mark.
- The last lines are numbered decisions or actions, one for each the old message asked.
