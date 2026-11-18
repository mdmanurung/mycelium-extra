# Loop rules and the values to offer

The four plan rows are the user's. Show each as a question with no recommended value, and list a sourced option only when it has a source. Do not write any value into the tree until the user approves the row.

## The rows

| Row | What it fixes | Sourced option to show |
|---|---|---|
| Run command | The one command every node runs. Nodes never change it. | None. It is the analysis's own command. |
| Readout | The metric or log line that decides better, same or worse, and where it is read. | None. It depends on the question. |
| Repair cap | How many in-place repairs a failed node gets before you ask. | 2: Idea from OpenResearch (MIT, alphaXiv). |
| Stop rule | When the loop ends by itself. `tree.py` counts answered nodes in a row, newest last, that were not `better`; it stops when the count reaches N. | 3: Idea from OpenResearch (MIT, alphaXiv), which stops after three failed or regressed runs. |

State the counting rule when you show the stop row, so the user knows `same` counts with `worse`. A stop rule of another shape (a metric target, a time budget) is a user decision too. Record the user's approved words in `--stop-rule` and leave out `--stop-after`: the words are the plan row. `tree.py` cannot judge such a rule, so `stop-check` exits 3 and tells you to ask the user. Run `tree.py stop --reason rule` only after the user says the rule is met.

## What the tree keeps

`plans/tree.jsonl` holds eight event kinds, appended and never edited: `add`, `plan`, `run`, `answer`, `repair`, `stop`, and, in method mode, `evaluator` and `arena`. A run cites a line of `.mycelium-extra/receipts.jsonl`, so the exit status comes from the gate's receipt and not from a second store. The run event also records the status `tree.py` saw when it ran (`ok`, `failed` or `unknown`), so a clone without the receipts file replays the same states. A receipt with no integer exit status (a background or compound command) gives `unknown`: the run counts as neither ok nor failed, `repair` is refused, and you ask the user how it ended. A node is `frozen` once an `answer` event exists. Replaying the file gives every view.

## Reading results

- The log names the variant and its config. A log that does not is not evidence for that node.
- Quote the lines that hold the readout. Do not paraphrase a number.
- A node that exited 0 but printed no readout has no result. Record the run with no `--readout-value`, say why, and do not answer the node.
- Idea from OpenResearch (MIT, alphaXiv): one line per node at the end of each turn that ran nodes.
