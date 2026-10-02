"""Differential check of the gate: an old gate.py against the working tree, byte for byte.

Run before changing hooks/gate.py; every case must be identical unless the change is meant
to alter that decision:

    python3 hooks/tests/gate_diff.py [--base REF] [--new PATH] [--fuzz N] [--seed S]

Each case builds the same throwaway repository twice, sends the same hook event to the old
gate (`git show REF:hooks/gate.py`, default HEAD) and the new one (default hooks/gate.py),
and compares exit status, stdout, stderr, and every file the gate leaves in its state
folder. Timestamps and the temp root are normalized. Run it under each interpreter
(python3.6, 3.11, 3.12) by changing the python that runs this file.
"""

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
FIXED = 1700000000
VOLATILE = [(re.compile(r'"(ts|approved_at|granted_at)": -?[0-9.e+]+'), r'"\1": 0'),
            (re.compile(r'"mtime": [0-9-]+'), '"mtime": 0')]
GIT_ENV = dict(os.environ, GIT_AUTHOR_DATE="1700000000 +0000", GIT_COMMITTER_DATE="1700000000 +0000",
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
PLAN = "## Plan\n| 1 | run `analysis/x.py` | repo | check |\n\nPlan status: READY"
BIGPLAN = "## Plan\n| # | step | source | check |\n" + "".join(
    "| %d | run `analysis/dir%d/mod%d.py` | repo: `repo:` x | ok |\n" % (i, i % 7, i)
    for i in range(120)) + "\nPlan status: READY"
BASE_FILES = {"analysis/x.py": "print(1)\n", "nbs/n.ipynb": "{}\n", "renv.lock": "{}\n",
              "job.sh": "#!/bin/bash\n#SBATCH -p cpu\nmodule load R/4.3\npython analysis/x.py\n",
              "main.nf": "workflow {}\n", "params.yaml": "a: 1\n", "config/c.yaml": "a: 1\n",
              "workflow/Snakefile": "rule all: input: []\n"}


def case(name, kind, payload, files=None, approvals=(), git=None, explore=(), seen=None,
         symlinks=False, outside=False, session="s1"):
    """One hook event plus the repository it runs in, all as plain data."""
    return dict(name=name, kind=kind, payload=payload, files=dict(BASE_FILES, **(files or {})),
                approvals=list(approvals), git=git, explore=list(explore), seen=seen,
                symlinks=symlinks, outside=outside, session=session)


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(text)
    os.utime(path, (FIXED, FIXED))


def build(root, c):
    state = os.path.join(root, ".mycelium-extra")
    write(root, ".mycelium-extra/gate.json", "{}")
    for rel, text in sorted(c["files"].items()):
        write(root, rel, text)
    for i, (age, plan) in enumerate(c["approvals"]):
        digest = "%08x" % (i + 1)
        write(root, ".mycelium-extra/approvals/%s.json" % digest,
              json.dumps({"hash": digest, "approved_at": time.time() - age, "plan": plan}))
    if c["explore"]:
        write(root, ".mycelium-extra/explore.log", "".join(
            json.dumps({"ts": 1.0, "session_id": sid, "command": cmd, "paths": []}, sort_keys=True) + "\n"
            for sid, cmd in c["explore"]))
    if c["seen"] is not None:
        write(root, ".mycelium-extra/pending/s1.explore-seen", str(c["seen"]))
    if c["symlinks"]:
        os.symlink(os.path.join(root, "analysis"), os.path.join(root, "link"))
        os.symlink("/nonexistent/dead", os.path.join(root, "dead"))
    if c["git"]:
        write(root, ".gitignore", ".mycelium-extra/\nlogs/\n*.dat\n")
        for args in (("init", "-q"), ("add", ".gitignore", "analysis/x.py", "renv.lock", "job.sh"),
                     ("commit", "-qm", "init")):
            subprocess.run(("git", "-C", root) + args, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, env=GIT_ENV)
        if c["git"] == "dirty":
            write(root, "analysis/x.py", "print(2222)\n")
            write(root, "analysis/new.py", "print(3)\n")
            write(root, "logs/out.log", "log\n")
            write(root, "ignored.dat", "x\n")
    return state


def run(gate, c):
    root = tempfile.mkdtemp(prefix="gate-diff-")
    elsewhere = tempfile.mkdtemp(prefix="gate-diff-out-")
    try:
        state = build(root, c)
        write(elsewhere, "analysis/y.py", "print(9)\n")
        event = dict(c["payload"], session_id=c["session"], cwd=elsewhere if c["outside"] else root)
        proc = subprocess.Popen([sys.executable, gate, c["kind"]], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        out, err = proc.communicate(json.dumps(event).encode("utf-8"))
        files = []
        for folder, dirs, names in os.walk(state):
            dirs.sort()
            for name in sorted(names):
                full = os.path.join(folder, name)
                with open(full, errors="replace") as handle:
                    files.append((os.path.relpath(full, root), handle.read()))

        def norm(text):
            text = text.replace(root, "<ROOT>").replace(elsewhere, "<OUT>")
            for pattern, repl in VOLATILE:
                text = pattern.sub(repl, text)
            return text
        return {"rc": proc.returncode, "out": norm(out.decode("utf-8", "replace")),
                "err": norm(err.decode("utf-8", "replace")),
                "state": [(rel, norm(text)) for rel, text in files]}
    finally:
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(elsewhere, ignore_errors=True)


def bash(command, response=None):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    if response is not None:
        payload["tool_response"] = response
    return payload


def plan_with(cells):
    return PLAN.replace("repo |", "repo | {} |".format(cells))


def scenarios():
    approved = [(0, PLAN)]
    return [
        case("tool gated runs, no plan", "tool", bash("python analysis/x.py; sbatch job.sh; snakemake -j 1")),
        case("tool covered run", "tool", bash("python analysis/x.py"), approvals=approved),
        case("tool ungated read", "tool", bash("cat analysis/x.py | rg print")),
        case("tool explore without grant", "tool", bash("MYCELIUM_EXTRA_EXPLORE=1 python analysis/x.py")),
        case("tool 40 approvals one command", "tool",
             bash("sbatch a.sbatch; sbatch b.sbatch; snakemake -s c.smk; python analysis/x.py"),
             approvals=[(i * 60, plan_with("sbatch | snakemake | analysis/x.py")) for i in range(40)]),
        case("tool big plan many approvals", "tool", bash("sbatch job.sh; python analysis/dir3/mod9.py"),
             approvals=[(i * 60, BIGPLAN) for i in range(12)]),
        case("tool symlinked repo", "tool", bash("python link/x.py; rm dead"), symlinks=True),
        case("tool write into state", "tool",
             bash("rm -rf .mycelium-extra/approvals; echo x > .mycelium-extra/pending/p.json"), approvals=approved),
        case("tool Write into state", "tool",
             {"tool_name": "Write", "tool_input": {"file_path": ".mycelium-extra/approvals/x.json"}}),
        case("tool cwd outside repo", "tool", bash("python analysis/y.py"), outside=True),
        case("post sbatch then python", "post",
             bash("sbatch -o logs/%j.out job.sh; python analysis/x.py",
                  {"stdout": "Submitted batch job 4242\n", "stderr": "", "interrupted": False}),
             approvals=[(0, plan_with("sbatch job.sh | analysis/x.py"))]),
        case("post four runners one call", "post",
             bash("python analysis/x.py; nextflow run main.nf -params-file params.yaml -resume -with-trace; "
                  "sbatch job.sh; snakemake --configfile config/c.yaml -j 4",
                  {"stdout": "N E X T F L O W ~ version 24\nLaunching `main.nf` [sick_bell] DSL2 - revision: x\n"
                             "Submitted batch job 9\n", "exit_code": 0}),
             approvals=[(0, plan_with("sbatch | nextflow | snakemake"))]),
        case("post big output", "post",
             bash("python analysis/x.py", {"stdout": "Submitted batch job 111\n" * 20000,
                                           "nested": {"a": [{"b": "x"}] * 50}}), approvals=approved),
        case("post parsable str response", "post", bash("sbatch --parsable job.sh", "4243;cluster1\n"),
             approvals=[(0, plan_with("sbatch"))]),
        case("post no tool_response", "post", bash("sbatch job.sh"), approvals=[(0, plan_with("sbatch"))]),
        case("post exotic response", "post",
             bash("sbatch job.sh; python analysis/x.py",
                  {"stdout": 42, "nested": {"deep": None, "num": 1.5, "t": True},
                   "lst": [None, 7, "Submitted batch job 31337"]}),
             approvals=[(0, plan_with("sbatch | analysis/x.py"))]),
        case("post sbatch --wrap", "post", bash("sbatch --wrap='python analysis/x.py'", "Submitted batch job 5\n"),
             approvals=[(0, plan_with("sbatch"))]),
        case("post clean git", "post", bash("python analysis/x.py", {"stdout": "1"}), approvals=approved, git="clean"),
        case("post dirty git", "post", bash("python analysis/x.py; python analysis/new.py", {"stdout": "2"}),
             approvals=[(0, PLAN.replace("analysis/x.py", "analysis/x.py analysis/new.py"))], git="dirty"),
        case("stop big plan", "stop", {"last_assistant_message": BIGPLAN}),
        case("stop plan without table", "stop",
             {"last_assistant_message": "## Plan\njust prose analysis/x.py\n\nPlan status: READY"}),
        case("stop plan with inputs", "stop",
             {"last_assistant_message": PLAN.replace("\n\nPlan", "\nInputs: renv.lock, config/\n\nPlan")}),
        case("stop explore log", "stop", {"last_assistant_message": ""},
             explore=[("s1", "python a.py"), ("s2", "python b.py"), ("s1", "sbatch c.sh"), ('s"x', "q")]),
        case("stop explore already seen", "stop", {"last_assistant_message": ""},
             explore=[("s1", "python a.py")], seen=1),
        case("prompt allow explore", "prompt", {"prompt": "allow explore"}),
        case("prompt approve unknown", "prompt", {"prompt": "approve plan deadbeef"}),
        case("prompt bare approve", "prompt", {"prompt": "approve plan"}),
        case("prompt long approve-ish", "prompt", {"prompt": "please approve plan deadbeef now " + "x" * 300}),
    ]


TOKENS = ["analysis/x.py", "nbs/n.ipynb", "job.sh", "main.nf", "workflow/Snakefile", "renv.lock",
          "config/c.yaml", "-o", "logs/%j.out", "--parsable", "--wrap=python analysis/x.py",
          "--configfile", "-params-file", "params.yaml", "--resume", "-j", "4", "-c",
          "import sys; open('analysis/x.py','w')", "$HOME", "/etc/passwd", "../outside.py", "a b.py",
          "x.dat", "-", "|", "&&", ";", "sub/../analysis/x.py", "~", "python analysis/x.py"]
LEADS = ["cd analysis", "cd /tmp", "export FOO=1", "MYCELIUM_EXTRA_EXPLORE=1", "sudo", "echo x >",
         ".mycelium-extra/receipts.jsonl", "rm -rf .mycelium-extra", "eval 'python a.py'", "command -v"]
HEADS = ["sbatch", "snakemake", "nextflow", "python", "python3.11", "Rscript", "bash", "jupyter",
         "papermill", "quarto", "ls", "cat"]
WRAPS = ["env", "conda run -n scanpy", "nice", "timeout 5", "srun", "uv run"]


def fuzz_cases(count, seed):
    rng = random.Random(seed)

    def plan():
        rows = ["| # | step | Source | check |", "| --- | --- | --- | --- |"] + [
            "| %d | %s | repo: `repo:` x | ok |" % (rng.randint(1, 9), rng.choice(TOKENS + HEADS[:3]))
            for _ in range(rng.randint(1, 5))]
        extra = "\nInputs: analysis/x.py, renv.lock\n" if rng.random() < 0.3 else ""
        return "## Plan\n" + "\n".join(rows) + extra + rng.choice(
            ["\nPlan status: READY", "\nPlan status: DECISION_REQUIRED", "\n\nno status here"])

    def command():
        parts = []
        for _ in range(rng.randint(1, 3)):
            words = [rng.choice(LEADS)] if rng.random() < 0.3 else []
            words += [rng.choice(WRAPS)] if rng.random() < 0.25 else []
            words += [rng.choice(HEADS)] + [rng.choice(TOKENS) for _ in range(rng.randint(0, 4))]
            parts.append(" ".join(words))
        return rng.choice(["; ", " && ", " | ", "\n"]).join(parts)

    def response():
        text = "".join(rng.choice(["Submitted batch job %d\n" % rng.randint(1, 99999), "7;cluster1\n",
                                   "Launching `main.nf` [warm_dog] DSL2\n", "", "noise\n"])
                       for _ in range(rng.randint(0, 3)))
        return rng.choice([text, {"stdout": text, "stderr": "", "exit_code": rng.choice([0, 1, None])}])

    cases = []
    for i in range(count):
        kind = rng.choice(["tool", "tool", "post", "post", "stop", "prompt"])
        payload = (bash(command(), response()) if kind in ("tool", "post")
                   else {"last_assistant_message": plan()} if kind == "stop"
                   else {"prompt": rng.choice(["approve plan 00000001", "allow explore", "stop explore",
                                               "hello", "approve plan"])})
        explore = [(rng.choice(["s1", "s2", "sess-é", 's"x']), "python a.py")
                   for _ in range(rng.randint(1, 4))] if rng.random() < 0.4 else []
        cases.append(case("fuzz #%d" % i, kind, payload,
                          approvals=[(rng.randint(0, 3600), plan()) for _ in range(rng.choice([0, 1, 3, 8]))],
                          git=rng.choice([None, "dirty"]), explore=explore,
                          seen=rng.randint(0, 3) if rng.random() < 0.3 else None,
                          outside=rng.random() < 0.2, session=rng.choice(["s1", "s2"])))
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--base", default="HEAD", help="git ref of the old gate.py (default HEAD)")
    parser.add_argument("--new", default=os.path.join(REPO, "hooks", "gate.py"), help="the new gate entry point")
    parser.add_argument("--fuzz", type=int, default=120, help="random cases after the fixed ones (default 120)")
    parser.add_argument("--seed", type=int, default=1234)
    args = parser.parse_args()
    folder = tempfile.mkdtemp(prefix="gate-diff-base-")
    try:
        old = os.path.join(folder, "gate.py")
        with open(old, "wb") as handle:
            handle.write(subprocess.check_output(["git", "-C", REPO, "show", args.base + ":hooks/gate.py"]))
        cases = scenarios() + fuzz_cases(args.fuzz, args.seed)
        fails = 0
        for c in cases:
            a, b = run(old, c), run(os.path.abspath(args.new), c)
            diffs = [field for field in ("rc", "out", "err", "state") if a[field] != b[field]]
            if diffs:
                fails += 1
                print("FAIL  {} ({})".format(c["name"], ", ".join(diffs)))
                if c["kind"] in ("tool", "post"):
                    print("   command: {!r}".format(c["payload"]["tool_input"]["command"]))
                for field in diffs:
                    print("   {} old: {!r}\n   {} new: {!r}".format(field, a[field], field, b[field])[:2000])
        print("{} {}: {}/{} identical (base {}, new {})".format(
            os.path.basename(sys.executable), sys.version.split()[0], len(cases) - fails, len(cases),
            args.base, os.path.relpath(os.path.abspath(args.new), REPO)))
        return 1 if fails else 0
    finally:
        shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
