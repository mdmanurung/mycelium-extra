"""Real end-to-end smoke test: scaffold, run with real Snakemake, R, Python and Quarto, then read the results.

Run:  python3.11 tests/e2e_real.py        (exit 0 on pass; about 3 to 10 minutes, longer on a busy machine)

It is opt-in: the name does not start with test_, so no CI loop picks it up. A missing tool is a failure
with a message, never a skip. Tools come from environment variables, each defaulting to the HPC path below
when that file exists:

    MX_RSCRIPT    Rscript with dplyr, ggplot2, ggpubr, knitr and rmarkdown
    MX_SNAKEMAKE  snakemake
    MX_QUARTO     quarto (always an absolute path: the quarto shim in the R4_51 env is broken)
    MX_PYTHON     python with pandas, pyarrow, jupyter and ipykernel
    MX_E2E_KEEP=1 keep the temporary folder (its path is printed either way on failure)

Everything runs in a temporary git repository with synthetic data; nothing outside it is read or written.
Each stage prints its name, so a failure says which stage broke. Fixtures: tests/fixtures/smoke/.

Stages: tools, setup, scaffold, where-not-run, run-1, where-current, panel, edit-stale, run-2, change-log,
dry-runs, flagged-run, failing-step, where-failed, plain-rerun-fails, repair, verify-runs, analysis-report, tables-only, no-marker.
"""

import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures" / "smoke"
PY_SH = REPO / "hooks" / "py.sh"
TEMPLATES = REPO / "skills" / "new-analysis" / "templates"
NEW_ANALYSIS = REPO / "skills" / "new-analysis" / "scripts" / "new_analysis.py"
VERIFY = REPO / "skills" / "verify" / "scripts" / "verify.py"
ANALYSIS_REPORT = REPO / "skills" / "analysis-report" / "scripts" / "analysis_report.py"
WHEREAMI = REPO / "hooks" / "whereami.py"
CONDA = "/exports/archive/hg-funcgenom-research/mdmanurung/conda/envs"
TOOLS = {  # name: (environment variable, HPC default)
    "rscript": ("MX_RSCRIPT", CONDA + "/R4_51/bin/Rscript"),
    "snakemake": ("MX_SNAKEMAKE", CONDA + "/snakemake/bin/snakemake"),
    "quarto": ("MX_QUARTO", "/exports/para-lipg-hpc/mdmanurung/tools/quarto-1.10.19/bin/quarto"),
    "python": ("MX_PYTHON", CONDA + "/scvi-test/bin/python"),
}
STEPS = ["01_scan", "02_fit", "03_show", "04_page"]
TIMEOUT = 1500  # seconds per command; the machine this was written on had a load above 100 on 4 CPUs


class Fail(Exception):
    pass


def check(condition, message):
    if not condition:
        raise Fail(message)


def tail(text, lines=25):
    return "\n".join(text.rstrip().splitlines()[-lines:])


