import json
from pathlib import Path

project = "Mycelium Extra"
author = "Mikhael Manurung"
release = json.loads((Path(__file__).resolve().parents[1] /
                      ".claude-plugin/plugin.json").read_text())["version"]
extensions = ["myst_parser", "sphinxcontrib.mermaid", "sphinx.ext.githubpages", "sphinx_design",
              "sphinx_copybutton"]
source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
root_doc = "index"
include_patterns = [
    "index.md",
    "docs/installation.md",
    "docs/usage.md",
    "docs/skills.md",
    "docs/approval-gate.md",
    "docs/verification.md",
    "docs/start/what-it-is.md",
    "docs/start/method.md",
    "docs/start/first-plan.md",
    "docs/guides/plan-an-analysis.md",
    "docs/guides/approve-and-run.md",
    "docs/guides/verify-and-provenance.md",
    "docs/guides/hand-off.md",
    "docs/guides/full-workflow.md",
    "docs/concepts/control-model.md",
    "docs/concepts/gaps-and-passes.md",
    "docs/concepts/not-guaranteed.md",
    "docs/examples/index.md",
    "docs/examples/E01-chat-yes-is-not-consent.md",
    "docs/examples/E03-sign-flipped-comparison.md",
    "docs/examples/E07-verify-unplanned-and-unrecorded.md",
    "docs/examples/track-changes.md",
]
exclude_patterns = ["docs/_build"]
myst_heading_anchors = 6
myst_fence_as_directive = ["mermaid"]
myst_enable_extensions = ["colon_fence", "deflist"]
html_theme = "scanpydoc"
html_title = "Mycelium Extra"
html_baseurl = "https://mdmanurung.github.io/mycelium-extra/"
html_extra_path = ["examples/track-changes-report.html"]
