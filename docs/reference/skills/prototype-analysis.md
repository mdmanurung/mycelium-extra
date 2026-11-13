# prototype-analysis

Builds a throwaway prototype that answers one analytic question, then records the verdict. It runs nothing on its own, grants nothing and writes no `.living/` file. Adapted from Matt Pocock's prototype skill (MIT).

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`). Run it as `/mycelium-extra:prototype-analysis` before a plan row commits to a method, a threshold or a panel layout.

The skill has no script. Its example runs on the standard library:

```bash
python3 skills/prototype-analysis/examples/prototype_paired_toy.py
python3.11 skills/prototype-analysis/tests/test_prototype_analysis.py
```

## The two branches

The question picks the branch.

| Question | Branch | The prototype |
|---|---|---|
| Does this method, threshold or model behave sensibly? | DATA | Runs on a toy table with known truth and on one small set of whole donors or batches, in memory. Prints shapes, counts per donor, what each step removed and the contrast sign after every action. |
| What should this panel look like? | FIGURE | Draws 3 radically different variants from one plotted table, with donors as points over a named summary, the lab theme and 89 mm width. Saves A, B, C and a contact sheet as PNGs. You pick by looking. |

A question that needs both is two prototypes; DATA goes first.

## Rules

1. Throwaway from the start. Files are named `prototype_*` and live in `analysis/<name>/scratch/prototype_<question>/`, for the analysis they belong to and away from its `code/` and `outputs/`.
2. One command runs it. That path is gated, so runs need your `allow explore` grant and the `MYCELIUM_EXTRA_EXPLORE=1` prefix ([approval gate](../../approval-gate.md)), and the gate logs each run as exploratory.
3. Nothing it prints or draws is cited. A prototype never feeds a reported result.
4. It suggests; you decide. Each impactful choice it turns up (threshold, filter, transform, contrast, model family) becomes a proposed plan row for you, never a change.
5. Capture at the end. The verdict and the question it settled go into `analysis/<name>/plans/ITERATIONS.md` (the `glossary` skill, when present) or the log of `analysis/<name>/plans/TRACKER.md`. You choose: delete the prototype or keep it in place. A throwaway branch `prototype/<question>` is made only when you ask, because it needs a commit.

## Reads and writes

Reads the plotted table or the small unit set you name, read-only. Writes under `analysis/<name>/scratch/prototype_<question>/` and one line in `analysis/<name>/plans/ITERATIONS.md` or `analysis/<name>/plans/TRACKER.md`. It never writes `.living/` or `todo/`.

## Default on or off

Off until you type it.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| A prototype run without your grant | Enforced: the gate denies the explore prefix until you type `allow explore` |
| A prototype run is logged | Enforced: runs under the gated scratch path go to the explore log |
| A prototype never reaches `outputs/` or a result | The agent's instruction: the gate does not check it |
| Naming, scratch path, state prints, three-variant rule | The agent's instruction |
| Capturing the verdict and removing the prototype | The agent's instruction |

See [check-first](check-first.md) to test a real step against known truth, and [grill](grill.md) to turn a kept idea into an approved plan row.
