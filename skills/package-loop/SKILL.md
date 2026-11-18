---
name: package-loop
disable-model-invocation: true
description: "Develop a bioinformatics package as a loop of small units, each ending on a green check. Use when an R or Python package changes over several steps; not for one planned run or for analysis scripts."
---

# Mycelium Extra: Package loop

`iterate` with the package's own check as the readout. Each node is one unit of work that ends green before the next starts. Nodes, freezing, the repair cap and the stop rule come from `iterate`; read its `SKILL.md` first.

Ideas from pstack (MIT, cursor/plugins; sequence-verifiable-units, test-behavior-not-implementation, blast-radius). No pstack text or code is copied.

## 1. Fix the plan rows

Put each of these in a `grill` plan as its own `user` row and wait for approval. Never fill one in yourself. Plan rows for the package itself (seams, failing test first, independent expected value) follow `skills/grill/references/package-plans.md`.

- The run command. See `references/check-rows.md` for the forms in use.
- The readout: the line `check_summary.py` prints, and which part decides better, same or worse.
- Which NOTEs count as failures. A NOTE is a package-specific call, so list the ones a baseline check shows and ask which fail.
- The repair cap and the stop rule, as in `iterate`.

Write the root node with `tree.py add` as `iterate` does. Done when `tree.py status` shows no `not set`.

## 2. One verifiable unit per node

A node changes one behaviour through one seam, with the test that fails first and an expected value that does not come from the code under test. Start from a green baseline: run the check on the starting commit and record it as the root's run. Do not start the next node until this one ends green or is answered `worse` and dropped. Idea from pstack (MIT, cursor/plugins): sequence verifiable units.

Write the test through the seam (an exported function, a public name), never through internals. A test that still passes when the behaviour breaks, or fails when only internals change, is fixed or deleted. Idea from pstack (MIT, cursor/plugins): test behavior, not implementation. The red-green loop is `/mattpocock-skills:tdd` where installed.

## 3. Run the check and read one line

Run the approved command with its output in a log, and read its exit status in the same Bash call, because the shell does not keep it for the next call:

```bash
<cmd> > checks/<slug>.log 2>&1; echo "check exit: $?"
```

Do not pipe the command to `tee`. A pipe returns `tee`'s status, so a crashed check reads as exit 0. To watch the output while it runs, use `set -o pipefail; <cmd> 2>&1 | tee checks/<slug>.log; echo "check exit: ${PIPESTATUS[0]}"`.

Then read the log:

```bash
<skill-dir>/../../hooks/mxpy - --notes checks/<slug>.log < <skill-dir>/scripts/check_summary.py
```

It prints one line, for example `rcheck: 0 ERROR, 1 WARNING, 2 NOTE`, `testthat: FAIL 0, WARN 0, SKIP 0, PASS 12` or `pytest: 2 failed, 10 passed in 1.23s`. `--notes` also lists the NOTE headings of the counted check run, so you can match them to the approved failing-NOTE row. The script never decides which NOTE fails.

Record the run with the exit status you printed. The check commands are not gated analysis runs, so the gate writes no receipt for them and there is no `--receipt` line to cite. Use `--exit`:

```bash
tree.py run <slug> --exit <check exit> --readout-value "<line>" --log checks/<slug>.log
```

Cite `--receipt <N>` only when the gate did write a receipt line for that exact command, and the command was not piped.

Exit codes of `check_summary.py`: 0 parsed, 2 no summary found. With `--exit-code` it exits 1 for an ERROR, a failed or errored test, no tests (pytest `no tests ran` or every test deselected, testthat with `PASS 0`), a ruff finding, or an R CMD check log with no `Status:` line (a check cut short). It exits 1 for no tests on purpose: a run that tested nothing is not green.

When the summary exits 2 and the check exit is not 0, the run failed: run `tree.py repair`. When the check exited 0 but no summary was found, `tree.py repair` refuses the node because the run counts as `ok`. Do not answer the node. Fix the command or the log capture, then record a new run with `tree.py run`, and ask the user if the second run also gives no summary.

Quote the lines of the log that hold the counts. Every conclusion cites an inspected figure (`/mycelium-extra:plot-first`) or is written `unsupported: no inspected figure`.

## 4. Before a release: blast radius

For each changed export, list its callers: `rg -n '\bname\(' .` plus `revdepcheck` where installed (R) or a search of dependent repos you own. Then find the one fact the change is safe because of, and prove it by running code: a script that calls the real function and fails loud if you are wrong. State how far each fact got: said, pointed at a line, walked step by step, or ran. Idea from pstack (MIT, cursor/plugins): blast radius.

A new impactful choice that surfaces (a changed default, a dropped NOTE, a new dependency) is not a node. Stop and ask.

## 5. Analyses that load the package

When an analysis loads this working copy (`pip install -e`, `devtools::load_all()`), keep its path in `gate.json`'s `dev_packages`. Each analysis receipt then records the package commit and whether it had uncommitted changes.

## Boundaries

- Writes no plan row, approves nothing, and never edits `tree.jsonl` by hand.
- Writes tests and package code only inside the package, never under the gate's gated paths.
- `check_summary.py` reads check output; it runs no check.
