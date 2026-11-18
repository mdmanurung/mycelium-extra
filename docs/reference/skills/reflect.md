# reflect

Looks back over one stretch of work and proposes learnings and skill edits. You accept, change or reject each one. Accepted learnings are appended to `.living/learnings.md` in Mycelium's entry format. Idea from pstack `reflect` (MIT, cursor/plugins).

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`). It has no script and no hook.

## Steps

| Step | Done when |
|---|---|
| Read | The agent has read the conversation, the decision log (`logs/decisions.tsv`), the experiment tree summary and the existing learnings, and can name the stretch in one line. |
| Filter | Each finding holds for six months, would change what a future agent does, and points at something the stretch used. Findings about your own data and defaults for impactful choices are dropped or recorded as observations. |
| Present | You have seen Accepted, Rejected and Backlog, and answered each item. A skill edit is shown as a diff and nothing more. |
| Record | Accepted learnings are appended to `.living/learnings.md`. |

## Writing to `.living/`

The skill writes only `.living/learnings.md`, and only after you confirm. It runs `hooks/confirm_write.py prepare --kind reflect` first. With `confirm_writes` on in `gate.json`, the gate denies the write until you type `confirm write <id>`. With it off, the confirmation is the agent's instruction.

Entries follow the template in the installed Mycelium plugin (`skills/core/templates/learning-entry.md`) and carry `mitigation_type: ambient-awareness`. A learning becomes `structural` only when [harden](harden.md) ships its test. The skill never writes conventions. When three or more entries share a theme, it offers Mycelium's `crystallize` mode and runs it only if you say yes.

## Skill edits

The skill never edits a skill. It shows the diff. You apply it, or pass it to [skill-style](skill-style.md). It never touches `plugins/cache/`.

## Default on or off

Off until you type it. It adds no hook, no notice and no gate rule.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| No write to `.living/learnings.md` before you type `confirm write <id>` | Enforced when `confirm_writes` is on, and only if the skill ran `prepare` |
| Filtering, the Accepted, Rejected and Backlog split, the entry format | The agent's instruction |
| Not editing skills, plans or code | The agent's instruction |
