---
name: questionnaire
disable-model-invocation: true
description: Turn questions only someone else can answer (a PI, core facility or collaborator) into a Markdown questionnaire to send them.
---

# Mycelium Extra: Questionnaire

Some questions in a plan belong to a person who is not in the session: the PI owns the hypothesis, the core facility knows the batch layout, the collaborator knows which samples were excluded and why. Write those questions into one Markdown file the user sends to that person, or fills in with them in a meeting.

Adapted from Matt Pocock's `to-questionnaire` (MIT).

## 1. Ask about the send, not the subject

The user cannot answer the subject; that is why a questionnaire exists. They can always answer two things about the send. Ask each in one exchange.

1. **Who gets it?** Role, expertise and relation to the user (PI, core facility, wet-lab colleague, clinician, data manager). This sets the tone and how much context the file must carry. Done when you know what the recipient knows that the user does not.
2. **What must come back?** The decisions or facts the user needs from this person. Take them from the user's message or from the grill brief's Parked items marked `answer from <role>`. Done when you have a concrete list of what the user must be able to decide afterwards.

Do not interview the user about the subject itself.

## 2. Write the file

Write `plans/questionnaire-<slug>.md` inside the analysis folder when the user names one, otherwise `questionnaire-<slug>.md` at the repository root. The slug comes from the topic. If the file exists, read it and ask before replacing it. Report the path.

Every item from step 1.2 gets at least one question. Write nothing else: no `.living/`, manifest, todo or plan edits.

Use this structure. Order questions most important first, because an async reply may come only once. Group them under `##` theme headings when there are more than about five.

```markdown
# <Questionnaire title>

**Purpose:** why this questionnaire exists and the decision that depends on it.
**From:** <user>  **To:** <recipient>  **How your answers will be used:** <where they go, for example the analysis plan for analysis/<name>>

## Context

One paragraph for a reader who was not in the planning session: the question, the data, and what is already known. Enough to answer well, not a page.

## How to answer

Deadline and rough effort. Partial answers and "I don't know" are useful: mark anything you are unsure of rather than skipping it.

## <Theme>

### <One question, one idea>

_Why this matters: <only where the question could be misread or invite a throwaway answer>._

>

## Anything else?

Anything we did not ask that we should know?
```

Each question asks one thing, never two joined by "and". Ask for the fact, not for agreement with a guess: "Which samples share a sequencing run?" rather than "Were all samples sequenced together?". Typical gaps in an analysis plan:

- **Design:** the replication unit, pairing, and which samples are technical repeats.
- **Batch:** processing or sequencing dates and runs per sample, and whether batch is confounded with condition.
- **Exclusions:** samples removed before the data arrived, and why.
- **Measurement:** assay units, normalisation done upstream, and detection limits.
- **Intent:** the contrast that matters most, and the result that would change the next experiment.

## 3. After the answers come back

When the user pastes or saves the answers, read them. Each answer that settles a Parked question goes back to `/mycelium-extra:grill` as evidence tagged `[human-stated: <role>]`, for example `[human-stated: core facility]`, quoting the recipient's role. Never use the bare `[human-stated]` tag for a recipient: it is reserved for the user's own words. A filled questionnaire approves nothing.
