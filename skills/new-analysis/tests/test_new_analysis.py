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
STEPS = ["01_prepare.R", "02_fit.R", "03_show.R"]
MIXED = "--steps=01_prepare.R,02_fit.py,03_explore.ipynb"  # one step of each kind, for the tests that need Python and a notebook


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
        self.assertEqual(set(os.listdir(os.path.join(self.dest, "code"))), set(STEPS + ["helpers.R", "theme.R", "theme.py"]))
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
        self.assertIn("| S02 | `analysis/demo-run/code/02_fit.R` |", plan)
        tracker = read(os.path.join(self.dest, "plans", "TRACKER.md"))
        self.assertIn("| S03 | `code/03_show.R` | todo | S02 |", tracker)
        self.assertIn("[DEMO_RUN.md](../DEMO_RUN.md)", tracker)
        self.assertIn("  reports/demo-run.qmd\n", out)
        report = read(os.path.join(self.dest, "reports", "demo-run.qmd"))
        self.assertEqual(sorted(os.listdir(os.path.join(self.dest, "reports"))),
                         ["README.md", "demo-run.qmd", "report-dark.scss", "report.scss"])  # the report and the theme it names
        self.assertNotIn("@@", report)
        self.assertIn('title: "demo-run"', report)
        self.assertIn("[DEMO_RUN.md](../DEMO_RUN.md)", report)
        self.assertEqual(report.count("::: {.panel-tabset}"), 3)
        self.assertEqual(report.count("\n:::\n"), 3)  # every tabset closed
        chain = report.split("```{mermaid}\n")[1].split("```")[0]
        self.assertEqual(chain.splitlines(), [
            "flowchart LR",
            '    d0[("data/cells.h5ad")] --> s01["code/01_prepare.R"] --> o01[("outputs/01_prepare/01_prepare.rds")]',
            '    o01 --> s02["code/02_fit.R"] --> o02[("outputs/02_fit/02_fit.rds")]',
            '    o02 --> s03["code/03_show.R"] --> o03[("outputs/03_show/source_data/03_show.tsv")]'])
        self.assertEqual(report.count("### 02 fit"), 2)  # one Methods tab, one Results tab
        self.assertIn('```{.r filename="code/02_fit.R"}', report)
        self.assertIn("[agent-derived: `outputs/02_fit/figures/02_[what-it-shows].png`]", report)

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
        self.assertTrue(doc.rstrip().endswith("| 03 | `code/03_show.R` | [what it does] "
                                              "| `outputs/03_show/source_data/03_show.tsv` |"))
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
        self.assertIn("| `outputs/02_fit/02_fit.rds` | [description] (step 02) |", doc)
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
        with open(os.path.join(templates, "stub.R"), "w") as handle:
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
        self.scaffold(MIXED)
        book = json.loads(read(os.path.join(self.dest, "code", "03_explore.ipynb")))
        self.assertEqual(book["nbformat"], 4)
        self.assertEqual(book["metadata"]["kernelspec"]["name"], "python3")
        for cell in book["cells"]:
            self.assertRegex(cell["id"], r"^[A-Za-z0-9_-]+$")
            self.assertIsInstance(cell["source"], list)
        setup = "".join(book["cells"][1]["source"])
        self.assertIn('STEP = Path(os.environ["STEP_DIR"])', setup)
        self.assertIn('OUTPUTS = Path(os.environ["OUTPUTS"])', setup)
        self.assertIn('INPUT = OUTPUTS / "02_fit" / "02_fit.parquet"', setup)
        self.assertNotIn("RUN_DIR", setup)
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
        head = read(os.path.join(self.dest, "code", "01_prepare.R")).splitlines()[:10]
        self.assertTrue(any("scilintr stage" in line for line in head))
        # scilintr reads a stage from `# STAGE: <name>` in the first 10 lines; the guidance must not set one
        self.assertFalse(any(re.match(r"^\s*#\s*STAGE:\s*\S+", line) for line in head))

    def test_snakefile_chains_every_step_in_order(self):
        self.scaffold("--steps=01_load.py,04_fit.R,07_look.ipynb", "--data=data/anndatas/cells.h5ad")
        snakefile = read(os.path.join(self.dest, "Snakefile"))
        self.assertEqual(re.findall(r"^rule (\w+):", snakefile, re.M),
                         ["all", "step01_load", "step04_fit", "step07_look"])
        self.assertIn('rule all:\n    input:\n        "outputs/07_look/07_look.parquet",', snakefile)
        self.assertIn('data=["data/cells.h5ad"],', snakefile)
        self.assertIn('prev="outputs/01_load/01_load.tsv",\n        script="code/04_fit.R",', snakefile)
        self.assertIn('prev="outputs/04_fit/04_fit.tsv",\n        notebook="code/07_look.ipynb",', snakefile)
        self.assertIn("workdir: workflow.basedir", snakefile)
        self.assertNotIn("@@", snakefile)
        for name in ["01_load.py", "04_fit.R", "07_look.ipynb"]:
            self.assertIn(name, os.listdir(os.path.join(self.dest, "code")))

    def test_python_stub_fails_loudly(self):
        self.scaffold(MIXED)
        proc = subprocess.run([sys.executable, "code/02_fit.py", "in", "out"], cwd=self.dest,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not written yet", proc.stderr)

    def test_r_stub_fails_loudly(self):
        rscript = shutil.which("Rscript")
        if not rscript:
            self.skipTest("Rscript is not installed")
        self.scaffold()
        proc = subprocess.run([rscript, "code/01_prepare.R", "out"], cwd=self.dest,
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
        self.assertEqual(contract["figures"][0]["source_data"], "analysis/demo-run/outputs/panels/source_data/Fig1a.tsv")
        self.assertEqual(contract["figures"][0]["outputs"], ["analysis/demo-run/outputs/panels/figures/Fig1a.pdf"])
        self.assertEqual(self.audit().returncode, 3)  # nothing released yet: a gap, never a pass

    def test_qmd_steps_render_through_a_quarto_project(self):
        out = self.scaffold("--steps=01_prep.qmd,02_fit.qmd", "--lang=python", "--data=data/anndatas/cells.h5ad")
        self.assertIn("rendered by quarto", out)
        snake = read(os.path.join(self.dest, "Snakefile"))
        self.assertIn('"STEP_DIR=outputs/02_fit OUTPUTS=outputs {QUARTO:q} render {input.script:q} '
                      '--output-dir outputs/02_fit > {log:q} 2>&1 && mv outputs/02_fit/code/02_fit.html '
                      'outputs/02_fit/02_fit.html && rmdir outputs/02_fit/code"', snake.replace("THREADS + ", ""))
        self.assertIn('"outputs/02_fit/02_fit.parquet"', snake)
        self.assertIn('"outputs/02_fit/02_fit.html"', snake)
        self.assertNotIn("reports/site", snake)
        self.assertIn('input:\n        "outputs/02_fit/02_fit.parquet",\n        "outputs/02_fit/02_fit.html",', snake.split("rule all:")[1])
        project = read(os.path.join(self.dest, "_quarto.yml"))
        self.assertIn("  execute-dir: project", project)
        self.assertNotIn("website", project)
        self.assertNotIn("output-dir", project)
        self.assertIn("```{python}", read(os.path.join(self.dest, "code", "01_prep.qmd")))
        self.assertFalse(os.path.exists(os.path.join(self.dest, "reports", "demo-run.qmd")))  # the steps are the report
        quarto = read(os.path.join(self.dest, "_quarto.yml"))  # the site's theme files exist where _quarto.yml points
        for theme in ("report.scss", "report-dark.scss"):
            self.assertIn("reports/" + theme, quarto)
            self.assertTrue(os.path.isfile(os.path.join(self.dest, "reports", theme)))

    def test_format_names_the_default_steps_and_a_flag_beats_gate_json(self):
        write(os.path.join(self.root, ".mycelium-extra", "gate.json"), json.dumps({"step_format": "qmd"}))
        out = self.scaffold()
        self.assertIn("step_format in .mycelium-extra/gate.json", out)
        self.assertEqual(sorted(os.listdir(os.path.join(self.dest, "code"))),
                         ["01_prepare.qmd", "02_fit.qmd", "03_show.qmd", "theme.R", "theme.py"])
        self.assertIn("```{r}", read(os.path.join(self.dest, "code", "01_prepare.qmd")))
        shutil.rmtree(self.dest)
        self.scaffold("--format=R", "--steps=01_a,02_b.py")
        self.assertEqual(sorted(os.listdir(os.path.join(self.dest, "code"))), ["01_a.R", "02_b.py", "theme.R", "theme.py"])
        self.assertTrue(os.path.exists(os.path.join(self.dest, "reports", "demo-run.qmd")))  # not all steps are qmd

    def test_refuses_a_bare_step_name_with_no_format_and_a_bad_step_format(self):
        proc = run(self.root, "--dest=analysis/demo-run", "--steps=01_a")
        self.assertIn("refused", proc.stdout)
        write(os.path.join(self.root, ".mycelium-extra", "gate.json"), json.dumps({"step_format": "docx"}))
        proc = run(self.root, "--dest=analysis/demo-run")
        self.assertIn('"step_format"', proc.stdout)
        self.assertFalse(os.path.exists(self.dest))

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
        run_dir = os.path.join(self.dest, "outputs", "03_show")
        proc = subprocess.run([interpreter, stub, run_dir], cwd=self.root, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
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

    def test_marimo_step_is_a_named_cell_notebook_the_snakefile_runs(self):
        out = self.scaffold("--steps=01_prep.py,02_explore.marimo.py")
        path = os.path.join(self.dest, "code", "02_explore.marimo.py")
        text = read(path)
        compile(text, path, "exec")
        self.assertNotIn("@@", text)
        self.assertIn("with app.setup:", text)
        self.assertIn('INPUT = OUTPUTS / "01_prep" / "01_prep.parquet"', text)
        self.assertIn('if __name__ == "__main__":\n    app.run()', text)
        snake = read(os.path.join(self.dest, "Snakefile"))
        self.assertIn("rule step02_explore:", snake)
        self.assertIn('notebook="code/02_explore.marimo.py"', snake)
        self.assertIn('"outputs/02_explore/02_explore.parquet"', snake)
        self.assertIn("STEP_DIR=outputs/02_explore OUTPUTS=outputs {PYTHON:q} -u {input.notebook:q}", snake)
        self.assertIn("marimo export html code/02_explore.marimo.py", out)
        marimo_python = os.environ.get("MARIMO_PYTHON")  # a python with marimo installed runs the stub for real
        if not marimo_python:
            self.skipTest("set MARIMO_PYTHON to run the stub under marimo")
        write(os.path.join(self.dest, "outputs", "01_prep", "01_prep.parquet"))
        proc = subprocess.run([marimo_python, "code/02_explore.marimo.py"], cwd=self.dest,
                              env=dict(os.environ, STEP_DIR="outputs/02_explore", OUTPUTS="outputs"),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertNotEqual(proc.returncode, 0)  # the stub stops until it is written
        self.assertIn("02_explore.marimo.py is not written yet", proc.stderr)

    def test_marimo_format_names_default_steps_marimo_py(self):
        self.scaffold("--format=marimo")
        self.assertIn("03_show.marimo.py", os.listdir(os.path.join(self.dest, "code")))

    def env_file(self, r, python):
        bindir = os.path.join(self.root, "env", "bin")
        for name in ("Rscript", "python", "jupyter"):
            write(os.path.join(bindir, name))
        write(os.path.join(self.root, "lucid-coder.yaml"),
              "version: 1\nenv:\n  manager: conda\n  name: R4\n  r: {}   # command -v Rscript\n  python: \"{}\"\n"
              "formatters:\n  air: \"0.x\"\n".format(r, python))
        return bindir

    def test_interpreters_come_from_lucid_coder_yaml(self):
        bindir = self.env_file(os.path.join(self.root, "env", "bin", "Rscript"),
                               os.path.join(self.root, "env", "bin", "python"))
        out = self.scaffold()
        snake = read(os.path.join(self.dest, "Snakefile"))
        for key, name in (("rscript", "Rscript"), ("python", "python"), ("jupyter", "jupyter")):
            self.assertIn('config.get("{}", {})'.format(key, json.dumps(os.path.join(bindir, name))), snake)
        self.assertIn("defaults from lucid-coder.yaml", snake)
        self.assertIn("environment: jupyter, python, rscript from lucid-coder.yaml", out)

    def test_a_dangling_interpreter_keeps_the_bare_name_and_warns(self):
        self.env_file("/nowhere/Rscript", os.path.join(self.root, "env", "bin", "python"))
        out = self.scaffold()
        snake = read(os.path.join(self.dest, "Snakefile"))
        self.assertIn('config.get("rscript", "Rscript")', snake)
        self.assertIn("WARNING: rscript in lucid-coder.yaml is not a file", out)

    def test_without_lucid_coder_yaml_the_names_on_path_stay(self):  # control
        out = self.scaffold()
        snake = read(os.path.join(self.dest, "Snakefile"))
        self.assertIn('config.get("rscript", "Rscript")', snake)
        self.assertIn('config.get("python", "python")', snake)
        self.assertIn("defaults are the names on PATH", snake)
        self.assertIn("environment: none recorded", out)

    # --- stress-test fixes -------------------------------------------------------------

    def test_folder_follows_the_umask_not_mkdtemp_0700(self):
        self.scaffold()
        mode = os.stat(self.dest).st_mode & 0o777
        umask = os.umask(0)
        os.umask(umask)
        self.assertEqual(mode, 0o777 & ~umask)

    def test_handoff_between_languages_is_a_tsv_and_notebooks_write_a_table(self):
        self.scaffold(MIXED)
        snake = read(os.path.join(self.dest, "Snakefile"))
        self.assertIn('"outputs/01_prepare/01_prepare.tsv"', snake)  # R to Python
        self.assertIn('"outputs/02_fit/02_fit.parquet"', snake)  # Python to Python keeps its type
        self.assertIn('"outputs/03_explore/03_explore.parquet",', snake)
        self.assertIn('"outputs/03_explore/03_explore.ipynb",', snake)  # the executed copy sits in the step folder
        self.assertIn("--output-dir outputs/03_explore", snake)
        book = json.loads(read(os.path.join(self.dest, "code", "03_explore.ipynb")))
        setup = "".join(book["cells"][1]["source"])
        self.assertIn('OUTPUT = STEP / "03_explore.parquet"', setup)

    def test_mycelium_root_is_the_nearest_living_folder_inside_a_bigger_git_repo(self):
        os.rmdir(os.path.join(self.root, ".living"))
        sub = os.path.join(self.root, "proj")
        os.makedirs(os.path.join(sub, ".living"))
        proc = run(sub, "--dest=analysis/demo-run")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(os.path.isfile(os.path.join(sub, "analysis", "demo-run", "DEMO_RUN.md")))
        self.assertIn("suggested analysis/ANALYSIS_MANIFEST.md entry", proc.stdout)

    def test_retrofit_warns_about_a_panel_the_kept_contract_lacks_and_refuses_a_second_kind(self):
        self.scaffold("--panels=Fig1a.R")
        out = self.scaffold("--panels=Fig1a.R,Fig1b.py")
        self.assertIn("WARNING: Fig1b not in kept config/figure_map.tsv", out)
        self.assertIn("WARNING: Fig1b not in kept config/manuscript_checks.json", out)
        proc = run(self.root, "--dest=analysis/demo-run", "--panels=Fig1a.py")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("refused", proc.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.dest, "code", "plot_Fig1a.py")))

    def test_lucid_coder_yaml_reads_only_env_expands_paths_and_survives_bad_bytes(self):
        tool = os.path.join(self.root, "bin", "Rscript")
        write(tool)
        write(os.path.join(self.root, "lucid-coder.yaml"),
              "packages:\n  python: {}\nenv:\n  r: bin/Rscript\n".format(os.path.join(self.root, "nope")))
        self.scaffold()
        snake = read(os.path.join(self.dest, "Snakefile"))
        self.assertIn(json.dumps(tool), snake)  # relative to the repository root, written absolute
        self.assertIn('config.get("python", "python")', snake)  # packages: did not set it
        shutil.rmtree(self.dest)
        with open(os.path.join(self.root, "lucid-coder.yaml"), "wb") as handle:
            handle.write(b"env:\n  r: \xff\xfe\n")
        self.assertIn("could not be read", self.scaffold())

    def test_unparsable_gate_json_is_noted(self):
        write(os.path.join(self.root, ".mycelium-extra", "gate.json"), "{not json")
        self.assertIn("gate.json does not parse", self.scaffold())

    def test_logs_and_outputs_survive_a_clone(self):
        self.scaffold()
        for folder in ("logs", "outputs"):
            self.assertTrue(os.path.isfile(os.path.join(self.dest, folder, ".gitkeep")))


    # --- step folders, theme, README and SOURCES ----------------------------------

    def test_every_rule_names_its_own_step_folder(self):
        self.scaffold(MIXED, "--data=data/anndatas/cells.h5ad")
        snake = read(os.path.join(self.dest, "Snakefile"))
        for old in ("RUN", "OUT", "config.get(\"run\")", "run_<", "RUN.txt", "RUN_DIR"):
            self.assertNotIn(old, snake.replace("OUTPUTS", ""))
        rules = re.split(r"^rule ", snake, flags=re.M)[1:]
        self.assertEqual(len(rules), 4)
        for body in rules[1:]:
            stem = re.search(r'log:\n        "outputs/(\w+)/logs/', body).group(1)
            declared = body.split("shell:")[0]
            for path in re.findall(r'"(outputs/[^"]*)"', declared.split("log:")[0].split("output:")[1]):
                self.assertTrue(path.startswith("outputs/{}/".format(stem)), path)  # an output only in its own folder
        self.assertIn('"outputs/02_fit/logs/02_fit.log"', snake)
        self.assertIn('"outputs/02_fit/logs/02_fit.benchmark.tsv"', snake)
        self.assertIn("each step owns outputs/<step>/".lower(), snake.lower().replace("\n", " ").replace("  ", " "))
        self.assertIn("overwrites", snake)
        self.assertIn("bash run.sh", snake)

    def test_figure_step_writes_figures_and_source_data_under_one_stem(self):
        self.scaffold()
        snake = read(os.path.join(self.dest, "Snakefile"))
        for out in ("figures/03_show.png", "figures/03_show.pdf", "source_data/03_show.tsv"):
            self.assertEqual(snake.count('"outputs/03_show/' + out + '"'), 2)  # in rule all and in the step's rule
        stub = read(os.path.join(self.dest, "code", "03_show.R"))
        self.assertIn('source("code/theme.R")', stub)
        self.assertIn('file.path(step_dir, "source_data", "03_show.tsv")', stub)
        self.assertIn('save_panel(p, step_dir, "03_show")', stub)
        self.assertIn("Rscript code/03_show.R outputs/02_fit/02_fit.rds outputs/03_show", stub)
        self.assertIn("outputs/03_show/figures/03_show.png", stub)
        self.assertNotIn("@@", stub)

    def test_theme_files_are_written_to_code(self):
        self.scaffold()
        theme_r = read(os.path.join(self.dest, "code", "theme.R"))
        self.assertIn("theme_set(ggpubr::theme_pubr(base_size = 8))", theme_r)
        self.assertIn("PALETTE <- c(", theme_r)
        self.assertIn("labels not in PALETTE", theme_r)
        self.assertIn("save_panel <- function(p, dir, stem, width = 89, height = 70)", theme_r)
        self.assertIn("device = cairo_pdf", theme_r)
        theme_py = os.path.join(self.dest, "code", "theme.py")
        compile(read(theme_py), theme_py, "exec")
        self.assertIn("raise ValueError", read(theme_py))
        self.assertIn("def save_panel(p, dir, stem, width=89, height=70)", read(theme_py))

    def test_panel_stubs_use_the_theme(self):
        self.scaffold("--panels=Fig1a.R,Fig1b.py")
        r_stub = read(os.path.join(self.dest, "code", "plot_Fig1a.R"))
        py_stub = read(os.path.join(self.dest, "code", "plot_Fig1b.py"))
        self.assertIn('source("analysis/demo-run/code/theme.R")', r_stub)
        self.assertIn("ggplot(plotted", r_stub)
        self.assertNotIn("plot(plotted$x", r_stub)
        self.assertIn("from theme import palette_for, save_panel", py_stub)
        self.assertIn("ggplot(plotted", py_stub)
        self.assertNotIn("matplotlib", py_stub)

    def test_reports_readme_and_sources_have_the_contract_rows(self):
        write(os.path.join(self.root, "data", "DATA_MANIFEST.md"), "# Data\n\n## raw-cells-v3\n\n`cells.h5ad`: the cells\n")
        write(os.path.join(self.root, "data", "other.csv"), "a\n")
        self.scaffold("--data=data/anndatas/cells.h5ad", "--data=data/other.csv")
        self.assertEqual(read(os.path.join(self.dest, "data", "SOURCES.md")),
                         "# Data sources\n\n| Link | Target | DATA_MANIFEST | Pinned by plan |\n|---|---|---|---|\n"
                         "| `cells.h5ad` | `data/anndatas/cells.h5ad` | raw-cells-v3 | |\n"
                         "| `other.csv` | `data/other.csv` | not listed | |\n")
        self.assertEqual(read(os.path.join(self.dest, "reports", "README.md")),
                         "# Reports\n\n| File | What it is | From outputs | Owner |\n|---|---|---|---|\n"
                         "| `demo-run.qmd` | the record | | analysis-report |\n"
                         "| `demo-run.html` | its render | | quarto render |\n"
                         "| `report.scss`, `report-dark.scss` | theme, DESIGN.md tokens | \u2014 | you |\n\n"
                         "The Artifact evaluation page lives in `.mycelium-extra/artifacts/` and is not a record.\n")

    def test_sources_say_not_listed_without_a_manifest_and_qmd_steps_add_no_site_row(self):
        self.scaffold("--steps=01_a.qmd", "--data=data/anndatas/cells.h5ad")
        self.assertIn("| `cells.h5ad` | `data/anndatas/cells.h5ad` | not listed | |", read(os.path.join(self.dest, "data", "SOURCES.md")))
        readme = read(os.path.join(self.dest, "reports", "README.md"))
        self.assertNotIn("site/", readme)
        self.assertNotIn("demo-run.qmd", readme)  # every step is qmd: no report skeleton

    def test_plan_names_the_approved_copy(self):
        self.scaffold()
        plan = read(os.path.join(self.dest, "plans", "PLAN.md")).splitlines()
        self.assertEqual(plan[2], "The approved copy is provenance/plan-<hash>.md; this file is the draft.")

    def test_listing_names_the_new_files(self):
        out = self.scaffold("--data=data/anndatas/cells.h5ad")
        for path in ("reports/README.md", "data/SOURCES.md", "code/theme.R", "code/theme.py"):
            self.assertIn("  " + path + "\n", out)


if __name__ == "__main__":
    unittest.main()
