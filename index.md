# Mycelium Extra

Mycelium Extra is a plugin for Claude Code, Codex and OpenCode that helps you plan an analysis, approve what runs, and check the execution record afterwards.
It plans before code runs, denies covered runs until you approve a plan that names them, and compares what ran against what you approved.
It works alongside [Mycelium](https://github.com/arjunrajlaboratory/mycelium) or in an ordinary repository, and you can start with planning alone.

::::{grid} 1 2 2 2
:gutter: 3

:::{grid-item-card} Installation
:link: docs/installation
:link-type: doc

New to Mycelium Extra? Install it for your host in a minute.
:::

:::{grid-item-card} Your first plan
:link: docs/start/first-plan
:link-type: doc

Plan, approve, run and verify one small analysis in ten minutes.
:::

:::{grid-item-card} Guides
:link: docs/guides/plan-an-analysis
:link-type: doc

Task-based guides for planning, approving, verifying and handing off.
:::

:::{grid-item-card} Reference
:link: docs/skills
:link-type: doc

Every skill, the approval gate and what verification checks.
:::

:::{grid-item-card} Examples
:link: docs/examples/index
:link-type: doc

Episodes from real projects: what the gate stopped and what the record showed.
:::

:::{grid-item-card} GitHub
:link: https://github.com/mdmanurung/mycelium-extra

Found a bug or want to contribute? The code, issues and changelog are here.
:::
::::

Claude Code and OpenCode use `/mycelium-extra:<skill>`; Codex uses `$mycelium-extra:<skill>`.

```{toctree}
:hidden:
:maxdepth: 1
:caption: Start

docs/start/what-it-is
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
