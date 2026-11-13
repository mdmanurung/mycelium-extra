# ITERATIONS.md: the exploratory loop log

Path: `analysis/<name>/plans/ITERATIONS.md`. Template: `templates/ITERATIONS.md`. Create it at the first loop the user wants logged.

## Why it exists

Exploratory work has no gold standard and no metric. The risk is drift: each look changes the story a little, and nobody can say what moved it. The log keeps one short entry per loop so the user can see what was believed, on which figure, and what would have changed their mind.

## Why there is no metric field

A score would make loops look more settled than they are. Without a gold standard the number measures nothing the user can check, and a rising number invites stopping for the wrong reason. The log has a stopping rule instead.

## Entry fields

| Field | Rule |
|---|---|
| Question | One sentence. |
| [SHAPE] | What the data look like now: donors, cells, groups. Donors are the replicates. |
| [PLOT] | Path of every saved figure inspected in this loop. Open each one before you cite it. No figure: `unsupported: no inspected figure`. |
| [FINDING] | What the user now believes, with a claim level: description, association, prediction, causation or mechanism. Never above what the design supports; an observational contrast is an association. |
| Would change my mind | An observable pattern, written before the next look. Examples: a negative control that also "responds", known biology that disagrees, the other modality not agreeing, the result vanishing under another preprocessing. |
| Last loop's test | After the next look: seen, not seen, or not testable, with the figure path. Fill it in the next entry, never edit the old one. |
| Conclusion changed | yes, no, or first loop. |
| Can the next loop change a decision | yes or no. |
| [NEXT] | The next question, or `stop: <rule>`. |

The agent drafts the entry; the user states the belief and the mind-changing pattern. If the user cannot name one, write `none yet` and make that the first thing to settle.

## Stopping rule

Stop when the conclusion did not change across two consecutive loops, or when the next loop cannot change a decision. Offer it; the user decides. Stopping early on one quiet loop is a choice the user makes, not a default.

## Choices found while logging

A preprocessing, filter, threshold or model change the loop needs is an impactful choice when an alternative would change a headline estimate, ranking, selection or conclusion. Stop and ask. It needs its own row in an approved plan, never a default. The log records that the loop happened; it does not approve anything.

## Decisions and dead ends

The log is not the decision record. When a loop settles a choice worth keeping, use the decision path in `SKILL.md`.
