Mycelium Extra
==============

**Plan an analysis. Approve what runs. Check the execution record.**

Use it in Claude Code, Codex or OpenCode, alongside
`Mycelium <https://github.com/arjunrajlaboratory/mycelium>`_ or in an ordinary repository.
Start small and add tools when you need them.

Choose your tier
----------------

.. list-table::
   :header-rows: 1
   :widths: 25 30 45

   * - Tier
     - Tools
     - What you get
   * - 1. Plan
     - ``grill``
     - A sourced plan before writing or running code.
   * - 2. Run with approval
     - Add ``init`` and plan approval
     - Covered execution checks, input pins, and receipts.
   * - 3. Verify reportable work
     - Add a pinned run plan and ``verify``
     - Check the execution record and save provenance after confirmation.
   * - 4. Full project workflow
     - Add structure, review, handoff, hardening, and Mycelium
     - Coordinate the analysis lifecycle and prevent recurring mistakes.

**Only need a plan?** Install the plugin and invoke ``grill``.
**Ready to run?** Follow Tier 2 in the usage guide.
See the `full analysis workflow diagram <docs/usage.html#full-analysis-workflow>`_
for the path from question to report.
Claude Code and OpenCode use ``/mycelium-extra:<skill>``; Codex uses ``$mycelium-extra:<skill>``.

.. toctree::
   :maxdepth: 1
   :caption: Start

   docs/start/what-it-is
   docs/installation
   docs/start/first-plan
   docs/usage
   docs/day
   docs/example
   docs/exercise

.. toctree::
   :maxdepth: 1
   :caption: Guides

   docs/guides/plan-an-analysis
   docs/guides/approve-and-run
   docs/guides/verify-and-provenance
   docs/guides/amend-freeze-rescope
   docs/guides/stay-oriented
   docs/guides/hand-off
   docs/guides/second-model-review
   docs/guides/harden-against-repeats
   docs/guides/with-mycelium-or-plain-repo
   docs/validation-recipes

.. toctree::
   :maxdepth: 1
   :caption: Reference

   docs/reference/index
   docs/skills
   docs/reference/gate
   docs/reference/gate-json
   docs/reference/state-files
   docs/approval-gate
   docs/verification
   docs/advanced
   docs/focus-and-track-changes
   docs/mycelium-integration

.. toctree::
   :maxdepth: 1
   :caption: Concepts

   docs/concepts/control-model
   docs/concepts/gaps-and-passes
   docs/concepts/not-guaranteed

.. toctree::
   :maxdepth: 1
   :caption: Development

   Development notes <https://github.com/mdmanurung/mycelium-extra/blob/main/docs/development.md>
   Decisions <https://github.com/mdmanurung/mycelium-extra/blob/main/docs/decisions.md>
   Changelog <https://github.com/mdmanurung/mycelium-extra/blob/main/CHANGELOG.md>

.. toctree::
   :hidden:

   docs/reference/skills/grill
   docs/reference/skills/init
   docs/reference/skills/verify
   docs/reference/skills/new-analysis
   docs/reference/skills/plan-review
   docs/reference/skills/decision-status
   docs/reference/skills/data-contract-check
   docs/reference/skills/focus
   docs/reference/skills/track-changes
   docs/reference/skills/handoff
   docs/reference/skills/idea
   docs/reference/skills/idea-triage
   docs/reference/skills/harden
   skills/grill/references/run-plans
   skills/track-changes/references/schema
