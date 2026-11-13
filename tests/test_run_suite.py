"""Run: python3 tests/test_run_suite.py

Runs tests/run_suite.py on a temporary mini-suite of three tiny test files and checks
sharding by class, exit codes, failure tails, --only, --list and the timings file.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

RUNNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_suite.py")

GATE_LIKE = '''import unittest


class FirstTest(unittest.TestCase):
    def test_one(self):
        self.assertTrue(True)


class SecondTest(FirstTest):
    def test_two(self):
        self.assertTrue(True)


class NotATest:
    def test_never(self):
        raise SystemExit(9)


if __name__ == "__main__":
    unittest.main()
'''

PASSING = '''import unittest


class OkTest(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(1, 1)


if __name__ == "__main__":
    unittest.main()
'''

FAILING = '''import unittest


class BadTest(unittest.TestCase):
    def test_bad(self):
        self.fail("BOOM-MARKER caf\\u00e9")


if __name__ == "__main__":
    unittest.main()
'''


class RunSuiteTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        for rel, text in (
            ("hooks/tests/test_gate.py", GATE_LIKE),
            ("tests/test_ok.py", PASSING),
            ("tests/test_fail.py", FAILING),
        ):
            path = os.path.join(self.root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)

    def run_suite(self, *args):
        proc = subprocess.run(
            [sys.executable, RUNNER, "--root", self.root, "--stage", "unit", "-j", "2"] + list(args),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=dict(os.environ, LC_ALL="C"),
        )
        return proc.returncode, proc.stdout.decode("utf-8", "replace")

    def test_list_shards_gate_file_by_class(self):
        code, out = self.run_suite("--list")
        self.assertEqual(code, 0, out)
        for name in ("hooks/tests/test_gate.py::FirstTest", "hooks/tests/test_gate.py::SecondTest",
                     "tests/test_ok.py", "tests/test_fail.py"):
            self.assertIn(name, out)
        self.assertNotIn("NotATest", out)
        self.assertIn("4 shards", out)

    def test_failure_gives_exit_one_and_a_tail(self):
        code, out = self.run_suite()
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL", out)
        self.assertIn("BOOM-MARKER", out)
        self.assertIn("4 shards, 3 passed, 1 failed", out)
        self.assertEqual(out.count("ok  "), 3, out)

    def test_only_runs_matching_shards_and_exits_zero(self):
        code, out = self.run_suite("--only", "test_ok", "--only", "SecondTest")
        self.assertEqual(code, 0, out)
        self.assertIn("2 shards, 2 passed, 0 failed", out)
        self.assertNotIn("test_fail", out)

    def test_only_with_no_match_fails(self):
        code, out = self.run_suite("--only", "nothing-like-this")
        self.assertEqual(code, 1, out)
        self.assertIn("No shards match", out)

    def test_timings_are_written_and_used(self):
        self.run_suite("--only", "test_ok")
        path = os.path.join(self.root, "tests", ".suite_timings.json")
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertEqual(list(data), ["tests/test_ok.py"])
        data["tests/test_fail.py"] = 99.0
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        _, out = self.run_suite("--list")
        lines = [line for line in out.splitlines() if "tests/" in line]
        self.assertIn("tests/test_fail.py", lines[0])  # longest first


    def test_a_failed_shard_keeps_its_old_timing(self):
        path = os.path.join(self.root, "tests", ".suite_timings.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"tests/test_fail.py": 99.0}, handle)
        self.run_suite("--only", "test_fail")
        with open(path, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["tests/test_fail.py"], 99.0)

    def test_a_timings_file_with_odd_values_means_no_timings(self):
        path = os.path.join(self.root, "tests", ".suite_timings.json")
        for text in ('{"a": null}', '{"a": [1]}'):
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            code, out = self.run_suite("--list")
            self.assertEqual(code, 0, out)

    def test_timeout_kills_the_grandchildren(self):
        marker = os.path.join(self.root, "grandchild.pid")
        hang = ("import os, subprocess, sys, time, unittest\n"
                "class HangTest(unittest.TestCase):\n"
                "    def test_hang(self):\n"
                "        child = subprocess.Popen(['sleep', '60'])\n"
                "        open(%r, 'w').write(str(child.pid))\n"
                "        time.sleep(60)\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n" % marker)
        with open(os.path.join(self.root, "tests", "test_hang.py"), "w", encoding="utf-8") as handle:
            handle.write(hang)
        code, out = self.run_suite("--only", "test_hang", "--timeout", "3")
        self.assertEqual(code, 1, out)
        self.assertIn("TIMEOUT", out)
        with open(marker, encoding="utf-8") as handle:
            pid = int(handle.read())
        time.sleep(0.5)
        try:
            os.kill(pid, 0)
            alive = True
        except OSError:
            alive = False
        self.assertFalse(alive, "the sleep grandchild survived the timeout")


if __name__ == "__main__":
    unittest.main()
