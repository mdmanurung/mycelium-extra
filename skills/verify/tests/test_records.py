"""Run: python3.11 skills/verify/tests/test_records.py

records.py holds the saved-record code that verify.py re-exports. These tests check the re-export,
the binding to verify's globals, and the readers of a saved bundle; `verify write` itself is
covered end to end in test_verify.py.
"""

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(PLUGIN, "hooks"))
sys.dont_write_bytecode = True
import gate  # noqa: E402

MOVED = ("recorded_qualification", "_write_bundle", "write", "target_row", "index_outputs",
         "provenance_receipts", "recorded_lint", "recorded_verify")


class RecordsTest(unittest.TestCase):
    def setUp(self):
        self.verify = gate.load_verify()
        self.records = self.verify._records()
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def put(self, name, text):
        with open(os.path.join(self.dir.name, name), "w", encoding="utf-8") as handle:
            handle.write(text)

    def test_verify_re_exports_every_moved_name(self):
        for name in MOVED:
            self.assertTrue(callable(getattr(self.verify, name)), name)
            self.assertTrue(callable(getattr(self.records, name)), name)

    def test_bind_hands_over_verify_helpers(self):
        self.assertIs(self.records.gate, self.verify.gate)
        self.assertIs(self.records.render, self.verify.render)
        self.assertIs(self.records.LINT_LINE, self.verify.LINT_LINE)

    def test_target_row_names_the_verify_record(self):
        self.assertEqual(self.verify.target_row({"hash": "abcd1234"}),
                         "provenance/verify-abcd1234.md in the Outputs table")

    def test_recorded_verify_reads_the_provenance_row(self):
        self.put("PROVENANCE.md", "| Plan | Approved | Verified | Status | Files |\n|---|---|---|---|---|\n"
                                  "| abcd1234 | 2026-11-01 | 2026-11-02 10:00 | verified | x |\n")
        self.assertEqual(self.verify.recorded_verify(self.dir.name, "abcd1234"), ("2026-11-01", "verified"))
        self.assertEqual(self.verify.recorded_verify(self.dir.name, "ffffffff"), ("?", "verified"))

    def test_recorded_qualification_reads_the_saved_report(self):
        self.put("verify-abcd1234.md", "- Qualification: **not qualified**\n")
        self.assertEqual(self.verify.recorded_qualification(self.dir.name, "abcd1234"), "not qualified")
        self.assertEqual(self.verify.recorded_qualification(self.dir.name, "ffffffff"), "not recorded")

    def test_recorded_lint_not_recorded_without_a_lint_file(self):
        self.assertEqual(self.verify.recorded_lint(self.dir.name, "abcd1234"), "not recorded")
        self.put("lint-abcd1234.txt", "$ scilintr\n")
        self.assertEqual(self.verify.recorded_lint(self.dir.name, "abcd1234"), "clean")


if __name__ == "__main__":
    unittest.main()
