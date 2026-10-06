Mycelium Extra
==============

**Plan an analysis. Approve what runs. Check the execution record.**

Use it in Claude Code or Codex, alongside
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
Claude Code uses ``/mycelium-extra:<skill>``; Codex uses ``$mycelium-extra:<skill>``.

.. toctree::
   :maxdepth: 1
   :caption: Start here

   docs/installation
   docs/usage

.. toctree::
   :maxdepth: 1
   :caption: Look up details

   docs/skills
   docs/approval-gate
   docs/verification
   docs/mycelium-integration

.. toctree::
   :hidden:

   skills/grill/references/run-plans
