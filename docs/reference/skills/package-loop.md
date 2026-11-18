# package-loop

Develops a bioinformatics package as a loop of small units. Each unit is a node of an `iterate` tree and ends on a green check before the next starts. Ideas from pstack (MIT, cursor/plugins).

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`). Read [iterate](iterate.md) first: nodes, freezing, the repair cap, the stop rule and the `loops` guard work the same way.

The check summary is a stdlib script, run from stdin. It reads check output from files named as arguments:

```bash
<skill-dir>/../../hooks/mxpy - [--kind auto|rcheck|testthat|pytest|ruff] [--notes] [--exit-code] LOG... < <skill-dir>/scripts/check_summary.py
```

## Plan rows are yours

The run command (`devtools::check()`, `R CMD check`, `pytest`, `ruff`), the readout, which NOTEs count as failures, the repair cap and the stop rule are impactful choices. Each is a `user` row in a `grill` plan. There is no default. The package's own rows (seam, failing test first, independent expected value) follow the grill reference on package plans.

## What it does

- Starts from a green baseline, then makes one node per verifiable unit. The test goes through the public seam, not internals, and its expected value does not come from the code under test.
- Runs the approved check into a log and reads its exit status in the same call (no `| tee`, which hides it). `check_summary.py` prints one line, such as `rcheck: 0 ERROR, 1 WARNING, 2 NOTE` or `pytest: 2 failed, 10 passed in 1.23s`. That line goes to `tree.py run --exit <status> --readout-value`. The check commands are not gated runs, so the gate writes no receipt for them.
- Before a release, lists the callers of each changed export (a search, plus `revdepcheck` where installed) and proves the one fact the change depends on by running code.
- Keeps `dev_packages` in `gate.json`, so analysis receipts record the working copy's commit.

## check_summary.py

| Input | Line |
|---|---|
| `R CMD check` or `devtools::check()` output | `rcheck: E ERROR, W WARNING, N NOTE`, from the `Status:` line or the devtools summary line, else counted from the `... NOTE` lines |
| The `testthat` line `[ FAIL n | WARN n | SKIP n | PASS n ]` | `testthat: FAIL 1, WARN 0, SKIP 0, PASS 7` |
| The pytest summary line, with or without `-q`, in the old `seconds` form too | `pytest: 2 failed, 10 passed, 1 skipped in 1.23s`, or `pytest: no tests ran` |
| The `ruff check` summary | `ruff: 3 errors` or `ruff: clean` |

Several kinds in one input join with `; `. `--notes` adds one `NOTE: <heading>` line per NOTE. `--exit-code` exits 1 for an ERROR, a failed or errored test, no tests (pytest `no tests ran` or every test deselected, testthat with `PASS 0`), a ruff finding, or an `R CMD check` log with no `Status:` line; a WARNING or NOTE never sets it, because which of those fail is your plan row. With several check runs in one input, the last summary and the NOTE headings of that run count. `ruff check --fix` counts the findings that remain. Exit 2 means no summary was found: with a failed check run, repair it; with a check that exited 0, fix the command or the log capture and record a new run, because `tree.py repair` refuses a run that exited 0. It reads output only and runs nothing.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| The tree rules (frozen nodes, repair cap, missing plan rows) | Enforced: `tree.py` |
| The summary line and its exit codes | Enforced: the script (tested on saved outputs) |
| One unit per node, test through the seam, blast-radius step | The agent's instruction |
| The plan rows are yours | The agent's instruction; the plan itself is the gate's |

See [iterate](iterate.md), [harden](harden.md) for the correct ladder and [grill](grill.md) for plans.
