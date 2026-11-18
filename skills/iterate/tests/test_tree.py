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
        rows = {"run-cmd": "python code/run.py", "readout": "auc", "repair-cap": "2", "stop-after": "3",
                "stop-rule": "stop after 3 not better"}
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

    def append_raw(self, text):
        with open(os.path.join(self.analysis, "plans", "tree.jsonl"), "a") as handle:
            handle.write(text)

    def test_replay_ignores_events_that_break_a_frozen_node(self):
        self.root()
        self.answer("a", "worse")
        self.append_raw(json.dumps({"ev": "add", "node": "a", "parent": "base"}) + "\n")
        self.append_raw(json.dumps({"ev": "run", "node": "a", "exit": 1}) + "\n")
        self.append_raw(json.dumps({"ev": "answer", "node": "a", "outcome": "better", "summary": "x"}) + "\n")
        node = tree.load(self.analysis)["nodes"]["a"]
        self.assertEqual((node["state"], node["answer"]["outcome"], len(node["runs"])), ("frozen", "worse", 1))
        self.assertEqual(tree.frozen_branches(tree.load(self.analysis)), ["exp/a"])

    def test_plan_fills_rows_the_root_lacked(self):
        self.root(**{"run-cmd": None, "readout": None, "repair-cap": None})
        self.assertEqual(self.call("stop-check")[0], 3)
        self.assertEqual(self.call("plan")[0], 1)
        code, text = self.call("plan", "--run-cmd", "python code/run.py", "--readout", "auc", "--repair-cap", "0")
        self.assertEqual(code, 0, text)
        self.assertEqual(self.call("add", "a", "--parent", "base")[0], 0)
        plan = tree.load(self.analysis)["plan"]
        self.assertEqual((plan["run_cmd"], plan["repair_cap"], plan["stop_after"]), ("python code/run.py", 0, 3))
        self.assertEqual(self.call("plan", "--repair-cap", "5")[0], 0)
        self.assertEqual(tree.load(self.analysis)["plan"]["repair_cap"], 5)

    def test_readout_and_stop_rule_words_are_required_rows(self):
        self.root(readout=None)
        self.assertIn("readout", self.call("stop-check")[1])
        shutil.rmtree(os.path.join(self.analysis, "plans"))
        code, text = self.root(**{"stop-rule": None})
        self.assertIn("stop rule", text)
        self.assertEqual(self.call("stop-check")[0], 3)

    def test_slug_must_make_a_git_branch(self):
        self.root()
        for slug in ("a..b", "x.lock", "x.", "_x", ".x"):
            self.assertEqual(self.call("add", slug, "--parent", "base")[0], 1, slug)
        self.assertEqual(self.call("add", "v1.2_x-y", "--parent", "base")[0], 0)

    def test_repair_cap_zero_means_no_repairs(self):
        self.root(**{"repair-cap": "0"})
        self.call("add", "a", "--parent", "base")
        self.call("run", "a", "--exit", "1")
        self.assertEqual(self.call("repair", "a")[0], 3)
        self.assertEqual(self.call("add", "b", "--parent", "base", "--repair-cap", "-1")[0], 1)

    def test_repair_needs_a_run_between_repairs(self):
        self.root(**{"repair-cap": "3"})
        self.call("add", "a", "--parent", "base")
        self.call("run", "a", "--exit", "1")
        self.assertEqual(self.call("repair", "a")[0], 0)
        self.assertEqual(self.call("repair", "a")[0], 3)
        self.assertEqual(tree.load(self.analysis)["nodes"]["a"]["repairs"], 1)

    def test_a_node_added_after_a_stop_resumes_the_loop(self):
        self.root()
        self.call("stop", "--reason", "user")
        self.assertEqual(self.call("stop-check")[0], 0)
        self.call("add", "c", "--parent", "base")
        self.assertEqual(self.call("stop-check")[0], 3)

    def test_bad_field_types_are_exit_two_not_a_traceback(self):
        self.root()
        for event in ({"ev": "run", "node": ["a"]}, {"ev": "add", "node": "z", "stop_after": "3"},
                      {"ev": "stop", "note": 5}, {"ev": "answer", "node": "a", "figures": [1]}):
            shutil.copy(os.path.join(self.analysis, "plans", "tree.jsonl"), os.path.join(self.tmp, "good"))
            self.append_raw(json.dumps(event) + "\n")
            self.assertEqual(self.call("stop-check")[0], 2, event)
            self.assertEqual(self.call("status")[0], 2, event)
            shutil.copy(os.path.join(self.tmp, "good"), os.path.join(self.analysis, "plans", "tree.jsonl"))

    def test_unfinished_last_line_is_dropped_and_the_log_recovers(self):
        self.root()
        self.append_raw('{"ev": "run", "node": "ba')
        self.assertEqual(self.call("stop-check")[0], 3)
        self.assertEqual(self.call("add", "a", "--parent", "base")[0], 0)
        with open(os.path.join(self.analysis, "plans", "tree.jsonl")) as handle:
            self.assertEqual([json.loads(line)["ev"] for line in handle], ["add", "add"])

    def test_concurrent_answers_record_one(self):
        self.root()
        self.call("add", "a", "--parent", "base")
        self.call("run", "a", "--exit", "0")
        procs = [subprocess.Popen([sys.executable, SCRIPT, "--analysis", self.analysis, "answer", "a", "--outcome",
                                   "better", "--summary", str(n)], stdout=subprocess.PIPE) for n in range(6)]
        codes = sorted((proc.communicate(), proc.returncode)[1] for proc in procs)
        self.assertEqual(codes, [0] + [3] * 5)

    def receipts(self, *statuses):
        state = os.path.join(self.tmp, ".mycelium-extra")
        os.makedirs(state, exist_ok=True)
        with open(os.path.join(state, "receipts.jsonl"), "w") as handle:
            for status in statuses:
                handle.write(json.dumps({"exit_status": status}) + "\n")
        return os.path.join(state, "receipts.jsonl")

    def test_stop_rule_in_words_is_a_plan_row_the_tree_cannot_judge(self):
        code, text = self.root(**{"stop-after": None, "stop-rule": "stop when AUC > 0.9"})
        self.assertEqual(code, 0)
        self.assertNotIn("missing", text)
        status = self.call("status")[1]
        self.assertNotIn("not set", status)
        self.assertIn("stop rule: stop when AUC > 0.9", status)
        code, text = self.call("stop-check")
        self.assertEqual(code, 3)
        self.assertIn("cannot judge", text)
        self.assertIn("Ask the user", text)
        self.assertNotIn("has no stop rule", text)
        self.answer("a", "better")
        self.assertEqual(self.call("stop-check")[0], 3)
        self.assertEqual(self.call("stop", "--reason", "rule")[0], 0)
        self.assertEqual(self.call("stop-check")[0], 0)

    def test_stop_count_without_words_is_still_a_missing_row(self):
        code, text = self.root(**{"stop-rule": None})
        self.assertIn("missing plan rows: stop rule", text)

    def test_run_status_is_kept_when_the_receipts_file_is_gone(self):
        path = self.receipts(0, 1)
        self.root()
        self.call("add", "a", "--parent", "base")
        self.call("add", "b", "--parent", "base")
        self.call("run", "a", "--receipt", "1")
        self.call("run", "b", "--receipt", "2")
        os.remove(path)
        nodes = tree.load(self.analysis)["nodes"]
        self.assertEqual((nodes["a"]["state"], nodes["b"]["state"]), ("ran", "failed"))
        self.assertEqual(self.call("answer", "a", "--outcome", "better", "--summary", "s")[0], 0)

    def test_receipts_of_a_folder_above_the_repository_are_not_read(self):
        outer = self.receipts(1)  # an unrelated project's receipts, one folder above the repository
        repo = os.path.join(self.tmp, "repo")
        self.analysis = os.path.join(repo, "analysis", "demo")
        os.makedirs(self.analysis)
        os.makedirs(os.path.join(repo, ".mycelium-extra"))  # the repository's own receipts are gone
        self.root()
        self.call("add", "c", "--parent", "base")
        code, text = self.call("run", "c", "--receipt", "1")
        self.assertEqual(code, 1, text)
        self.assertEqual(tree.load(self.analysis)["nodes"]["c"]["state"], "new")
        self.assertIsNone(tree.find_receipts(self.analysis))
        self.assertTrue(os.path.isfile(outer))

    def test_old_run_event_with_no_receipt_is_unknown_not_failed(self):
        self.root()
        self.call("add", "a", "--parent", "base")
        self.append_raw(json.dumps({"ev": "run", "node": "a", "receipt": 4}) + "\n")
        self.assertEqual(tree.load(self.analysis)["nodes"]["a"]["state"], "unknown")
        self.assertIn("[unknown]", self.call("status")[1])

    def test_receipt_without_an_integer_exit_status_is_unknown_and_spends_no_repair(self):
        self.receipts("unknown")
        self.root()
        self.call("add", "a", "--parent", "base")
        code, text = self.call("run", "a", "--receipt", "1", "--exit", "0")
        self.assertEqual(code, 0)
        self.assertIn("recorded for a: unknown", text)
        self.assertEqual(tree.load(self.analysis)["nodes"]["a"]["state"], "unknown")
        self.assertIn("[unknown]", self.call("status")[1])
        self.assertEqual(self.call("repair", "a")[0], 3)
        code, text = self.call("answer", "a", "--outcome", "better", "--summary", "s")
        self.assertEqual(code, 3)
        self.assertIn("unknown exit status", text)
        self.assertEqual(tree.load(self.analysis)["nodes"]["a"]["repairs"], 0)
        self.assertEqual(self.call("run", "a", "--exit", "0")[0], 0)
        self.assertEqual(self.call("answer", "a", "--outcome", "better", "--summary", "s")[0], 0)


if __name__ == "__main__":
    unittest.main()
