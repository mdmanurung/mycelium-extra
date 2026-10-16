"""Real local qualification. Missing tools and failed assertions are failures, never skips.

Run with the pinned validation Python; pass --rscript, --nextflow, --java and --evidence.
All computations use synthetic data in a disposable directory; no scheduler or model calls.
"""

import argparse
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
import time

REPO = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("rscript", "nextflow", "java", "evidence"):
        parser.add_argument("--" + option, required=True)
    args = parser.parse_args()
    evidence = Path(args.evidence).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix="attempt-", dir=str(evidence)))
    records = []
    with tempfile.TemporaryDirectory(prefix="mx-real-workflows-") as temporary:
        root = Path(temporary)
        env = dict(os.environ, PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"],
                   XDG_CACHE_HOME=str(root / "cache"), JUPYTER_DATA_DIR=str(root / "jupyter"),
                   JUPYTER_RUNTIME_DIR=str(root / "jupyter-runtime"), IPYTHONDIR=str(root / "ipython"),
                   JAVA_CMD=args.java, NXF_HOME="/tmp/mx-remediation-nextflow", NXF_OFFLINE="true",
                   NXF_DISABLE_CHECK_LATEST="true", PYTHONDONTWRITEBYTECODE="1", CORES="1")
        def run(name, command, cwd=root, ok=True, timeout=90):
            result = subprocess.run(command, cwd=str(cwd), env=env, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, timeout=timeout)
            (evidence / (name + ".log")).write_bytes(result.stdout)
            if (cwd / "logs").is_dir():
                shutil.copytree(str(cwd / "logs"), str(evidence / (name + "-files")))
            records.append({"case": name, "command": [str(x) for x in command], "exit": result.returncode,
                            "expected_success": ok, "log": name + ".log"})
            (evidence / "results.json").write_text(json.dumps(records, indent=2) + "\n")
            assert (result.returncode == 0) == ok, name + ": " + result.stdout.decode(errors="replace")[-2500:]
            return result.stdout

        run("versions-python", [sys.executable, "-V"])
        run("versions-snakemake", ["snakemake", "--version"])
        run("versions-r", [args.rscript, "--version"])
        run("versions-nextflow", [args.nextflow, "-version"])
        run("kernel", [sys.executable, "-m", "ipykernel", "install", "--user", "--name", "python3"])
        run("git-init", ["git", "init", "-q"])
        (root / "data").mkdir()
        source = root / "data" / "counts.tsv"
        source.write_text("sample\tcount\nA\t2\nB\t3\n")
        def scaffold(name, steps):
            run("scaffold-" + name, [sys.executable, str(REPO / "skills/new-analysis/scripts/new_analysis.py"),
                                    "--dest=" + str(root / "analysis" / name), "--steps=" + steps,
                                    "--data=" + str(source)])
            return root / "analysis" / name

        python = scaffold("python", "01_count.py")
        snake = ["bash", "run.sh"]
        run("stub-fails", snake, python, ok=False)
        script = python / "01_count.py"
        script.write_text("import sys, csv\nimport pyarrow as pa\nimport pyarrow.parquet as pq\n"
                          "with open('data/counts.tsv') as h: rows=list(csv.DictReader(h,delimiter='\\t'))\n"
                          "pq.write_table(pa.table({'total':[sum(int(r['count']) for r in rows)]}),sys.argv[1])\n")
        run("python-success", snake, python)
        import pyarrow.parquet as pq
        output = python / "outputs/01_count.parquet"
        assert pq.read_table(str(output)).to_pydict() == {"total": [5]}
        before = output.stat().st_mtime_ns
        run("python-no-stale-rebuild", snake, python)
        assert output.stat().st_mtime_ns == before
        time.sleep(1.1)
        source.write_text("sample\tcount\nA\t2\nB\t4\n")
        run("python-changed-input", snake, python)
        assert pq.read_table(str(output)).to_pydict() == {"total": [6]}
        output.write_bytes(b"stale invalid output")
        run("python-force-stale-output", snake + ["--forceall"], python)
        assert pq.read_table(str(output)).to_pydict() == {"total": [6]}

        original = script.read_text()
        script.write_text("from pathlib import Path\nimport time\nPath('started').write_text('started')\ntime.sleep(30)\n" + original)
        proc = subprocess.Popen(snake + ["--forceall"], cwd=str(python), env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.monotonic() + 30
        while not (python / "started").exists() and proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.1)
        assert (python / "started").exists(), "interruption fixture never started"
        os.killpg(proc.pid, signal.SIGINT)
        log, unused = proc.communicate(timeout=20)
        (evidence / "python-interrupted.log").write_bytes(log)
        assert proc.returncode != 0
        script.write_text(original)
        run("python-resumed", snake + ["--rerun-incomplete"], python)
        assert pq.read_table(str(output)).to_pydict() == {"total": [6]}

        r = scaffold("r", "01_count.R")
        (r / "01_count.R").write_text("args <- commandArgs(TRUE)\nx <- read.delim('data/counts.tsv')\n"
                                      "saveRDS(sum(x$count), args[[1]])\n")
        run("r-success", snake + ["--config", "rscript=" + args.rscript], r)
        run("r-output-assert", [args.rscript, "-e", "stopifnot(readRDS('outputs/01_count.rds') == 6)"], r)

        notebook = scaffold("notebook", "01_inspect.ipynb")
        path = notebook / "01_inspect.ipynb"
        book = json.loads(path.read_text())
        book["cells"][-1]["source"] = ["assert INPUT.read_text().count('\\n') == 3\n", "print('two samples')\n"]
        path.write_text(json.dumps(book))
        run("notebook-success", snake, notebook)
        executed = json.loads((notebook / "logs/01_inspect.ipynb").read_text())
        assert all(c.get("execution_count") for c in executed["cells"] if c["cell_type"] == "code")
        book["cells"][-1]["source"] = ["raise RuntimeError('planted notebook failure')"]
        path.write_text(json.dumps(book))
        run("notebook-failure", snake, notebook, ok=False)

        nf = root / "nextflow"
        nf.mkdir()
        (nf / "main.nf").write_text("params.fail = false\nprocess tiny {\n output:\n path 'value.txt'\n"
                                    " script:\n params.fail ? 'exit 7' : 'echo 6 > value.txt'\n}\nworkflow { tiny() }\n")
        run("nextflow-success", [args.nextflow, "run", "main.nf", "-with-trace", "success.tsv"], nf)
        run("nextflow-failure", [args.nextflow, "run", "main.nf", "--fail", "true", "-resume", "-with-trace", "failure.tsv"], nf, ok=False)
        run("nextflow-resume", [args.nextflow, "run", "main.nf", "-resume", "-with-trace", "resume.tsv"], nf)
        assert "CACHED" in (nf / "resume.tsv").read_text()

        run("h5ad-contracts", [sys.executable, str(REPO / "skills/data-contract-check/tests/test_data_contract_check.py")])
        assert b"skipped=" not in (evidence / "h5ad-contracts.log").read_bytes()
        # Real-tool opt-in belongs only to the linter subprocesses.
        env.update(MX_E2E_REAL_TOOLS="1", MX_E2E_SCILINTR=str(Path(sys.executable).parent / "scilintr"),
                   MX_E2E_RSCRIPT=args.rscript)
        run("real-linters", [sys.executable, str(REPO / "hooks/tests/test_gate.py"),
                             "GateTest.test_write_lint_with_real_scilintr", "LauncherTest.test_write_lint_with_real_scilintr"])
        assert b"skipped=" not in (evidence / "real-linters.log").read_bytes()
    print("Real local integrations passed; evidence:", evidence)


if __name__ == "__main__":
    main()
