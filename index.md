# Mycelium Extra

**Use an LLM to help with analysis without handing it your judgement.**

Mycelium Extra is built on one idea: the agent may propose and run, but *you* decide what the analysis is, and the record shows whether it ran that way. It works in three steps:

1. **Plan.** A sourced plan, where every consequential choice says who made it: the repository, you, or a labelled default.
2. **Approve.** You type the approval. Covered runs are denied until you do.
3. **Check.** Afterwards, the plan is compared with the run record. Anything that could not be checked shows as a gap, never as a pass.

It is a plugin for Claude Code, Codex and OpenCode, and it works alongside [Mycelium](https://github.com/arjunrajlaboratory/mycelium) or in an ordinary repository. The three steps are a method, not a product: [The method](docs/start/method.md) shows how to follow them with any tool, or by hand.

**Scope.** It catches execution mistakes and shows gaps. It is not a security boundary and it does not judge the science. See [what it does not guarantee](docs/concepts/not-guaranteed.md).

::::{grid} 1 2 2 2
:gutter: 3

:::{grid-item-card} What it is
:link: docs/start/what-it-is
:link-type: doc

The intent and scope on one page, and how it fits with Mycelium.
:::

:::{grid-item-card} The method
:link: docs/start/method
:link-type: doc

Plan, approve, check, hand off: the habits that make LLM-assisted analysis trustworthy, with or without the plugin.
:::

:::{grid-item-card} Install
:link: docs/installation
:link-type: doc

One page per host: Claude Code, Codex, OpenCode.
:::

:::{grid-item-card} Your first plan
:link: docs/start/first-plan
:link-type: doc

Plan, approve, run and verify one small analysis in ten minutes.
:::

:::{grid-item-card} Guides
:link: docs/guides/plan-an-analysis
:link-type: doc

One task each: plan, approve and run, verify, hand off.
:::

:::{grid-item-card} Reference
:link: docs/skills
:link-type: doc

Skills, the approval gate, verification, and what is not guaranteed.
:::
::::

Claude Code and OpenCode use `/mycelium-extra:<skill>`; Codex uses `$mycelium-extra:<skill>`.

```{toctree}
:hidden:
:maxdepth: 1
:caption: Start

docs/start/what-it-is
docs/start/method
docs/installation
docs/start/first-plan
docs/usage
```

```{toctree}
:hidden:
:maxdepth: 1
:caption: Guides

docs/guides/plan-an-analysis
docs/guides/approve-and-run
docs/guides/verify-and-provenance
docs/guides/hand-off
docs/guides/full-workflow
```

```{toctree}
:hidden:
:maxdepth: 1
:caption: Concepts

docs/concepts/control-model
docs/concepts/gaps-and-passes
docs/concepts/not-guaranteed
```

```{toctree}
:hidden:
:maxdepth: 1
:caption: Reference

docs/skills
docs/approval-gate
docs/verification
```

```{toctree}
:hidden:
:maxdepth: 1
:caption: Examples

docs/examples/index
docs/examples/E01-chat-yes-is-not-consent
docs/examples/E03-sign-flipped-comparison
docs/examples/E07-verify-unplanned-and-unrecorded
docs/examples/track-changes
```

```{toctree}
:hidden:
:maxdepth: 1
:caption: More

All docs <https://github.com/mdmanurung/mycelium-extra/tree/main/docs>
Development notes <https://github.com/mdmanurung/mycelium-extra/blob/main/docs/development.md>
Changelog <https://github.com/mdmanurung/mycelium-extra/blob/main/CHANGELOG.md>
```
