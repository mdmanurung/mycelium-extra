"""Run: python3 skills/verify/tests/test_verify.py

Approvals and receipts are made by the real gate hooks, so the tests follow the
receipt format the gate actually writes.
"""

import base64
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "verify.py")
PLUGIN = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
GATE = os.path.join(PLUGIN, "hooks", "gate.py")
sys.path.insert(0, os.path.join(PLUGIN, "hooks"))
sys.dont_write_bytecode = True
import gate  # noqa: E402

FIT = "analysis/a/scripts/01_fit.py"


def plan(*rows, outputs="analysis/a/outputs/", inputs=None):
    lines = ["**Objective.** Fit the model; see `analysis/a/scripts/old.py` for the previous attempt.", ""]
    if inputs:
        lines.append("Inputs: " + inputs)
    if outputs is not None:
        lines.append("Outputs: " + outputs)
    lines += ["", "| # | Step | Choice | Source | Validation |", "|---|---|---|---|---|"]
    lines += ["| {} | {} | x | user | ok |".format(i + 1, row) for i, row in enumerate(rows)]
    return "\n".join(lines + ["", "Plan status: READY"])


class VerifyTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, ".mycelium-extra"))
        self.write(".mycelium-extra/gate.json", "{}")
        self.write(FIT, "print(1)\n", mtime=time.time() - 3600)  # scripts predate their plan
        self.sacct = self.fake_sacct("")

    def tearDown(self):
        shutil.rmtree(self.root)

    def write(self, rel, text, mtime=None):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write(text)
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def fake_sacct(self, line):
        path = self.write("bin/sacct", "#!/bin/sh\necho '{}'\n".format(line))
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    def hook(self, event, payload):
        payload = dict(payload, session_id="s1", cwd=self.root)
        proc = subprocess.Popen([sys.executable, GATE, event], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate(json.dumps(payload).encode("utf-8"))
        self.assertEqual(proc.returncode, 0, err)
        return json.loads(out.decode("utf-8")) if out.strip() else None

    def approve(self, text):
        notice = self.hook("stop", {"last_assistant_message": text})["systemMessage"]
        digest = notice.split("approve plan ")[1][:8]
        self.hook("prompt", {"prompt": "approve plan " + digest})
        return digest

    def run_cmd(self, command, exit_code=0, stdout=""):
        self.hook("post", {"tool_name": "Bash", "tool_input": {"command": command},
                           "tool_response": {"stdout": stdout, "exit_code": exit_code}})
        receipts = gate.state_path(self.root, "receipts.jsonl")
        with open(receipts) as handle:
            return json.loads(handle.readlines()[-1])

    def verify(self, *args, **kwargs):
        with open(SCRIPT) as source:
            proc = subprocess.Popen([sys.executable, "-", "--plugin-root", PLUGIN, "--repo", self.root,
                                     "--sacct", kwargs.get("sacct", self.sacct)] + list(args),
                                    stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    cwd=self.root)
            out, err = proc.communicate()
        if kwargs.get("fails"):
            self.assertNotEqual(proc.returncode, 0)
            return err.decode("utf-8")
        self.assertEqual(proc.returncode, 0, err.decode("utf-8"))
        return out.decode("utf-8")

    def test_conforming_run(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        receipt = self.run_cmd("python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        out = self.verify("report", digest)
        self.assertIn("| `{}` | ran |".format(FIT), out)
        self.assertIn("`python {}`".format(FIT), out)
        self.assertIn("analysis folder `analysis/a`", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)

    def test_output_never_repeats_the_plan_status_line(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.run_cmd("python " + FIT)
        for args in (("report", digest), ("report", digest, "--json"), ("list",),
                     ("write", digest, "--analysis-dir", "analysis/a")):
            self.assertIsNone(gate.PLAN_STATUS.search(self.verify(*args)), args)
        with open(os.path.join(self.root, "analysis/a/provenance/plan-{}.md".format(digest))) as handle:
            self.assertIn("Plan status: READY", handle.read())

    def test_explore_run_of_a_planned_script_does_not_count(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.hook("prompt", {"prompt": "allow explore"})
        receipt = self.run_cmd("MYCELIUM_EXTRA_EXPLORE=1 python " + FIT)
        self.assertEqual(receipt["plans"], [digest])  # the gate still names the covering plan
        out = self.verify("report", digest)
        self.assertIn("| `{}` | no receipt |".format(FIT), out)
        self.assertIn("Explore run in the analysis folder", out)
        self.assertIn("(explore, not reportable)", out)
        self.assertIn("0 run(s) under this plan", out)
        self.assertIn("not a git repository", out)

    def test_failed_run_and_edited_script_block(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.run_cmd("python " + FIT, exit_code=1)
        out = self.verify("report", digest)
        self.assertIn("failed (exit 1)", out)
        self.assertIn("Verify status: DOES_NOT_CONFORM", out)
        self.run_cmd("python " + FIT)
        self.write(FIT, "print(2)\n")
        out = self.verify("report", digest)
        self.assertIn("was edited after its run", out)
        self.assertIn("Verify status: DOES_NOT_CONFORM", out)

    def test_outputs_older_than_approval_or_untied(self):
        self.write("analysis/a/outputs/old.tsv", "x\n", mtime=time.time() - 3600)
        digest = self.approve(plan("run `{}`".format(FIT),
                                   outputs="analysis/a/outputs/old.tsv, analysis/a/outputs/"))
        receipt = self.run_cmd("python " + FIT)
        self.write("analysis/a/outputs/late.tsv", "x\n", mtime=receipt["ts"] + 600)
        out = self.verify("report", digest)
        self.assertIn("**block**: Output `analysis/a/outputs/old.tsv` was written", out)
        self.assertIn("Output `analysis/a/outputs/late.tsv` (written", out)
        self.assertIn("not tied to any recorded run", out)

    def test_earlier_runs_files_in_an_output_folder_are_not_blocking(self):
        self.write("analysis/a/results/run_0930/old.tsv", "x\n", mtime=time.time() - 3600)
        digest = self.approve(plan("run `{}`".format(FIT), outputs="analysis/a/results/run_*/"))
        receipt = self.run_cmd("python " + FIT)
        self.write("analysis/a/results/run_1001/new.tsv", "x\n", mtime=receipt["ts"] - 1)
        out = self.verify("report", digest)
        self.assertIn("1 file(s) under `analysis/a/results/run_*/` predate this plan", out)
        self.assertNotIn("run_0930/old.tsv`", out)
        self.assertIn("| `analysis/a/results/run_1001/new.tsv` |", out)
        self.assertIn("Verify status: CONFORMS", out)

    def test_reapproving_the_same_plan_keeps_its_earlier_runs(self):
        text = plan("run `{}`".format(FIT))
        digest = self.approve(text)
        receipt = self.run_cmd("python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        path = gate.state_path(self.root, "approvals", digest + ".json")
        record = gate.read_json(path, None)
        record["approved_at"] = receipt["ts"] + 86400  # approved again a day later
        with open(path, "w") as handle:
            json.dump(record, handle)
        out = self.verify("report", digest)
        self.assertIn("| `{}` | ran |".format(FIT), out)
        self.assertIn("re-approved; first run", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)

    def test_plan_without_outputs_line_is_a_gap(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs=None))
        self.run_cmd("python " + FIT)
        out = self.verify("report", digest)
        self.assertIn("no `Outputs:` line", out)
        self.assertIn("Verify status: CONFORMS_WITH_GAPS", out)

    def test_changed_pinned_input_blocks(self):
        self.write("data/samples.tsv", "a\n")
        digest = self.approve(plan("run `{}`".format(FIT), inputs="data/samples.tsv"))
        self.run_cmd("python " + FIT)
        self.write("data/samples.tsv", "a\nb\n")
        out = self.verify("report", digest)
        self.assertIn("Input `data/samples.tsv` changed since the approval", out)
        self.assertIn("(changed)", out)

    def test_script_outside_the_table_that_ran(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.write("analysis/a/scripts/02_extra.py", "print(3)\n")
        self.write("analysis/a/scripts/old.py", "print(0)\n")
        self.run_cmd("python " + FIT)
        other = self.approve(plan("run `analysis/a/scripts/02_extra.py`"))
        self.run_cmd("python analysis/a/scripts/02_extra.py")
        out = self.verify("report", digest)
        self.assertIn("`analysis/a/scripts/02_extra.py` ran since the approval but is not in the plan", out)
        self.assertIn("(under plan {})".format(other), out)
        self.assertIn("1 other script(s) in the analysis folder", out)  # old.py, cited only in prose

    def snakemake_record(self, output, rule, start, inputs, shellcmd):
        name = base64.urlsafe_b64encode(output.encode("utf-8")).decode("ascii")
        self.write("analysis/a/.snakemake/metadata/" + name, json.dumps({
            "rule": rule, "starttime": start, "endtime": start + 1, "incomplete": False,
            "input": inputs, "shellcmd": shellcmd, "code": None}))

    def test_steps_inside_a_snakemake_wrapper(self):
        # The rule shapes new-analysis generates: the step file is the `script=` or `notebook=` input,
        # and later steps take the previous step's output as `prev=`.
        step, notebook = "analysis/a/01_step.R", "analysis/a/02_plot.ipynb"
        for path in (step, notebook, "analysis/a/run.sh"):
            self.write(path, "x\n", mtime=time.time() - 60)
        digest = self.approve(plan("`analysis/a/run.sh`", "`{}`".format(step), "`{}`".format(notebook)))
        start = time.time()
        self.write("analysis/a/outputs/01_table.tsv", "x\n", mtime=start + 1)
        self.write("analysis/a/outputs/02_plot.pdf", "x\n", mtime=start + 1)
        self.snakemake_record("outputs/01_table.tsv", "s01_step", start, ["01_step.R", "data/in.tsv"],
                              "Rscript 01_step.R data/in.tsv outputs/01_table.tsv > logs/01_step.log 2>&1")
        self.snakemake_record("outputs/02_plot.pdf", "s02_plot", start, ["02_plot.ipynb", "outputs/01_table.tsv"],
                              "jupyter nbconvert --to notebook --execute 02_plot.ipynb --output-dir logs "
                              "--output 02_plot.ipynb")
        self.run_cmd("bash analysis/a/run.sh")
        out = self.verify("report", digest)
        self.assertIn("| `{}` | ran in Snakemake rule `s01_step` |".format(step), out)
        self.assertIn("| `{}` | ran in Snakemake rule `s02_plot` |".format(notebook), out)
        self.assertIn("wrapper: 2 Snakemake job(s) ran inside", out)
        self.assertIn("via Snakemake rule `s01_step`", out)
        self.assertIn("via Snakemake rule `s02_plot`", out)
        self.assertIn("Verify status: CONFORMS", out)

    def test_sbatch_state_comes_from_sacct(self):
        self.write("analysis/a/job.sh", "#!/bin/bash\n#SBATCH -t 1:00:00\npython analysis/a/scripts/01_fit.py\n")
        digest = self.approve(plan("`sbatch analysis/a/job.sh`"))
        self.run_cmd("sbatch analysis/a/job.sh", stdout="Submitted batch job 4242")
        done = self.fake_sacct("4242|COMPLETED|0:0|2026-09-30T10:00:00|2026-09-30T10:05:00")
        self.assertIn("job 4242 COMPLETED", self.verify("report", digest, sacct=done))
        failed = self.fake_sacct("4242|FAILED|1:0|2026-09-30T10:00:00|2026-09-30T10:05:00")
        out = self.verify("report", digest, sacct=failed)
        self.assertIn("Slurm job 4242 ended FAILED", out)
        self.assertIn("Verify status: DOES_NOT_CONFORM", out)
        missing = self.verify("report", digest, sacct=os.path.join(self.root, "no-sacct"))
        self.assertIn("state unknown (no sacct)", missing)

    def test_lineage_shows_computation_the_gate_did_not_see(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.run_cmd("python " + FIT)
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.write(".living/log/data-lineage/2026-10-01-001.json", json.dumps({
            "session_id": "2026-10-01-001",
            "actions": [{"ts": stamp, "script": "/tmp/scratchpad/smoke.R"},
                        {"ts": stamp, "script": os.path.join(self.root, FIT)},
                        {"ts": stamp, "script": None, "bash_cmd": "python3 -c 'print(1)'"}]}))
        out = self.verify("report", digest)
        self.assertIn("lineage saw `/tmp/scratchpad/smoke.R`", out)
        self.assertNotIn("lineage saw `{}`".format(FIT), out)
        self.assertIn("1 inline command(s)", out)

    def test_write_provenance_and_rewrite(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs="analysis/a/"))
        receipt = self.run_cmd("python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        out = self.verify("write", digest, "--analysis-dir", "analysis/a")
        folder = os.path.join(self.root, "analysis/a/provenance")
        for name in ("PROVENANCE.md", "plan-{}.md", "receipts-{}.jsonl", "outputs-{}.tsv", "verify-{}.md"):
            self.assertTrue(os.path.isfile(os.path.join(folder, name.format(digest))), name)
            self.assertIn("wrote analysis/a/provenance/" + name.format(digest), out)
        with open(os.path.join(folder, "receipts-{}.jsonl".format(digest))) as handle:
            self.assertEqual(json.loads(handle.readline())["command"], "python " + FIT)
        with open(os.path.join(folder, "outputs-{}.tsv".format(digest))) as handle:
            rows = [line.rstrip("\n").split("\t") for line in handle][1:]
        self.assertEqual([r[0] for r in rows], ["analysis/a/outputs/fit.tsv"])  # the script predates the plan
        self.assertEqual(len(rows[0][3]), 64)  # the full sha256
        self.verify("write", digest, "--analysis-dir", "analysis/a")
        with open(os.path.join(folder, "PROVENANCE.md")) as handle:
            self.assertEqual(sum(line.startswith("| {} |".format(digest)) for line in handle), 1)
        self.assertNotIn("provenance/", self.verify("report", digest).split("## Outputs")[1].split("##")[0])

    def test_write_needs_the_folder_and_list_shows_plans(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.assertIn("--analysis-dir", self.verify("write", digest, fails=True))
        self.assertIn("| {} |".format(digest), self.verify("list"))
        self.run_cmd("python " + FIT)
        self.run_cmd("python " + FIT)
        row, = [line for line in self.verify("list").splitlines() if digest in line]
        self.assertTrue(row.endswith("| 2 |"), row)
        self.assertIn("no approved plan", self.verify("report", "deadbeef", fails=True))

    def test_gate_must_be_on(self):
        os.remove(os.path.join(self.root, ".mycelium-extra", "gate.json"))
        self.assertIn("not on", self.verify("list", fails=True))


if __name__ == "__main__":
    unittest.main()
