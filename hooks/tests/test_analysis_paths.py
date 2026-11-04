"""Run: python3 hooks/tests/test_analysis_paths.py

hooks/analysis_paths.py: the one resolver for an analysis's runs, current run, numbers, figures and doc."""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import analysis_paths as ap  # noqa: E402


def touch(path, text="x", mtime=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(text)
    if mtime:
        os.utime(path, (mtime, mtime))


RUN_B = """# run
run: run_20261104_baseline
kind: analysis            # analysis | figures | scratch
status: current           # running | current | side | superseded | failed | scratch

# origin
why: paired titre change day 0 to 28, 8 donors
plan: 596f0693
labeled: 2026-11-04 by run.sh

# links
superseded_by:
notes: rerun of the 20261030 run with the corrected donor table
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.repo = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo)
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.folder = os.path.join(self.repo, "analysis", "my-study")
        os.makedirs(self.folder)

    def path(self, *parts):
        return os.path.join(self.folder, *parts)


class RunLayout(Base):
    def setUp(self):
        super().setUp()
        now = time.time()
        touch(self.path("outputs", "run_20261001_fit", "RUN.txt"),
              "run: run_20261001_fit\nkind: analysis\nstatus: current\n")
        touch(self.path("outputs", "run_20261001_fit", "02_fit.tsv"), mtime=now - 500)
        touch(self.path("outputs", "run_20261002_fit_v02", "RUN.txt"), "run: x\nkind: analysis\nstatus: running\n")
        touch(self.path("outputs", "run_20261002_fit_v02", "02_fit.tsv"), mtime=now - 400)
        touch(self.path("outputs", "run_20261003_try", "RUN.txt"), "kind: scratch\nstatus: scratch\n")
        touch(self.path("outputs", "run_20261003_try", "x.tsv"), mtime=now - 10)

    def test_runs_listed_with_fields(self):
        found = ap.runs(self.folder)
        self.assertEqual([r["name"] for r in found],
                         ["run_20261001_fit", "run_20261002_fit_v02", "run_20261003_try"])
        self.assertTrue(all(r["layout"] == "run" for r in found))
        self.assertEqual(found[0]["status"], "current")
        self.assertEqual(found[2]["kind"], "scratch")
        self.assertEqual(found[0]["run_txt"]["run"], "run_20261001_fit")

    def test_current_link(self):
        os.symlink("run_20261001_fit", self.path("outputs", "current"))
        run, why = ap.current_run(self.folder)
        self.assertEqual((run["name"], why), ("run_20261001_fit", "current link"))

    def test_current_missing_takes_newest_non_scratch(self):
        run, why = ap.current_run(self.folder)
        self.assertEqual((run["name"], why), ("run_20261002_fit_v02", "newest run"))

    def test_newest_uses_file_mtime_not_folder_mtime(self):
        old = self.path("outputs", "run_20261001_fit")
        os.utime(old, (time.time() + 1000, time.time() + 1000))  # folder looks newest
        self.assertEqual(ap.current_run(self.folder)[0]["name"], "run_20261002_fit_v02")

    def test_current_outside_repository(self):
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside)
        os.symlink(outside, self.path("outputs", "current"))
        self.assertEqual(ap.current_run(self.folder), (None, "outside repository"))

    def test_results_dir_override(self):
        touch(self.path("elsewhere", "run_20260901_a", "RUN.txt"), "kind: figures\nstatus: current\n")
        self.assertEqual([r["name"] for r in ap.runs(self.folder, "elsewhere")], ["run_20260901_a"])
        self.assertEqual(ap.current_run(self.folder, "elsewhere")[0]["name"], "run_20260901_a")

    def test_results_folder_preferred_over_outputs(self):
        touch(self.path("results", "run_20260801_r", "RUN.txt"), "kind: analysis\n")
        self.assertEqual([r["name"] for r in ap.runs(self.folder)], ["run_20260801_r"])

    def test_numbers_precedence(self):
        run = ap.runs(self.folder)[0]
        self.assertIsNone(ap.numbers(self.folder, run))
        touch(self.path("outputs", "numbers.json"), "{}")
        self.assertEqual(ap.numbers(self.folder, run), self.path("outputs", "numbers.json"))
        touch(os.path.join(run["path"], "numbers.json"), "{}")
        self.assertEqual(ap.numbers(self.folder, run), os.path.join(run["path"], "numbers.json"))

    def test_figures_source_data_tables_and_stem(self):
        run = ap.runs(self.folder)[0]
        for sub, name in (("figures", "02_fit.png"), ("figures", "01_a.pdf"), ("source_data", "02_fit.tsv"),
                          ("tables", "02_fit.tsv.gz")):
            touch(os.path.join(run["path"], sub, name))
        self.assertEqual([os.path.basename(f) for f in ap.figures(run)], ["01_a.pdf", "02_fit.png"])
        self.assertEqual(ap.stem(ap.figures(run)[1]), ap.stem(ap.source_data(run)[0]))
        self.assertEqual(ap.stem(ap.tables(run)[0]), "02_fit")


class FlatLayout(Base):
    def test_flat(self):
        touch(self.path("outputs", "03_fx.png"))
        touch(self.path("outputs", "numbers.json"), "{}")
        found = ap.runs(self.folder)
        self.assertEqual(len(found), 1)
        self.assertEqual((found[0]["layout"], found[0]["path"]), ("flat", self.path("outputs")))
        run, why = ap.current_run(self.folder)
        self.assertEqual(why, "flat layout")
        self.assertEqual([os.path.basename(f) for f in ap.figures(run)], ["03_fx.png"])
        self.assertEqual(ap.numbers(self.folder), self.path("outputs", "numbers.json"))

    def test_dotfile_only_outputs_is_not_a_flat_layout(self):
        touch(self.path("outputs", ".gitkeep"))
        self.assertEqual(ap.runs(self.folder), [])
        self.assertEqual(ap.current_run(self.folder), (None, "none"))
        self.assertEqual(ap.base(self.folder), self.path("outputs"))

    def test_nothing(self):
        self.assertEqual(ap.runs(self.folder), [])
        self.assertEqual(ap.current_run(self.folder), (None, "none"))


class Docs(Base):
    def test_find_doc(self):
        self.assertIsNone(ap.find_doc(self.folder))
        touch(self.path("README.md"))
        self.assertEqual(ap.find_doc(self.folder), self.path("README.md"))
        touch(self.path("MY_STUDY.md"))
        self.assertEqual(ap.find_doc(self.folder), self.path("MY_STUDY.md"))


class Small(Base):
    def test_run_txt_bad_kind(self):
        touch(self.path("RUN.txt"), "run: r\nkind: model\nstatus: current\n")
        meta = ap.parse_run_txt(self.path("RUN.txt"))
        self.assertIn("kind_error", meta)
        self.assertEqual(meta["status"], "current")
        self.assertEqual(ap.parse_run_txt(self.path("none.txt")), {})

    def test_run_txt_shape_b(self):
        touch(self.path("RUN.txt"), RUN_B)
        self.assertEqual(ap.parse_run_txt(self.path("RUN.txt")), {
            "run": "run_20261104_baseline", "kind": "analysis", "status": "current",
            "why": "paired titre change day 0 to 28, 8 donors", "plan": "596f0693",
            "labeled": "2026-11-04 by run.sh", "superseded_by": "",
            "notes": "rerun of the 20261030 run with the corrected donor table"})
        touch(self.path("Q.txt"), 'why: "a # b" # c\n')
        self.assertEqual(ap.parse_run_txt(self.path("Q.txt"))["why"], '"a # b"')

    def test_roots(self):
        self.assertEqual(ap.repo_root(self.folder), self.repo)
        self.assertIsNone(ap.gate_root(self.folder))
        touch(os.path.join(self.repo, ".mycelium-extra", "gate.json"), "{}")
        self.assertEqual(ap.gate_root(self.folder), self.repo)
        self.assertEqual(ap.living_root(self.folder), self.repo)  # the toplevel when no .living
        os.makedirs(self.path(".living"))
        self.assertEqual(ap.living_root(self.path("code")), self.folder)

    def test_fill_read_sha(self):
        touch(self.path("t.txt"), "a @@X@@ b")
        self.assertEqual(ap.fill(ap.read(self.path("t.txt")), {"X": "1"}), "a 1 b")
        self.assertEqual(ap.sha256_file(self.path("t.txt")), ap.sha256_bytes(b"a @@X@@ b"))


if __name__ == "__main__":
    unittest.main()
