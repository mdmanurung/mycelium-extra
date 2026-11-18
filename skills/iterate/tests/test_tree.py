"""Run: python3 skills/iterate/tests/test_tree.py"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "tree.py")
sys.path.insert(0, os.path.dirname(SCRIPT))
import tree  # noqa: E402


class TreeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.analysis = os.path.join(self.tmp, "analysis", "demo")
        os.makedirs(self.analysis)

    def call(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = tree.main(["--analysis", self.analysis] + list(argv))
        return code, out.getvalue()

    def root(self, **plan):
        rows = {"run-cmd": "python code/run.py", "readout": "auc", "repair-cap": "2", "stop-after": "3"}
        rows.update(plan)
        args = ["add", "base"]
        for key, value in rows.items():
            if value is not None:
                args += ["--" + key, value]
        return self.call(*args)

    def answer(self, slug, outcome):
        self.call("add", slug, "--parent", "base")
        self.call("run", slug, "--exit", "0")
        return self.call("answer", slug, "--outcome", outcome, "--summary", "s")

    def test_no_tree_exits_two(self):
        self.assertEqual(self.call("stop-check")[0], 2)
        self.assertEqual(self.call("status")[0], 2)

    def test_log_is_append_only_json_lines(self):
        self.root()
        self.call("add", "a", "--parent", "base")
        self.call("run", "a", "--exit", "0", "--run-id", "r1", "--readout-value", "0.8")
        with open(os.path.join(self.analysis, "plans", "tree.jsonl")) as handle:
            events = [json.loads(line) for line in handle]
        self.assertEqual([e["ev"] for e in events], ["add", "add", "run"])
        self.assertEqual(events[0]["run_cmd"], "python code/run.py")
        self.assertEqual(events[2]["run_id"], "r1")

    def test_replay_gives_node_states(self):
        self.root()
        self.call("add", "a", "--parent", "base")
        self.call("add", "b", "--parent", "base")
        self.call("run", "a", "--exit", "1")
        self.call("run", "b", "--exit", "0")
        self.call("answer", "b", "--outcome", "better", "--summary", "gain", "--figure", "figs/b.png")
        state = tree.load(self.analysis)["nodes"]
        self.assertEqual((state["base"]["state"], state["a"]["state"], state["b"]["state"]),
                         ("new", "failed", "frozen"))
        self.assertIn("figs/b.png", self.call("summary")[1])

    def test_frozen_list_and_refusals(self):
        self.root()
        self.answer("a", "same")
        self.assertEqual(self.call("frozen"), (0, "exp/a\n"))
        self.assertEqual(self.call("run", "a", "--exit", "0")[0], 3)
        self.assertEqual(self.call("repair", "a")[0], 3)
        self.assertEqual(self.call("answer", "a", "--outcome", "better", "--summary", "x")[0], 3)

    def test_failed_run_answers_nothing(self):
        self.root()
        self.call("add", "a", "--parent", "base")
        self.call("run", "a", "--exit", "137")
        code, text = self.call("answer", "a", "--outcome", "better", "--summary", "x")
        self.assertEqual(code, 3)
        self.assertIn("repair", text)

    def test_repair_cap_stops_at_the_user_cap(self):
        self.root(**{"repair-cap": "2"})
        self.call("add", "a", "--parent", "base")
        self.call("run", "a", "--exit", "1")
        self.assertEqual(self.call("repair", "a")[0], 0)
        self.call("run", "a", "--exit", "1")
        self.assertEqual(self.call("repair", "a")[0], 0)
        self.call("run", "a", "--exit", "1")
        code, text = self.call("repair", "a")
        self.assertEqual(code, 3)
        self.assertIn("Ask the user", text)
        self.assertEqual(tree.load(self.analysis)["nodes"]["a"]["repairs"], 2)

    def test_missing_cap_is_asked_not_defaulted(self):
        self.root(**{"repair-cap": None})
        self.call("add", "a", "--parent", "base")
        self.call("run", "a", "--exit", "1")
        code, text = self.call("repair", "a")
        self.assertEqual(code, 3)
        self.assertIn("no repair cap", text)

    def test_stop_check_missing_rule_exits_three_and_asks(self):
        self.root(**{"stop-after": None})
        code, text = self.call("stop-check")
        self.assertEqual(code, 3)
        self.assertIn("Ask the user", text)
        self.assertIn("stop rule", text)
        self.root_missing_cmd()

    def root_missing_cmd(self):
        shutil.rmtree(os.path.join(self.analysis, "plans"))
        self.root(**{"run-cmd": None})
        code, text = self.call("stop-check")
        self.assertEqual(code, 3)
        self.assertIn("run command", text)

    def test_stop_check_rule_counts_trailing_answers_not_better(self):
        self.root(**{"stop-after": "2"})
        self.answer("a", "worse")
        self.assertEqual(self.call("stop-check")[0], 3)
        self.answer("b", "same")
        self.assertEqual(self.call("stop-check")[0], 0)

    def test_better_answer_resets_the_streak(self):
        self.root(**{"stop-after": "2"})
        self.answer("a", "worse")
        self.answer("b", "better")
        self.answer("c", "worse")
        self.assertEqual(self.call("stop-check")[0], 3)

    def test_recorded_stop_exits_zero(self):
        self.root()
        self.assertEqual(self.call("stop-check")[0], 3)
        self.assertEqual(self.call("stop", "--reason", "user")[0], 0)
        code, text = self.call("stop-check")
        self.assertEqual(code, 0)
        self.assertIn("user", text)

    def test_children_cannot_set_plan_rows_and_one_root(self):
        self.root()
        self.assertEqual(self.call("add", "x", "--parent", "base", "--repair-cap", "9")[0], 1)
        self.assertEqual(self.call("add", "y")[0], 1)
        self.assertEqual(self.call("add", "z", "--parent", "nope")[0], 1)

    def test_corrupt_log_is_exit_two(self):
        self.root()
        with open(os.path.join(self.analysis, "plans", "tree.jsonl"), "a") as handle:
            handle.write("not json\n")
        self.assertEqual(self.call("stop-check")[0], 2)

    def test_run_cites_a_receipt_line(self):
        state = os.path.join(self.tmp, ".mycelium-extra")
        os.makedirs(state)
        with open(os.path.join(state, "receipts.jsonl"), "w") as handle:
            handle.write(json.dumps({"exit_status": 1}) + "\n" + json.dumps({"exit_status": 0}) + "\n")
        self.root()
        self.call("add", "a", "--parent", "base")
        self.assertEqual(self.call("run", "a", "--receipt", "9")[0], 1)
        self.call("run", "a", "--receipt", "1")
        self.assertEqual(tree.load(self.analysis)["nodes"]["a"]["state"], "failed")
        self.call("run", "a", "--receipt", "2")
        self.assertEqual(tree.load(self.analysis)["nodes"]["a"]["state"], "ran")

    def test_runs_through_the_launcher_from_stdin(self):
        mxpy = os.path.join(HERE, "..", "..", "..", "hooks", "mxpy")
        with open(SCRIPT, "rb") as source:
            result = subprocess.run(["/bin/sh", mxpy, "-", "--analysis", self.analysis, "stop-check"], stdin=source,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 2, result.stderr)


if __name__ == "__main__":
    unittest.main()
