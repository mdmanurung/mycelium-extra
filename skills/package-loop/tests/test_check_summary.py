"""Run: python3 skills/package-loop/tests/test_check_summary.py"""

import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "check_summary.py")
sys.path.insert(0, os.path.dirname(SCRIPT))
import check_summary as cs  # noqa: E402


def sample(name):
    with open(os.path.join(HERE, "samples", name), encoding="utf-8") as fh:
        return fh.read()


class SummaryTest(unittest.TestCase):
    def line(self, name, **kw):
        return cs.summarize(sample(name), **kw)[0]

    def test_rcmdcheck_status_line(self):
        self.assertEqual(self.line("rcmdcheck_notes.txt"), "rcheck: 0 ERROR, 1 WARNING, 2 NOTE")

    def test_rcmdcheck_ok(self):
        self.assertEqual(self.line("rcmdcheck_ok.txt"), "rcheck: 0 ERROR, 0 WARNING, 0 NOTE")

    def test_devtools_error(self):
        line, _, bad = cs.summarize(sample("devtools_error.txt"))
        self.assertEqual(line, "rcheck: 1 ERROR, 0 WARNING, 2 NOTE")
        self.assertTrue(bad)

    def test_devtools_clean(self):
        self.assertEqual(self.line("devtools_clean.txt"), "rcheck: 0 ERROR, 0 WARNING, 0 NOTE")

    def test_note_count_falls_back_to_check_lines(self):
        text = "* checking R code ... NOTE\nx\n* checking docs ... NOTE\n* checking tests ... WARNING\n"
        self.assertEqual(cs.summarize(text)[0], "rcheck: 0 ERROR, 1 WARNING, 2 NOTE")

    def test_note_headings(self):
        notes = cs.summarize(sample("rcmdcheck_notes.txt"), want_notes=True)[1]
        self.assertEqual(notes, ["checking R code for possible problems", "checking for future file timestamps"])

    def test_pytest_failures(self):
        line, _, bad = cs.summarize(sample("pytest_fail.txt"))
        self.assertEqual(line, "pytest: 2 failed, 10 passed, 1 skipped in 1.23s")
        self.assertTrue(bad)

    def test_pytest_quiet_pass(self):
        line, _, bad = cs.summarize(sample("pytest_quiet_pass.txt"))
        self.assertEqual(line, "pytest: 11 passed in 0.42s")
        self.assertFalse(bad)

    def test_pytest_no_tests_is_bad(self):
        line, _, bad = cs.summarize(sample("pytest_none.txt"))
        self.assertEqual(line, "pytest: no tests ran")
        self.assertTrue(bad)

    def test_ruff(self):
        self.assertEqual(self.line("ruff_found.txt"), "ruff: 2 errors")
        self.assertEqual(self.line("ruff_clean.txt"), "ruff: clean")

    def test_joined_parts(self):
        text = sample("pytest_quiet_pass.txt") + sample("ruff_clean.txt")
        self.assertEqual(cs.summarize(text)[0], "pytest: 11 passed in 0.42s; ruff: clean")

    def test_ansi_is_stripped(self):
        text = "\x1b[31m1 failed\x1b[0m, 2 passed in 0.1s"
        self.assertEqual(cs.summarize(text)[0], "pytest: 1 failed, 2 passed in 0.1s")

    def test_kind_limits_parsing(self):
        text = sample("pytest_quiet_pass.txt") + sample("ruff_clean.txt")
        self.assertEqual(cs.summarize(text, kind="ruff")[0], "ruff: clean")

    def test_warnings_and_notes_do_not_set_bad(self):
        self.assertFalse(cs.summarize(sample("rcmdcheck_notes.txt"))[2])


class CliTest(unittest.TestCase):
    def run_cli(self, *args, stdin=""):
        return subprocess.run([sys.executable, SCRIPT] + list(args), input=stdin,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True)

    def test_stdin_prints_one_line(self):
        r = self.run_cli(stdin=sample("pytest_fail.txt"))
        self.assertEqual((r.returncode, r.stdout), (0, "pytest: 2 failed, 10 passed, 1 skipped in 1.23s\n"))

    def test_exit_code_flag(self):
        path = os.path.join(HERE, "samples", "devtools_error.txt")
        self.assertEqual(self.run_cli("--exit-code", path).returncode, 1)
        self.assertEqual(self.run_cli(path).returncode, 0)

    def test_unrelated_text_exits_2(self):
        r = self.run_cli(stdin=sample("unrelated.txt"))
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")

    def test_notes_flag(self):
        r = self.run_cli("--notes", os.path.join(HERE, "samples", "rcmdcheck_notes.txt"))
        self.assertEqual(r.stdout.splitlines()[0], "rcheck: 0 ERROR, 1 WARNING, 2 NOTE")
        self.assertIn("NOTE: checking R code for possible problems", r.stdout)


if __name__ == "__main__":
    unittest.main()
