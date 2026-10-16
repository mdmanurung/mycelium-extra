"""Run: python3 skills/decision-status/tests/test_decision_threads.py"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
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

    def test_ascii_locale_prints_non_ascii(self):
        # Python 3.6 under LC_ALL=C writes ASCII to stdout; 3.7+ does so once locale coercion is off.
        living = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, living)
        with open(os.path.join(living, "decisions.md"), "w", encoding="utf-8") as handle:
            handle.write("# Decisions\n\n## 2026-10-01 Use BH, α = 0.05\n\n**Status:** active\n")
        env = dict(os.environ, LC_ALL="C", PYTHONCOERCECLOCALE="0", PYTHONUTF8="0")
        with open(SCRIPT, "rb") as source:
            out = subprocess.check_output([sys.executable, "-", "--living-dir", living], stdin=source, env=env)
        self.assertIn(b"BH, \\u03b1 = 0.05", out)

    def test_term_searches_body_of_untagged_entries(self):
        lines = [e["line"] for e in run("--term", "method-b")]
        self.assertIn(24, lines)

    def test_invalid_search_regex_is_a_usage_error(self):
        with open(SCRIPT) as source:
            proc = subprocess.run([sys.executable, "-", "--living-dir", LIVING, "--term", "["],
                                  stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  universal_newlines=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("invalid --term regex", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_nested_fence_markers_do_not_create_decision_entries(self):
        living = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, living)
        with open(os.path.join(living, "decisions.md"), "w", encoding="utf-8") as handle:
            handle.write("## 2026-10-01 Actual decision\n\n````markdown\n```\n"
                         "## 2026-10-02 Example, not a decision\n~~~\n"
                         "## 2026-10-03 Also an example\n````\n"
                         "## 2026-10-04 Another actual decision\n")
        entries = run("--living-dir", living)
        self.assertEqual([entry["title"] for entry in entries],
                         ["Actual decision", "Another actual decision"])


if __name__ == "__main__":
    unittest.main()