class Smoke:
    def __init__(self, tools, root):
        self.tools = tools
        self.root = root
        self.main = root / "analysis" / "smoke"
        self.tables = root / "analysis" / "tables_only"
        scratch = root / "_env"
        path = os.pathsep.join(sorted({str(Path(p).parent) for p in tools.values()}) + [os.environ.get("PATH", "")])
        self.env = dict(
            os.environ, PATH=path, XDG_CACHE_HOME=str(scratch / "cache"), JUPYTER_DATA_DIR=str(scratch / "jupyter"),
            JUPYTER_RUNTIME_DIR=str(scratch / "jupyter-runtime"), IPYTHONDIR=str(scratch / "ipython"),
            MYCELIUM_EXTRA_PYTHON=sys.executable, QUARTO_R=tools["rscript"], QUARTO_PYTHON=tools["python"],
            SNAKEMAKE=tools["snakemake"], CORES="2", PYTHONDONTWRITEBYTECODE="1", LC_ALL="C.UTF-8",
        )
        self.config = ["--config", "rscript=" + tools["rscript"], "python=" + tools["python"],
                       "quarto=" + tools["quarto"], "jupyter=" + str(Path(tools["python"]).parent / "jupyter")]

    # ---------------------------------------------------------------- helpers

    def spawn(self, command, cwd, handle):
        # Own process group: a timeout or Ctrl-C kills snakemake, Rscript and quarto too.
        proc = subprocess.Popen(command, cwd=cwd, env=self.env, stdin=handle, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, start_new_session=True)
        try:
            stdout, _ = proc.communicate(timeout=TIMEOUT)
        except BaseException:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                proc.kill()
            proc.communicate()
            raise
        return subprocess.CompletedProcess(command, proc.returncode, stdout)

    def run(self, command, cwd=None, stdin=None, ok=True):
        handle = open(str(stdin)) if stdin else subprocess.DEVNULL
        try:
            result = self.spawn([str(c) for c in command], str(cwd or self.root), handle)
        finally:
            if stdin:
                handle.close()
        out = result.stdout.decode("utf-8", "replace")
        check((result.returncode == 0) == ok, "{} exited {} (expected {}):\n{}".format(
            " ".join(str(c) for c in command[:4]), result.returncode, "0" if ok else "non-zero", tail(out)))
        return out

    def run_sh(self, analysis, *args, ok=True):
        return self.run(["bash", "run.sh"] + list(args) + self.config, cwd=analysis, ok=ok)

    def scaffold(self, name, steps, extra=()):
        out = self.run(["sh", PY_SH, "-", "--dest=analysis/" + name, "--steps=" + steps, "--templates=" + str(TEMPLATES)]
                       + list(extra), stdin=NEW_ANALYSIS)
        check("refused" not in out and "created analysis/" + name in out, "scaffold of {} did not create it:\n{}".format(
            name, tail(out)))

    def install(self, analysis, fixture_dir):
        for source in sorted(fixture_dir.iterdir()):
            shutil.copyfile(str(source), str(analysis / "code" / source.name))

    def where(self, analysis):
        """The step marks of the full card, e.g. {"01_scan": "x"}; --no-write keeps the repository clean."""
        out = self.run([sys.executable, WHEREAMI, "--repo", self.root, "--cwd", analysis, "--no-write"])
        marks = dict((stem, mark) for mark, stem in re.findall(r"^  \[(.)\] (\S+)$", out, re.M))
        check(marks, "where printed no step marks for {}:\n{}".format(analysis.name, out))
        return marks, out

    def expect_marks(self, analysis, wanted):
        marks, out = self.where(analysis)
        check(marks == wanted, "where marks {} for {}, wanted {}:\n{}".format(marks, analysis.name, wanted, out))

    def entries(self, analysis):
        """One dict per logs/CHANGES.md entry: the heading, the code lines and the output folders."""
        path = analysis / "logs" / "CHANGES.md"
        if not path.is_file():
            return []
        found = []
        for block in re.split(r"(?m)^## ", path.read_text())[1:]:
            lines = block.splitlines()
            found.append({"heading": lines[0], "code": [l for l in lines if l.startswith("- code/")],
                          "outputs": [l for l in lines if l.startswith("- outputs/")]})
        return found

    def edit(self, path, old, new):
        text = path.read_text()
        check(old in text, "{} has no line {!r} to edit".format(path.name, old))
        path.write_text(text.replace(old, new, 1))

    def read_runs(self, analysis):
        return self.run(["sh", PY_SH, "-", "--plugin-root=" + str(REPO), "--repo=" + str(self.root), "runs",
                         analysis / "outputs"], stdin=VERIFY)

    # ---------------------------------------------------------------- stages

    def setup(self):
        scratch = self.root / "_env"
        scratch.mkdir()
        self.run(["git", "init", "-q", "."])
        (self.root / ".living").mkdir()
        # quarto's jupyter engine looks for a kernel named python3 in JUPYTER_DATA_DIR, which is a temp folder
        self.run([self.tools["python"], "-m", "ipykernel", "install", "--user", "--name", "python3"])

    def scaffold_main(self):
        self.scaffold("smoke", ",".join(["01_scan.R", "02_fit.py", "03_show.R", "04_page.qmd"]),
                      ["--lang=r", "--panels=Fig1a.R"])
        for name in ("Snakefile", "run.sh", "code/theme.R", "code/plot_Fig1a.R", "plans/PLAN.md", "outputs/.gitkeep"):
            check((self.main / name).is_file(), "scaffold wrote no " + name)
        stub = self.run([self.tools["rscript"], "code/01_scan.R", "x.tsv"], cwd=self.main, ok=False)
        check("not written yet" in stub, "the scanned stub should fail on purpose:\n" + stub)
        self.install(self.main, FIXTURES / "main")

    def where_not_run(self):
        self.expect_marks(self.main, dict.fromkeys(STEPS, " "))

    def run_1(self):
        self.run_sh(self.main)
        out = self.main / "outputs"
        for stem, name in [("01_scan", "01_scan.tsv"), ("02_fit", "02_fit.tsv"), ("03_show", "figures/03_show.png"),
                           ("03_show", "figures/03_show.pdf"), ("03_show", "source_data/03_show.tsv"),
                           ("04_page", "04_page.rds"), ("04_page", "04_page.html")]:
            check((out / stem / name).is_file(), "missing outputs/{}/{}".format(stem, name))
        check(sorted(p.name for p in out.glob("run_*")) == [], "a run_* folder exists: the layout is per-step folders")
        check(not list(self.main.rglob("RUN.txt")), "a RUN.txt was written: the layout has none")
        html = (out / "04_page" / "04_page.html").read_text(errors="replace")
        check("<html" in html.lower(), "outputs/04_page/04_page.html is not an HTML page")
        check((out / "04_page" / "logs" / "04_page.session.txt").is_file(), "the qmd step wrote no session file in logs/")
        check(not (out / "04_page" / "code").exists(), "the qmd step left outputs/04_page/code/ behind")
        found = self.entries(self.main)
        check(len(found) == 1 and found[0]["heading"].endswith(" ok"), "want one ok entry in CHANGES.md, got {}".format(found))
        check("- code/02_fit.py: new" in found[0]["code"], "entry 1 does not list code/02_fit.py as new: {}".format(found[0]))
        check(found[0]["outputs"] == ["- outputs/{}/".format(s) for s in STEPS], "entry 1 outputs: {}".format(found[0]["outputs"]))

    def where_current(self):
        self.expect_marks(self.main, dict.fromkeys(STEPS, "x"))

    def panel(self):
        panels = self.main / "outputs" / "panels"
        self.run([self.tools["rscript"], "analysis/smoke/code/plot_Fig1a.R", panels.relative_to(self.root)])
        for name in ("source_data/Fig1a.tsv", "figures/Fig1a.png", "figures/Fig1a.pdf"):
            check((panels / name).is_file(), "the panel wrote no outputs/panels/" + name)

    def edit_stale(self):
        time.sleep(1.1)  # the script must be newer than the outputs at one-second resolution
        self.edit(self.main / "code" / "02_fit.py", "FACTOR = 2", "FACTOR = 3")
        self.expect_marks(self.main, {"01_scan": "x", "02_fit": "~", "03_show": "~", "04_page": "~"})

    def run_2(self):
        self.run_sh(self.main)
        fit = (self.main / "outputs" / "02_fit" / "02_fit.tsv").read_text().splitlines()
        check(fit[1].endswith("\t6.0"), "02_fit did not rerun with FACTOR = 3: {}".format(fit[:2]))
        self.expect_marks(self.main, dict.fromkeys(STEPS, "x"))

    def change_log(self):
        found = self.entries(self.main)
        check(len(found) == 2, "want two CHANGES.md entries, got {}".format(len(found)))
        check(found[1]["code"] == ["- code/02_fit.py: changed"], "entry 2 must name only the edited script: {}".format(found[1]))
        check(found[1]["outputs"] == ["- outputs/{}/".format(s) for s in STEPS[1:]],
              "entry 2 must list the steps after 02_fit: {}".format(found[1]["outputs"]))

    def dry_runs(self):
        before = (self.main / "logs" / "CHANGES.md").read_text()
        for flag in ("-pn", "-n"):
            self.run_sh(self.main, flag)
            check((self.main / "logs" / "CHANGES.md").read_text() == before, "run.sh {} logged an entry".format(flag))

    def flagged_run(self):
        # -R has an n in the rule name but is no dry run: it reruns step 01 and what follows, and it logs
        self.run_sh(self.main, "-Rstep01_scan")
        found = self.entries(self.main)
        check(len(found) == 3, "run.sh -Rstep01_scan must log one entry (got {} in all)".format(len(found)))
        check(found[2]["code"] == [] and "- outputs/01_scan/" in found[2]["outputs"],
              "the -R entry should list 01_scan and no code change: {}".format(found[2]))

    def failing_step(self):
        show = self.main / "code" / "03_show.R"
        self.edit(show, "set.seed(0)\n", 'set.seed(0)\nstop("boom")\n')
        # The second run is forced with -R: a plain rerun of the same script is a no-op for Snakemake (the output
        # of the failed step is gone, but its downstream page is still up to date). It lists the edit again only
        # if the first failed run kept the old hashes.
        for attempt, flags in ((1, []), (2, ["-Rstep03_show"])):
            out = self.run_sh(self.main, *flags, ok=False)
            found = self.entries(self.main)
            check(len(found) == 3 + attempt and found[-1]["heading"].endswith(" failed"),
                  "failing run {} must log a failed entry: {}".format(attempt, found[-1:]))
            check(found[-1]["code"] == ["- code/03_show.R: changed"],
                  "failing run {} must list the unrepaired edit (kept hashes): {}\n{}".format(attempt, found[-1], tail(out, 8)))

    def where_failed(self):
        marks, out = self.where(self.main)
        check(marks.get("03_show") == "!", "where should mark 03_show failed: {}\n{}".format(marks, out))

    def plain_rerun_of_unrepaired(self):
        # A plain rerun with the script still unrepaired must fail and log "failed". It once exited 0 and logged
        # "ok": rule all asked only for the last step's outputs, so Snakemake saw "Nothing to be done" while
        # outputs/03_show/ held no figures. rule all now also requests every step's outputs.
        shown = self.main / "outputs" / "03_show" / "figures" / "03_show.png"
        before = len(self.entries(self.main))
        out = self.run_sh(self.main, ok=False)
        after = self.entries(self.main)
        check(len(after) == before + 1 and after[-1]["heading"].endswith(" failed"),
              "a plain rerun with 03_show unrepaired must log a failed entry (had {}, now {}): {}\n{}".format(
                  before, len(after), after[-1:], tail(out, 8)))
        check(not shown.exists(), "the failing step left " + str(shown))

    def repair(self):
        self.edit(self.main / "code" / "03_show.R", 'stop("boom")\n', "# repaired\n")
        self.run_sh(self.main)
        found = self.entries(self.main)
        check(found[-1]["heading"].endswith(" ok") and found[-1]["code"] == ["- code/03_show.R: changed"],
              "the repair run must log an ok entry naming 03_show.R: {}".format(found[-1]))
        self.expect_marks(self.main, dict.fromkeys(STEPS, "x"))

    def verify_runs(self):
        out = self.read_runs(self.main)
        for stem in STEPS + ["panels"]:
            check("| {} |".format(stem) in out, "verify runs lists no row for {}:\n{}".format(stem, out))
        check("Last change: " in out and "none logged" not in out, "verify runs shows no last change:\n" + out)
        check("holds no files" not in out and "RUN.txt" not in out, "verify runs reports a step problem:\n" + out)

    def analysis_report(self):
        out = self.run(["sh", PY_SH, "-", "--dest=analysis/smoke", "--templates=" + str(TEMPLATES), "--dry-run"],
                       stdin=ANALYSIS_REPORT)
        check(all(stem in out for stem in STEPS), "analysis_report --dry-run names not every step:\n" + tail(out, 40))

    def tables_only(self):
        # A Python qmd step and a table-only step: no figures, source_data or tables folder anywhere, so the
        # step folders hold only their outputs and logs/. They must still read as a steps layout.
        self.scaffold("tables_only", "01_calc.py,02_page.qmd", ["--lang=python"])
        self.install(self.tables, FIXTURES / "tables_only")
        self.run_sh(self.tables)
        out = self.tables / "outputs"
        for name in ("01_calc/01_calc.parquet", "02_page/02_page.parquet", "02_page/02_page.html"):
            check((out / name).is_file(), "missing outputs/" + name)
        for stem in ("01_calc", "02_page"):
            extra = {p.name for p in (out / stem).iterdir()} & {"figures", "source_data", "tables"}
            check(not extra, "outputs/{} holds {}: the fixture must stay table-only".format(stem, sorted(extra)))
        self.table_only_reads_as_steps()

    def table_only_reads_as_steps(self):
        self.expect_marks(self.tables, {"01_calc": "x", "02_page": "x"})
        runs = self.read_runs(self.tables)
        for stem in ("01_calc", "02_page"):
            check("| {} |".format(stem) in runs, "verify runs lists no row for table-only step {}:\n{}".format(stem, runs))
        check("No `run_" not in runs, "verify runs found no steps layout in a table-only analysis:\n" + runs)

    def no_marker(self):
        # Without an outputs/.layout marker (an analysis scaffolded before it existed) the resolver guesses from
        # the folder names: a step folder counts once it holds logs/ or a figures, source_data or tables folder.
        marker = self.tables / "outputs" / ".layout"
        if marker.exists():
            marker.unlink()
        self.table_only_reads_as_steps()


