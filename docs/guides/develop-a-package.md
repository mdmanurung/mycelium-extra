# Develop a package

Package work needs fewer approvals than a reportable analysis, but the same care about tests and versions. Switch the gate off where approvals only slow you down, let grill plan the change test-first, and record which package commit an analysis used.

## What you control here

- **Your typed word:** `gate off` and `gate on` for the repository; `/goal <condition>` and `/goal clear` for one Claude Code session. The agent cannot type them for you.
- **Shown to you:** one line when the gate switches off or on, or when a `/goal` pause starts or ends.
- **To say no:** type `gate on`. It also ends this session's `/goal` pause.

## Work without approvals

```text
gate off                                     # this repository, until gate on
/goal the tests in tests/testthat pass       # this session, until the goal is met or fails
```

`gate off` lasts for the repository, across sessions. While it holds, runs need no approved plan, no plans are pinned and no receipts are written. Approvals you gave before are kept for when you switch it back on.

`/goal` pauses the gate for one session only. The pause ends when Claude Code reports the goal met or impossible, which the gate sees at your next prompt, or on `/goal clear` or `gate on`. Other sessions keep the gate.

Under `gate off`, grill shows its plan and goes on to execute it. With the gate on, grill waits for `approve` even under `/goal`, so a goal that needs a grill plan stalls until you approve it.

Mycelium's own hooks are not part of this. In a Mycelium repository its Stop check can still ask you to update `.living/` after real work. Disable the Mycelium plugin in the package repository if you do not want that.

## Plan a change test-first

```text
/mycelium-extra:grill <the change you want>
```

When the repository has a `DESCRIPTION` or a `pyproject.toml` with a package folder, grill follows [package plans](https://github.com/mdmanurung/mycelium-extra/blob/main/skills/grill/references/package-plans.md):

1. Each row names its seam: the exported function a test calls.
2. Each row's check is a test that fails before the change. The red-green loop is Pocock's `/mattpocock-skills:tdd` where it is installed, otherwise `devtools::test()` or `pytest`.
3. Each expected value comes from a hand-worked literal, a published example, or a reference tool's output saved as a fixture with its version. It never comes from the code under test.
4. A checklist covers the replication unit, shuffled order, missing levels, edge sizes, sparse versus dense input, and seeds.

Grill also reads `GLOSSARY.md` and flags an overloaded word (sample, replicate, batch). The brief lists settled terms under Terms to record, for `GLOSSARY.md`. Outside a Mycelium repository, a decision that is hard to reverse, surprising, and a real trade-off becomes an ADR under `docs/adr/`.

## Record which package version an analysis used

When an analysis repository loads the package from a working copy, name the copy in its `gate.json`:

```json
{"dev_packages": ["../mypkg"]}
```

Each run receipt then records the package's commit and whether it had uncommitted changes. `verify report` lists them under Packages in development. Keep the gate on in the analysis repository: a switched-off gate writes no receipts.

## Reference

[gate](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/gate.md#typed-commands) · [gate.json](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/gate-json.md) · [grill](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/grill.md) · [what is not guaranteed](../concepts/not-guaranteed.md)
