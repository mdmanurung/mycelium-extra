# Start here

**Use an LLM for analysis without handing it your judgement.** The agent proposes and runs. You decide what the analysis is. The record shows whether it ran that way.

Mycelium Extra is a plugin for Claude Code, Codex and OpenCode. It works alongside [Mycelium](https://github.com/arjunrajlaboratory/mycelium) or in an ordinary repository.

## What it does in three steps

1. **Plan.** The agent writes a sourced plan. Every choice says who made it: the repository, you, or a labelled default.
2. **Approve.** You type the approval. While the gate is on, covered runs are denied until you do.
3. **Check.** Afterwards, the plan is compared with the run record. A planned run with no matching record shows as a gap, never as a pass.

![A researcher states a question, an agent proposes a sourced plan, the researcher approves, covered work leaves records, and verification compares the records with the plan.](docs/figures/overview.svg)

## What you get

:::{figure} docs/figures/scenario/paired-change.svg
:alt: Per-donor log2 change from day 0 to day 28 for 8 interferon genes and 4 control genes, vaccine versus placebo. Vaccine donors rise; placebo donors and control genes stay near zero.
:width: 90%

Per-donor log2 change from day 0 to day 28 for the 8 interferon (IFN) genes and 4 control genes. Vaccine donors rise (mean +1.71); placebo stays flat (−0.05). The data are simulated with known truth, so you can see the plan, the run and the check agree with it. The [walkthrough](docs/walkthrough.md) builds this figure step by step.
:::

## Install

Claude Code:

```bash
claude plugin marketplace add mdmanurung/mycelium-extra
claude plugin install mycelium-extra@mycelium-extra
```

Codex (CLI 0.160.0 or later). Then open `/hooks`, trust every Mycelium Extra hook and start a new task:

```bash
codex plugin marketplace add mdmanurung/mycelium-extra
codex plugin add mycelium-extra@mycelium-extra
```

OpenCode: point both settings at a checkout, in `~/.config/opencode/opencode.json(c)`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugins": ["/absolute/path/to/mycelium-extra/opencode"],
  "skills": ["/absolute/path/to/mycelium-extra/skills"]
}
```

All hosts need Python 3.9 or later. On RHEL 8, `python3` is 3.6, so set `MYCELIUM_EXTRA_PYTHON=python3.11`. Restart the host after installing.

## Your first ten minutes

Claude Code and OpenCode use `/mycelium-extra:<skill>`. Codex uses `$mycelium-extra:<skill>`.

1. **Turn on the gate.** Run `/mycelium-extra:init`.
2. **Plan.** Run `/mycelium-extra:grill <your question>`. It shows a numbered plan and a card with a hash.
3. **Approve.** Type `approve` as your whole message. It takes the card shown last. To pick an older card, type `approve plan <hash>`.
4. **Run.** Ask the agent to run the plan's steps. Covered runs now pass and leave receipts.
5. **Verify.** Run `/mycelium-extra:verify <hash>`. It compares the receipts with the plan and writes provenance after you confirm.

## What it does not guarantee

It catches execution mistakes and shows gaps. It is not a security boundary: an agent set on bypassing the gate through Bash can do so. Runs made while the gate is off, or outside its view, leave no record. A run can match its plan and still be scientifically wrong, because the check covers what ran, not whether the method is right.

## Where next

- [Walkthrough](docs/walkthrough.md): one realistic study, from question to verified result.
- [Commands](docs/commands.md): every typed command and skill on one page.

```{toctree}
:hidden:
:maxdepth: 1

docs/walkthrough
docs/commands
Changelog <https://github.com/mdmanurung/mycelium-extra/blob/main/CHANGELOG.md>
GitHub <https://github.com/mdmanurung/mycelium-extra>
```
