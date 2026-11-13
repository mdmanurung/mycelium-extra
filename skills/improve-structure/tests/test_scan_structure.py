"""Run: python3.11 skills/improve-structure/tests/test_scan_structure.py

The scanner finds each smell in tests/fixtures/smelly and nothing in tests/fixtures/clean.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "scan_structure.py")
SMELLY = os.path.join(HERE, "fixtures", "smelly")
CLEAN = os.path.join(HERE, "fixtures", "clean")


def scan(path, *extra):
    proc = subprocess.run([sys.executable, "-B", SCRIPT, path, "--json"] + list(extra), capture_output=True, text=True)
    return proc, (json.loads(proc.stdout) if proc.returncode == 0 else None)


def findings(path, *extra):
    proc, result = scan(path, *extra)
    assert proc.returncode == 0, proc.stderr
    assert len(result["analyses"]) == 1
    return result["analyses"][0]


def kinds(item, kind):
    return [f for f in item["findings"] if f["kind"] == kind]


class Smelly(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.item = findings(SMELLY)

    def files(self, kind):
        return sorted(f["files"][0] for f in kinds(self.item, kind))

    def test_shared_folder_read(self):
        self.assertEqual(self.files("shared_folder_read"), ["02_fit.R"])
        self.assertIn("dirname", kinds(self.item, "shared_folder_read")[0]["detail"])
        self.assertIn("run_dir", kinds(self.item, "shared_folder_read")[0]["detail"])

    def test_absolute_path_into_another_step(self):
        self.assertEqual(self.files("absolute_step_path"), ["02_fit.R"])

    def test_fan_in_only_where_more_than_two_steps_are_read(self):
        self.assertEqual(self.files("fan_in"), ["04_combine.R"])
        self.assertEqual(kinds(self.item, "fan_in")[0]["steps"], ["01", "02", "03"])

    def test_duplicated_block(self):
        dup = kinds(self.item, "duplicated_block")
        self.assertEqual(len(dup), 1)
        self.assertEqual(dup[0]["files"], ["01_prepare.R", "02_fit.R"])
        self.assertEqual(dup[0]["length"], 9)

    def test_dup_lines_threshold(self):
        self.assertEqual(kinds(findings(SMELLY, "--dup-lines", "10"), "duplicated_block"), [])

    def test_heavy_notebook(self):
        self.assertEqual(self.files("heavy_notebook"), ["06_explore.qmd"])

    def test_no_rule(self):
        self.assertEqual(self.files("no_rule"), ["07_orphan.py"])

    def test_no_check(self):
        self.assertEqual(self.files("no_check"), ["02_fit.R", "03_plot.R", "04_combine.R", "06_explore.qmd", "07_orphan.py"])

    def test_midscript_parameters_and_late_knob(self):
        self.assertEqual(self.files("midscript_parameter"), ["02_fit.R"])
        self.assertEqual(kinds(self.item, "midscript_parameter")[0]["count"], 4)
        self.assertEqual(self.files("knob_not_at_top"), ["02_fit.R"])

    def test_plot_style(self):
        self.assertEqual(self.files("plot_without_theme"), ["03_plot.R", "04_combine.R"])
        palette = kinds(self.item, "palette_repeated")
        self.assertEqual(len(palette), 1)
        self.assertEqual(palette[0]["files"], ["03_plot.R", "04_combine.R"])

    def test_hot_spots_from_changes_md(self):
        top = self.item["hot_spots"][0]
        self.assertEqual(top["file"], "code/02_fit.R")
        self.assertEqual(top["changes_md_entries"], 3)
        self.assertEqual([h["file"] for h in self.item["hot_spots"]], ["code/02_fit.R"])

    def test_no_findings_on_the_wrong_steps(self):
        # 01 is clean except for the duplicate it shares with 02 (it has a check and a rule)
        own = [f["kind"] for f in self.item["findings"] if f["files"] == ["01_prepare.R"]]
        self.assertEqual(own, [])

    def test_text_summary(self):
        proc = subprocess.run([sys.executable, "-B", SCRIPT, SMELLY], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("fan_in: 04_combine.R", proc.stdout)
        self.assertIn("Edited most: code/02_fit.R", proc.stdout)


class Clean(unittest.TestCase):
    def test_no_findings(self):
        item = findings(CLEAN)
        self.assertEqual(item["findings"], [])
        self.assertEqual(item["hot_spots"], [])

    def test_text_says_so(self):
        proc = subprocess.run([sys.executable, "-B", SCRIPT, CLEAN], capture_output=True, text=True)
        self.assertIn("No findings.", proc.stdout)


class Thresholds(unittest.TestCase):
    def make(self, tmp, name, text):
        os.makedirs(os.path.join(tmp, "code"), exist_ok=True)
        with open(os.path.join(tmp, "code", name), "w") as handle:
            handle.write(text)

    def test_long_script_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make(tmp, "01_big.R", "x <- 1\n" * 301)
            self.assertEqual(len(kinds(findings(tmp), "long_script")), 1)
        with tempfile.TemporaryDirectory() as tmp:
            self.make(tmp, "01_big.R", "x <- 1\n" * 300)
            self.assertEqual(kinds(findings(tmp), "long_script"), [])

    def test_long_pipe_default(self):
        pipe = "y <- x |>\n" + "  f() |>\n" * 15 + "  g()\n"  # 17 lines
        with tempfile.TemporaryDirectory() as tmp:
            self.make(tmp, "01_pipe.R", pipe)
            hit = kinds(findings(tmp), "long_pipe")
            self.assertEqual(len(hit), 1)
            self.assertEqual(hit[0]["count"], 17)
        short = "y <- x |>\n" + "  f() |>\n" * 3 + "  g()\n"
        with tempfile.TemporaryDirectory() as tmp:
            self.make(tmp, "01_pipe.R", short)
            self.assertEqual(kinds(findings(tmp), "long_pipe"), [])

    def test_no_snakefile(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make(tmp, "01_a.R", "x <- 1\n")
            self.assertEqual(len(kinds(findings(tmp), "no_snakefile")), 1)

    def test_git_hot_spots(self):
        if shutil.which("git") is None:
            self.skipTest("git not found")
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
            repo = os.path.join(tmp, "repo")
            analysis = os.path.join(repo, "analysis", "a")
            os.makedirs(analysis)
            subprocess.run(["git", "-C", repo, "init", "-q"], check=True, env=env)
            self.make(analysis, "01_a.R", "x <- 1\n")
            self.make(analysis, "02_b.R", "y <- 1\n")
            for n in range(3):
                self.make(analysis, "01_a.R", "x <- {}\n".format(n + 2))
                subprocess.run(["git", "-C", repo, "add", "-A"], check=True, env=env)
                subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "c{}".format(n)], check=True, env=env)
            item = findings(analysis)
            self.assertEqual(item["hot_spots"], [{"file": "code/01_a.R", "git_commits": 3, "changes_md_entries": 0}])

    def test_folder_of_analyses(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("a", "b"):
                shutil.copytree(CLEAN, os.path.join(tmp, name))
            proc, result = scan(tmp)
            self.assertEqual(sorted(os.path.basename(a["path"]) for a in result["analyses"]), ["a", "b"])

    def test_bad_path(self):
        proc, _ = scan("/no/such/folder")
        self.assertEqual(proc.returncode, 2)

    def test_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = os.path.join(tmp, "s")
            shutil.copytree(SMELLY, copy)
            before = sorted((os.path.join(r, f), os.path.getmtime(os.path.join(r, f))) for r, _, fs in os.walk(copy) for f in fs)
            scan(copy)
            after = sorted((os.path.join(r, f), os.path.getmtime(os.path.join(r, f))) for r, _, fs in os.walk(copy) for f in fs)
            self.assertEqual(before, after)


class FalsePositives(unittest.TestCase):
    """Own-folder writes, helper files, list entries and raw inputs are not friction."""

    def make(self, tmp, files):
        code = os.path.join(tmp, "a", "code")
        os.makedirs(code)
        for name, text in files.items():
            with open(os.path.join(code, name), "w") as handle:
                handle.write(text)
        return findings(os.path.join(tmp, "a"))

    def test_own_writes_helper_params_and_raw_inputs(self):
        files = {
            "01_a.R": "x <- readRDS('data/x.rds')\nrun_dir <- dirname(output_path)\n"
            "write_tsv(x, file.path(run_dir, 'tables', '01_a.tsv'))\n",
            "02_b.R": "args <- commandArgs(TRUE)\nbase_dir <- args[[1]]\n"
            "y <- readRDS(file.path(base_dir, '01_a.rds'))\n"
            "z <- read_tsv('data/outputs/06b_counts.tsv.gz')\n"
            "w <- read_tsv('data/outputs/07_other.tsv.gz')\n"
            "v <- read_tsv('data/outputs/08_other.tsv.gz')\n"
            "params <- list(\n  KNOB_A = KNOB_A,\n  KNOB_B = KNOB_B\n)\n",
            "theme.R": "save_panel <- function(p, run, stem) ggsave(file.path(run, stem), p)\n",
        }
        with tempfile.TemporaryDirectory() as tmp:
            item = self.make(tmp, files)
        self.assertEqual([f["files"][0] for f in kinds(item, "shared_folder_read")], ["02_b.R"])
        self.assertEqual(kinds(item, "shared_folder_read")[0]["lines"], [3])
        self.assertEqual(kinds(item, "knob_not_at_top"), [])
        self.assertEqual(kinds(item, "fan_in"), [])  # 06b, 07 and 08 have no script here


if __name__ == "__main__":
    unittest.main()
