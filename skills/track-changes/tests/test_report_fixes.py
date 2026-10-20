"""Run: python3 skills/track-changes/tests/test_report_fixes.py

Regression tests for the track-changes findings in docs/roadmap/13-function-audit.md: two analyses must
not overwrite one report folder, the item cap must keep the attention items, and redaction must cover the
secret shapes a diff really carries.
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
SCRIPT = os.path.join(PLUGIN, "skills", "track-changes", "scripts", "track_changes.py")
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("track_changes_under_test", SCRIPT)
tc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tc)


class FolderTest(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.base)

    def snapshot(self, folder, analysis_path):
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "snapshot.json"), "w") as handle:
            json.dump({"analysis_path": analysis_path}, handle)

    # C38: `a/b` and a folder literally named `a__b` must not share one report folder
    def test_two_analyses_that_spell_one_folder_name_keep_both(self):
        first = tc.output_folder(self.base, "a/b")
        self.snapshot(first, "a/b")
        second = tc.output_folder(self.base, "a__b")
        self.assertNotEqual(first, second)
        self.snapshot(second, "a__b")
        self.assertEqual(tc.output_folder(self.base, "a/b"), first)
        self.assertEqual(tc.output_folder(self.base, "a__b"), second)

    def test_the_same_analysis_keeps_its_folder(self):
        first = tc.output_folder(self.base, "analysis/one")
        self.snapshot(first, "analysis/one")
        self.assertEqual(tc.output_folder(self.base, "analysis/one"), first)


class CapTest(unittest.TestCase):
    # X20: routine items collected early must not push an attention item past the cap
    def test_the_cap_keeps_attention_items(self):
        items = [{"bucket": "routine", "kind": "output", "id": "r{}".format(n)} for n in range(tc.CAP_ITEMS + 10)]
        items += [{"bucket": "attention", "kind": "plan", "id": "a{}".format(n)} for n in range(5)]
        snap = types.SimpleNamespace(items=items, limitations=[])
        tc.prioritize(snap)
        self.assertEqual(len(snap.items), tc.CAP_ITEMS)
        self.assertEqual(sum(1 for i in snap.items if i["bucket"] == "attention"), 5)
        self.assertTrue(any("left out" in limitation for limitation in snap.limitations))


class RedactionTest(unittest.TestCase):
    # X21: shapes a diff carries that the first pattern set missed
    def test_secret_shapes_in_a_diff_are_redacted(self):
        samples = {
            "url password": ("DATABASE_URL=postgres://svc:hunter2hunter2@db.example.org/prod", "hunter2hunter2"),
            "jwt": ("token " + "eyJ" + "a" * 12 + "." + "b" * 12 + "." + "c" * 12, "eyJa"),
            "quoted password": ('password: "correct horse battery staple"', "battery"),
            "private key body": ("-----BEGIN OPENSSH PRIVATE KEY-----\n"
                                  "b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQ\n"
                                  "-----END OPENSSH PRIVATE KEY-----", "b3BlbnNzaC1rZXkt"),
        }
        for name, (text, secret) in samples.items():
            redactor = tc.Redactor()
            out = redactor(text)
            self.assertNotIn(secret, out, name)
            self.assertIn("[redacted]", out, name)
            self.assertGreater(redactor.count, 0, name)

    def test_a_harmless_line_is_left_alone(self):
        redactor = tc.Redactor()
        self.assertEqual(redactor("the model fits in 4 minutes"), "the model fits in 4 minutes")
        self.assertEqual(redactor.count, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
