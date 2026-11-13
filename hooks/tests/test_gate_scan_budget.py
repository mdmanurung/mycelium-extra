"""Run: python3 hooks/tests/test_gate_scan_budget.py

The approvals scan: per-process memo, deadline over the listing, `scan_seconds`, `scan_mtime_filter`."""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

HOOKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.dont_write_bytecode = True
sys.path.insert(0, HOOKS)
import gate  # noqa: E402

STATE = ".mycelium-extra"


class ScanBudgetTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.folder = os.path.join(self.root, STATE, "approvals")
        os.makedirs(self.folder)
        self.config({})
        gate.clear_scan_memo()
        gate.SCAN_NOTE.clear()
        self.addCleanup(gate.clear_scan_memo)

    def config(self, data):
        with open(os.path.join(self.root, STATE, "gate.json"), "w") as handle:
            json.dump(data, handle)
        self.cfg = gate.load_config(self.root)

    def record(self, name, hours_ago=1.0, session="s1", text=None):
        digest = (name * 8)[:8]
        path = os.path.join(self.folder, name + ".json")
        with open(path, "w") as handle:
            text = text if text is not None else json.dumps(
                {"hash": digest, "plan": "plan " + name, "approved_at": time.time() - hours_ago * 3600,
                 "session_id": session})
            handle.write(text)
        return path

    def counted(self, call):
        with mock.patch.object(gate, "read_approval", wraps=gate.read_approval) as reads, \
                mock.patch.object(gate.os, "scandir", wraps=os.scandir) as scans:
            call()
        return scans.call_count, reads.call_count

    def calls(self):
        return (lambda: gate.all_approvals(self.root, self.cfg),
                lambda: gate.active_approvals(self.root, self.cfg, "s1"),
                lambda: gate.active_approvals(self.root, self.cfg, "s2"),
                lambda: gate.active_approvals(self.root, self.cfg),
                lambda: gate.active_approvals(self.root, self.cfg, ""))

    def test_memo_cuts_scans(self):
        for name in "abc":
            self.record(name)

        def three():
            gate.all_approvals(self.root, self.cfg)
            gate.active_approvals(self.root, self.cfg, "s1")
            gate.active_approvals(self.root, self.cfg)

        self.assertEqual(self.counted(three), (1, 3))
        gate.clear_scan_memo()
        self.assertEqual(self.counted(three), (1, 3), "the same after a clear")

    def test_results_equal_with_and_without_memo(self):
        self.record("a", hours_ago=1)
        self.record("b", hours_ago=30)
        self.record("c", hours_ago=2, session="s2")
        memo = tuple(call() for call in self.calls())
        fresh = []
        for call in self.calls():
            gate.clear_scan_memo()
            fresh.append(call())
        self.assertEqual(memo, tuple(fresh))
        self.assertEqual([r["plan"] for r in memo[0]], ["plan a", "plan c", "plan b"])  # newest first
        self.assertEqual([r["plan"] for r in memo[1]], ["plan a"])
        self.assertEqual([r["plan"] for r in memo[3]], ["plan a", "plan c"])
        self.assertEqual(memo[4], [])

    def test_memo_cleared_after_an_approval_write(self):
        self.record("a")
        writers = (lambda: gate.create_exclusive(os.path.join(self.root, "other.json"), {"x": 1}),
                   lambda: gate.write_instance(self.root, {"hash": "aaaaaaaa", "plan": "p", "approved_at": 1}, True),
                   lambda: gate.log_approval(self.root, {"session_id": "s1"},
                                             {"hash": "aaaaaaaa", "text": "p"}, 1.0, None))
        for writer in writers:
            gate.all_approvals(self.root, self.cfg)
            self.assertTrue(gate.SCAN_MEMO)
            writer()
            self.assertFalse(gate.SCAN_MEMO)

    def test_a_new_file_is_seen_even_when_the_folder_time_stamp_did_not_move(self):
        self.record("a")
        self.assertEqual(len(gate.all_approvals(self.root, self.cfg)), 1)
        stamp = os.stat(self.folder).st_mtime_ns
        self.record("b")
        os.utime(self.folder, ns=(stamp + 10 ** 9, stamp + 10 ** 9))  # a later time stamp: the memo is stale
        self.assertEqual(len(gate.all_approvals(self.root, self.cfg)), 2)

    def test_patched_scan_seconds_zero_bypasses_the_memo_and_times_out(self):
        self.record("a")
        self.assertIsNotNone(gate.active_approvals(self.root, self.cfg, "s1"))
        with mock.patch.object(gate, "SCAN_SECONDS", 0):
            self.assertIsNone(gate.active_approvals(self.root, self.cfg, "s1"))
            self.assertIsNone(gate.all_approvals(self.root, self.cfg))
        self.assertEqual(len(gate.active_approvals(self.root, self.cfg, "s1")), 1)

    def test_scan_seconds_default_and_clamp(self):
        self.assertEqual(gate.scan_limit(self.root, self.cfg), 5)
        for given, used in ((0, 1), (0.2, 1), (3, 3), (8, 8), (50, 8)):
            self.config({"scan_seconds": given})
            self.assertEqual(gate.scan_limit(self.root, self.cfg), used, given)
        self.config({"scan_seconds": "slow"})
        self.assertEqual(self.cfg["scan_seconds"], 5)
        self.assertTrue(any("scan_seconds" in n for n in self.cfg["_notices"]))
        self.assertEqual(gate.scan_limit(self.root, self.cfg), 5)
        self.config({"scan_seconds": True})
        self.assertEqual(gate.scan_limit(self.root, self.cfg), 5)
        self.config({"scan_seconds": 7})
        self.assertEqual(gate.scan_limit(self.root), 7, "read from gate.json when no config is passed")

    def test_timeout_message_states_files_seconds_and_command(self):
        for name in "abcd":
            self.record(name)
        with mock.patch.object(gate, "SCAN_SECONDS", 0):
            self.assertIsNone(gate.active_approvals(self.root, self.cfg, "s1"))
            message = gate.scan_timeout_message(self.root)
        self.assertIn("took longer than", message)
        self.assertIn("it had seen 1 files after ", message)
        self.assertIn(" s)", message)
        self.assertIn("mkdir -p {0}-old && find {0} -maxdepth 1 -name '*.json' -mmin +2880 -exec mv -t {0}-old {{}} +"
                      .format(self.folder), message)
        self.assertIn("older than 48 hours", message)
        self.assertIn("scan_seconds", message)

    def test_listing_is_covered_by_the_deadline(self):
        for name in "abcdef":
            self.record(name)
        clock = iter([100.0, 100.0, 100.0, 106.0] + [106.0] * 40)  # start, two checks in time, then late
        with mock.patch.object(gate.time, "time", lambda: next(clock)):
            self.assertIsNone(gate.scan_approvals(self.root, self.cfg))
        self.assertEqual(gate.SCAN_NOTE["files"], 3)  # stopped part-way through the listing
        self.assertEqual(round(gate.SCAN_NOTE["seconds"]), 6)

    def test_mtime_filter_is_off_by_default_and_skips_old_files_when_on(self):
        old = self.record("a", hours_ago=1)
        self.record("b", hours_ago=1)
        long_ago = time.time() - 10 * 86400
        os.utime(old, (long_ago, long_ago))
        self.assertEqual(len(gate.active_approvals(self.root, self.cfg)), 2, "off: nothing skipped")
        self.assertEqual(len(gate.all_approvals(self.root, self.cfg)), 2)
        self.config({"scan_mtime_filter": True})
        gate.clear_scan_memo()
        self.assertEqual([r["plan"] for r in gate.active_approvals(self.root, self.cfg)], ["plan b"])
        self.assertEqual(len(gate.all_approvals(self.root, self.cfg)), 2, "all_approvals never filters")

    def test_corrupt_file_denies_when_filter_off_and_old_corrupt_file_is_skipped_when_on(self):
        bad = self.record("z", text="{truncated")
        long_ago = time.time() - 10 * 86400
        os.utime(bad, (long_ago, long_ago))
        with self.assertRaises(gate.InvalidApproval):
            gate.active_approvals(self.root, self.cfg, "s1")
        with self.assertRaises(gate.InvalidApproval):
            gate.all_approvals(self.root, self.cfg)
        self.config({"scan_mtime_filter": True})
        gate.clear_scan_memo()
        self.assertEqual(gate.active_approvals(self.root, self.cfg, "s1"), [])
        self.record("y", text="[]")
        gate.clear_scan_memo()  # a coarse directory mtime can hide the new file from the memo
        with self.assertRaises(gate.InvalidApproval):  # a recent corrupt file still denies with the filter on
            gate.active_approvals(self.root, self.cfg, "s1")

    def test_filter_key_must_be_boolean(self):
        self.config({"scan_mtime_filter": "yes"})
        self.assertIs(self.cfg["scan_mtime_filter"], False)
        self.assertTrue(any("scan_mtime_filter" in n for n in self.cfg["_notices"]))


if __name__ == "__main__":
    unittest.main()
