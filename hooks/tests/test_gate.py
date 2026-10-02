"""Run: python3 hooks/tests/test_gate.py"""

import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
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
            "command sbatch job.sh",
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
            "command -v sbatch", "command -V snakemake && echo ok",
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
        self.approve("| 1 | run `nbs/a/b/x.ipynb` and analysis/b04_v3/run.py | user | ok |\n\n"
                     "Plan status: READY")
        self.assertTrue(self.denied(self.bash("jupyter nbconvert --execute nbs/a/c/y.ipynb")))
        self.assertTrue(self.denied(self.bash("python analysis/b04/run.py")))
        self.assertIsNone(self.bash("python analysis/b04_v3/run.py"))
        self.approve("| 1 | rerun everything in nbs/a/ as before | user | ok |\n\nPlan status: READY")
        self.assertIsNone(self.bash("jupyter nbconvert --execute nbs/a/c/y.ipynb"))

    def test_only_the_plan_table_approves(self):
        plan = "\n".join([
            "The table below had paths without the `nbs/cyto/` prefix; corrected here. No `sbatch`.",
            "",
            "- `nbs/cyto/08_focus/code/fit.R:10-40` is reused for contrasts.",
            "",
            "| # | Step (script) | Choice | Source | Validation |",
            "|---|---|---|---|---|",
            "| 1 | `nbs/cyto/13_vax/code/01_frame.R` | cohorts | user; `repo: nbs/cyto/03_surv/timing.R:144` "
            "| counts |",
            "| 2 | `nbs/cyto/13_vax/code/02_fit.R` | `~ g + (1\\|participant)` | nbs/cyto/06_sig/old.R "
            "| weights |",
            "| 3 | `nbs/cyto/13_vax/code/03_meta.R` | FE/REML | `repo: nbs/cyto/05_cox/rob.R:125` | Q |",
            "",
            "Plan status: READY_WITH_ASSUMPTIONS",
        ])
        notice = self.hook("stop", {"last_assistant_message": plan})["systemMessage"]
        self.assertIn("approving lets these run: nbs/cyto/13_vax/code/01_frame.R, "
                      "nbs/cyto/13_vax/code/02_fit.R, nbs/cyto/13_vax/code/03_meta.R.", notice)
        self.hook("prompt", {"prompt": "approve plan " + notice.split("approve plan ")[1][:8]})
        for script in ("01_frame.R", "02_fit.R", "03_meta.R"):
            self.assertIsNone(self.bash("Rscript nbs/cyto/13_vax/code/" + script), script)
        for command in [
            "Rscript nbs/cyto/13_vax/code/05_extra.R",  # same folder, not in the table
            "Rscript nbs/cyto/08_focus/code/fit.R",     # cited in Evidence
            "Rscript nbs/cyto/03_surv/timing.R",        # cited in a Source cell
            "Rscript nbs/cyto/06_sig/old.R",            # Source column, no `repo:` prefix
            "Rscript nbs/cyto/05_cox/rob.R",
            "sbatch job.sh",                            # named in prose only
        ]:
            self.assertTrue(self.denied(self.bash(command)), command)

    def test_plan_without_table_approves_nothing(self):
        text = "run analysis/x.py and sbatch job.sh\n\nPlan status: READY"
        notice = self.hook("stop", {"last_assistant_message": text})["systemMessage"]
        self.assertIn("no plan table", notice)
        self.approve(text)
        self.assertTrue(self.denied(self.bash("python analysis/x.py")))
        self.assertTrue(self.denied(self.bash("sbatch job.sh")))

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
        for command in [
            "echo {} > .mycelium-extra/approvals/a.json",
            "echo {} >.mycelium-extra/approvals/a.json",
            "rm .mycelium-extra/gate.json",
            "python3 -c \"open('.mycelium-extra/approvals/x.json','w').write('{}')\"",
            "cd .mycelium-extra && rm gate.json",
            "cp /tmp/a.json .mycelium-extra/approvals/",
            "mv .mycelium-extra/gate.json /tmp/",
            "sed -i s/24/9999/ .mycelium-extra/gate.json",
            "D=.mycelium-extra; rm $D/gate.json",
            'for f in .mycelium-extra/approvals/*; do rm "$f"; done',
            "python3 - <<'EOF'\nimport json\njson.dump({}, open('.mycelium-extra/approvals/x.json', 'w'))\nEOF",
            "find .mycelium-extra -name '*.json' -delete",
            "dd if=/dev/zero of=.mycelium-extra/gate.json",
            "echo x | tee -a .mycelium-extra/receipts.jsonl",
            'bash -c "rm .mycelium-extra/gate.json"',
            'eval "rm .mycelium-extra/gate.json"',
            "ls .mycelium-extra/approvals | xargs rm",
            "python3 tools/x.py .mycelium-extra/approvals/a.json",
            "mkdir -p .mycelium-extra/approvals",
        ]:
            self.assertTrue(self.denied(self.bash(command)), command)
        for command in [
            "cat .mycelium-extra/gate.json",
            "ls .mycelium-extra/ 2>/dev/null",
            "git check-ignore -v .mycelium-extra/gate.json || echo NOT-ignored",
            "cp .mycelium-extra/receipts.jsonl /tmp/r.jsonl",
            "cat .mycelium-extra/gate.json > /tmp/g.json 2>&1",
            # Mycelium's session-end writes, with text that mentions the folder
            "printf '### Gate blocked a run\\n**What happened**: see .mycelium-extra/approvals\\n' "
            ">> .living/learnings.md",
            "cat >> .living/learnings.md <<'EOF'\napprovals live in .mycelium-extra/approvals\nEOF",
            'python3 "$MYC/skills/core/scripts/upsert_registry_row.py" .living/log/LOG_REGISTRY.md s1 '
            '"| read .mycelium-extra/receipts.jsonl |"',
            "python3 - <<'EOF'\nimport json\nprint(json.load(open('.mycelium-extra/approvals/x.json')))\nEOF",
        ]:
            self.assertIsNone(self.bash(command), command)
        self.assertIsNone(self.hook("tool", {"tool_name": "Write",
                                             "tool_input": {"file_path": "analysis/x.py"}}))

    def test_no_gate_file_means_no_gate(self):
        os.remove(os.path.join(self.root, ".mycelium-extra", "gate.json"))
        self.assertIsNone(self.bash("python analysis/x.py"))
        self.assertIsNone(self.hook("stop", {"last_assistant_message": PLAN}))

    def test_subdirectory_cwd_finds_root(self):
        os.makedirs(os.path.join(self.root, "analysis"))
        self.assertTrue(self.denied(self.bash("python x.py", cwd=os.path.join(self.root, "analysis"))))

    # ------------------------------------------------------------ pinned inputs

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path) or self.root, exist_ok=True)
        with open(path, "w") as handle:
            handle.write(text)
        return path

    def approval(self, digest):
        with open(os.path.join(self.root, ".mycelium-extra", "approvals", digest + ".json")) as handle:
            return json.load(handle)

    def inputs_plan(self, line):
        return PLAN.replace("## Plan", "Inputs: " + line + "\n\n## Plan")

    def test_plan_without_inputs_line_pins_nothing(self):
        notice = self.hook("stop", {"last_assistant_message": PLAN})
        self.assertIn("no inputs pinned (the plan has no `Inputs:` line)", notice["systemMessage"])
        digest, result = self.approve()
        self.assertIn("No inputs pinned", result["systemMessage"])
        self.assertEqual(self.approval(digest)["pins"], {})
        self.assertIsNone(self.bash("python analysis/x.py"))

    def test_changed_input_blocks_launch(self):
        self.write("data/samples.tsv", "id\tcohort\nA\t1\n")
        self.write("renv.lock", "{}")
        digest, result = self.approve(self.inputs_plan("`data/samples.tsv` (sample table), renv.lock."))
        self.assertIn("data/samples.tsv", result["systemMessage"])
        self.assertEqual(sorted(self.approval(digest)["pins"]), ["data/samples.tsv", "renv.lock"])
        self.assertIsNone(self.bash("python analysis/x.py"))
        self.write("data/samples.tsv", "id\tcohort\nA\t2\n")
        denial = self.bash("python analysis/x.py")
        self.assertTrue(self.denied(denial))
        reason = denial["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("data/samples.tsv: sha256", reason)
        self.assertNotIn("renv.lock", reason)
        self.write("data/samples.tsv", "id\tcohort\nA\t1\n")
        self.assertIsNone(self.bash("python analysis/x.py"), "same content passes despite a new mtime")

    def test_deleted_or_new_input_blocks(self):
        self.write("data/samples.tsv", "x")
        self.approve(self.inputs_plan("data/samples.tsv, data/later.tsv"))
        self.write("data/later.tsv", "y")
        self.assertTrue(self.denied(self.bash("python analysis/x.py")))
        os.remove(os.path.join(self.root, "data", "later.tsv"))
        os.remove(os.path.join(self.root, "data", "samples.tsv"))
        self.assertTrue(self.denied(self.bash("python analysis/x.py")))

    def test_repin_names_changed_files_and_outside_paths(self):
        self.write("data/samples.tsv", "x")
        plan = self.inputs_plan("data/samples.tsv, ../elsewhere/raw.tsv, /etc/hostname")
        first = self.hook("stop", {"last_assistant_message": plan})["systemMessage"]
        self.assertIn("Outside the repository, not pinned: ../elsewhere/raw.tsv, /etc/hostname", first)
        self.assertNotIn("Changed since", first)
        self.write("data/samples.tsv", "changed")
        again = self.hook("stop", {"last_assistant_message": plan})["systemMessage"]
        self.assertIn("Changed since this plan was last shown: data/samples.tsv", again)

    def test_hash_budget_falls_back_to_size_and_mtime(self):
        self.config({"pin_hash_mb": 0})
        path = self.write("data/big.tsv", "aaaa")
        stamp = os.stat(path).st_mtime
        digest, _ = self.approve(self.inputs_plan("data/big.tsv"))
        self.assertNotIn("sha256", self.approval(digest)["pins"]["data/big.tsv"])
        self.write("data/big.tsv", "bbbb")
        os.utime(path, (stamp, stamp))
        self.assertIsNone(self.bash("python analysis/x.py"), "size+mtime cannot see this edit")
        self.write("data/big.tsv", "bbbbb")
        self.assertTrue(self.denied(self.bash("python analysis/x.py")))

    def test_time_limit_falls_back_and_says_so(self):
        self.config({"pin_seconds": 0})
        self.write("data/samples.tsv", "x")
        self.write("data/fcs/a.fcs", "1")
        notice = self.hook("stop", {"last_assistant_message": self.inputs_plan("data/samples.tsv, data/fcs/")})
        message = notice["systemMessage"]
        self.assertIn("data/samples.tsv (size+mtime)", message)
        self.assertIn("data/fcs (not pinned: time limit)", message)
        self.hook("prompt", {"prompt": "approve plan " + message.split("approve plan ")[1][:8]})
        self.write("data/fcs/b.fcs", "2")
        result = self.bash("python analysis/x.py")
        self.assertNotIn("hookSpecificOutput", result)
        self.assertIn("not re-checked", result["systemMessage"])
        self.assertIn("data/fcs", result["systemMessage"])

    def test_folder_input_is_pinned_by_listing(self):
        self.write("data/fcs/a.fcs", "1")
        self.approve(self.inputs_plan("`data/fcs/`"))
        self.assertIsNone(self.bash("python analysis/x.py"))
        self.write("data/fcs/b.fcs", "2")
        self.assertTrue(self.denied(self.bash("python analysis/x.py")))

    def test_explore_and_old_approvals_skip_pins(self):
        self.write("data/samples.tsv", "x")
        self.approve(self.inputs_plan("data/samples.tsv"))
        self.write("data/samples.tsv", "changed")
        self.hook("prompt", {"prompt": "allow explore"})
        self.assertIsNone(self.bash("MYCELIUM_EXTRA_EXPLORE=1 python analysis/x.py"))
        folder = os.path.join(self.root, ".mycelium-extra", "approvals")
        for name in os.listdir(folder):
            os.remove(os.path.join(folder, name))
        with open(os.path.join(folder, "0ld0ld00.json"), "w") as handle:
            json.dump({"hash": "0ld0ld00", "approved_at": time.time(), "plan": PLAN}, handle)
        self.assertIsNone(self.bash("python analysis/x.py"))

    # ------------------------------------------------------------ run receipts

    def post(self, command, response, cwd=None):
        return self.hook("post", {"tool_name": "Bash", "tool_input": {"command": command},
                                  "tool_response": response}, cwd)

    def receipts(self):
        path = os.path.join(self.root, ".mycelium-extra", "receipts.jsonl")
        if not os.path.isfile(path):
            return []
        with open(path) as handle:
            return [json.loads(line) for line in handle]

    def test_slow_approval_scan_denies_and_degrades_receipt(self):
        # A timeout killing the hook would print nothing and let the run through ungated.
        digest, _ = self.approve()
        sys.dont_write_bytecode = True
        sys.path.insert(0, os.path.dirname(GATE))
        import gate
        payload = {"tool_name": "Bash", "tool_input": {"command": "python analysis/x.py"},
                   "session_id": "s1", "cwd": self.root}
        config = gate.load_config(self.root)
        self.assertIsNone(gate.on_tool(payload, self.root, config), "covered when the scan finishes")
        saved, gate.SCAN_SECONDS = gate.SCAN_SECONDS, 0
        try:
            result = gate.on_tool(payload, self.root, config)
            self.assertTrue(self.denied(result))
            self.assertIn("took longer than", result["hookSpecificOutput"]["permissionDecisionReason"])
            notice = gate.on_post(dict(payload, tool_response={"stdout": ""}), self.root, config)
        finally:
            gate.SCAN_SECONDS = saved
        self.assertIn("approvals not read", notice["systemMessage"])
        self.assertEqual(self.receipts()[-1]["plans"], [])
        self.assertTrue(self.receipts()[-1]["approvals_unread"])
        self.assertTrue(os.path.isfile(os.path.join(self.root, ".mycelium-extra", "approvals",
                                                    digest + ".json")), "approvals are kept")

    def test_sbatch_receipt(self):
        self.write("job.sh", "#!/bin/bash\n#SBATCH -p cpu\n#SBATCH --mem=8G\nmodule load R/4.3\n"
                             "conda activate scanpy\nRscript analysis/x.R\n")
        self.write("renv.lock", "{}")
        digest, _ = self.approve(PLAN.replace("repo |", "repo | sbatch job.sh |"))
        notice = self.post("sbatch -o logs/%j.out job.sh",
                           {"stdout": "Submitted batch job 4242\n", "stderr": "", "interrupted": False})
        self.assertIn("sbatch job 4242", notice["systemMessage"])
        receipt, = self.receipts()
        self.assertEqual(receipt["job_id"], "4242")
        self.assertEqual(receipt["plans"], [digest])
        self.assertTrue(receipt["pins_checked"])
        self.assertEqual(receipt["script"]["path"], "job.sh")
        self.assertIn("sha256", receipt["script"])
        self.assertEqual(receipt["env_lines"], ["module load R/4.3", "conda activate scanpy"])
        self.assertEqual(receipt["sbatch_lines"], ["#SBATCH -p cpu", "#SBATCH --mem=8G"])
        self.assertEqual([f["path"] for f in receipt["lockfiles"]], ["renv.lock"])
        self.assertEqual(receipt["response_keys"], ["interrupted", "stderr", "stdout"])
        self.assertIsNone(receipt["exit_status"])
        self.assertIsNone(receipt["git"])

    def test_parsable_sbatch_and_wrap_give_one_receipt(self):
        self.approve(PLAN.replace("repo |", "repo | sbatch |"))
        self.post("sbatch --parsable --wrap='module load R; python analysis/x.py'", "4243;cluster1\n")
        receipt, = self.receipts()
        self.assertEqual(receipt["job_id"], "4243")
        self.assertIn("wrap_sha256", receipt)
        self.assertEqual(receipt["env_lines"], ["module load R"])
        self.assertEqual(receipt["response_keys"], "str")

    def test_nextflow_receipt(self):
        self.write("main.nf", "workflow {}")
        self.write("params.yaml", "a: 1")
        self.approve(PLAN.replace("repo |", "repo | nextflow |"))
        self.post("nextflow run main.nf -params-file params.yaml -profile slurm -resume -with-trace",
                  {"stdout": "N E X T F L O W  ~  version 24\nLaunching `main.nf` [sick_bell] DSL2 - revision: x\n",
                   "exit_code": 0})
        receipt, = self.receipts()
        engine = receipt["engine"]
        self.assertEqual(engine["run_name"], "sick_bell")
        self.assertEqual(engine["profile"], "slurm")
        self.assertTrue(engine["resume"])
        self.assertIs(engine["trace"], True)
        self.assertEqual([f["path"] for f in engine["files"]], ["params.yaml"])
        self.assertEqual(engine["record"], ".nextflow/history")
        self.assertEqual(receipt["script"]["path"], "main.nf")
        self.assertEqual(receipt["exit_status"], 0)

    def test_snakemake_receipt(self):
        self.write("workflow/Snakefile", "rule all: input: []")
        self.write("config/c.yaml", "a: 1")
        self.approve(PLAN.replace("repo |", "repo | snakemake |"))
        self.post("snakemake --configfile config/c.yaml --report report.html -j 4", {"stdout": ""})
        receipt, = self.receipts()
        self.assertEqual(receipt["script"]["path"], "workflow/Snakefile")
        self.assertEqual(receipt["engine"]["configfiles"], ["config/c.yaml"])
        self.assertEqual(receipt["engine"]["report"], "report.html")
        self.assertEqual(receipt["engine"]["record"], ".snakemake/metadata")

    def test_explore_receipt_tells_agent_not_reportable(self):
        notice = self.post("MYCELIUM_EXTRA_EXPLORE=1 python analysis/x.py", {"stdout": ""})
        self.assertIn("explore run", notice["systemMessage"])
        self.assertIn("Exploratory run (not reportable)", notice["hookSpecificOutput"]["additionalContext"])
        self.assertTrue(self.receipts()[0]["explore"])
        notice = self.post("python analysis/x.py", {"stdout": ""})
        self.assertNotIn("hookSpecificOutput", notice)

    def test_ungated_and_uncovered_runs(self):
        self.assertIsNone(self.post("ls analysis", {"stdout": ""}))
        self.assertEqual(self.receipts(), [])
        notice = self.post("conda run -n scanpy python analysis/x.py", {"stdout": ""})
        self.assertIn("no approved plan", notice["systemMessage"])
        receipt, = self.receipts()
        self.assertEqual(receipt["plans"], [])
        self.assertEqual(receipt["command_env"], {"manager": "conda", "env": "scanpy"})
        self.assertEqual(receipt["script"]["path"], "analysis/x.py")
        self.assertTrue(receipt["script"]["missing"])

    def test_receipt_git_state(self):
        def run(*args):
            subprocess.check_call(("git", "-C", self.root, "-c", "user.name=t", "-c", "user.email=t@t")
                                  + args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        run("init", "-q")
        self.write(".gitignore", ".mycelium-extra/\n")
        self.write("analysis/x.py", "print(1)\n")
        run("add", ".gitignore", "analysis/x.py")
        run("commit", "-qm", "init")
        self.approve()
        self.post("python analysis/x.py", {"stdout": "1"})
        self.write("analysis/x.py", "print(2)\n")
        self.post("python analysis/x.py", {"stdout": "2"})
        clean, dirty = self.receipts()
        self.assertEqual(len(clean["git"]["head"]), 40)
        self.assertFalse(clean["git"]["dirty"])
        self.assertEqual(clean["script"]["git"], "committed")
        self.assertTrue(dirty["git"]["dirty"])
        self.assertEqual(dirty["script"]["git"], "modified")
        self.write("analysis/new.py", "print(3)\n")
        self.approve(PLAN.replace("analysis/x.py", "analysis/new.py"))
        self.post("python analysis/new.py", {"stdout": "3"})
        self.assertEqual(self.receipts()[-1]["script"]["git"], "untracked")


class CompatibilityTest(unittest.TestCase):
    def test_scripts_compile_on_python_36(self):
        # Hooks call bare `python3`, which is 3.6 on some HPC systems. A SyntaxError there
        # happens before gate.py can fail open and say so, so the gate silently switches off.
        python36 = shutil.which("python3.6")
        if not python36:
            self.skipTest("python3.6 is not installed")
        repo = os.path.join(os.path.dirname(GATE), "..")
        for script in [GATE] + glob.glob(os.path.join(repo, "skills", "*", "scripts", "*.py")):
            proc = subprocess.Popen(
                [python36, "-c", "import sys; compile(open(sys.argv[1]).read(), sys.argv[1], 'exec')",
                 script], stderr=subprocess.PIPE)
            _, err = proc.communicate()
            self.assertEqual(proc.returncode, 0, err.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
