---
name: harden
disable-model-invocation: true
description: Ship one Mycelium learning's structural_mitigation_candidate as a real test, then mark the learning structural.
---

# Mycelium Extra: Harden

Turn a learning the project keeps having to remember into a test that remembers it. Mycelium counts a learning as `structural` only once its check has shipped; until then it stays `ambient-awareness`, the weakest kind. This skill ships the check. One learning per run.

## 1. Find a candidate

- Requires `.living/learnings.md`. Without it, say so and stop.
- `rg -n 'structural_mitigation_candidate' .living/learnings.md`, then read each matching entry (it starts at the `### [YYYY-MM-DD]` heading above the match).
- Keep entries whose `mitigation_type` is not `structural` and whose candidate names a concrete check: a function, file, column, or assertion. Skip the template placeholder and vague candidates ("be careful with X").
- A candidate that places its check in analysis code ("In `analysis/.../x.py`, assert ...") still qualifies when the check reads a file a test can read too: show it with "(check moves to a test)". If it checks a value only the running script holds, skip it and say why: it belongs to a grill plan and a re-run.
- Show at most five, newest first: date, title, the candidate in one line. The user picks one. If none qualifies, say so and stop.

## The correct ladder: fix at the highest level that works

A repeated mistake is one that has happened twice. Before section 2, ask which level removes it, and take the highest that works. Say why each higher level did not work. Idea from pstack (MIT, cursor/plugins): correct.

1. **Structure.** One owner for each piece of state, one supported way for each task, internals hidden so the wrong import fails, one source for any hand-synced list, old paths deleted so no agent copies them.
2. **Types.** Make the bad state impossible to write (a class, an enum, a checked constructor).
3. **A lint whose message names the fix.** The error names the file, function or type to use instead. Where the bad pattern is already common, fail only when a change adds more.
4. **A test.** Sections 2 to 4 below. It tests behaviour through a public name, and it must fail on the real past mistake.
5. **Docs or an agent rule, last.** Only for judgment calls: nothing fails when a reader skips them.

Levels 1 to 3 change package or repository code. Make that change only when the user approves it, and never in analysis code, which belongs to a grill plan and a re-run. When the choice is level 4, go on with sections 2 to 4.

For a level 1 to 3 fix, show the user the change (the files and the diff) and the reproduction of the past mistake, and make the change only after a yes. Then prove it on the reproduction: before the change the mistake goes through, and after it the wrong import fails, the bad state cannot be written, or the lint fires with its message. Show both results. If the mistake still goes through after the change, revert the change, stop, and leave the entry `ambient-awareness`. Then go to section 4, and record the changed file (or the lint rule) in place of a test path.

The learning becomes `structural` only for a level 1 to 4 fix that ships and is proved on the reproduction (section 3 for a test); a docs-only fix leaves it `ambient-awareness`.

## 2. Place the test

- Follow the repository's test setup: `pytest.ini`, `[tool.pytest]` in `pyproject.toml`, `tests/testthat/`, or existing `test_*.py` files and how they are run (check `README`, `AGENTS.md`, `CLAUDE.md`).
- With no setup, create `tests/test_<slug>.py` (stdlib `assert`, runnable with `python3`) or `tests/testthat/test-<slug>.R`.
- Never place the test under the approval gate's gated paths (`gated_paths` in `.mycelium-extra/gate.json`; default `analysis/**`, `nbs/**`), and never edit analysis code. A check inside analysis code changes what ran, so it belongs to a grill plan and a re-run, not to this skill. For a candidate placed in analysis code, write the same assertion in the test, reading the file the analysis reads or writes, and leave the script as it is.
- Name the test after the learning and cite it in a one-line comment: `# Guards learning "<title>" (.living/learnings.md, <date>).`

## 3. Prove it guards something

Do not write the test file yet. Show the user the proposed test (path and body) and the reproduction it will use, and ask whether that reproduction really is the problem the learning describes: you chose it, and a wrong reproduction makes a worthless test. Write the file only after the user says yes; if they correct the reproduction, revise and ask again.

Then run the test twice and show both results:

1. Against a minimal inline reproduction of the original problem (a small fixture built in the test, or a parameter that recreates the bad input). It must **fail**.
2. Against the current code or data. It must **pass**.

If it cannot be made to fail on the reproduction, it guards nothing: delete the test file you wrote, stop, and leave the entry `ambient-awareness`. If it fails on the current code, the problem is live: report it, and do not mark the learning structural.

For a data learning (a column, a sample count, a file format), the test may read the repository's data file. If that file is large or git-ignored, say the test only runs where the data exists.

## 4. Record, after the user confirms

Show the test path (or the changed files), both runs, and the exact edit, then ask. After the user confirms, edit only that entry:

- `**mitigation_type**: structural`
- Append to the `**structural_mitigation_candidate**:` line: ` Shipped: \`<test path, or the changed file or lint rule for a level 1 to 3 fix>\` (YYYY-MM-DD).`

Change no other field or entry. Do not commit. This confirmation is the agent's instruction, not a gate rule: nothing enforces it, unless `.mycelium-extra/gate.json` sets `confirm_writes` to true. Then, before writing the test file (section 3), run `<skill-dir>/../../hooks/mxpy <skill-dir>/../../hooks/confirm_write.py prepare --kind harden --target <test path or changed file> --target .living/learnings.md`, show the user the `confirm write <id>` line, and write either file only after they type it: the gate denies both before. If Mycelium's Stop hook asks for `.living/` updates afterwards, follow it. End with one line: the learning, the test path (or the changed file), and how to run it.
