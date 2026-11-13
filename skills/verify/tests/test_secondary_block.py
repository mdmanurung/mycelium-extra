"""verify prints the optional `secondary-data` plan block (stage C, S2).

Run: python3 skills/verify/tests/test_secondary_block.py
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(PLUGIN, "hooks"))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import verify  # noqa: E402

BASE = "**Objective.** Fit.\n\nOutputs: analysis/a/outputs/\n\n| # | Step | Choice | Source | Validation |\n|---|---|---|---|---|\n"
BLOCK = """<!-- secondary-data
prior exposure: the team saw the raw outcome plots in 2025
target population: adults in the 2019 cohort
estimand: adults, week-12 score, treatment-policy for dropout, mean difference
interpretation would change if: the effect reverses under complete-case analysis
sensitivity analyses (same estimand, different assumptions): complete-case; multiple imputation
supplementary analyses (a different question): effect by sex
-->
"""


class SecondaryBlock(unittest.TestCase):
    def test_present_is_rendered(self):
        text = "\n".join(verify.secondary_data_lines(BASE + BLOCK))
        self.assertIn("## Secondary data", text)
        self.assertIn("prior exposure: the team saw the raw outcome plots in 2025", text)
        self.assertIn("sensitivity analyses (same estimand, different assumptions): complete-case", text)
        self.assertIn("supplementary analyses (a different question): effect by sex", text)

    def test_absent_changes_nothing(self):
        self.assertEqual(verify.secondary_data_lines(BASE), [])
        self.assertEqual(verify.secondary_data_lines(None), [])
        self.assertEqual(verify.secondary_data_lines(BASE + "<!-- secondary-data\n-->"), [])

    def test_malformed_does_not_break(self):
        for bad in ("<!-- secondary-data no label at all -->", "<!-- secondary-data\n: : |||\n\x00 -->",
                    "<!-- secondary-data never closed\nprior exposure: x"):
            lines = verify.secondary_data_lines(BASE + bad)
            self.assertIsInstance(lines, list)
        self.assertEqual(verify.secondary_data_lines(BASE + "<!-- secondary-data never closed"), [])
        self.assertIn("no label at all", "\n".join(verify.secondary_data_lines(BASE + "<!-- secondary-data no label at all -->")))

    def test_gate_parse_unchanged(self):
        import gate
        self.assertEqual(gate.output_words(BASE), gate.output_words(BASE + BLOCK))
        self.assertEqual(gate.plan_inputs(BASE), gate.plan_inputs(BASE + BLOCK))


if __name__ == "__main__":
    unittest.main()
