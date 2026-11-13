"""Run: python3.11 hooks/tests/test_gate_mycelium.py

The post-run notice for each runner Mycelium does or does not detect, and the approval-time
`**Planning**:` line (gate.json `planning_line`)."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

GATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gate.py")
PLAN = "## Plan\n| 1 | run `analysis/x/fit.py` | repo | check |\n\nPlan status: READY"
DOC = "analysis/x/X.md"
PENDING = "# X\n\n**Planning**: pending\n\nbody\n"
STATE = ".mycelium-extra"


class Base(unittest.TestCase):
    def setUp(self):
        saved = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(saved)))
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        os.environ["HOME"] = home
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, STATE))
        self.config({})

    def config(self, data):
        with open(os.path.join(self.root, STATE, "gate.json"), "w") as handle:
            json.dump(data, handle)

    def write(self, rel, data, mode="w"):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode) as handle:
            handle.write(data)
        return path

    def read(self, rel):
        with open(os.path.join(self.root, rel), "rb") as handle:
            return handle.read()

    def hook(self, event, payload):
        payload = dict(payload, session_id="s1", cwd=self.root)
        proc = subprocess.run([sys.executable, GATE, event], input=json.dumps(payload).encode("utf-8"),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout) if proc.stdout.strip() else None


class PostRunNotice(Base):
    def context(self, command):
        notice = self.hook("post", {"tool_name": "Bash", "tool_input": {"command": command},
                                    "tool_response": {"stdout": ""}})
        return ((notice or {}).get("hookSpecificOutput") or {}).get("additionalContext", "")

    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(self.root, ".living"))

    def test_runners_mycelium_detects_get_no_did_not_fire_notice(self):
        for command in ["python analysis/x/fit.py", "Rscript analysis/x/fit.R", "bash analysis/x/run.sh",
                        "./analysis/x/run.sh", "snakemake -s analysis/x/Snakefile", "sbatch analysis/x/job.sh",
                        "nextflow run analysis/x/main.nf"]:
            self.assertNotIn("did not fire", self.context(command), command)

    def test_runners_mycelium_misses_still_get_it(self):
        for command in ["julia analysis/x/fit.jl", "perl analysis/x/fit.pl"]:
            self.assertIn("post-action protocol did not fire", self.context(command), command)

    def test_sbatch_says_to_wait_for_the_job(self):
        text = self.context("sbatch analysis/x/job.sh")
        self.assertIn("may not have finished", text)
        self.assertIn("If Mycelium opened its post-action protocol", text)
        for command in ["python analysis/x/fit.py", "bash analysis/x/run.sh", "snakemake -s analysis/x/Snakefile"]:
            self.assertNotIn("check the job status", self.context(command), command)

    def test_no_living_folder_no_notice(self):
        shutil.rmtree(os.path.join(self.root, ".living"))
        self.assertEqual(self.context("julia analysis/x/fit.jl"), "")
        self.assertEqual(self.context("sbatch analysis/x/job.sh"), "")


class PlanningLine(Base):
    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(self.root, ".living"))
        self.write(".living/INDEX.md", "index\n")

    def approve(self, text=PLAN):
        notice = self.hook("stop", {"last_assistant_message": text})
        digest = notice["systemMessage"].split("approve plan ")[1][:8]
        return digest, self.hook("prompt", {"prompt": "approve plan " + digest})

    def tree(self):
        found = {}
        for folder, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if d != STATE]
            for name in files:
                path = os.path.join(folder, name)
                if not os.path.islink(path):
                    with open(path, "rb") as handle:
                        found[os.path.relpath(path, self.root)] = handle.read()
        return found

    def test_set_once(self):
        self.write(DOC, PENDING)
        digest, _ = self.approve()
        lines = self.read(DOC).decode().splitlines()
        self.assertRegex(lines[2], r"^\*\*Planning\*\*: discussed \d{4}-\d\d-\d\d \(approved plan %s\)$" % digest)
        self.assertEqual(lines[:2] + lines[3:], ["# X", "", "", "body"])
        after = self.read(DOC)
        self.approve()  # a second approval finds no pending line and leaves the doc as it is
        self.assertEqual(self.read(DOC), after)

    def test_bullet_prefix_is_kept(self):
        self.write(DOC, "# X\n\n- **Planning**: pending\n")
        self.approve()
        self.assertTrue(self.read(DOC).decode().splitlines()[2].startswith("- **Planning**: discussed "))

    def test_absent_doc(self):
        before = self.tree()
        self.approve()
        self.assertEqual(self.tree(), before)

    def test_already_discussed(self):
        self.write(DOC, "# X\n\n**Planning**: discussed 2026-10-01\n")
        before = self.tree()
        self.approve()
        self.assertEqual(self.tree(), before)

    def test_step_folder_readme_without_the_line_does_not_hide_the_doc(self):
        self.write("analysis/x/code/README.md", "# code\n\nno planning line\n")
        self.write(DOC, PENDING)
        plan = PLAN.replace("analysis/x/fit.py", "analysis/x/code/01_fit.R")
        self.write("analysis/x/code/01_fit.R", "x\n")
        digest, _ = self.approve(plan)
        self.assertIn("approved plan " + digest, self.read(DOC).decode())

    def test_two_matching_lines(self):
        self.write(DOC, "**Planning**: pending\n\n**Planning**: pending\n")
        before = self.tree()
        self.approve()
        self.assertEqual(self.tree(), before)

    def test_key_off(self):
        self.config({"planning_line": False})
        self.write(DOC, PENDING)
        before = self.tree()
        self.approve()
        self.assertEqual(self.tree(), before)

    def test_no_living_folder(self):
        shutil.rmtree(os.path.join(self.root, ".living"))
        self.write(DOC, PENDING)
        before = self.tree()
        self.approve()
        self.assertEqual(self.tree(), before)

    def test_symlink_doc_is_not_touched(self):
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside)
        target = os.path.join(outside, "doc.md")
        with open(target, "w") as handle:
            handle.write(PENDING)
        os.makedirs(os.path.join(self.root, "analysis/x"))
        os.symlink(target, os.path.join(self.root, DOC))
        self.approve()
        with open(target) as handle:
            self.assertEqual(handle.read(), PENDING)
        self.assertTrue(os.path.islink(os.path.join(self.root, DOC)))

    def test_crlf_file_keeps_its_line_endings(self):
        self.write(DOC, PENDING.replace("\n", "\r\n").encode(), "wb")
        self.approve()
        data = self.read(DOC)
        self.assertEqual(data.count(b"\r\n"), data.count(b"\n"))
        self.assertIn(b"discussed", data)

    def test_defaults_change_no_file_but_the_doc(self):
        self.write(DOC, PENDING)
        self.write("analysis/x/fit.py", "pass\n")
        self.write("README.md", "**Planning**: pending\n")  # outside the plan's folders
        before = self.tree()
        self.approve()
        after = self.tree()
        self.assertEqual([k for k in after if after[k] != before.get(k)], [DOC])
        self.assertEqual(set(after), set(before), "no temp file is left behind")

    def test_plan_with_no_doc_folder_leaves_the_repo_readme(self):
        self.write("README.md", "**Planning**: pending\n")
        before = self.tree()
        self.approve()
        self.assertEqual(self.tree(), before)

    def test_error_goes_to_the_log_only_when_it_exists(self):
        self.write(DOC, PENDING)
        folder = os.path.join(self.root, "analysis/x")
        os.chmod(folder, 0o555)  # the temp file cannot be made
        self.addCleanup(os.chmod, folder, 0o755)
        if os.access(folder, os.W_OK):
            self.skipTest("running as a user who ignores folder modes")
        log = os.path.join(self.root, STATE, "gate-errors.jsonl")
        self.approve()
        self.assertFalse(os.path.exists(log))
        self.assertEqual(self.read(DOC).decode(), PENDING)
        with open(log, "w") as handle:
            handle.write("")
        self.approve()
        with open(log) as handle:
            self.assertIn("planning_line", handle.read())


class Config(Base):
    def test_new_keys_validate(self):
        sys.path.insert(0, os.path.dirname(GATE))
        import gate
        self.assertIs(gate.DEFAULTS["planning_line"], True)
        self.assertIs(gate.DEFAULTS["where_mycelium"], False)
        self.config({"planning_line": "yes", "where_mycelium": 1})
        config = gate.load_config(self.root)
        self.assertIs(config["planning_line"], True)
        self.assertIs(config["where_mycelium"], False)
        self.assertEqual(len(config["_notices"]), 2)


if __name__ == "__main__":
    unittest.main()
