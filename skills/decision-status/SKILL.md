---
name: decision-status
description: Work out which past decision still binds a task when a Mycelium project's `.living/decisions.md` holds several entries on the same choice (a method, cohort, contrast, threshold, or tool that was confirmed, held, shelved, rejected, or revisited over time). Lists only the entries the task touches, oldest first, applies explicit supersession, asks the user about genuinely contested threads (at most three per session), and after the user confirms, appends a resolution entry so the question is not asked again. Use when the user invokes mycelium-extra decision-status, asks which decision is current or binding, or when grill or planning finds two or more decision entries on a choice the task depends on. Not for recording a brand-new decision (use Mycelium's normal logging) or auditing a whole decision log.
---

# Mycelium Extra: Decision status

Settle which past decision binds the current task. Retrieve only the entries the task touches, resolve what the log itself settles, ask the user about the rest, and record the user's answer as a new entry. The newest entry never wins by recency alone.

## 1. Retrieve the touched thread

- Requires `.living/decisions.md`. Without it, say so and stop.
- Name the decision points the task depends on (for example batch correction, the DE model, a cohort filter). For each, pick tags from `.living/INDEX.md` or the entries' `**Tags**:` lines, and plain terms for the method names. About half the entries in real logs carry no tags, so always pass terms as well.
- Run the parser beside this file, from stdin so Mycelium's hooks stay closed:

  ```bash
  python3 - --living-dir .living --tag <tag> --term '<regex>' < <skill-dir>/scripts/decision_threads.py
  ```

  `--tag` and `--term` repeat; `--include-learnings` adds `learnings.md`; `--json` gives the raw records. Running the script by path opens Mycelium's post-action cycle, so never do that. If `python3` is missing or fails, fall back to `rg -n '^#{2,3} .*<term>' .living/decisions.md` and read the entries directly.
- The output is extraction only. `status`, `supersedes`, `scope`, and `revisit` are raw field text (both `**Field**:` and `**Field:**` are read); `hints` are status words found in the heading. None of them is a verdict.
- Read the body of every listed entry that could bind the task before resolving anything. A heading word such as "held" may be qualified in the body.

## 2. Resolve by rule

For each decision point, apply the first rule that fits:

1. **Explicit supersession.** An entry that names an earlier one in a `**Supersedes**:` line, or in its heading or body text ("supersedes the entry above", "ADDENDUM to ..."), replaces it for the stated scope. Follow the chain to its end. Only replace, supersede, overturn, or reverse wording counts. An addendum amends: it binds together with the original and overrides only the part it changes.
2. **Scope match.** Entries that answer different questions (different datasets, stages, or estimands) do not conflict. The entry whose scope matches the task binds. Existing entries often use `**Scope**:` for other things (for example what a fix covered), so read it; trust it as a binding scope only on entries with a `**Resolved-by**:` line.
3. **Contested.** Otherwise the thread is contested. Status words are not interchangeable: "held", "shelved", "rejected for cause", and "superseded" leave different options open, and a later "shelved" does not undo an earlier "confirmed" on a different method.

An entry with no status is `unknown`, not `current`. You may say an entry looks superseded and why, but never treat it as demoted until the log or the user says so. Positional IDs (`D-143`, `L-42`) in headings are not stable; cite entries by date and exact heading title with the line number.

## 3. Ask only what is contested

- Ask only about a decision point the task touches that has two or more entries unresolved by rules 1–2, or where a premise named in an entry has changed (for example new data, or a `**Revisit when**:` condition that now holds).
- One question per message, most consequential first. Quote the competing entries by date, title, and line, say what each implies for the task, and recommend one.
- Cap: **three questions per session**. Past the cap, carry each remaining contested point forward as `contested` with your recommended reading, and name it in the answer; do not quietly pick one.

## 4. Record the user's answer

Once the user explicitly confirms a resolution in the conversation, append one new entry to the end of `.living/decisions.md`. Never edit, reorder, renumber, or delete an existing entry. Match the file's heading level (`###` unless the file uses `##`):

```markdown
### [YYYY-MM-DD] Resolution: <decision point>

**Context**: <the task that raised it; the entries in conflict>
**Decision**: <what binds now, in the user's words>
**Status**: active
**Supersedes**: [YYYY-MM-DD] <exact heading title>; ...
**Scope**: <what this covers, and what it does not>
**Revisit when**: <condition, or "user reopens it">
**Resolved-by**: user, YYYY-MM-DD
**Tags**: <the thread's tags, so the next lookup finds this entry>
```

Cite superseded entries by date and exact heading title only; line numbers shift when entries are added. List in `Supersedes` only entries the user agreed are replaced. An entry that stays valid for a narrower scope goes in `Scope`, not `Supersedes`. In a Mycelium repository, this edit is an ordinary `.living/` update; if a Mycelium hook then asks for post-action updates, follow it. Write nothing if the user did not confirm, and do not record inferred resolutions.

## 5. Report

End with a short table, one row per touched decision point: the point, the binding entry (date, title, line) or `contested`, the rule that settled it (`supersedes`, `scope`, `user`, or `contested`), and what it means for the task. Below it, list any entry written, and any contested point carried forward. When called from grill, this table is `repo` or `user` evidence for the plan; a `contested` point becomes one of grill's questions or a `DECISION_REQUIRED`.
