"""Run: python3 skills/package-loop/tests/test_docs.py  (the docs say what the script does)"""

import os
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


class DocsTest(unittest.TestCase):
    def test_no_tests_exit_code_is_documented(self):
        for text in (read("skills", "package-loop", "SKILL.md"), read("skills", "package-loop", "scripts", "check_summary.py")):
            self.assertIn("no tests", text)
            self.assertNotIn("exits 1 only", text)

    def test_step3_keeps_the_exit_status(self):
        text = read("skills", "package-loop", "SKILL.md")
        self.assertIn("--exit <check exit>", text)
        self.assertIn("PIPESTATUS", text)
        self.assertNotIn("<cmd> 2>&1 | tee checks/<slug>.log`. Then", text)

    def test_testthat_form_has_a_readout_row(self):
        self.assertIn("testthat", read("skills", "package-loop", "references", "check-rows.md").split("## Readout parts")[1])

    def test_exit0_without_summary_is_not_sent_to_repair(self):
        text = read("skills", "package-loop", "SKILL.md")
        self.assertIn("`tree.py repair` refuses", text)

    def test_harden_ladder_covers_levels_1_to_3(self):
        skill = read("skills", "harden", "SKILL.md")
        self.assertIn("For a level 1 to 3 fix", skill)
        self.assertIn("changed file or lint rule", skill)
        page = read("docs", "reference", "skills", "harden.md")
        self.assertNotIn("Writes one test file in the test folder (after your yes)", page)
        self.assertIn("levels 1 to 3", page)


if __name__ == "__main__":
    unittest.main()
