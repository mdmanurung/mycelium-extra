"""Bounded synthetic checks for the unqualified capacity and diary drafts."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import capacity
import journal


class CapacityTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mx-capacity-audit-")
        self.addCleanup(shutil.rmtree, self.root)
        self.sid = "audit-session"
        self.directory = capacity.session_dir(self.root, "claude", self.sid)

    def usage(self, percent=10, observed=None):
        now = time.time()
        return {"observed": now if observed is None else observed,
                "windows": {name: {"used": percent, "reset": now + 3600}
                            for name in ("five_hour", "seven_day")}}

    def enable(self):
        capacity.setup(self.root, "codex")

    def record(self, **values):
        return capacity.checkpoint(self.root, "claude", self.sid, "coordinator", self.root, values)

    def test_allowance_boundaries(self):
        for percent, expected in ((0, "normal"), (79.9, "normal"), (80, "wind_down"),
                                  (89.9, "wind_down"), (90, "closeout"), (100, "closeout")):
            self.assertEqual(capacity.assess(self.usage(percent))[0], expected)

    def test_malformed_or_stale_reading_is_unavailable(self):
        for value in (None, {}, self.usage(observed=time.time() - 301),
                      self.usage(observed=time.time() + 30)):
            self.assertEqual(capacity.assess(value)[0], "unavailable")
        for bad in (True, -1, 101, float("nan"), float("inf"), "10"):
            self.assertEqual(capacity.assess(self.usage(bad))[0], "unavailable")

    def test_missing_window_never_counts_as_normal(self):
        value = self.usage()
        value["windows"]["five_hour"] = None
        self.assertEqual(capacity.assess(value)[0], "unavailable")

    def test_pause_requires_explicit_fresh_resume(self):
        self.enable()
        path = os.path.join(self.directory, "usage.json")
        capacity.write(path, self.usage(90))
        self.assertEqual(capacity.mode(self.root, "claude", self.sid)[0], "paused")
        capacity.write(path, self.usage(10))
        self.assertEqual(capacity.mode(self.root, "claude", self.sid)[0], "paused")
        self.assertEqual(capacity.mode(self.root, "claude", self.sid, resume=True)[0], "normal")
        capacity.write(path, self.usage(80))
        with self.assertRaises(ValueError):
            capacity.mode(self.root, "claude", self.sid, resume=True)

    def test_checkpoint_merges_without_losing_completed_work(self):
        path = self.record(completed="unit one", ownership=["owned.txt"])
        self.record(next_action="unit two")
        value = capacity.read(path)
        self.assertEqual(value["completed"], "unit one")
        self.assertEqual(value["next_action"], "unit two")
        self.assertIsNone(value["checkout"]["files"]["owned.txt"])

    def test_checkpoint_refuses_corrupt_previous_record(self):
        path = self.record(completed="preserve")
        with open(path, "w") as handle:
            handle.write("{partial")
        with self.assertRaises(ValueError):
            self.record(next_action="replacement")
        with open(path) as handle:
            self.assertEqual(handle.read(), "{partial")

    def test_checkpoint_cli_rejects_missing_or_malformed_record(self):
        path = self.record(completed="preserve")
        for text in (None, "{partial", "[]", "null"):
            note = os.path.join(self.root, "input.json")
            if os.path.exists(note):
                os.unlink(note)
            if text is not None:
                with open(note, "w") as handle:
                    handle.write(text)
            result = subprocess.run([sys.executable, capacity.SCRIPT, "checkpoint", "--root", self.root,
                                     "--host", "claude", "--session", self.sid, "--record", note],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertNotEqual(result.returncode, 0, text)
            self.assertEqual(capacity.read(path)["completed"], "preserve")

    def test_ownership_cannot_escape_checkout(self):
        for path in ("../escape", os.path.dirname(self.root)):
            with self.assertRaises(ValueError):
                self.record(ownership=[path])

    def test_atomic_refuses_symlink_target(self):
        target = os.path.join(self.root, "target")
        with open(target, "w") as handle:
            handle.write("preserve")
        link = os.path.join(self.root, "link")
        os.symlink(target, link)
        with self.assertRaises(ValueError):
            capacity.atomic(link, "replace")
        with open(target) as handle:
            self.assertEqual(handle.read(), "preserve")

    def test_paused_execution_denied_without_approval_override(self):
        self.enable()
        handled, reply = capacity.handle({"cwd": self.root, "session_id": self.sid,
                                         "hook_event_name": "PreToolUse", "tool_name": "Bash",
                                         "tool_input": {"command": "python3 analysis/a.py"}})
        self.assertTrue(handled)
        self.assertEqual(reply["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_recovery_names_live_process_without_relaunch(self):
        self.record(running=[{"kind": "pid", "id": os.getpid()}])
        record = capacity.recovery(self.root, "claude", self.sid)[0]
        self.assertIn("identity unconfirmed; do not relaunch", record["jobs"][0]["status"])

    def test_codex_transcript_identity_and_truncated_last_line(self):
        path = os.path.join(self.root, "rollout.jsonl")
        events = [{"type": "session_meta", "payload": {"id": self.sid}},
                  {"type": "event_msg", "timestamp": "2026-10-16T12:00:00Z", "payload": {
                      "type": "token_count", "rate_limits": {
                          name: {"used_percent": 10, "resets_at": 2000000000}
                          for name in ("primary", "secondary")}}}]
        with open(path, "w") as handle:
            handle.write("\n".join(json.dumps(event) for event in events) + "\n{partial")
        self.assertIsNotNone(capacity.codex_rollout(self.sid, path))
        self.assertIsNone(capacity.codex_rollout("another-session", path))

    def test_draft_preserves_user_edits(self):
        self.record(completed="done")
        path = journal.draft(self.root, "claude", self.sid)
        with open(path, "a") as handle:
            handle.write("\nMy edited interpretation.\n")
        journal.draft(self.root, "claude", self.sid)
        with open(path, encoding="utf-8") as handle:
            self.assertTrue(handle.read().endswith("My edited interpretation.\n"))

    def test_diary_review_and_idempotent_append(self):
        journal.draft(self.root, "claude", self.sid)
        with self.assertRaises(ValueError):
            journal.save(self.root, "claude", self.sid)
        for unused in range(2):
            journal.save(self.root, "claude", self.sid, reviewed=True)
        log = os.path.join(self.root, capacity.STATE, "session-log", "claude-" + self.sid + ".md")
        with open(log, encoding="utf-8") as handle:
            self.assertEqual(handle.read().count("<!-- journal:"), 1)
        draft = os.path.join(self.directory, "journal.md")
        with open(draft, "a") as handle:
            handle.write("\nSecond interpretation.\n")
        journal.save(self.root, "claude", self.sid, reviewed=True)
        with open(log, encoding="utf-8") as handle:
            self.assertEqual(handle.read().count("<!-- journal:"), 2)

    def test_missing_mycelium_adapter_preserves_draft(self):
        os.mkdir(os.path.join(self.root, ".living"))
        path = journal.draft(self.root, "claude", self.sid)
        with open(path, "rb") as handle:
            before = handle.read()
        with self.assertRaises(ValueError):
            journal.save(self.root, "claude", self.sid, reviewed=True)
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(), before)

    def test_disabled_hooks_and_statusline_write_nothing(self):
        config = os.path.join(self.root, capacity.STATE, "capacity.json")
        capacity.write(config, {"enabled": False})
        before = set(os.listdir(os.path.dirname(config)))
        for name in ("SessionStart", "PreToolUse", "Stop", "SessionEnd", "PreCompact", "SubagentStart"):
            self.assertEqual(capacity.handle({"cwd": self.root, "hook_event_name": name}), (False, None))
        capacity.statusline(self.root, json.dumps({"session_id": self.sid}))
        self.assertEqual(set(os.listdir(os.path.dirname(config))), before)

    def test_session_start_is_silent_and_stop_text_is_not_completion(self):
        self.enable()
        event = {"cwd": self.root, "session_id": self.sid, "hook_event_name": "SessionStart"}
        self.assertEqual(capacity.handle(event), (True, None))
        event.update(hook_event_name="Stop", last_assistant_message="All tests passed; finished")
        capacity.handle(event)
        record = capacity.read(os.path.join(self.directory, "coordinator.json"))
        self.assertEqual(record["completed"], "unconfirmed")
        self.assertEqual(record["assistant_note"], "All tests passed; finished")
        self.assertIn("unverified", record["completion_evidence"])
        capacity.handle(event)
        self.assertEqual(capacity.read(os.path.join(self.directory, "coordinator.json")), record)

    def test_corrupt_pause_state_is_retained(self):
        self.enable()
        path = os.path.join(self.root, capacity.STATE, "capacity", "claude.json")
        capacity.write(path, [])
        with self.assertRaisesRegex(ValueError, "malformed capacity state"):
            capacity.mode(self.root, "claude", self.sid)
        self.assertEqual(capacity.read(path), [])

    def test_assignments_blocked_before_creation_and_notes_remain_available(self):
        self.enable()
        event = {"cwd": self.root, "session_id": self.sid, "hook_event_name": "PreToolUse"}
        for tool in ("Agent", "Task", "spawn_agent", "followup_task", "TaskCreate", "SendMessage"):
            handled, reply = capacity.handle(dict(event, tool_name=tool, tool_input={}))
            self.assertTrue(handled)
            self.assertEqual(reply["hookSpecificOutput"]["permissionDecision"], "deny")
        note = os.path.join(self.directory, "coordinator.input.json")
        handled, unused = capacity.handle(dict(event, tool_name="Write", tool_input={"file_path": note}))
        self.assertFalse(handled)

    def test_checkpoint_records_checkout_changes_and_repeated_finalization_is_stable(self):
        path = self.record(ownership=["owned.txt"], completed="reported unit")
        with open(os.path.join(self.root, "owned.txt"), "w") as handle:
            handle.write("changed")
        capacity.checkpoint(self.root, "claude", self.sid, "coordinator", self.root, final=True)
        before = capacity.read(path)
        self.assertTrue(before["checkout_history"])
        capacity.checkpoint(self.root, "claude", self.sid, "coordinator", self.root, final=True)
        self.assertEqual(capacity.read(path), before)

    def test_timestamp_requires_offset_and_preserves_offsets(self):
        self.assertEqual(capacity.timestamp("2026-10-16T12:00:00Z"),
                         capacity.timestamp("2026-10-16T14:00:00+02:00"))
        for text in ("2026-10-16T12:00:00", "2026-10-16T12:00:00nonsense"):
            with self.assertRaises(ValueError):
                capacity.timestamp(text)

    def test_launcher_keeps_capacity_and_approval_independent(self):
        self.enable()
        capacity.write(os.path.join(self.root, capacity.STATE, "gate.json"), {})
        capacity.write(os.path.join(self.directory, "usage.json"), self.usage())
        launcher = os.path.join(os.path.dirname(capacity.SCRIPT), "gate_run.py")
        event = {"cwd": self.root, "session_id": self.sid, "hook_event_name": "PreToolUse",
                 "tool_name": "Bash", "tool_input": {"command": "python3 analysis/a.py"}}
        for enabled in (True, False):
            capacity.write(os.path.join(self.root, capacity.STATE, "capacity.json"), {"enabled": enabled})
            result = subprocess.run([sys.executable, launcher, "tool"], input=json.dumps(event).encode(),
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(result.returncode, 0, result.stderr)
            reply = json.loads(result.stdout)
            self.assertEqual(reply["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn("no active approved plan", reply["hookSpecificOutput"]["permissionDecisionReason"])

    def test_lifecycle_registrations_are_held_back_in_a_fragment(self):
        import re
        folder = os.path.dirname(capacity.SCRIPT)
        events = ("SessionStart", "SessionEnd", "SubagentStart", "SubagentStop", "PreCompact")
        with open(os.path.join(folder, "capacity-hooks.json")) as handle:
            fragment = json.load(handle)
        for name in ("hooks.json", "codex.json"):
            with open(os.path.join(folder, name)) as handle:
                hooks = json.load(handle)["hooks"]
            for event in events:  # shipped manifests stay as in 0.9.70 until native lifecycle checks pass
                self.assertNotIn(event, hooks)
                self.assertIn(event, fragment[name])
                self.assertIn(event, fragment[name][event][0]["hooks"][0]["command"])
        for tool in ("Agent", "spawn_agent", "functions.spawn_agent", "TaskCreate", "future_assignment_tool"):
            self.assertIsNotNone(re.search(fragment["PreToolUse_matcher"], tool))

    def test_malformed_checkpoint_is_visible_and_diary_metadata_is_retained(self):
        path = self.record(completed="reported unit")
        capacity.atomic(path, "{partial")
        self.assertIn("Recovery gap", capacity.summary(self.root, "claude", self.sid))
        self.assertIn("do not relaunch", capacity.recovery(self.root, "claude", self.sid)[0]["status"])
        journal.draft(self.root, "claude", self.sid)
        meta = os.path.join(self.directory, "draft.json")
        capacity.atomic(meta, "[]")
        with self.assertRaisesRegex(ValueError, "metadata is malformed"):
            journal.save(self.root, "claude", self.sid, reviewed=True)
        self.assertEqual(capacity.read(meta), [])


if __name__ == "__main__":
    unittest.main()
