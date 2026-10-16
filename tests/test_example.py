"""docs/example.md quotes real output (tests/e2e/make_example.py). This keeps what it quotes in step with
the code: the status lines and commands it shows must still exist in the skills and hooks, and the README
must link it. It does not regenerate the example, which needs real scilintr and R."""
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(REPO, *parts), encoding="utf-8") as handle:
        return handle.read()


class ExampleTest(unittest.TestCase):
    def setUp(self):
        self.example = read("docs", "example.md")

    def test_quoted_status_lines_still_exist(self):
        sources = read("hooks", "gate.py") + read("skills", "verify", "scripts", "verify.py") + read(
            "skills", "grill", "SKILL.md")
        for line in set(re.findall(r"^(?:Plan status|Verify status): (\w+)", self.example, re.M)):
            self.assertIn(line, sources, "the example shows status {} that no source defines".format(line))
        self.assertIn("Plan status: READY", self.example)
        self.assertIn("Verify status: ", self.example)

    def test_quoted_commands_still_exist(self):
        grill = read("skills", "grill", "SKILL.md") + read("docs", "skills.md")
        for command in set(re.findall(r"/mycelium-extra:(\w[\w-]*)", self.example)):
            self.assertTrue(os.path.isdir(os.path.join(REPO, "skills", command)), command)
        self.assertIn("approve plan", read("hooks", "gate.py"))
        self.assertIn("mycelium-extra:grill", grill)

    def test_readme_links_the_example(self):
        self.assertIn("docs/example.md", read("README.md"))

    def test_no_scratch_paths_leak_into_it(self):
        self.assertNotRegex(self.example, r"/tmp/|mx-e2e-")


if __name__ == "__main__":
    unittest.main()
