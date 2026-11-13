# skill-style

A reference and a read-only audit for the documents agents read: skills, `AGENTS.md`, `CLAUDE.md`, reference files and hook notices. Adapted from Matt Pocock's writing-for-agents skill (MIT).

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`).

`/mycelium-extra:skill-style` (Codex: `$mycelium-extra:skill-style`). The audit script:

```bash
<skill-dir>/../../hooks/mxpy - [--root DIR] [--format table|json|both] < <skill-dir>/scripts/skill_audit.py
```

`--root` is a repository (it reads `skills/*/SKILL.md`) or a skills folder. Default format is `both`: a table, then `JSON:` and the JSON report.

## What it does

1. **Audit.** For each skill the script reports description words and first-sentence length (over the plugin's caps of 60 words and 150 characters is flagged), whether the description opens on a leading word (not `This`, `A`, `The`), line count with a sprawl flag over 150 lines, negations (`never`, `don't`, `do not`, `must not`) per 100 lines, numbered steps with no completion cue, and `references/` files no pointer reaches. A pointer from another skill counts, and a file that only a test names is listed as developer-only, not as an orphan. Across skills it lists sentences of 8 or more words that appear in two or more files, and totals the description words of model-invoked skills (the always-loaded cost).
2. **Writing rules.** Eight rules, each with a checkable end: context pointers, the two loads, the information hierarchy, completion criteria, leading words, a positive target before any ban, pruning, and length.
3. **Invocation.** When to make a skill model-invoked, when to split one, and when a router helps (`references/invocation-and-routers.md`).
4. **Contracts.** Grill briefs, plan tables, exploration tags, hook-parsed lines and plain-text hook notices stay as written (`references/lab-contracts.md`).

## Reads and writes

Reads `skills/*/SKILL.md` and each skill's `references/` folder. Writes nothing. A numbered step passes on a completion cue in the step or in its section. The steps-without-a-cue and duplicate-sentence checks are heuristics: they point you at a line to read, they do not judge it. The audit exits 0 whatever it finds, and 2 when the root or its skills folder is unusable.

## Default on or off

On when invoked. It adds no description to the context.

## Enforced versus the agent's instruction

Nothing is enforced. `tests/test_skill_frontmatter.py` already enforces the description caps and the user-invoked flags in both hosts; the audit repeats the caps only as a flag. Leaving contracts unchanged is the agent's instruction: check `git diff` afterwards.

See [grill](grill.md) for the brief format. The exploration tags that hooks parse are defined in the plot-first skill.
