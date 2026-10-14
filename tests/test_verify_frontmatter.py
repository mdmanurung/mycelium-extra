"""Run: python3 tests/test_verify_frontmatter.py

Verify uses a JSON-quoted description scalar, a subset of YAML syntax. This
regression checks that representation, not arbitrary YAML frontmatter.
"""

import json
import os
import unittest

SKILL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "skills", "verify", "SKILL.md")


class VerifyFrontmatterTest(unittest.TestCase):
    def test_description_is_a_quoted_scalar(self):
        with open(SKILL, encoding="utf-8") as handle:
            frontmatter = handle.read().split("---", 2)[1]
        self.assertIn("\nname: verify\n", frontmatter)
        value = next(line.partition(": ")[2] for line in frontmatter.splitlines()
                     if line.startswith("description: "))
        description = json.loads(value)
        self.assertIsInstance(description, str)
        self.assertIn("Subcommands:", description)

    def test_original_unquoted_colon_shape_is_rejected(self):
        with self.assertRaises(ValueError):
            json.loads("Read plans. Subcommands: report")


if __name__ == "__main__":
    unittest.main()
