# Socratic mode, Explain and Challenge

Help the researcher reason about a decision they own, so that approving a plan is an informed act. The agent asks, explains and objects; it never steers toward approval, never quizzes for its own sake, and never decides. Nothing here changes a hook, a gate decision, or the approval words.

## Off by default

Friction is opt-in. Socratic mode starts when the user invokes grill with `socratic`, or says "walk me through it", "help me decide" or "quiz me". It ends on "stop socratic". It lives in the conversation only: no file, no `gate.json` key, no stored state, and nothing is collected from the user's answers.

`explain row N` and `challenge row N` (below) are available at any time after the plan is shown, with or without Socratic mode.

## One probe inside the question

When a rule-3 `user` question is asked, add **one** probe to the same message, after the evidence (and the librarian dossier, if the user chose the lookup, see [evidence-assistance.md](evidence-assistance.md)) and before the options. The user's one reply answers both. A probe costs nothing against the five-question cap and is never a second question. Pick the one that fits:

- Expectation: "Whichever option you pick, what would you expect to see if it is right?"
- Disconfirmation: "What result would make you drop the option you pick?"
- Consequence: "If the option you pick is wrong, which later step breaks first?"

Keep the options and the recommended default exactly as without the probe. Word the probe neutrally: it must not name the answer the agent prefers. If the user skips it, proceed and do not ask again.

The useful product is the user's own words. A stated disconfirmation or expectation becomes that row's Validation cell, sourced `user` and tagged `[human-stated]` in the brief's Evidence. Do not paraphrase it into something safer.

## Explain and Challenge (read-only, on request)

Two ordinary prompts the user may type after the plan is shown. The hook does not act on them; the agent answers, in at most six plain lines each.

- `explain row N`: what the step does, the choice and its source tag (`repo:`, `user`, or `default: <reason>`), the assumption behind it, one alternative and when it would be better, and what the check would show if the choice is right.
- `challenge row N`: the strongest reason this row could be wrong, grounded in repository or retrieved evidence, and the cheapest check that would settle it. If there is no strong objection, say `no strong objection found`; do not manufacture one.

Both are read-only. They do not count toward the cap, change the plan status, edit a file, or approve anything. A challenge that exposes a real plan change ends with an amendment draft the user can accept through the normal route, never with an edit. Do not close either answer by asking whether to approve; the user types `approve plan <hash>` when they decide.

## Explain plan (the linear walkthrough)

`explain plan` answers the whole table at once, in row order, so a reader can go from the top down
instead of piecing the plan together from separate rows. It is the same read-only prompt as
`explain row N`, widened: no file, no state, no approval.

Per row, in order:

- what the step does and the choice it makes, with its source tag;
- what it assumes about its `depends_on` rows, named by row;
- the strongest alternative and when that alternative would be better;
- what its Validation cell would show if the choice is right;
- what breaks downstream if it is wrong, naming the rows.

Budget about 50 words per row, and after ten rows give one line per remaining row. Quote the output
recorded in the plan's `<!-- plan-evidence -->` block verbatim (see
[plan-evidence.md](plan-evidence.md)); never retype a number from memory, and say `not recorded` where
the block has no entry rather than filling the gap.

Open with one sentence naming what the plan is for, and close with the shortest reading order: which
two or three rows to check first, and why those. Do not restate the whole table, do not add a verdict,
and do not end by asking whether to approve.


## What it may not do

- No leading: no probe that contains its own answer, no pressure toward the recommended default.
- No quizzing on what the repository already settles; ask only what the user owns.
- No more than one probe per question, and no probe on a `default:` row the user has not asked about.
- No claim that a source supports a choice it does not. Retrieved evidence stays `[agent-asserted: <DOI or URL>]` and never becomes `repo:`.
- No study data: a live study with researchers stays parked until the usage measurement, and nothing in this mode records what the user answered.
