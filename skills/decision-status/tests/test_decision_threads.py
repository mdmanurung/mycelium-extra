"""Run: python3 skills/decision-status/tests/test_decision_threads.py"""

import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "decision_threads.py")
LIVING = os.path.join(HERE, "fixtures", ".living")


def run(*args):
    with open(SCRIPT) as source:
        out = subprocess.check_output(
            [sys.executable, "-", "--living-dir", LIVING, "--json"] + list(args),
            stdin=source)
    return json.loads(out.decode("utf-8"))


class DecisionThreadsTest(unittest.TestCase):
    def test_counts_headings_outside_fences(self):
        titles = [e["title"] for e in run()]
        self.assertEqual(len(titles), 6)
        self.assertNotIn("Not an entry inside a fence", titles)

    def test_template_status_is_ignored(self):
        fmt = [e for e in run() if e["title"] == "Format"][0]
        self.assertNotIn("status", fmt)

    def test_sorted_by_date_not_file_order(self):
        lines = [e["line"] for e in run("--tag", "method-selection")]
        self.assertEqual(lines, [17, 11, 32])

    def test_heading_formats(self):
        by_line = {e["line"]: e for e in run()}
        self.assertEqual(by_line[17]["date"], "2026-03-01")
        self.assertEqual(by_line[17]["title"], "Method A confirmed as production correction")
        self.assertEqual(by_line[17]["positional_ids"], ["D-007"])
        self.assertEqual(by_line[24]["date"], "2026-03-05")
        self.assertIsNone(by_line[28]["date"])

    def test_raw_fields_and_hints(self):
        by_line = {e["line"]: e for e in run()}
        self.assertEqual(by_line[17]["status"], "active (supersedes the [2026-02-01 revisit] note)")
        self.assertEqual(by_line[11]["hints"], ["held"])
        self.assertEqual(by_line[17]["hints"], ["confirmed"])
        self.assertNotIn("status", by_line[11])
        self.assertEqual(by_line[32]["resolved_by"], "user, 2026-04-01")

    def test_colon_inside_bold_field(self):
        by_line = {e["line"]: e for e in run()}
        self.assertEqual(by_line[11]["tags"], ["method-selection", "method-b"])

    def test_term_searches_body_of_untagged_entries(self):
        lines = [e["line"] for e in run("--term", "method-b")]
        self.assertIn(24, lines)


if __name__ == "__main__":
    unittest.main()
