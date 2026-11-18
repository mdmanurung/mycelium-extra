"""Run: python3 hooks/tests/test_loop_guard.py

End to end with a temporary git repository: the loop guard as the host runs it (event JSON on stdin).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GUARD = os.path.join(PLUGIN, "hooks", "loop_guard.py")
TREE = os.path.join(PLUGIN, "skills", "iterate", "scripts", "tree.py")
ANALYSIS = "analysis/demo"


class LoopGuardTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.git("init", "-q", "-b", "main")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "init")
        os.makedirs(os.path.join(self.root, ".mycelium-extra"))
        self.loops("block")

    def git(self, *args):
        subprocess.run(["git", "-C", self.root] + list(args), check=True, stdout=subprocess.PIPE)

    def loops(self, value):
        config = {} if value is None else {"loops": value}
        with open(os.path.join(self.root, ".mycelium-extra", "gate.json"), "w") as handle:
            json.dump(config, handle)

    def tree(self, *args):
        out = subprocess.run([sys.executable, TREE, "--analysis", os.path.join(self.root, ANALYSIS)] + list(args),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        return out.returncode, out.stdout

    def freeze_a(self):
        self.tree("add", "base", "--run-cmd", "python code/run.py", "--repair-cap", "2", "--stop-after", "3")
        self.tree("add", "a", "--parent", "base")
        self.tree("run", "a", "--exit", "0")
        self.tree("answer", "a", "--outcome", "worse", "--summary", "no gain")
        self.git("checkout", "-q", "-b", "exp/a")

    def hook(self, action, **event):
        event.setdefault("cwd", self.root)
        out = subprocess.run([sys.executable, GUARD, action], input=json.dumps(event), stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout) if out.stdout.strip() else {}

    def bash(self, command, **extra):
        return self.hook("tool", tool_name="Bash", tool_input={"command": command}, **extra)

    def denied(self, reply):
        return reply.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_off_by_default_and_without_gate_json(self):
        self.freeze_a()
        self.loops(None)
        self.assertEqual(self.bash("git commit -m x"), {})
        self.assertEqual(self.hook("stop", session_id="s"), {})
        self.loops("off")
        self.assertEqual(self.bash("git commit -m x"), {})
        os.remove(os.path.join(self.root, ".mycelium-extra", "gate.json"))
        self.assertEqual(self.bash("git commit -m x"), {})

    def test_block_refuses_commit_on_a_frozen_branch_only(self):
        self.freeze_a()
        reply = self.bash("git commit -m x")
        self.assertTrue(self.denied(reply))
        self.assertIn("exp/a", reply["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertTrue(self.denied(self.bash("cd . && git -C . commit --amend")))
        self.assertEqual(self.bash("git status"), {})
        self.git("checkout", "-q", "-b", "exp/b")
        self.assertEqual(self.bash("git commit -m x"), {})

    def test_warn_notes_and_allows(self):
        self.freeze_a()
        self.loops("warn")
        reply = self.bash("git commit -m x")
        self.assertFalse(self.denied(reply))
        self.assertIn("frozen", reply["systemMessage"])

    def test_env_prefixed_fixed_command(self):
        self.freeze_a()
        self.git("checkout", "-q", "main")
        self.assertTrue(self.denied(self.bash("SEED=2 python code/run.py")))
        self.assertTrue(self.denied(self.bash("env SEED=2 python code/run.py --x")))
        self.assertEqual(self.bash("python code/run.py"), {})
        self.assertEqual(self.bash("SEED=2 python code/other.py"), {})
        self.loops("warn")
        self.assertFalse(self.denied(self.bash("SEED=2 python code/run.py")))
        self.assertIn("env", self.bash("SEED=2 python code/run.py")["systemMessage"])

    def test_stop_blocks_once_then_honours_stop_hook_active(self):
        self.freeze_a()
        first = self.hook("stop", session_id="s")
        self.assertEqual(first["decision"], "block")
        self.assertIn("tree.py", first["reason"])
        self.assertIn("--reason user", first["reason"])
        self.assertIn("warn", first["reason"])
        self.assertEqual(self.hook("stop", session_id="s", stop_hook_active=True), {})

    def test_stop_escapes(self):
        self.freeze_a()
        self.assertEqual(self.tree("stop", "--reason", "user")[0], 0)
        self.assertEqual(self.hook("stop", session_id="s"), {})

    def test_stop_warn_does_not_block_and_rule_met_passes(self):
        self.freeze_a()
        self.loops("warn")
        reply = self.hook("stop", session_id="s")
        self.assertNotIn("decision", reply)
        self.assertIn("research loop is not finished", reply["systemMessage"])
        self.loops("block")
        for slug in ("b", "c"):
            self.tree("add", slug, "--parent", "base")
            self.tree("run", slug, "--exit", "0")
            self.tree("answer", slug, "--outcome", "same", "--summary", "s")
        self.assertEqual(self.hook("stop", session_id="s"), {})

    def test_no_tree_and_unreadable_events_are_silent(self):
        self.assertEqual(self.hook("stop", session_id="s"), {})
        self.assertEqual(self.bash("git commit -m x"), {})
        out = subprocess.run([sys.executable, GUARD, "tool"], input="not json", stdout=subprocess.PIPE,
                             universal_newlines=True)
        self.assertEqual((out.returncode, out.stdout), (0, ""))

    def test_codex_and_opencode_shapes(self):
        self.freeze_a()
        shell = self.hook("tool", tool_name="exec_command", tool_input={"cmd": "git commit -m x"})
        self.assertTrue(self.denied(shell))
        out = subprocess.run([sys.executable, GUARD, "--host", "opencode", "tool"], universal_newlines=True,
                             input=json.dumps({"tool_name": "shell", "tool_input": {"command": "git commit -m x"},
                                               "cwd": self.root}), stdout=subprocess.PIPE)
        self.assertTrue(self.denied(json.loads(out.stdout)))


if __name__ == "__main__":
    unittest.main()
