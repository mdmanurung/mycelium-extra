"""Run: python3 hooks/tests/test_opencode_gate.py

The OpenCode launcher entry point: payload normalization, the approval flow, receipts
(including the missing-exit-status gap), and state protection for edits, writes and patches.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PLUGIN, "hooks"))
import gate
import gate_run


class OpenCodeGateTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, ".mycelium-extra"))
        with open(os.path.join(self.root, ".mycelium-extra", "gate.json"), "w") as f:
            json.dump({}, f)

    def hook(self, action, **payload):
        payload.setdefault("cwd", self.root)
        payload.setdefault("session_id", "opencode-test")
        result = subprocess.run(
            [sys.executable, os.path.join(PLUGIN, "hooks", "gate_run.py"),
             "--host", "opencode", action], input=json.dumps(payload).encode("utf-8"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else None

    def test_approval_and_receipts(self):
        bash = dict(tool_name="shell", tool_input={"command": "python analysis/x.py"},
                    tool_use_id="call-1")
        blocked = self.hook("tool", **bash)
        self.assertEqual(blocked["hookSpecificOutput"]["permissionDecision"], "deny")
        plan = "## Plan\n| 1 | run `analysis/x.py` | repo | check |\n\nPlan status: READY"
        notice = self.hook("stop", last_assistant_message=plan)
        digest = notice["systemMessage"].split("approve plan ")[1][:8]
        approved = self.hook("prompt", prompt="approve plan " + digest)
        self.assertIn("approved", approved["systemMessage"])
        self.assertIsNone(self.hook("tool", **bash))
        for payload in ({"status": "completed", "tool_response": {"content": "ok"}},
                        {"status": "completed", "tool_response": {"content": "ok", "exitCode": 7}},
                        {"status": "error", "error": {"message": "Command failed", "metadata": {}}}):
            self.hook("post", hook_event_name="PostToolUse", **dict(bash, **payload))
        with open(os.path.join(self.root, ".mycelium-extra", "receipts.jsonl")) as f:
            receipts = [json.loads(line) for line in f]
        self.assertEqual([r["exit_status"] for r in receipts], ["unknown", 7, "unknown"])
        self.assertEqual([r["exit_source"] for r in receipts], [None, "response", None])
        self.assertTrue(all(r["host"] == "opencode" for r in receipts))

    def test_opencode_missing_status_is_not_success(self):
        # The launcher records no exit code for a completed OpenCode shell result (unless the
        # response carries one), so a receipt must never claim 0 from the event alone.
        self.assertEqual(gate.exit_status({"host": "opencode", "hook_event_name": "PostToolUse",
                                           "tool_response": {"content": "ok"}})[0], "unknown")
        self.assertEqual(gate.exit_status({"host": "opencode", "hook_event_name": "PostToolUse",
                                           "tool_input": {"run_in_background": True},
                                           "tool_response": {}})[0], "unknown")
        self.assertEqual(gate.exit_status({"host": "opencode", "hook_event_name": "PostToolUse",
                                           "tool_response": {"exitCode": 0}})[0:2], (0, "response"))
        self.assertEqual(gate.exit_status({"host": "opencode", "hook_event_name": "PostToolUseFailure",
                                           "error": "Command failed"})[0], "unknown")

    def test_payload_normalization(self):
        event = gate_run.opencode_event({"tool_name": "shell", "hook_event_name": "PreToolUse",
                                         "tool_input": {"command": "sbatch run.sh", "background": True}})
        self.assertEqual(event["tool_name"], "Bash")
        self.assertEqual(event["tool_input"]["command"], "sbatch run.sh")
        self.assertTrue(event["tool_input"]["run_in_background"])
        event = gate_run.opencode_event({"tool_name": "edit", "hook_event_name": "PreToolUse",
                                         "tool_input": {"path": "analysis/x.py", "oldString": "a",
                                                        "newString": "b"}})
        self.assertEqual((event["tool_name"], event["tool_input"]["file_path"]), ("Edit", "analysis/x.py"))
        event = gate_run.opencode_event({"tool_name": "write", "hook_event_name": "PreToolUse",
                                         "tool_input": {"path": "analysis/y.py", "content": "x"}})
        self.assertEqual((event["tool_name"], event["tool_input"]["file_path"]), ("Write", "analysis/y.py"))
        event = gate_run.opencode_event({"tool_name": "patch", "hook_event_name": "PreToolUse",
                                         "tool_input": {"patchText": "*** Begin Patch\n*** Add File: a\n+x\n*** End Patch"}})
        self.assertEqual(event["tool_name"], "apply_patch")
        self.assertIn("*** Add File: a", event["tool_input"]["command"])
        event = gate_run.opencode_event({"tool_name": "read", "hook_event_name": "PreToolUse",
                                         "tool_input": {"path": "README.md"}})
        self.assertEqual(event["tool_name"], "read")
        event = gate_run.opencode_event({"tool_name": "shell", "hook_event_name": "PostToolUse",
                                         "status": "error", "tool_input": {"command": "python x.py"},
                                         "error": {"message": "Command failed", "metadata": {"exitCode": 2}}})
        self.assertEqual(event["hook_event_name"], "PostToolUseFailure")
        self.assertEqual(event["error"], "Command failed")
        self.assertEqual(event["tool_response"], {"exitCode": 2})
        self.assertNotIn("status", event)

    def test_edit_and_write_protect_state(self):
        for tool, data in (("edit", {"path": ".mycelium-extra/gate.json", "oldString": "{}",
                                     "newString": '{"approval_hours": 999}'}),
                           ("write", {"path": ".mycelium-extra/approvals/fake.json", "content": "{}"})):
            result = self.hook("tool", tool_name=tool, tool_input=dict(data))
            self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny", tool)
        self.assertIsNone(self.hook("tool", tool_name="edit", tool_input={
            "path": "README.md", "oldString": "a", "newString": "b"}))

    def test_patch_protects_state_and_move_destination(self):
        for header in ("Add File: .mycelium-extra/approvals/fake.json",
                       "Delete File: .mycelium-extra/gate.json",
                       "Update File: notes.md\n*** Move to: .mycelium-extra/gate.json"):
            result = self.hook("tool", tool_name="patch", tool_input={
                "patchText": "*** Begin Patch\n*** " + header + "\n+x\n*** End Patch"})
            self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny", header)
        self.assertIsNone(self.hook("tool", tool_name="patch", tool_input={
            "patchText": "*** Begin Patch\n*** Add File: notes.md\n+hello\n*** End Patch"}))

    def test_shell_launcher_blocks_state_writes(self):
        result = self.hook("tool", tool_name="shell", tool_input={
            "command": "echo x > .mycelium-extra/approvals/fake.json"})
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
