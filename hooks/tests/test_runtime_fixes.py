"""Run: python3 hooks/tests/test_runtime_fixes.py

Regression tests for the host/runtime findings in docs/roadmap/13-function-audit.md: a project root
that is reached through a symlink must not stop the gate writing its own state, and a focus target
must resolve inside a gated folder, not to the project root, a non-gated folder, or the state folder.
"""

import os
import shutil
import sys
import tempfile
import unittest

HOOKS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HOOKS)
sys.dont_write_bytecode = True
import focus  # noqa: E402
import stateio  # noqa: E402


class SymlinkRootTest(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.base)

    # C17: the project root itself reached through a symlink is normal
    def test_state_writes_work_under_a_symlinked_root(self):
        real = os.path.join(self.base, "real")
        os.makedirs(real)
        link = os.path.join(self.base, "link")
        os.symlink(real, link)
        path = os.path.join(link, ".mycelium-extra", "focus", "s.json")
        stateio.atomic(path, "{}")
        with open(os.path.join(real, ".mycelium-extra", "focus", "s.json")) as handle:
            self.assertEqual(handle.read(), "{}")
        with stateio.locked(os.path.join(link, ".mycelium-extra", "focus.lock")):
            pass

    # the guard still refuses a state folder that is itself a link
    def test_a_symlinked_state_folder_is_still_refused(self):
        outside = os.path.join(self.base, "outside")
        root = os.path.join(self.base, "root")
        os.makedirs(outside)
        os.makedirs(root)
        os.symlink(outside, os.path.join(root, ".mycelium-extra"))
        with self.assertRaises(ValueError):
            stateio.atomic(os.path.join(root, ".mycelium-extra", "x.json"), "{}")
        with self.assertRaises(ValueError):
            with stateio.locked(os.path.join(root, ".mycelium-extra", "x.lock")):
                pass
        with self.assertRaises(ValueError):  # deeper inside the linked state folder too
            stateio.atomic(os.path.join(root, ".mycelium-extra", "approvals", "x.json"), "{}")


class FocusTargetTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, "analysis", "one"))
        os.makedirs(os.path.join(self.root, "tools", "x"))
        os.makedirs(os.path.join(self.root, ".mycelium-extra", "pending"))

    def resolve(self, name):
        return focus.resolve_target(self.root, name, ["analysis"])

    # X19: these three links name something that is not an analysis
    def test_a_symlink_to_the_project_root_is_refused(self):
        os.symlink(self.root, os.path.join(self.root, "analysis", "rootlink"))
        with self.assertRaises(focus.FocusError):
            self.resolve("analysis/rootlink")

    def test_a_symlink_to_a_non_gated_folder_is_refused(self):
        os.symlink(os.path.join(self.root, "tools", "x"), os.path.join(self.root, "analysis", "toolslink"))
        with self.assertRaises(focus.FocusError):
            self.resolve("analysis/toolslink")

    def test_a_symlink_into_the_state_folder_is_refused(self):
        os.symlink(os.path.join(self.root, ".mycelium-extra", "pending"),
                   os.path.join(self.root, "analysis", "statelink"))
        with self.assertRaises(focus.FocusError):
            self.resolve("analysis/statelink")

    def test_a_link_inside_the_gated_folder_is_still_a_target(self):
        os.makedirs(os.path.join(self.root, "analysis", "two"))
        os.symlink(os.path.join(self.root, "analysis", "two"), os.path.join(self.root, "analysis", "alias"))
        self.assertEqual(self.resolve("analysis/alias"), "analysis/alias")
        self.assertEqual(self.resolve("analysis/one"), "analysis/one")


if __name__ == "__main__":
    unittest.main(verbosity=2)
