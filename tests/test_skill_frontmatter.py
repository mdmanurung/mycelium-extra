"""Run: python3 tests/test_skill_frontmatter.py

Every skill description is a context pointer that loads on every turn: one line,
short, with the trigger in a first sentence that fits OpenCode's 150-character cut
(opencode/index.js, skillCommands). Skills only a human types are user-invoked in
both hosts: `disable-model-invocation: true` (Claude Code) and
`policy.allow_implicit_invocation: false` (Codex), kept in sync.
"""

import glob
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = sorted(glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md")))
USER_INVOKED = {"focus", "handoff", "harden", "idea-triage", "init", "new-analysis"}
MAX_WORDS = 60
MAX_FIRST_SENTENCE = 150


def frontmatter(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read().split("---", 2)[1]


def description(fm):
    lines = [line for line in fm.splitlines() if line.startswith("description:")]
    assert len(lines) == 1, "one description line"
    return lines[0].partition(":")[2].strip().strip('"')


class SkillFrontmatterTest(unittest.TestCase):
    def test_descriptions_are_short_single_lines(self):
        self.assertTrue(SKILLS)
        for path in SKILLS:
            fm = frontmatter(path)
            desc = description(fm)
            name = os.path.basename(os.path.dirname(path))
            self.assertTrue(desc, name)
            self.assertFalse(desc.endswith(("|", ">")), name + ": block scalars break the OpenCode parser")
            self.assertLessEqual(len(desc.split()), MAX_WORDS, name)
            first = desc.split(". ")[0]
            self.assertLessEqual(len(first), MAX_FIRST_SENTENCE, name + ": " + first)

    def test_user_invoked_skills_are_flagged_in_both_hosts(self):
        for path in SKILLS:
            name = os.path.basename(os.path.dirname(path))
            fm = frontmatter(path)
            claude = "\ndisable-model-invocation: true\n" in fm
            yaml_path = os.path.join(os.path.dirname(path), "agents", "openai.yaml")
            with open(yaml_path, encoding="utf-8") as handle:
                codex = "allow_implicit_invocation: false" in handle.read()
            self.assertEqual(claude, name in USER_INVOKED, name)
            self.assertEqual(codex, name in USER_INVOKED, name + ": openai.yaml out of sync")


if __name__ == "__main__":
    unittest.main()
