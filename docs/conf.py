import json
from pathlib import Path

project = "Mycelium Extra"
author = "Mikhael Manurung"
release = json.loads((Path(__file__).resolve().parents[1] /
                      ".claude-plugin/plugin.json").read_text())["version"]
extensions = ["myst_parser", "sphinxcontrib.mermaid", "sphinx.ext.githubpages"]
source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
root_doc = "index"
include_patterns = [
    "index.rst",
    "docs/installation.md",
    "docs/usage.md",
    "docs/day.md",
    "docs/example.md",
    "docs/exercise.md",
    "docs/skills.md",
    "docs/approval-gate.md",
    "docs/verification.md",
    "docs/advanced.md",
    "docs/validation-recipes.md",
    "docs/mycelium-integration.md",
    "docs/focus-and-track-changes.md",
    "docs/start/what-it-is.md",
    "docs/start/first-plan.md",
    "docs/guides/plan-an-analysis.md",
    "docs/guides/approve-and-run.md",
    "docs/guides/verify-and-provenance.md",
    "docs/guides/amend-freeze-rescope.md",
    "docs/guides/stay-oriented.md",
    "docs/guides/hand-off.md",
    "docs/guides/second-model-review.md",
    "docs/guides/harden-against-repeats.md",
    "docs/guides/with-mycelium-or-plain-repo.md",
    "docs/examples/index.md",
    "docs/examples/E*.md",
    "docs/reference/index.md",
    "docs/reference/gate.md",
    "docs/reference/gate-json.md",
    "docs/reference/state-files.md",
    "docs/reference/skills/grill.md",
    "docs/reference/skills/init.md",
    "docs/reference/skills/verify.md",
    "docs/reference/skills/new-analysis.md",
    "docs/reference/skills/plan-review.md",
    "docs/reference/skills/decision-status.md",
    "docs/reference/skills/data-contract-check.md",
    "docs/reference/skills/focus.md",
    "docs/reference/skills/track-changes.md",
    "docs/reference/skills/handoff.md",
    "docs/reference/skills/idea.md",
    "docs/reference/skills/idea-triage.md",
    "docs/reference/skills/harden.md",
    "docs/concepts/control-model.md",
    "docs/concepts/gaps-and-passes.md",
    "docs/concepts/not-guaranteed.md",
    "skills/grill/references/run-plans.md",
    "skills/track-changes/references/schema.md",
]
exclude_patterns = ["docs/_build"]
myst_heading_anchors = 6
myst_fence_as_directive = ["mermaid"]
html_theme = "sphinx_clarity_theme"
html_title = "Mycelium Extra"
html_baseurl = "https://mdmanurung.github.io/mycelium-extra/"
html_theme_options = {
    "header_title": "Mycelium Extra",
    "announcement": "Evidence before execution: plan, approve, verify.",
    "header_menu": [
        {"content": "GitHub", "url": "https://github.com/mdmanurung/mycelium-extra"},
    ],
}
