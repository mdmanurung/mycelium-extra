"""Run: python3 skills/analysis-report/tests/test_analysis_report.py"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

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
        self.assertEqual([(s["file"], [(r["rule"], r["scripts"]) for r in s["rules"]])
                          for s in inventory["snakefiles"]],
                         [("Snakefile", [("prepare", ["01_prepare.R"]), ("fit", ["02_fit.R"])]),
                          ("Snakefile.figures", [("figures", ["03_plot.py"])])])
        self.assertEqual(inventory["outputs"]["current"], "run_2")
        self.assertEqual(inventory["outputs"]["figures"], ["outputs/run_2/03_effects.png"])
        self.assertEqual(inventory["outputs"]["reports"], ["outputs/run_2/03_REPORT.md"])

        out = self.run_script()
        self.assertIn("wrote nbs/demo/reports/demo.qmd", out)
        self.assertIn("wrote nbs/demo/reports/report.scss", out)
        self.assertIn("wrote nbs/demo/reports/report-dark.scss", out)
        with open(os.path.join(self.dest, "reports", "demo.qmd")) as handle:
            report = handle.read()
        self.assertNotIn("@@", report)
        self.assertIn("engine: markdown", report)
        self.assertIn('subgraph w0["Snakefile"]', report)
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

        # The theme files the report names are written beside it; a project's own copy is kept.
        self.assertIn("theme:\n      light: [default, report.scss]", report)
        theme = os.path.join(self.dest, "reports", "report.scss")
        with open(theme, "w") as handle:
            handle.write("/* the project's own theme */\n")
        out = self.run_script("--overwrite")
        self.assertIn("wrote nbs/demo/reports/demo.qmd", out)
        self.assertNotIn("reports/report.scss", out)
        self.assertNotIn("reports/report-dark.scss", out)
        with open(theme) as handle:
            self.assertEqual(handle.read(), "/* the project's own theme */\n")

    def test_only_real_workflows_are_read_and_input_keys_name_the_script(self):
        os.makedirs(os.path.join(self.dest, "Snakefile.d"))
        write(os.path.join(self.dest, "Snakefile.bak"), "rule old:\n    shell: \"Rscript 01_prepare.R\"\n")
        write(os.path.join(self.dest, "extra.smk"), "rule e:\n    shell: \"echo\"\n")
        write(os.path.join(self.dest, "Snakefile.keys"), 'rule k:\n    input:\n        script="code/03_plot.py",\n'
              '    shell:\n        "{PYTHON:q} -u {input.script:q}"\n')
        out = self.run_script("--dry-run")
        inventory = json.loads(out[:out.rindex("}") + 1])
        self.assertEqual([s["file"] for s in inventory["snakefiles"]], ["Snakefile", "Snakefile.figures", "Snakefile.keys", "extra.smk"])
        self.assertEqual(inventory["snakefiles"][2]["rules"][0]["scripts"], ["03_plot.py"])

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

    def test_a_marimo_step_gets_a_python_methods_tab(self):
        write(os.path.join(self.dest, "code", "04_explore.marimo.py"), "import marimo\n")
        self.run_script()
        with open(os.path.join(self.dest, "reports", "demo.qmd")) as handle:
            self.assertIn('```{.python filename="code/04_explore.marimo.py"}', handle.read())

RUN_DOC = "# demo\n\n## Outputs\n\n| File | Description |\n|------|-------------|\n| `outputs/x.png` | a figure |\n\n## Notes\n\nend\n"


class RunLayoutTest(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp())
        subprocess.run(["git", "-C", self.root, "init", "-q"], check=True)
        self.dest = os.path.join(self.root, "nbs", "demo")
        write(os.path.join(self.dest, "README.md"), RUN_DOC)
        write(os.path.join(self.dest, "code", "01_fit.py"), "1\n")
        old = os.path.join(self.dest, "outputs", "run_20261101_first")
        new = os.path.join(self.dest, "outputs", "run_20261104_second")
        write(os.path.join(old, "RUN.txt"), "run: run_20261101_first\nstatus: superseded\n")
        write(os.path.join(old, "figures", "01_old.png"))
        write(os.path.join(new, "RUN.txt"), "run: run_20261104_second\nstatus: current\n")
        write(os.path.join(new, "figures", "01_a.png"))
        write(os.path.join(new, "figures", "01_b.png"))
        write(os.path.join(new, "source_data", "01_a.tsv"), "x\n")
        write(os.path.join(new, "tables", "01_a.tsv"), "x\n")
        write(os.path.join(new, "numbers.json"), "{}")
        os.symlink("run_20261104_second", os.path.join(self.dest, "outputs", "current"))

    def tearDown(self):
        shutil.rmtree(self.root)

    def run_script(self, *args):
        with open(SCRIPT) as source:
            proc = subprocess.run([sys.executable, "-", "--dest=nbs/demo", "--templates=" + TEMPLATES] + list(args),
                                  stdin=source, cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  universal_newlines=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc.stdout

    def read(self, *parts):
        with open(os.path.join(self.dest, *parts)) as handle:
            return handle.read()

    def test_current_run_figures_pair_with_source_data(self):
        write(os.path.join(self.dest, "outputs", "run_20261104_second", "figures", "01_b.pdf"))  # PDF and PNG share a stem
        out = self.run_script()
        outputs = json.loads(out[:out.rindex("}") + 1].split("\nwrote")[0])["outputs"]
        self.assertEqual((outputs["layout"], outputs["current"], outputs["run"]), ("run", "run_20261104_second", "run_20261104_second"))
        self.assertEqual(outputs["figures"], ["outputs/run_20261104_second/figures/01_a.png",
                                              "outputs/run_20261104_second/figures/01_b.png"])
        self.assertEqual(outputs["source_data_missing"], ["outputs/run_20261104_second/figures/01_b.png"])
        self.assertEqual(outputs["numbers"], ["outputs/run_20261104_second/numbers.json"])
        report = self.read("reports", "demo.qmd")
        self.assertIn("- source data missing: outputs/run_20261104_second/figures/01_b.png", report)
        self.assertEqual(report.count("source data missing:"), 2)  # Open items and the Results tab
        self.assertNotIn("01_old.png", report)
        self.assertNotIn("source data missing: outputs/run_20261104_second/figures/01_a.png", report)

    def test_outputs_row_appends_once_and_replaces(self):
        self.run_script()
        write(os.path.join(self.dest, "reports", "README.md"),
              "# Reports\n\n| File | What it is | From outputs | Owner |\n|---|---|---|---|\n"
              "| `demo.qmd` | the record | `none` | analysis-report |\n| `demo.html` | its render | same | quarto render |\n")
        self.run_script("--outputs-row", "--date=2026-11-04")
        self.run_script("--outputs-row", "--date=2026-11-05")
        doc = self.read("README.md")
        self.assertEqual(doc.count("| reports/demo.html |"), 1)
        self.assertIn("| reports/demo.html | Quarto report (rendered 2026-11-05, run run_20261104_second) |", doc)
        self.assertLess(doc.index("| reports/demo.html |"), doc.index("## Notes"))
        self.assertIn("| `outputs/x.png` | a figure |", doc)
        readme = self.read("reports", "README.md")
        self.assertIn("| `demo.qmd` | the record | `run_20261104_second` | analysis-report |", readme)
        self.assertIn("| `demo.html` | its render, 2026-11-05 | `run_20261104_second` | quarto render |", readme)

    def test_outputs_row_without_a_table_or_readme(self):
        write(os.path.join(self.dest, "README.md"), "# demo\n")
        self.run_script("--outputs-row", "--date=2026-11-04")
        self.assertIn("## Outputs\n\n| File | Description |", self.read("README.md"))
        self.assertFalse(os.path.exists(os.path.join(self.dest, "reports", "README.md")))


class StepsLayoutTest(unittest.TestCase):
    """A steps layout: outputs/<stem>/ per script, an old run folder left beside it."""

    run_script, read, tearDown = RunLayoutTest.run_script, RunLayoutTest.read, RunLayoutTest.tearDown

    def setUp(self):
        RunLayoutTest.setUp(self)
        outputs = os.path.join(self.dest, "outputs")
        os.remove(os.path.join(outputs, "current"))
        write(os.path.join(self.dest, "code", "02_show.qmd"), "x\n")
        write(os.path.join(outputs, "01_fit", "tables", "01_fit.tsv"), "x\n")
        write(os.path.join(outputs, "02_show", "figures", "02_show.png"))
        write(os.path.join(outputs, "02_show", "figures", "02_other.png"))
        write(os.path.join(outputs, "02_show", "source_data", "02_show.tsv"), "x\n")
        write(os.path.join(outputs, "02_show", "02_show.html"), "<html></html>")
        write(os.path.join(outputs, "numbers.json"), "{}")
        write(os.path.join(self.dest, "logs", "CHANGES.md"),
              "# Changes\n\n## 2026-11-12 09:30 abc1234 ok\n\n## 2026-11-10 08:00 abc1233 ok\n")

    def test_inventory_reads_the_step_folders(self):
        out = self.run_script("--dry-run")
        outputs = json.loads(out[:out.rindex("}") + 1])["outputs"]
        self.assertEqual((outputs["layout"], outputs["current"]), ("steps", None))
        self.assertEqual(outputs["run"], "outputs/ (steps), last change 2026-11-12")
        self.assertEqual(outputs["figures"], ["outputs/02_show/figures/02_other.png", "outputs/02_show/figures/02_show.png"])
        self.assertEqual(outputs["source_data_missing"], ["outputs/02_show/figures/02_other.png"])
        self.assertEqual(outputs["tables"], ["outputs/01_fit/tables/01_fit.tsv"])
        self.assertEqual(outputs["pages"], ["outputs/02_show/02_show.html"])
        self.assertEqual(outputs["numbers"], ["outputs/numbers.json"])
        self.assertEqual(outputs["runs"], ["01_fit", "02_show"])

    def test_inventory_lists_panels_and_a_fresh_marked_scaffold(self):
        write(os.path.join(self.dest, "outputs", "panels", "figures", "plot_a.png"))
        out = self.run_script("--dry-run")
        self.assertEqual(json.loads(out[:out.rindex("}") + 1])["outputs"]["runs"], ["01_fit", "02_show", "panels"])
        shutil.rmtree(os.path.join(self.dest, "outputs"))  # a fresh scaffold: marker only
        write(os.path.join(self.dest, "outputs", ".layout"), "layout: steps\nversion: 1\n")
        out = self.run_script("--dry-run")
        outputs = json.loads(out[:out.rindex("}") + 1])["outputs"]
        self.assertEqual((outputs["layout"], outputs["runs"], outputs["figures"]), ("steps", [], []))

    def test_outputs_row_names_the_steps_layout(self):
        write(os.path.join(self.dest, "reports", "README.md"),
              "# Reports\n\n| File | What it is | From outputs | Owner |\n|---|---|---|---|\n"
              "| `demo.qmd` | the record | `none` | analysis-report |\n")
        self.run_script("--outputs-row", "--date=2026-11-12")
        self.assertIn("run outputs/ (steps), last change 2026-11-12)", self.read("README.md"))
        self.assertIn("`outputs/ (steps), last change 2026-11-12`", self.read("reports", "README.md"))

    def test_all_qmd_steps_point_at_the_step_folder(self):
        os.remove(os.path.join(self.dest, "code", "01_fit.py"))
        self.assertIn("outputs/<stem>/<stem>.html", self.run_script())

    def test_no_change_log_leaves_the_bare_label(self):
        os.remove(os.path.join(self.dest, "logs", "CHANGES.md"))
        out = self.run_script("--dry-run")
        self.assertEqual(json.loads(out[:out.rindex("}") + 1])["outputs"]["run"], "outputs/ (steps)")


    def rules_plugin(self, body):
        root = os.path.join(self.root, "lucid-coder")
        write(os.path.join(root, "scripts", "rules.js"), body)
        return root

    def test_inventory_lists_active_learned_rules_that_apply(self):
        if not shutil.which("node"):
            self.skipTest("node is not installed")
        rules = [{"id": "r-0002", "topic": "user.report_embedded_figures", "scope": {"kind": "global"}, "status": "active"},
                 {"id": "r-0017", "topic": "fig.theme", "scope": {"kind": "language", "language": "r"}, "status": "active"},
                 {"id": "r-0020", "topic": "py.thing", "scope": {"kind": "language", "language": "python"}, "status": "active"}]
        plugin = self.rules_plugin("if (process.argv.slice(2).join(' ') !== 'list --status active --json') process.exit(1);\n"
                                   "console.log(JSON.stringify({}));\n".format(json.dumps(rules)))
        with mock.patch.dict(os.environ, {"MX_LUCID_CODER_ROOT": plugin}):
            out = self.run_script("--dry-run")
        line = [l for l in out.splitlines() if l.startswith("info: lucid-coder learned rules")]
        self.assertEqual(len(line), 1, out)
        self.assertIn("(3)", line[0])  # the steps mix R and Python
        self.assertIn("r-0002 user.report_embedded_figures", line[0])
        self.assertIn("r-0017 fig.theme", line[0])
        self.assertIn("not enforced", line[0])
        self.assertIn("steps", json.loads(out[:out.rindex("}") + 1]))  # the inventory stays parseable

    def test_learned_rules_fail_open_and_stay_quiet(self):
        if not shutil.which("node"):
            self.skipTest("node is not installed")
        for env in ({"MX_LUCID_CODER_ROOT": os.path.join(self.root, "missing")},
                    {"MX_LUCID_CODER_ROOT": self.rules_plugin("process.exit(1);\n")},
                    {"MX_LUCID_CODER_ROOT": self.rules_plugin("console.log('[]');\n")}):
            with mock.patch.dict(os.environ, env):
                self.assertNotIn("lucid-coder learned rules", self.run_script("--dry-run"))


class SkillTextTest(unittest.TestCase):
    """The agent text and the fixture agree with the plot-first and r-0002 rules."""

    def text(self, *parts):
        with open(os.path.join(HERE, "..", "..", *parts), encoding="utf-8") as handle:
            return handle.read()

    def test_skill_embeds_png_and_checks_claims_before_hand_off(self):
        skill = self.text("analysis-report", "SKILL.md")
        self.assertIn("user.report_embedded_figures", skill)
        self.assertIn("never as a link to a PDF", skill)
        self.assertIn("pdftoppm -r 150 -png", skill)
        self.assertNotIn("or the link form above", skill)
        self.assertIn("lucid-writer", skill)
        self.assertIn("<!-- claims -->", skill)
        self.assertIn("report <hash> --analysis-dir <folder> --claims <folder>/reports/<name>.qmd --resolve-citations", skill)
        self.assertIn("only if the user asks", skill)
        self.assertIn("lucid-evidence-auditor", skill)

    def test_plot_first_puts_the_marker_before_the_tag(self):
        text = self.text("plot-first", "SKILL.md")
        self.assertIn("before its fact tag so the tag still ends the line", text)
        self.assertNotIn("after the conclusion in the same document", text)

    def test_fixture_tags_end_the_line_and_name_an_artifact_path(self):
        tag = re.compile(r"\[agent-derived: `([^`]+)`\]\s*$")
        lines = [l for l in self.text("analysis-report", "tests", "fixtures", "artifact", "demo.qmd").splitlines()
                 if l.startswith("**Conclusion.**")]
        self.assertEqual(len(lines), 2)
        for line in lines:
            match = tag.search(line)
            self.assertTrue(match, line)
            self.assertTrue(match.group(1).startswith("outputs/") and "." in match.group(1), line)
        self.assertRegex(lines[1], r"unsupported: no inspected figure \[agent-derived:")


if __name__ == "__main__":
    unittest.main()
