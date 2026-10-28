"""Run: python3 skills/analysis-report/tests/test_analysis_report.py"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "analysis_report.py")
TEMPLATES = os.path.join(HERE, "..", "..", "new-analysis", "templates")

SNAKEFILE = '''"""fits"""
RUN = "outputs/run_1"
rule all:
    input: RUN + "/02.rds"
rule prepare:
    output: RUN + "/01.rds"
    shell: "Rscript 01_prepare.R {output}"
rule fit:
    input: RUN + "/01.rds"
    output: RUN + "/02.rds"
    shell: "Rscript 02_fit.R {input} {output}"
'''


def write(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(text)


class AnalysisReportTest(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp())
        subprocess.run(["git", "-C", self.root, "init", "-q"], check=True)
        self.dest = os.path.join(self.root, "nbs", "demo")
        write(os.path.join(self.dest, "DEMO.md"), "# demo\n")
        write(os.path.join(self.dest, "01_prepare.R"), "1\n")
        write(os.path.join(self.dest, "02_fit.R"), "2\n")
        write(os.path.join(self.dest, "code", "03_plot.py"), "3\n")
        write(os.path.join(self.dest, "Snakefile"), SNAKEFILE)
        write(os.path.join(self.dest, "Snakefile.figures"), 'RUN = "outputs/run_2"\nrule all:\n    input: "x"\n'
              'rule figures:\n    shell: "python code/03_plot.py"\n')
        write(os.path.join(self.dest, "outputs", "run_1", "01.rds"), "")
        write(os.path.join(self.dest, "outputs", "run_2", "03_effects.png"), "")
        write(os.path.join(self.dest, "outputs", "run_2", "03_REPORT.md"), "")
        os.symlink("run_2", os.path.join(self.dest, "outputs", "current"))

    def tearDown(self):
        shutil.rmtree(self.root)

    def run_script(self, *args):
        with open(SCRIPT) as source:
            proc = subprocess.run([sys.executable, "-", "--dest=nbs/demo", "--templates=" + TEMPLATES] + list(args),
                                  stdin=source, cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  universal_newlines=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc.stdout

    def test_inventory_and_skeleton(self):
        out = self.run_script("--dry-run")
        self.assertFalse(os.path.exists(os.path.join(self.dest, "reports")))
        inventory = json.loads(out[:out.rindex("}") + 1])
        self.assertEqual(inventory["doc"], "DEMO.md")
        self.assertEqual(inventory["steps"], ["01_prepare.R", "02_fit.R", "code/03_plot.py"])
        self.assertEqual([(s["file"], s["run"], [(r["rule"], r["scripts"]) for r in s["rules"]])
                          for s in inventory["snakefiles"]],
                         [("Snakefile", "outputs/run_1", [("prepare", ["01_prepare.R"]), ("fit", ["02_fit.R"])]),
                          ("Snakefile.figures", "outputs/run_2", [("figures", ["03_plot.py"])])])
        self.assertEqual(inventory["outputs"]["current"], "run_2")
        self.assertEqual(inventory["outputs"]["figures"], ["outputs/run_2/03_effects.png"])
        self.assertEqual(inventory["outputs"]["reports"], ["outputs/run_2/03_REPORT.md"])

        out = self.run_script()
        self.assertIn("wrote nbs/demo/reports/demo.qmd", out)
        with open(os.path.join(self.dest, "reports", "demo.qmd")) as handle:
            report = handle.read()
        self.assertNotIn("@@", report)
        self.assertIn("engine: markdown", report)
        self.assertIn('subgraph w0["Snakefile → outputs/run_1"]', report)
        self.assertIn('r0_0["prepare: 01_prepare.R"] --> r0_1["fit: 02_fit.R"]', report)
        self.assertIn('r1_0["figures: 03_plot.py"]', report)
        self.assertIn('```{.python filename="code/03_plot.py"}', report)
        self.assertEqual(report.count("### 03 plot"), 2)  # a Methods tab, and the one Results tab with evidence
        self.assertEqual(report.count("### 01 prepare"), 1)
        self.assertIn("[agent-derived: `outputs/run_2/03_effects.png`]", report)
        self.assertIn("![Figure 1. [caption]. `outputs/run_2/03_effects.png`](../outputs/run_2/03_effects.png)", report)
        self.assertEqual(report.count("**Question.**"), 1)
        self.assertIn("[agent-derived: `outputs/run_2/03_REPORT.md`]", report)

        with open(os.path.join(self.dest, "reports", "demo.qmd"), "w") as handle:
            handle.write("filled\n")
        self.assertIn("kept: nbs/demo/reports/demo.qmd exists", self.run_script())
        self.assertIn("wrote", self.run_script("--overwrite"))

    def test_folder_without_snakefile_chains_steps(self):
        for name in ("Snakefile", "Snakefile.figures"):
            os.remove(os.path.join(self.dest, name))
        self.run_script()
        with open(os.path.join(self.dest, "reports", "demo.qmd")) as handle:
            self.assertIn('s01["01_prepare.R"] --> s02["02_fit.R"] --> s03["code/03_plot.py"]', handle.read())

    def test_all_qmd_steps_are_the_report(self):
        for name in ("01_prepare.R", "02_fit.R"):
            os.remove(os.path.join(self.dest, name))
        os.remove(os.path.join(self.dest, "code", "03_plot.py"))
        write(os.path.join(self.dest, "code", "01_prepare.qmd"), "---\ntitle: x\n---\n")
        self.assertIn("every step is a qmd", self.run_script())
        self.assertFalse(os.path.exists(os.path.join(self.dest, "reports", "demo.qmd")))

if __name__ == "__main__":
    unittest.main()
