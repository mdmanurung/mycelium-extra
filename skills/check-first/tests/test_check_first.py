"""The check-first example goes red on the wrong implementation and green on the right one."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLE = os.path.join(HERE, "..", "examples", "paired_check.py")


def run(which, out=None):
    cmd = [sys.executable, "-B", EXAMPLE, which] + (["--out", out] if out else [])
    return subprocess.run(cmd, capture_output=True, text=True)


class CheckFirstExample(unittest.TestCase):
    def test_wrong_is_red(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "r.json")
            proc = run("wrong", out)
            self.assertEqual(proc.returncode, 1, proc.stdout)
            self.assertIn("RED", proc.stdout)
            self.assertEqual(json.load(open(out))["status"], "failed")

    def test_right_is_green(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "r.json")
            proc = run("right", out)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertIn("GREEN", proc.stdout)
            self.assertEqual(json.load(open(out))["status"], "passed")

    def test_red_then_green(self):
        self.assertEqual([run(w).returncode for w in ("wrong", "right")], [1, 0])

    def test_skill_files_present(self):
        root = os.path.join(HERE, "..")
        for rel in ("SKILL.md", "agents/openai.yaml", "references/independent-truth.md", "references/seams-and-slices.md"):
            self.assertTrue(os.path.exists(os.path.join(root, rel)), rel)
        text = open(os.path.join(root, "SKILL.md")).read()
        self.assertIn("disable-model-invocation: true", text)
        self.assertIn("Matt Pocock", text)


if __name__ == "__main__":
    unittest.main()
