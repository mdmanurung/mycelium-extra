"""Run: python3 skills/new-analysis/tests/test_new_analysis.py"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, "..")
SCRIPT = os.path.join(SKILL, "scripts", "new_analysis.py")
TEMPLATES = os.path.join(SKILL, "templates")
GATE = os.path.join(SKILL, "..", "..", "hooks", "gate.py")
STEPS = ["01_prepare_data.R", "02_train_model.py", "03_explore_model.ipynb"]


def run(cwd, *args):
    with open(SCRIPT) as source:
        return subprocess.run([sys.executable, "-", "--templates=" + TEMPLATES] + list(args),
                              stdin=source, cwd=cwd, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def write(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(text)


def git(cwd, *args):
    subprocess.run(["git", "-C", cwd] + list(args), stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, check=True)


class NewAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp())
        git(self.root, "init", "-q")
        os.mkdir(os.path.join(self.root, ".living"))
        os.mkdir(os.path.join(self.root, "analysis"))
        write(os.path.join(self.root, "data", "anndatas", "cells.h5ad"), "x")
        write(os.path.join(self.root, "src", "helpers.R"), "f <- 1\n")
        self.dest = os.path.join(self.root, "analysis", "demo-run")

    def tearDown(self):
        shutil.rmtree(self.root)

    def scaffold(self, *args):
        proc = run(self.root, "--dest=analysis/demo-run", *args)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc.stdout

    def test_dry_run_writes_nothing(self):
        out = self.scaffold("--data=data/anndatas/cells.h5ad", "--dry-run")
        self.assertIn("would create analysis/demo-run/", out)
        self.assertFalse(os.path.exists(self.dest))

    def test_full_tree_in_mycelium_repo(self):
        out = self.scaffold("--data=data/anndatas/cells.h5ad", "--code=src/helpers.R")
        expected = set(STEPS + ["Snakefile", "run.sh", "DEMO_RUN.md", "PLAN.md", "TRACKER.md",
                                "data", "code", "outputs", "logs", "reports"])
        self.assertEqual(set(os.listdir(self.dest)), expected)
        self.assertTrue(os.access(os.path.join(self.dest, "run.sh"), os.X_OK))
        link = os.path.join(self.dest, "data", "cells.h5ad")
        self.assertEqual(os.readlink(link), "../../../data/anndatas/cells.h5ad")
        self.assertEqual(read(link), "x")
        self.assertEqual(read(os.path.join(self.dest, "code", "helpers.R")), "f <- 1\n")
        self.assertIn("suggested analysis/ANALYSIS_MANIFEST.md entry", out)
        self.assertIn("datasets: [cells.h5ad]", out)
        plan = read(os.path.join(self.dest, "PLAN.md"))
        self.assertIn("Inputs: data/anndatas/cells.h5ad", plan)
        self.assertIn("| S02 | `analysis/demo-run/02_train_model.py` |", plan)
        tracker = read(os.path.join(self.dest, "TRACKER.md"))
        self.assertIn("| S03 | `03_explore_model.ipynb` | todo | S02 |", tracker)
        self.assertIn("[DEMO_RUN.md](DEMO_RUN.md)", tracker)

    def test_readme_outside_mycelium(self):
        os.rmdir(os.path.join(self.root, ".living"))
        out = self.scaffold()
        self.assertIn("README.md", os.listdir(self.dest))
        self.assertNotIn("ANALYSIS_MANIFEST", out)

    def test_doc_uses_mycelium_template_through_plugin_root(self):
        plugin = os.path.join(self.root, "plugin")
        write(os.path.join(plugin, "skills", "core", "templates", "analysis-readme.md"),
              "# [Analysis Name]\n\nMARKER\n\n## Key Findings\n\n- x\n")
        write(os.path.join(self.root, ".mycelium", "plugin-root"), plugin + "\n")
        out = self.scaffold()
        self.assertIn("Mycelium's template at", out)
        doc = read(os.path.join(self.dest, "DEMO_RUN.md"))
        self.assertTrue(doc.startswith("# demo-run\n\nMARKER"))
        self.assertTrue(doc.rstrip().endswith("| 03 | `03_explore_model.ipynb` | [what it does] "
                                              "| `logs/03_explore_model.ipynb` |"))
        self.assertIn(".living/findings ID", doc)

    def test_doc_from_bundled_template(self):
        out = self.scaffold("--data=data/anndatas/cells.h5ad")
        self.assertIn("bundled copy", out)
        doc = read(os.path.join(self.dest, "DEMO_RUN.md"))
        self.assertTrue(doc.startswith("# demo-run\n"))
        self.assertNotIn("NAMING:", doc)
        self.assertNotIn("[analysis-name]", doc)
        self.assertIn("cd analysis/demo-run\nbash run.sh", doc)
        self.assertIn("- `data/cells.h5ad` → `data/anndatas/cells.h5ad`", doc)
        self.assertLess(doc.index("## Steps"), doc.index("## Reproducibility"))
        self.assertIn("| `outputs/02_train_model.parquet` | [description] (step 02) |", doc)
        self.assertEqual(doc.count("<!--", doc.index("## Key Findings"),
                                   doc.index("## Open Questions")), 1)

    def test_refuses_non_empty_dest(self):
        write(os.path.join(self.dest, "notes.txt"), "keep")
        proc = run(self.root, "--dest=analysis/demo-run")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("not empty", proc.stdout)
        self.assertEqual(os.listdir(self.dest), ["notes.txt"])

    def test_empty_dest_is_filled(self):
        os.mkdir(self.dest)
        self.scaffold()
        self.assertIn("Snakefile", os.listdir(self.dest))

    def test_refuses_bad_steps_and_links(self):
        cases = [("--steps=1_a.R", "must look like"),
                 ("--steps=02_a.R,01_b.py", "must increase"),
                 ("--steps=01_a.sh", "must look like"),
                 ("--data=data/missing.h5ad", "does not exist")]
        for option, message in cases:
            proc = run(self.root, "--dest=analysis/demo-run", option)
            self.assertEqual(proc.returncode, 1, option)
            self.assertIn(message, proc.stdout, option)
            self.assertFalse(os.path.exists(self.dest), option)
        write(os.path.join(self.root, "other", "cells.h5ad"), "y")
        proc = run(self.root, "--dest=analysis/demo-run", "--data=data/anndatas/cells.h5ad",
                   "--data=other/cells.h5ad")
        self.assertIn("both named cells.h5ad", proc.stdout)
        self.assertFalse(os.path.exists(self.dest))

    def test_notebook_is_nbformat_4(self):
        self.scaffold()
        book = json.loads(read(os.path.join(self.dest, "03_explore_model.ipynb")))
        self.assertEqual(book["nbformat"], 4)
        self.assertEqual(book["metadata"]["kernelspec"]["name"], "python3")
        for cell in book["cells"]:
            self.assertRegex(cell["id"], r"^[A-Za-z0-9_-]+$")
            self.assertIsInstance(cell["source"], list)
        setup = "".join(book["cells"][1]["source"])
        self.assertIn('INPUT = Path("outputs/02_train_model.parquet")', setup)
        self.assertNotIn("assert ", setup)  # scilintr's runtime-assert would fail verify's lint

    def test_snakefile_chains_every_step_in_order(self):
        self.scaffold("--steps=01_load.py,04_fit.R,07_look.ipynb", "--data=data/anndatas/cells.h5ad")
        snakefile = read(os.path.join(self.dest, "Snakefile"))
        self.assertEqual(re.findall(r"^rule (\w+):", snakefile, re.M),
                         ["all", "step01_load", "step04_fit", "step07_look"])
        self.assertIn('rule all:\n    input:\n        "logs/07_look.ipynb",', snakefile)
        self.assertIn('data=["data/cells.h5ad"],', snakefile)
        self.assertIn('prev="outputs/01_load.parquet",\n        script="04_fit.R",', snakefile)
        self.assertIn('prev="outputs/04_fit.rds",\n        notebook="07_look.ipynb",', snakefile)
        self.assertIn("workdir: workflow.basedir", snakefile)
        self.assertNotIn("@@", snakefile)
        for name in ["01_load.py", "04_fit.R", "07_look.ipynb"]:
            self.assertIn(name, os.listdir(self.dest))

    def test_python_stub_fails_loudly(self):
        self.scaffold()
        proc = subprocess.run([sys.executable, "02_train_model.py", "in", "out"], cwd=self.dest,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not written yet", proc.stderr)

    def test_r_stub_fails_loudly(self):
        rscript = shutil.which("Rscript")
        if not rscript:
            self.skipTest("Rscript is not installed")
        self.scaffold()
        proc = subprocess.run([rscript, "01_prepare_data.R", "out"], cwd=self.dest,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not written yet", proc.stderr)

    def test_git_ignored_paths(self):
        write(os.path.join(self.root, ".gitignore"), "analysis/*/reports/\nanalysis/*/logs/\n")
        out = self.scaffold("--dry-run")
        self.assertIn("WARNING: git ignores analysis/demo-run/reports/", out)
        self.assertIn("note: git ignores analysis/demo-run/logs/", out)
        self.assertNotIn("WARNING: git ignores analysis/demo-run/logs/", out)

    def test_mycelium_notes(self):
        write(os.path.join(self.root, "elsewhere", "raw.csv"), "a\n")
        out = run(self.root, "--dest=nbs/My_Run", "--data=elsewhere/raw.csv").stdout
        self.assertIn("note: outside analysis/", out)
        self.assertIn("lowercase-with-hyphens", out)
        self.assertIn("elsewhere/raw.csv is not under data/", out)

    def gate_decision(self, command):
        write(os.path.join(self.root, ".mycelium-extra", "gate.json"), "{}\n")
        event = {"cwd": self.root, "hook_event_name": "PreToolUse", "tool_name": "Bash",
                 "tool_input": {"command": command}}
        out = subprocess.run([sys.executable, GATE, "tool"], input=json.dumps(event),
                             stdout=subprocess.PIPE, universal_newlines=True).stdout
        return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out.strip() else None

    def test_gate_allows_documented_command(self):
        tail = " --templates=/plugin/skills/new-analysis/templates < " \
               "/plugin/skills/new-analysis/scripts/new_analysis.py"
        self.assertIsNone(self.gate_decision(
            "python3 - --dest=analysis/demo-run --data=data/anndatas/cells.h5ad" + tail))
        # A bare positional path is read as the script to run, which is why SKILL.md
        # always uses --flag=value.
        self.assertEqual(self.gate_decision("python3 - --dest analysis/demo-run" + tail), "deny")


if __name__ == "__main__":
    unittest.main()
