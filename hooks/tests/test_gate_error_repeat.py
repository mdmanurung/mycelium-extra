"""Run: python3 hooks/tests/test_gate_error_repeat.py

A broken gate says so once per event kind and session, not on every tool call (0.31). The first error is
logged and shown; a repeat in the same session within the hour is neither. A deny policy still blocks every
tool call, and an error with no session id is never treated as a repeat.
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

    def test_a_repeat_in_the_same_session_is_silent_and_not_logged(self):  # planted break: one line per call
        self.error()
        for _ in range(5):
            self.assertEqual(self.error(), {})
        self.assertEqual(self.log_lines(), 1)

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
        seen["keys"] = {k: time.time() - gate_run.REPEAT_SECONDS - 1 for k in seen["keys"]}
        json.dump(seen, open(path, "w"))
        self.assertIn("systemMessage", self.error())
        self.assertEqual(self.log_lines(), 2)

    def test_a_deny_policy_still_blocks_every_tool_call(self):  # the quiet path must never open the gate
        self.config('{"on_error": "deny"}\n')
        for _ in range(3):
            out = self.error(error="the gate broke")
            self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_a_corrupt_seen_file_does_not_break_the_hook(self):
        self.error()
        with open(os.path.join(self.root, STATE, gate_run.SEEN), "w") as handle:
            handle.write("{not json")
        self.assertIn("systemMessage", self.error())


if __name__ == "__main__":
    unittest.main()
