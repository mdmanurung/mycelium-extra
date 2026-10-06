import json
from pathlib import Path

project = "Mycelium Extra"
author = "Mikhael Manurung"
release = json.loads((Path(__file__).resolve().parents[1] /
                      ".claude-plugin/plugin.json").read_text())["version"]
extensions = ["myst_parser", "sphinxcontrib.mermaid", "sphinx.ext.githubpages"]
source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
root_doc = "index"
include_patterns = ["index.rst", "docs/installation.md", "docs/usage.md",
                    "docs/skills.md", "docs/approval-gate.md", "docs/verification.md",
                    "docs/mycelium-integration.md", "skills/grill/references/run-plans.md"]
exclude_patterns = ["docs/_build"]
myst_heading_anchors = 6
myst_fence_as_directive = ["mermaid"]
html_theme = "alabaster"
html_title = "Mycelium Extra"
html_baseurl = "https://mdmanurung.github.io/mycelium-extra/"
html_theme_options = {"description": "Evidence before execution",
                      "github_user": "mdmanurung", "github_repo": "mycelium-extra"}
html_sidebars = {"**": ["about.html", "navigation.html", "searchfield.html"]}
