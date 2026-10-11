"""Run: python3 tests/test_fixture_data.py

The committed fixture data must be exactly what the generator produces, so a hand
edit to a count, a metadata cell, or an expected value fails here.
"""

import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GENERATOR = os.path.join(HERE, "fixtures", "make_fixture_data.py")
PROJECT = os.path.join(HERE, "fixtures", "mycelium-project")


def run(*args):
    proc = subprocess.Popen([sys.executable, GENERATOR] + list(args), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    out = proc.communicate()[0].decode("utf-8")
    return proc.returncode, out


class FixtureDataTest(unittest.TestCase):
    def test_committed_files_match_generator(self):
        code, out = run("--check")
        self.assertEqual(code, 0, out)
        self.assertIn("fixture check: 6 file(s) match seed 0", out)

    def test_failing_seed_is_refused(self):
        code, out = run("--check", "--seed", "2")
        self.assertEqual(code, 2, out)
        self.assertIn("refused: seed 2: median-of-ratios finds 7 true", out)
        code, out = run("--check", "--seed", "13")
        self.assertEqual(code, 2, out)
        self.assertIn("refused: seed 13: total-count CPM gives 0 false positive(s)", out)

    def test_project_stays_small(self):
        files = [os.path.join(d, f) for d, _, names in os.walk(PROJECT) for f in names]
        self.assertLess(len(files), 40)
        self.assertLess(sum(os.path.getsize(f) for f in files), 200 * 1024)


if __name__ == "__main__":
    unittest.main()
