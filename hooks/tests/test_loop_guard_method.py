"""Run: python3 hooks/tests/test_loop_guard_method.py

The loop guard's method-mode parts, as the host runs them (event JSON on stdin): edits to a hashed evaluator
file, a changed evaluator at Stop, and the bridge to a tusoskill-shaped state/state.json.
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
FIXTURE = os.path.join(PLUGIN, "tests", "fixtures", "tusoskill")
STUB = os.path.join(FIXTURE, "scripts", "biomni_method_state.py")
ANALYSIS = "analysis/demo"
STATE_DIR = ".mycelium-extra"


class Base(unittest.TestCase):
    script = os.path.join(tempfile.gettempdir(), "mx-no-such-tusoskill-script.py")

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, STATE_DIR))
        self.loops("block")

    def loops(self, value):
        with open(os.path.join(self.root, STATE_DIR, "gate.json"), "w") as handle:
            json.dump({} if value is None else {"loops": value}, handle)

    def hook(self, action, **event):
        event.setdefault("cwd", self.root)
        env = dict(os.environ, MYCELIUM_TUSOSKILL_SCRIPT=self.script)
        out = subprocess.run([sys.executable, GUARD, action], input=json.dumps(event), stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, universal_newlines=True, env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout) if out.stdout.strip() else {}

    def denied(self, reply):
        return reply.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


class EvaluatorTest(Base):
    def setUp(self):
        super().setUp()
        self.analysis = os.path.join(self.root, ANALYSIS)
        os.makedirs(os.path.join(self.analysis, "bench"))
        for name, text in (("card.md", "metric: auc\n"), ("score.py", "print(1)\n"), ("notes.md", "n\n")):
            with open(os.path.join(self.analysis, "bench", name), "w") as handle:
                handle.write(text)
        self.tree("add", "base", "--kind", "baseline", "--mode", "method", "--run-cmd", "python bench/score.py",
                  "--readout", "auc", "--repair-cap", "2", "--floor", "2", "--card", "bench/card.md")
        self.tree("freeze-evaluator", "--file", "bench/score.py")
        self.score = os.path.join(self.analysis, "bench", "score.py")

    def tree(self, *args):
        out = subprocess.run([sys.executable, TREE, "--analysis", self.analysis] + list(args),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    def edit(self, tool, path, key="file_path", **extra):
        return self.hook("tool", tool_name=tool, tool_input={key: path}, **extra)

    def test_edit_tools_on_a_hashed_file_are_denied(self):
        for tool in ("Write", "Edit", "MultiEdit"):
            reply = self.edit(tool, self.score)
            self.assertTrue(self.denied(reply), tool)
            self.assertIn("bench/score.py", reply["hookSpecificOutput"]["permissionDecisionReason"])
            self.assertIn("freeze-evaluator --refreeze", reply["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertTrue(self.denied(self.edit("NotebookEdit", self.score, key="notebook_path")))
        card = os.path.join(self.analysis, "bench", "card.md")
        self.assertTrue(self.denied(self.edit("Edit", card)))  # the card is hashed too

    def test_a_relative_path_resolves_against_the_event_cwd(self):
        self.assertTrue(self.denied(self.edit("Edit", "bench/score.py", cwd=self.analysis)))
        self.assertTrue(self.denied(self.edit("Edit", "../demo/bench/./score.py", cwd=self.analysis)))

    def test_other_files_and_other_tools_pass(self):
        self.assertEqual(self.edit("Edit", os.path.join(self.analysis, "bench", "notes.md")), {})
        self.assertEqual(self.edit("Edit", os.path.join(self.analysis, "code", "new.py")), {})
        self.assertEqual(self.hook("tool", tool_name="Read", tool_input={"file_path": self.score}), {})

    def test_a_symlink_to_a_hashed_file_is_caught(self):
        link = os.path.join(self.root, "link.py")
        os.symlink(self.score, link)
        self.assertTrue(self.denied(self.edit("Edit", link)))

    def test_codex_and_opencode_names(self):
        patch = "*** Begin Patch\n*** Update File: {}\n@@\n-print(1)\n+print(2)\n*** End Patch\n".format(self.score)
        self.assertTrue(self.denied(self.hook("tool", tool_name="apply_patch", tool_input={"command": patch})))
        move = "*** Begin Patch\n*** Update File: x.py\n*** Move to: {}\n*** End Patch\n".format(self.score)
        self.assertTrue(self.denied(self.hook("tool", tool_name="apply_patch", tool_input={"command": move})))
        other = "*** Begin Patch\n*** Add File: {}/code/x.py\n+1\n*** End Patch\n".format(self.analysis)
        self.assertEqual(self.hook("tool", tool_name="apply_patch", tool_input={"command": other}), {})
        self.assertTrue(self.denied(self.hook("tool", tool_name="edit", tool_input={"filePath": self.score})))
        self.assertTrue(self.denied(self.hook("tool", tool_name="write", tool_input={"filePath": self.score})))
        self.assertTrue(self.denied(self.hook("tool", tool_name="patch", tool_input={"patchText": patch})))

    def test_warn_notes_and_off_is_silent(self):
        self.loops("warn")
        reply = self.edit("Write", self.score)
        self.assertFalse(self.denied(reply))
        self.assertIn("hashed evaluator", reply["systemMessage"])
        self.loops("off")
        self.assertEqual(self.edit("Write", self.score), {})

    def test_no_freeze_means_no_hashed_files(self):
        os.remove(os.path.join(self.analysis, "plans", "tree.jsonl"))
        self.tree("add", "base", "--run-cmd", "x", "--readout", "r", "--repair-cap", "1", "--stop-after", "1",
                  "--stop-rule", "s")
        self.assertEqual(self.edit("Write", self.score), {})

    def test_stop_reports_a_changed_evaluator_once(self):
        self.assertEqual(self.hook("stop", session_id="s").get("decision"), "block")  # the floor is not met
        with open(self.score, "w") as handle:
            handle.write("print(99)\n")
        reply = self.hook("stop", session_id="s2")
        self.assertEqual(reply["decision"], "block")
        self.assertIn("frozen evaluator changed", reply["reason"])
        self.assertIn("bench/score.py changed", reply["reason"])
        self.assertEqual(self.hook("stop", session_id="s3"), {})


class BridgeTest(Base):
    script = STUB

    def setUp(self):
        super().setUp()
        self.run_dir = os.path.join(self.root, "method")
        shutil.copytree(os.path.join(FIXTURE, "state"), os.path.join(self.run_dir, "state"))

    def state(self, **change):
        path = os.path.join(self.run_dir, "state", "state.json")
        with open(path) as handle:
            data = json.load(handle)
        data.update(change)
        with open(path, "w") as handle:
            json.dump(data, handle)

    def test_exit_three_blocks_once_and_names_the_user_escape(self):
        reply = self.hook("stop", session_id="s")
        self.assertEqual(reply["decision"], "block")
        self.assertIn("STOP-GATE: iteration=3/50", reply["reason"])
        self.assertIn("record-blocker", reply["reason"])
        self.assertIn("--kind user", reply["reason"])
        self.assertIn("the user says to stop", reply["reason"])
        self.assertEqual(self.hook("stop", session_id="s", stop_hook_active=True), {})
        self.assertEqual(self.hook("stop", session_id="s2"), {})  # state unchanged since the report
        self.state(iteration=4)
        self.assertEqual(self.hook("stop", session_id="s3")["decision"], "block")

    def test_a_recorded_user_blocker_passes(self):
        out = subprocess.run([sys.executable, STUB, "record-blocker", "--root", self.run_dir, "--kind", "user",
                              "--detail", "the user said stop"], stdout=subprocess.PIPE)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(self.hook("stop", session_id="s"), {})

    def test_the_floor_reached_passes(self):
        self.state(iteration=50)
        self.assertEqual(self.hook("stop", session_id="s"), {})

    def test_a_missing_script_is_silent(self):
        BridgeTest.script = os.path.join(self.root, "nope.py")
        self.addCleanup(setattr, BridgeTest, "script", STUB)
        self.assertEqual(self.hook("stop", session_id="s"), {})

    def test_a_state_file_of_another_shape_is_silent(self):
        self.state(max_iterations="fifty")
        self.assertEqual(self.hook("stop", session_id="s"), {})
        self.state(max_iterations=50, run_id=None)
        self.assertEqual(self.hook("stop", session_id="s"), {})

    def test_warn_notes_and_off_is_silent(self):
        self.loops("warn")
        reply = self.hook("stop", session_id="s")
        self.assertNotIn("decision", reply)
        self.assertIn("STOP-GATE", reply["systemMessage"])
        self.loops("off")
        self.assertEqual(self.hook("stop", session_id="s9"), {})

    def test_a_state_with_null_counters_is_silent(self):
        self.state(iteration=None)
        self.assertEqual(self.hook("stop", session_id="s"), {})

    def test_a_nested_run_folder_is_found(self):
        shutil.rmtree(self.run_dir)
        nested = os.path.join(self.root, "analysis", "m2")
        shutil.copytree(os.path.join(FIXTURE, "state"), os.path.join(nested, "state"))
        self.assertIn("analysis/m2", self.hook("stop", session_id="s")["reason"])

    def test_an_unchanged_state_is_not_rechecked(self):
        counter = os.path.join(self.root, "calls.txt")
        stub = os.path.join(self.root, "counting.py")
        with open(stub, "w") as handle:
            handle.write("import sys\nopen({!r}, 'a').write('x')\nprint('{{}}')\nsys.exit(3)\n".format(counter))
        BridgeTest.script = stub
        self.addCleanup(setattr, BridgeTest, "script", STUB)
        self.assertEqual(self.hook("stop", session_id="s")["decision"], "block")
        self.assertEqual(self.hook("stop", session_id="s2"), {})
        self.assertEqual(self.hook("stop", session_id="s3"), {})
        with open(counter) as handle:
            self.assertEqual(handle.read(), "x")
        with open(os.path.join(self.run_dir, "state", "ledger.jsonl"), "w") as handle:
            handle.write("{}\n")  # a ledger write is a state change
        self.assertEqual(self.hook("stop", session_id="s4")["decision"], "block")

    def test_runs_past_the_deadline_are_named_not_run(self):
        sys.path.insert(0, os.path.join(PLUGIN, "hooks"))
        import loop_guard
        os.environ["MYCELIUM_TUSOSKILL_SCRIPT"] = STUB
        self.addCleanup(os.environ.pop, "MYCELIUM_TUSOSKILL_SCRIPT")
        lines, unchecked, slow = loop_guard.tusoskill_lines(self.root, deadline=0)  # long past
        self.assertEqual((lines, unchecked, slow), ([], ["method"], []))
        lines, unchecked, slow = loop_guard.tusoskill_lines(self.root)  # not recorded as checked, so it runs now
        self.assertEqual(len(lines), 1)
        self.assertEqual((unchecked, slow), ([], []))

    def test_a_slow_check_is_cut_off_and_named(self):
        sys.path.insert(0, os.path.join(PLUGIN, "hooks"))
        import loop_guard
        stub = os.path.join(self.root, "slow.py")
        with open(stub, "w") as handle:
            handle.write("import time\ntime.sleep(30)\n")
        os.environ["MYCELIUM_TUSOSKILL_SCRIPT"] = stub
        self.addCleanup(os.environ.pop, "MYCELIUM_TUSOSKILL_SCRIPT")
        import time
        start = time.monotonic()
        lines, unchecked, slow = loop_guard.tusoskill_lines(self.root, deadline=time.monotonic() + 1)
        self.assertLess(time.monotonic() - start, 5)
        self.assertEqual((lines, unchecked, slow), ([], [], ["method"]))
        # the timed-out state is recorded, so an unchanged run does not cost the budget again
        start = time.monotonic()
        self.assertEqual(loop_guard.tusoskill_lines(self.root, deadline=time.monotonic() + 1), ([], [], []))
        self.assertLess(time.monotonic() - start, 0.5)


if __name__ == "__main__":
    unittest.main()
