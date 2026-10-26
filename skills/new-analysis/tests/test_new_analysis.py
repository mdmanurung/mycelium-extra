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
AUDIT = os.path.join(SKILL, "..", "manuscript-audit", "scripts", "manuscript_audit.py")
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
        expected = {"Snakefile", "run.sh", "run.sbatch", "DEMO_RUN.md",
                    "data", "code", "plans", "outputs", "logs", "reports"}
        self.assertEqual(set(os.listdir(self.dest)), expected)
        self.assertEqual(set(os.listdir(os.path.join(self.dest, "code"))), set(STEPS + ["helpers.R"]))
        self.assertEqual(set(os.listdir(os.path.join(self.dest, "plans"))), {"PLAN.md", "TRACKER.md"})
        self.assertTrue(os.access(os.path.join(self.dest, "run.sh"), os.X_OK))
        link = os.path.join(self.dest, "data", "cells.h5ad")
        self.assertEqual(os.readlink(link), "../../../data/anndatas/cells.h5ad")
        self.assertEqual(read(link), "x")
        self.assertEqual(read(os.path.join(self.dest, "code", "helpers.R")), "f <- 1\n")
        self.assertIn("suggested analysis/ANALYSIS_MANIFEST.md entry", out)
        self.assertIn("datasets: [cells.h5ad]", out)
        plan = read(os.path.join(self.dest, "plans", "PLAN.md"))
        self.assertIn("Inputs: data/anndatas/cells.h5ad", plan)
        self.assertIn("| S02 | `analysis/demo-run/code/02_train_model.py` |", plan)
        tracker = read(os.path.join(self.dest, "plans", "TRACKER.md"))
        self.assertIn("| S03 | `code/03_explore_model.ipynb` | todo | S02 |", tracker)
        self.assertIn("[DEMO_RUN.md](../DEMO_RUN.md)", tracker)
        self.assertIn("  reports/demo-run.qmd\n", out)
        report = read(os.path.join(self.dest, "reports", "demo-run.qmd"))
        self.assertEqual(os.listdir(os.path.join(self.dest, "reports")), ["demo-run.qmd"])
        self.assertNotIn("@@", report)
        self.assertIn('title: "demo-run"', report)
        self.assertIn("[DEMO_RUN.md](../DEMO_RUN.md)", report)
        self.assertEqual(report.count("::: {.panel-tabset}"), 3)
        self.assertEqual(report.count("\n:::\n"), 3)  # every tabset closed
        chain = report.split("```{mermaid}\n")[1].split("```")[0]
        self.assertEqual(chain.splitlines(), [
            "flowchart LR",
            '    d0[("data/cells.h5ad")] --> s01["code/01_prepare_data.R"] --> o01[("outputs/01_prepare_data.rds")]',
            '    o01 --> s02["code/02_train_model.py"] --> o02[("outputs/02_train_model.parquet")]',
            '    o02 --> s03["code/03_explore_model.ipynb"] --> o03[("logs/03_explore_model.ipynb")]'])
        self.assertEqual(report.count("### 02 train model"), 2)  # one Methods tab, one Results tab
        self.assertIn('```{.python filename="code/02_train_model.py"}', report)
        self.assertIn('```{.r filename="code/01_prepare_data.R"}', report)
        self.assertIn("[agent-derived: `outputs/02_[what-it-shows].png`]", report)

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
        self.assertTrue(doc.rstrip().endswith("| 03 | `code/03_explore_model.ipynb` | [what it does] "
                                              "| `logs/03_explore_model.ipynb` |"))
        self.assertIn(".living/findings ID", doc)
        self.assertIn("saved, inspected plot and panel", doc)
        self.assertIn("explicit fallback", doc)

    def test_doc_from_bundled_template(self):
        out = self.scaffold("--data=data/anndatas/cells.h5ad")
        self.assertIn("bundled copy", out)
        doc = read(os.path.join(self.dest, "DEMO_RUN.md"))
        self.assertTrue(doc.startswith("# demo-run\n"))
        self.assertIn("saved, inspected plot and panel", doc)
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

    def test_concurrent_scaffolds_publish_only_one_complete_tree(self):
        command = [sys.executable, SCRIPT, "--templates=" + TEMPLATES, "--dest=" + self.dest]
        jobs = [subprocess.Popen(command, cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                for i in range(2)]
        codes = []
        for job in jobs:
            job.communicate(timeout=10)
            codes.append(job.returncode)
        self.assertEqual(sorted(codes), [0, 1])
        self.assertTrue(os.path.isfile(os.path.join(self.dest, "Snakefile")))
        self.assertEqual(len(os.listdir(self.dest)), 10)

    def test_symlink_destination_and_staging_failure_leave_targets_untouched(self):
        target = os.path.join(self.root, "target")
        os.mkdir(target)
        os.symlink(target, self.dest)
        proc = run(self.root, "--dest=" + self.dest)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(os.listdir(target), [])
        os.unlink(self.dest)
        templates = os.path.join(self.root, "templates")
        shutil.copytree(TEMPLATES, templates)
        with open(os.path.join(templates, "stub.py"), "w") as handle:
            handle.write("@@UNRESOLVED@@")
        os.mkdir(self.dest)
        proc = run(self.root, "--dest=" + self.dest, "--templates=" + templates,
                   "--data=data/anndatas/cells.h5ad")
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(os.listdir(self.dest), [])
        self.assertEqual(read(os.path.join(self.root, "data", "anndatas", "cells.h5ad")), "x")

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
        book = json.loads(read(os.path.join(self.dest, "code", "03_explore_model.ipynb")))
        self.assertEqual(book["nbformat"], 4)
        self.assertEqual(book["metadata"]["kernelspec"]["name"], "python3")
        for cell in book["cells"]:
            self.assertRegex(cell["id"], r"^[A-Za-z0-9_-]+$")
            self.assertIsInstance(cell["source"], list)
        setup = "".join(book["cells"][1]["source"])
        self.assertIn('INPUT = Path("outputs/02_train_model.parquet")', setup)
        self.assertNotIn("assert ", setup)  # scilintr's runtime-assert would fail verify's lint

    def test_quoted_data_names_are_python_literals_in_workflow_and_notebook(self):
        basename = 'samples "quoted" \\new.tsv'
        write(os.path.join(self.root, "data", basename), "sample\nA\n")
        self.scaffold("--steps=01_look.ipynb", "--data=data/" + basename)
        snakefile = read(os.path.join(self.dest, "Snakefile"))
        match = re.search(r"        data=(\[.*\]),", snakefile)
        import ast
        self.assertEqual(ast.literal_eval(match.group(1)), ["data/" + basename])
        book = json.loads(read(os.path.join(self.dest, "code", "01_look.ipynb")))
        setup = "".join(book["cells"][1]["source"])
        parsed = ast.parse(setup)
        assignment = next(node for node in parsed.body if isinstance(node, ast.Assign)
                          and any(getattr(t, "id", None) == "INPUT" for t in node.targets))
        self.assertEqual(ast.literal_eval(assignment.value.args[0]), "data/" + basename)

    def test_r_stub_points_at_scilintr_stage_without_setting_one(self):
        self.scaffold()
        head = read(os.path.join(self.dest, "code", "01_prepare_data.R")).splitlines()[:10]
        self.assertTrue(any("scilintr stage" in line for line in head))
        # scilintr reads a stage from `# STAGE: <name>` in the first 10 lines; the guidance must not set one
        self.assertFalse(any(re.match(r"^\s*#\s*STAGE:\s*\S+", line) for line in head))

    def test_snakefile_chains_every_step_in_order(self):
        self.scaffold("--steps=01_load.py,04_fit.R,07_look.ipynb", "--data=data/anndatas/cells.h5ad")
        snakefile = read(os.path.join(self.dest, "Snakefile"))
        self.assertEqual(re.findall(r"^rule (\w+):", snakefile, re.M),
                         ["all", "step01_load", "step04_fit", "step07_look"])
        self.assertIn('rule all:\n    input:\n        "logs/07_look.ipynb",', snakefile)
        self.assertIn('data=["data/cells.h5ad"],', snakefile)
        self.assertIn('prev="outputs/01_load.parquet",\n        script="code/04_fit.R",', snakefile)
        self.assertIn('prev="outputs/04_fit.rds",\n        notebook="code/07_look.ipynb",', snakefile)
        self.assertIn("workdir: workflow.basedir", snakefile)
        self.assertNotIn("@@", snakefile)
        for name in ["01_load.py", "04_fit.R", "07_look.ipynb"]:
            self.assertIn(name, os.listdir(os.path.join(self.dest, "code")))

    def test_python_stub_fails_loudly(self):
        self.scaffold()
        proc = subprocess.run([sys.executable, "code/02_train_model.py", "in", "out"], cwd=self.dest,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not written yet", proc.stderr)

    def test_r_stub_fails_loudly(self):
        rscript = shutil.which("Rscript")
        if not rscript:
            self.skipTest("Rscript is not installed")
        self.scaffold()
        proc = subprocess.run([rscript, "code/01_prepare_data.R", "out"], cwd=self.dest,
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

    # --- manuscript panels -------------------------------------------------------------

    def audit(self):
        """manuscript-audit on the scaffold's contract, from the repository root."""
        return subprocess.run([sys.executable, AUDIT, "--root", self.root, "--config",
                               "analysis/demo-run/config/manuscript_checks.json"],
                              stdout=subprocess.PIPE, universal_newlines=True)

    def tree(self):
        found = {}
        for folder, _, names in os.walk(self.dest):
            for name in names:
                path = os.path.join(folder, name)
                found[os.path.relpath(path, self.dest)] = read(path)
        return found

    def test_panels_add_stubs_map_and_contract(self):
        write(os.path.join(self.root, "data", "DATA_MANIFEST.md"), "# Data\n")
        out = self.scaffold("--panels=Fig1a.R,Fig1b.py")
        for path in ("code/plot_Fig1a.R", "code/plot_Fig1b.py", "config/figure_map.tsv",
                     "config/manuscript_checks.json"):
            self.assertIn(path, out)
            self.assertTrue(os.path.isfile(os.path.join(self.dest, path)), path)
        rows = read(os.path.join(self.dest, "config", "figure_map.tsv")).splitlines()
        self.assertEqual(rows[0].split("\t")[:3], ["figure", "script", "source_data"])
        self.assertEqual([r.split("\t")[1] for r in rows[1:]],
                         ["analysis/demo-run/code/plot_Fig1a.R", "analysis/demo-run/code/plot_Fig1b.py"])
        contract = json.loads(read(os.path.join(self.dest, "config", "manuscript_checks.json")))
        self.assertEqual(contract["data_manifest"], "data/DATA_MANIFEST.md")
        self.assertEqual(self.audit().returncode, 3)  # nothing released yet: a gap, never a pass

    def test_panels_need_a_repository(self):
        with tempfile.TemporaryDirectory() as bare:
            proc = run(bare, "--dest=analysis/x", "--panels=Fig1a.R")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("needs a git or Mycelium repository", proc.stdout)
        for bad in ("Fig 1.R", "Fig1a.ipynb", "Fig1a.R,Fig1a.py"):
            self.assertEqual(run(self.root, "--dest=analysis/demo-run", "--panels=" + bad).returncode, 1, bad)

    def test_retrofit_adds_only_missing_files_and_never_overwrites(self):
        self.scaffold()
        mine = "figure\tscript\tsource_data\nFig3e\tcode/mine.R\tsrc.tsv\n"
        write(os.path.join(self.dest, "config", "figure_map.tsv"), mine)
        before = self.tree()
        dry = self.scaffold("--panels=Fig1a.R", "--dry-run")
        self.assertIn("would add code/plot_Fig1a.R", dry)
        self.assertIn("kept config/figure_map.tsv", dry)
        self.assertEqual(self.tree(), before)
        self.scaffold("--panels=Fig1a.R")
        after = self.tree()
        self.assertEqual(set(after) - set(before), {"code/plot_Fig1a.R", "config/manuscript_checks.json"})
        self.assertEqual({p: after[p] for p in before}, before)  # every existing byte unchanged
        again = self.scaffold("--panels=Fig1a.R")
        self.assertNotIn("added code", again)
        self.assertEqual(self.tree(), after)

    def test_retrofit_refuses_a_symlinked_code_folder(self):
        self.scaffold()
        outside = tempfile.mkdtemp()
        try:
            shutil.rmtree(os.path.join(self.dest, "code"))
            os.symlink(outside, os.path.join(self.dest, "code"))
            proc = run(self.root, "--dest=analysis/demo-run", "--panels=Fig1a.R")
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(os.listdir(outside), [])
        finally:
            shutil.rmtree(outside)

    def render_only(self, interpreter, stub, run_dir):
        """Run the stub without its export section: the panel must redraw from the released table alone."""
        text = read(stub)
        head, _, rest = text.partition("# ---- 1.")
        script = os.path.join(self.root, "render_only" + os.path.splitext(stub)[1])
        write(script, head + "# ---- 2." + rest.partition("# ---- 2.")[2])
        return subprocess.run([interpreter, script, run_dir], cwd=self.root, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)

    def check_stub_renders_from_source_only(self, interpreter, panel):
        self.scaffold("--panels=" + panel)
        stub = os.path.join(self.dest, "code", "plot_" + panel)
        run_dir = os.path.join(self.dest, "outputs", "run_20261026_demo")
        proc = subprocess.run([interpreter, stub, run_dir], cwd=self.root, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        os.symlink("run_20261026_demo", os.path.join(self.dest, "outputs", "current"))
        self.assertEqual(self.audit().returncode, 0, self.audit().stdout)
        figure = os.path.join(run_dir, "figures", panel.split(".")[0] + ".pdf")
        os.remove(figure)
        self.assertEqual(self.render_only(interpreter, stub, run_dir).returncode, 0)  # the table suffices
        self.assertTrue(os.path.isfile(figure))
        os.remove(os.path.join(run_dir, "source_data", panel.split(".")[0] + ".tsv"))
        self.assertNotEqual(self.render_only(interpreter, stub, run_dir).returncode, 0)  # and is required

    @unittest.skipUnless(subprocess.run([sys.executable, "-c", "import matplotlib"],
                                        stderr=subprocess.DEVNULL).returncode == 0, "matplotlib is not installed")
    def test_python_panel_renders_from_its_source_table_alone(self):
        self.check_stub_renders_from_source_only(sys.executable, "Fig1b.py")

    @unittest.skipUnless(shutil.which("Rscript"), "Rscript is not on PATH")
    def test_r_panel_renders_from_its_source_table_alone(self):
        self.check_stub_renders_from_source_only(shutil.which("Rscript"), "Fig1a.R")

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
        self.assertIsNone(self.gate_decision("python3 - --dest=analysis/demo-run --panels=Fig1a.R,Fig1b.py" + tail))
        # A bare positional path is read as the script to run, which is why SKILL.md
        # always uses --flag=value.
        self.assertEqual(self.gate_decision("python3 - --dest analysis/demo-run" + tail), "deny")


if __name__ == "__main__":
    unittest.main()
