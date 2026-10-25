"""Regenerate docs/examples/track-changes-report.html: the real track-changes report on a synthetic analysis.

    python3 tests/e2e/make_track_changes_example.py

Approvals, re-pins and receipts come from the real gate hooks in a throwaway repository with invented
analysis names and no data, so nothing here comes from a real project. The report is whatever
skills/track-changes/scripts/track_changes.py wrote; this script only drives the session and copies the file.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
GATE = os.path.join(REPO, "hooks", "gate.py")
SCRIPT = os.path.join(REPO, "skills", "track-changes", "scripts", "track_changes.py")
OUT = os.path.join(REPO, "docs", "examples", "track-changes-report.html")
FIT = "analysis/pbmc-ifn/scripts/01_fit.py"
PLOT = "analysis/pbmc-ifn/scripts/02_plot.py"


def plan(choice, outputs, min_cells):
    rows = ["| 1 | run `{}` | {} | user | counts per donor, 12 donors |".format(FIT, choice),
            "| 2 | run `{}` | volcano of the contrast | default: standard figure | file written |".format(PLOT)]
    evidence = {"version": 1, "rows": [
        {"row": "1", "depends_on": [], "evidence": [
            {"claim": "the threshold this plan approved", "cmd": "rg -n '^min_cells' " + FIT,
             "out": "1:min_cells = {}".format(min_cells)}]},
        {"row": "2", "depends_on": ["1"], "evidence": [
            {"claim": "the plotting entry point", "cmd": "head -n 1 " + PLOT, "out": "print('volcano')"}]}]}
    return "\n".join(["> Question (user's words): \"Does the interferon response differ between arms?\"", "",
                      "**Objective.** Compare the interferon response between arms.", "", "Outputs: " + outputs, "",
                      "| # | Step | Choice | Source | Validation |", "|---|---|---|---|---|"] + rows
                     + ["", "Plan status: READY", "",
                        "<!-- plan-evidence " + json.dumps(evidence) + " -->"])


class Session:
    def __init__(self, root):
        self.root, self.calls = root, 0

    def write(self, rel, text, age=0):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write(text)
        stamp = time.time() - age
        os.utime(path, (stamp, stamp))

    def hook(self, event, payload):
        payload = dict(payload, session_id="s1", cwd=self.root)
        proc = subprocess.run([sys.executable, GATE, event], input=json.dumps(payload).encode(), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=dict(os.environ, CLAUDE_CODE_SESSION_ID="s1"))
        if proc.returncode:
            sys.exit(proc.stderr.decode())
        return json.loads(proc.stdout.decode()) if proc.stdout.strip() else None

    def approve(self, text):
        notice = self.hook("stop", {"last_assistant_message": text})["systemMessage"]
        digest = notice.split("approve plan ")[1][:8]
        self.hook("prompt", {"prompt": "approve plan " + digest})
        return digest

    def run(self, command, code=0):
        self.calls += 1
        call = "toolu_{}".format(self.calls)
        reply = self.hook("tool", {"tool_name": "Bash", "tool_input": {"command": command}, "tool_use_id": call})
        if ((reply or {}).get("hookSpecificOutput") or {}).get("permissionDecision") == "deny":
            sys.exit("the gate denied " + command)
        self.hook("post", {"tool_name": "Bash", "tool_input": {"command": command}, "tool_use_id": call,
                           "tool_response": {"stdout": "", "exit_code": code}})


def main():
    root = tempfile.mkdtemp()
    try:
        os.environ["HOME"] = root
        session = Session(root)
        os.makedirs(os.path.join(root, ".mycelium-extra"))
        session.write(".mycelium-extra/gate.json", "{}")
        session.write(FIT, "min_cells = 500\n", age=7200)
        session.write(PLOT, "print('volcano')\n", age=7200)
        session.write("analysis/pbmc-ifn/PBMC_IFN.md", "Objective: Characterize the interferon response.\n")
        first = session.approve(plan("minimum 500 cells per donor", "analysis/pbmc-ifn/outputs/", 500))
        session.run("python " + FIT, code=1)  # a failed run stays visible, with its retry
        session.run("python " + FIT)
        session.write(FIT, "min_cells = 200\n", age=1800)  # edited after the approval
        session.approve(plan("minimum 200 cells per donor", "analysis/pbmc-ifn/outputs_v2/", 200))
        session.run("python " + FIT)
        with open(SCRIPT) as source:
            proc = subprocess.run([sys.executable, "-", "--plugin-root", REPO, "--repo", root, "--analysis",
                                   "analysis/pbmc-ifn", "--original", first], stdin=source, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, cwd=root, universal_newlines=True,
                                  env=dict(os.environ, CLAUDE_CODE_SESSION_ID="s1"))
        if proc.returncode:
            sys.exit(proc.stderr)
        report = os.path.join(root, ".mycelium-extra", "track-changes", "analysis__pbmc-ifn", "report.html")
        with open(report, encoding="utf-8") as handle:
            html = handle.read()
        if "http://" in html or "https://" in html:
            sys.exit("the report is not offline: it names an external URL")
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        shutil.copyfile(report, OUT)
        print(proc.stdout)
        print("wrote", OUT, "({} bytes)".format(len(html)))
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
