# Method mode

Method mode is for building a method against a benchmark: a model, a score, a feature pipeline. The loop is the same tree as research mode. The metric and the evaluator are fixed first, so a candidate cannot win by moving them. Ideas from tusoskill (no licence line), rewritten here; nothing is copied.

## The plan rows

Method mode asks for five user rows: the run command, the readout, the repair cap, the iteration floor and the benchmark card. It has no stop count or stop rule; the floor is the stop. Each row is an impactful choice. Show each as a question with no recommended value.

| Row | What it fixes | Sourced option to show |
|---|---|---|
| Iteration floor | How many candidates must be answered before the loop may end by itself. | 50: Idea from tusoskill (no licence line), which sets a floor of 50 iterations. |
| Benchmark card | A file in the repository that names the metric, its direction, the splits and the protected files. | None. It belongs to the task. |
| Rubric (arena only) | 3 to 6 gradeable criteria for comparing sibling candidates, fixed before the runs. | Idea from pstack's `arena` (MIT, cursor/plugins), which derives the rubric before candidates are produced. |

The repair cap and the readout work as in `loop-rules.md`.

## The benchmark card

A plain file, for example `bench/card.md`, with these lines:

- the metric and which direction is better;
- how the data are split and which split each candidate is scored on;
- the protected files: the scorer, the split lists, the labels;
- what a candidate may change.

`tree.py` reads none of it. It hashes the card and the files you pass with `--file`, so write the protected files into the `freeze-evaluator` call yourself. A folder is hashed file by file.

## Order of work

1. Add the root with `--mode method --kind baseline --floor N --card <path>` and the other approved rows. The root is the baseline node.
2. Run `freeze-evaluator --file <scorer> --file <splits> ...`. No node runs before this. Every later run and answer checks the hashes and refuses on a mismatch.
3. Run the baseline. Add one sanity node (`--kind sanity`): a constant prediction, shuffled labels or a no-signal input. It shows that the scorer can tell a method from noise. A sanity node that scores like a real method means the evaluator leaks; stop and ask the user.
4. Add candidates. A candidate answered before the baseline and the sanity node have run is refused. Baseline and sanity answers never count toward the floor.
5. `stop-check` exits 0 once the floor is met. The user may end the loop sooner (`stop --reason user`). `stop --reason rule` is refused before the floor.

## Changing the evaluator

A hashed file is the user's. The loop guard refuses an edit through Write, Edit, MultiEdit, NotebookEdit or apply_patch (`loops: block`), and notes it under `warn`. Shell commands that write the file are not caught there; `check-evaluator` and the turn-end check catch the change by hash. To change it on purpose, ask the user, make the change, then run `freeze-evaluator --refreeze --note "<what changed, user agreed>"`. Results from before the change are not comparable: say so in the next summary.

## Arena step

Use it when siblings answer one decision and you cannot rank them by the metric alone (cost, clarity, stability).

1. Ask the user for the rubric. Record it with `plan --rubric "<criteria>"` before any sibling runs.
2. Run the siblings as normal nodes.
3. Score each sibling per criterion, not on feel, and record the pick: `arena A B C --winner B --note "<why>"`. The command refuses a rubric set after a sibling's first run, non-siblings, and a winner outside the list.

The arena records a comparison. It does not answer a node or freeze one.
