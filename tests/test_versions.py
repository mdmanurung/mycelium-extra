"""Run: python3 tests/test_versions.py

The three plugin manifests carry the same version, and the newest released heading in
CHANGELOG.md names it, so a bump that misses a file fails here.
"""

import json
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(rel):
    with open(os.path.join(REPO, rel), encoding="utf-8") as handle:
        return handle.read()


class VersionsTest(unittest.TestCase):
    def test_manifests_and_changelog_agree(self):
        versions = {
            ".claude-plugin/plugin.json": json.loads(read(".claude-plugin/plugin.json"))["version"],
            ".codex-plugin/plugin.json": json.loads(read(".codex-plugin/plugin.json"))["version"],
            ".claude-plugin/marketplace.json":
                json.loads(read(".claude-plugin/marketplace.json"))["metadata"]["version"],
            "CHANGELOG.md": re.search(r"^## \[(\d[^\]]*)\]", read("CHANGELOG.md"), re.M).group(1),
        }
        self.assertEqual(len(set(versions.values())), 1, versions)


if __name__ == "__main__":
    unittest.main()
