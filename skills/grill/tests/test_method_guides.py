"""Run: python3 skills/grill/tests/test_method_guides.py

The method guides under references/methods/ are plugin references for grill: each has the five sections a plan
needs, links nothing that is missing, names no thresholds as rules, and is reachable from scientific-conventions.md."""

import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REFS = os.path.join(HERE, "..", "references")
METHODS = os.path.join(REFS, "methods")
SECTIONS = ("## Input contract", "## Stop conditions", "## Plan checks", "## Output contract", "## What a pass would not show")


def sections_in_order(text):
    positions = [text.find(section) for section in SECTIONS]
    return -1 not in positions and positions == sorted(positions)


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class MethodGuideTest(unittest.TestCase):
    def guides(self):
        found = sorted(name for name in os.listdir(METHODS) if name.endswith(".md"))
        self.assertTrue(found, "no method guides")
        return found

    def test_every_guide_has_the_five_sections_in_order(self):
        for name in self.guides():
            text = read(os.path.join(METHODS, name))
            self.assertTrue(sections_in_order(text), name)
            self.assertIn("never a `repo:` convention", text, name)

    def test_a_guide_missing_a_section_is_caught(self):
        good = read(os.path.join(METHODS, self.guides()[0]))
        self.assertTrue(sections_in_order(good))
        self.assertFalse(sections_in_order(good.replace("## Stop conditions", "## Notes")))  # a missing section
        swapped = good.replace("## Input contract", "## @@").replace("## Output contract", "## Input contract").replace("## @@", "## Output contract")
        self.assertFalse(sections_in_order(swapped))  # sections out of order

    def test_every_guide_is_reachable_and_every_link_resolves(self):
        science = read(os.path.join(REFS, "scientific-conventions.md"))
        for name in self.guides():
            self.assertIn("methods/" + name, science, name + " is not linked from scientific-conventions.md")
            for target in re.findall(r"\]\(([^)#]+\.md)\)", read(os.path.join(METHODS, name))):
                self.assertTrue(os.path.isfile(os.path.join(METHODS, target)), name + " links missing " + target)
        for target in re.findall(r"\]\((methods/[^)#]+\.md)\)", science):
            self.assertTrue(os.path.isfile(os.path.join(REFS, target)), "scientific-conventions.md links missing " + target)

    def test_no_guide_states_a_numeric_threshold_as_a_rule(self):
        for name in self.guides():
            text = read(os.path.join(METHODS, name))
            self.assertIsNone(re.search(r"\b(R-hat|ESS|p)\s*[<>≥≤]=?\s*\d", text), name)
            self.assertIsNone(re.search(r"\b\d+(\.\d+)?\s*(%|percent)\b", text), name)

    def test_the_single_cell_routing_is_not_duplicated_here(self):
        self.assertEqual([n for n in self.guides() if "single" in n or "scanpy" in n], [])


if __name__ == "__main__":
    unittest.main()
