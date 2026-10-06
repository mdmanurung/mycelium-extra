Mycelium Extra
==============

Plan analysis work using repository evidence, approve it before execution,
and check what ran against the frozen plan. The plugin works alongside
`Mycelium <https://github.com/arjunrajlaboratory/mycelium>`_ and also works
in repositories without Mycelium.

Start with the installation instructions and host compatibility table.
Claude Code uses ``/mycelium-extra:grill``; Codex uses
``$mycelium-extra:grill``.

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
