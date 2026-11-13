"""Run: python3 skills/ask-extra/tests/test_ask_extra.py

The router table must list every user-invoked skill, name only skills that exist,
and match the committed references/router-table.md. A user-invoked skill with no
group is a warning (it lists under Other), not an error.
"""

import importlib.util
import io
import os
import re
import subprocess
import sys
import tempfile
import unittest
import warnings
from contextlib import redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(SKILL))
SCRIPT = os.path.join(SKILL, "scripts", "make_router_table.py")
TABLE = os.path.join(SKILL, "references", "router-table.md")
spec = importlib.util.spec_from_file_location("make_router_table", SCRIPT)
mrt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mrt)


def table_names(text):
    names = set()
    for cell in re.findall(r"^\| (.+?) \| .* \|$", text, re.M):
        names.update(re.findall(r"/mycelium-extra:([a-z0-9-]+)", cell))
        names.update(re.findall(r"`([a-z][a-z-]*)(?: <\w+>)?`", cell))
    return names


class RouterTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skills = mrt.read_skills(REPO)
        cls.text, cls.unmapped, cls.missing = mrt.build(cls.skills)

    def test_every_user_invoked_skill_is_listed(self):
        listed = table_names(self.text)
        for name, skill in self.skills.items():
            if skill["user"] and name != mrt.ROUTER:
                self.assertIn(name, listed, f"user-invoked skill '{name}' missing from the table")

    def test_every_listed_name_exists(self):
        for name in table_names(self.text):
            self.assertIn(name, self.skills, f"table names '{name}' but skills/{name}/ does not exist")

    def test_router_is_user_invoked_and_not_listed(self):
        self.assertTrue(self.skills[mrt.ROUTER]["user"])
        self.assertNotIn(mrt.ROUTER, table_names(self.text))

    def test_committed_table_is_current(self):
        with open(TABLE, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), self.text, "regenerate references/router-table.md")

    def test_unmapped_skills_warn_not_fail(self):
        for name in self.unmapped:
            warnings.warn(f"user-invoked skill '{name}' has no group in make_router_table.py (listed under Other)")
        self.assertEqual(self.text.count(f"## {mrt.OTHER}"), 1 if self.unmapped else 0)

    def test_mapped_but_missing_names_are_skipped(self):
        for name in self.missing:
            warnings.warn(f"group map names '{name}' but skills/{name}/ does not exist")
            self.assertNotIn(f"/mycelium-extra:{name}`", self.text)

    def test_unknown_skill_lands_in_other(self):
        skills = dict(self.skills, brand_new={"user": True, "description": "A new thing. More text."})
        text, unmapped, _ = mrt.build(skills)
        self.assertIn("brand_new", unmapped)
        self.assertIn("## Other", text)
        self.assertIn("/mycelium-extra:brand_new", text)

    def test_cli_check_and_print(self):
        run = lambda *a: subprocess.run(
            [sys.executable, SCRIPT, "--repo", REPO, *a], capture_output=True, text=True
        )
        self.assertEqual(run().stdout, self.text)
        self.assertEqual(run("--check", TABLE).returncode, 0)
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as stale:
            stale.write("old\n")
        try:
            self.assertEqual(run("--check", stale.name).returncode, 1)
        finally:
            os.unlink(stale.name)

    def test_skill_md_points_at_table_and_script(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as handle:
            body = handle.read()
        self.assertIn("references/router-table.md", body)
        self.assertIn("scripts/make_router_table.py", body)
        self.assertLessEqual(len(body.splitlines()), 100)


if __name__ == "__main__":
    unittest.main()
