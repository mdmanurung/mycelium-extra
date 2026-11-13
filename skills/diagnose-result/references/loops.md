# Loops for analyses

A loop is one command with a stable verdict that can go red on this symptom. "It ran without error" is not a verdict.

## Kinds, roughly in order of preference

| Loop | How | Good for |
|---|---|---|
| Check on one output | A few lines that read `outputs/<stem>/` and assert the symptom: row count, unique keys, value range, a label count, no `NA` in a column | A number that is plausible but wrong |
| One step, few units | Rerun one script on 2 to 4 whole units (donors or batches) with all their cells and controls, seeded | A step that is slow or fails |
| Replay | Load a saved file from `outputs/<stem>/` and run only the step after it | Skipping slow upstream steps |
| Differential | Run old and new state, compare tables with `scripts/diff_tables.py` | A result that moved after a change |
| Bisection | Walk code states with git, or halve the data subset, until the symptom flips | A symptom that appeared between two known states |
| Permutation or null | Shuffle labels (donors, not cells) or simulate data with no effect, repeat 20 to 100 times, count how often the symptom shows | Results that are only sometimes wrong |
| Figure | Save a figure that shows the symptom, open it, write what you saw | Symptoms only visible in a plot |

## Sampling rule

Sample whole units. A per-donor step needs every cell of that donor. A per-batch threshold needs the whole batch. Random rows break both and give a different symptom.

## Differential loop, step by step

1. `logs/CHANGES.md` lists the code files that changed in each run and the step folders it rewrote. Find the first run where the symptom could have entered.
2. Get the old code with `git show <hash>:analysis/<name>/code/<file>` or a worktree. Do not check out over your working tree.
3. Copy the current output into the scratch folder first. Then run the old step into a scratch folder, not into `outputs/<stem>/` (a step overwrites its own folder).
4. Compare: `diff_tables.py OLD NEW --key <ids> --redact-keys`.
5. Change one thing between the two states at a time. If many changed, bisect.

## Tighten

Make it faster (smaller units, cached input), sharper (assert the symptom itself) and more deterministic (seed, fixed thread count where results depend on it). A 30-second flaky loop is barely better than none.

## Figure loops

The figure is the signal. Save it under the step folder with the debug prefix, open it, and note the panel and what is wrong in it. A conclusion drawn from it cites that path. If you could not open it, the conclusion is `unsupported: no inspected figure`.
