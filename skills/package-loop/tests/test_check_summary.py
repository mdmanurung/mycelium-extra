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
    def test_pytest_singular_counts(self):
        self.assertEqual(cs.summarize("== 3 passed, 1 warning in 0.5s ==")[0], "pytest: 3 passed, 1 warning in 0.5s")
        self.assertEqual(cs.summarize("== 1 error in 0.5s ==")[0], "pytest: 1 error in 0.5s")
        self.assertEqual(cs.summarize("== 2 passed, 2 warnings in 0.5s ==")[0], "pytest: 2 passed, 2 warnings in 0.5s")

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
        self.assertTrue(cs.summarize(text)[0].startswith("rcheck: 0 ERROR, 1 WARNING, 2 NOTE (no Status line"))

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
        self.assertEqual(cs.summarize("Found 1 error.\n", kind="ruff")[0], "ruff: 1 error")

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


class FableFixTest(unittest.TestCase):
    def test_build_failure_is_not_clean(self):
        text = "* checking for file './DESCRIPTION' ... OK\n* creating vignettes ... ERROR\n"
        line, _, bad = cs.summarize(text)
        self.assertIn("1 ERROR", line)
        self.assertTrue(bad)

    def test_killed_check_without_status_is_bad(self):
        text = "* checking for file './DESCRIPTION' ... OK\n* checking package namespace information ... OK\n"
        line, _, bad = cs.summarize(text)
        self.assertIn("no Status line", line)
        self.assertTrue(bad)

    def test_tests_error_on_own_line_counts(self):
        text = "* checking tests ...\n  Running 'testthat.R'\n ERROR\n"
        line, _, bad = cs.summarize(text)
        self.assertTrue(line.startswith("rcheck: 1 ERROR"))
        self.assertTrue(bad)

    def test_status_line_log_is_complete(self):
        self.assertNotIn("no Status line", self.line_of("rcmdcheck_ok.txt"))

    def line_of(self, name):
        return cs.summarize(sample(name))[0]

    def test_testthat_summary(self):
        line, _, bad = cs.summarize("[ FAIL 1 | WARN 0 | SKIP 0 | PASS 7 ]\nError: Test failures\n")
        self.assertEqual(line, "testthat: FAIL 1, WARN 0, SKIP 0, PASS 7")
        self.assertTrue(bad)
        line, _, bad = cs.summarize("[ FAIL 0 | WARN 1 | SKIP 0 | PASS 8 ]\n")
        self.assertEqual(line, "testthat: FAIL 0, WARN 1, SKIP 0, PASS 8")
        self.assertFalse(bad)

    def test_testthat_with_no_tests_is_bad(self):
        self.assertTrue(cs.summarize("[ FAIL 0 | WARN 0 | SKIP 0 | PASS 0 ]\n")[2])

    def test_last_devtools_summary_wins(self):
        clean = "0 errors \u2714 | 0 warnings \u2714 | 0 notes \u2714\n"
        err = "1 error  \u2716 | 0 warnings \u2714 | 0 notes \u2714\n"
        self.assertEqual(cs.summarize(clean + err)[0], "rcheck: 1 ERROR, 0 WARNING, 0 NOTE")
        self.assertTrue(cs.summarize(clean + err)[2])
        self.assertEqual(cs.summarize(err + clean)[0], "rcheck: 0 ERROR, 0 WARNING, 0 NOTE")

    def test_all_deselected_is_bad(self):
        line, _, bad = cs.summarize("============ 2 deselected in 0.03s ============\n")
        self.assertEqual(line, "pytest: 2 deselected in 0.03s")
        self.assertTrue(bad)
        self.assertFalse(cs.summarize("== 3 passed, 2 deselected in 0.03s ==\n")[2])

    def test_ruff_fix_summary(self):
        self.assertEqual(cs.summarize("Found 3 errors (1 fixed, 2 remaining).\n")[0], "ruff: 2 errors")
        self.assertTrue(cs.summarize("Found 3 errors (1 fixed, 2 remaining).\n")[2])
        self.assertEqual(cs.summarize("Found 1 error (1 fixed, 0 remaining).\n")[0], "ruff: clean")
        text = "== 5 passed in 0.10s ==\nFound 3 errors (1 fixed, 2 remaining).\n"
        self.assertEqual(cs.summarize(text)[0], "pytest: 5 passed in 0.10s; ruff: 2 errors")

    def test_notes_come_from_the_counted_run(self):
        first = "* checking A ... NOTE\nStatus: 1 NOTE\n"
        second = "* checking B ... NOTE\n* checking C ... NOTE\nStatus: 2 NOTEs\n"
        line, notes, _ = cs.summarize(first + second, want_notes=True)
        self.assertEqual(line, "rcheck: 0 ERROR, 0 WARNING, 2 NOTE")
        self.assertEqual(notes, ["checking B", "checking C"])

    def test_old_pytest_seconds(self):
        line, _, bad = cs.summarize("===== 3 passed in 0.12 seconds =====\n")
        self.assertEqual(line, "pytest: 3 passed in 0.12s")
        self.assertFalse(bad)
        self.assertTrue(cs.summarize("===== 1 failed, 2 passed in 0.12 seconds =====\n")[2])

    def test_kind_testthat(self):
        self.assertEqual(cs.summarize("[ FAIL 0 | WARN 0 | SKIP 0 | PASS 3 ]", kind="testthat")[0],
                         "testthat: FAIL 0, WARN 0, SKIP 0, PASS 3")


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
