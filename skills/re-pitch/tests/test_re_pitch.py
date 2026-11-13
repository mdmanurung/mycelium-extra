"""The re-pitch skill has its required elements and a reference page."""

import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SKILL = os.path.join(ROOT, "skills", "re-pitch", "SKILL.md")
YAML = os.path.join(ROOT, "skills", "re-pitch", "agents", "openai.yaml")
DOC = os.path.join(ROOT, "docs", "reference", "skills", "re-pitch.md")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class RePitch(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL)

    def test_frontmatter(self):
        fm = self.text.split("---")[1]
        self.assertIn("name: re-pitch", fm)
        self.assertIn("disable-model-invocation: true", fm)
        desc = re.search(r"^description: (.+)$", fm, re.M).group(1).strip('"')
        self.assertLessEqual(len(desc.split(".")[0]), 150)
        self.assertLessEqual(len(desc.split()), 60)

    def test_four_rules(self):
        t = self.text
        self.assertIn("Keep every number", t)
        self.assertIn("unsupported: no inspected figure", t)
        self.assertIn("rows word for word", t)
        self.assertIn("numbered `1.`", t)

    def test_glossary_pointer(self):
        self.assertIn("GLOSSARY.md", self.text)

    def test_credit_and_where(self):
        self.assertIn("Adapted from Matt Pocock's wait-what skill (MIT)", self.text)
        self.assertIn("`where`", self.text)

    def test_length(self):
        self.assertLess(len(self.text.splitlines()), 40)

    def test_openai_yaml(self):
        self.assertIn("allow_implicit_invocation: false", read(YAML))

    def test_doc_page(self):
        self.assertTrue(os.path.isfile(DOC))
        self.assertIn("where", read(DOC))


if __name__ == "__main__":
    unittest.main()
