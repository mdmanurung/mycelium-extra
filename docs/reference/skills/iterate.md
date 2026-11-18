# iterate

Runs a tree of experiments on one fixed command. Each variant is a git branch `exp/<slug>`, frozen once a run answers it, repaired in place when it fails. The loop ends when a stop rule you approved is met. Ideas from OpenResearch (MIT, alphaXiv). Method mode (`--mode method`) adds a frozen evaluator for benchmark work, with ideas from tusoskill and pstack.

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`).

The tree is kept by a stdlib script, run from stdin:

```bash
<skill-dir>/../../hooks/mxpy - [--analysis DIR] <command> [options] < <skill-dir>/scripts/tree.py
```

## Plan rows are yours

The run command, the readout, the repair cap and the stop rule are impactful choices. Each is a `user` row in a `grill` plan, and the root node of the tree stores them. There is no default: when one is missing, `tree.py` says so, exits 3 and the agent asks you. OpenResearch's values (a cap of 2, stop after three failed or regressed runs) are shown as sourced options only.

## Commands

| Command | What it does |
|---|---|
| `plan` | Sets or changes plan rows on the root (`--run-cmd`, `--readout`, `--repair-cap`, `--stop-after`, `--stop-rule`) after you confirm them. A root added with rows missing gets them here. Each change is an event in the log. |
| `add SLUG` | Records a node for branch `exp/SLUG` (the agent creates the git branch). A slug must make a valid branch name. The root, with no `--parent`, takes `--run-cmd`, `--readout`, `--repair-cap`, `--stop-after`, `--stop-rule`. A child takes none of them. |
| `run SLUG` | Records a run: `--receipt N` (a line of `.mycelium-extra/receipts.jsonl`, whose exit status is used) or `--exit CODE`; also `--commit`, `--run-id`, `--readout-value`, `--log`. Refuses a frozen node. |
| `answer SLUG` | `--outcome better\|same\|worse`, `--summary`, `--figure PATH`. Freezes the node. Refuses a node with no successful run. A node with no `--figure` shows `unsupported: no inspected figure`. |
| `repair SLUG` | Counts one in-place repair of a failed node. Refuses at the cap (0 means no repairs), when no cap is recorded, and while the node has not run since its last repair. |
| `stop --reason user\|blocker\|rule` | Records that the loop ended. |
| `status`, `summary`, `frozen` | Read the replay: nodes with state, one line per node, the frozen branches. `status --json` for raw output. |
| `freeze-evaluator`, `check-evaluator`, `arena` | Method mode only. See the next section. |
| `stop-check` | Exit 0: the stop rule is met or a stop is recorded. Exit 3: not yet, or a plan row (run command, readout, repair cap, stop rule) is missing. A node added after a recorded stop ends the stop. Exit 2: no tree, or a line that is not an event. |

The stop rule counts the answered nodes in a row, newest last, that were not `better`. It is met when the count reaches the number you set. `same` counts with `worse`.

## Method mode

Add the root with `--mode method` to build a method against a benchmark. Ideas from tusoskill (no licence line), rewritten with no copied code or text, and from pstack's `arena` (MIT, cursor/plugins). The guide is `skills/iterate/references/method-mode.md`.

Method mode has five user rows: the run command, the readout, the repair cap, the **iteration floor** and the **benchmark card**. Each has no default. tusoskill's floor of 50 is shown as one sourced option. The stop count and stop rule do not apply; the loop stops at the floor.

| Command | What it does |
|---|---|
| `add --kind baseline\|sanity\|candidate` | A node's role. The root is usually the baseline. A sanity node is a constant, shuffled-label or no-signal run. |
| `freeze-evaluator [--file PATH ...]` | Writes SHA-256 hashes of the card and each file (a folder hashes every file in it except `__pycache__` and `.pyc`; a file added later shows as `added`) as an `evaluator` event. A second freeze needs `--refreeze --note`. |
| `check-evaluator` | Exit 0: every hashed file matches. Exit 3: one changed or is gone, or nothing is frozen. Exit 2: no tree. |
| `arena SLUG SLUG ... --winner SLUG` | Records a comparison of sibling candidates on the rubric (`plan --rubric`, a `user` row). Refuses a rubric set after the siblings' first run. |

Enforced by `tree.py`: no run before the evaluator is frozen; a run or an answer is refused while a hashed file differs; a candidate answer is refused until a baseline and a sanity node have run; only answered candidates count toward the floor; `stop --reason rule` is refused before the floor.

## State

`<analysis>/plans/tree.jsonl`, one JSON event per line, appended and never edited. A node is frozen once it has an `answer` event; the replay ignores any later `add`, `run`, `repair` or `answer` for it. The commands take a file lock, and an unfinished last line from a killed writer is dropped on the next write. A run's status comes from the cited receipt, not from a second run store.

## Loop guard (opt-in)

`"loops"` in `.mycelium-extra/gate.json` is `"off"` (default), `"warn"` or `"block"`. It works with the gate on or off. See [gate.json](../gate-json.md).

| Where | What it checks | `block` | `warn` |
|---|---|---|---|
| Before a Bash call | A commit-making git call (`commit`, `merge`, `cherry-pick`, `revert`, `rebase`, `am`, `pull`, or an alias of one), also inside `sh -c`, a block, `env` or `nohup`, while HEAD is a frozen `exp/*` branch; or the root's run command run behind an env var (`SEED=2 python run.py`, `export SEED=2; ...`). Display and device variables (`PYTHONUNBUFFERED`, `CUDA_VISIBLE_DEVICES`, and a few more, listed in `HARMLESS_ENV`) pass. | Denies the call. | Adds a note. |
| Before Write, Edit, MultiEdit, NotebookEdit (Claude), apply_patch (Codex), edit, write, patch (OpenCode) | A target that is a hashed evaluator file, including through a symlink or a patch's `Move to`. Shell commands that write the file are not checked here. | Denies the call. | Adds a note. |
| At turn end | A tree whose `stop-check` exits 3, or a hashed evaluator file that changed. | Blocks once per tree state: a turn that left the tree unchanged is not stopped again, and `stop_hook_active` skips it. The message tells the agent to ask you. | Adds a note. |
| At turn end, tusoskill bridge | A `state/state.json` within three folders of the repo root that has tusoskill's shape (`run_id`, integer `iteration` and `max_iterations`). The guard runs `~/.claude/skills/tusoskill/scripts/biomni_method_state.py stop-check --root <run folder>`; the path can be set with `MYCELIUM_TUSOSKILL_SCRIPT`. | Blocks once per state while that script exits 3. Silent when the script is absent or exits anything else. | Adds a note. |

The bridge message names `record-blocker --kind user` for the agent to run when you say to stop. Escapes: tell the agent to stop (it then records `tree.py stop --reason user`), or set `"loops"` to `"warn"` or `"off"`. The hook is `hooks/loop_guard.py`, registered in `hooks/hooks.json`, `hooks/codex.json` and `opencode/index.js`. It does not touch `hooks/gate.py`.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| A frozen node refuses a run, a repair and a second answer | Enforced: `tree.py` |
| The repair cap and the missing plan rows | Enforced: `tree.py` exits 3 |
| A commit on a frozen branch, an env-prefixed fixed command, a Stop before the rule or floor is met, an edit-tool write to a hashed file, the tusoskill bridge | Enforced only when `"loops"` is `"block"` |
| The evaluator hashes, the floor, the baseline and sanity gate | Enforced: `tree.py` |
| That the card lists every protected file, and that a shell command does not rewrite one | The agent's instruction; a rewrite shows up at the next `check-evaluator` or turn end |
| Branch per node, nodes differ only in committed code, results read from logs | The agent's instruction |
| The four plan rows are yours | The agent's instruction; the plan itself is the gate's |

See [glossary](glossary.md) for loops with no metric, [grill](grill.md) for the plan and the promote-explore path, and [verify](verify.md) for the checked record.
