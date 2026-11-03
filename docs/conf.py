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
    "docs/walkthrough.md",
    "docs/commands.md",
]
exclude_patterns = ["docs/_build"]
myst_heading_anchors = 6
myst_fence_as_directive = ["mermaid"]
myst_enable_extensions = ["colon_fence", "deflist"]
html_theme = "scanpydoc"
html_title = "Mycelium Extra"
html_baseurl = "https://mdmanurung.github.io/mycelium-extra/"
html_static_path = ["_static"]
html_css_files = ["overviews.css"]
