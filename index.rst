Mycelium Extra
==============

**Give each analysis a plan you can check against its execution.**

Research projects carry decisions that are easy to lose between a question,
a script, and a finished report. You may know why a cohort was filtered one
way, but the next session may not. A sample table may change after you checked
it. A result may be quoted without a clear link to the run that produced it.

Mycelium Extra makes those connections explicit. It reads the project before
planning, helps you settle consequential choices, and checks covered runs
against the plan you approved. Verification then shows what the execution
record supports and where evidence is missing.

Use it in Claude Code or Codex, alongside
`Mycelium <https://github.com/arjunrajlaboratory/mycelium>`_ or in an ordinary
repository. Mycelium supplies the project's memory and analysis conventions;
Mycelium Extra supplies the planning and verification steps around a run.

Start with the installation instructions and host compatibility table.
Claude Code uses ``/mycelium-extra:grill``; Codex uses
``$mycelium-extra:grill``.

* **Start with the question.** Planning uses your repository's evidence and
  asks about choices that need your judgment.
* **Approve the work.** The gate checks covered commands and pinned inputs
  before execution.
* **Read the record.** Verification connects the frozen plan, receipts,
  outputs, and checked claims without re-running the analysis.

.. toctree::
   :maxdepth: 2
   :caption: Use the plugin

   README
   docs/installation
   docs/skills
   docs/approval-gate

.. toctree::
   :maxdepth: 1
   :caption: Reference and development

   docs/mycelium-integration
   docs/development
   CHANGELOG
   docs/roadmap/README

.. toctree::
   :maxdepth: 1
   :caption: Design and validation

   docs/design/c1-fixture-project
   docs/design/claim_artifact_checker_design
   docs/design/SKILL_verify_claims
   docs/design/e4-real-use

.. toctree::
   :hidden:
   :glob:

   docs/roadmap/0*
   skills/*/references/*
