# Harden against repeated mistakes

`harden` turns one Mycelium learning your project keeps having to remember into a test that remembers it. One learning per run. It needs `.living/learnings.md`.

## What you control here

- **Your typed word:** which learning to harden, a yes that the reproduction really is the problem, and a yes before the entry is edited. Those confirmations are the agent's instructions; nothing enforces them.
- **Shown to you:** up to five candidates, the proposed test and its reproduction before the file is written, and both test runs.
- **To say no:** answer no at either confirmation. If the test cannot be made to fail on the reproduction, the file is deleted and the learning stays `ambient-awareness`.

## Steps

1. Invoke it:

   ```text
   /mycelium-extra:harden
   ```

2. It lists learnings that are not yet `structural` and whose `structural_mitigation_candidate` names a concrete check (a function, file, column or assertion). Pick one.
3. It proposes the test, placed in the repository's own test setup and never under the gated paths. It shows the test and its minimal reproduction and asks whether that reproduction is the real problem.
4. After your yes it writes the test and runs it twice: against the reproduction (must fail) and against the current code (must pass). A failure on current code means the problem is live, and the learning is not marked.
5. After your yes it edits only that entry: `mitigation_type` becomes `structural` and a line `Shipped: <test path> (date)` is appended. It does not commit and never edits analysis code.

## Worked example

No captured `harden` session exists, so no output is shown. The entry edit is the one fixed output, from `skills/harden/SKILL.md`:

```text
**mitigation_type**: structural
**structural_mitigation_candidate**: <the candidate> Shipped: `<test path>` (YYYY-MM-DD).
```

## What this does not guarantee

A test guards only what its reproduction captures. A wrong reproduction makes a worthless test, which is why you confirm it. A passing test does not show the analysis is right, and the gate does not check that any test ran. A check that lives in analysis code, or reads a value only the running script holds, belongs to a grill plan and a re-run, not here. See [what this does not guarantee](../concepts/not-guaranteed.md).

## Reference

[harden](../reference/skills/harden.md) · [decision-status](../reference/skills/decision-status.md) · next: [with Mycelium or in a plain repo](with-mycelium-or-plain-repo.md)
