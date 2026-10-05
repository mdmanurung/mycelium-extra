"""Run: python3 skills/verify/tests/test_verify.py

Approvals and receipts are made by the real gate hooks, so the tests follow the
receipt format the gate actually writes.
"""

import base64
import glob
import json
import os
import pickle
import re
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


def hermetic(test):
    """Hide the host's env variables and ~/.conda from the gate and verify for one test."""
    saved = dict(os.environ)
    test.addCleanup(lambda: (os.environ.clear(), os.environ.update(saved)))
    for key in gate.HOOK_ENV + ("CLAUDE_CODE_SESSION_ID",):
        os.environ.pop(key, None)
    home = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, home)
    os.environ["HOME"] = home


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
        hermetic(self)
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, ".mycelium-extra"))
        self.write(".mycelium-extra/gate.json", "{}")
        self.write(FIT, "print(1)\n", mtime=time.time() - 3600)  # scripts predate their plan
        self.sacct = self.fake_sacct("")
        self.scilintr = self.fake_tool("bin/scilintr", "", 0)
        self.rscript = self.fake_tool("bin/Rscript", "", 0)

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

    def fake_tool(self, rel, output, code):
        path = self.write(rel, "#!/bin/sh\nprintf '%s' '{}'\nexit {}\n".format(output, code))
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
                                     "--sacct", kwargs.get("sacct", self.sacct),
                                     "--scilintr", kwargs.get("scilintr", self.scilintr),
                                     "--rscript", kwargs.get("rscript", self.rscript)] + list(args),
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

    def test_unknown_exit_status_is_a_gap(self):
        # Claude Code's Bash result may carry no exit status; the run is then not a success.
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.hook("post", {"tool_name": "Bash", "tool_input": {"command": "python " + FIT},
                           "tool_response": {"stdout": "", "stderr": "", "interrupted": False}})
        receipts = gate.state_path(self.root, "receipts.jsonl")
        with open(receipts) as handle:
            receipt = json.loads(handle.readlines()[-1])
        self.assertEqual(receipt["exit_status"], "unknown")
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        out = self.verify("report", digest)
        self.assertIn("| `{}` | ran (exit status unknown) |".format(FIT), out)
        self.assertIn("carried no exit status, so the run is not counted as a success", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)
        with open(receipts, "a") as handle:  # older gates wrote null
            handle.write(json.dumps(dict(receipt, exit_status=None, ts=receipt["ts"] + 0.01)) + "\n")
        out = self.verify("report", digest)
        self.assertIn("| `{}` | ran (exit status unknown) |".format(FIT), out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)
        self.run_cmd("python " + FIT)  # a later run that reports exit 0 conforms
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=time.time())
        self.assertTrue(self.verify("report", digest).rstrip().endswith("Verify status: CONFORMS"))

    def test_exit_status_from_the_hook_event(self):
        # PostToolUse fires only after success: an event-inferred 0 conforms.
        digest = self.approve(plan("run `{}`".format(FIT)))
        command = {"command": "python " + FIT}
        ok = {"stdout": "", "stderr": "", "interrupted": False}
        self.hook("post", {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": command,
                           "tool_response": ok})
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=time.time())
        out = self.verify("report", digest)
        self.assertIn("| `{}` | ran (exit 0 from hook event) |".format(FIT), out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)
        # PostToolUseFailure: the same finding as a failed run with an exit code.
        self.hook("post", {"hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "tool_input": command,
                           "error": "Exit code 2\nTraceback ..."})
        out = self.verify("report", digest)
        self.assertIn("| `{}` | failed (exit 2) |".format(FIT), out)
        self.assertIn("`{}` failed (exit 2) at".format(FIT), out)
        self.assertTrue(out.rstrip().endswith("Verify status: DOES_NOT_CONFORM"), out)
        for extra, row, finding in (
                ({"error": "Command timed out after 2m 0s"}, "failed (no exit code)",
                 "failed without an exit code at {}: Command timed out after 2m 0s"),
                ({"error": "Exit code 130", "is_interrupt": True}, "interrupted", "was interrupted at {}")):
            self.hook("post", dict(extra, hook_event_name="PostToolUseFailure", tool_name="Bash",
                                   tool_input=command))
            out = self.verify("report", digest)
            self.assertIn("| `{}` | {} |".format(FIT, row), out)
            self.assertRegex(out, re.escape("`{}` ".format(FIT)) + finding.format(".*"))
            self.assertTrue(out.rstrip().endswith("Verify status: DOES_NOT_CONFORM"), out)
        # A background start or a payload with no event name is unknown: a gap, not a success.
        self.hook("post", {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_response": ok,
                           "tool_input": dict(command, run_in_background=True)})
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=time.time())
        out = self.verify("report", digest)
        self.assertIn("| `{}` | started in the background (exit status unknown) |".format(FIT), out)
        self.assertIn("so its exit status is not known", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)
        self.hook("post", {"tool_name": "Bash", "tool_input": command, "tool_response": ok})
        out = self.verify("report", digest)
        self.assertIn("| `{}` | ran (exit status unknown) |".format(FIT), out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)

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

    def snakemake_record(self, output, rule, start, inputs, shellcmd, folder="analysis/a", code=None):
        name = base64.urlsafe_b64encode(output.encode("utf-8")).decode("ascii")
        self.write(folder + "/.snakemake/metadata/" + name, json.dumps({
            "rule": rule, "starttime": start, "endtime": start + 1, "incomplete": False,
            "input": inputs, "shellcmd": shellcmd, "code": code}))

    def test_snakemake_script_rules_and_inputs(self):
        # A rule input is read, not run. A `script:` rule's path is in `code`: base64 of a pickled
        # code object before Snakemake 9, the rule's source text in 9.x.
        def pickle_code(code):  # Snakemake 8's persistence.pickle_code
            consts = [(pickle_code(c) if type(c) == type(code) else c) for c in code.co_consts]
            return pickle.dumps((code.co_code, code.co_varnames, consts, code.co_names), protocol=4)
        scope = {}
        exec("def run(input, output, basedir):\n    script('01_step.py', basedir, input, output)\n", scope)
        old = base64.b64encode(pickle_code(scope["run"].__code__)).decode("ascii")
        steps = ["analysis/a/01_step.py", "analysis/a/02_step.py", "analysis/a/03_helper.py"]
        for path in steps:
            self.write(path, "x\n", mtime=time.time() - 60)
        digest = self.approve(plan(*["`{}`".format(p) for p in steps]))
        start = time.time()
        self.snakemake_record("outputs/1.tsv", "s01", start, ["data/in.tsv"], None, code=old)
        self.snakemake_record("outputs/2.tsv", "s02", start, ["02_step.py"], None,
                              code='    script: "02_step.py"\n')
        self.snakemake_record("outputs/3.tsv", "s03", start, ["03_helper.py"],
                              "python other.py > outputs/3.tsv")
        out = self.verify("report", digest)
        self.assertIn("| `analysis/a/01_step.py` | ran in Snakemake rule `s01` |", out)
        self.assertIn("| `analysis/a/02_step.py` | ran in Snakemake rule `s02` |", out)
        self.assertIn("| `analysis/a/03_helper.py` | no receipt |", out)
        self.assertIn("`analysis/a/03_helper.py`: no run under this plan was recorded.", out)

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

    def test_snakemake_records_beside_a_planned_script(self):
        # run.sh `cd`s into its own folder, so Snakemake writes its records there, below the
        # analysis folder; the Snakefile counts as run by the rules it defines.
        top, step, snakefile = "analysis/p/top.R", "analysis/p/a/01_step.R", "analysis/p/a/Snakefile"
        for path in (top, step):
            self.write(path, "x\n", mtime=time.time() - 60)
        self.write(snakefile, "rule s01_step:\n    input: script='01_step.R'\n", mtime=time.time() - 60)
        digest = self.approve(plan("`{}`".format(top), "`{}`".format(step), "`{}`".format(snakefile)))
        self.snakemake_record("outputs/t.tsv", "s01_step", time.time(), ["01_step.R"], "Rscript 01_step.R",
                              folder="analysis/p/a")
        out = self.verify("report", digest)
        self.assertIn("analysis folder `analysis/p`", out)
        self.assertIn("| `{}` | ran in Snakemake rule `s01_step` |".format(step), out)
        self.assertIn("| `{}` | ran in Snakemake rule `s01_step` |".format(snakefile), out)
        os.remove(os.path.join(self.root, step))
        out = self.verify("report", digest)
        self.assertIn("`{}` was deleted after its Snakemake run".format(step), out)
        self.assertIn("Verify status: DOES_NOT_CONFORM", out)

    def test_paths_only_passed_to_other_code_are_not_runs(self):
        digest = self.approve(plan("run `{}`".format(FIT), "sbatch job.sh"))
        self.run_cmd("python3 -c 'import ast' " + FIT)  # a parse check
        self.run_cmd("python3 - --code={} < /tmp/tool.py".format(FIT))  # another tool's script
        with open(gate.state_path(self.root, "receipts.jsonl"), "a") as handle:  # older gates recorded these
            handle.write(json.dumps({"command": "command -v sbatch", "kind": "sbatch", "paths": [],
                                     "plans": [digest], "ts": time.time(), "cwd": "."}) + "\n")
        out = self.verify("report", digest)
        self.assertIn("| `{}` | not run: only passed to other code |".format(FIT), out)
        self.assertIn("lint and parse calls look like this", out)
        self.assertIn("0 run(s) under this plan", out)
        self.assertIn("2 receipt(s) under this plan only passed planned paths", out)
        self.assertIn("The plan names `sbatch`, but no `sbatch` run under it was recorded.", out)
        self.run_cmd("python3 - < " + os.path.join(self.root, FIT))  # the script itself read from stdin runs
        self.assertIn("| `{}` | ran ".format(FIT), self.verify("report", digest))

    def test_deleted_script_and_code_in_an_output_folder(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs="outputs/"))
        receipt = self.run_cmd("python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        self.write("analysis/a/outputs/helper.py", "x\n", mtime=receipt["ts"] - 1)
        os.remove(os.path.join(self.root, FIT))
        out = self.verify("report", digest)
        self.assertIn("deleted since it ran", out)
        self.assertNotIn("edited", out)
        self.assertIn("Output `outputs/` read as `analysis/a/outputs/`", out)
        self.assertIn("analysis/a/outputs/fit.tsv", out)
        self.assertNotIn("helper.py", out)

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
        self.run_cmd("python3 -c 'import ast' " + FIT)  # kept in provenance, marked as not a run
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        out = self.verify("write", digest, "--analysis-dir", "analysis/a")
        folder = os.path.join(self.root, "analysis/a/provenance")
        for name in ("PROVENANCE.md", "plan-{}.md", "receipts-{}.jsonl", "outputs-{}.tsv", "verify-{}.md"):
            self.assertTrue(os.path.isfile(os.path.join(folder, name.format(digest))), name)
            self.assertIn("wrote analysis/a/provenance/" + name.format(digest), out)
        with open(os.path.join(folder, "receipts-{}.jsonl".format(digest))) as handle:
            ran, handed = [json.loads(line) for line in handle]
        self.assertEqual(ran["command"], "python " + FIT)
        self.assertNotIn("not_a_run", ran)
        self.assertIn("other code", handed["not_a_run"])
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
        self.run_cmd("python3 -c 'import ast' " + FIT)  # a parse check is not a run
        row, = [line for line in self.verify("list").splitlines() if digest in line]
        self.assertTrue(row.endswith("| 2 |"), row)
        self.assertIn("no approved plan", self.verify("report", "deadbeef", fails=True))

    def test_diff_shows_changed_rows_and_flags_choice(self):
        old = self.approve(plan("run `{}`".format(FIT), "run `analysis/a/scripts/02_plot.py`",
                                inputs="data/samples.tsv"))
        changed = plan("run `{}`".format(FIT), "run `analysis/a/scripts/03_report.py`", "run `analysis/a/run.sh`",
                       inputs="data/samples.tsv, analysis/a/Snakefile").replace(
            "| 1 | run `{}` | x |".format(FIT), "| 1 | run `{}` | donor-level |".format(FIT))
        notice = self.hook("stop", {"last_assistant_message": changed})["systemMessage"]
        new = notice.split("approve plan ")[1][:8]  # shown, not yet approved: the moment to diff
        out = self.verify("diff", old, new)
        self.assertIn("Step 1, choice: `x` -> `donor-level`. **Possible scientific change.**", out)
        self.assertIn("Step 2, step: `run `analysis/a/scripts/02_plot.py`` -> "
                      "`run `analysis/a/scripts/03_report.py``.", out)
        self.assertNotIn("Step 2, step: `run `analysis/a/scripts/02_plot.py`` -> "
                         "`run `analysis/a/scripts/03_report.py``. **Possible", out)
        self.assertIn("Step 3: added:", out)
        self.assertIn("- Inputs: + analysis/a/Snakefile", out)
        self.assertIn("No plan-table row", self.verify("diff", old, old))
        self.assertIn("needs the old and the new", self.verify("diff", old, fails=True))

    def test_multiplicity_lists_revisions_and_runs_before_the_selected_plan(self):
        def choice(text, value):
            return plan("run `{}`".format(FIT)).replace("| x |", "| {} |".format(value)) + "\n" + text
        other = self.approve(plan("run `analysis/b/scripts/01_other.py`", outputs="analysis/b/outputs/"))
        gone = self.approve(choice("Moved away.", "BH 0.2"))
        self.run_cmd("python " + FIT)
        os.remove(gate.state_path(self.root, "approvals", gone + ".json"))
        first = self.approve(choice("", "BH 0.1"))
        self.hook("prompt", {"prompt": "allow explore"})
        self.run_cmd("MYCELIUM_EXTRA_EXPLORE=1 python " + FIT)
        self.run_cmd("MYCELIUM_EXTRA_EXPLORE=1 python {} --fdr 0.2".format(FIT))
        self.write(FIT, "print(2)\n")
        self.run_cmd("MYCELIUM_EXTRA_EXPLORE=1 python " + FIT, exit_code=1)
        second = self.approve(choice("Second try.", "BH 0.05"))
        self.run_cmd("python " + FIT)
        self.write(FIT, "print(3)\n")
        digest = self.approve(choice("", "paired t; BH 0.05"))
        self.hook("post", {"tool_name": "Bash", "tool_input": {"command": "python " + FIT},
                           "tool_response": {"stdout": ""}})
        out = self.verify("multiplicity", digest)
        self.assertIn("2 earlier plan revision(s), 3 explore run(s) before the approval, 1 run(s) under "
                      "earlier plans, 1 run(s) under this plan. 1 run(s) under a plan whose approval is not on file "
                      "(gap). 2 of 2 plan change(s) edited a Choice cell.", out)
        self.assertIn("| plan {} | first plan |".format(first), out)
        self.assertIn("| plan {} | step 1 choice: `BH 0.1` -> `BH 0.05` |".format(second), out)
        self.assertIn("| plan {} | approved (selected); step 1 choice: `BH 0.05` -> `paired t; BH 0.05` |"
                      .format(digest), out)
        self.assertIn("| explore run | `MYCELIUM_EXTRA_EXPLORE=1 python {} --fdr 0.2` (other code version) | 0 |"
                      .format(FIT), out)
        self.assertIn("| run (plan {}) | `python {}` (other code version) | 0 |".format(second, FIT), out)
        self.assertIn("| run | `python {}` | not recorded |".format(FIT), out)
        self.assertNotIn(other, out)
        self.assertIn("| run (plan {}, approval not on file) |".format(gone), out)
        order = [out.index(x) for x in (first, "--fdr 0.2", "| 1 |", second, "| run | ")]
        self.assertEqual(order, sorted(order))
        data = json.loads(self.verify("multiplicity", digest, "--json"))
        self.assertEqual((data["revisions"], data["counts"]["explore before"]), (2, 3))
        self.assertIn("no approved plan", self.verify("multiplicity", "0" * 8, fails=True))

    def test_stale_lists_what_changed_since_provenance(self):
        self.assertIn("No verified plans", self.verify("stale"))
        self.write("data/samples.tsv", "a\n")
        digest = self.approve(plan("run `{}`".format(FIT), outputs="analysis/a/outputs/", inputs="data/samples.tsv"))
        receipt = self.run_cmd("python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        self.write("analysis/a/outputs/keep.tsv", "y\n", mtime=receipt["ts"] - 1)
        self.verify("write", digest, "--analysis-dir", "analysis/a")
        self.assertIn("0 of 1 verified plans stale", self.verify("stale"))
        self.write(FIT, "print(2)\n")
        self.write("data/samples.tsv", "a\nb\n")
        self.write("analysis/a/outputs/fit.tsv", "x2\n")
        os.remove(os.path.join(self.root, "analysis/a/outputs/keep.tsv"))
        os.remove(os.path.join(self.root, ".mycelium-extra", "gate.json"))  # provenance alone suffices
        out = self.verify("stale")
        self.assertIn("## Plan {} - `analysis/a`".format(digest), out)
        self.assertIn("script `{}` edited since it ran".format(FIT), out)
        self.assertIn("input `data/samples.tsv` changed", out)
        self.assertIn("output `analysis/a/outputs/fit.tsv` rewritten", out)
        self.assertIn("output `analysis/a/outputs/keep.tsv` deleted", out)
        self.assertIn("sessions: s1", out)
        self.assertIn("findings: `rg -n 's1|plan {}' .living/findings/`".format(digest), out)
        self.assertIn("1 of 1 verified plans stale", out)
        self.assertNotIn("Plan status", out)
        self.assertEqual(json.loads(self.verify("stale", "--json"))["stale"][0]["hash"], digest)
        subprocess.check_call(["git", "-C", self.root, "init", "-q"])  # git lists untracked provenance too
        self.assertIn("1 of 1 verified plans stale", self.verify("stale"))
        self.write(".gitignore", "analysis/\n")  # ignored provenance is not swept
        self.assertIn("No verified plans", self.verify("stale"))

    def test_scilintr_findings_block_and_missing_linter_is_a_gap(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        receipt = self.run_cmd("python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        self.write("analysis/a/scripts/02_plot.R", "x <- 1  # ANALYSIS_OK[magic-threshold]: fixed by design\n",
                   mtime=time.time() - 3600)
        self.write("analysis/a/outputs/junk.py", "pass\n")  # outputs are not linted
        clean = self.verify("report", digest)
        self.assertIn("scilintr: 1 Python file(s) clean", clean)
        self.assertIn("scilintr: 1 R file(s) clean", clean)
        self.assertIn("`analysis/a/scripts/02_plot.R:1` x <- 1", clean)
        self.assertTrue(clean.rstrip().endswith("Verify status: CONFORMS"), clean)
        broken = self.write("analysis/a/scripts/03_broken.py", "def f(:\n    pass\n", mtime=time.time() - 3600)
        out = self.verify("report", digest)  # scilintr passes code that does not parse, silently
        self.assertIn("`analysis/a/scripts/03_broken.py` does not parse under Python", out)
        self.assertIn("scilintr: 1 Python file(s) clean", out)
        self.assertIn("Verify status: CONFORMS_WITH_GAPS", out)
        os.remove(broken)
        finding = FIT + ":3:0: [broad-exception] broad except"
        dirty = self.fake_tool("bin/scilintr-dirty", finding + "\\n", 1)
        out = self.verify("report", digest, scilintr=dirty)
        self.assertIn("1 scilintr finding(s) remain in Python code (1 broad-exception)", out)
        self.assertIn("`{}:3` [broad-exception]".format(FIT), out)
        self.assertIn("Verify status: DOES_NOT_CONFORM", out)
        missing = self.verify("report", digest, scilintr=os.path.join(self.root, "no-scilintr"))
        self.assertIn("scilintr (Python) not checked", missing)
        self.assertIn("Verify status: CONFORMS_WITH_GAPS", missing)
        broken = self.fake_tool("bin/Rscript-broken", "there is no package called scilintr", 1)
        self.assertIn("scilintr (R) not checked: exit 1", self.verify("report", digest, rscript=broken))
        self.verify("write", digest, "--analysis-dir", "analysis/a", scilintr=dirty)
        with open(os.path.join(self.root, "analysis/a/provenance/lint-{}.txt".format(digest))) as handle:
            text = handle.read()
        self.assertIn("[broad-exception]", text)
        self.assertIn("ANALYSIS_OK waivers (1)", text)

    def notebook(self, rel, cells, language="python"):
        self.write(rel, json.dumps({
            "metadata": {"kernelspec": {"language": language}},
            "cells": [{"cell_type": kind, "source": source.splitlines(True)} for kind, source in cells]}),
            mtime=time.time() - 3600)

    def test_notebook_code_cells_are_linted(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        receipt = self.run_cmd("python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        flagger = self.write("bin/flagger", "#!{}\nimport os, sys\nhits = 0\nfor path in sys.argv[1:]:\n"
                             "    if os.path.isfile(path):\n        for n, line in enumerate(open(path), 1):\n"
                             "            if 'FLAG' in line and not line.lstrip().startswith('#'):\n                hits += 1\n"
                             "                print('{{}}:{{}}:0: [magic-threshold] flagged'.format(path, n))\n"
                             "sys.exit(1 if hits else 0)\n".format(sys.executable))
        os.chmod(flagger, os.stat(flagger).st_mode | stat.S_IEXEC)
        self.notebook("analysis/a/03_explore.ipynb", [
            ("markdown", "# FLAG in prose is ignored"), ("code", "%matplotlib inline\nimport os"),
            ("code", "%%bash\nls FLAG"), ("code", "x = 1\ny = x  # FLAG")])
        self.notebook("analysis/a/04_plot.ipynb", [("code", "FLAG <- 1")], language="R")
        rmd = ["---", "title: FLAG", "---", "FLAG in prose", "```{r setup, include=FALSE}", "x <- 1", "```",
               "```r", "FLAG in a display block", "```", "```{bash}", "echo FLAG", "```",
               "````markdown", "```{r}", "FLAG in a shown example", "```", "````",
               "```{R label}", "y <- FLAG", "```", "Inline `r FLAG` is skipped."]
        self.write("analysis/a/05_notes.Rmd", "\n".join(rmd) + "\n")
        qmd = ["```{python}", "#| echo: false", "%matplotlib inline", "!echo FLAG", "w = FLAG", "```",
               "```{.python}", "FLAG", "```", "```{r}", "v <- FLAG", "```"]
        self.write("analysis/a/06_mixed.qmd", "\n".join(qmd) + "\n")
        self.write("analysis/a/07_prose.qmd", "Prose only, FLAG.\n")
        out = self.verify("report", digest, scilintr=flagger, rscript=flagger)
        self.assertIn("`analysis/a/03_explore.ipynb[code cell 3]:2` [magic-threshold]", out)
        self.assertIn("2 scilintr finding(s) remain in Python code", out)
        self.assertIn("`analysis/a/04_plot.ipynb[code cell 1]:1` [magic-threshold]", out)
        self.assertIn("`analysis/a/05_notes.Rmd:{}` [magic-threshold]".format(rmd.index("y <- FLAG") + 1), out)
        self.assertIn("`analysis/a/06_mixed.qmd:{}` [magic-threshold]".format(qmd.index("w = FLAG") + 1), out)
        self.assertIn("`analysis/a/06_mixed.qmd:{}` [magic-threshold]".format(qmd.index("v <- FLAG") + 1), out)
        self.assertIn("3 scilintr finding(s) remain in R code", out)
        self.assertIn("1 notebook(s) not linted: analysis/a/07_prose.qmd", out)
        self.assertNotIn("mycelium-extra-lint-", out)
        self.notebook("analysis/a/08_broken.ipynb", [("code", "def f(:\n    pass")])
        self.write("analysis/a/09_broken.qmd", "Text\n```{python}\ndef f(:\n```\n")
        out = self.verify("report", digest)
        self.assertIn("scilintr (Python) not checked: `analysis/a/08_broken.ipynb` does not parse", out)
        self.assertIn("scilintr (Python) not checked: `analysis/a/09_broken.qmd` does not parse", out)
        self.assertIn("line 3", out)
        self.assertIn("Verify status: CONFORMS_WITH_GAPS", out)

    def conda_env(self):
        """A fake conda env named fakeenv, listed in a fake ~/.conda/environments.txt."""
        prefix = os.path.join(self.root, "envs", "fakeenv")
        self.write("envs/fakeenv/conda-meta/b-2-0.json", json.dumps({"url": "https://x/b-2-0.conda", "md5": "bb"}))
        self.write("envs/fakeenv/conda-meta/a-1-0.json", json.dumps({"url": "https://x/a-1-0.conda", "md5": "aa"}))
        self.write("envs/fakeenv/conda-meta/history", "==> 2024 <==\n", mtime=time.time() - 7200)
        self.write("envs/fakeenv/bin/python", "")
        self.write("home/.conda/environments.txt", prefix + "\n/elsewhere/envs/other\n")
        home = os.environ.get("HOME")
        os.environ["HOME"] = os.path.join(self.root, "home")
        self.addCleanup(lambda: os.environ.__setitem__("HOME", home) if home else os.environ.pop("HOME"))
        return prefix

    def test_conda_env_is_recorded_into_provenance(self):
        self.conda_env()
        digest = self.approve(plan("run `{}`".format(FIT)))
        receipt = self.run_cmd("conda run -n fakeenv python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        self.assertIn("Conda env `fakeenv` (`conda run`): 2 packages recorded", self.verify("report", digest))
        self.verify("write", digest, "--analysis-dir", "analysis/a")
        with open(os.path.join(self.root, "analysis/a/provenance/env-{}.txt".format(digest))) as handle:
            self.assertIn("@EXPLICIT\nhttps://x/a-1-0.conda#aa\nhttps://x/b-2-0.conda#bb\n", handle.read())
        with open(os.path.join(self.root, "analysis/a/provenance/PROVENANCE.md")) as handle:
            self.assertIn("[conda env](env-{}.txt)".format(digest), handle.read())
        history = os.path.join(self.root, "envs/fakeenv/conda-meta/history")
        os.utime(history, (receipt["ts"] + 100, receipt["ts"] + 100))
        out = self.verify("report", digest)
        self.assertIn("Conda env `fakeenv` changed", out)
        self.assertIn("Verify status: CONFORMS_WITH_GAPS", out)

    def test_conda_env_from_interpreter_path_and_missing_env(self):
        prefix = self.conda_env()
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.run_cmd("{}/bin/python {}".format(prefix, FIT))
        self.run_cmd("conda run -n nosuch python " + FIT)
        out = self.verify("report", digest)
        self.assertIn("Conda env `fakeenv` (interpreter path): 2 packages recorded", out)
        self.assertIn("Conda env `nosuch` (`conda run`) was not found", out)

    def test_conda_env_from_prefix_and_job_script(self):
        self.conda_env()
        self.write("job.sh", "#!/bin/bash\n#SBATCH -p cpu\nconda activate fakeenv\npython {}\n".format(FIT))
        digest = self.approve(plan("run `{}`".format(FIT), "sbatch `job.sh`"))
        self.run_cmd("sbatch job.sh", stdout="Submitted batch job 4242\n")
        self.assertIn("Conda env `fakeenv` (`activate` in the job script): 2 packages recorded",
                      self.verify("report", digest))
        self.run_cmd("conda run -p envs/fakeenv python " + FIT)  # one env, two sources: first one named
        out = self.verify("report", digest)
        self.assertEqual(out.count("Conda env "), 1, out)

    def test_session_env_only_when_the_job_declares_none(self):
        prefix = self.conda_env()
        self.write("job.sh", "#!/bin/bash\nmodule load R/4.3\nRscript analysis/a/x.R\n")
        digest = self.approve(plan("sbatch `job.sh`"))
        os.environ["CONDA_PREFIX"] = prefix  # the gate's hook records the session's env
        self.addCleanup(os.environ.pop, "CONDA_PREFIX")
        self.run_cmd("sbatch job.sh", stdout="Submitted batch job 4243\n")
        self.assertNotIn("Conda env", self.verify("report", digest))
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.run_cmd("python " + FIT)
        self.assertIn("Conda env `fakeenv` (session `CONDA_PREFIX`)", self.verify("report", digest))

    def test_conda_lock_means_no_snapshot(self):
        self.conda_env()
        self.write("conda-lock.yml", "version: 1\n")
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.run_cmd("conda run -n fakeenv python " + FIT)
        self.assertNotIn("Conda env", self.verify("report", digest))

    def pip_env(self):
        """fakeenv plus site-packages: two conda-owned folders (one reinstalled by pip at the same
        version), a pip-only package, a pip upgrade over a conda one, an editable uv install, and a
        plain-file egg-info. Every folder is older than the run."""
        prefix = self.conda_env()
        site = "envs/fakeenv/lib/python3.12/site-packages/"
        for name, version in [("anndata", "0.10.9"), ("scipy", "1.11.0"), ("numpy", "1.26.0")]:
            files = ["lib/python3.12/site-packages/{}-{}.dist-info/METADATA".format(name, version)]
            self.write("envs/fakeenv/conda-meta/{}-{}-0.json".format(name, version), json.dumps(
                {"name": name, "version": version, "url": "https://x/{}.conda".format(name), "files": files}))
        meta = "Metadata-Version: 2.1\nName: {}\nVersion: {}\n\nName: not-a-header\n"
        for folder, name, version, installer in [
                ("anndata-0.10.9", "anndata", "0.10.9", "conda"), ("scipy-1.11.0", "scipy", "1.11.0", "pip"),
                ("loguru-0.7.2", "loguru", "0.7.2", "pip"), ("numpy-1.26.4", "numpy", "1.26.4", "pip"),
                ("my_tool-0.1", "my_tool", "0.1", "uv")]:
            self.write(site + folder + ".dist-info/METADATA", meta.format(name, version))
            self.write(site + folder + ".dist-info/INSTALLER", installer)
        self.write(site + "my_tool-0.1.dist-info/direct_url.json",
                   json.dumps({"url": "file:///home/me/my-tool", "dir_info": {"editable": True}}))
        self.write(site + "old-2.egg-info", meta.format("old", "2"))
        for path in glob.glob(os.path.join(prefix, "lib/python3.12/site-packages/*")):
            os.utime(path, (time.time() - 7200, time.time() - 7200))
        return prefix

    def test_pip_packages_are_recorded_beside_conda_ones(self):
        self.pip_env()
        digest = self.approve(plan("run `{}`".format(FIT)))
        receipt = self.run_cmd("conda run -n fakeenv python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        out = self.verify("report", digest)
        self.assertIn("Conda env `fakeenv` (`conda run`): 5 packages recorded; 5 pip packages "
                      "(2 also in conda-meta).", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)
        self.verify("write", digest, "--analysis-dir", "analysis/a")
        with open(os.path.join(self.root, "analysis/a/provenance/pip-{}.txt".format(digest))) as handle:
            text = handle.read()
        self.assertIn("# env: fakeenv\n", text)
        self.assertIn("\nloguru==0.7.2\nmy_tool==0.1  # installer: uv; editable: file:///home/me/my-tool\n"
                      "numpy==1.26.4  # also in conda-meta as 1.26.0\nold==2\n"
                      "scipy==1.11.0  # also in conda-meta as 1.11.0\n", text)
        self.assertNotIn("anndata", text)
        with open(os.path.join(self.root, "analysis/a/provenance/PROVENANCE.md")) as handle:
            self.assertIn("[conda env](env-{0}.txt) - [pip](pip-{0}.txt) |".format(digest), handle.read())

    def test_conda_lock_still_records_pip_packages(self):
        self.pip_env()
        self.write("conda-lock.yml", "version: 1\n")
        digest = self.approve(plan("run `{}`".format(FIT)))
        receipt = self.run_cmd("conda run -n fakeenv python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        self.assertIn("Conda env `fakeenv` (`conda run`): conda packages pinned by `conda-lock.yml`; 5 pip "
                      "packages (2 also in conda-meta) recorded.", self.verify("report", digest))
        self.verify("write", digest, "--analysis-dir", "analysis/a")
        provenance = os.path.join(self.root, "analysis/a/provenance")
        self.assertTrue(os.path.isfile(os.path.join(provenance, "pip-{}.txt".format(digest))))
        self.assertFalse(os.path.exists(os.path.join(provenance, "env-{}.txt".format(digest))))
        self.run_cmd("conda run -n nosuch python " + FIT)
        self.assertIn("Conda env `nosuch` (`conda run`) was not found, so its pip packages were not recorded",
                      self.verify("report", digest))

    def test_pip_install_after_the_run_and_unreadable_metadata_are_gaps(self):
        prefix = self.pip_env()
        digest = self.approve(plan("run `{}`".format(FIT)))
        receipt = self.run_cmd("conda run -n fakeenv python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        late = os.path.join(prefix, "lib/python3.12/site-packages/loguru-0.7.2.dist-info")
        os.utime(late, (receipt["ts"] + 100, receipt["ts"] + 100))
        self.write("envs/fakeenv/lib/python3.12/site-packages/broken-1.dist-info/INSTALLER", "pip")
        os.utime(os.path.dirname(late) + "/broken-1.dist-info", (receipt["ts"] - 100, receipt["ts"] - 100))
        out = self.verify("report", digest)
        self.assertIn("Pip packages in conda env `fakeenv` changed", out)
        self.assertIn("1 pip package folder(s) have no readable name and version, so they were not recorded: "
                      "`broken-1.dist-info`", out)
        self.assertIn("Verify status: CONFORMS_WITH_GAPS", out)

    def test_env_without_site_packages_has_no_pip_line(self):
        self.conda_env()
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.run_cmd("conda run -n fakeenv python " + FIT)
        out = self.verify("report", digest)
        self.assertIn("Conda env `fakeenv` (`conda run`): 2 packages recorded.", out)
        self.assertNotIn("pip package", out)

    def test_explore_lists_this_sessions_runs_for_a_plan(self):
        self.hook("prompt", {"prompt": "allow explore"})
        first = self.run_cmd("MYCELIUM_EXTRA_EXPLORE=1 python " + FIT)
        self.run_cmd("MYCELIUM_EXTRA_EXPLORE=1 python " + FIT)
        self.run_cmd("MYCELIUM_EXTRA_EXPLORE=1 python -c 'import x' " + FIT)  # path handed to code: no run
        other = dict(first, session_id="s2", command="MYCELIUM_EXTRA_EXPLORE=1 python analysis/a/other.py")
        with open(gate.state_path(self.root, "receipts.jsonl"), "a") as handle:
            handle.write(json.dumps(other) + "\n")
        self.write(FIT, "print(2)\n")
        session = os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        self.addCleanup(lambda: session and os.environ.__setitem__("CLAUDE_CODE_SESSION_ID", session))
        os.environ["CLAUDE_CODE_SESSION_ID"] = "s1"
        out = self.verify("explore")
        self.assertIn("# Explore runs (session s1)", out)
        self.assertIn("1. `python {}`".format(FIT), out)
        self.assertIn("(2 runs)", out)
        self.assertIn("script `{}` edited since this run".format(FIT), out)
        self.assertNotIn("other.py", out)
        self.assertNotIn("2. ", out)
        self.assertIn("other.py", self.verify("explore", "--all"))
        del os.environ["CLAUDE_CODE_SESSION_ID"]
        self.assertIn("no session ID found, so every session is shown", self.verify("explore"))
        self.assertEqual(len(json.loads(self.verify("explore", "--session", "s2", "--json"))), 1)

    def test_status_lists_plans_with_verify_lint_stale_and_manifest(self):
        self.assertIn("No plans", self.verify("status"))
        verified = self.approve(plan("run `{}`".format(FIT)))
        receipt = self.run_cmd("python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        dirty = self.fake_tool("bin/scilintr-dirty", FIT + ":3:0: [broad-exception] broad except\\n", 1)
        self.verify("write", verified, "--analysis-dir", "analysis/a", scilintr=dirty)
        self.write("analysis/b/scripts/01_x.py", "print(1)\n", mtime=time.time() - 3600)
        pending = self.approve(plan("run `analysis/b/scripts/01_x.py`"))
        out = self.verify("status")
        self.assertIn("| {} | `analysis/a` |".format(verified), out)
        self.assertIn("| 1 | DOES_NOT_CONFORM | no | 1 finding(s) | not listed |", out)
        self.assertIn("| {} | `analysis/b` |".format(pending), out)
        self.assertIn("| 0 | not verified | - | - | not listed |", out)
        shapes = {  # Mycelium's YAML template and the shapes real manifests use
            "# Analysis Manifest\n\n### a\n```yaml\nname: a\n# a comment\nstatus: active\n```\n\n### b\n": "listed: active",
            "| Analysis | Location | Status |\n|---|---|---|\n| A | `analysis/a/` | Complete 2026-09-25 in x |\n":
                "listed: complete",
            "## Fit\n\n**Status**: draft — 2026-07-21\nLives in `analysis/a`.\n": "listed: draft",
            "| # | Name | Status |\n|---|---|---|\n| A1 | `analysis/a` | ✅\U0001F7E1 **Primary** x |\n":
                "listed: primary",
            "Folder `analysis/a` holds the fit.\n": "listed",
            "See `analysis/ab/` and analysis/a.old\n": "not listed",
        }
        for text, expected in shapes.items():
            with open(os.path.join(self.root, "analysis/ANALYSIS_MANIFEST.md"), "w", encoding="utf-8") as handle:
                handle.write(text)
            rows = {r["hash"]: r for r in json.loads(self.verify("status", "--json"))}
            self.assertEqual(rows[verified]["manifest"], expected, text)
        self.write("analysis/a/scripts/02_plot.R", "x <- 1\n", mtime=time.time() - 3600)
        self.verify("write", verified, "--analysis-dir", "analysis/a",  # R clean, Python linter missing
                    scilintr=os.path.join(self.root, "no-scilintr"))
        rows = {r["hash"]: r for r in json.loads(self.verify("status", "--json"))}
        self.assertEqual(rows[verified]["lint"], "gap: Python not checked")
        self.write(FIT, "print(2)\n")
        os.remove(os.path.join(self.root, ".mycelium-extra", "gate.json"))  # provenance alone suffices
        out = self.verify("status")
        self.assertIn("| 1 change(s) |", out)
        self.assertNotIn(pending, out)

    def claims_run(self, block, prose=""):
        """One planned run writing two outputs, and the analysis doc carrying `block`."""
        digest = self.approve(plan("run `{}`".format(FIT)))
        receipt = self.run_cmd("python " + FIT)
        self.write("analysis/a/outputs/de.tsv", "gene\tlog2fc\tpadj\tshare\nIL7R\t1.23456\t0.0412\t0.344\n"
                   "CD3E\t-0.5\t0.05\t0.1\nCD3E\t2\t0.9\t0.2\n", mtime=receipt["ts"] - 1)
        self.write("analysis/a/outputs/numbers.json", '{"qc": {"n": 48, "kept": [40, 8]}}',
                   mtime=receipt["ts"] - 1)
        self.write("analysis/a/A.md", "# a\n\n## Key Findings\n\n{}\n<!-- claims\n{}\n-->\n\n## Next\n\n"
                                      "Run 5 more.\n".format(prose, block))
        return digest, receipt

    def test_claims_verified_by_rounding_transform_inequality_rows_and_json(self):
        digest, _ = self.claims_run("\n".join([
            "- 1.235 | outputs/de.tsv log2fc IL7R", "- 1.234 | outputs/de.tsv log2fc IL7R",
            "- 34% | outputs/de.tsv share IL7R", "- < 0.05 | outputs/de.tsv padj IL7R",
            "- 3 | outputs/de.tsv rows", "- 48 | outputs/numbers.json qc.n | donors",
            "- 8 | analysis/a/outputs/numbers.json qc.kept.1"]),
            prose="IL7R rose 1.235 log2 units in 48 donors (padj 0.0412, n = 3).")
        out = self.verify("report", digest)
        self.assertIn("`analysis/a/A.md`: 7 verified (1 via transform), 0 mismatch, 0 unverified", out)
        # "log2" and the "5" of "Run 5 more", in the next section, are not listed.
        self.assertIn("1 number(s) in `analysis/a/A.md` near its claims block are not claims, so not checked: "
                      "L5 `0.0412`.", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)
        self.assertEqual(json.loads(self.verify("report", digest, "--json"))["claims"][0]["counts"],
                         {"verified": 6, "verified-transform": 1})

    def test_claims_mismatch_blocks(self):
        digest, _ = self.claims_run("- 1.3 | outputs/de.tsv log2fc IL7R\n- > 0.05 | outputs/de.tsv padj IL7R")
        out = self.verify("report", digest)
        self.assertIn("**block**: `analysis/a/A.md:7` claims 1.3, but `analysis/a/outputs/de.tsv` log2fc row "
                      "IL7R holds 1.23456.", out)
        self.assertIn("`analysis/a/A.md:8` claims >0.05", out)
        self.assertIn("Verify status: DOES_NOT_CONFORM", out)

    def test_fact_tags_counted_and_flagged_in_plan_and_key_findings(self):
        evidence = "\n".join([
            "", "**Evidence**", "- 48 donors [agent-derived: `data/meta.tsv:1`]",
            "- the contrast is day 28 [human-stated]", "- BH suits independent tests [agent-asserted: none]",
            "- an untagged fact", "  that wraps", "- a derived fact [agent-derived]", "",
            "Facts: 2 agent-derived, 1 human-stated, 1 agent-asserted (1 unsourced).", ""])
        digest = self.approve(plan("run `{}`".format(FIT)).replace("\nOutputs:", evidence + "\nOutputs:"))
        self.run_cmd("python " + FIT)
        self.write("analysis/a/A.md", "# a\n\n## Key Findings\n\n<!-- one bullet per result -->\n"
                                      "- IL7R rises [agent-derived: `outputs/de.tsv`].\n- CD3E falls\n\n## Next\n")
        out = self.verify("report", digest)
        self.assertIn("Fact tags in the plan's Evidence: 2 agent-derived, 1 human-stated, 1 agent-asserted, "
                      "1 untagged; flagged: L6 agent-asserted without a source; L7 untagged `an untagged fact "
                      "that wraps`; L9 agent-derived without its artifact.", out)
        self.assertIn("Fact tags in `analysis/a/A.md` Key Findings: 1 agent-derived, 1 untagged; "
                      "flagged: L7 untagged `CD3E falls`.", out)
        self.assertEqual(re.findall(r"\*\*(?:gap|block)\*\*: (?:Fact|Default)", out), [])  # advisory

    def test_untagged_or_absent_facts(self):
        digest = self.approve(plan("run `{}`".format(FIT)).replace(
            "\nOutputs:", "\nEvidence:\n- one\n- two\n\nOutputs:"))
        self.run_cmd("python " + FIT)
        out = self.verify("report", digest)
        self.assertIn("Fact tags: 2 fact(s) in the plan's Evidence, none tagged (written before D7, "
                      "or untagged).", out)
        self.assertNotIn("Key Findings", out)  # no analysis doc, no line
        digest = self.approve(plan("run `{}`".format(FIT), outputs="analysis/a/outputs/x"))
        self.assertNotIn("Fact tags", self.verify("report", digest))

    def test_section_bullets_layouts(self):
        sys.path.insert(0, os.path.dirname(SCRIPT))
        import verify
        for label in ("## Evidence", "**Evidence**", "Evidence:", "- **Evidence**:", "**Evidence.**"):
            self.assertEqual(verify.section_bullets("x\n{}\n\n- a [human-stated]\n* b\n1. c\nnext\n- d"
                                                    .format(label), "Evidence"),
                             [(4, "a [human-stated]"), (5, "b"), (6, "c")], label)
        self.assertEqual(verify.section_bullets("Evidence suggests x\n- a\n", "Evidence"), [])

    def test_unlocated_claims_are_gaps(self):
        # 0.05 is in the padj column, but no row is named: a common value never verifies by itself.
        digest, _ = self.claims_run("\n".join([
            "- 0.05 | outputs/de.tsv padj", "- 2 | outputs/de.tsv log2fc CD3E", "- 1 | outputs/missing.tsv x",
            "- 1 | outputs/de.tsv pval IL7R", "- 1 | outputs/de.tsv log2fc GAPDH", "- 1 | outputs/de.tsv gene IL7R",
            "- about 2 | outputs/de.tsv log2fc IL7R"]))
        self.write("analysis/a/notes.md", "1.2\n")
        out = self.verify("report", digest, "--claims", "analysis/a/notes.md", "--claims", "nope.md")
        for text in ["claim 0.05 is unverified: 3 rows match; name one by its first-column label",
                     "claim 2 is unverified: 2 rows are labelled `CD3E`",
                     "cites `analysis/a/outputs/missing.tsv`, but it does not exist", "no column `pval`",
                     "no row `GAPDH`", "row IL7R holds `IL7R`, not a number", "claims line does not parse",
                     "Claims not checked in `analysis/a/notes.md`: it has no `<!-- claims -->` block",
                     "Claims not checked in `nope.md`: it does not exist"]:
            self.assertIn(text, out)
        self.assertNotIn("**block**", out)
        self.assertIn("Verify status: CONFORMS_WITH_GAPS", out)

    def test_claim_from_an_explore_output_blocks(self):
        digest, receipt = self.claims_run("- 1.235 | outputs/de.tsv log2fc IL7R")
        self.hook("prompt", {"prompt": "allow explore"})
        explore = self.run_cmd("MYCELIUM_EXTRA_EXPLORE=1 python " + FIT)
        mtime = explore["ts"] + 4.99  # past the planned run's 5 s tolerance, within the explore run's
        self.assertGreater(mtime, receipt["ts"] + 5)
        os.utime(os.path.join(self.root, "analysis/a/outputs/de.tsv"), (mtime, mtime))
        out = self.verify("report", digest)
        self.assertIn("claims 1.235 from `analysis/a/outputs/de.tsv` log2fc row IL7R, which an explore run "
                      "wrote", out)
        self.assertIn("1 explore-only", out)
        self.assertIn("Verify status: DOES_NOT_CONFORM", out)

    def test_gate_must_be_on(self):
        os.remove(os.path.join(self.root, ".mycelium-extra", "gate.json"))
        self.assertIn("not on", self.verify("list", fails=True))


if __name__ == "__main__":
    unittest.main()
