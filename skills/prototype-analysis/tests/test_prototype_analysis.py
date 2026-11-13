"""The prototype-analysis example runs, prints state after each action, and flags the impactful choice."""

import os
import re
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, "..")
EXAMPLE = os.path.join(SKILL, "examples", "prototype_paired_toy.py")


class PrototypeExample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proc = subprocess.run([sys.executable, "-B", EXAMPLE], capture_output=True, text=True)

    def test_runs_clean(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)

    def test_prints_state_after_each_action(self):
        out = self.proc.stdout
        self.assertIn("[simulated] rows=", out)
        self.assertEqual(len(re.findall(r"\[filter value >= ", out)), 3)
        self.assertIn("control=", out)
        self.assertIn("removed=", out)
        self.assertIn("treated-control", out)

    def test_flags_impactful_choice_without_picking(self):
        self.assertIn("IMPACTFUL", self.proc.stdout)
        self.assertIn("plan row", self.proc.stdout)

    def test_is_deterministic(self):
        again = subprocess.run([sys.executable, "-B", EXAMPLE], capture_output=True, text=True)
        self.assertEqual(self.proc.stdout, again.stdout)


class SkillFiles(unittest.TestCase):
    def test_skill_is_lean_and_one_line_description(self):
        text = open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8").read()
        self.assertLessEqual(len(text.splitlines()), 100)
        front = text.split("---")[1]
        self.assertIn("disable-model-invocation: true", front)
        self.assertEqual(len([l for l in front.splitlines() if l.startswith("description:")]), 1)
        self.assertIn("Adapted from Matt Pocock's prototype skill (MIT)", text)
        for ref in ("data-branch.md", "figure-branch.md"):
            self.assertIn("references/" + ref, text)
            self.assertTrue(os.path.isfile(os.path.join(SKILL, "references", ref)))

    def test_openai_yaml_blocks_implicit(self):
        text = open(os.path.join(SKILL, "agents", "openai.yaml"), encoding="utf-8").read()
        self.assertIn("allow_implicit_invocation: false", text)


if __name__ == "__main__":
    unittest.main()
