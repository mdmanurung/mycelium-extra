"""Run: python3 hooks/tests/test_gate_error_repeat.py

A broken gate says so once per event kind and session, not on every tool call (0.31). The first error is
logged and shown; a repeat in the same session within the hour is still logged (verify counts the journal) but
its message is not shown again. A deny policy still blocks every tool call, and an error with no session id is
never treated as a repeat. The seen file keeps several sessions, evicts the oldest stamps first and is written
atomically.
"""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.dont_write_bytecode = True
import gate_run  # noqa: E402

STATE = gate_run.STATE_DIR


class RepeatedGateError(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        os.makedirs(os.path.join(self.root, STATE))
        self.config("x\n")  # a gate.json that is not JSON: every hook errors

    def config(self, text):
        with open(os.path.join(self.root, STATE, "gate.json"), "w") as handle:
            handle.write(text)

    def log_lines(self):
        path = os.path.join(self.root, STATE, "gate-errors.jsonl")
        return open(path).read().count("\n") if os.path.isfile(path) else 0

    def error(self, name="tool", session="s1", error="boom"):
        event = {"session_id": session, "tool_use_id": "t"} if session else {}
        return gate_run.error_output(name, error, self.root, event, root=self.root)

    def test_the_first_error_is_logged_and_shown(self):
        out = self.error()
        self.assertIn("gate error (tool)", out["systemMessage"])
        self.assertEqual(self.log_lines(), 1)

    def test_a_repeat_in_the_same_session_is_silent_but_still_logged(self):  # planted break: repeat not journaled
        self.error()
        for _ in range(5):
            self.assertEqual(self.error(), {})
        self.assertEqual(self.log_lines(), 6)

    def test_a_repeat_later_leaves_a_journal_line_with_a_fresh_stamp(self):
        self.error()
        before = time.time()
        self.error()
        path = os.path.join(self.root, STATE, "gate-errors.jsonl")
        stamps = [json.loads(line)["ts"] for line in open(path)]
        self.assertEqual(len(stamps), 2)
        self.assertGreaterEqual(stamps[-1], int(before))

    def test_another_event_kind_a_new_session_or_a_new_error_is_reported_again(self):
        self.error()
        self.assertIn("systemMessage", self.error(name="post"))
        self.assertIn("systemMessage", self.error(session="s2"))
        self.assertIn("systemMessage", self.error(error="different"))
        self.assertEqual(self.log_lines(), 4)

    def test_no_session_id_is_never_a_repeat(self):
        self.error(session=None)
        self.assertIn("systemMessage", self.error(session=None))
        self.assertEqual(self.log_lines(), 2)

    def test_a_repeat_after_an_hour_is_reported_again(self):
        self.error()
        path = os.path.join(self.root, STATE, gate_run.SEEN)
        seen = json.load(open(path))
        seen["sessions"] = {s: {k: time.time() - gate_run.REPEAT_SECONDS - 1 for k in keys}
                            for s, keys in seen["sessions"].items()}
        json.dump(seen, open(path, "w"))
        self.assertIn("systemMessage", self.error())
        self.assertEqual(self.log_lines(), 2)

    def test_a_deny_policy_still_blocks_every_tool_call(self):  # the quiet path must never open the gate
        self.config('{"on_error": "deny"}\n')
        for _ in range(3):
            out = self.error(error="the gate broke")
            self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_interleaved_sessions_each_keep_their_dedupe(self):  # planted break: one session per file
        self.error(session="a")
        self.error(session="b")
        self.assertEqual(self.error(session="a"), {})
        self.assertEqual(self.error(session="b"), {})

    def test_the_cap_evicts_the_oldest_stamp_not_the_first_inserted(self):
        for i in range(gate_run.SEEN_CAP):
            self.error(error="e{}".format(i))
        path = os.path.join(self.root, STATE, gate_run.SEEN)
        seen = json.load(open(path))
        now = time.time()
        for key in seen["sessions"]["s1"]:
            index = int(key.split("\t")[1][1:])  # e0 expired (oldest), then e1 the oldest fresh stamp, e2 ...
            seen["sessions"]["s1"][key] = 0 if index == 0 else now - 100 + index
        json.dump(seen, open(path, "w"))
        self.assertIn("systemMessage", self.error(error="e0"))  # expired, so shown again and re-stamped: now the newest
        self.error(error="new")  # over the cap: evicts the oldest stamp, e1
        self.assertEqual(self.error(error="e0"), {})
        self.assertIn("systemMessage", self.error(error="e1"))

    def test_the_seen_file_is_written_atomically(self):
        calls = []
        real = os.replace
        gate_run.os.replace = lambda a, b: (calls.append((a, b)), real(a, b))[1]
        try:
            self.error()
        finally:
            gate_run.os.replace = real
        self.assertEqual(len(calls), 1)
        self.assertEqual(os.path.dirname(calls[0][0]), os.path.dirname(calls[0][1]))
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, STATE))),
                         ["gate-errors.jsonl", "gate-errors.seen.json", "gate.json"])

    def test_a_deny_policy_logs_every_call(self):
        self.config('{"on_error": "deny"}\n')
        for _ in range(3):
            self.error(error="the gate broke")
        self.assertEqual(self.log_lines(), 3)

    def test_a_corrupt_seen_file_does_not_break_the_hook(self):
        self.error()
        with open(os.path.join(self.root, STATE, gate_run.SEEN), "w") as handle:
            handle.write("{not json")
        self.assertIn("systemMessage", self.error())


if __name__ == "__main__":
    unittest.main()
