---
name: skill-style
disable-model-invocation: true
description: Write or audit a document an agent reads (skill, AGENTS.md, CLAUDE.md, reference, hook notice); includes a read-only audit of the plugin's skills.
---

# Mycelium Extra: Skill style

Adapted from Matt Pocock's writing-for-agents skill (MIT). Use it when you write or edit a skill, `AGENTS.md`, `CLAUDE.md`, a reference file or a hook notice. A document steers an agent the same way each run only when its pointers, steps and words are tight.

## Audit first

Run it before you edit; it is read-only and always exits 0 (2 on a bad root):

```bash
<skill-dir>/../../hooks/mxpy - --root <repo> < <skill-dir>/scripts/skill_audit.py
```

It prints one table row per skill and then JSON. Done when you can name the three worst rows. Read each flag as a prompt to look, not a verdict: `steps?` and duplicate sentences are heuristics.

## Writing rules

Apply each rule to a draft. A rule is done when you can point at the line that satisfies it.

1. **Pointer.** A description or an `AGENTS.md` line that names other material is a context pointer. Put the leading word first, give one trigger per branch, and drop identity the body already says. Done when no two triggers name the same case.
2. **Two loads.** Always-loaded text costs context every turn. A document only you remember costs your memory. Done when each new document has a chosen load.
3. **Hierarchy.** Steps come first, in order. Reference the agent consults on demand sits below. Reference only some branches need goes in `references/` behind a pointer that states its trigger. Done when every step is in the file and every `references/` file has a pointer from a step, or from another skill that reads it, or is named by a test as developer-only.
4. **Completion.** End each step on a condition the agent can check, and make it exhaustive: "every modified model accounted for", not "produce a change list". Done when a reader can tell finished from unfinished.
5. **Leading words.** Replace a repeated phrase with one existing, pretrained word and use it as a token. Define a coined word once. Done when each retired phrase is gone from the file.
6. **Positive target.** Write the behaviour to do. Keep a prohibition only as a hard guardrail, and put the positive target next to it. Done when each remaining "never" has a "do" beside it.
7. **Prune.** Keep each meaning in one place. Leave what the repository already says (a script name, a config key, `--help`) to the repository. Delete a sentence the agent obeys by default, as a whole sentence. Done when each line changes behaviour or carries a reason the environment cannot show.
8. **Length.** Keep a `SKILL.md` at about 100 lines or fewer. Move reference behind a pointer instead of trimming steps. Done when the `lines` column reads 100 or less, or you can name what each line past 100 does that a reference file cannot. The `sprawl` flag marks only the hard limit of 150.

## Invocation

Make a skill model-invoked only when the agent or another skill must reach it. Its description then loads every turn. Otherwise make it user-invoked and keep the description as a short human line. This plugin keeps descriptions to one line, at most 60 words, with a first sentence under 150 characters; `tests/test_skill_frontmatter.py` enforces that, and a user-invoked skill is flagged in both hosts. When user-invoked skills pile up, a router skill names them and says when to use each; it cannot start them.

Read [references/invocation-and-routers.md](references/invocation-and-routers.md) when you choose an invocation, split a skill or write a router.

## Contracts stay as written

Before you restyle any text, read [references/lab-contracts.md](references/lab-contracts.md). It lists the formats other code or the user's approval depends on: grill briefs, plan tables, hook-parsed lines and plain-text hook notices. Do not reword them for style; change them only with their own code and tests.

## After the edit

1. Run the audit again. Done when no flag got worse.
2. Run the skill-frontmatter test if you changed a description. Done when it passes.
3. Say which rules you applied and which flags remain. Done when the reply names each.
