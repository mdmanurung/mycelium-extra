---
name: iterate
disable-model-invocation: true
description: "Run a tree of experiments on one fixed command, one git branch per node, until a stop rule you chose is met. Use for try, measure, keep-or-drop loops on an analysis; not for one planned run."
---

# Mycelium Extra: Iterate

Try a variant, measure it, keep or drop it, repeat, without losing track. Each variant is a node in a tree, kept in `plans/tree.jsonl`. Node runs go through the plan gate. The winner is promoted through `grill` and checked by `verify`.

Ideas from OpenResearch (MIT, alphaXiv). The tree state is this plugin's own; no OpenResearch code is used.

## 1. Fix four plan rows

The run command, the readout, the repair cap and the stop rule each change what the loop concludes. Each is an impactful choice: put it in a `grill` plan as its own `user` row and wait for the user to approve. Never fill one in yourself. See `references/loop-rules.md` for the sourced values to show as options.

Then write the root node from the approved rows:

```bash
<skill-dir>/../../hooks/mxpy - --analysis analysis/<name> add <slug> --run-cmd "<cmd>" --readout "<name>" --repair-cap <N> --stop-after <N> --stop-rule "<the row's words>" < <skill-dir>/scripts/tree.py
```

Done when `tree.py status` shows all four rows and no `not set`. A missing row makes `stop-check` exit 3 and name the row to ask for.

## 2. Make a node

One node is one git branch `exp/<slug>` in the analysis repo. Make it from the parent's branch with `tree.py add <slug> --parent <parent> --question "<one line>"`. Children inherit code and the run command. Nodes differ only in committed code or config, never in env vars or flags. Done when `tree.py status` lists the node and `git branch` shows `exp/<slug>`. Idea from OpenResearch (MIT, alphaXiv): nodes as branches with one fixed command.

## 3. Run it through the gate

Commit the change on the node's branch, then run the fixed command as an explore run (`allow explore <plan hash>`). The gate pins the run command and data inputs; it does not pin node code, and `pin_scripts` re-pins an edited script with a notice. Record the run with `tree.py run <slug> --receipt <N>`, where N is the line of `.mycelium-extra/receipts.jsonl` the run wrote. With no gate, use `--exit <code>`. Done when `tree.py status` shows the run and its state, `ran` or `failed`.

## 4. Read the result from the log

Status is not a result. Open the log and check that it names the variant and its config, then quote the lines that hold the readout. Record it: `tree.py run` takes `--readout-value` and `--log`. Each turn that ran nodes ends with `tree.py summary`, one line per node, and you confirm the readout line matches the node you ran. Idea from OpenResearch (MIT, alphaXiv): read results from logs, not status.

Every conclusion cites a saved figure you opened (`/mycelium-extra:plot-first`). A conclusion with none is written `unsupported: no inspected figure`.

## 5. Answer, repair or branch

- **Answered.** The run measured the variant: `tree.py answer <slug> --outcome better|same|worse --summary "<line>" --figure <path>`. This freezes the node; do not commit on its branch again.
- **Failed.** An OOM or a bug answers nothing. Fix it in place and run again, then `tree.py repair <slug> --note "<what>"` for each fix. At the cap the command refuses: ask the user to raise the cap, drop the node or stop.
- **Fan out** only for co-equal options of one decision. Otherwise descend onto the winner and write what the parent established in the child's question. Idea from OpenResearch (MIT, alphaXiv): fan out for options, descend for the next decision.

A new impactful choice that surfaces mid-loop (a filter, a threshold, a dropped sample) is not a node. Stop and ask.

## 6. Stop and promote

Run `tree.py stop-check` before ending a turn. Exit 0: the stop rule is met or a stop is recorded. Exit 3: not yet, and the message says why. Exit 2: no tree. The user can end the loop at any time: `tree.py stop --reason user`.

Promote the winner with `grill`'s promote-explore path: a full plan, a re-run under approval, then `verify`. Explore results are not reportable.

## The loop guard

`"loops": "off" | "warn" | "block"` in `.mycelium-extra/gate.json` (default `off`) turns on `hooks/loop_guard.py`. It works with the gate on or off. It refuses (`block`) or notes (`warn`) a `git commit` on a frozen branch and the fixed command run behind an env var. At turn end it blocks once while `stop-check` exits 3. The message names the escapes: `tree.py stop --reason user`, or `"loops": "warn"`.

## Boundaries

- Writes `plans/tree.jsonl` only through `tree.py`. Never edit a line.
- Approves nothing and does not change the plan. `glossary`'s `ITERATIONS.md` is for loops with no metric; this tree is for loops with one.
