# The method

Mycelium Extra is one implementation of a method for working with an LLM on analysis. The method does not depend on the plugin or on any one model. Use these six habits with another tool, or by hand, and you keep most of the benefit.

## Why a method

An agent is fluent and fast, and it fails in quiet ways. These are the failures the habits below are built for:

- It treats "yes" in chat as permission to run something new.
- It fills a gap with a plausible default and does not say so.
- It reuses an old decision whose basis has changed.
- It edits code after you reviewed it.
- It reports a number that differs from the output file.

None of this is malice. It is what fluent text generation does when nobody stops it. Each habit below puts one checkpoint where you can see it. See [the examples](../examples/index.md) for each failure in a real project.

## Six habits

| # | Habit | With Mycelium Extra | Without it |
|---|---|---|---|
| 1 | **State the question and the claim you hope for, in your own words, before any code.** | `grill` asks first | Write two lines at the top of `PLAN.md` |
| 2 | **Make every consequential choice visible, with its source.** Mark each as yours, the repository's, or a default. | The plan table's Choice column | A table: step, choice, who decided, why |
| 3 | **Approve explicitly, and name what may run.** Approval is something you do, not something the agent infers. | `approve plan <hash>`; the gate denies other runs | Commit the plan with a sign-off line; run only the listed scripts |
| 4 | **Keep exploration apart from reportable runs.** Quick tries are fine; they are never results. | `allow explore`; explore runs are flagged | A `scratch/` folder whose outputs you never cite |
| 5 | **Record what ran, then check the record against the plan.** Treat anything unknown as a gap, not a pass. | Receipts, then `verify` | Log command, code version, input checksums and exit status; compare by hand |
| 6 | **Hand off in writing.** The next session knows only what you wrote down. | `handoff` | A short file: goal, next action, decisions locked, dead ends |

## Three rules that hold across tools

1. **Unknown is not fine.** If a check could not run, say "not checked". A silent pass is the worst outcome.
2. **A matching record is not a correct analysis.** Verification shows the run followed the plan. Review the methods separately.
3. **The human approves; the agent proposes.** Do not let the same session that proposes a step also approve it.

## Learning to work with an LLM this way

- Start with habit 1 alone: write the question before you ask for code. Add the others as a project needs them; [usage tiers](../usage.md) show an order.
- When something surprises you, ask what the agent assumed. Surprises usually come from an unmarked default.
- Keep the record small. A short plan and a log you read beat a long one you skip.

## Next

[What the plugin does](what-it-is.md) · [Install](../installation.md) · [Your first plan](first-plan.md)
