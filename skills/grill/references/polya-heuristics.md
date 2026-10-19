# Reasoning heuristics for a blocked plan

Use this file when the plan is blocked: a decision point will not resolve from the repository, the user's question does not yet name a claim that can be checked, or two defensible designs remain and neither is obviously right. It is a resolution aid, not a second questionnaire: it never adds questions beyond the cap in `SKILL.md`, and its output is one or more plan rows, not prose.

## Backward-chaining the plan

Work from the hoped-for claim back to the check, not from the data forward to a method. Four links, each of which must be writable in one line before the plan is stable:

1. **Claim** — the sentence the user hopes to write, with its direction and population ("treated donors have a higher X than controls in this cohort").
2. **Estimand** — the exact quantity that sentence rests on: contrast, direction, unit, and population. If the claim is causal, say what design licenses it (randomization, an explicit identification strategy, or nothing, which makes the claim observational).
3. **Replication unit** — what is independently sampled and therefore what the test's n counts. This link usually decides the model; it is the most common place a plan is quietly wrong.
4. **Discriminating check** — the observation that would separate the claim from its nearest rival, and the result that would refute it. A check that cannot fail is not a check.

If a link cannot be written, that link is the plan's open decision, and the question is worth spending one of the five on. If the chain reads backwards (the method was chosen first and the claim retrofitted), say so plainly and rebuild it.

## Five selective heuristics

Apply only the ones the blockage calls for, and record which one produced the row you add.

- **Work backward.** Start from the check in link 4 and ask what must be true of the data, the joins, and the model for that check to mean anything. Each answer becomes a guard row. This is the default move for a plan that is stuck on method choice.
- **Analogy to a prior analysis in this repository.** Search for the closest settled decision or finding (`.living/decisions.md`, `.living/findings.md`, a sibling analysis's plan) and cite it as `repo:`. Analogy carries the *shape* of a decision, never its numbers: a threshold from another cohort is a default with a reason, not evidence.
- **A simpler counterexample or a known-answer fixture.** When a method's correctness is the doubt, propose the smallest input whose right answer is known by hand (two samples, one deliberate sign flip, one positionally mis-joined row) and make it a check the plan runs before the real data. Prefer this to reasoning about whether the code is right.
- **Decomposition.** When the blockage is "this is too large to plan", split it until each piece has its own check and its own output path, and park the pieces the current question does not need with a return condition.
- **An auxiliary plot.** When the doubt is about the data rather than the method — batch structure, a bimodal library size, a suspicious cluster — propose one small figure as a *guard* (a QC view whose surprising shape changes the plan) rather than as a deliverable, and say what surprising shape would change the plan.

## What these heuristics may not do

- They never settle something the user owns: the scientific question, the estimand, or an accepted trade-off. Those stay `user` questions under the gate in `SKILL.md`.
- They never convert absent evidence into evidence. A heuristic result is `default: <reason>`, not `repo:`.
- They never widen the plan: a new step added by a heuristic must trace to the claim in link 1, or it goes to Parked with a return condition.
- They never change the brief's shape: the same 150-word brief, the same one plan table, the same statuses.
