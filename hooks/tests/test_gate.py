"""Run: python3 hooks/tests/test_gate.py"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

GATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gate.py")
PLAN = "## Plan\n| 1 | run `analysis/x.py` | repo | check |\n\nPlan status: READY"


class GateTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, ".mycelium-extra"))
        self.config({})

    def tearDown(self):
        shutil.rmtree(self.root)

    def config(self, data):
        with open(os.path.join(self.root, ".mycelium-extra", "gate.json"), "w") as handle:
            json.dump(data, handle)

    def hook(self, event, payload, cwd=None):
        payload = dict(payload, session_id="s1", cwd=cwd or self.root)
        proc = subprocess.Popen([sys.executable, GATE, event], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate(json.dumps(payload).encode("utf-8"))
        self.assertEqual(proc.returncode, 0, err)
        return json.loads(out.decode("utf-8")) if out.strip() else None

    def bash(self, command, cwd=None):
        return self.hook("tool", {"tool_name": "Bash", "tool_input": {"command": command}}, cwd)

    def denied(self, result):
        return bool(result) and result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def approve(self, text=PLAN):
        notice = self.hook("stop", {"last_assistant_message": text})
        digest = notice["systemMessage"].split("approve plan ")[1][:8]
        result = self.hook("prompt", {"prompt": "approve plan " + digest})
        return digest, result

    def test_gated_runs_are_denied(self):
        for command in [
            "python analysis/x.py",
            "python3 - < analysis/x.py",
            'python -c "$(cat analysis/x.py)"',
            "cd analysis && python x.py",
            "/opt/envs/R4_51/bin/Rscript analysis/x.R",
            "conda run -n scanpy python analysis/x.py",
            "timeout 60 python analysis/x.py 2>&1 | tail",
            "srun -p gpu -c 4 python analysis/x.py",
            "sbatch job.sh",
            "./analysis/run.sh",
            "jupyter nbconvert --to notebook --execute nbs/n.ipynb",
            "python -m analysis.x",
            "MYCELIUM_EXTRA_EXPLORE=1 true && python analysis/x.py",
            "echo hi\npython analysis/x.py",
            "Rscript -e \"source('analysis/x.R')\"",
            'bash -lc "python analysis/x.py"',
            "sbatch --wrap='python analysis/x.py'",
            "R CMD BATCH analysis/x.R",
            "R --file=analysis/x.R",
            "python -W ignore analysis/x.py",
            "source analysis/env.sh",
            ". analysis/env.sh",
        ]:
            self.assertTrue(self.denied(self.bash(command)), command)

    def test_reading_and_ungated_runs_pass(self):
        for command in [
            "cat analysis/x.py", "rg foo analysis/", "sed -n 1,5p analysis/x.py",
            "git add analysis/x.py", "python tools/y.py", "ls nbs",
            "python3 - --contract /tmp/c.json < /plugin/check.py",
            "python3 - <<'EOF'\nimport os; os.system('python analysis/x.py')\nEOF",
            "python tools/plot.py analysis/b04/outputs/numbers.json",
        ]:
            self.assertIsNone(self.bash(command), command)

    def test_explore_prefix_needs_user_grant(self):
        self.assertTrue(self.denied(self.bash("MYCELIUM_EXTRA_EXPLORE=1 python analysis/x.py")))
        self.assertIsNone(self.hook("prompt", {"prompt": "please allow explore now"}))
        self.assertTrue(self.denied(self.bash("MYCELIUM_EXTRA_EXPLORE=1 python analysis/x.py")))
        self.assertIn("allowed", self.hook("prompt", {"prompt": "allow explore"})["systemMessage"])
        self.assertIsNone(self.bash("MYCELIUM_EXTRA_EXPLORE=1 python analysis/x.py"))
        self.assertTrue(self.denied(self.bash("python analysis/x.py")))
        self.assertTrue(self.denied(self.bash("MYCELIUM_EXTRA_EXPLORE=1 true && python analysis/x.py")))
        self.hook("prompt", {"prompt": "stop explore"})
        self.assertTrue(self.denied(self.bash("MYCELIUM_EXTRA_EXPLORE=1 python analysis/x.py")))

    def test_explore_grant_is_per_session(self):
        self.hook("prompt", {"prompt": "allow explore"})
        payload = {"tool_name": "Bash", "session_id": "s2", "cwd": self.root,
                   "tool_input": {"command": "MYCELIUM_EXTRA_EXPLORE=1 python analysis/x.py"}}
        proc = subprocess.Popen([sys.executable, GATE, "tool"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        out, _ = proc.communicate(json.dumps(payload).encode("utf-8"))
        self.assertIn("deny", out.decode("utf-8"))

    def test_explore_prefix_runs_and_is_listed_once(self):
        self.hook("prompt", {"prompt": "allow explore"})
        self.assertIsNone(self.bash("MYCELIUM_EXTRA_EXPLORE=1 python analysis/x.py"))
        notice = self.hook("stop", {"last_assistant_message": "done"})
        self.assertIn("not reportable", notice["systemMessage"])
        self.assertIsNone(self.hook("stop", {"last_assistant_message": "done"}))

    def test_approval_unlocks_only_plan_paths(self):
        self.assertTrue(self.denied(self.bash("python analysis/x.py")))
        digest, result = self.approve()
        self.assertIn("approved", result["systemMessage"])
        self.assertIsNone(self.bash("python analysis/x.py"))
        self.assertTrue(self.denied(self.bash("python analysis/other.py")))

    def test_wrap_payload_must_also_be_planned(self):
        self.approve(PLAN.replace("repo |", "repo | sbatch |"))
        self.assertTrue(self.denied(self.bash("sbatch --wrap='python analysis/other.py'")))
        self.assertIsNone(self.bash("sbatch --wrap='python analysis/x.py'"))

    def test_gated_command_needs_its_word_in_plan(self):
        self.approve()
        self.assertTrue(self.denied(self.bash("snakemake -j 4")))
        self.approve(PLAN.replace("repo |", "repo | sbatch job |"))
        self.assertIsNone(self.bash("sbatch job.sh"))

    def test_decision_required_gets_no_hash(self):
        self.assertIsNone(self.hook("stop", {"last_assistant_message": "Plan status: DECISION_REQUIRED"}))

    def test_approval_must_be_the_whole_prompt(self):
        notice = self.hook("stop", {"last_assistant_message": PLAN})
        digest = notice["systemMessage"].split("approve plan ")[1][:8]
        result = self.hook("prompt", {"prompt": "the agent said: approve plan " + digest})
        self.assertIn("nothing approved", result["systemMessage"])
        self.assertTrue(self.denied(self.bash("python analysis/x.py")))
        self.assertIn("approved", self.hook("prompt", {"prompt": "Approve plan {}.".format(digest)})["systemMessage"])
        self.assertIsNone(self.bash("python analysis/x.py"))

    def test_bare_approve_lists_pending(self):
        notice = self.hook("stop", {"last_assistant_message": PLAN})
        digest = notice["systemMessage"].split("approve plan ")[1][:8]
        result = self.hook("prompt", {"prompt": "approve plan"})
        self.assertIn(digest, result["hookSpecificOutput"]["additionalContext"])
        self.assertTrue(self.denied(self.bash("python analysis/x.py")))

    def test_status_must_be_its_own_line(self):
        echoed = "blocked; present a plan ending with a `Plan status: READY` line"
        self.assertIsNone(self.hook("stop", {"last_assistant_message": echoed}))
        self.assertIsNotNone(self.hook("stop", {"last_assistant_message": "x\n**Plan status**: READY"}))

    def test_plan_binding_is_by_path_token(self):
        self.approve("run `nbs/a/b/x.ipynb` and analysis/b04_v3/run.py\n\nPlan status: READY")
        self.assertTrue(self.denied(self.bash("jupyter nbconvert --execute nbs/a/c/y.ipynb")))
        self.assertTrue(self.denied(self.bash("python analysis/b04/run.py")))
        self.assertIsNone(self.bash("python analysis/b04_v3/run.py"))
        self.approve("rerun everything in nbs/a/ as before\n\nPlan status: READY")
        self.assertIsNone(self.bash("jupyter nbconvert --execute nbs/a/c/y.ipynb"))

    def test_unknown_hash_says_so(self):
        result = self.hook("prompt", {"prompt": "approve plan deadbeef"})
        self.assertIn("Nothing was approved", result["systemMessage"])

    def test_expired_approval_denies(self):
        self.config({"approval_hours": 0})
        self.approve()
        self.assertTrue(self.denied(self.bash("python analysis/x.py")))

    def test_state_writes_are_denied(self):
        for tool, field, path in [
            ("Write", "file_path", ".mycelium-extra/approvals/abc.json"),
            ("Edit", "file_path", "analysis/../.mycelium-extra/gate.json"),
            ("NotebookEdit", "notebook_path", ".mycelium-extra/x.ipynb"),
        ]:
            result = self.hook("tool", {"tool_name": tool, "tool_input": {field: path}})
            self.assertTrue(self.denied(result), path)
        self.assertTrue(self.denied(self.bash("echo {} > .mycelium-extra/approvals/a.json")))
        self.assertTrue(self.denied(self.bash("rm .mycelium-extra/gate.json")))
        self.assertTrue(self.denied(self.bash(
            "python3 -c \"open('.mycelium-extra/approvals/x.json','w').write('{}')\"")))
        self.assertIsNone(self.bash("cat .mycelium-extra/gate.json"))
        self.assertIsNone(self.hook("tool", {"tool_name": "Write",
                                             "tool_input": {"file_path": "analysis/x.py"}}))

    def test_no_gate_file_means_no_gate(self):
        os.remove(os.path.join(self.root, ".mycelium-extra", "gate.json"))
        self.assertIsNone(self.bash("python analysis/x.py"))
        self.assertIsNone(self.hook("stop", {"last_assistant_message": PLAN}))

    def test_subdirectory_cwd_finds_root(self):
        os.makedirs(os.path.join(self.root, "analysis"))
        self.assertTrue(self.denied(self.bash("python x.py", cwd=os.path.join(self.root, "analysis"))))


if __name__ == "__main__":
    unittest.main()
