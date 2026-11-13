---
name: prototype-analysis
disable-model-invocation: true
description: "Build a throwaway prototype that answers one analytic question: does a method behave sensibly, or what should a panel look like. Use before a plan row commits to either."
---

# Mycelium Extra: Prototype analysis

A prototype is throwaway code that answers ONE analytic question. The question picks the branch. Adapted from Matt Pocock's prototype skill (MIT).

A prototype never feeds a reported result. Nothing it prints is cited, and no figure it draws is evidence (plot-first treats it as exploration).

## 1. State the question

Write one sentence: the question, and the answer that would change the next step. Ask the user when it is unclear.

Done when the sentence names a branch:

- **DATA**: "does this method, threshold or model behave sensibly?" Read `references/data-branch.md`.
- **FIGURE**: "what should this panel look like?" Read `references/figure-branch.md`.

A question that needs both is two prototypes. Run DATA first.

## 2. Agree the scratch path

Name the analysis the prototype belongs to (the focused one, or ask). Put the prototype in `analysis/<name>/scratch/prototype_<question>/`, away from `code/` and `outputs/`. Name every file `prototype_*`.

That path is gated, so a run needs the user's `allow explore` grant and the `MYCELIUM_EXTRA_EXPLORE=1` prefix (see the approval-gate doc). The gate logs each run as exploratory. Keeping the prototype out of `outputs/` and out of reported results is your job: the gate does not check it.

Done when the user has confirmed the path and typed `allow explore`.

## 3. Build it throwaway

- One command runs it, and the command is the first line of the file.
- State lives in memory. No cache, no output under `outputs/`, no step stem.
- No polish: no argument parsing beyond one knob, no tests, no helpers used once.
- Seed every random step and print the seed.

Done when one command, run from the project root, prints its state with no other file needed.

## 4. Show the state

DATA prints the full relevant state after every action. FIGURE saves PNGs the user can open. Open each PNG yourself before you describe it.

Done when you can state, from what the prototype printed or drew, what each action changed.

## 5. Take the verdict from the user

Report what you saw. The user judges. Any choice that a different value would turn into a different estimate, ranking, selected feature or conclusion is impactful (threshold, filter, transform, contrast, model family, family of tests). The prototype only suggests it.

Done when each suggested choice is a proposed plan row (value, why, alternatives tried), and none is applied. A DATA prototype draws no figure, so write its verdict as what it printed, not as a conclusion. A conclusion drawn from a FIGURE variant cites the PNG you opened.

## 6. Capture and clean up

Write the verdict as a dated entry in `analysis/<name>/plans/ITERATIONS.md` (the `glossary` skill, when present) or else the log of `analysis/<name>/plans/TRACKER.md`. Use this shape:

`<date> prototype <name>: question <one sentence>; verdict <one sentence>; figure <PNG path you opened | none, DATA>; folder deleted | kept`

Then ask the user: delete `analysis/<name>/scratch/prototype_<question>/`, or keep it in place. A throwaway git branch `prototype/<question>` needs a commit, so make one only when the user asks for it.

Done when the verdict line exists and the user has chosen delete or keep. After a delete, `ls` shows no `prototype_*` file in the folder.

## Boundaries

- A prototype that works is not a step. A kept idea becomes a plan row (`grill`) whose script is written fresh under `analysis/`, then run through the gate.
- Never write `.living/` or `todo/`. A settled decision goes through `decision-status`, after the user confirms.
- To check a real step against known truth, use `check-first`. To chase a surprising result, use `diagnose-result`.
