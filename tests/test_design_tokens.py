"""Run: python3 tests/test_design_tokens.py

DESIGN.md at the repo root holds the colour tokens. Three files copy them: the track-changes
viewer CSS, the Quarto report theme (light and dark SCSS) and the docs figure script. A colour
edited in one copy and not the others drifts silently, so each copy must equal DESIGN.md.
"""

import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN = re.compile(r'^  ([a-z0-9-]+): "(#[0-9a-f]{6})"$', re.M)
UI = ["paper", "paper-2", "ink", "ink-2", "rule", "rule-strong", "accent",
      "pass", "stale", "gap", "fail", "routine", "add", "del"]
SCSS = ["paper", "paper-2", "ink", "ink-2", "rule", "rule-strong", "accent"]
# make_figures.py constant -> DESIGN.md token (data series stay Okabe-Ito and are not checked here)
FIGURES = {"INK": "ink", "MUTED": "ink-2", "GRID": "rule", "AXIS": "routine", "PAPER": "paper",
           "FRAME": "rule-strong", "ROWLINE": "paper-2", "PASS": "pass", "GAP": "gap", "FAIL": "fail"}


def read(rel):
    with open(os.path.join(REPO, rel), encoding="utf-8") as handle:
        return handle.read()


def tokens():
    front = read("DESIGN.md").split("---")[1]
    colors = front.split("colors:")[1].split("\ntypography:")[0]
    return dict(TOKEN.findall(colors))


class DesignTokens(unittest.TestCase):
    def setUp(self):
        self.tok = tokens()

    def test_every_ui_token_has_a_dark_value(self):
        for name in UI:
            self.assertIn(name, self.tok)
            self.assertIn(name + "-dark", self.tok)

    def test_viewer_css(self):
        css = read("skills/track-changes/assets/viewer.css")
        light = css.split(":root[data-theme=\"dark\"]")[0]
        dark_toggle = css.split(":root[data-theme=\"dark\"]")[1].split("@media")[0]
        dark_media = css.split(":root:not([data-theme=\"light\"])")[1].split("}")[0]
        for name in UI:
            self.assertIn("--{}: {};".format(name, self.tok[name]), light, name)
            for block in (dark_toggle, dark_media):
                self.assertIn("--{}: {};".format(name, self.tok[name + "-dark"]), block, name + "-dark")
        for old, new in (("st-attention", "stale"), ("st-authorized", "pass"), ("st-routine", "routine")):
            self.assertIn("--{}: var(--{});".format(old, new), light)

    def test_quarto_theme(self):
        light = read("skills/new-analysis/templates/report.scss")
        dark = read("skills/new-analysis/templates/report-dark.scss")
        for name in SCSS:
            self.assertIn("${}: {} !default;".format(name, self.tok[name]), light, name)
            self.assertIn("${}: {};".format(name, self.tok[name + "-dark"]), dark, name + "-dark")

    def test_figure_script(self):
        source = read("docs/scenario/make_figures.py")
        values = {}
        for names, literals in re.findall(r"^([A-Z, ]+) = ((?:\"#[0-9a-f]{6}\",? ?)+)$", source, re.M):
            values.update(zip([n.strip() for n in names.split(",")], re.findall(r"#[0-9a-f]{6}", literals)))
        for constant, name in FIGURES.items():
            self.assertEqual(values.get(constant), self.tok[name], constant)


if __name__ == "__main__":
    unittest.main()
