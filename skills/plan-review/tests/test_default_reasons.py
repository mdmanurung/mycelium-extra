"""Unit tests for the advisory default-reason check (roadmap D9).

Run: python3 skills/plan-review/tests/test_default_reasons.py
"""

import os
import subprocess
import sys
import tempfile
import unittest

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(SKILL, "scripts", "default_reasons.py")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
sys.dont_write_bytecode = True
import default_reasons  # noqa: E402

BH = "default: BH, since the tests are not strongly dependent and no weighting is planned"


def plan(*sources):
    lines = ["| # | Step | Choice | Source | Validation |", "|---|---|---|---|---|"]
    lines += ["| {} | step {} | x | {} | ok |".format(i + 1, i + 1, s) for i, s in enumerate(sources)]
    return "\n".join(["**Objective.** Test.", ""] + lines + ["", "Plan status: READY"])


def flagged(text):
    return [(f["row"], f["problem"]) for f in default_reasons.check_plan(text)[2]]


class DefaultReasonsTest(unittest.TestCase):
    def test_acceptance_rows(self):
        self.assertEqual(flagged(plan("default:", "default: standard", BH)),
                         [("1", "no reason"), ("2", "an empty phrase, not a reason")])

    def test_empty_phrases_any_case_and_trivial_punctuation(self):
        for reason in ("Standard", "STANDARD.", "standard!", "(standard)", "common practice",
                       "Common Practice.", "best practice", "best practices", "typical", "Typical;",
                       '"standard"', "standard choice", "it's standard", "the standard approach"):
            self.assertEqual(flagged(plan("default: " + reason)), [("1", "an empty phrase, not a reason")],
                             reason)

    def test_short_and_missing_reasons(self):
        self.assertEqual(flagged(plan("default: Seurat default")), [("1", "a reason under 3 words")])
        self.assertEqual(flagged(plan("default: .")), [("1", "no reason")])
        self.assertEqual(flagged(plan("DEFAULT :")), [("1", "no reason")])
        self.assertEqual(flagged(plan("[repo: / user / default:]")), [("1", "no reason")])

    def test_reasons_that_pass(self):
        for reason in (BH[len("default: "):], "matches step 2",
                       "standard here because the counts are raw UMI from 10x",
                       "typically 30 PCs capture the elbow in this dataset"):
            self.assertEqual(flagged(plan("default: " + reason)), [], reason)

    def test_other_sources_and_other_columns_are_not_read(self):
        text = plan("user", "repo: AGENTS.md", "repo: x.md; default: standard")
        self.assertEqual(flagged(text), [("3", "an empty phrase, not a reason")])
        # A `default:` in the Choice column is a parameter's value, not a source.
        text = "| # | Step | Choice | Source |\n|---|---|---|---|\n| 1 | fit | k (default: 10) | user |"
        self.assertEqual(flagged(text), [])

    def test_source_before_another_source(self):
        self.assertEqual(flagged(plan("default: standard; repo: AGENTS.md")),
                         [("1", "an empty phrase, not a reason")])

    def test_counts_and_step_named(self):
        found, defaults, flags = default_reasons.check_plan(plan("default:", BH, "user"))
        self.assertEqual((found, defaults, len(flags)), (1, 2, 1))
        self.assertEqual(flags[0]["step"], "step 1")
        self.assertIn('row 1 (step 1): "default:" is no reason.', default_reasons.describe(flags[0]))

    def run_cli(self, text, stdin_source=True):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as handle:
            handle.write(text)
        try:
            with open(SCRIPT) as source:
                proc = subprocess.Popen([sys.executable, "-", "--plan", handle.name], stdin=source,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, err = proc.communicate()
        finally:
            os.unlink(handle.name)
        return proc.returncode, out.decode("utf-8"), err.decode("utf-8")

    def test_cli_from_stdin_is_advisory_plain_text(self):
        code, out, _ = self.run_cli(plan("default:", "default: standard", BH))
        self.assertEqual(code, 0)
        self.assertIn("2 of 3 default(s) need a reason", out)
        self.assertIn("- row 1 (step 1):", out)
        self.assertIn("- row 2 (step 2):", out)
        self.assertNotIn("row 3", out)
        self.assertNotIn("**", out)
        self.assertNotIn("`", out)
        code, out, _ = self.run_cli(plan(BH))
        self.assertEqual((code, out), (0, "Default reasons: 1 default(s), each with a reason.\n"))

    def test_cli_gaps_are_not_clean(self):
        code, out, _ = self.run_cli("No table here.")
        self.assertEqual(code, 3)
        self.assertIn("not checked", out)
        with open(SCRIPT) as source:
            proc = subprocess.Popen([sys.executable, "-", "--plan", "/nonexistent/plan.md"], stdin=source,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _, err = proc.communicate()
        self.assertEqual(proc.returncode, 1)
        self.assertIn(b"cannot read the plan", err)


if __name__ == "__main__":
    unittest.main()
