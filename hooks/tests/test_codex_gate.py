"""Run: python3 hooks/tests/test_codex_gate.py"""
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


class CodexGateTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, ".mycelium-extra"))
        with open(os.path.join(self.root, ".mycelium-extra", "gate.json"), "w") as f:
            json.dump({}, f)

    def hook(self, action, **payload):
        payload.update(cwd=self.root, session_id="codex-test")
        result = subprocess.run(
            [sys.executable, os.path.join(PLUGIN, "hooks", "gate_run.py"),
             "--host", "codex", action], input=json.dumps(payload).encode("utf-8"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else None

    def test_approval_and_receipts(self):
        bash = dict(tool_name="Bash", tool_input={"command": "python analysis/x.py"})
        blocked = self.hook("tool", **bash)
        self.assertEqual(blocked["hookSpecificOutput"]["permissionDecision"], "deny")
        plan = "## Plan\n| 1 | run `analysis/x.py` | repo | check |\n\nPlan status: READY"
        notice = self.hook("stop", last_assistant_message=plan)
        digest = notice["systemMessage"].split("approve plan ")[1][:8]
        self.hook("prompt", prompt="approve plan " + digest)
        self.assertIsNone(self.hook("tool", **bash))
        for response in ({"exit_code": 0}, {"exit_code": 7}, {"output": "no exit status"}):
            self.hook("post", hook_event_name="PostToolUse", tool_response=response, **bash)
        with open(os.path.join(self.root, ".mycelium-extra", "receipts.jsonl")) as f:
            receipts = [json.loads(line) for line in f]
        self.assertEqual([r["exit_status"] for r in receipts], [0, 7, "unknown"])
        self.assertTrue(all(r["host"] == "codex" for r in receipts))

    def test_patch_protects_state_and_move_destination(self):
        for header in ("Add File: .mycelium-extra/approvals/fake.json",
                       "Delete File: .mycelium-extra/gate.json",
                       "Update File: .mycelium-extra/gate.json",
                       "Update File: notes.md\n*** Move to: .mycelium-extra/gate.json"):
            result = self.hook("tool", tool_name="apply_patch",
                               tool_input={"command": "*** Begin Patch\n*** " + header +
                                           "\n+x\n*** End Patch"})
            self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIsNone(self.hook("tool", tool_name="apply_patch", tool_input={
            "command": "*** Begin Patch\n*** Add File: notes.md\n+hello\n*** End Patch"}))

    def test_codex_missing_status_is_not_success(self):
        for response in (None, False, {"exit_code": False},
                         "Process exited with code 0", '{"exit_code": 0}'):
            self.assertEqual(gate.exit_status({"host": "codex", "hook_event_name": "PostToolUse",
                                              "tool_response": response})[0], "unknown")

    def test_patch_paths_resolve_against_cwd_and_symlinks(self):
        os.mkdir(os.path.join(self.root, "sub"))
        os.symlink(os.path.join(self.root, ".mycelium-extra"), os.path.join(self.root, "alias"))
        for path in ("../.mycelium-extra/gate.json", "../alias/gate.json"):
            result = gate.on_tool({"cwd": os.path.join(self.root, "sub"),
                                   "tool_name": "apply_patch", "tool_input": {
                                       "command": "*** Begin Patch\n*** Delete File: " + path +
                                                  "\n*** End Patch"}}, self.root, {})
            self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
