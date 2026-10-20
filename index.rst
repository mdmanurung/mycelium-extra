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

.. toctree::
   :maxdepth: 1
   :caption: Core guides

   docs/guides/plan-an-analysis
   docs/guides/approve-and-run
   docs/guides/verify-and-provenance
   docs/guides/hand-off

.. toctree::
   :maxdepth: 1
   :caption: Reference

   docs/skills
   docs/approval-gate
   docs/verification

.. toctree::
   :maxdepth: 1
   :caption: Examples

   docs/examples/index
   docs/examples/E01-chat-yes-is-not-consent
   docs/examples/E03-sign-flipped-comparison
   docs/examples/E07-verify-unplanned-and-unrecorded

.. toctree::
   :maxdepth: 1
   :caption: More (on GitHub)

   All docs <https://github.com/mdmanurung/mycelium-extra/tree/main/docs>
   Development notes <https://github.com/mdmanurung/mycelium-extra/blob/main/docs/development.md>
   Changelog <https://github.com/mdmanurung/mycelium-extra/blob/main/CHANGELOG.md>
