# questionnaire

Writes the questions only someone outside the session can answer (a PI, core facility or collaborator) into one Markdown file you send them or fill in together. Adapted from Matt Pocock's `to-questionnaire` (MIT).

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`).

`/mycelium-extra:questionnaire [topic or analysis folder]` (Codex: `$mycelium-extra:questionnaire`). No script and no flags.

## What it does

1. Asks two things about the send, one exchange each: who gets the file (role, expertise, relation to you), and what must come back (the decisions or facts you need). It takes the second list from your message or from a grill brief's Parked items marked `answer from <role>`. It does not interview you about the subject.
2. Writes `<analysis>/plans/questionnaire-<slug>.md`, or `questionnaire-<slug>.md` at the repository root when no analysis is named. Sections: Purpose, From/To/How your answers will be used, Context, How to answer, one heading per theme with one question each and an answer stub, and Anything else. Questions go most important first, one idea each.
3. When the answers come back, it reads them; each answer that settles a Parked question goes back to `/mycelium-extra:grill` as `[human-stated]` evidence naming the recipient's role.

## Reads and writes

Reads the conversation and the latest grill brief. Writes only the questionnaire file; if it exists, the agent reads it and asks before replacing it. It never writes `.living/`, manifests, `todo/` or plans.

## Default on or off

On when invoked. Grill names it in a brief's Parked section when a question is marked `answer from <role>`.

## Enforced versus the agent's instruction

Nothing here is enforced. The two-question limit, the file location and asking before replacing a file are the agent's instructions. A filled questionnaire approves nothing: only a typed `approve plan <hash>` does.

## Related

[grill](grill.md) parks third-party questions; [data-contract-check](data-contract-check.md) shows which design facts the tables cannot answer.
