"""Skill-text checks for the cold-reader test.

Run: python3 skills/handoff/tests/test_cold_reader.py
"""

import os
import re
import unittest

SKILLS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(SKILLS)


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as handle:
        return handle.read()


HANDOFF = read(SKILLS, "handoff", "SKILL.md")
REFERENCE = read(SKILLS, "grill", "references", "cold-reader.md")


class ColdReader(unittest.TestCase):
    def test_verb_sits_in_finish_section(self):
        finish = HANDOFF.split("## 3. Finish", 1)[1]
        self.assertIn("`handoff test`", finish)
        self.assertIn("references/cold-reader.md", finish)

    def test_offer_line_ends_handoff_and_report(self):
        for name in ("handoff", "analysis-report"):
            last = read(SKILLS, name, "SKILL.md").rstrip().splitlines()[-1]
            self.assertIn("handoff test", last, name)

    def test_reference_has_prompt_and_rules(self):
        for needle in ("Do not guess", "no gaps", "MISSING.txt", "missing file",
                       "not a sandbox", "Host without subagents", "after the user says so"):
            self.assertIn(needle, REFERENCE, needle)

    def test_command_listed(self):
        self.assertIn("`handoff test`", read(REPO, "docs", "commands.md"))

    def test_state_and_open_items_templates(self):
        self.assertIn("- Assumed, not run: <", HANDOFF)
        self.assertRegex(HANDOFF, r"## Open items\n- .*lean \(not a decision\)")

    def test_state_has_a_run_line(self):
        state = HANDOFF.split("## State", 1)[1].split("## Open items", 1)[0]
        self.assertIn("- Run: <", state)
        for needle in ("status <RUN.txt status>", "kind <kind>", "`flat layout`", "`no run`"):
            self.assertIn(needle, state, needle)
        self.assertIn("docs/concepts/analysis-layout.md", state)

    def test_track_changes_brief_path_uses_the_double_underscore_encoding(self):
        grill = read(SKILLS, "grill", "SKILL.md")
        path = ".mycelium-extra/track-changes/<analysis path with `/` written as `__`>/brief.md"
        self.assertIn(path, HANDOFF)
        self.assertIn(path, grill)
        self.assertNotIn("track-changes/<analysis>/brief.md", HANDOFF)

    def test_no_banned_words(self):
        for word in ("leverage", "robust", "seamless", "comprehensive"):
            self.assertIsNone(re.search(word, REFERENCE, re.I), word)


if __name__ == "__main__":
    unittest.main()
