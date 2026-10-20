# E04. A plan question exposed a wrong assumption in the project's own docs

Control point: **visibility**

Anonymised from a real project. Source: the approved "check the plan against the data" brief in project B (no analysis ran; docs only). The card is regenerated on the fixture. The librarian block is illustrative: the dossier feature post-dates that session, nothing external was searched, and no researcher answer is recorded.

## 1. Socratic: ask these first

- What does the planning document say about one sample per donor at the first visit, and who checked it against the sample table?
- If the claim is wrong, which later fit counts a donor twice?
- What would I expect the data contract to show if the document is right?

## 2. What the tool showed

The grill ran read-only probes and reported what it confirmed and what was wrong or incomplete. The wrong item:

```text
Wrong or incomplete in the docs:
- Duplicate aliquots. N donor x timepoint cells have 2-3 aliquots; K of them at the first visit.
  So step T3.4's "one aliquot per donor at the first visit, drop the donor random effect" is false.
  That fit would count those donors twice.
```

Approval card for the corrected plan (regenerated):

```text
Question  "does the change differ between arms within the subset"
Choices   1 baseline contrasts inside the paired fit; keep the donor random effect  [default: repo policy keeps duplicate aliquots]*
Defaults to confirm: step 1  (* = a default decided)
Checks    plan text no longer says 'drop donor random effect' · ...
```

The `*` marks a default the researcher is asked to confirm; the Evidence listed "3 agent-derived, 0 human-stated, 0 agent-asserted".

## 3. Track-changes shape

Observed: documentation text differs from the sample table (K duplicated cells). Potential analytical implication: a variance component estimated as if each donor appeared once. Gap: no fit had run, so no estimate depends on it yet. Unknown: how many other documents repeat the sentence.

## 4. Librarian-style evidence block (illustrative)

```text
Question:    "should a lower minimum-cells cutoff rescue the thin comparisons?"   [human-stated, as asked]
Searched:    repository only (decisions, findings, a precedent script). No external service.
Found:       .living/decisions.md entry on the duplicate policy [agent-derived: .living/decisions.md]
             precedent script using min_cells = 20      [agent-derived: scripts/precedent.R]
Alternatives: keep 20 (assumes group size matters more than coverage; fails when groups drop below 3 per side);
             lower to 5 (assumes noise is tolerable; fails: still leaves failing contrasts and is very noisy)
Not found:   no paper library in the project for this choice; none cited.
Disagreement: none among the sources read.
Yours to decide: the cutoff. Parked until a question needs the thin comparisons.
```

## 5. What the human decided

Approve the docs-only correction (keep the random effect; list the failing contrasts as not claimable; keep the cutoff).

## 6. Without the tool

The fit would have been built on the false sentence and its donor variance read as if each donor appeared once.

Basis: 1 plan of 45 in project B; wrong-assumption items in that plan: 6.
