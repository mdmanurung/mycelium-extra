"""Run: python3 hooks/tests/test_plantable.py

hooks/plantable.py: the plan table's grant cells, paths, commands, rows and covered scripts.
Every name must also stay reachable as `gate.<name>`, the same object."""

import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.dont_write_bytecode = True
import gate  # noqa: E402
import plantable as pt  # noqa: E402

CONFIG = {"gated_paths": ["analysis/**"], "gated_commands": ["sbatch", "snakemake", "nextflow"]}
PLAN = """## Plan

| # | Step | Choice | Source | Validation |
|---|------|--------|--------|------------|
| 1 | run `analysis/a/fit.py` | model A | repo: docs/m.md | check `analysis/a/out/x.tsv` |
| 2 | run `snakemake` | none | human-stated | rows match |

Plan status: READY
"""


class PlanTable(unittest.TestCase):
    def test_only_step_cells_grant(self):
        table = pt.plan_table(PLAN)
        self.assertIn("analysis/a/fit.py", table)
        self.assertIn("snakemake", table)
        self.assertNotIn("x.tsv", table)
        self.assertNotIn("docs/m.md", table)

    def test_every_cell_keeps_all_but_source(self):
        table = pt.plan_table(PLAN, True)
        self.assertIn("x.tsv", table)
        self.assertNotIn("human-stated", table)

    def test_no_table_gives_nothing(self):
        self.assertEqual(pt.plan_table("run analysis/a/fit.py in prose"), "")

    def test_escaped_pipe_stays_in_its_cell(self):
        text = "| Step | Source |\n|---|---|\n| run `a\\|b` | s |\n"
        self.assertIn("a|b", pt.plan_table(text))

    def test_names_command_is_a_whole_word(self):
        self.assertTrue(pt.names_command("snakemake", "run snakemake now"))
        self.assertFalse(pt.names_command("snakemake", "run snakemakes now"))


class PlanPaths(unittest.TestCase):
    def test_plan_paths_need_a_slash(self):
        self.assertEqual(pt.plan_paths("run ./analysis/a/fit.py, then fit.py and b/c/"),
                         frozenset({"analysis/a/fit.py", "b/c"}))

    def test_plan_paths_in_makes_root_paths_relative(self):
        self.assertEqual(pt.plan_paths_in("/r", "run /r/analysis/a/x.py"), frozenset({"analysis/a/x.py"}))

    def test_a_named_folder_covers_what_is_below(self):
        self.assertTrue(pt.path_in_plan("/r", "analysis/a/x.py", "run analysis/a/"))
        self.assertFalse(pt.path_in_plan("/r", "analysis/b/x.py", "run analysis/a/"))

    def test_grants_are_gated_paths_and_commands(self):
        paths, commands = pt.plan_grants("/r", PLAN, CONFIG)
        self.assertEqual((paths, commands), (["analysis/a/fit.py"], ["snakemake"]))


class PlanRows(unittest.TestCase):
    def test_rows_read_the_columns(self):
        rows = pt.plan_rows(PLAN)
        self.assertEqual([r["num"] for r in rows], ["1", "2"])
        self.assertEqual(rows[0]["step"], "run `analysis/a/fit.py`")
        self.assertEqual(rows[0]["choice"], "model A")
        self.assertEqual(rows[0]["source"], "repo: docs/m.md")
        self.assertEqual(rows[1]["check"], "rows match")
        self.assertEqual(rows[0]["id"], "1")

    def test_no_step_column_gives_none(self):
        self.assertIsNone(pt.plan_rows("| A | B |\n|---|---|\n| 1 | 2 |\n"))

    def test_table_cells(self):
        self.assertEqual(pt.table_cells("| a | b\\|c |"), ["a", "b|c"])


class CoveredScripts(unittest.TestCase):
    def test_only_existing_gated_scripts_are_pinned(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        os.makedirs(os.path.join(root, "analysis", "a"))
        with open(os.path.join(root, "analysis", "a", "fit.py"), "w") as handle:
            handle.write("x = 1\n")
        text = "| Step |\n|---|\n| run `analysis/a/fit.py` and `analysis/a/new.py` and `data/x.py` |\n"
        self.assertEqual(pt.covered_scripts(root, text, CONFIG), ["analysis/a/fit.py"])


class GateReExports(unittest.TestCase):
    def test_every_public_name_is_the_same_object(self):
        names = [n for n in dir(pt) if not n.startswith("_") and n not in ("functools", "os", "re")]
        for name in names:
            with self.subTest(name=name):
                self.assertIs(getattr(gate, name), getattr(pt, name))


if __name__ == "__main__":
    unittest.main()