def find_tools():
    tools, missing = {}, []
    for name, (variable, default) in TOOLS.items():
        path = os.environ.get(variable) or (default if os.path.exists(default) else "")
        if not path:
            missing.append("{}: set {} (default {} does not exist)".format(name, variable, default))
        elif not os.path.isabs(path) or not os.access(path, os.X_OK):
            missing.append("{}: {}={} is not an absolute, executable path".format(name, variable, path))
        else:
            tools[name] = path
    return tools, missing


def main():
    if sys.version_info < (3, 9):
        print("FAILED at stage tools: run with python3.9 or later, not " + sys.version.split()[0])
        return 1
    tools, missing = find_tools()
    if missing:
        print("FAILED at stage tools: missing real tools (a missing tool is a failure, not a skip):")
        print("\n".join("  " + m for m in missing))
        return 1
    root = Path(tempfile.mkdtemp(prefix="mx-e2e-real-"))
    smoke = Smoke(tools, root)
    stages = [("setup", smoke.setup), ("scaffold", smoke.scaffold_main), ("where-not-run", smoke.where_not_run),
              ("run-1", smoke.run_1), ("where-current", smoke.where_current), ("panel", smoke.panel),
              ("edit-stale", smoke.edit_stale), ("run-2", smoke.run_2), ("change-log", smoke.change_log),
              ("dry-runs", smoke.dry_runs), ("flagged-run", smoke.flagged_run), ("failing-step", smoke.failing_step),
              ("where-failed", smoke.where_failed),
              ("plain-rerun-fails", smoke.plain_rerun_of_unrepaired), ("repair", smoke.repair), ("verify-runs", smoke.verify_runs),
              ("analysis-report", smoke.analysis_report), ("tables-only", smoke.tables_only),
              ("no-marker", smoke.no_marker)]
    print("e2e_real: tools " + ", ".join("{}={}".format(k, v) for k, v in sorted(tools.items())))
    print("e2e_real: working in " + str(root))
    for name, stage in stages:
        began = time.time()
        try:
            stage()
        except Fail as error:
            print("FAILED at stage {}: {}\n(folder kept: {})".format(name, error, root))
            return 1
        except BaseException as error:  # a crash or Ctrl-C still says which stage and keeps the folder
            print("FAILED at stage {}: {}: {}\n(folder kept: {})".format(name, type(error).__name__, error, root))
            return 130 if isinstance(error, KeyboardInterrupt) else 1
        print("ok   {:<16} {:5.1f}s".format(name, time.time() - began), flush=True)
    if os.environ.get("MX_E2E_KEEP") == "1":
        print("kept " + str(root))
    else:
        shutil.rmtree(str(root), ignore_errors=True)
    print("e2e_real: all {} stages passed".format(len(stages)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
