# E05. The hoped-for claim became a check, and the evidence said the documented folder did not exist

Control point: **visibility**

Anonymised from a real project. Source: an approved figure plan in project B. Cards regenerated on the fixture.

![The notes describe a figures folder, while inspection finds that folder absent. A prose intention to match figure numbers is not an executed or bound validation check.](../figures/document-versus-inspection.svg)

This schematic draws on the anonymised plan and regenerated card below. A written intention is not evidence that its validation ran or passed.

## 1. Socratic: ask these first

- In my words, what must be true of every number on a figure?
- Which statement in the project notes did the agent check, and what did it find?
- Which row of the plan will fail loudly if a figure drifts from the record?

## 2. What the tool showed

The grill echoed the question in the researcher's words and the hoped-for claim, then listed Evidence with tags:

```text
> Question (user's words): "which figures show each recorded finding without changing any claim"
> Hoped-for claim: "every number on a figure reproduces the number in the findings"

Evidence
- The folder the project notes describe (`figures/`) does not exist. [agent-derived: ls]
- No shared palette exists in the repo, so one is defined once at the top of the script. [agent-derived: grep of scripts]
Facts: 2 agent-derived, 0 human-stated, 0 agent-asserted.
```

`card <hash> full` (regenerated) shows what is not established:

```text
Sequence   (* = a default decided; confirm it)
    1 <script>*
        - choice: one palette block; every figure checks its own numbers before saving
        - assumed: no shared style exists
        - check: every number on a figure equals the number in the findings file
Not established before running
  - Validation on rows 1, 2 is prose: no validation-bindings check is bound to it
  Out of scope here: whether the science is right, and runs the gate's hooks do not see
```

## 3. Track-changes shape

Not a change episode. The Coverage line states the check is prose only; that is a Gap in track-changes wording, not a pass.

## 4. Librarian block

Not applicable: the repository settled every question (no methodological choice left open), so no lookup was offered.

## 5. What the human decided

Approved with the palette default confirmed; figures stay exploratory and change no claim.

## 6. Without the tool

The notes' folder would have been assumed, and the claim "numbers match" would have been an intention rather than a stated validation cell that `verify` can later grade.

Basis: 1 plan; Facts line 6 agent-derived, 0 human-stated in the original.
