"""Run: python3 skills/iterate/tests/test_method.py

Method mode of tree.py: the frozen evaluator, the baseline and sanity gate, the iteration floor and the arena.
"""

import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import tree  # noqa: E402


class MethodTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.analysis = os.path.join(self.tmp, "analysis", "demo")
        os.makedirs(os.path.join(self.analysis, "bench"))
        self.write("bench/card.md", "metric: auc\n")
        self.write("bench/score.py", "print('auc 0.5')\n")

    def write(self, rel, text):
        with open(os.path.join(self.analysis, rel), "w") as handle:
            handle.write(text)

    def call(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = tree.main(["--analysis", self.analysis] + list(argv))
        return code, out.getvalue()

    def root(self, **plan):
        rows = {"mode": "method", "run-cmd": "python bench/score.py", "readout": "auc", "repair-cap": "2",
                "floor": "2", "card": "bench/card.md"}
        rows.update(plan)
        args = ["add", "base", "--kind", "baseline"]
        for key, value in rows.items():
            if value is not None:
                args += ["--" + key, value]
        return self.call(*args)

    def freeze(self):
        return self.call("freeze-evaluator", "--file", "bench/score.py")

    def finish(self, slug, kind="candidate", parent="base", outcome="same"):
        self.call("add", slug, "--parent", parent, "--kind", kind)
        self.call("run", slug, "--exit", "0")
        return self.call("answer", slug, "--outcome", outcome, "--summary", "s")

    def test_method_rows_are_asked_not_defaulted(self):
        self.root(floor=None, card=None)
        code, text = self.call("stop-check")
        self.assertEqual(code, 3)
        self.assertIn("iteration floor", text)
        self.assertIn("benchmark card", text)
        self.assertIn("no default", text)

    def test_floor_card_and_rubric_belong_to_method_mode(self):
        code, text = self.call("add", "base", "--run-cmd", "x", "--floor", "5")
        self.assertEqual(code, 1)
        self.assertIn("method mode", text)
        code, text = self.root(**{"stop-after": "3"})
        self.assertEqual(code, 1)
        self.assertIn("iteration floor", text)

    def test_freeze_writes_hashes_and_check_sees_a_change(self):
        self.root()
        self.assertEqual(self.freeze()[0], 0)
        events = tree.read_events(tree.tree_path(self.analysis))
        hashes = events[-1]["hashes"]
        self.assertEqual(sorted(hashes), ["bench/card.md", "bench/score.py"])
        self.assertEqual(len(hashes["bench/score.py"]), 64)
        self.assertEqual(self.call("check-evaluator")[0], 0)
        self.write("bench/score.py", "print('auc 0.99')\n")
        code, text = self.call("check-evaluator")
        self.assertEqual(code, 3)
        self.assertIn("score.py (changed)", text)
        os.remove(os.path.join(self.analysis, "bench", "score.py"))
        self.assertIn("(missing)", self.call("check-evaluator")[1])

    def test_second_freeze_needs_refreeze_and_a_note(self):
        self.root()
        self.freeze()
        self.assertEqual(self.freeze()[0], 3)
        self.assertEqual(self.call("freeze-evaluator", "--refreeze")[0], 1)
        self.write("bench/score.py", "print('auc 0.7')\n")
        self.assertEqual(self.call("freeze-evaluator", "--file", "bench/score.py", "--refreeze", "--note",
                                   "user agreed: fixed a typo")[0], 0)
        self.assertEqual(self.call("check-evaluator")[0], 0)

    def test_unfrozen_evaluator_fails_the_check_and_research_trees_refuse_a_freeze(self):
        self.root()
        self.assertEqual(self.call("check-evaluator")[0], 3)
        shutil.rmtree(os.path.join(self.analysis, "plans"))
        self.call("add", "r", "--run-cmd", "x", "--readout", "r", "--repair-cap", "1", "--stop-after", "1",
                  "--stop-rule", "s")
        self.assertEqual(self.call("freeze-evaluator")[0], 3)

    def test_no_run_before_the_evaluator_is_frozen_or_after_it_drifts(self):
        self.root()
        self.call("add", "b", "--parent", "base", "--kind", "baseline")
        code, text = self.call("run", "b", "--exit", "0")
        self.assertEqual(code, 3)
        self.assertIn("not frozen", text)
        self.freeze()
        self.assertEqual(self.call("run", "b", "--exit", "0")[0], 0)
        self.write("bench/card.md", "metric: f1\n")
        self.assertEqual(self.call("run", "b", "--exit", "0")[0], 3)
        self.assertEqual(self.call("answer", "b", "--outcome", "same", "--summary", "s")[0], 3)

    def test_candidates_count_only_after_baseline_and_sanity_ran(self):
        self.root()
        self.freeze()
        self.call("add", "c1", "--parent", "base")
        self.call("run", "c1", "--exit", "0")
        code, text = self.call("answer", "c1", "--outcome", "better", "--summary", "s")
        self.assertEqual(code, 3)
        self.assertIn("baseline", text)
        self.call("run", "base", "--exit", "0")
        code, text = self.call("answer", "c1", "--outcome", "better", "--summary", "s")
        self.assertEqual(code, 3)
        self.assertIn("sanity", text)
        self.finish("sanity1", kind="sanity")
        self.assertEqual(self.call("answer", "c1", "--outcome", "better", "--summary", "s")[0], 0)

    def test_stop_check_names_the_missing_step_then_counts_the_floor(self):
        self.root()
        self.assertIn("not frozen", self.call("stop-check")[1])
        self.freeze()
        self.assertIn("baseline or sanity", self.call("stop-check")[1])
        self.call("run", "base", "--exit", "0")
        self.finish("sanity1", kind="sanity")
        code, text = self.call("stop-check")
        self.assertEqual((code, "0 of 2" in text), (3, True))
        self.finish("c1", outcome="worse")
        self.assertEqual(self.call("stop-check")[0], 3)
        self.finish("c2", outcome="worse")
        code, text = self.call("stop-check")
        self.assertEqual(code, 0)
        self.assertIn("floor met: 2 of 2", text)

    def test_an_answered_baseline_and_sanity_do_not_count_toward_the_floor(self):
        self.root(floor="1")
        self.freeze()
        self.call("run", "base", "--exit", "0")
        self.call("answer", "base", "--outcome", "same", "--summary", "baseline")
        self.finish("sanity1", kind="sanity")
        self.assertEqual(self.call("stop-check")[0], 3)
        self.finish("c1")
        self.assertEqual(self.call("stop-check")[0], 0)

    def test_a_rule_stop_before_the_floor_is_refused_but_the_user_can_stop(self):
        self.root()
        self.freeze()
        self.assertEqual(self.call("stop", "--reason", "rule")[0], 3)
        self.assertEqual(self.call("stop", "--reason", "user")[0], 0)
        self.assertEqual(self.call("stop-check")[0], 0)

    def test_kind_needs_method_mode(self):
        code, text = self.call("add", "base", "--run-cmd", "x", "--kind", "sanity")
        self.assertEqual(code, 1)
        self.assertIn("method mode", text)

    def test_arena_needs_a_rubric_fixed_before_the_runs(self):
        self.root()
        self.freeze()
        self.call("add", "a", "--parent", "base")
        self.call("add", "b", "--parent", "base")
        code, text = self.call("arena", "a", "b", "--winner", "a")
        self.assertEqual(code, 3)
        self.assertIn("rubric", text)
        self.call("run", "a", "--exit", "0")
        self.call("plan", "--rubric", "clarity then cost")
        code, text = self.call("arena", "a", "b", "--winner", "a")
        self.assertEqual(code, 3)
        self.assertIn("after the runs of a", text)

    def test_arena_with_a_rubric_set_first_is_recorded(self):
        self.root(rubric="effect size, then cost")
        self.freeze()
        for slug in ("a", "b"):
            self.call("add", slug, "--parent", "base")
            self.call("run", slug, "--exit", "0")
        self.assertEqual(self.call("arena", "a", "--winner", "a")[0], 1)
        self.assertEqual(self.call("arena", "a", "b", "--winner", "c")[0], 1)
        code, text = self.call("arena", "a", "b", "--winner", "b", "--note", "cheaper")
        self.assertEqual(code, 0)
        self.assertIn("b won over a", text)
        self.assertIn("arena: b won over a", self.call("status")[1])
        self.assertEqual(self.call("status", "--json")[0], 0)

    def test_arena_compares_siblings_only(self):
        self.root(rubric="r")
        self.freeze()
        self.call("add", "a", "--parent", "base")
        self.call("add", "a2", "--parent", "a")
        self.assertEqual(self.call("arena", "a", "a2", "--winner", "a")[0], 3)

    def test_status_shows_the_method_rows(self):
        self.root()
        text = self.call("status")[1]
        self.assertIn("mode method; iteration floor: 2; benchmark card: bench/card.md; evaluator: not frozen", text)
        self.assertIn("baseline", text)

    def test_folder_expands_to_its_files(self):
        self.root()
        os.makedirs(os.path.join(self.analysis, "bench", "splits"))
        self.write("bench/splits/a.tsv", "1\n")
        self.write("bench/splits/b.tsv", "2\n")
        self.call("freeze-evaluator", "--file", "bench/splits")
        hashes = tree.read_events(tree.tree_path(self.analysis))[-1]["hashes"]
        self.assertIn("bench/splits/b.tsv", hashes)
        self.assertEqual(self.call("freeze-evaluator", "--file", "bench/nope", "--refreeze", "--note", "x")[0], 1)


if __name__ == "__main__":
    unittest.main()
