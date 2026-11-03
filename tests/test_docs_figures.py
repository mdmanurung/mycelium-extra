"""The committed docs figures and facts.json equal what docs/scenario/make_figures.py makes now.

    python3 tests/test_docs_figures.py

If this fails, rerun `python3 docs/scenario/make_figures.py` and commit the changed files.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "docs", "scenario", "make_figures.py")
FIGURES = os.path.join(REPO, "docs", "figures", "scenario")
FACTS = os.path.join(REPO, "docs", "scenario", "facts.json")
NAMES = ["paired-change.svg", "samples.svg", "session-timeline.svg", "verify-outcome.svg", "volcano.svg"]


def read(path):
    with open(path, "rb") as handle:
        return handle.read()


@unittest.skipUnless(shutil.which("git"), "git is needed: the replay commits a temp copy of the fixture")
class DocsFigures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="mx-figures-")
        proc = subprocess.run([sys.executable, SCRIPT, cls.tmp], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if proc.returncode != 0:
            raise AssertionError("make_figures.py failed:\n" + proc.stdout.decode("utf-8", "replace"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_svgs_match_committed(self):
        for name in NAMES:
            with self.subTest(name):
                self.assertEqual(read(os.path.join(self.tmp, name)), read(os.path.join(FIGURES, name)),
                                 name + " is stale: rerun docs/scenario/make_figures.py")

    def test_facts_match_committed(self):
        self.assertEqual(read(os.path.join(self.tmp, "facts.json")), read(FACTS),
                         "facts.json is stale: rerun docs/scenario/make_figures.py")

    def test_svgs_parse(self):
        for name in NAMES:
            with self.subTest(name):
                root = ET.fromstring(read(os.path.join(FIGURES, name)))
                self.assertTrue(root.tag.endswith("svg"))
                self.assertTrue(root.get("viewBox"))
                self.assertIsNotNone(root.find("{http://www.w3.org/2000/svg}title"))
                self.assertIsNotNone(root.find("{http://www.w3.org/2000/svg}desc"))


if __name__ == "__main__":
    unittest.main()
