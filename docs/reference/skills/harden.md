# harden

Ships one Mycelium learning's `structural_mitigation_candidate` as a real test, then marks the learning `structural`. Guide: [Harden against repeats](../../guides/harden-against-repeats.md).

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`).

`/mycelium-extra:harden` (Codex: `$mycelium-extra:harden`). No script and no flags. One learning per run.

## Steps

1. **Find a candidate.** Requires `.living/learnings.md`. Greps for `structural_mitigation_candidate`; keeps entries whose `mitigation_type` is not `structural` and whose candidate names a concrete check (a function, file, column or assertion). Shows at most five, newest first; you pick one. A candidate placed in analysis code qualifies only if a test can read the same file; it is marked "(check moves to a test)".
2. **Place the test** in the repository's own test setup (`pytest.ini`, `pyproject.toml`, `tests/testthat/`, existing `test_*.py`), else `tests/test_<slug>.py` or `tests/testthat/test-<slug>.R`. Never under `gated_paths`, never edits analysis code.
3. **Prove it guards something.** It shows you the proposed test and its reproduction and asks whether that reproduction really is the problem. Only after you say yes does it write the file. It then runs the test against a minimal reproduction (must fail) and against current code (must pass). If it cannot fail on the reproduction it deletes the test file and leaves the entry `ambient-awareness`. If it fails on current code the problem is live; it reports that and does not mark the learning.
4. **Record, after you confirm.** Edits only that entry: `**mitigation_type**: structural`, and appends ` Shipped: \`<test path>\` (YYYY-MM-DD).` to the candidate line. No commit.

## Reads and writes

Reads `.living/learnings.md`, test setup files, `README`, `AGENTS.md`, `CLAUDE.md`, and a data file when the test needs one. Writes one test file in the test folder (after your yes) and one edited entry in `.living/learnings.md` (after your confirmation).

## Default on or off

On when invoked.

## Enforced versus the agent's instruction

Nothing is enforced. Asking before writing the test, asking before editing the learning, keeping out of gated paths and leaving analysis code alone are the skill's instructions to the agent. The gate does not block a test written under a gated path or an edit to `.living/`. Check the diff.
