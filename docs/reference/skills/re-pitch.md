# re-pitch

Rewrites the assistant's last message in short plain sentences when you lost the thread. It reads no project state and runs nothing. Adapted from Matt Pocock's wait-what skill (MIT).

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`).

```text
/mycelium-extra:re-pitch
```

## What you get

| Part | Content |
|---|---|
| Answer | One sentence on where we are. |
| Context | Two lines: the goal and the current step. |
| Content | Short sentences, about 12 words, one idea each, active voice, no idioms. |
| List | At most five items. |
| Decision | The decision or action needed, numbered `1.`. Several impactful choices or plan rows get one numbered item each. |

## Rules it follows

- It uses the terms in `analysis/<name>/GLOSSARY.md` (see [glossary](glossary.md)). Without one, it uses the analysis doc and data dictionary terms.
- It keeps numbers, units, effect direction, uncertainty and caveats. It does not weaken a claim to shorten it.
- It keeps the figure paths and `unsupported: no inspected figure` tags of the old message next to their conclusions. It adds no path. A conclusion with neither gets `no figure named in the old message`.
- It keeps the rows of a plan or card word for word and rewords only the text around them.
- It adds no finding, step or advice that the old message lacked.

## Difference from where

[where](where.md) reads files and says where the analysis stands. `re-pitch` rewrites what was just said and reads no project state.

## Reads and writes

Reads the conversation, plus the glossary, analysis doc and data dictionary to match terms. Writes nothing.

## Default on or off

Off until you type it. It never loads context on its own.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| Nothing is written | The agent's instruction: the skill has no script, but no hook blocks a write |
| Keeping caveats, figure paths and table rows | The agent's instruction |
