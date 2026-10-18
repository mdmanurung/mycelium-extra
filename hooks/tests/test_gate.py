"""Run: python3 hooks/tests/test_gate.py"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

GATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gate.py")
LAUNCHER = os.path.join(os.path.dirname(GATE), "gate_run.py")
PLAN = "## Plan\n| 1 | run `analysis/x.py` | repo | check |\n\nPlan status: READY"

REAL_HOME = os.environ.get("HOME", "")  # setUp points HOME at a scratch folder


class GateTest(unittest.TestCase):
    entry = GATE

    def setUp(self):
        # Hooks record the session's env variables in receipts; keep the host's out of them.
        saved = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(saved)))
        for key in ("CONDA_DEFAULT_ENV", "CONDA_PREFIX", "VIRTUAL_ENV", "PIXI_ENVIRONMENT_NAME"):
            os.environ.pop(key, None)
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        os.environ["HOME"] = home
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, ".mycelium-extra"))
        self.config({})

    def tearDown(self):
        shutil.rmtree(self.root)

    def config(self, data):
        with open(os.path.join(self.root, ".mycelium-extra", "gate.json"), "w") as handle:
            json.dump(data, handle)

    def hook(self, event, payload, cwd=None, session="s1"):
        payload = dict(payload, session_id=session, cwd=cwd or self.root)
        proc = subprocess.Popen([sys.executable, self.entry, event], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate(json.dumps(payload).encode("utf-8"))
        self.assertEqual(proc.returncode, 0, err)
        return json.loads(out.decode("utf-8")) if out.strip() else None

    def bash(self, command, cwd=None):
        return self.hook("tool", {"tool_name": "Bash", "tool_input": {"command": command}}, cwd)

    def denied(self, result):
        return bool(result) and result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

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
            "snakemake -n",  # a Snakefile is Python: a dry run still runs its top-level code
            "bash analysis/x/run.sh -n",
            "python3 -c \"exec(open('analysis/x.py').read())\"",
            "python3 -c \"import sys; sys.path.insert(0, 'analysis/lib'); import fit\"",
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
            # inline probes that read gated data or folders run no gated code
            "python3 -c \"import anndata; print(anndata.read_h5ad('analysis/x/data/a.h5ad'))\"",
            "python3 -c \"import os; print(os.listdir('nbs/sub'))\"",
        ]:
            self.assertIsNone(self.bash(command), command)

    def test_each_deny_is_counted_and_an_allow_is_not(self):
        self.assertTrue(self.denied(self.bash("python analysis/x.py")))
        self.assertIsNone(self.bash("ls"))
        with open(os.path.join(self.root, ".mycelium-extra", "denies.jsonl")) as handle:
            lines = [json.loads(line) for line in handle]
        self.assertEqual([(l["session_id"], l["tool"]) for l in lines], [("s1", "Bash")])
        self.assertTrue(lines[0]["reason"])

    def test_the_python_launcher_is_read_as_python(self):
        launcher = "sh /plugin/hooks/py.sh "
        for command in ["analysis/x.py", "- < analysis/x.py", '-c "$(cat analysis/x.py)"',
                        "--hook analysis/x.py", "- --dest analysis/demo < /plugin/new_analysis.py"]:
            self.assertTrue(self.denied(self.bash(launcher + command)), command)
            self.assertTrue(self.denied(self.bash("python3 " + command.replace("--hook ", ""))), command)
        self.assertIsNone(self.bash(launcher + "- --contract /tmp/c.json < /plugin/check.py"))
        self.assertTrue(self.denied(self.bash("sh analysis/py.sh")))  # a gated py.sh is a script, not the launcher

    # wrapper options: a known option's value is skipped, not read as the command (ME-04)
    def test_wrapper_option_values_do_not_hide_gated_runs(self):
        root = self.root
        for command in [
            "conda run -p /tmp/env python analysis/x.py",
            "conda run --prefix=/tmp/env python analysis/x.py",
            "conda run -n scanpy python analysis/x.py",
            "uv run --project envdir python analysis/x.py",
            "uv run --project . python analysis/x.py",
            "uv run --python 3.12 python analysis/x.py",
            "uv run -p 3.12 --with pandas python analysis/x.py",
            "uv run --directory . python analysis/x.py",
            "env -C %s python analysis/x.py" % root,
            "env --chdir=%s python analysis/x.py" % root,
            "env -C analysis python x.py",  # relative path resolves against the new folder
            "env -u HOME python analysis/x.py",
            "env -S 'python analysis/x.py'",
            "env FOO=1 python analysis/x.py",
            "srun -D analysis python x.py",
            "timeout -s KILL 5 python analysis/x.py",  # an option the reader does not know
            "uv run --not-an-option value python analysis/x.py",
        ]:
            self.assertTrue(self.denied(self.bash(command)), command)

    def test_wrapped_commands_that_run_nothing_gated_pass(self):
        for command in [
            "uv run --help", "env", "env -u HOME", "conda env list", "conda run -n x ls",
            "conda run -p /tmp/env ls", "time ls", "uv run --with pandas ls",
            "uv run --not-an-option value cat analysis/x.py",
            "env -C /tmp python tools/y.py", "conda run --cwd /tmp python y.py",
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
        notice = self.hook("stop", {"last_assistant_message": "done"})["systemMessage"]
        self.assertIn("1 exploratory run(s) this session are not reportable", notice)
        self.assertIn('Say "promote explore runs" to plan a reportable re-run.', notice)

    def test_explore_grant_is_per_session(self):
        self.hook("prompt", {"prompt": "allow explore"})
        payload = {"tool_name": "Bash", "session_id": "s2", "cwd": self.root,
                   "tool_input": {"command": "MYCELIUM_EXTRA_EXPLORE=1 python analysis/x.py"}}
        proc = subprocess.Popen([sys.executable, self.entry, "tool"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
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

    def test_absolute_plan_path_inside_the_root_means_the_relative_path(self):
        self.approve(PLAN.replace("`analysis/x.py`", "`{}/analysis/x.py`".format(self.root)))
        self.assertIsNone(self.bash("python analysis/x.py"))
        self.assertTrue(self.denied(self.bash("python analysis/other.py")))

    def test_absolute_plan_path_outside_the_root_approves_nothing(self):
        self.approve(PLAN.replace("`analysis/x.py`", "`/elsewhere/analysis/x.py`"))
        self.assertTrue(self.denied(self.bash("python analysis/x.py")))

    def test_quoted_script_with_spaces_is_granted_and_pinned_without_fragment_grants(self):
        self.write("analysis/my script.py", "print(1)\n")
        for quote in ("`", '"', "'"):
            self.approve(PLAN.replace("`analysis/x.py`", quote + "analysis/my script.py" + quote))
            self.assertIsNone(self.bash('python "analysis/my script.py"'))
            self.assertTrue(self.denied(self.bash("python analysis/my/other.py")))
        self.write("analysis/my script.py", "print(2)\n")
        result = self.bash('python "analysis/my script.py"')
        self.assertFalse(self.denied(result))
        self.assertIn("analysis/my script.py re-pinned", result["systemMessage"])

    CARD_PLAN = "\n".join([
        "> Question (user's words): \"does A beat B?\"",
        "> Hoped-for claim: \"yes\"",
        "",
        "**Objective.** Compare A with B on the cohort, no refits.",
        "",
        "**Evidence**",
        "- Both placebo fits fail the E-BFMI gate. [agent-derived: results/x.tsv]",
        "- Cohort has 24 rows. [human-stated]",
        "",
        "Facts: 1 agent-derived, 1 human-stated, 0 agent-asserted.",
        "",
        "Inputs: data/in.tsv",
        "Outputs: analysis/a/out/res.tsv",
        "",
        "| # | Step | Choice | Source | Validation |",
        "|---|---|---|---|---|",
        "| 1 | Back up the old table (done) | keep old output | default: nothing is lost | md5 equal |",
        "| 2 | Run `analysis/a/02_fit.py` | exact permutation test | user | 12 donors x 2 visits |",
        "| 3 | Run `snakemake` | dry run only | repo: CLAUDE.md | dry run resolves |",
        "",
        "Plan status: READY_WITH_ASSUMPTIONS",
    ])

    AMENDED_ROW = "| 4 | Run `analysis/a/04_plot.py` | volcano of step 2 | agent | none written |\n"

    def amended(self, plan=None, row=None, outputs=None):
        """CARD_PLAN with one more row (and output), the way an agent adds a script to an approved plan."""
        plan = (plan or self.CARD_PLAN).replace("| dry run resolves |\n", "| dry run resolves |\n" + (row or self.AMENDED_ROW), 1)
        return plan.replace("Outputs: analysis/a/out/res.tsv", "Outputs: " + (outputs or "analysis/a/out/res.tsv, analysis/a/out/volcano.pdf"))

    def test_a_plan_that_only_adds_a_script_shows_the_change_only_card(self):
        self.write_file("analysis/a/04_plot.py", "import sys\nprint(1)\n")
        digest, _ = self.approve(self.CARD_PLAN)
        card = self.card(self.amended())
        self.assertIn("amendment to {} \u00b7 +1 step, +1 script".format(digest), card)
        self.assertIn("Adds      analysis/a/04_plot.py   (new, 2 lines)", card)
        self.assertIn("Row       4  volcano of step 2  [agent]   check: none written", card)
        self.assertIn("Writes    new: analysis/a/out/volcano.pdf", card)
        self.assertIn("Grant     script analysis/a/04_plot.py; any arguments; no folder or command grant added", card)
        self.assertIn("Unchanged 3 steps, 0 scripts pinned, 1 input", card)
        self.assertRegex(card, r"\u25b6 approve amendment [0-9a-f]{8}  \(or approve\)\Z")
        self.assertNotIn("Choices", card)
        self.assertIn("Sequence", self.full(self.amended()), "the whole card stays behind `card <hash> full`")
        self.assertTrue(self.denied(self.bash("python analysis/a/04_plot.py")))
        self.hook("prompt", {"prompt": "approve"})  # the one card waiting
        self.assertIsNone(self.bash("python analysis/a/04_plot.py"))

    def test_an_amendment_that_changes_anything_else_gets_the_whole_card(self):
        self.approve(self.CARD_PLAN)
        for name, plan in (
                ("a changed choice", self.amended().replace("exact permutation test", "asymptotic test")),
                ("a removed row", self.amended().replace(
                    "| 3 | Run `snakemake` | dry run only | repo: CLAUDE.md | dry run resolves |\n", "")),
                ("another objective", self.amended().replace("no refits", "with refits")),
                ("a new input", self.amended().replace("Inputs: data/in.tsv", "Inputs: data/in.tsv, data/more.tsv")),
                ("a folder grant", self.amended(row="| 4 | Run `analysis/b/` scripts | all | agent | none |\n")),
                ("a new command grant", self.amended(row="| 4 | Run `sbatch` | queue | agent | none |\n"))):
            card = self.card(plan)
            self.assertNotIn("amendment to", card, name)
            self.assertIn("Choices", card, name)

    def test_the_same_plan_shown_again_is_not_an_amendment(self):
        self.approve(self.CARD_PLAN)
        self.assertNotIn("amendment to", self.card(self.CARD_PLAN))

    def card(self, plan):
        return self.hook("stop", {"last_assistant_message": plan})["systemMessage"]

    def full(self, plan):
        """The full card (`card <hash> full`) of a plan shown now; self.card is the compact one."""
        return self.asked(self.card(plan), "full")

    def asked(self, card, part=""):
        """What `card <hash> <part>` shows the user; the agent never gets the prompt."""
        digest = re.findall(r"approve (?:plan|amendment) ([0-9a-f]{8})", card)[-1]
        answer = self.hook("prompt", {"prompt": ("card {} {}".format(digest, part)).strip()})
        self.assertEqual(answer["decision"], "block")
        return answer["reason"]

    def fake_linter(self, output="", code=0):
        """A scilintr that prints `output`, recorded in tools.json."""
        path = os.path.join(self.root, "fake-scilintr")
        with open(path, "w") as handle:
            handle.write("#!/bin/sh\nprintf '%s\\n' '{}'\nexit {}\n".format(output, code))
        os.chmod(path, 0o755)
        self.write_file(".mycelium-extra/tools.json", json.dumps({"scilintr": path}))

    def test_card_shows_scilintr_per_step_and_never_blocks(self):
        self.write_file("analysis/a/02_fit.py", "print(1)\n")
        self.fake_linter()
        self.assertIn("        - check: 12 donors x 2 visits\n        - lint: clean\n  \u2193 3 snakemake", self.full(self.CARD_PLAN))
        self.assertIn("          lint: clean", self.card(self.CARD_PLAN))
        self.fake_linter("analysis/a/02_fit.py:1:1: [broad-exception] x", 1)
        card = self.card(self.CARD_PLAN)
        self.assertIn("          lint: step 2: 1 open (broad-exception)", card)
        self.assertIn("        - lint: 1 open (broad-exception)", self.asked(card, "full"))
        self.assertIn("approve plan ", card.splitlines()[-1])
        self.write_file(".mycelium-extra/tools.json", json.dumps({"scilintr": "/nonexistent/scilintr"}))
        self.assertIn("        - lint: not checked (`/nonexistent/scilintr` not found.", self.full(self.CARD_PLAN))
        self.assertIn("lint: step 2: not checked (`/nonexistent/scilintr` not found.", self.card(self.CARD_PLAN))
        self.write_file(".mycelium-extra/gate.json", json.dumps({"card_lint": False}))
        self.assertNotIn("- lint:", self.card(self.CARD_PLAN))

    def written(self, rel, tool="Write", session="s1"):
        path = os.path.join(self.root, rel)
        return self.hook("post", {"tool_name": tool, "tool_input": {"file_path": path}}, session=session)

    def context(self, notice):
        return ((notice or {}).get("hookSpecificOutput") or {}).get("additionalContext", "")

    def test_write_lint_reaches_the_agent_once_per_change(self):
        self.write_file("analysis/a/02_fit.py", "print(1)\n")
        self.fake_linter("analysis/a/02_fit.py:1:1: [broad-exception] x", 1)
        first = self.context(self.written("analysis/a/02_fit.py"))
        self.assertIn("1 open finding(s) in `analysis/a/02_fit.py`", first)
        self.assertIn("analysis/a/02_fit.py:1: [broad-exception] x", first)
        self.assertEqual(self.context(self.written("analysis/a/02_fit.py", "Edit")), "", "same findings: once")
        self.fake_linter("analysis/a/02_fit.py:1:1: [broad-exception] x\nanalysis/a/02_fit.py:2:1: [silent-coercion] y", 1)
        self.assertIn("2 open finding(s)", self.context(self.written("analysis/a/02_fit.py", "MultiEdit")))
        self.fake_linter()
        self.assertEqual(self.context(self.written("analysis/a/02_fit.py")), "")
        self.fake_linter("analysis/a/02_fit.py:1:1: [broad-exception] x", 1)
        self.assertIn("1 open finding(s)", self.context(self.written("analysis/a/02_fit.py")), "reappears after clean")

    def test_write_lint_stays_silent_outside_gated_code(self):
        self.fake_linter("scripts/x.py:1:1: [broad-exception] x", 1)
        self.write_file("scripts/x.py", "print(1)\n")
        self.write_file("analysis/a/NOTES.md", "x\n")
        for rel in ("scripts/x.py", "analysis/a/NOTES.md", "analysis/a/missing.py"):
            self.assertIsNone(self.written(rel), rel)
        self.write_file("analysis/a/02_fit.py", "print(1)\n")
        self.write_file(".mycelium-extra/gate.json", json.dumps({"lint_on_write": False}))
        self.assertIsNone(self.written("analysis/a/02_fit.py"))

    def test_what_could_not_be_checked_is_said_once_per_session(self):
        # A script that does not parse under the hook's Python is not "clean", whether half written or
        # valid for a newer Python than the hook's (`:=` on 3.6): say so once, and keep earlier findings.
        self.write_file("analysis/a/02_fit.py", "print(1)\n")
        self.fake_linter("analysis/a/02_fit.py:1:1: [broad-exception] x", 1)
        self.written("analysis/a/02_fit.py")
        self.write_file("analysis/a/02_fit.py", "def (:\n")
        first = self.context(self.written("analysis/a/02_fit.py"))
        self.assertIn("not a clean result", first)
        self.assertIn("`analysis/a/02_fit.py` does not parse", first)
        self.assertEqual(self.context(self.written("analysis/a/02_fit.py")), "", "once per session")
        self.assertIn("not a clean result", self.context(self.written("analysis/a/02_fit.py", session="s2")))
        folder = os.path.join(self.root, ".mycelium-extra", "pending", "s1.lint")
        self.assertEqual(len(os.listdir(folder)), 1, "the earlier findings are kept")
        self.fake_linter("analysis/b/03.py:1:1: [x] y", 1)
        self.write_file(".mycelium-extra/tools.json", json.dumps({"scilintr": "/nonexistent/scilintr"}))
        self.write_file("analysis/a/03_ok.py", "print(1)\n")
        self.assertIn("`/nonexistent/scilintr` not found", self.context(self.written("analysis/a/03_ok.py")))
        self.assertEqual(self.context(self.written("analysis/a/03_ok.py", "Edit")), "")

    def test_unreadable_notebook_is_reported_as_unchecked(self):
        self.write_file("analysis/a/draft.ipynb", "{unfinished")
        text = self.context(self.written("analysis/a/draft.ipynb", "NotebookEdit"))
        self.assertIn("not a clean result", text)
        self.assertIn("`analysis/a/draft.ipynb` has no readable code", text)

    def test_parallel_writes_keep_every_script(self):
        names = ["analysis/a/0{}_fit.py".format(n) for n in range(1, 5)]
        for rel in names:
            self.write_file(rel, "print(1)\n")
        self.fake_linter("\n".join("{}:1:1: [broad-exception] x".format(rel) for rel in names), 1)
        threads = [threading.Thread(target=self.written, args=(rel,)) for rel in names]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        notice = self.hook("stop", {"last_assistant_message": "done"})["systemMessage"]
        for n in range(1, 5):
            self.assertIn("0{}_fit.py".format(n), notice)

    def test_missing_linter_with_extension_keeps_earlier_findings(self):
        self.write_file("analysis/a/02_fit.py", "print(1)\n")
        self.fake_linter("analysis/a/02_fit.py:1:1: [broad-exception] x", 1)
        self.written("analysis/a/02_fit.py")
        self.write_file(".mycelium-extra/tools.json", json.dumps({"scilintr": "/missing/scilintr.py"}))
        self.assertIn("not a clean result", self.context(self.written("analysis/a/02_fit.py")))
        notice = self.hook("stop", {"last_assistant_message": "done"})
        self.assertIn("02_fit.py (broad-exception)", notice["systemMessage"])

    def test_parallel_unchecked_writes_report_a_gap_once_without_errors(self):
        names = ["analysis/a/0{}_fit.py".format(n) for n in range(1, 5)]
        for rel in names:
            self.write_file(rel, "print(1)\n")
        self.write_file(".mycelium-extra/tools.json", json.dumps({"scilintr": "/missing/scilintr.py"}))
        replies, errors = [], []

        def written(rel):
            try:
                replies.append(self.written(rel))
            except Exception as error:
                errors.append(error)

        threads = [threading.Thread(target=written, args=(rel,)) for rel in names]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(sum("not a clean result" in self.context(reply) for reply in replies), 1)
        self.assertFalse(any(reply and "gate error" in reply.get("systemMessage", "") for reply in replies))

    def test_stop_includes_an_r_waiver_without_a_reason(self):
        self.write_file("analysis/a/03_sum.R", '# ANALYSIS_OK[R016]:\nsamples <- c("S1", "S2")\n')
        rscript = os.path.join(self.root, "fake-rscript")
        with open(rscript, "w") as handle:
            handle.write("#!/bin/sh\ncase \"$*\" in *apply_waivers*) "
                         "printf '%s\\n' 'analysis/a/03_sum.R:2:1: [R016] sample IDs'; exit 1;; esac\n")
        os.chmod(rscript, 0o755)
        self.write_file(".mycelium-extra/tools.json", json.dumps({"rscript": rscript}))
        self.assertIn("waives R016 with no reason", self.context(self.written("analysis/a/03_sum.R")))
        notice = self.hook("stop", {"last_assistant_message": "done"})
        self.assertIn("03_sum.R (waiver-reason)", notice["systemMessage"])

    def test_a_patch_is_linted_for_every_file_it_adds_or_updates(self):
        names = ["analysis/a/01_load.py", "analysis/a/02_fit.py", "analysis/a/03_plot.py"]
        for rel in names:
            self.write_file(rel, "print(1)\n")
        self.fake_linter("analysis/a/01_load.py:1:1: [unchecked-merge] x\nanalysis/a/02_fit.py:2:1: [silent-pass] y", 1)
        patch = ("*** Begin Patch\n*** Update File: {}\n@@\n-a\n+b\n*** Add File: {}\n+print(1)\n"
                 "*** Delete File: {}\n*** End Patch").format(*names)
        notice = self.hook("post", {"tool_name": "apply_patch", "tool_input": {"command": patch},
                                    "hook_event_name": "PostToolUse"})
        text = self.context(notice)
        self.assertIn("analysis/a/01_load.py:1: [unchecked-merge] x", text)
        self.assertIn("analysis/a/02_fit.py:2: [silent-pass] y", text)
        self.assertNotIn("03_plot", text, "a deleted file is not linted")

    def test_patch_limit_reports_the_files_it_could_not_check(self):
        names = ["analysis/a/0{}_fit.py".format(n) for n in range(1, 7)]
        for rel in names:
            self.write_file(rel, "print(1)\n")
        self.fake_linter("analysis/a/01_fit.py:1:1: [silent-pass] x", 1)
        patch = "*** Begin Patch\n" + "".join("*** Update File: {}\n".format(rel) for rel in names) + "*** End Patch"
        text = self.context(self.hook("post", {"tool_name": "apply_patch", "tool_input": {"command": patch}}))
        self.assertIn("01_fit.py:1: [silent-pass]", text)
        self.assertIn("`analysis/a/06_fit.py` exceeds the five-file write limit", text)

    def test_internal_lint_error_is_advisory_and_reported_once(self):
        sys.path.insert(0, os.path.dirname(GATE))
        import gate
        self.write_file("analysis/a/02_fit.py", "print(1)\n")
        event = {"session_id": "s1", "tool_name": "Write", "tool_input": {"file_path": "analysis/a/02_fit.py"}}
        config = {"gated_paths": ["analysis/**"]}
        with mock.patch.object(gate, "load_verify", side_effect=ValueError("unreadable")):
            self.assertIn("lint hook failed (ValueError)", self.context(gate.lint_on_write(event, self.root, config)))
            self.assertIsNone(gate.lint_on_write(event, self.root, config))

    def test_stop_skips_a_script_changed_while_the_linter_ran(self):
        sys.path.insert(0, os.path.dirname(GATE))
        import gate
        rel = "analysis/a/02_fit.py"
        self.write_file(rel, "print(1)\n")
        path = os.path.join(self.root, rel)
        verify = gate.load_verify()

        def lint(*args, **kwargs):
            os.utime(path, (os.path.getmtime(path) + 5,) * 2)
            return {"findings": [(rel, "1", "1", "silent-pass", "x")]}

        event = {"session_id": "s1", "tool_name": "Write", "tool_input": {"file_path": rel}}
        with mock.patch.object(gate, "load_verify", return_value=verify), mock.patch.object(verify, "lint", side_effect=lint):
            gate.lint_on_write(event, self.root, {"gated_paths": ["analysis/**"]})
        self.assertIsNone(gate.open_lint_notice(self.root, event, {}))

    def test_finding_text_is_cleaned_before_the_agent_reads_it(self):
        self.write_file("analysis/a/02_fit.py", "print(1)\n")
        self.fake_linter("analysis/a/02_fit.py:1:1: [broad-exception] a\x1b[31m" + "b" * 400, 1)
        text = self.context(self.written("analysis/a/02_fit.py"))
        self.assertNotIn("\x1b", text)
        self.assertLess(max(len(line) for line in text.splitlines()), 330)

    def test_stop_tells_the_user_what_is_still_open_once(self):
        self.write_file("analysis/a/02_fit.py", "print(1)\n")
        self.fake_linter("analysis/a/02_fit.py:1:1: [broad-exception] x", 1)
        self.written("analysis/a/02_fit.py")
        notice = self.hook("stop", {"last_assistant_message": "done"})["systemMessage"]
        self.assertIn("still open in script(s) written this session: 02_fit.py (broad-exception)", notice)
        self.assertIsNone(self.hook("stop", {"last_assistant_message": "done"}), "shown once")
        self.assertIsNone(self.hook("stop", {"last_assistant_message": "done"}, session="s2"), "another session")
        self.fake_linter()
        self.write_file("analysis/a/03_clean.py", "print(1)\n")
        self.written("analysis/a/03_clean.py")
        self.assertIsNone(self.hook("stop", {"last_assistant_message": "done"}), "a clean new file is no change")
        self.fake_linter()
        self.written("analysis/a/02_fit.py")
        self.assertIsNone(self.hook("stop", {"last_assistant_message": "done"}))
        self.fake_linter("analysis/a/02_fit.py:1:1: [broad-exception] x", 1)
        self.written("analysis/a/02_fit.py")
        self.assertIn("still open", self.hook("stop", {"last_assistant_message": "done"})["systemMessage"],
                      "findings that return after a clean result must be shown again")
        self.fake_linter()
        self.written("analysis/a/02_fit.py")
        self.fake_linter("analysis/a/02_fit.py:1:1: [broad-exception] x", 1)
        self.written("analysis/a/02_fit.py")
        self.assertIn("still open", self.hook("stop", {"last_assistant_message": "done"})["systemMessage"],
                      "a clean result followed by the same finding in one turn must also be shown")

    def test_stop_skips_a_script_edited_since_its_lint(self):
        self.write_file("analysis/a/02_fit.py", "print(1)\n")
        self.fake_linter("analysis/a/02_fit.py:1:1: [broad-exception] x", 1)
        self.written("analysis/a/02_fit.py")
        path = os.path.join(self.root, "analysis/a/02_fit.py")
        os.utime(path, (os.path.getmtime(path) + 5,) * 2)
        self.assertIsNone(self.hook("stop", {"last_assistant_message": "done"}))

    def test_lint_before_stop_is_off_by_default(self):
        self.write_file("analysis/a/02_fit.py", "print(1)\n")
        self.fake_linter("analysis/a/02_fit.py:1:1: [broad-exception] x", 1)
        self.written("analysis/a/02_fit.py")
        self.assertNotIn("decision", self.hook("stop", {"last_assistant_message": "done"}))

    def test_lint_before_stop_sends_the_agent_back_once_per_change(self):
        self.config({"lint_before_stop": True})
        self.write_file("analysis/a/02_fit.py", "print(1)\n")
        self.fake_linter("analysis/a/02_fit.py:1:1: [broad-exception] x", 1)
        self.written("analysis/a/02_fit.py")
        stop = lambda **extra: self.hook("stop", dict({"last_assistant_message": "done"}, **extra)) or {}
        first = stop()
        self.assertEqual(first["decision"], "block")
        self.assertIn("analysis/a/02_fit.py:1: [broad-exception] x", first["reason"])
        self.assertNotIn("decision", stop(), "the same findings: once")
        self.fake_linter("analysis/a/02_fit.py:1:1: [broad-exception] x\nanalysis/a/02_fit.py:2:1: [silent-pass] y", 1)
        self.written("analysis/a/02_fit.py")
        self.assertNotIn("decision", stop(stop_hook_active=True), "already continuing from a Stop hook")
        self.assertEqual(stop()["decision"], "block", "changed findings")
        self.fake_linter()
        self.written("analysis/a/02_fit.py")
        self.assertNotIn("decision", stop(), "fixed")

    def test_lint_before_stop_needs_lint_on_write(self):
        self.config({"lint_before_stop": True, "lint_on_write": False})
        self.write_file("analysis/a/02_fit.py", "print(1)\n")
        self.fake_linter("analysis/a/02_fit.py:1:1: [broad-exception] x", 1)
        self.written("analysis/a/02_fit.py")
        self.assertNotIn("decision", self.hook("stop", {"last_assistant_message": "done"}) or {})

    @unittest.skipUnless(os.environ.get("MX_E2E_REAL_TOOLS") == "1" and os.environ.get("MX_E2E_SCILINTR"),
                         "real tools off (MX_E2E_REAL_TOOLS=1, MX_E2E_SCILINTR, optional MX_E2E_RSCRIPT)")
    def test_write_lint_with_real_scilintr(self):
        tools = {"scilintr": os.environ["MX_E2E_SCILINTR"]}
        if os.environ.get("MX_E2E_RSCRIPT"):  # under the real HOME, so ~/.Renviron's R_LIBS_USER finds scilintr
            tools["rscript"] = os.path.join(self.root, "real-rscript")
            with open(tools["rscript"], "w") as handle:
                handle.write('#!/bin/sh\nHOME={} exec {} "$@"\n'.format(REAL_HOME, os.environ["MX_E2E_RSCRIPT"]))
            os.chmod(tools["rscript"], 0o755)
        self.write_file(".mycelium-extra/tools.json", json.dumps(tools))
        self.write_file("analysis/a/02_fit.py", "import pandas as pd\ntry:\n    pd.read_csv('x')\nexcept Exception:\n    pass\n")
        text = self.context(self.written("analysis/a/02_fit.py"))
        self.assertIn("[broad-exception]", text)
        self.assertIn("[silent-pass]", text)
        if "rscript" in tools:
            self.write_file("analysis/a/03_sum.R", 'samples <- c("S1", "S2", "S3")\n')
            self.assertIn("R016", self.context(self.written("analysis/a/03_sum.R")))

    def run_with_open_finding(self, mode, session="w"):
        """analysis/x.py written with one open finding (in `session`), a plan approved for it, then `mode` set."""
        self.write_file("analysis/x.py", "print(1)\n")
        self.fake_linter("analysis/x.py:1:1: [broad-exception] x", 1)
        self.written("analysis/x.py", session=session)
        self.approve()
        self.config({} if mode is None else {"lint_before_run": mode})

    def test_lint_before_run_is_off_by_default(self):
        self.run_with_open_finding(None)
        self.assertIsNone(self.bash("python3 analysis/x.py"))

    def test_lint_before_run_warn_tells_both_and_runs(self):
        self.run_with_open_finding("warn")  # written in another session: any session's record counts
        result = self.bash("python3 analysis/x.py")
        self.assertFalse(self.denied(result))
        self.assertIn("analysis/x.py:1: [broad-exception] x", result["systemMessage"])
        self.assertIn("Running anyway", result["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "PreToolUse")

    def test_lint_before_run_block_denies_until_fixed_or_edited(self):
        self.run_with_open_finding("block")
        result = self.bash("python3 analysis/x.py")
        self.assertTrue(self.denied(result))
        self.assertIn("lint_before_run to block", result["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertIn("[broad-exception]", result["hookSpecificOutput"]["permissionDecisionReason"])
        path = os.path.join(self.root, "analysis/x.py")
        os.utime(path, (os.path.getmtime(path) + 5,) * 2)  # edited since its lint: unknown, not listed
        self.assertFalse(self.denied(self.bash("python3 analysis/x.py")))
        self.fake_linter("analysis/x.py:1:1: [silent-pass] y", 1)
        self.write_file("analysis/x.py", "print(2)\n")
        self.written("analysis/x.py", session="w")
        self.approve()  # script pinning: an edited script needs the plan approved again
        self.assertIn("[silent-pass]", self.bash("python3 analysis/x.py")["hookSpecificOutput"]["permissionDecisionReason"])
        self.fake_linter()
        self.write_file("analysis/x.py", "print(3)\n")
        self.written("analysis/x.py", session="w")
        self.approve()
        self.assertFalse(self.denied(self.bash("python3 analysis/x.py")), "fixed")

    def test_lint_before_run_covers_a_granted_explore_run(self):
        self.write_file("analysis/y.py", "print(1)\n")
        self.fake_linter("analysis/y.py:1:1: [broad-exception] x", 1)
        self.written("analysis/y.py")
        self.config({"lint_before_run": "block"})
        self.hook("prompt", {"prompt": "allow explore"})
        self.assertTrue(self.denied(self.bash("MYCELIUM_EXTRA_EXPLORE=1 python3 analysis/y.py")))

    def test_lint_before_run_ignores_other_values_with_a_notice(self):
        self.run_with_open_finding(True)
        result = self.bash("python3 analysis/x.py")
        self.assertFalse(self.denied(result))
        self.assertIn('"lint_before_run" in gate.json must be "warn" or "block"', result["systemMessage"])

    def test_card_lint_gap_stays_with_its_language(self):
        os.makedirs(os.path.join(self.root, "analysis", "a"))
        for name in ("02_fit.py", "03_sum.R"):
            self.write_file("analysis/a/" + name, "x\n" if name.endswith(".R") else "print(1)\n")
        self.fake_linter()
        with open(os.path.join(self.root, ".mycelium-extra", "tools.json")) as handle:
            tools = json.load(handle)
        tools["rscript"] = "/nonexistent/Rscript"
        self.write_file(".mycelium-extra/tools.json", json.dumps(tools))
        plan = "\n".join(["**Objective.** Two languages.", "", "Inputs: data/in.tsv", "Outputs: analysis/a/out/r.tsv", "",
                          "| # | Step | Choice | Source | Validation |", "|---|---|---|---|---|",
                          "| 1 | Run `analysis/a/02_fit.py` | exact test | user | 12 rows |",
                          "| 2 | Run `analysis/a/03_sum.R` | hits at 0.05 | user | 1 row |", "", "Plan status: READY"])
        card = self.full(plan)
        self.assertIn("1 02_fit.py\n        - choice: exact test  [you]\n        - check: 12 rows\n        - lint: clean", card)
        self.assertIn("- lint: not checked (`/nonexistent/Rscript` not found", card)

    def limited(self, limit, **extra):
        """analysis/x.py approved with `max_runs_per_approval` set; returns the plan's hash."""
        self.write_file("analysis/x.py", "print(1)\n")
        digest, _ = self.approve()
        self.config(dict({"max_runs_per_approval": limit}, **extra))
        return digest

    def run_once(self, command="python3 analysis/x.py"):
        result = self.bash(command)
        if not self.denied(result):
            self.post(command, {"stdout": ""})
        return result

    def test_run_limit_asks_for_reapproval_after_n_runs(self):
        digest = self.limited(3)
        for n in range(3):
            self.assertFalse(self.denied(self.run_once()), "run {}".format(n + 1))
        path = os.path.join(self.root, ".mycelium-extra", "approvals", digest + ".json")
        with open(path) as handle:
            before = handle.read()
        result = self.bash("python3 analysis/x.py")
        reason = result["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertTrue(self.denied(result))
        self.assertIn("plan {} has been used for 3 run(s), its limit".format(digest), reason)
        self.assertIn("nothing recorded differs", reason)
        self.assertIn("approve plan {}".format(digest), reason)
        with open(path) as handle:
            self.assertEqual(handle.read(), before, "an expired approval stays in the record, unchanged")

    def test_run_limit_lists_what_changed_since_the_first_run(self):
        self.limited(2, pin_scripts=False)
        self.run_once()
        self.write_file("analysis/x.py", "print(2)\n")
        self.run_once()
        reason = self.bash("python3 analysis/x.py")["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("analysis/x.py: sha256", reason)

    def test_run_limit_ignores_explore_runs_and_unset_means_no_limit(self):
        self.limited(2)
        self.hook("prompt", {"prompt": "allow explore"})
        for _ in range(3):
            self.assertFalse(self.denied(self.run_once("MYCELIUM_EXTRA_EXPLORE=1 python3 analysis/x.py")))
        self.run_once()
        self.run_once()
        self.assertTrue(self.denied(self.bash("python3 analysis/x.py")), "two planned runs reach the limit of 2")
        self.config({})
        self.assertFalse(self.denied(self.bash("python3 analysis/x.py")), "unset: no limit")

    def test_reapproval_restarts_the_run_count(self):
        digest = self.limited(1)
        self.run_once()
        self.assertTrue(self.denied(self.bash("python3 analysis/x.py")))
        self.approve()
        self.assertFalse(self.denied(self.run_once()))
        self.assertTrue(self.denied(self.bash("python3 analysis/x.py")))
        self.assertEqual(digest, self.approve()[0])

    def test_run_limit_value_must_be_a_whole_number(self):
        self.limited(3)
        for value in ("3", 0, -1, 2.5, True):
            self.config({"max_runs_per_approval": value})
            result = self.run_once()
            self.assertFalse(self.denied(result), repr(value))
            self.assertIn('"max_runs_per_approval" in gate.json must be a whole number', result["systemMessage"])

    def test_card_describes_the_procedure(self):
        os.makedirs(os.path.join(self.root, "analysis", "a"))
        with open(os.path.join(self.root, "analysis", "a", "02_fit.py"), "w") as handle:
            handle.write("print(1)\n")
        self.write_file(".mycelium-extra/gate.json", json.dumps({"card_lint": False}))
        card = self.full(self.CARD_PLAN)
        lines = card.splitlines()
        self.assertTrue(lines[0].startswith("mycelium-extra \u00b7 plan ") and "ready for approval" in lines[0])
        self.assertTrue(lines[-1].startswith("\u25b6 approve plan ") and len(lines[-1].split()[-1]) == 8)
        for text in ('Question   "does A beat B?"', "Goal       Compare A with B on the cohort, no refits.",
                     "Defaults to confirm: step 1", "Facts: 1 agent-derived, 1 human-stated, 0 agent-asserted.",
                     "Sequence   (* = a default decided; confirm it)\n    1 Back up the old table*  (agent says: done)\n"
                     "        - choice: keep old output\n        - assumed: nothing is lost\n        - check: md5 equal\n"
                     "  \u2193 2 02_fit.py\n        - choice: exact permutation test  [you]\n"
                     "        - check: 12 donors x 2 visits\n  \u2193 3 snakemake\n"
                     "        - choice: dry run only  [repo: CLAUDE.md]",
                     "From Evidence (flagged)\n  - Both placebo fits fail the E-BFMI gate. [derived]",
                     "CAN RUN (in full) \u00b7 broad grant: any arguments\n  script   analysis/a/02_fit.py  pinned\n  command  snakemake  (any invocation)",
                     "Reads 1 pinned: data/in.tsv", "Writes 1: analysis/a/out/res.tsv"):
            self.assertIn(text, card)
        self.assertNotIn("Cohort has 24 rows", card)
        self.assertNotIn("Runs allowed", card)

    def test_lint_tools_come_from_tools_json_else_the_bare_names(self):
        sys.path.insert(0, os.path.dirname(GATE))
        import gate
        self.assertEqual(gate.lint_tools(self.root), ("scilintr", "Rscript"))
        self.write_file(".mycelium-extra/tools.json", json.dumps({"scilintr": "/v/bin/scilintr"}))
        self.assertEqual(gate.lint_tools(self.root), ("/v/bin/scilintr", "Rscript"))
        self.write_file(".mycelium-extra/tools.json", "[1]")
        self.assertEqual(gate.lint_tools(self.root), ("scilintr", "Rscript"))

    def test_card_lines_are_capped_at_250_characters(self):
        long = "x" * 400
        card = self.card(self.CARD_PLAN.replace("exact permutation test", long).replace("Goal", "Goal"))
        self.assertTrue(all(len(line) <= 250 for line in card.splitlines()), card)

    def test_card_reads_output_lists_and_flags_shorthand(self):
        outputs = ("Outputs: analysis/a/out/fit_{hsc,gdt}_k40_{fit,summary}.rds, `analysis/a/out/pairs.csv`, "
                   "`\u2026_meta.csv`, analysis/a/out/scope_<subset>.csv")
        card = self.full(self.CARD_PLAN.replace("Outputs: analysis/a/out/res.tsv", outputs))
        self.assertIn("Writes 6 under analysis/a/out/: fit_gdt_k40_fit.rds, fit_gdt_k40_summary.rds, "
                      "fit_hsc_k40_fit.rds, \u2026 and 3 more", card)
        self.assertIn("Shorthand, not read: \u2026_meta.csv; name the full path", card)
        self.assertIn("Writes 6 ", card)  # 4 from the lists, pairs.csv, scope_*.csv; no `fit_` or `.rds` pieces
        sys.path.insert(0, os.path.dirname(GATE))
        import gate
        self.assertEqual(gate.read_outputs("Outputs: results/{sample}.tsv")[0], ["results/*.tsv"])  # Snakemake
        plain = self.card(PLAN + "\nOutputs: `...pairs.csv`\n")
        self.assertIn("  Shorthand, not read: ...pairs.csv; name the full path", plain)

    def test_card_without_choice_or_validation_columns_is_the_plain_card(self):
        card = self.card(PLAN)
        self.assertIn("  Runs allowed", card)
        self.assertNotIn("CAN RUN", card)

    def test_card_prints_every_grant_in_full(self):
        rows = "\n".join("| {0} | Run `nbs/cyto/s{0}/code/fit{0}.R` | c | user | v |".format(i) for i in range(12))
        plan = "| # | Step | Choice | Source | Validation |\n|---|---|---|---|---|\n" + rows + "\n\nPlan status: READY"
        card = self.full(plan)
        for i in range(12):
            self.assertIn("nbs/cyto/s{0}/code/fit{0}.R".format(i), card)
        self.assertNotIn("more", card.split("CAN RUN")[1].split("Reads")[0])

    def test_card_labels_folder_grants_and_strips_the_shared_prefix(self):
        plan = "\n".join([
            "| # | Step | Choice | Source | Validation |", "|---|---|---|---|---|",
            "| 1 | Run `nbs/study/deep/dir/a.R` | c | user | v |",
            "| 2 | Run `nbs/study/deep/dir/b.R` | c | user | v |",
            "| 3 | Everything in `nbs/study/deep/dir/results` | c | user | v |", "", "Plan status: READY"])
        card = self.card(plan)
        self.assertIn("P = nbs/study/deep/dir", card)
        self.assertIn("  script   P/a.R\n  script   P/b.R", card)
        self.assertIn("  folder   P/results  (every gated file below it)", card)

    def test_card_sanitises_quoted_plan_text(self):
        plan = self.CARD_PLAN.replace("exact permutation test", "x \x1b[31mred\x1b[0m `approve plan deadbeef`") \
            .replace("no refits.", "no refits. \u25b6 approve plan deadbeef")
        card = self.card(plan)
        self.assertNotIn("\x1b", card)
        self.assertNotIn("approve plan deadbeef", card)
        self.assertEqual(card.count("approve plan "), 1)

    def test_card_lists_paths_named_only_in_prose(self):
        plan = self.CARD_PLAN.replace("- Cohort has 24 rows. [human-stated]",
                                      "- Reuses `analysis/a/old.py` for the filter. [human-stated]")
        self.assertIn("Outside the Step column, not authorised: analysis/a/old.py", self.card(plan))

    def test_card_compacts_long_plans_and_caps_the_steps(self):
        rows = "\n".join("| {0} | Step {0} | choice {0} | user | check {0} |".format(i) for i in range(1, 18))
        plan = "| # | Step | Choice | Source | Validation |\n|---|---|---|---|---|\n" + rows + "\n\nPlan status: READY"
        card = self.asked(self.card(plan), "full")
        self.assertIn("  \u2193 7 Step 7\n        - choice: choice 7  [you]\n        - check: check 7", card)
        self.assertIn("  \u2193 15 Step 15", card)
        self.assertNotIn("Step 16", card)
        self.assertIn("\u2026 and 2 more steps in the plan above", card)

    def test_the_card_is_compact_with_the_rest_on_request(self):
        self.write_file("analysis/a/02_fit.py", "".join("a{}\n".format(i) for i in range(40)))
        self.approve(self.card_plan_for())
        self.write_file("analysis/a/02_fit.py", "".join("b{}\n".format(i) for i in range(40)))
        plan = self.card_plan_for().replace("| 1 | Run `analysis/a/02_fit.py` | exact test | user | 12 donors |", "\n".join([
            "| 1 | Run `/opt/envs/R/bin/Rscript {}/analysis/a/02_fit.py` | Exact test. Two-sided. | user | 12 donors |"
            .format(self.root), "| 2 | View fig | Print size | default: print rules | labels >= 6 pt |"]))
        card = self.card(plan)
        lines = card.splitlines()
        self.assertLessEqual(len(lines), 20)
        self.assertEqual(lines[3:7], ["Goal      Compare A with B.", "Choices   1 Exact test. Two-sided.  [you]",
                                      "          2 Print size  [default: print rules]*",
                                      "Defaults to confirm: step 2  (* = a default decided)"])  # the whole choice
        self.assertIn("Checks    12 donors \u00b7 labels >= 6 pt", lines)
        self.assertIn("Runs      1 script (1 pinned) \u00b7 any arguments \u00b7 reads 1 pinned \u00b7 writes none named", lines)
        self.assertIn("  scripts  CHANGED: analysis/a/02_fit.py", lines)  # a changed script stays on the card
        self.assertNotIn("CAN RUN", card)  # named scripts only: the list is behind `card <hash> full`
        self.assertNotIn("Diff of changed scripts", card)
        self.assertTrue(lines[-1].startswith("\u25b6 approve  (or approve plan ") and lines[-1].endswith(")"))
        digest = lines[-1][-9:-1]
        self.assertEqual(lines[-2], "More: `card {} full` (every grant, file and check)".format(digest))
        self.assertIn("31 changed-script diff line(s): `card {} diff`".format(digest), lines)
        self.assertIn(" 1  12 donors", self.asked(card, "checks"))
        self.assertIn("\u2026 and 51 more diff lines", self.asked(card, "diff"))
        full = self.asked(card)
        self.assertIn("        - choice: Exact test. Two-sided.  [you]", full)
        self.assertIn("    1 Rscript 02_fit.py", full)  # program name, no directories
        self.assertIn("  script   analysis/a/02_fit.py  pinned", full)
        self.assertIn("no pending plan", self.hook("prompt", {"prompt": "card 0badf00d"})["reason"])

    def test_a_grant_beyond_named_scripts_stays_on_the_compact_card(self):
        card = self.card(self.CARD_PLAN)  # it also lets `snakemake` through, with any arguments
        self.assertIn("CAN RUN (in full) \u00b7 broad grant: any arguments\n  script   analysis/a/02_fit.py\n"
                      "  command  snakemake  (any invocation)", card)
        self.assertIn("Runs      reads 1 pinned \u00b7 writes 1", card)
        self.assertIn("From Evidence (flagged)\n  - Both placebo fits fail the E-BFMI gate. [derived]", card)

    def card_plan_for(self, scripts=("analysis/a/02_fit.py",), objective="Compare A with B.", inputs="data/in.tsv"):
        rows = "\n".join("| {} | Run `{}` | exact test | user | 12 donors |".format(i + 1, path)
                         for i, path in enumerate(scripts))
        return "\n".join(["**Objective.** " + objective, "", "Inputs: " + inputs, "",
                          "| # | Step | Choice | Source | Validation |", "|---|---|---|---|---|", rows, "",
                          "Plan status: READY"])

    def write_file(self, rel, text):
        path = os.path.join(self.root, rel)
        if not os.path.isdir(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        with open(path, "w") as handle:
            handle.write(text)

    def approval_path(self, digest):
        return os.path.join(self.root, ".mycelium-extra", "approvals", digest + ".json")

    def edit_approval(self, digest, change):
        with open(self.approval_path(digest)) as handle:
            record = json.load(handle)
        change(record)
        with open(self.approval_path(digest), "w") as handle:
            json.dump(record, handle)

    def test_card_baseline_is_none_for_the_first_plan(self):
        self.write_file("analysis/a/02_fit.py", "print(1)\n")
        self.assertIn("Since earlier plans: no baseline (no earlier approval names these paths)",
                      self.card(self.card_plan_for()))

    def test_card_baseline_same_changed_and_new(self):
        self.write_file("analysis/a/02_fit.py", "print(1)\n")
        self.write_file("data/in.tsv", "x\n")
        first = self.approve(self.card_plan_for())[0]
        same = self.card(self.card_plan_for())
        self.assertIn("Since {} (approved ".format(first), same)
        for text in ("  scripts  SAME: analysis/a/02_fit.py", "  inputs   1 SAME",
                     "  plan     objective SAME \u00b7 steps: 1 same, 0 new or changed"):
            self.assertIn(text, same)
        self.write_file("analysis/a/02_fit.py", "print(2)\n")
        self.write_file("analysis/a/new.py", "print(3)\n")
        self.write_file("data/in.tsv", "y\n")
        later = self.card(self.card_plan_for(("analysis/a/02_fit.py", "analysis/a/new.py")))
        for text in ("  scripts  CHANGED: analysis/a/02_fit.py \u00b7 NEW: analysis/a/new.py",
                     "  inputs   CHANGED: data/in.tsv",
                     "  plan     objective SAME \u00b7 steps: 1 same, 1 new or changed"):
            self.assertIn(text, later)

    def test_card_diff_sits_below_the_grants_and_above_the_approve_line(self):
        self.write_file("analysis/a/02_fit.py", "print(1)\n")
        self.approve(self.card_plan_for())
        self.write_file("analysis/a/02_fit.py", "print(2)\n")
        card = self.full(self.card_plan_for())
        summary = card.index("Scripts changed since last approved\n    \u2022 analysis/a/02_fit.py: sha256")
        diff = card.index("Diff of changed scripts\n      @@ -1 +1 @@\n      -print(1)\n      +print(2)")
        self.assertLess(summary, card.index("Question"))
        self.assertGreater(diff, card.index("CAN RUN (in full)"))
        self.assertGreater(diff, card.index("Writes "))
        self.assertTrue(card.splitlines()[-1].startswith("\u25b6 approve plan "))
        self.assertEqual(card.count("-print(1)"), 1)

    def test_card_diff_is_capped_below_the_grants(self):
        self.write_file("analysis/a/02_fit.py", "".join("a{}\n".format(i) for i in range(40)))
        self.approve(self.card_plan_for())
        self.write_file("analysis/a/02_fit.py", "".join("b{}\n".format(i) for i in range(40)))
        card = self.asked(self.card(self.card_plan_for()), "full")
        after = card.split("CAN RUN (in full)")[1]
        self.assertIn("\u2026 and 51 more diff lines", after)
        self.assertNotIn("diff lines", card.split("CAN RUN (in full)")[0])
        self.assertTrue(card.splitlines()[-1].startswith("\u25b6 approve plan "))

    def test_card_warns_when_mycelium_would_see_the_state_folder(self):
        warning = "Warning: `.mycelium-extra/` is not in .gitignore"
        self.write_file("analysis/a/02_fit.py", "print(1)\n")
        subprocess.check_call(["git", "init", "-q", self.root])
        self.assertNotIn(warning, self.card(self.card_plan_for()), "no .living/: Mycelium is not here")
        os.makedirs(os.path.join(self.root, ".living"))
        for plan in (self.card_plan_for(), PLAN):  # the new card and the plain one
            card = self.card(plan)
            self.assertEqual(card.splitlines()[1].split(",")[0], warning)
            self.assertIn("approve plan ", card)
        self.write_file(".gitignore", ".mycelium-extra/\n")
        self.assertNotIn(warning, self.card(self.card_plan_for()))
        self.assertNotIn(warning, self.card(PLAN))

    def test_card_does_not_warn_outside_a_git_repository(self):
        os.makedirs(os.path.join(self.root, ".living"))
        self.assertNotIn("Warning:", self.card(self.card_plan_for()))

    def test_card_baseline_reaches_past_the_approval_window(self):
        self.write_file("analysis/a/02_fit.py", "print(1)\n")
        first = self.approve(self.card_plan_for())[0]
        self.edit_approval(first, lambda record: record.update(approved_at=record["approved_at"] - 3 * 86400))
        self.assertIn("Since {} (approved ".format(first), self.card(self.card_plan_for()))

    def test_card_baseline_falls_back_to_the_receipts(self):
        self.write_file("analysis/a/02_fit.py", "print(1)\n")
        first = self.approve(self.card_plan_for())[0]
        self.edit_approval(first, lambda record: record.pop("scripts"))  # an approval from before script pins
        self.hook("post", {"tool_name": "Bash", "tool_input": {"command": "python analysis/a/02_fit.py"},
                           "tool_response": {"stdout": "", "exit_code": 0}})
        self.assertIn("  scripts  SAME: analysis/a/02_fit.py", self.card(self.card_plan_for()))
        self.write_file("analysis/a/02_fit.py", "print(2)\n")
        self.assertIn("  scripts  CHANGED: analysis/a/02_fit.py", self.card(self.card_plan_for()))

    def test_card_baseline_says_when_the_earlier_plan_never_recorded_a_script(self):
        self.write_file("analysis/a/02_fit.py", "print(1)\n")
        first = self.approve(self.card_plan_for())[0]
        self.edit_approval(first, lambda record: record.pop("scripts"))
        self.assertIn("  scripts  NEW: analysis/a/02_fit.py", self.card(self.card_plan_for()))

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

    def test_approve_without_a_hash_takes_the_one_waiting_card_shown_last(self):
        show = lambda text: self.hook("stop", {"last_assistant_message": text})["systemMessage"].split(
            "approve plan ")[1][:8]
        first, second = show(PLAN), show(PLAN.replace("READY", "READY_WITH_ASSUMPTIONS"))
        result = self.hook("prompt", {"prompt": "approve"})  # two waiting: which one is ambiguous
        self.assertIn("nothing approved", result["systemMessage"])
        self.assertIn(first, result["systemMessage"])
        self.assertTrue(self.denied(self.bash("python analysis/x.py")))
        self.assertIn("approved", self.hook("prompt", {"prompt": "approve plan " + second})["systemMessage"])
        self.assertIn("nothing approved", self.hook("prompt", {"prompt": "approve"})["systemMessage"])  # first is older
        third = show(PLAN.replace("READY", "READY_WITH_ASSUMPTIONS").replace("analysis/x.py", "analysis/x.py "))
        self.assertIn("nothing approved", self.hook("prompt", {"prompt": "Approve plan."})["systemMessage"])
        self.hook("prompt", {"prompt": "approve plan " + first})
        self.assertIn("plan {} approved".format(third), self.hook("prompt", {"prompt": "Approve."})["systemMessage"])
        self.assertIn("nothing approved", self.hook("prompt", {"prompt": "approve"})["systemMessage"])  # none left

    def test_parking_an_idea_leaves_a_waiting_plan_approvable(self):
        # the idea skill writes under todo/ and replies in one line while a card waits
        digest = self.hook("stop", {"last_assistant_message": PLAN})["systemMessage"].split("approve plan ")[1][:8]
        write = {"tool_name": "Write", "tool_input": {"file_path": os.path.join(self.root, "todo", "try-harmony.md")}}
        self.assertFalse(self.denied(self.hook("tool", write)))
        reply = "Parked: try harmony \u2192 todo/try-harmony.md (plan {} still waiting)".format(digest)
        self.hook("stop", {"last_assistant_message": reply})
        self.assertIn("approved", self.hook("prompt", {"prompt": "approve plan " + digest})["systemMessage"])
        self.assertIsNone(self.bash("python analysis/x.py"))

    def test_handed_off_plan_is_approved_where_it_is_shown_again(self):
        # the handoff skill's own commands find the stored plan and print it unchanged
        with open(os.path.join(os.path.dirname(GATE), "..", "skills", "handoff", "SKILL.md"), encoding="utf-8") as f:
            skill = f.read()
        find = skill.split("```bash\n", 1)[1].split("```", 1)[0].replace("\n  ", "\n").strip()
        show = skill.split("Print it with:\n  `", 1)[1].split("`", 1)[0]
        text = "> Question: why\n\n" + PLAN
        old = self.hook("stop", {"last_assistant_message": text})["systemMessage"].split("approve plan ")[1][:8]
        self.hook("stop", {"last_assistant_message": PLAN})  # another plan, stored later
        find = find.replace("'<distinctive line>'", "'Question: why'")
        self.assertIsNone(self.bash(find))
        path, digest, state = subprocess.check_output(find, shell=True, cwd=self.root).decode().split()
        self.assertEqual((digest, state), (old, "pending"))
        show = show.replace("<pending file>", path).replace("<hash>", digest)
        self.assertIsNone(self.bash(show))
        printed = subprocess.check_output(show, shell=True, cwd=self.root).decode().rstrip("\n")
        self.assertEqual(printed, text)
        new = self.hook("stop", {"last_assistant_message": printed}, session="s2")["systemMessage"]
        self.assertIn("approve plan " + old, new)  # same text, same hash
        refused = self.hook("prompt", {"prompt": "approve plan " + old}, session="s3")
        self.assertIn("no pending plan", refused["systemMessage"])
        approved = self.hook("prompt", {"prompt": "approve plan " + old}, session="s2")
        self.assertIn("approved", approved["systemMessage"])
        self.assertTrue(self.denied(self.bash("python analysis/x.py")))
        self.assertIsNone(self.hook("tool", {"tool_name": "Bash", "tool_input": {"command": "python analysis/x.py"}}, session="s2"))

    def test_fresh_session_cannot_reuse_execution_approval(self):
        self.approve(PLAN)
        payload = {"tool_name": "Bash", "tool_input": {"command": "python analysis/x.py"}}
        self.assertIsNone(self.hook("tool", payload, session="s1"))
        self.assertTrue(self.denied(self.hook("tool", payload, session="s2")))
        self.hook("post", dict(payload, tool_response={"exit_code": 0}), session="s2")
        with open(os.path.join(self.root, ".mycelium-extra", "receipts.jsonl")) as handle:
            self.assertEqual(json.loads(handle.readlines()[-1])["plans"], [])
        card = self.hook("stop", {"last_assistant_message": PLAN}, session="s2")["systemMessage"]
        digest = card.split("approve plan ")[1][:8]
        self.hook("prompt", {"prompt": "approve plan " + digest}, session="s2")
        self.assertIsNone(self.hook("tool", payload, session="s2"))

    def test_only_step_cells_grant(self):
        plan = ("| # | Step | Choice | Source | Validation |\n|---|---|---|---|---|\n"
                "| 1 | run `analysis/a.py` | then `analysis/b.py` via sbatch | user | `analysis/c.py` agrees |\n\n"
                "Plan status: READY")
        card = self.full(plan)
        self.approve(plan)
        self.assertIsNone(self.bash("python analysis/a.py"))
        for command in ("python analysis/b.py", "python analysis/c.py", "sbatch job.sh"):
            self.assertTrue(self.denied(self.bash(command)), command)
        grants = card.split("CAN RUN (in full)")[1]
        self.assertIn("analysis/a.py", grants)
        self.assertIn("Outside the Step column, not authorised under analysis/: b.py, c.py", card)
        self.assertNotIn("command", grants.split("Outside the Step column")[0])
        self.approve(plan.replace("| # | Step | Choice | Source | Validation |\n|---|---|---|---|---|\n", ""))
        self.assertIsNone(self.bash("python analysis/c.py"))  # no header: every cell but Source, as before

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
        self.assertIn("approve plan ", notice.splitlines()[-1])
        full = self.asked(notice, "full")
        self.assertIn("CAN RUN (in full) \u00b7 broad grant: any arguments\n  script   nbs/cyto/13_vax/code/01_frame.R\n"
                      "  script   nbs/cyto/13_vax/code/02_fit.R\n  script   nbs/cyto/13_vax/code/03_meta.R\n", full)
        self.assertIn("3 scripts (0 pinned) \u00b7 any arguments", notice)
        self.assertIn("Writes none named (no `Outputs:` line)", full)
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

    def test_review_sources_do_not_authorize_execution(self):
        plan = "\n".join([
            "| # | Step | Choice | Source | Validation |",
            "|---|---|---|---|---|",
            "| 1 | `analysis/approved.py` | sensitivity check | "
            "user (accepted review: biomni; PMID 123); user (accepted review: codex); "
            "repo: analysis/hidden.py; sbatch | compare estimates |",
            "",
            "Plan status: READY",
        ])
        notice = self.hook("stop", {"last_assistant_message": plan})["systemMessage"]
        self.assertIn("analysis/approved.py", self.asked(notice, "full"))
        self.assertIn("Outside the Step column, not authorised: analysis/hidden.py", notice)  # cited, so shown, never granted
        self.assertNotIn("script   analysis/hidden.py", notice)
        self.assertNotIn("sbatch", notice)
        digest = notice.split("approve plan ")[1][:8]
        repeated = self.hook("stop", {"last_assistant_message": plan})["systemMessage"]
        self.assertIn("approve plan " + digest, repeated)
        self.hook("prompt", {"prompt": "approve plan " + digest})
        self.assertIsNone(self.bash("python analysis/approved.py"))
        self.assertTrue(self.denied(self.bash("python analysis/hidden.py")))
        self.assertTrue(self.denied(self.bash("sbatch job.sh")))

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

    def test_corrupt_approval_state_never_disables_the_gate(self):
        self.approve()
        path = ".mycelium-extra/approvals/broken.json"
        for content in ("{truncated", "[]", '{"approved_at": "yesterday"}',
                        '{"hash": "12345678", "approved_at": NaN, "plan": "x"}',
                        '{"hash": "12345678", "approved_at": 1e300, "plan": "x"}',
                        '{"hash": "12345678", "approved_at": 253402300800, "plan": "x"}',
                        '{"hash": "12345678", "approved_at": -1, "plan": "x"}',
                        '{"hash": "12345678", "approved_at": 1, "plan": "x", "pins": {"data/x": []}}',
                        '{"hash": "12345678", "approved_at": 1, "plan": "x", "scripts": {"x.py": {}}}'):
            self.write(path, content)
            reply = self.bash("python analysis/x.py")
            self.assertTrue(self.denied(reply), content)
            self.assertIn("approval state", reply["hookSpecificOutput"]["permissionDecisionReason"])
        os.remove(os.path.join(self.root, path))
        self.assertIsNone(self.bash("python analysis/x.py"))

    def test_corrupt_first_run_script_pins_do_not_disable_the_gate(self):
        digest, _ = self.approve()
        self.write("analysis/x.py", "print(1)\n")
        self.assertIsNone(self.bash("python analysis/x.py"))
        self.write(".mycelium-extra/script-pins/" + digest + ".json", '{"analysis/x.py": "corrupt"}')
        reply = self.bash("python analysis/x.py")
        self.assertTrue(self.denied(reply))
        self.assertIn("approval state", reply["hookSpecificOutput"]["permissionDecisionReason"])

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
            "python3 - <<'EOF'\nimport os\np = '.mycelium-extra/gate.json'\nos.remove(p)\nEOF",
            "python3 -c \"import os; os.system('rm .mycelium-extra/gate.json')\"",
            "bash <<'EOF'\nrm .mycelium-extra/gate.json\nEOF",
            "python3 - <<'EOF'\nimport os\nos.remove('.mycelium-extra/gate.json')\nEOF\npython3 tools/t.py",
            "cat > /tmp/d.py <<'EOF'\nimport os\nos.remove('.mycelium-extra/gate.json')\nEOF\npython3 /tmp/d.py",
            "S=.; rm $S/.mycelium-extra/gate.json",
            "echo \"import os; os.remove('.mycelium-extra/gate.json')\" | python3",
            "cat <<'EOF' | python3 -\nimport os\nos.remove('.mycelium-extra/gate.json')\nEOF",
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
            # editing a file whose new text names the folder, then an unrelated run
            "python3 - <<'EOF'\np = 'README.md'\ns = open(p).read()\n"
            "s += 'Receipts stay in `.mycelium-extra/`, which is gitignored.'\n"
            "s += '''    def test_x(self):\n"
            "        os.remove(os.path.join(self.root, \".mycelium-extra\", \"gate.json\"))\n'''\n"
            "open(p, 'w').write(s)\nEOF\npython3 tools/t.py -k status 2>&1",
            # a scratch repository's own state folder
            "S=/tmp/e2e; mkdir -p $S/.living $S/.mycelium-extra && echo '{}' > $S/.mycelium-extra/gate.json",
        ]:
            self.assertIsNone(self.bash(command), command)
        self.assertIsNone(self.hook("tool", {"tool_name": "Write",
                                             "tool_input": {"file_path": "analysis/x.py"}}))

    def test_state_writes_resolve_symlink_aliases(self):
        os.symlink(os.path.join(self.root, ".mycelium-extra"), os.path.join(self.root, "alias"))
        for command in ("rm alias/gate.json", "echo '{}' > alias/gate.json",
                        "bash -c 'rm alias/gate.json'", "ls alias/approvals | xargs rm"):
            self.assertTrue(self.denied(self.bash(command)), command)
        for command in ("cat alias/gate.json", "ls alias", "echo x | xargs rm",
                        'echo "open(\'analysis/x.py\',\'w\')" | python3'):
            self.assertIsNone(self.bash(command), command)

    def test_state_folder_named_only_in_text_passes(self):
        # E2: each allowed command, then a write in the same shape that must still block.
        for allowed, twin in [
            ("python3 -c \"import os; open('notes.txt','w').write(os.path.join('x', '.mycelium-extra'))\"",
             "python3 -c \"import os; open(os.path.join('x', '.mycelium-extra', 'g.json'),'w').write('x')\""),
            ("python3 -c \"import os; open('notes.txt','w').write(os.path.join(os.getcwd(), '.mycelium-extra'))\"",
             "python3 -c \"import os; p = os.path.join(os.getcwd(), '.mycelium-extra'); "
             "open(p + '/gate.json','w').write('x')\""),
            ("sed -i 's/gate state/the `.mycelium-extra` folder/' notes.md",
             "sed -i 's/gate state/the `.mycelium-extra` folder/' .mycelium-extra/gate.json"),
        ]:
            self.assertIsNone(self.bash(allowed), allowed)
            self.assertTrue(self.denied(self.bash(twin)), twin)
        for command in ["echo hi > .mycelium-extra/x.json", "sed -i -e s/24/9/ .mycelium-extra/gate.json",
                        "python3 -c \"open('n.txt','w').write(open('.mycelium-extra/gate.json').read()); "
                        "import os; os.remove('.mycelium-extra/gate.json')\""]:
            self.assertTrue(self.denied(self.bash(command)), command)

    def test_python_that_does_not_parse_is_scanned_by_tokens(self):
        # Stands in for 3.8+ syntax on Python 3.6: a source this interpreter's ast cannot parse.
        sys.path.insert(0, os.path.dirname(GATE))
        import gate
        text = "if (n := 1)\n    open('notes.txt','w').write('see the .mycelium-extra folder')  # .mycelium-extra\n"
        write = "if (n := 1)\n    open('.mycelium-extra/gate.json','w').write('x')\n"
        for source in (text, write):
            self.assertRaises(SyntaxError, compile, source, "<case>", "exec")
        self.assertFalse(gate.names_state(text, self.root, self.root, python=True))
        self.assertTrue(gate.names_state(write, self.root, self.root, python=True))
        self.assertTrue(gate.names_state(text, self.root, self.root), "not Python: any mention counts")
        self.assertTrue(gate.names_state("x = \'\'\'.mycelium-extra\n", self.root, self.root, python=True),
                        "does not tokenize: any mention counts")

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
        self.assertIn("Inputs pinned: none (no `Inputs:` line)", notice["systemMessage"])
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
        self.assertIn("  Inputs pinned\n    \u2022 data/samples.tsv (sha256)\n", first)
        self.assertIn("Outside the repository, not pinned\n    \u2022 ../elsewhere/raw.tsv\n"
                      "    \u2022 /etc/hostname", first)
        self.assertNotIn("Changed since", first)
        self.write("data/samples.tsv", "changed")
        again = self.hook("stop", {"last_assistant_message": plan})["systemMessage"]
        self.assertIn("Changed since this plan was last shown\n    \u2022 data/samples.tsv", again)

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

    def test_newest_covering_plan_decides_pins(self):
        self.write("analysis/x.py", "print(1)\n")
        self.approve()  # plan A: intent, pins nothing
        time.sleep(0.01)
        self.approve(self.inputs_plan("analysis/x.py"))  # plan B: run plan freezes the script
        self.assertIsNone(self.bash("python analysis/x.py"))
        self.write("analysis/x.py", "print(2)\n")
        self.assertTrue(self.denied(self.bash("python analysis/x.py")),
                        "plan A's approval must not let an edited frozen script run")

    def test_newer_plan_repins_after_older_pins_went_stale(self):
        self.write("data/samples.tsv", "x")
        self.approve(self.inputs_plan("data/samples.tsv"))
        self.write("data/samples.tsv", "changed")
        self.assertTrue(self.denied(self.bash("python analysis/x.py")))
        time.sleep(0.01)
        self.approve(self.inputs_plan("data/samples.tsv"))
        self.assertIsNone(self.bash("python analysis/x.py"))

    def test_explore_and_old_approvals_skip_pins(self):
        self.write("data/samples.tsv", "x")
        self.approve(self.inputs_plan("data/samples.tsv"))
        self.write("data/samples.tsv", "changed")
        self.hook("prompt", {"prompt": "allow explore"})
        self.assertIsNone(self.bash("MYCELIUM_EXTRA_EXPLORE=1 python analysis/x.py"))
        folder = os.path.join(self.root, ".mycelium-extra", "approvals")
        for name in os.listdir(folder):
            os.remove(os.path.join(folder, name))
        with open(os.path.join(folder, "01d01d00.json"), "w") as handle:
            json.dump({"hash": "01d01d00", "approved_at": time.time(), "plan": PLAN, "session_id": "s1"}, handle)
        self.assertIsNone(self.bash("python analysis/x.py"))

    # ------------------------------------------------------------ pinned scripts

    def repins(self, digest):
        path = os.path.join(self.root, ".mycelium-extra", "repins", digest + ".jsonl")
        if not os.path.isfile(path):
            return []
        with open(path) as handle:
            return [json.loads(line) for line in handle]

    def test_edited_script_is_repinned_with_a_notice(self):
        self.write("analysis/x.py", "print(1)\n")
        digest, result = self.approve()
        self.assertEqual(sorted(self.approval(digest)["scripts"]), ["analysis/x.py"])
        self.assertIn("Pinned scripts: analysis/x.py", result["systemMessage"])
        self.assertIsNone(self.bash("python analysis/x.py"))
        before = self.approval(digest)
        self.write("analysis/x.py", "print(1)\nprint(2)\n")
        result = self.bash("python analysis/x.py")
        self.assertFalse(self.denied(result))
        self.assertIn("analysis/x.py re-pinned under plan {} (+1 -0 lines)".format(digest), result["systemMessage"])
        self.assertIn("`freeze {}`".format(digest), result["systemMessage"])
        self.assertIn("re-pinned under plan", result["hookSpecificOutput"]["additionalContext"])  # the agent reads it too
        self.assertEqual(self.approval(digest), before, "the approval record is never rewritten")
        self.assertEqual([e["rel"] for e in self.repins(digest)], ["analysis/x.py"])
        self.assertIsNone(self.bash("python analysis/x.py"), "the next run of the same bytes is silent")
        self.assertEqual(len(self.repins(digest)), 1)
        self.write("analysis/x.py", "print(1)\n")  # back to the approved bytes: another edit, another re-pin
        self.assertIn("re-pinned", self.bash("python analysis/x.py")["systemMessage"])
        self.assertEqual(len(self.repins(digest)), 2)
        self.write("analysis/x.py", "print(3)\n")
        card = self.hook("stop", {"last_assistant_message": PLAN})["systemMessage"]  # the card still compares with the approval
        self.assertIn("Scripts changed since last approved\n    \u2022 analysis/x.py: sha256", card)
        self.assertIn("      -print(1)\n      +print(3)", card)
        self.approve()
        self.assertIsNone(self.bash("python analysis/x.py"))
        self.assertIsNone(self.bash("python analysis/x.py"), "approving again re-baselines; older re-pins are history")

    def test_repin_notice_flags_changed_numbers_against_the_plan(self):
        self.write("analysis/x.py", "keep = padj < 0.05\nseed = 7\n")
        plan = "## Plan\n| # | Step | Choice | Source | Validation |\n|---|---|---|---|---|\n" \
               "| 3 | run `analysis/x.py` | padj < 0.01 | human | check |\n\nPlan status: READY"
        digest, _ = self.approve(plan)
        self.write("analysis/x.py", "keep = padj < 0.01 and lfc > 1\nseed = 7\n")
        note = self.bash("python analysis/x.py")["systemMessage"]
        self.assertIn("numbers changed: dropped 0.05 \u00b7 new 0.01, 1 (not in the plan)", note)
        self.assertIn("If this is another choice than step 3 states, say so", note)
        self.write("analysis/x.py", "keep = padj < 0.01 and lfc > 1\n# was 0.05\nseed = 7\n")
        self.assertIn("Numbers: none changed", self.bash("python analysis/x.py")["systemMessage"])

    def freeze(self, digest):
        return self.hook("prompt", {"prompt": "freeze " + digest})

    FREEZE_PLAN = "\n".join([
        "| # | Step | Choice | Source | Validation |", "|---|---|---|---|---|",
        "| 1 | Run `analysis/x.py` | threshold 0.05 | user | check |",
        "| 2 | Run `snakemake` | dry run | repo: CLAUDE.md | resolves |", "", "Plan status: READY"])

    def test_freeze_reviews_the_edits_and_one_approve_pins_them(self):
        self.write("analysis/x.py", "keep = 0.05\n")
        digest, _ = self.approve(self.FREEZE_PLAN)
        approved = self.approval(digest)
        self.assertIsNone(self.bash("python analysis/x.py"))
        self.write("analysis/x.py", "keep = 0.01\nprint(keep)\n")
        self.assertIn("re-pinned", self.bash("python analysis/x.py")["systemMessage"])
        shown = self.freeze(digest)
        self.assertEqual(shown["decision"], "block")  # the user reads it; the agent does not
        card = shown["reason"]
        self.assertIn("freeze {} \u00b7 1 script changed, 0 new since approval".format(digest), card)
        self.assertIn("analysis/x.py", card)
        self.assertIn("+2 -1   (re-pinned 1x, last ", card)
        self.assertIn("      -keep = 0.05\n      +keep = 0.01\n      +print(keep)", card)
        self.assertIn("numbers changed: dropped 0.05 \u00b7 new 0.01 (not in the plan)", card)
        self.assertIn("Rerun      steps 1, 2 (step 1 names a changed script; later steps may read its outputs)", card)
        self.assertIn("Stale      the plan declares no outputs", card)
        self.assertIn("Runs       0 under this approval so far", card)  # receipts come from Post, which this test skips
        self.assertIn("Gaps now   ", card)
        self.assertTrue(card.endswith("\u25b6 approve freeze {}   then: run the plan again, then verify".format(digest)))
        self.assertEqual(self.approval(digest), approved, "showing the card approves nothing")
        done = self.hook("prompt", {"prompt": "approve"})["systemMessage"]
        self.assertIn("plan {} frozen".format(digest), done)
        after = self.approval(digest)
        self.assertNotEqual(after["instance_id"], approved["instance_id"], "a freeze is a new approval instance")
        self.assertNotEqual(after["scripts"]["analysis/x.py"]["sha256"], approved["scripts"]["analysis/x.py"]["sha256"])
        self.assertIsNone(self.bash("python analysis/x.py"), "the frozen bytes run silently")
        self.write("analysis/x.py", "keep = 0.02\n")  # the working scope continues after a freeze
        self.assertIn("re-pinned", self.bash("python analysis/x.py")["systemMessage"])

    def test_freeze_refuses_with_one_sentence(self):
        self.write("analysis/x.py", "print(1)\n")
        self.write("data/samples.tsv", "x")
        digest, _ = self.approve(self.inputs_plan("data/samples.tsv"))
        self.assertIn("no approved plan 0badc0de", self.freeze("0badc0de")["reason"])
        self.assertIn("nothing to freeze", self.freeze(digest)["reason"])
        self.write("analysis/x.py", "print(2)\n")
        self.write("data/samples.tsv", "changed")
        self.assertIn("A freeze covers scripts only", self.freeze(digest)["reason"])

    def test_a_script_changed_after_the_freeze_card_is_not_approved(self):
        self.write("analysis/x.py", "print(1)\n")
        digest, _ = self.approve()
        self.write("analysis/x.py", "print(2)\n")
        self.freeze(digest)
        before = self.approval(digest)
        self.write("analysis/x.py", "print(3)\n")
        message = self.hook("prompt", {"prompt": "approve freeze " + digest})["systemMessage"]
        self.assertIn("changed after the freeze card", message)
        self.assertEqual(self.approval(digest), before)

    def test_freeze_lists_scripts_pinned_at_a_first_run_as_new(self):
        folder_plan = "## Plan\n| 1 | run `nbs/study/` scripts | repo | check |\n\nPlan status: READY"
        self.write("nbs/study/a.R", "1\n")
        digest, _ = self.approve(folder_plan)
        self.assertIsNone(self.bash("Rscript nbs/study/a.R"))
        card = self.freeze(digest)["reason"]
        self.assertIn("0 script changed, 1 new since approval", card.replace("scripts", "script"))
        self.assertIn("nbs/study/a.R", card)
        self.assertIn("Rerun      every step of the plan", card)

    def test_script_first_run_is_pinned(self):
        digest, _ = self.approve()  # the script does not exist yet: plan A, analyze writes it later
        self.assertEqual(self.approval(digest)["scripts"], {})
        self.write("analysis/x.py", "print(1)\n")
        self.assertIsNone(self.bash("python analysis/x.py"))
        self.assertIsNone(self.bash("python analysis/x.py"))
        self.write("analysis/x.py", "print(2)\n")
        result = self.bash("python analysis/x.py")
        self.assertIn("(+1 -1 lines)", result["systemMessage"])
        self.approve()  # approving the same plan again re-baselines
        self.assertIsNone(self.bash("python analysis/x.py"))

    def test_denied_run_does_not_pin_a_script(self):
        self.approve(PLAN.replace("analysis/x.py", "analysis/y.py"))
        self.write("analysis/x.py", "print(1)\n")
        self.assertTrue(self.denied(self.bash("python analysis/x.py")))  # no plan covers x.py
        self.assertFalse(os.path.exists(os.path.join(self.root, ".mycelium-extra", "script-pins")))

    def test_folder_named_scripts_are_pinned_at_first_run(self):
        self.write("nbs/study/a.R", "1\n")
        self.write("nbs/study/.snakemake/tmp.py", "junk\n")
        folder_plan = "## Plan\n| 1 | run `nbs/study/` scripts | repo | check |\n\nPlan status: READY"
        digest, _ = self.approve(folder_plan)
        self.assertEqual(self.approval(digest)["scripts"], {}, "a folder is not walked at show time")
        self.assertIsNone(self.bash("Rscript nbs/study/a.R"))
        self.write("nbs/study/a.R", "2\n")
        self.assertIn("nbs/study/a.R re-pinned", self.bash("Rscript nbs/study/a.R")["systemMessage"])
        card = self.hook("stop", {"last_assistant_message": folder_plan})["systemMessage"]
        self.assertIn("Scripts changed since last approved\n    \u2022 nbs/study/a.R: sha256", card)
        self.assertIn("      -1\n      +2", card)
        self.assertNotIn(".snakemake", card)

    def test_data_files_named_in_the_plan_are_not_pinned_as_scripts(self):
        self.write("analysis/x.py", "print(1)\n")
        self.write("analysis/out/de.tsv", "gene\tp\n")
        plan = PLAN.replace("check |", "check `analysis/out/de.tsv` |")
        digest, _ = self.approve(plan)
        self.assertEqual(sorted(self.approval(digest)["scripts"]), ["analysis/x.py"])

    def test_executing_a_notebook_does_not_change_its_pin(self):
        def notebook(code, output):
            return json.dumps({"cells": [
                {"cell_type": "markdown", "source": ["# notes " + output]},
                {"cell_type": "code", "source": ["x = ", code], "outputs": [{"text": output}],
                 "execution_count": len(output)}]})
        plan = "## Plan\n| 1 | run `nbs/n.ipynb` | repo | check |\n\nPlan status: READY"
        run = "jupyter nbconvert --to notebook --execute --inplace nbs/n.ipynb"
        self.write("nbs/n.ipynb", notebook("1", "a"))
        digest, _ = self.approve(plan)
        self.assertIn("sha256", self.approval(digest)["scripts"]["nbs/n.ipynb"])
        self.assertIsNone(self.bash(run))
        self.write("nbs/n.ipynb", notebook("1", "bbbb"))  # outputs and counts rewritten by the run
        self.assertIsNone(self.bash(run))
        self.write("nbs/n.ipynb", notebook("2", "bbbb"))  # a code cell edited
        result = self.bash(run)  # re-pinned with a notice, not blocked
        self.assertFalse(self.denied(result))
        self.assertIn("(+1 -1 lines)", result["systemMessage"])

    def test_explore_deleted_and_opt_out_skip_script_pins(self):
        self.write("analysis/x.py", "print(1)\n")
        self.approve()
        self.write("analysis/x.py", "print(2)\n")
        self.hook("prompt", {"prompt": "allow explore"})
        self.assertIsNone(self.bash("MYCELIUM_EXTRA_EXPLORE=1 python analysis/x.py"))
        os.remove(os.path.join(self.root, "analysis", "x.py"))
        self.assertIsNone(self.bash("python analysis/x.py"), "a missing script is the run's own error")
        self.write("analysis/x.py", "print(3)\n")
        self.config({"pin_scripts": False})
        self.assertIsNone(self.bash("python analysis/x.py"))
        self.assertEqual(self.approval(self.approve()[0])["scripts"], {})

    def test_malformed_pin_scripts_value_pins_and_says_so(self):
        self.config({"pin_scripts": "no"})
        self.write("analysis/x.py", "print(1)\n")
        digest, _ = self.approve()
        self.assertEqual(sorted(self.approval(digest)["scripts"]), ["analysis/x.py"])
        result = self.bash("python analysis/x.py")
        self.assertIn('"pin_scripts" in gate.json must be true or false', result["systemMessage"])
        self.assertIsNone(self.bash("ls analysis"), "an ungated command gets no notice")

    def test_large_script_is_pinned_without_a_snapshot(self):
        self.write("analysis/x.py", "#" * (300 * 1024) + "\n")
        digest, _ = self.approve()
        self.assertIn("sha256", self.approval(digest)["scripts"]["analysis/x.py"])
        self.write("analysis/x.py", "#" * (300 * 1024) + "\nprint(1)\n")
        result = self.bash("python analysis/x.py")
        self.assertFalse(self.denied(result))
        self.assertIn("(diff not kept)", result["systemMessage"])
        self.assertNotIn("numbers changed", result["systemMessage"])

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

    def test_hints_toggle_and_prompt_rules(self):
        ask = lambda text: self.hook("prompt", {"prompt": text})
        self.assertIsNone(ask("analyze the DE results"))  # off by default
        self.assertIn("hints on", ask("hints on")["systemMessage"])
        hint = ask("analyze the DE results")
        self.assertIn("/mycelium-extra:grill", hint["systemMessage"])
        self.assertIn("ask before switching", hint["hookSpecificOutput"]["additionalContext"])
        self.assertIn(":handoff", ask("let's wrap up the analysis")["systemMessage"])  # specific rule first
        self.assertIn(":new-analysis", ask("create a new analysis folder")["systemMessage"])
        self.assertIsNone(ask("write the report"))  # Mycelium-only without .living/
        os.makedirs(os.path.join(self.root, ".living"))
        self.assertIn("/mycelium:report", ask("write the report")["systemMessage"])
        for skipped in ("/mycelium-extra:grill analyze it", "run mycelium analyze", "fix the typo"):
            self.assertIsNone(ask(skipped), skipped)
        self.approve()
        self.assertIsNone(ask("analyze the DE results"))  # a plan is already approved
        self.assertIn("off", ask("hints off")["systemMessage"])
        self.assertIsNone(ask("write the report"))

    def test_stop_hints_verify_and_handoff_once(self):
        digest, _ = self.approve()
        self.post("python analysis/x.py", {"stdout": ""})
        self.assertIsNone(self.hook("stop", {"last_assistant_message": "done"}))  # off
        self.hook("prompt", {"prompt": "hints on"})
        transcript = os.path.join(self.root, "t.jsonl")
        with open(transcript, "w") as handle:
            for tokens, side in ((150000, True), (90000, False)):
                handle.write(json.dumps({"isSidechain": side, "message": {"usage": {
                    "input_tokens": 2, "cache_read_input_tokens": tokens}}}) + "\n")
        stop = lambda: self.hook("stop", {"last_assistant_message": "done", "transcript_path": transcript})
        notice = stop()
        self.assertIn("/mycelium-extra:verify " + digest, notice["systemMessage"])
        self.assertNotIn("handoff", notice["systemMessage"])  # sidechain usage ignored
        self.assertNotIn("hookSpecificOutput", notice)  # user-only
        with open(transcript, "a") as handle:
            handle.write(json.dumps({"message": {"usage": {"input_tokens": 1, "cache_read_input_tokens": 130000}}})
                         + "\n")
        self.assertIn(":handoff", stop()["systemMessage"])
        self.assertIsNone(stop())  # each hint once per session

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
        shutil.rmtree(os.path.join(self.root, ".mycelium-extra", "launches"))  # the post below has no launch
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
        self.assertIsNone(self.bash("sbatch -o logs/%j.out job.sh"))  # the launch the receipt is checked against
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
        self.assertEqual(receipt["exit_status"], "unknown")  # the submit's status, not the job's
        self.assertIsNone(receipt["git"])

    def test_missing_exit_status_is_recorded_as_unknown(self):
        self.approve()
        for response in ({"stdout": "", "stderr": "", "interrupted": False}, "1\n", None,
                         {"stdout": "", "exit_code": 3}, {"result": {"returncode": 0}}):
            self.post("python analysis/x.py", response)
        self.assertEqual([r["exit_status"] for r in self.receipts()], ["unknown", "unknown", "unknown", 3, 0])
        self.assertEqual([r["exit_source"] for r in self.receipts()], [None, None, None, "response", "response"])

    def test_compound_shell_status_does_not_claim_each_script_succeeded(self):
        for command in ("python analysis/x.py; true", "false && python analysis/x.py",
                        "python analysis/x.py | cat", "bash -lc 'python analysis/x.py; true'"):
            self.post(command, {"exit_code": 0})
            receipt = self.receipts()[-1]
            self.assertEqual(receipt["exit_status"], "unknown", command)
            self.assertIsNone(receipt["exit_source"])
            self.assertEqual(receipt["command_exit_status"], 0)
            self.assertEqual(receipt["command_exit_source"], "response")
        self.post("python analysis/x.py && python analysis/y.py", {"exit_code": 7})
        for receipt in self.receipts()[-2:]:
            self.assertEqual(receipt["exit_status"], "unknown")
            self.assertEqual(receipt["command_exit_status"], 7)

    def test_compound_shell_output_does_not_assign_one_job_id_to_two_jobs(self):
        self.post("sbatch job.sh; sbatch other.sh", {
            "stdout": "Submitted batch job 41\nSubmitted batch job 42\n", "exit_code": 0})
        for receipt in self.receipts():
            self.assertIsNone(receipt["job_id"])
            self.assertEqual(receipt["exit_status"], "unknown")

    def test_background_shell_launch_is_not_a_finished_script(self):
        for command in ("python analysis/x.py &", "bash -lc 'python analysis/x.py &'"):
            self.post(command, {"exit_code": 0})
            receipt = self.receipts()[-1]
            self.assertEqual(receipt["exit_status"], "unknown", command)
            self.assertEqual(receipt["command_exit_status"], 0)
        self.post("python analysis/x.py '&'", {"exit_code": 0})
        self.assertEqual(self.receipts()[-1]["exit_status"], 0)

    def test_exit_status_from_the_hook_event(self):
        # PostToolUse fires only after success; PostToolUseFailure carries `Exit code N` or a bare message.
        self.approve()
        ok = {"stdout": "", "stderr": "", "interrupted": False}
        shapes = [
            ({"hook_event_name": "PostToolUse", "tool_response": ok}, 0, "event"),
            ({"hook_event_name": "PostToolUse", "tool_response": dict(ok, exit_code=4)}, 4, "response"),
            ({"hook_event_name": "PostToolUse", "tool_response": ok, "background": True}, "unknown", None),
            ({"hook_event_name": "PostToolUse", "tool_response": dict(ok, backgroundTaskId="b1")}, "unknown", None),
            ({"hook_event_name": "PostToolUse", "tool_response": dict(ok, interrupted=True)}, "interrupted", "event"),
            ({"hook_event_name": "PostToolUseFailure", "error": "Exit code 2\nTraceback: secret " + "x" * 500},
             2, "error"),
            ({"hook_event_name": "PostToolUseFailure", "error": "Command timed out after 2m 0s\npartial"},
             "failed", "event"),
            ({"hook_event_name": "PostToolUseFailure", "error": "Exit code 0\n"}, "failed", "event"),
            ({"hook_event_name": "PostToolUseFailure", "error": "Exit code 1\n", "is_interrupt": True},
             "interrupted", "event"),
            ({"hook_event_name": "PostToolUseFailure"}, "failed", "event"),
            ({"tool_response": ok}, "unknown", None),
            ({"hook_event_name": "SomethingElse", "tool_response": ok}, "unknown", None),
        ]
        for extra, _, _ in shapes:
            tool_input = {"command": "python analysis/x.py"}
            if extra.pop("background", False):
                tool_input["run_in_background"] = True
            self.hook("post", dict(extra, tool_name="Bash", tool_input=tool_input))
        receipts = self.receipts()
        self.assertEqual([(r["exit_status"], r["exit_source"]) for r in receipts],
                         [(status, source) for _, status, source in shapes])
        self.assertEqual([r.get("background") for r in receipts[2:5]], [True, True, None])
        self.assertEqual(receipts[5]["error_line"], "Exit code 2")  # the first line only, never the output
        self.assertNotIn("secret", json.dumps(receipts))
        self.assertEqual(receipts[6]["error_line"], "Command timed out after 2m 0s")
        self.assertNotIn("error_line", receipts[9])
        self.hook("post", {"hook_event_name": "PostToolUseFailure", "tool_name": "Bash",
                                  "tool_input": {"command": "python analysis/x.py"}, "error": "y" * 999})
        self.assertEqual(len(self.receipts()[-1]["error_line"]), 200)

    def test_parsable_sbatch_and_wrap_give_one_receipt(self):
        self.approve(PLAN.replace("repo |", "repo | sbatch |"))
        self.post("sbatch --parsable --wrap='module load R; python analysis/x.py'", "4243;cluster1\n")
        receipt, = self.receipts()
        self.assertEqual(receipt["job_id"], "4243")
        self.assertIn("wrap_sha256", receipt)
        self.assertEqual(receipt["env_lines"], ["module load R"])
        self.assertEqual(receipt["response_keys"], "str")

    def test_sbatch_chdir_wrap_runs_in_the_job_folder(self):
        # sbatch resolves a --wrap payload's paths against -D/--chdir, not where sbatch ran.
        self.write("analysis/a/x.py", "print(1)")
        self.write("x.py", "print(1)")
        self.write("analysis/x.py", "print(1)")
        self.approve(PLAN.replace("analysis/x.py", "analysis/a/x.py").replace("repo |", "repo | sbatch |"))
        forms = ["sbatch --chdir=analysis/a --wrap='python x.py'", "sbatch --chdir analysis/a --wrap='python x.py'",
                 "sbatch -D analysis/a --wrap='python x.py'", "sbatch -Danalysis/a --wrap 'python x.py'"]
        for command in forms:
            self.assertIsNone(self.bash(command), command)
            self.post(command, "Submitted batch job 77\n")
        for twin in ("sbatch -D analysis --wrap='python x.py'", "sbatch --wrap='python x.py' -D analysis",
                     "sbatch --chdir=analysis/a --wrap='python ../x.py'"):
            self.assertTrue(self.denied(self.bash(twin)), twin)
        self.post("sbatch -D analysis --wrap='python x.py'", "Submitted batch job 78\n")
        receipts = self.receipts()
        self.assertEqual([r["paths"] for r in receipts], [["analysis/a/x.py"]] * 4 + [["analysis/x.py"]])
        self.assertEqual([r["job_cwd"] for r in receipts], ["analysis/a"] * 4 + ["analysis"])
        self.assertEqual([len(r["plans"]) for r in receipts], [1, 1, 1, 1, 0], "a plan must name what the job runs")
        self.post("sbatch --wrap='python analysis/a/x.py'", "Submitted batch job 79\n")
        self.assertEqual(self.receipts()[-1]["paths"], ["analysis/a/x.py"])
        self.assertNotIn("job_cwd", self.receipts()[-1])

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

    def test_runs_mycelium_misses_get_a_post_action_reminder(self):
        context = lambda notice: (notice.get("hookSpecificOutput") or {}).get("additionalContext", "")
        self.assertNotIn("post-action", context(self.post("bash analysis/x/run.sh", {"stdout": ""})),
                         "no .living/: not a Mycelium repository")
        os.makedirs(os.path.join(self.root, ".living"))
        for command in ["bash analysis/x/run.sh", "snakemake -s analysis/x/Snakefile",
                        "sbatch analysis/x/job.sh"]:
            self.assertIn("post-action protocol did not fire", context(self.post(command, {"stdout": ""})),
                          command)
        for command in ["python analysis/x.py", "Rscript analysis/x.R"]:
            self.assertNotIn("post-action", context(self.post(command, {"stdout": ""})), command)
        both = context(self.post("MYCELIUM_EXTRA_EXPLORE=1 bash analysis/x/run.sh", {"stdout": ""}))
        self.assertIn("post-action protocol did not fire", both)
        self.assertIn("Exploratory run (not reportable)", both)

    def test_planned_run_suggests_ledger_cell_with_plan(self):
        context = lambda notice: (notice.get("hookSpecificOutput") or {}).get("additionalContext", "")
        digest, _ = self.approve()
        self.assertNotIn("Run/Session", context(self.post("python analysis/x.py", {"stdout": ""})),
                         "no .living/: not a Mycelium repository")
        os.makedirs(os.path.join(self.root, ".living"))
        planned = context(self.post("python analysis/x.py", {"stdout": ""}))
        self.assertIn("`s1; plan {}`".format(digest), planned)
        self.assertIn("Result cell with `[agent-derived: <output path>]`", planned)
        explore = context(self.post("MYCELIUM_EXTRA_EXPLORE=1 python analysis/x.py", {"stdout": ""}))
        self.assertNotIn("Run/Session", explore)

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


    def test_on_error_fails_open_by_default_and_denies_only_tool_calls_when_set(self):
        broken = {"gated_commands": 5, "gated_paths": 5}  # the tool handler raises on a config it cannot read
        self.config(broken)
        result = self.bash("ls")
        self.assertFalse(self.denied(result))
        self.assertIn("mycelium-extra gate error (tool)", result["systemMessage"])
        self.config(dict(broken, on_error="deny"))
        result = self.bash("ls")
        self.assertTrue(self.denied(result))
        self.assertIn("on_error", result["hookSpecificOutput"]["permissionDecisionReason"])
        for event in ("prompt", "stop", "post"):  # nothing to block outside a tool call
            proc = subprocess.Popen([sys.executable, self.entry, event], stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.root)
            out, err = proc.communicate(b"{not json")  # an unreadable event is an error in any handler
            self.assertEqual(proc.returncode, 0, err)
            reply = json.loads(out.decode("utf-8"))
            self.assertFalse(self.denied(reply), event)
            self.assertIn("gate error ({})".format(event), reply["systemMessage"])
        with open(os.path.join(self.root, ".mycelium-extra", "gate-errors.jsonl"), encoding="utf-8") as log:
            records = [json.loads(line) for line in log]
        self.assertEqual([r["decision"] for r in records if r["event"] == "tool"], ["allow", "deny"])

    def test_on_error_deny_survives_a_log_that_cannot_be_written(self):
        self.config({"gated_commands": 5, "on_error": "deny"})
        os.makedirs(os.path.join(self.root, ".mycelium-extra", "gate-errors.jsonl"))  # a folder cannot be appended to
        self.assertTrue(self.denied(self.bash("ls")))

    def test_on_error_must_be_allow_or_deny(self):
        self.config({"gated_commands": 5, "on_error": "block"})
        result = self.bash("ls")
        self.assertFalse(self.denied(result))
        self.assertIn('"on_error" in gate.json must be "allow" or "deny"', result["systemMessage"])

    def test_default_decisions_do_not_change_without_an_error(self):
        self.config({"on_error": "deny"})
        self.assertTrue(self.denied(self.bash("python analysis/x.py")))
        self.assertIsNone(self.bash("ls"))


class LauncherTest(GateTest):
    """Every gate test again, through the entry point hooks.json calls."""
    entry = LAUNCHER


class LauncherOnlyTest(unittest.TestCase):
    def run_launcher(self, stdin, code=None):
        args = [sys.executable, LAUNCHER, "tool"] if code is None else [sys.executable, "-c", code]
        proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate(stdin.encode("utf-8"))
        self.assertEqual(proc.returncode, 0, err)
        return out.decode("utf-8")

    def test_gate_off_prints_nothing_and_never_loads_the_gate(self):
        folder = tempfile.mkdtemp()
        try:
            event = json.dumps({"tool_name": "Bash", "cwd": folder,
                                "tool_input": {"command": "python analysis/x.py"}})
            self.assertEqual(self.run_launcher(event), "")
            probe = ("import runpy, sys; sys.argv = [{!r}, 'tool']\n"
                     "try:\n    runpy.run_path({!r}, run_name='__main__')\n"
                     "except SystemExit:\n    pass\n"
                     "print('gate' in sys.modules)").format(LAUNCHER, LAUNCHER)
            self.assertEqual(self.run_launcher(event, probe).strip(), "False")
        finally:
            shutil.rmtree(folder)

    def test_unreadable_event_fails_open_like_the_gate(self):
        message = self.run_launcher("{not json")
        self.assertIn("mycelium-extra gate error (tool)", message)
        proc = subprocess.Popen([sys.executable, GATE, "tool"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.assertEqual(message, proc.communicate(b"{not json")[0].decode("utf-8"))

    def test_on_error_covers_a_gate_that_cannot_load_on_both_hosts(self):
        folder = tempfile.mkdtemp()
        try:
            hooks = os.path.join(folder, "hooks")
            os.makedirs(hooks)
            shutil.copy(LAUNCHER, hooks)
            with open(os.path.join(hooks, "gate.py"), "w") as broken:
                broken.write("def main(:\n")
            repo = os.path.join(folder, "repo")
            os.makedirs(os.path.join(repo, ".mycelium-extra"))
            event = json.dumps({"tool_name": "Bash", "cwd": repo, "tool_input": {"command": "ls"}})

            def run(*args):
                proc = subprocess.Popen([sys.executable, os.path.join(hooks, "gate_run.py")] + list(args),
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, err = proc.communicate(event.encode("utf-8"))
                self.assertEqual(proc.returncode, 0, err)
                return json.loads(out.decode("utf-8"))

            def config(text):
                with open(os.path.join(repo, ".mycelium-extra", "gate.json"), "w") as handle:
                    handle.write(text)

            for args in (("tool",), ("--host", "codex", "tool")):
                config("{}")
                reply = run(*args)
                self.assertIn("mycelium-extra gate error (tool)", reply["systemMessage"])
                config('{"on_error": "deny"}')
                reply = run(*args)
                self.assertEqual(reply["hookSpecificOutput"]["permissionDecision"], "deny")
                config('{"on_error": "deny"')  # unreadable: it cannot opt in
                reply = run(*args)
                self.assertIn("unreadable", reply["systemMessage"])
        finally:
            shutil.rmtree(folder)

    def test_find_root_copies_agree(self):
        sys.dont_write_bytecode = True
        sys.path.insert(0, os.path.dirname(GATE))
        import gate
        import gate_run
        root = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(root, ".mycelium-extra"))
            open(os.path.join(root, ".mycelium-extra", "gate.json"), "w").close()
            os.makedirs(os.path.join(root, "a", "b"))
            for cwd in (root, os.path.join(root, "a", "b"), os.path.dirname(root), "", None):
                self.assertEqual(gate.find_root(cwd), gate_run.find_root(cwd), cwd)
        finally:
            shutil.rmtree(root)


class CompatibilityTest(unittest.TestCase):
    def test_codex_loads_its_own_gate_hooks(self):
        repo = os.path.join(os.path.dirname(GATE), "..")
        with open(os.path.join(repo, ".codex-plugin", "plugin.json")) as handle:
            manifest = json.load(handle)
        self.assertEqual(manifest.get("hooks"), "./hooks/codex.json")
        with open(os.path.join(repo, "hooks", "codex.json")) as handle:
            hooks = json.load(handle)["hooks"]
        self.assertNotIn("PostToolUseFailure", hooks)
        self.assertIsNotNone(re.fullmatch(hooks["PreToolUse"][0]["matcher"], "apply_patch"))
        self.assertTrue(os.path.isfile(os.path.join(repo, "hooks", "hooks.json")))

    def test_failed_bash_runs_reach_the_post_hook(self):
        # PostToolUse fires only on success, so a failed run is receipted from PostToolUseFailure.
        with open(os.path.join(os.path.dirname(GATE), "hooks.json")) as handle:
            hooks = json.load(handle)["hooks"]
        self.assertEqual(hooks["PostToolUseFailure"], hooks["PostToolUse"][:1])
        self.assertEqual(hooks["PostToolUse"][0]["matcher"], "Bash")
        self.assertEqual(hooks["PostToolUse"][1]["matcher"], "Write|Edit|MultiEdit|NotebookEdit")  # lint on write
        self.assertIn('gate_run.py" post;', hooks["PostToolUse"][0]["hooks"][0]["command"])

class PreparationAndLaunchTest(unittest.TestCase):
    """ME-09: a plan is approvable only once prepared. ME-07: a receipt keeps the approval its launch was checked against."""
    entry = GATE
    setUp, tearDown, config, hook, bash, denied = (
        GateTest.setUp, GateTest.tearDown, GateTest.config, GateTest.hook, GateTest.bash, GateTest.denied)
    PLAN_WITH_INPUT = "Inputs: data/in.tsv\n\n" + PLAN

    def path(self, *parts):
        return os.path.join(self.root, ".mycelium-extra", *parts)

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write(text)

    def pending(self):
        with open(self.path("pending", "s1.json")) as handle:
            return json.load(handle)

    def approval(self, digest):
        with open(self.path("approvals", digest + ".json")) as handle:
            return json.load(handle)

    def show(self, text, session="s1"):
        notice = self.hook("stop", {"last_assistant_message": text}, session=session)
        return notice["systemMessage"].split("approve plan ")[1][:8]

    def prompt(self, text, session="s1"):
        return self.hook("prompt", {"prompt": text}, session=session)["systemMessage"]

    def receipts(self):
        if not os.path.isfile(self.path("receipts.jsonl")):
            return []
        with open(self.path("receipts.jsonl")) as handle:
            return [json.loads(line) for line in handle]

    def tool(self, command="python analysis/x.py", session="s1", **event):
        return self.hook("tool", dict({"tool_name": "Bash", "tool_input": {"command": command}}, **event),
                         session=session)

    def post(self, command="python analysis/x.py", session="s1", **event):
        return self.hook("post", dict({"tool_name": "Bash", "tool_input": {"command": command},
                                       "tool_response": {"stdout": ""}}, **event), session=session)

    def expire(self, digest):
        record = self.approval(digest)
        record["approved_at"] -= 30 * 24 * 3600
        with open(self.path("approvals", digest + ".json"), "w") as handle:
            json.dump(record, handle)

    def launches(self):
        folder = self.path("launches")
        return sorted(n for n in os.listdir(folder) if n.endswith(".json")) if os.path.isdir(folder) else []

    def stop_fails(self, name):
        sys.dont_write_bytecode = True
        sys.path.insert(0, os.path.dirname(GATE))
        import gate
        event = {"session_id": "s1", "cwd": self.root, "last_assistant_message": self.PLAN_WITH_INPUT}
        with mock.patch.object(gate, name, side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                gate.on_stop(event, self.root, gate.load_config(self.root))

    def test_a_fully_prepared_plan_is_approvable_on_the_first_prompt(self):
        self.write("data/in.tsv", "a\n")
        digest = self.show(self.PLAN_WITH_INPUT)
        self.assertTrue(self.pending()[0]["ready"])
        self.assertIn("approved", self.prompt("approve plan " + digest))
        self.assertIn("data/in.tsv", self.approval(digest)["pins"])

    def test_interrupted_preparation_keeps_the_text_but_refuses_approval(self):
        self.write("data/in.tsv", "a\n")
        for name in ("pin_inputs", "pin_scripts", "approval_card"):
            self.stop_fails(name)
            entry, = self.pending()
            self.assertEqual((entry["text"], entry["ready"]), (self.PLAN_WITH_INPUT.strip(), False), name)
            digest = entry["hash"]
            self.assertIn(digest + " (preparing)", self.prompt("approve plan"))
            self.assertIn("not fully prepared", self.prompt("approve plan " + digest))
            self.assertFalse(os.path.exists(self.path("approvals", digest + ".json")), name)
        self.assertEqual(self.show(self.PLAN_WITH_INPUT), digest)  # showing the plan again prepares it
        self.assertTrue(self.pending()[0]["ready"])
        self.assertIn("approved", self.prompt("approve plan " + digest))
        self.assertIn("data/in.tsv", self.approval(digest)["pins"])  # one approval, with its pins

    def test_a_pending_entry_from_before_the_ready_field_is_approvable(self):
        digest = self.show(PLAN)
        entries = self.pending()
        del entries[0]["ready"]
        with open(self.path("pending", "s1.json"), "w") as handle:
            json.dump(entries, handle)
        self.assertIn("approved", self.prompt("approve plan " + digest))

    def covered_launch(self, **event):
        self.write("data/in.tsv", "a\n")
        digest = self.show(self.PLAN_WITH_INPUT)
        self.prompt("approve plan " + digest)
        self.assertIsNone(self.tool(**event))
        return digest

    def test_a_launch_keeps_its_approval_after_expiry_and_a_new_launch_is_denied(self):
        digest = self.covered_launch()
        pins = self.approval(digest)["pins"]
        self.assertTrue(pins)
        self.expire(digest)
        self.post()
        receipt, = self.receipts()
        self.assertEqual((receipt["plans"], receipt["pins"], receipt["pins_checked"]), ([digest], pins, True))
        self.assertEqual(self.launches(), [], "the record goes once its call reports back")
        self.assertTrue(self.denied(self.bash("python analysis/x.py")))

    def test_a_plan_approved_after_the_launch_is_not_credited_to_it(self):
        first = self.covered_launch()
        second = self.show(PLAN + "\nPlan revision: amended assumption.", session="s2")
        self.prompt("approve plan " + second, session="s2")
        self.assertNotEqual(first, second)
        self.post()
        self.assertEqual(self.receipts()[0]["plans"], [first])

    def test_a_post_without_a_launch_record_is_unattributed_once_the_approval_expires(self):
        digest = self.show(PLAN)
        self.prompt("approve plan " + digest)
        self.expire(digest)
        notice = self.post()  # no hook saw this launch, and nothing covers it now
        self.assertIn("no approved plan", notice["systemMessage"])
        self.assertEqual(self.receipts()[0]["plans"], [])

    def test_launch_records_are_keyed_by_the_call_id_and_stale_ones_pruned(self):
        digest = self.covered_launch(tool_use_id="t1")
        self.tool(tool_use_id="t2")
        old = self.path("launches", "old.json")
        with open(old, "w") as handle:
            json.dump({"ts": 1, "runs": {"python analysis/x.py": {"plans": ["deadbeef"], "pins": {}}}}, handle)
        os.utime(old, (1, 1))
        self.tool(tool_use_id="t3")
        self.assertEqual(len(self.launches()), 3, "t1, t2, t3; the stale record is gone")
        self.post(tool_use_id="t2")
        self.assertEqual(len(self.launches()), 2)
        self.post(tool_use_id="t1")
        self.assertEqual([r["plans"] for r in self.receipts()], [[digest], [digest]])


class ReviewFixesTest(unittest.TestCase):
    """Fixes from the independent review of the launch record and the wrapper reader."""
    entry = GATE
    setUp, tearDown, config, hook, bash, denied = (
        GateTest.setUp, GateTest.tearDown, GateTest.config, GateTest.hook, GateTest.bash, GateTest.denied)
    path, write, approval, show, prompt, receipts, tool, post, expire, launches = (
        PreparationAndLaunchTest.path, PreparationAndLaunchTest.write, PreparationAndLaunchTest.approval,
        PreparationAndLaunchTest.show, PreparationAndLaunchTest.prompt, PreparationAndLaunchTest.receipts,
        PreparationAndLaunchTest.tool, PreparationAndLaunchTest.post, PreparationAndLaunchTest.expire,
        PreparationAndLaunchTest.launches)

    def approve(self, text, session="s1"):
        digest = self.show(text, session)
        self.prompt("approve plan " + digest, session)
        return digest

    @staticmethod
    def plan(step, inputs=""):
        return (("Inputs: {}\n\n".format(inputs) if inputs else "")
                + "## Plan\n| 1 | {} | repo | check |\n\nPlan status: READY".format(step))

    def gate(self):
        sys.dont_write_bytecode = True
        sys.path.insert(0, os.path.dirname(GATE))
        import gate
        return gate

    def test_the_same_segment_in_two_folders_is_credited_to_its_own_plan(self):
        for name in ("a", "b"):
            self.write("data/{}.tsv".format(name), name + "\n")
            self.write("analysis/{}/run.py".format(name), "pass\n")
        first = self.approve(self.plan("run `analysis/a/run.py`", "data/a.tsv"))
        second = self.approve(self.plan("run `analysis/b/run.py`", "data/b.tsv"))
        command = "cd analysis/a && python run.py; cd ../b && python run.py"
        self.assertIsNone(self.tool(command, tool_use_id="t1"))
        self.post(command, tool_use_id="t1")
        one, two = self.receipts()
        self.assertEqual((one["plans"], sorted(one["pins"])), ([first], ["data/a.tsv"]))
        self.assertEqual((two["plans"], sorted(two["pins"])), ([second], ["data/b.tsv"]))

    def test_a_wrap_receipt_keeps_the_pins_of_the_plan_it_credits(self):
        self.write("data/a.tsv", "a\n")
        self.write("data/b.tsv", "b\n")
        first = self.approve(self.plan("run `analysis/x.py` via sbatch --wrap", "data/a.tsv"))
        self.approve(self.plan("submit with sbatch", "data/b.tsv"))  # newer, names no script
        command = "sbatch --wrap='python analysis/x.py'"
        self.assertIsNone(self.tool(command, tool_use_id="t1"))
        self.post(command, tool_use_id="t1")
        receipt, = self.receipts()
        self.assertEqual((receipt["plans"], sorted(receipt["pins"])), ([first], ["data/a.tsv"]))

    def test_launch_cleanup_survives_records_vanishing(self):
        gate = self.gate()
        event = {"session_id": "s1", "tool_use_id": "t1", "tool_input": {"command": "x"}}
        folder = self.path("launches")
        os.makedirs(folder)
        for name in ("old.json", "gone.json"):
            with open(os.path.join(folder, name), "w") as handle:
                handle.write("{}")
            os.utime(os.path.join(folder, name), (1, 1))
        real_remove = os.remove

        def racing_remove(path):  # a parallel call's hook removed it first
            real_remove(path)
            raise FileNotFoundError(path)

        with mock.patch.object(gate.os, "listdir", return_value=["old.json", "ghost.json", "gone.json"]):
            with mock.patch.object(gate.os, "remove", side_effect=racing_remove):
                gate.write_launch(self.root, event, {"x": []})
        self.assertEqual(self.launches(), [gate.os.path.basename(gate.launch_path(self.root, event))])
        with mock.patch.object(gate.os, "remove", side_effect=racing_remove):
            self.assertEqual(gate.take_launch(self.root, event), {"x": []})
        self.assertEqual(self.launches(), [])

    def test_parallel_launch_writes_do_not_share_a_temp_file(self):
        gate = self.gate()
        names = []
        real_replace = os.replace
        with mock.patch.object(gate.os, "replace", side_effect=lambda a, b: (names.append(a), real_replace(a, b))):
            gate.write_json(self.path("launches", "k.json"), {})
        self.assertNotEqual(names[0], self.path("launches", "k.json.tmp"))

    def test_a_folder_option_before_a_recursing_payload_still_moves_the_folder(self):
        for command in [
            'env -C analysis/demo bash -c "python run.py"',
            'srun -D analysis/demo bash -c "python run.py"',
            'conda run --cwd analysis/demo bash -c "python step.py"',
            'uv run --directory analysis/demo bash -c "python step.py"',
            'env -C analysis/demo -S "python step.py"',
            "env -C analysis/demo sbatch --wrap='python step.py'",
        ]:
            self.assertTrue(self.denied(self.bash(command)), command)
        self.write("analysis/demo/step.py", "pass\n")
        self.approve(self.plan("submit with sbatch"))
        self.assertTrue(self.denied(self.bash("env -C analysis/demo sbatch --wrap='python step.py'")))
        self.approve(self.plan("run `analysis/demo/step.py`"))
        command = 'env -C analysis/demo bash -c "python step.py"'
        self.assertIsNone(self.tool(command, tool_use_id="t1"))
        self.post(command, tool_use_id="t1")
        receipt, = self.receipts()
        self.assertEqual((receipt["cwd"], receipt["paths"]), ("analysis/demo", ["analysis/demo/step.py"]))

    def test_wrapper_flags_that_take_no_value_do_not_hide_a_read(self):
        for command in [
            "stdbuf -oL grep -rn python analysis/",
            "stdbuf -oL grep python analysis/",
            "env -i grep -n python analysis/demo/step.py",
            "env --ignore-environment grep -n python analysis/demo/step.py",
            "uv run --frozen pytest -k python analysis/demo",
            "uv run --locked --no-sync grep -n python analysis/demo/step.py",
            "uv run --isolated --no-project pytest python analysis/demo",
            "srun --exclusive grep -rn python analysis/",
            "conda run --no-capture-output grep -rn python analysis/",
        ]:
            self.assertIsNone(self.bash(command), command)
        for command in [
            "env -i python analysis/demo/step.py",
            "uv run --frozen python analysis/demo/step.py",
            "uv run --no-project --python 3.12 python analysis/x.py",
            "srun --exclusive python analysis/x.py",
            "conda run --no-capture-output python analysis/x.py",
            "stdbuf -oL python analysis/x.py",
            "timeout -sKILL 5 python analysis/x.py",
            "timeout -s KILL 5 python analysis/x.py",
            "env -C %s python analysis/demo/step.py" % self.root,
            "conda run -p /p python analysis/x.py",
            "uv run --project envdir python analysis/x.py",
            "uv run --python 3.12 python analysis/x.py",
            "conda run -n synthetic python analysis/x.py",
            "uv run --project . python analysis/x.py",
        ]:
            self.assertTrue(self.denied(self.bash(command)), command)

    def test_wrappers_named_by_absolute_path_are_still_wrappers(self):
        for command in [
            "/usr/bin/env python analysis/x.py",
            "/usr/bin/env -C analysis/demo python step.py",
            "/usr/bin/time python analysis/x.py",
            "/opt/conda/bin/conda run -n x python analysis/x.py",
            "~/miniforge3/bin/conda run -n x python analysis/x.py",
            "/usr/bin/python analysis/x.py",
            "./analysis/x.py",
        ]:
            self.assertTrue(self.denied(self.bash(command)), command)
        for command in ["/usr/bin/ls analysis/x.py", "/usr/bin/env", "/usr/bin/time ls analysis",
                        "/opt/conda/bin/conda run -n x ls", "/usr/bin/env -C /tmp python tools/y.py"]:
            self.assertIsNone(self.bash(command), command)

    def test_a_gated_script_named_like_a_wrapper_stays_gated(self):
        self.assertTrue(self.denied(self.bash("analysis/run")))
        self.assertTrue(self.denied(self.bash("./analysis/time --fast")))


# ---------------------------------------------------------------- D10: approval latency and checkpoint

class ApprovalLatencyTest(unittest.TestCase):
    """GateTest's helpers without its tests, so they are not run twice."""
    entry = GATE
    setUp, tearDown, config, hook = GateTest.setUp, GateTest.tearDown, GateTest.config, GateTest.hook

    CHOICES = {"1": "keep all donors", "2": "exact permutation test", "3": "alpha 0.05", "4": "log scale"}
    LONG = "\n".join([
        "## Plan", "| # | Step | Choice | Source | Validation |", "|---|---|---|---|---|",
        "| 1 | Run `analysis/a/01_load.py` | keep all donors | user | 24 rows |",
        "| 2 | Run `analysis/a/02_fit.py` | exact permutation test | user | 12 donors |",
        "| 3 | Run `analysis/a/03_sum.py` | alpha 0.05 | default: convention | 1 row |",
        "| 4 | Run `analysis/a/04_plot.py` | log scale | repo: CLAUDE.md | one png |",
        "", "Plan status: READY"])
    NO_CHOICE = "\n".join([
        "## Plan", "| # | Step | Validation |", "|---|---|---|",
        "| 1 | Back up the table | md5 equal |",
        "| 2 | Run `analysis/a/02_fit.py` | 12 donors |",
        "| 3 | Report the hits | 1 row |",
        "", "Plan status: READY"])

    def show(self, text):
        return self.hook("stop", {"last_assistant_message": text})["systemMessage"].split("approve plan ")[1][:8]

    def say(self, digest, answer=None):
        return self.hook("prompt", {"prompt": "approve plan {}{}".format(digest, "" if answer is None else " " + answer)})

    def approved(self, digest):
        return os.path.isfile(os.path.join(self.root, ".mycelium-extra", "approvals", digest + ".json"))

    def ledger(self):
        with open(os.path.join(self.root, ".mycelium-extra", "approvals.jsonl")) as handle:
            return [json.loads(line) for line in handle]

    def asked(self, digest):
        """(reply, number that answers it) for the checkpoint question."""
        reply = self.say(digest)["systemMessage"]
        text = re.search(r'Choice: "(.*)"\?', reply).group(1)
        return reply, [n for n, choice in self.CHOICES.items() if choice == text][0]

    def test_an_approval_logs_its_latency_and_size(self):
        digest = self.show(PLAN)
        pending = os.path.join(self.root, ".mycelium-extra", "pending", "s1.json")
        with open(pending) as handle:
            entries = json.load(handle)
        entries[0]["ts"] = time.time() - 30
        with open(pending, "w") as handle:
            json.dump(entries, handle)
        reply = self.say(digest)["systemMessage"]
        self.assertIn("approved", reply)
        self.assertNotIn("latency", reply.lower())
        (record,) = self.ledger()
        self.assertEqual((record["hash"], record["session_id"], record["plan_rows"], record["plan_chars"]),
                         (digest, "s1", 0, len(PLAN)))  # PLAN has no headed table: no step rows
        self.assertTrue(29 < record["latency_s"] < 40, record)
        self.assertAlmostEqual(record["approved_ts"] - record["shown_ts"], record["latency_s"], delta=0.2)
        self.assertNotIn("checkpoint", record)

    def test_plan_rows_counts_the_step_rows(self):
        self.say(self.show(self.LONG))
        self.assertEqual(self.ledger()[0]["plan_rows"], 4)

    def test_the_log_is_appended_across_approvals(self):
        self.say(self.show(PLAN))
        self.say(self.show(self.LONG))
        self.assertEqual([r["plan_rows"] for r in self.ledger()], [0, 4])

    def test_a_failing_log_write_does_not_stop_the_approval(self):
        os.makedirs(os.path.join(self.root, ".mycelium-extra", "approvals.jsonl"))  # appending to it fails
        digest = self.show(PLAN)
        self.assertIn("approved", self.say(digest)["systemMessage"])
        self.assertTrue(self.approved(digest))

    def test_the_checkpoint_is_off_by_default(self):
        digest = self.show(self.LONG)
        self.assertIn("approved", self.say(digest)["systemMessage"])
        self.assertTrue(self.approved(digest))
        self.assertNotIn("checkpoint", self.ledger()[0])

    def test_the_checkpoint_asks_one_question_and_a_right_answer_approves(self):
        self.config({"checkpoint_steps": 3})
        digest = self.show(self.LONG)
        reply, right = self.asked(digest)
        self.assertIn("not approved yet", reply)
        self.assertIn("approve plan {} <number>".format(digest), reply)
        self.assertFalse(self.approved(digest))
        reply2, _ = self.asked(digest)
        self.assertEqual(reply2, reply, "the same question is asked twice")
        wrong = str(int(right) % 4 + 1)
        shown = self.say(digest, wrong)["systemMessage"]
        self.assertFalse(self.approved(digest), "a wrong answer approves nothing")
        self.assertIn("Not step {}. Step {}: Run analysis/a/0{}".format(wrong, right, right), shown)
        self.assertIn("Choice: {} | Source: ".format(self.CHOICES[right]), shown)
        self.assertIn("approve plan {} <number>".format(digest), shown)
        self.assertEqual(self.say(digest, "99")["systemMessage"].count("Not step 99"), 1)
        self.assertFalse(self.approved(digest))
        self.assertIn("approved", self.say(digest, right)["systemMessage"])
        self.assertTrue(self.approved(digest))
        self.assertEqual(self.ledger()[0]["checkpoint"], {"asked": True, "passed": True, "wrong_attempts": 2})

    def test_a_reapproval_asks_again(self):
        self.config({"checkpoint_steps": 3})
        digest = self.show(self.LONG)
        _, right = self.asked(digest)
        self.say(digest, right)
        self.assertIn("not approved yet", self.say(digest)["systemMessage"])
        self.say(digest, right)
        self.assertEqual([r["checkpoint"]["wrong_attempts"] for r in self.ledger()], [0, 0])

    def test_a_plan_at_or_below_the_threshold_skips_the_checkpoint(self):
        self.config({"checkpoint_steps": 4})
        self.assertIn("approved", self.say(self.show(self.LONG))["systemMessage"])
        self.assertNotIn("checkpoint", self.ledger()[0])

    def test_a_trailing_number_with_the_checkpoint_off_approves_nothing(self):
        digest = self.show(self.LONG)
        self.assertIn("nothing approved", self.say(digest, "2")["systemMessage"])
        self.assertFalse(self.approved(digest))

    def test_an_invalid_value_is_ignored_with_a_notice(self):
        digest = self.show(self.LONG)
        for value in ("3", -1, 2.5, True):
            self.config({"checkpoint_steps": value})
            reply = self.say(digest)["systemMessage"]
            self.assertIn("approved", reply, repr(value))
            self.assertIn('"checkpoint_steps" in gate.json must be a whole number', reply)
        self.config({"checkpoint_steps": 0})
        self.assertNotIn("checkpoint_steps", self.say(digest)["systemMessage"])

    def test_a_plan_without_choice_cells_asks_for_the_first_script(self):
        self.config({"checkpoint_steps": 2})
        digest = self.show(self.NO_CHOICE)
        reply = self.say(digest)["systemMessage"]
        self.assertIn('which step number names "analysis/a/02_fit.py"?', reply)
        self.assertEqual(self.say(digest, "2")["systemMessage"].count("approved"), 1)

    def test_a_plan_with_nothing_to_ask_skips_the_checkpoint(self):
        self.config({"checkpoint_steps": 1})
        plan = "\n".join(["## Plan", "| # | Step | Validation |", "|---|---|---|", "| 1 | Back up | ok |",
                          "| 2 | Report | ok |", "", "Plan status: READY"])
        self.assertIn("approved", self.say(self.show(plan))["systemMessage"])
        self.assertIn("approved", self.say(self.show(PLAN))["systemMessage"])  # no step table at all


# ---------------------------------------------------------------- open gaps closed after 0.9.72

class OpenGapsTest(unittest.TestCase):
    """Folder options that hold an expansion, `sbatch --wrap` needing one plan, and legacy pending entries."""
    entry = GATE
    setUp, tearDown, config, hook, bash, denied = (
        GateTest.setUp, GateTest.tearDown, GateTest.config, GateTest.hook, GateTest.bash, GateTest.denied)
    path, write, approval, pending, show, prompt, receipts, tool, post = (
        PreparationAndLaunchTest.path, PreparationAndLaunchTest.write, PreparationAndLaunchTest.approval,
        PreparationAndLaunchTest.pending, PreparationAndLaunchTest.show, PreparationAndLaunchTest.prompt,
        PreparationAndLaunchTest.receipts, PreparationAndLaunchTest.tool, PreparationAndLaunchTest.post)
    plan = staticmethod(ReviewFixesTest.plan)

    def approve(self, text, session="s1"):
        digest = self.show(text, session)
        self.prompt("approve plan " + digest, session)
        return digest

    def reason(self, command, cwd=None):
        result = self.bash(command, cwd)
        self.assertTrue(self.denied(result), command)
        return result["hookSpecificOutput"]["permissionDecisionReason"]

    # GAP 1: a wrapper's folder option that is a shell expansion

    def test_pwd_and_home_in_a_folder_option_are_resolved(self):
        os.environ["HOME"] = self.root  # the hook inherits it
        for command in [
            'env -C "$PWD/analysis/demo" python step.py',
            'env -C "${PWD}/analysis/demo" python step.py',
            "env -C $PWD/analysis/demo python step.py",
            'srun -D "$PWD/analysis/demo" python step.py',
            'conda run --cwd "$PWD/analysis/demo" python step.py',
            'uv run --directory "$PWD/analysis/demo" python step.py',
            "env --chdir=$PWD/analysis/demo python step.py",
            'env -C "$HOME/analysis/demo" python step.py',
            "env -C ~/analysis/demo python step.py",
        ]:
            reason = self.reason(command)
            self.assertIn("python analysis/demo/step.py", reason, command)  # resolved: no guessing
            self.assertNotIn("cannot resolve", reason, command)
        self.assertIn("python analysis/demo/step.py", self.reason('env -C "$PWD/demo" python step.py',
                                                                  os.path.join(self.root, "analysis")))
        self.approve(self.plan("run `analysis/demo/step.py`"))
        for command in ['env -C "$PWD/analysis/demo" python step.py', 'env -C "$HOME/analysis/demo" python step.py']:
            self.assertIsNone(self.tool(command, tool_use_id="t1"), command)
        self.post('env -C "$PWD/analysis/demo" python step.py', tool_use_id="t1")
        receipt, = self.receipts()
        self.assertEqual((receipt["cwd"], receipt["paths"]), ("analysis/demo", ["analysis/demo/step.py"]))

    def test_a_resolved_folder_outside_the_gated_paths_passes(self):
        for command in ['env -C "$PWD/tools" python y.py', "env -C $HOME/x python y.py", 'env -C "$PWD" ls']:
            self.assertIsNone(self.bash(command), command)

    def test_an_unresolvable_folder_option_is_gated_and_says_so(self):
        for command in [
            'env -C "$ANALYSIS/demo" python step.py',
            'env -C "$PWD/analysis/$NAME" python step.py',
            'env -C "${PWD:-.}/analysis" python step.py',
            'env -C "$PWDX/a" python step.py',
            'env -C "$(pwd)/analysis/demo" python step.py',
            "env -C `pwd`/analysis/demo python step.py",
            'env --chdir="$X" python step.py',
            'srun -D "$X" python step.py',
            'conda run --cwd "$X" python step.py',
            'uv run --directory "$X" python step.py',
            'env -C "$X" bash -c "python step.py"',
            'env -C "$X" -S "python step.py"',
            'env -C "$X" -C sub python step.py',
            "sbatch -D \"$X\" --wrap='python step.py'",
            "env -C \"$X\" sbatch --wrap='python step.py'",
        ]:
            reason = self.reason(command)
            self.assertIn("cannot resolve", reason, command)
            self.assertIn("literal path", reason, command)
        self.assertIn("`$ANALYSIS/demo`", self.reason('env -C "$ANALYSIS/demo" python step.py'))

    def test_an_unresolvable_folder_is_checked_against_both_readings(self):
        self.approve(self.plan("run `analysis/demo/step.py`"))
        command = 'env -C "$X/demo" python step.py'
        self.assertTrue(self.denied(self.bash(command)))  # from the root, the script is step.py: not planned
        self.assertIsNone(self.bash(command, os.path.join(self.root, "analysis", "demo")), "outer folder reading")
        self.approve(self.plan("run `analysis/x.py`"))
        self.assertIsNone(self.bash('env -C "$X" python analysis/x.py'), "repo root reading")
        self.assertTrue(self.denied(self.bash('env -C "$X" python analysis/other.py')))

    def test_an_unresolvable_folder_leaves_read_only_wrapped_commands_alone(self):
        for command in [
            'env -C "$PWD/x" ls', 'env -C "$X" ls', 'env -C "$X" cat analysis/x.py', 'env -C "$X" grep -rn python .',
            'env -C "$X" python -c "print(1)"', 'env -C "$X" python', 'conda run --cwd "$X" ls',
            'uv run --directory "$X" pytest', 'srun -D "$X" hostname', 'env -C "$X" command -v python',
        ]:
            self.assertIsNone(self.bash(command), command)

    def test_a_gated_command_in_an_unresolvable_folder_needs_its_word_in_a_plan(self):
        self.assertTrue(self.denied(self.bash('env -C "$X" snakemake -j 4')))
        self.approve(self.plan("run `analysis/x.py` with snakemake"))
        self.assertIsNone(self.bash('env -C "$X" snakemake -j 4'))

    def test_cd_into_an_expansion_is_unchanged(self):
        # control: `cd` is not a wrapper option; this reading is the same as before this change
        for command in ['cd "$PWD/analysis/demo" && python step.py', 'cd "$X" && python step.py']:
            self.assertIsNone(self.bash(command), command)
        self.assertTrue(self.denied(self.bash('cd analysis/demo && python step.py')))

    def test_literal_folder_options_are_gated_as_before(self):
        for command in ["env -C analysis/demo python step.py", "srun -D analysis/demo python step.py",
                        "conda run -n synthetic python analysis/x.py", "uv run --project . python analysis/x.py"]:
            reason = self.reason(command)
            self.assertNotIn("cannot resolve", reason, command)

    # GAP 2: one plan must name both sbatch and what --wrap runs

    SPLIT = ("run `analysis/x.py`", "submit with sbatch")

    def test_sbatch_wrap_with_the_parts_in_different_plans_is_denied(self):
        for step in self.SPLIT:
            self.approve(self.plan(step))
        reason = self.reason("sbatch --wrap='python analysis/x.py'")
        self.assertIn("one approved plan names both sbatch and what the payload runs", reason)
        self.assertIn("analysis/x.py", reason)
        self.assertEqual(self.launches_left(), [])

    def test_sbatch_wrap_with_one_plan_naming_both_is_allowed_and_credited(self):
        self.approve(self.plan("run `analysis/x.py`"))
        both = self.approve(self.plan("run `analysis/x.py` via sbatch --wrap"))
        self.approve(self.plan("submit with sbatch"))  # newer, names no script
        command = "sbatch --wrap='python analysis/x.py'"
        self.assertIsNone(self.tool(command, tool_use_id="t1"))
        record, = [self.read_launch(name) for name in self.launches_left()]
        plans = [e["plans"] for entries in record["runs"].values() for e in entries]
        self.assertIn([both], plans, "the sbatch segment's launch record credits only the plan naming both")
        self.post(command, tool_use_id="t1")
        receipt, = self.receipts()
        self.assertEqual(receipt["plans"], [both])

    def test_sbatch_without_a_wrap_and_with_a_read_only_wrap_are_unchanged(self):
        self.approve(self.plan("submit with sbatch job"))
        self.assertIsNone(self.bash("sbatch job.sh"))
        self.assertIsNone(self.bash("sbatch --wrap='echo hello'"))
        self.assertIsNone(self.bash("sbatch --wrap='cat analysis/x.py'"))
        self.assertTrue(self.denied(self.bash("sbatch --wrap='python analysis/x.py'")))

    def test_sbatch_wrap_in_a_job_folder_needs_one_plan_too(self):
        for step in ("run `analysis/a/x.py`", "submit with sbatch"):
            self.approve(self.plan(step))
        self.assertIn("names both", self.reason("sbatch -D analysis/a --wrap='python x.py'"))
        self.approve(self.plan("run `analysis/a/x.py` with sbatch"))
        self.assertIsNone(self.bash("sbatch -D analysis/a --wrap='python x.py'"))

    def launches_left(self):
        folder = self.path("launches")
        return sorted(n for n in os.listdir(folder) if n.endswith(".json")) if os.path.isdir(folder) else []

    def read_launch(self, name):
        with open(self.path("launches", name)) as handle:
            return json.load(handle)

    # GAP 3: a pending plan from before the `ready` field

    def legacy(self, **changes):
        digest = self.show(PLAN)
        entry, = self.pending()
        del entry["ready"]
        entry.update(changes)
        with open(self.path("pending", "s1.json"), "w") as handle:
            json.dump([entry], handle)
        return digest

    def test_a_complete_pending_entry_from_0_9_44_to_0_9_70_is_approvable(self):
        digest = self.legacy()  # `scripts` is there: those versions wrote it only after pinning
        self.assertIn("scripts", self.pending()[0])
        self.assertNotIn("(preparing)", self.prompt("approve plan"))
        self.assertIn("approved", self.prompt("approve plan " + digest))

    def test_a_pending_entry_saved_before_its_scripts_were_pinned_is_not_approvable(self):
        digest = self.legacy()
        entry, = self.pending()
        del entry["scripts"]  # what the first save of those versions held: hash, ts, text, pins
        with open(self.path("pending", "s1.json"), "w") as handle:
            json.dump([entry], handle)
        self.assertIn(digest + " (preparing)", self.prompt("approve plan"))
        self.assertIn("not fully prepared", self.prompt("approve plan " + digest))
        self.assertFalse(os.path.exists(self.path("approvals", digest + ".json")))
        self.assertEqual(self.show(PLAN), digest)  # showing it again prepares it
        self.assertIn("approved", self.prompt("approve plan " + digest))

    def test_an_entry_from_before_scripts_were_recorded_at_all_stays_approvable(self):
        digest = self.legacy(ts=1790000000)  # 2026-09-21: 0.9.43 or older wrote no `scripts` to any entry
        entry, = self.pending()
        del entry["scripts"]
        with open(self.path("pending", "s1.json"), "w") as handle:
            json.dump([entry], handle)
        self.assertIn("approved", self.prompt("approve plan " + digest))


class PlanComparisonAndPathsTest(unittest.TestCase):
    """C02 (F03): the card compares whole plan cells, removed and reordered rows before it shortens
    anything. C03 (F10): `Inputs:` and `Outputs:` read quoted literal paths exactly and say what they
    could not read instead of pinning a fragment."""
    entry = GATE
    setUp, tearDown, config, hook, approve, card, asked, write_file = (
        GateTest.setUp, GateTest.tearDown, GateTest.config, GateTest.hook, GateTest.approve,
        GateTest.card, GateTest.asked, GateTest.write_file)
    full = GateTest.full
    HEAD = ("#", "Step", "Choice", "Source", "Validation")

    def gate(self):
        sys.path.insert(0, os.path.dirname(GATE))
        import gate
        return gate

    def plan(self, rows, objective="Compare A with B.", inputs="data/in.tsv", outputs=None, head=HEAD, extra=()):
        parts = ["**Objective.** " + objective, "", "Inputs: " + inputs]
        parts += ["Outputs: " + outputs] if outputs else []
        parts += ["", "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
        parts += ["| " + " | ".join(row) + " |" for row in rows] + list(extra) + ["", "Plan status: READY"]
        return "\n".join(parts)

    def row(self, num="1", script="fit", choice="exact test", check="12 donors"):
        return (num, "Run `analysis/a/{}.py`".format(script), choice, "user", check)

    def files(self):
        for name in ("fit", "b"):
            self.write_file("analysis/a/{}.py".format(name), "print(1)\n")
        for name in ("in", "b"):
            self.write_file("data/{}.tsv".format(name), "x\n")

    # C02: what a changed plan reports

    def compared(self, old, new):
        """The card's `plan` line when `new` is shown after `old` was approved."""
        self.files()
        self.approve(old)
        card = self.card(new)
        return [line for line in card.splitlines() if line.startswith("  plan ")][0], card

    def test_a_changed_choice_after_a_long_shared_prefix_is_reported(self):
        shared = "selected specification " + "x" * 230
        old = self.plan([self.row(choice=shared + " exclude vaccinees")])
        line, _ = self.compared(old, self.plan([self.row(choice=shared + " include vaccinees")]))
        self.assertIn("steps: 0 same, 1 new or changed", line)
        self.assertEqual(self.compared(old, old)[0], "  plan     objective SAME · steps: 1 same, 0 new or changed")

    def test_a_removed_decision_or_validation_row_is_counted(self):
        decision = self.row("2", "b", "drop the outlier donors", "6 donors left")
        check = ("3", "Check the result has 60 rows", "", "user", "60 rows")
        old = self.plan([self.row(), decision, check])
        line, _ = self.compared(old, self.plan([self.row()]))
        self.assertIn("steps: 1 same, 0 new or changed, 2 removed", line)

    def test_a_removed_input_and_a_removed_output_are_shown(self):
        old = self.plan([self.row()], inputs="data/in.tsv, data/b.tsv", outputs="analysis/a/out/a.tsv, analysis/a/out/b.tsv")
        _, card = self.compared(old, self.plan([self.row()], outputs="analysis/a/out/a.tsv"))
        self.assertIn("  inputs   1 SAME, REMOVED: data/b.tsv", card)
        self.assertIn("  outputs  REMOVED: analysis/a/out/b.tsv", card)

    def test_reordered_steps_are_reported(self):
        first, second = self.row("1"), self.row("2", "b")
        line, _ = self.compared(self.plan([first, second]), self.plan([second, first]))
        self.assertIn("steps: 2 same, 0 new or changed, order changed", line)

    def test_a_long_changed_objective_is_reported(self):
        long = "Compare A with B. " + "y" * 300
        line, _ = self.compared(self.plan([self.row()], objective=long + " one"), self.plan([self.row()], objective=long + " two"))
        self.assertIn("objective CHANGED", line)

    def test_duplicate_ids_cannot_be_compared(self):
        old = self.plan([self.row("1"), self.row("1", "b")])
        line, _ = self.compared(old, old)
        self.assertIn("cannot compare: 2 rows with a repeated ID", line)
        self.assertNotIn("2 same", line)

    def test_an_ID_column_names_the_rows(self):
        head = ("ID", "Step", "Choice", "Source", "Validation")
        gate = self.gate()
        self.assertEqual([r["num"] for r in gate.plan_rows(self.plan([self.row("S1"), self.row("S2", "b")], head=head))],
                         ["S1", "S2"])
        # S1 changes its choice and moves: the row is found by its ID, not by its position
        old = self.plan([self.row("S1"), self.row("S2", "b")], head=head)
        line, _ = self.compared(old, self.plan([self.row("S2", "b"), self.row("S1", choice="permutation test")], head=head))
        self.assertIn("steps: 1 same, 1 new or changed, order changed", line)

    def test_a_change_of_whitespace_alone_is_the_same(self):
        old = self.plan([self.row(choice="exact  test")], objective="Compare A with B.")
        new = self.plan([self.row(choice=" exact\ttest ")], objective="Compare   A with B.")
        self.assertEqual(self.compared(old, new)[0], "  plan     objective SAME · steps: 1 same, 0 new or changed")

    def test_a_changed_validation_bindings_block_is_reported(self):
        block = '<!-- validation-bindings {"version": 1, "checks": []} -->'
        old = self.plan([self.row()], extra=["", block])
        changed = ('<!-- validation-bindings {"version": 1, "checks": [{"id": "V1", "plan_row": "1", "required": true, '
                   '"defined_by": "agent-proposed", "test_paths": ["data/in.tsv"], "invocation": ["python", '
                   '"analysis/a/fit.py"], "evidence_path": "analysis/a/out.json"}]} -->')  # a valid block: the gate now parses it
        _, card = self.compared(old, self.plan([self.row()], extra=["", changed]))
        self.assertIn("  blocks   validation-bindings CHANGED", card)
        _, card = self.compared(old, self.plan([self.row()]))
        self.assertIn("  blocks   validation-bindings REMOVED", card)

    def test_comparison_text_keeps_everything_but_control_characters_and_spacing(self):
        gate = self.gate()
        long = "x" * 500
        self.assertEqual(gate.comparison_text("a\x1b[31m  b\t\n`c`  " + long), "a b `c` " + long)

    # C03: literal paths

    def read(self, line, root=None):
        return self.gate().read_inputs("Inputs: " + line, root)

    def test_a_quoted_input_with_a_space_is_pinned_exactly(self):
        self.write_file("data/cohort samples.tsv", "sample\nA\n")
        self.write_file("data/cohort", "x\n")
        gate = self.gate()
        pins, outside = gate.pin_inputs(self.root, "Inputs: `data/cohort samples.tsv`", gate.load_config(self.root))
        self.assertEqual((sorted(pins), outside), (["data/cohort samples.tsv"], []))

    def test_quotes_commas_and_apostrophes_are_read_literally(self):
        for line, expected in [
            ("`data/cohort samples.tsv`", ["data/cohort samples.tsv"]),
            ("'data/cohort samples.tsv'.", ["data/cohort samples.tsv"]),
            ('"data/cohort samples.tsv"', ["data/cohort samples.tsv"]),
            ("`data/o'brien samples.tsv`", ["data/o'brien samples.tsv"]),
            ("\"data/o'brien.tsv\"", ["data/o'brien.tsv"]),
            ("'data/o'brien.tsv'", ["data/o'brien.tsv"]),
            ("`data/a,b.tsv`, \"data/c d.tsv\", data/e.tsv", ["data/a,b.tsv", "data/c d.tsv", "data/e.tsv"]),
            ("`/abs/dir/x y.tsv` and ./data/f.tsv", ["/abs/dir/x y.tsv", "and", "data/f.tsv"]),
        ]:
            words, notes = self.read(line)
            self.assertEqual((words, notes), (expected, []), line)

    def test_an_absolute_quoted_input_outside_the_repository_is_named_not_pinned(self):
        gate = self.gate()
        pins, outside = gate.pin_inputs(self.root, 'Inputs: "/abs/dir/x y.tsv"', gate.load_config(self.root))
        self.assertEqual((pins, outside), ({}, ["/abs/dir/x y.tsv"]))

    def test_unquoted_inputs_read_as_before(self):
        self.assertEqual(self.read("data/a.tsv, ./data/b.tsv (from the lab's freezer), ~/c.tsv.")[0],
                         ["data/a.tsv", "data/b.tsv", "from", "the", "lab", "s", "freezer", "~/c.tsv"])
        self.assertEqual(self.read("**data/a.tsv** and [notes](data/b.tsv)"), (["data/a.tsv", "and", "notes", "data/b.tsv"], []))

    def test_a_missing_exact_input_is_pinned_as_missing_not_as_a_fragment(self):
        self.write_file("data/cohort", "x\n")
        gate = self.gate()
        pins, _ = gate.pin_inputs(self.root, 'Inputs: "data/cohort samples.tsv"', gate.load_config(self.root))
        self.assertEqual(pins, {"data/cohort samples.tsv": {"missing": True}})

    def test_unsupported_input_expressions_are_diagnosed_and_pin_nothing(self):
        self.write_file("data/x.tsv", "x\n")
        self.write_file("data/cohort", "x\n")
        self.write_file("DATA/x.tsv", "x\n")
        gate = self.gate()
        for line in ["$DATA/x.tsv", "`$(ls data)/x.tsv`", "${DATA}/x.tsv", "`data/cohort samples.tsv",
                     '"data/cohort samples.tsv', "` `", "data/cohort\\ samples.tsv", "`data/x.tsv, data/y.tsv`", "*.tsv"]:
            pins, outside = gate.pin_inputs(self.root, "Inputs: " + line, gate.load_config(self.root))
            self.assertEqual((pins, outside), ({}, []), line)
            self.assertTrue(self.read(line, self.root)[1], line)

    def test_a_wildcard_or_brace_input_pins_its_folder_as_before(self):
        self.write_file("data/raw/a.csv", "x\n")
        gate = self.gate()
        for line in ["data/raw/*.csv", "data/raw/{a,b}.csv", "./data/raw/s*/x.csv"]:
            pins, outside = gate.pin_inputs(self.root, "Inputs: " + line, gate.load_config(self.root))
            self.assertEqual((sorted(pins), outside), (["data/raw"], []), line)
            self.assertIn("its folder `", self.read(line)[1][0], line)
        before = gate.pin_inputs(self.root, "Inputs: data/raw/*.csv", gate.load_config(self.root))[0]
        self.write_file("data/raw/a.csv", "changed\n")
        self.assertFalse(gate.unchanged(before["data/raw"], gate.pin_inputs(
            self.root, "Inputs: data/raw/*.csv", gate.load_config(self.root))[0]["data/raw"]))

    def test_a_quoted_name_that_looks_like_a_pattern_is_read_when_the_file_exists(self):
        self.write_file("data/s{1} a,b.tsv", "x\n")
        gate = self.gate()
        pins, _ = gate.pin_inputs(self.root, "Inputs: `data/s{1} a,b.tsv`", gate.load_config(self.root))
        self.assertEqual(sorted(pins), ["data/s{1} a,b.tsv"])
        self.assertTrue(gate.read_inputs("Inputs: `data/s{1} a,b.tsv`")[1])  # unknown to the reader without a folder

    def test_the_card_names_each_unread_input_and_output_on_one_line(self):
        self.files()
        shown = self.card(self.plan([self.row()], inputs="$DATA/x.tsv, `data/in.tsv, data/b.tsv`, data/*.tsv",
                                    outputs="$OUT/y.tsv"))
        card = self.asked(shown, "full")
        for each in (shown, card):
            lines = [line for line in each.splitlines() if "not read:" in line and "Shorthand" not in line]
            self.assertEqual(len(lines), 4, each)
            self.assertEqual([line.split(":")[0] for line in lines], ["Inputs not read"] * 3 + ["Outputs not read"])
        self.assertIn("Reads 1 pinned: data\n", card)  # the pattern's folder, as before 0.9.75

    def test_the_plain_card_names_unread_inputs_too(self):
        card = self.card(PLAN + "\nInputs: $DATA/x.tsv\n")
        self.assertIn("Inputs not read: `$DATA/x.tsv`", card)

    def test_quoted_outputs_are_read_literally(self):
        gate = self.gate()
        for line, expected in [
            ("`results/cohort samples.tsv`, \"results/o'brien.tsv\", results/a,b.csv", ["results/cohort samples.tsv", "results/o'brien.tsv", "results/a", "b.csv"]),
            ("`results/a,b.csv`", ["results/a,b.csv"]),
            ("'results/{x,y} z.tsv'", ["results/x z.tsv", "results/y z.tsv"]),
            ("`/abs/dir/o p.tsv`", ["/abs/dir/o p.tsv"]),
        ]:
            self.assertEqual(gate.read_outputs("Outputs: " + line)[0], expected, line)

    def test_brace_and_wildcard_outputs_are_unchanged(self):
        gate = self.gate()
        self.assertEqual(gate.read_outputs("Outputs: results/{sample}.tsv, out/{a,b}_{1,2}.rds, out/*.pdf, out/<name>.csv"),
                         (["results/*.tsv", "out/a_1.rds", "out/a_2.rds", "out/b_1.rds", "out/b_2.rds", "out/*.pdf", "out/*.csv"], []))
        self.assertEqual(gate.read_outputs("Outputs: `…_meta.csv`, ...x.csv"), ([], ["…_meta.csv", "...x.csv"]))
        self.assertEqual(gate.read_outputs("no outputs here"), (None, []))

    def test_unsupported_and_truncated_outputs_are_diagnosed_not_read_as_fragments(self):
        gate = self.gate()
        big = "x_{" + ",".join(str(i) for i in range(15)) + "}_{" + ",".join(str(i) for i in range(15)) + "}.tsv"
        for line in ["$OUT/y.tsv", "`$(pwd)/y.tsv`", "out/{a,b", "`out/y.tsv", big, "`out/a.tsv, out/b.tsv`"]:
            words, shorthand, notes = gate.read_outputs_notes("Outputs: " + line)
            self.assertEqual((words, shorthand), ([], []), line)
            self.assertEqual(len(notes), 1, line)


class AttemptEvidenceTest(unittest.TestCase):
    """C01/C04/C05 gate side: what a receipt may claim about its launch, attempt, approval and outputs."""
    entry = GATE
    setUp, tearDown, config, hook, bash, denied = (
        GateTest.setUp, GateTest.tearDown, GateTest.config, GateTest.hook, GateTest.bash, GateTest.denied)
    path, write, approval, pending, show, prompt, receipts, tool, post, expire, launches = (
        PreparationAndLaunchTest.path, PreparationAndLaunchTest.write, PreparationAndLaunchTest.approval,
        PreparationAndLaunchTest.pending, PreparationAndLaunchTest.show, PreparationAndLaunchTest.prompt,
        PreparationAndLaunchTest.receipts, PreparationAndLaunchTest.tool, PreparationAndLaunchTest.post,
        PreparationAndLaunchTest.expire, PreparationAndLaunchTest.launches)
    plan = staticmethod(ReviewFixesTest.plan)

    def approve(self, text=None, session="s1"):
        digest = self.show(text or self.plan("run `analysis/x.py`"), session)
        self.prompt("approve plan " + digest, session)
        return digest

    def launch_records(self):
        folder = self.path("launches")
        names = [n for n in sorted(os.listdir(folder)) if n.endswith(".json")] if os.path.isdir(folder) else []
        records = []
        for name in names:
            with open(os.path.join(folder, name)) as handle:
                records.append(json.load(handle))
        return records

    # F02: pins_checked needs a launch record for this very call

    def test_post_without_pre_does_not_claim_pins_checked(self):
        digest = self.approve()
        self.post()  # no PreToolUse hook saw this call
        receipt, = self.receipts()
        self.assertEqual(receipt["plans"], [digest], "a plan that covers it stays visible as context")
        self.assertFalse(receipt["pins_checked"])
        self.assertEqual(receipt["launch_match"], "unmatched")

    def test_a_post_that_follows_its_pre_claims_checked_pins(self):  # control
        digest = self.approve()
        self.assertIsNone(self.tool(tool_use_id="t1"))
        self.post(tool_use_id="t1")
        receipt, = self.receipts()
        self.assertEqual((receipt["plans"], receipt["pins_checked"], receipt["launch_match"]),
                         ([digest], True, "matched"))

    # C01: a run allowed although its folder was unresolved says so

    def test_an_allowed_run_with_an_unresolved_folder_carries_a_limitation(self):
        self.approve()
        command = 'env -C "$X" python analysis/x.py'  # covered by the repo-root reading
        self.assertIsNone(self.tool(command, tool_use_id="t1"))
        entry, = [e for r in self.launch_records() for es in r["runs"].values() for e in es]
        self.assertEqual(entry["limitations"], ["cwd unresolved: $X"])
        notice = self.post(command, tool_use_id="t1")
        receipt, = self.receipts()
        self.assertEqual(receipt["limitations"], ["cwd unresolved: $X"])
        self.assertIn("cwd unresolved: $X", notice["systemMessage"])

    def test_a_resolved_folder_has_no_limitation(self):  # control
        self.approve()
        self.assertIsNone(self.tool("env -C analysis python x.py", tool_use_id="t1"))
        notice = self.post("env -C analysis python x.py", tool_use_id="t1")
        receipt, = self.receipts()
        self.assertNotIn("limitations", receipt)
        self.assertNotIn("unresolved", notice["systemMessage"])

    # C04: attempts

    def age(self, path, seconds):
        old = time.time() - seconds
        os.utime(path, (old, old))

    def test_a_launch_record_and_its_receipt_share_an_attempt_id(self):
        self.approve()
        self.tool(tool_use_id="t1")
        self.tool(tool_use_id="t2")
        records = self.launch_records()
        ids = sorted(r["attempt_id"] for r in records)
        self.assertEqual(len(set(ids)), 2)
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{16}", i) for i in ids))
        first, = [r for r in records if r["call_id"] == "t1"]
        self.assertEqual((first["cwd"], isinstance(first["started"], float)), (".", True))
        self.post(tool_use_id="t1")
        receipt, = self.receipts()
        self.assertEqual((receipt["attempt_id"], receipt["call_id"], receipt["launch_match"]),
                         (first["attempt_id"], "t1", "matched"))

    def test_identical_launches_without_a_call_id_are_ambiguous_and_never_guessed(self):  # F05
        digest = self.approve()
        self.tool()
        self.tool()  # the same command again before the first one reported back
        record, = self.launch_records()
        self.assertTrue(record["ambiguous"])
        self.assertEqual(len(record["attempts"]), 2)
        self.assertEqual(len(set(a["attempt_id"] for a in record["attempts"])), 2)
        self.post()
        self.post()
        for receipt in self.receipts():
            self.assertEqual((receipt["launch_match"], receipt["pins_checked"], receipt["attempt_id"]),
                             ("ambiguous", False, None))
            self.assertEqual(receipt["plans"], [digest], "the covering plan stays visible as context")
            self.assertEqual(len(receipt["attempt_candidates"]), 2)
        self.assertEqual(self.launch_records(), [])

    def test_a_single_launch_without_a_call_id_is_matched(self):  # control
        self.approve()
        self.tool()
        self.post()
        receipt, = self.receipts()
        self.assertEqual((receipt["launch_match"], receipt["pins_checked"]), ("matched", True))
        self.assertTrue(receipt["attempt_id"])
        self.assertIsNone(receipt["call_id"])

    def test_parallel_identical_launches_with_call_ids_stay_matched(self):  # control
        self.approve()
        self.tool(tool_use_id="t1")
        self.tool(tool_use_id="t2")
        self.post(tool_use_id="t2")
        self.post(tool_use_id="t1")
        second, first = self.receipts()
        self.assertEqual((first["launch_match"], second["launch_match"]), ("matched", "matched"))
        self.assertTrue(first["pins_checked"] and second["pins_checked"])
        self.assertNotEqual(first["attempt_id"], second["attempt_id"])

    def test_a_duplicate_post_for_a_taken_call_id_is_unmatched(self):
        self.approve()
        self.tool(tool_use_id="t1")
        self.post(tool_use_id="t1")
        self.post(tool_use_id="t1")
        first, second = self.receipts()
        self.assertEqual(first["launch_match"], "matched")
        self.assertEqual((second["launch_match"], second["pins_checked"], second["attempt_id"]),
                         ("unmatched", False, None))
        self.assertIn("duplicate", second["launch_note"])

    def test_a_launch_that_never_reported_back_is_kept_as_abandoned(self):
        self.approve()
        self.tool(tool_use_id="t1")
        stale, = [n for n in os.listdir(self.path("launches")) if n.endswith(".json")]
        with open(self.path("launches", stale)) as handle:
            lost = json.load(handle)
        self.age(self.path("launches", stale), 3 * 24 * 3600)
        self.tool(tool_use_id="t2")
        self.assertFalse(os.path.exists(self.path("launches", stale)))
        kept = os.listdir(self.path("launches", "abandoned"))
        self.assertEqual(len(kept), 1)
        with open(self.path("launches", "abandoned", kept[0])) as handle:
            self.assertEqual(json.load(handle)["attempt_id"], lost["attempt_id"])
        self.post(tool_use_id="t1")  # a very late report finds nothing to match
        receipt, = self.receipts()
        self.assertEqual((receipt["launch_match"], receipt["pins_checked"]), ("unmatched", False))

    def test_a_launch_taken_after_its_expiry_is_unmatched_and_kept(self):
        self.approve()
        self.tool(tool_use_id="t1")
        name, = [n for n in os.listdir(self.path("launches")) if n.endswith(".json")]
        with open(self.path("launches", name)) as handle:
            record = json.load(handle)
        record["ts"] = time.time() - 3 * 24 * 3600
        with open(self.path("launches", name), "w") as handle:
            json.dump(record, handle)
        self.post(tool_use_id="t1")
        receipt, = self.receipts()
        self.assertEqual(receipt["launch_match"], "unmatched")
        self.assertEqual(len(os.listdir(self.path("launches", "abandoned"))), 1)

    def test_a_launch_record_without_attempt_fields_is_legacy_and_not_matched(self):
        digest = self.approve()
        self.tool(tool_use_id="t1")
        name, = [n for n in os.listdir(self.path("launches")) if n.endswith(".json")]
        with open(self.path("launches", name)) as handle:
            record = json.load(handle)
        for key in ("attempt_id", "call_id", "started", "cwd"):
            del record[key]
        with open(self.path("launches", name), "w") as handle:
            json.dump(record, handle)
        self.post(tool_use_id="t1")
        receipt, = self.receipts()
        self.assertEqual((receipt["launch_match"], receipt["pins_checked"], receipt["plans"]),
                         ("unmatched", False, [digest]))

    # C04: approval instances

    def instances(self, digest):
        folder = self.path("approval-instances", digest)
        out = {}
        for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
            with open(os.path.join(folder, name)) as handle:
                out[name[:-5]] = json.load(handle)
        return out

    def test_approval_writes_an_immutable_instance_and_names_it_in_the_approval(self):
        self.write("data/in.tsv", "a\n")
        digest = self.approve(self.plan("run `analysis/x.py`", "data/in.tsv"))
        (instance_id, instance), = self.instances(digest).items()
        self.assertEqual(self.approval(digest)["instance_id"], instance_id)
        self.assertEqual((instance["schema"], instance["instance_id"], instance["hash"], instance["prepared"],
                          instance["limitations"]), ("mycelium-extra.approval-instance.v1", instance_id, digest,
                                                     "complete", []))
        self.assertEqual(instance["pins"], self.approval(digest)["pins"])
        self.assertEqual(instance["scripts"], self.approval(digest)["scripts"])
        self.assertEqual(len(instance["plan_sha256"]), 64)
        self.assertTrue(instance["plan_sha256"].startswith(digest))
        self.assertEqual(instance["session_id"], "s1")
        self.assertTrue(re.fullmatch(r"[0-9a-f]{16}", instance_id))

    def test_same_prose_reapproval_while_a_run_is_active_keeps_both_instances(self):  # roadmap probe
        self.write("data/in.tsv", "first\n")
        text = self.plan("run `analysis/x.py`", "data/in.tsv")
        digest = self.approve(text)
        old, = self.instances(digest)
        old_pins = self.approval(digest)["pins"]
        self.assertIsNone(self.tool(tool_use_id="t1"))  # the run starts under the first freeze
        self.write("data/in.tsv", "second, longer\n")
        self.assertEqual(self.approve(text), digest)  # the same prose, new pins
        instances = self.instances(digest)
        self.assertEqual(len(instances), 2)
        new, = [i for i in instances if i != old]
        self.assertEqual(self.approval(digest)["instance_id"], new)
        self.assertNotEqual(instances[old]["pins"], instances[new]["pins"])
        self.assertEqual(instances[old]["pins"], old_pins, "the first freeze is untouched")
        self.post(tool_use_id="t1")
        receipt, = self.receipts()
        self.assertEqual((receipt["approval_instance"], receipt["pins"]), (old, old_pins))

    def test_identical_reapproval_reuses_the_instance(self):  # control
        self.write("data/in.tsv", "a\n")
        text = self.plan("run `analysis/x.py`", "data/in.tsv")
        digest = self.approve(text)
        first = self.approval(digest)
        self.approve(text)
        self.assertEqual(list(self.instances(digest)), [first["instance_id"]])
        self.assertEqual(self.approval(digest)["instance_id"], first["instance_id"])

    def test_a_receipt_names_the_instance_of_the_credited_plan(self):
        digest = self.approve()
        self.tool(tool_use_id="t1")
        self.post(tool_use_id="t1")
        receipt, = self.receipts()
        self.assertEqual(receipt["approval_instance"], self.approval(digest)["instance_id"])

    def test_an_approval_without_an_instance_id_is_legacy(self):
        digest = self.approve()
        record = self.approval(digest)
        del record["instance_id"]
        with open(self.path("approvals", digest + ".json"), "w") as handle:
            json.dump(record, handle)
        self.tool(tool_use_id="t1")
        self.post(tool_use_id="t1")
        receipt, = self.receipts()
        self.assertEqual((receipt["plans"], receipt["approval_instance"], receipt["pins_checked"]),
                         ([digest], None, True))

    def test_a_pending_entry_approved_by_the_legacy_rule_is_marked(self):
        digest = self.show(PLAN)
        entry, = self.pending()
        del entry["ready"]  # 0.9.44 to 0.9.70 wrote no `ready`; `scripts` marks a finished preparation
        with open(self.path("pending", "s1.json"), "w") as handle:
            json.dump([entry], handle)
        self.prompt("approve plan " + digest)
        (_, instance), = self.instances(digest).items()
        self.assertEqual(instance["prepared"], "legacy-no-ready")
        self.assertTrue(instance["limitations"])
        self.assertIn("readiness", instance["limitations"][0])

    def test_pins_that_are_not_content_hashes_are_listed_as_limitations(self):
        self.write("data/in.tsv", "a\n")
        digest = self.approve(self.plan("run `analysis/x.py`", "data/in.tsv"))
        (_, instance), = self.instances(digest).items()
        self.assertEqual(instance["limitations"], [])
        self.config({"pin_hash_mb": 0})  # nothing may be hashed: size and mtime only
        self.write("data/in.tsv", "b\n")
        digest = self.approve(self.plan("run `analysis/x.py`", "data/in.tsv"))
        weak = [i for i in self.instances(digest).values() if i["limitations"]]
        self.assertEqual(len(weak), 1)
        self.assertIn("data/in.tsv", weak[0]["limitations"][0])

    # C04: concurrency hygiene

    def gate(self):
        sys.dont_write_bytecode = True
        sys.path.insert(0, os.path.dirname(GATE))
        import gate
        return gate

    def test_snapshots_of_parallel_hooks_do_not_share_a_temp_file(self):
        gate = self.gate()
        self.write("analysis/x.py", "print(1)\n")
        pin = gate.fingerprint(os.path.join(self.root, "analysis", "x.py"), gate.hash_budget(gate.DEFAULTS))
        real, inner = os.replace, []

        def other_hook_finishes_first(source, target):
            if not inner:
                inner.append(source)
                gate.keep_snapshot(self.root, "analysis/x.py", pin)
            real(source, target)

        with mock.patch.object(gate.os, "replace", side_effect=other_hook_finishes_first):
            gate.keep_snapshot(self.root, "analysis/x.py", pin)  # raised FileNotFoundError on the shared <hash>.tmp
        with open(self.path("scripts", pin["sha256"]), "rb") as handle:
            self.assertEqual(handle.read(), b"print(1)\n")
        self.assertEqual(os.listdir(self.path("scripts")), [pin["sha256"]], "no temp file is left behind")

    def test_first_run_pins_of_parallel_hooks_are_both_kept(self):
        gate = self.gate()
        for name in ("a", "b"):
            self.write("analysis/{}.py".format(name), name + "\n")
        budget = gate.hash_budget(gate.DEFAULTS)
        real, calls = gate.fingerprint, []

        def other_hook_finishes_first(path, budget_, pin=None):
            found = real(path, budget_, pin)
            if not calls:
                calls.append(path)
                gate.note_first_runs(self.root, [("deadbeef", "analysis/b.py")], budget)
            return found

        with mock.patch.object(gate, "fingerprint", side_effect=other_hook_finishes_first):
            gate.note_first_runs(self.root, [("deadbeef", "analysis/a.py")], budget)
        with open(self.path("script-pins", "deadbeef.json")) as handle:
            self.assertEqual(sorted(json.load(handle)), ["analysis/a.py", "analysis/b.py"])

    # C05 gate side: declared outputs observed around each launch

    OUT = "analysis/out/r.csv"

    def with_outputs(self, *words, **kwargs):
        step = kwargs.get("step", "run `analysis/x.py`")
        return "Outputs: {}\n\n".format(", ".join(words)) + self.plan(step)

    def out_receipt(self, run=None, command="python analysis/x.py", **event):
        """Launch, run `run()` between the hooks, report back: the one receipt."""
        self.assertIsNone(self.tool(command, tool_use_id="t1", **event))
        if run:
            run()
        self.post(command, tool_use_id="t1", **event)
        receipt, = self.receipts()
        return receipt

    def test_a_changed_output_is_observed(self):
        self.write(self.OUT, "a\n")
        self.approve(self.with_outputs(self.OUT))
        self.assertIsNone(self.tool(tool_use_id="t1"))
        entry, = [e for r in self.launch_records() for es in r["runs"].values() for e in es]
        self.assertEqual(sorted(entry["outputs_before"]), [self.OUT])
        size, mtime_ns = entry["outputs_before"][self.OUT]
        self.assertEqual((size, isinstance(mtime_ns, int)), (2, True))
        self.write(self.OUT, "a longer table\n")
        self.post(tool_use_id="t1")
        receipt, = self.receipts()
        self.assertEqual(receipt["outputs_observation"], "observed")
        self.assertEqual(receipt["outputs_changed"], {"created": [], "changed": [self.OUT], "deleted": []})

    def test_a_created_and_a_deleted_output_are_observed(self):
        self.write("analysis/out/gone.csv", "x\n")
        self.approve(self.with_outputs(self.OUT, "analysis/out/gone.csv"))
        receipt = self.out_receipt(lambda: (self.write(self.OUT, "new\n"), os.remove(
            os.path.join(self.root, "analysis/out/gone.csv"))))
        self.assertEqual(receipt["outputs_changed"], {"created": [self.OUT], "changed": [],
                                                      "deleted": ["analysis/out/gone.csv"]})
        self.assertEqual(receipt["outputs_observation"], "observed")

    def test_an_untouched_pre_existing_output_is_not_reported_changed(self):  # control
        self.write(self.OUT, "a\n")
        self.write("analysis/out/other.csv", "b\n")
        self.approve(self.with_outputs(self.OUT, "analysis/out/other.csv"))
        receipt = self.out_receipt(lambda: self.write("analysis/out/other.csv", "bb changed\n"))
        self.assertEqual(receipt["outputs_changed"], {"created": [], "changed": ["analysis/out/other.csv"],
                                                      "deleted": []})
        self.assertNotIn(self.OUT, json.dumps(receipt["outputs_changed"]))

    def test_nothing_written_is_an_observation_of_no_change(self):
        self.write(self.OUT, "a\n")
        self.approve(self.with_outputs(self.OUT))
        receipt = self.out_receipt()
        self.assertEqual((receipt["outputs_observation"], receipt["outputs_changed"]),
                         ("observed", {"created": [], "changed": [], "deleted": []}))

    def test_a_glob_sees_a_new_file_and_not_an_untouched_one(self):
        self.write("analysis/out/old.csv", "o\n")
        self.approve(self.with_outputs("analysis/out/*.csv"))
        receipt = self.out_receipt(lambda: self.write("analysis/out/new.csv", "n\n"))
        self.assertEqual(receipt["outputs_changed"], {"created": ["analysis/out/new.csv"], "changed": [],
                                                      "deleted": []})

    def test_a_glob_over_too_many_files_is_skipped_not_scanned_on(self):
        for i in range(201):
            self.write("analysis/out/f{}.csv".format(i), "x\n")
        self.approve(self.with_outputs("analysis/out/*.csv"))
        receipt = self.out_receipt(lambda: self.write("analysis/out/f0.csv", "changed\n"))
        self.assertTrue(receipt["outputs_observation"].startswith("skipped: cap reached"), receipt)
        self.assertNotIn("outputs_changed", receipt)

    def test_a_recursive_glob_is_not_expanded(self):
        self.approve(self.with_outputs("analysis/**/r.csv"))
        receipt = self.out_receipt()
        self.assertTrue(receipt["outputs_observation"].startswith("skipped: pattern with **"), receipt)

    def test_an_unmatched_launch_skips_the_observation(self):
        self.write(self.OUT, "a\n")
        self.approve(self.with_outputs(self.OUT))
        self.post()  # no pre hook, so nothing was snapshotted
        receipt, = self.receipts()
        self.assertEqual(receipt["outputs_observation"], "skipped: unmatched launch")
        self.assertNotIn("outputs_changed", receipt)

    def test_a_plan_without_outputs_skips_the_observation(self):
        self.approve()
        receipt = self.out_receipt()
        self.assertEqual(receipt["outputs_observation"], "skipped: no declared outputs")
        self.assertNotIn("outputs_changed", receipt)

    def test_a_job_submission_and_a_compound_call_skip_the_observation(self):
        self.write("job.sh", "#!/bin/bash\necho hi\n")
        self.approve(self.with_outputs(self.OUT, step="run `analysis/x.py` with sbatch job.sh"))
        receipt = self.out_receipt(command="sbatch job.sh")
        self.assertTrue(receipt["outputs_observation"].startswith("skipped: job submission"), receipt)
        compound = "python analysis/x.py; python analysis/x.py"
        self.assertIsNone(self.tool(compound, tool_use_id="t2"))
        self.post(compound, tool_use_id="t2")
        for receipt in self.receipts()[1:]:
            self.assertEqual(receipt["outputs_observation"], "skipped: compound shell command")

    # C01: a gate error says which call it was

    def errors(self):
        path = self.path("gate-errors.jsonl")
        if not os.path.isfile(path):
            return []
        with open(path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle]

    def run_entry(self, entry, args, payload):
        proc = subprocess.Popen([sys.executable, entry] + args, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate(payload.encode("utf-8") if isinstance(payload, str)
                                    else json.dumps(payload).encode("utf-8"))
        self.assertEqual(proc.returncode, 0, err)
        return json.loads(out.decode("utf-8"))

    BROKEN = {"gated_commands": 5, "gated_paths": 5}  # the tool handler raises on a config it cannot read

    def test_a_gate_error_records_event_decision_host_session_and_call(self):
        for entry in (GATE, LAUNCHER):
            self.config(self.BROKEN)
            payload = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "tool_use_id": "t9",
                       "session_id": "sX", "cwd": self.root}
            reply = self.run_entry(entry, ["tool"], payload)
            self.assertFalse(self.denied(reply))
            self.config(dict(self.BROKEN, on_error="deny"))
            self.assertTrue(self.denied(self.run_entry(entry, ["tool"], payload)))
        allowed, denied, allowed_again, denied_again = self.errors()
        for record, decision in ((allowed, "allow"), (denied, "deny"), (allowed_again, "allow"), (denied_again, "deny")):
            self.assertEqual((record["event"], record["decision"], record["session_id"], record["call_id"],
                              record["host"]), ("tool", decision, "sX", "t9", None))
            self.assertIn("ts", record)
            self.assertIn("error", record)

    def test_a_codex_gate_error_names_its_host_thread_and_call(self):
        self.config(self.BROKEN)
        payload = {"tool_name": "shell", "tool_input": {"command": ["ls"]}, "tool_use_id": "c1",
                   "thread_id": "th1", "cwd": self.root}
        self.run_entry(LAUNCHER, ["--host", "codex", "tool"], payload)
        record, = self.errors()
        self.assertEqual((record["host"], record["session_id"], record["call_id"]), ("codex", "th1", "c1"))

    def test_an_unreadable_event_records_unknown_identity(self):
        self.config({})
        proc = subprocess.Popen([sys.executable, LAUNCHER, "tool"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, cwd=self.root)
        proc.communicate(b"{not json")
        record, = self.errors()
        self.assertEqual((record["event"], record["session_id"], record["call_id"], record["host"]),
                         ("tool", None, None, None))

    def test_a_gate_that_cannot_load_still_records_identity(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        hooks = os.path.join(folder, "hooks")
        os.makedirs(hooks)
        shutil.copy(LAUNCHER, hooks)
        with open(os.path.join(hooks, "gate.py"), "w") as broken:
            broken.write("def main(:\n")
        payload = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "tool_use_id": "t5",
                   "session_id": "sY", "cwd": self.root}
        self.run_entry(os.path.join(hooks, "gate_run.py"), ["tool"], payload)
        self.run_entry(os.path.join(hooks, "gate_run.py"), ["--host", "codex", "tool"], payload)
        claude, codex = self.errors()
        self.assertEqual((claude["session_id"], claude["call_id"], claude["host"]), ("sY", "t5", None))
        self.assertEqual((codex["session_id"], codex["call_id"], codex["host"]), ("sY", "t5", "codex"))

    def test_a_log_that_cannot_be_written_leaves_no_record_and_says_so(self):
        self.config(self.BROKEN)
        os.makedirs(self.path("gate-errors.jsonl"))  # a folder cannot be appended to
        reply = self.run_entry(GATE, ["tool"], {"tool_name": "Bash", "tool_input": {"command": "ls"},
                                                "session_id": "sX", "cwd": self.root})
        self.assertFalse(self.denied(reply))
        self.assertIn("could not be recorded", reply["systemMessage"])
        self.assertEqual(os.listdir(self.path("gate-errors.jsonl")), [])


class ValidationBindingsTest(unittest.TestCase):
    """C06 gate side: `validation-bindings` are validated before a plan is approvable, their files pinned and
    shown, a changed expectation denies a covered run, and a matching invocation is recorded in the launch."""
    entry = GATE
    setUp, tearDown, config, hook, bash, denied = (
        GateTest.setUp, GateTest.tearDown, GateTest.config, GateTest.hook, GateTest.bash, GateTest.denied)
    path, write, approval, pending, prompt, receipts, tool, post = (
        PreparationAndLaunchTest.path, PreparationAndLaunchTest.write, PreparationAndLaunchTest.approval,
        PreparationAndLaunchTest.pending, PreparationAndLaunchTest.prompt, PreparationAndLaunchTest.receipts,
        PreparationAndLaunchTest.tool, PreparationAndLaunchTest.post)
    launch_records = AttemptEvidenceTest.launch_records
    TABLE = ("## Plan\n| # | Step | Choice | Source | Validation |\n|---|---|---|---|---|\n"
             "| 1 | run `analysis/x/fit.py` | model A | user | rows |\n"
             "| 2 | run `analysis/x/tests/check.py` | acceptance check | user | passes |\n\n")
    EXPECT = "analysis/x/tests/expect.tsv"

    def check(self, **changes):
        base = {"id": "V1", "plan_row": "2", "required": True, "defined_by": "researcher-approved",
                "test_paths": [self.EXPECT], "invocation": ["python", "analysis/x/tests/check.py"],
                "evidence_path": "analysis/x/outputs/check.json"}
        base.update(changes)
        return dict((k, v) for k, v in base.items() if v is not None)

    def plan(self, *checks, **top):
        block = "<!-- validation-bindings {} -->\n\n".format(json.dumps(dict({"version": 1, "checks": list(checks)}, **top)))
        return self.TABLE + block + "Plan status: READY"

    def setup_files(self):
        self.write(self.EXPECT, "rows\n24\n")
        self.write("analysis/x/fit.py", "pass\n")
        self.write("analysis/x/tests/check.py", "pass\n")

    def show(self, text):
        notice = self.hook("stop", {"last_assistant_message": text})["systemMessage"]
        return notice

    def approved(self, text):
        notice = self.show(text)
        digest = notice.split("approve plan ")[1][:8]
        self.prompt("approve plan " + digest)
        return digest, notice

    def test_a_valid_block_is_pinned_shown_and_frozen_into_the_instance(self):
        self.setup_files()
        digest, card = self.approved(self.plan(self.check()))
        self.assertIn("V1", card)
        self.assertIn("row 2", card)
        self.assertIn("required", card)
        self.assertIn("declared by researcher-approved", card)
        self.assertIn("1 test file pinned", card)
        record = self.approval(digest)
        one, = record["validation"]["checks"]
        self.assertEqual(sorted(one["files"]), [self.EXPECT])
        self.assertEqual(len(one["definition_sha256"]), 64)
        instance, = os.listdir(self.path("approval-instances", digest))
        with open(self.path("approval-instances", digest, instance)) as handle:
            frozen = json.load(handle)
        self.assertEqual(frozen["validation"], record["validation"])
        self.assertEqual(frozen["instance_id"], record["instance_id"])

    def test_a_plan_without_the_block_is_unchanged(self):  # control
        self.setup_files()
        digest, card = self.approved(self.TABLE + "Plan status: READY")
        self.assertNotIn("Validation bindings", card)
        self.assertNotIn("validation", self.approval(digest))
        instance, = os.listdir(self.path("approval-instances", digest))
        with open(self.path("approval-instances", digest, instance)) as handle:
            self.assertNotIn("validation", json.load(handle))

    def invalid(self, text, expected):
        self.setup_files()
        notice = self.show(text)
        self.assertNotIn("approve plan ", notice)
        self.assertIn(expected, notice)
        entry, = self.pending()
        self.assertFalse(entry["ready"])
        self.assertTrue(entry["invalid"])
        reply = self.prompt("approve plan " + entry["hash"])
        self.assertIn("Nothing was approved", reply)
        self.assertIn("Fix the block", reply)
        self.assertFalse(os.path.exists(self.path("approvals", entry["hash"] + ".json")))
        self.assertTrue(self.denied(self.bash("python analysis/x/fit.py")))

    def test_an_invalid_block_is_not_approvable(self):
        self.invalid(self.plan(self.check(plan_row="9")), "unknown plan row 9")

    def test_a_missing_test_file_is_not_approvable(self):
        self.invalid(self.plan(self.check(test_paths=["analysis/x/tests/nope.tsv"])), "cannot be pinned")

    def test_an_unsafe_path_is_not_approvable(self):
        self.invalid(self.plan(self.check(test_paths=["../outside.tsv"])), "leaves the repository")

    def test_an_unsupported_version_is_not_approvable(self):
        self.invalid(self.plan(self.check(), version=2), "unsupported version")

    def test_a_duplicate_check_id_is_not_approvable(self):
        self.invalid(self.plan(self.check(), self.check(plan_row="1")), "duplicate check id")

    def test_malformed_json_is_not_approvable(self):
        self.invalid(self.TABLE + "<!-- validation-bindings {oops} -->\n\nPlan status: READY", "not valid JSON")

    def test_a_corrected_block_is_approvable_again(self):
        self.setup_files()
        self.show(self.plan(self.check(plan_row="9")))
        digest, _ = self.approved(self.plan(self.check()))
        self.assertTrue(os.path.isfile(self.path("approvals", digest + ".json")))

    def test_a_changed_pinned_expectation_denies_a_covered_run_until_the_plan_is_approved_again(self):
        self.setup_files()
        digest, _ = self.approved(self.plan(self.check()))
        self.assertIsNone(self.tool("python analysis/x/fit.py"))
        self.write(self.EXPECT, "rows\n7\n")  # the expectation is edited to excuse the analysis
        result = self.tool("python analysis/x/fit.py")
        self.assertTrue(self.denied(result))
        reason = result["hookSpecificOutput"]["permissionDecisionReason"]
        for text in ("V1", self.EXPECT, "changed", digest, "shown and approved again"):
            self.assertIn(text, reason)
        self.assertTrue(self.denied(self.tool("python analysis/x/tests/check.py")))
        digest2, _ = self.approved(self.plan(self.check()))  # shown again: the new bytes are pinned
        self.assertEqual(digest2, digest)
        self.assertIsNone(self.tool("python analysis/x/fit.py"))

    def test_a_deleted_pinned_expectation_denies_too(self):
        self.setup_files()
        self.approved(self.plan(self.check()))
        os.remove(os.path.join(self.root, self.EXPECT))
        reason = self.tool("python analysis/x/fit.py")["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("missing", reason)

    def test_the_evidence_file_and_unrelated_files_may_change_between_runs(self):  # control
        self.setup_files()
        self.approved(self.plan(self.check()))
        self.assertIsNone(self.tool("python analysis/x/tests/check.py", tool_use_id="t1"))
        self.write("analysis/x/outputs/check.json", '{"rows": 24}')  # what the check writes
        self.write("analysis/x/notes.md", "unrelated edit\n")
        self.assertIsNone(self.tool("python analysis/x/tests/check.py", tool_use_id="t2"))
        self.write("analysis/x/outputs/check.json", '{"rows": 25}')
        self.assertIsNone(self.tool("python analysis/x/fit.py", tool_use_id="t3"))

    def test_a_run_of_the_checks_invocation_records_the_check_in_its_launch_and_receipt(self):
        self.setup_files()
        self.approved(self.plan(self.check()))
        self.assertIsNone(self.tool("python analysis/x/tests/check.py", tool_use_id="t1"))
        self.assertIsNone(self.tool("python analysis/x/fit.py", tool_use_id="t2"))
        self.assertIsNone(self.tool("python analysis/x/tests/check.py --extra", tool_use_id="t3"))
        launched = dict((r["call_id"], [e for es in r["runs"].values() for e in es][0]) for r in self.launch_records())
        self.assertEqual(launched["t1"]["validation_check"], "V1")
        self.assertNotIn("validation_check", launched["t2"])
        self.assertNotIn("validation_check", launched["t3"], "another argv is not the declared invocation")
        self.post("python analysis/x/tests/check.py", tool_use_id="t1")
        receipt, = self.receipts()
        self.assertEqual((receipt["validation_check"], receipt["launch_match"]), ("V1", "matched"))

    def test_an_invocation_under_an_ungated_folder_is_flagged_on_the_card(self):
        self.setup_files()
        self.write("tests/check.py", "pass\n")
        card = self.show(self.plan(self.check(invocation=["python", "tests/check.py"])))
        self.assertIn("not gated", card)
        self.assertIn("gated_paths", card)

    def test_an_invocation_the_plan_table_does_not_name_is_flagged_on_the_card(self):
        self.setup_files()
        self.write("analysis/x/tests/other.py", "pass\n")
        card = self.show(self.plan(self.check(invocation=["python", "analysis/x/tests/other.py"])))
        self.assertIn("not named in the plan table", card)
        named = self.show(self.plan(self.check()))
        self.assertNotIn("not named in the plan table", named)
        self.assertNotIn("not gated", named)


class ExactExecutionTest(unittest.TestCase):
    """C07 / F09 gate side: a plan's `exact-execution` block holds a covered run to its declared argv, folder and
    inline variables, except the flags it lists as operational; plans without the block keep a broad grant."""
    entry = GATE
    setUp, tearDown, config, hook, bash, denied = (
        GateTest.setUp, GateTest.tearDown, GateTest.config, GateTest.hook, GateTest.bash, GateTest.denied)
    path, write, approval, pending, prompt, receipts, tool, post = (
        PreparationAndLaunchTest.path, PreparationAndLaunchTest.write, PreparationAndLaunchTest.approval,
        PreparationAndLaunchTest.pending, PreparationAndLaunchTest.prompt, PreparationAndLaunchTest.receipts,
        PreparationAndLaunchTest.tool, PreparationAndLaunchTest.post)
    launch_records = AttemptEvidenceTest.launch_records
    TABLE = ("## Plan\n| # | Step | Choice | Source | Validation |\n|---|---|---|---|---|\n"
             "| 1 | run `analysis/x/fit.py` | model A | user | rows |\n"
             "| 2 | run `analysis/x/plot.py` | figure | user | renders |\n\n")
    FIT = ["python", "analysis/x/fit.py", "--model", "original", "--threads", "4"]
    DECLARED = "python analysis/x/fit.py --model original --threads 4"

    def step(self, **changes):
        base = {"row": "1", "argv": self.FIT, "cwd": ".", "env": {}, "operational": ["--threads"]}
        base.update(changes)
        return base

    def plan(self, *steps, **top):
        block = "<!-- exact-execution {} -->\n\n".format(json.dumps(dict({"version": 1, "steps": list(steps)}, **top)))
        return self.TABLE + block + "Plan status: READY"

    def show(self, text):
        return self.hook("stop", {"last_assistant_message": text})["systemMessage"]

    def approved(self, text):
        notice = self.show(text)
        digest = notice.split("approve plan ")[1][:8]
        self.prompt("approve plan " + digest)
        return digest, notice

    def reason(self, result):
        self.assertTrue(self.denied(result), result)
        return result["hookSpecificOutput"]["permissionDecisionReason"]

    def setUp(self):  # noqa: F811
        GateTest.setUp(self)
        for name in ("fit", "plot"):
            self.write("analysis/x/{}.py".format(name), "pass\n")

    def test_a_changed_analytical_argument_is_denied_for_a_frozen_step(self):  # the roadmap probe, F09
        self.approved(self.plan(self.step()))
        reason = self.reason(self.tool(self.DECLARED.replace("original", "alternative")))
        self.assertIn("declared: " + self.DECLARED, reason)
        self.assertIn("actual:   python analysis/x/fit.py --model alternative --threads 4", reason)
        self.assertIn("--threads", reason)  # what an operational retry may change
        self.assertIn("operational", reason)
        self.assertIn("researcher", reason)

    def test_the_declared_command_and_its_operational_variants_are_allowed(self):  # control
        self.approved(self.plan(self.step()))
        for command in (self.DECLARED, "python analysis/x/fit.py --model original --threads 16",
                        "python analysis/x/fit.py --model original",
                        "python analysis/x/fit.py --model original --threads=8",
                        "python ./analysis/x/fit.py --model original --threads 4",
                        self.DECLARED + " > fit.log 2>&1",
                        "conda run -n env1 " + self.DECLARED,
                        "timeout 600 " + self.DECLARED):
            self.assertIsNone(self.tool(command), command)

    def test_every_other_change_is_denied(self):
        self.approved(self.plan(self.step()))
        for command in ("python analysis/x/fit.py --model original --threads 4 --alpha 0.1",
                        "python analysis/x/fit.py --threads 4",
                        "python analysis/x/fit.py --model original --threads 4 extra.tsv",
                        "python analysis/x/fit.py --model original --verbose extra.tsv",
                        "python analysis/x/fit.py --model original --threads 4 < other.tsv",
                        "python3 analysis/x/fit.py --model original --threads 4",
                        "cd analysis/x && python fit.py --model original --threads 4"):
            self.assertTrue(self.denied(self.tool(command)), command)

    def test_a_substitution_or_an_unresolved_folder_cannot_satisfy_a_frozen_step(self):
        self.approved(self.plan(self.step()))
        self.assertIn("substitution", self.reason(self.tool("python analysis/x/fit.py --model $(cat model.txt)")))
        self.assertIn("substitution", self.reason(self.tool("python analysis/x/fit.py --model $MODEL")))
        reason = self.reason(self.tool('env -C "$WORK" ' + self.DECLARED))
        self.assertIn("unresolved", reason)
        self.assertIn("$WORK", reason)

    def test_inline_variables_must_be_declared(self):
        self.approved(self.plan(self.step(env={"SEED": "1"})))
        self.assertIsNone(self.tool("SEED=1 " + self.DECLARED))
        self.assertIsNone(self.tool(self.DECLARED))
        self.assertIn("SEED=2", self.reason(self.tool("SEED=2 " + self.DECLARED)))
        self.assertTrue(self.denied(self.tool("OTHER=1 " + self.DECLARED)))

    def test_a_step_with_a_declared_folder(self):
        self.write("analysis/x/run.R", "1\n")
        text = self.TABLE.replace("analysis/x/plot.py", "analysis/x/run.R")
        block = {"version": 1, "steps": [{"row": "1", "argv": ["Rscript", "run.R", "--n", "3"], "cwd": "analysis/x"}]}
        self.approved(text + "<!-- exact-execution {} -->\n\nPlan status: READY".format(json.dumps(block)))
        self.assertIsNone(self.tool("cd analysis/x && Rscript run.R --n 3"))
        self.assertIsNone(self.tool("env -C analysis/x Rscript run.R --n 3"))
        self.assertIn("folder differs", self.reason(self.tool("Rscript analysis/x/run.R --n 3")))
        self.assertTrue(self.denied(self.tool("cd analysis/x && Rscript run.R --n 4")))

    def test_the_launch_and_the_receipt_record_the_exact_match(self):
        self.approved(self.plan(self.step()))
        self.assertIsNone(self.tool(self.DECLARED, tool_use_id="t1"))
        self.assertIsNone(self.tool("python analysis/x/plot.py --dpi 300", tool_use_id="t2"))  # no step names it
        launched = dict((r["call_id"], [e for es in r["runs"].values() for e in es][0]) for r in self.launch_records())
        self.assertEqual((launched["t1"]["exact_match"], launched["t1"]["exact_step"]), (True, "1"))
        self.assertIs(launched["t2"]["exact_match"], False)
        self.assertNotIn("exact_step", launched["t2"])
        self.post(self.DECLARED, tool_use_id="t1")
        self.post("python analysis/x/plot.py --dpi 300", tool_use_id="t2")
        one, two = self.receipts()
        self.assertEqual((one["exact_match"], one["exact_step"]), (True, "1"))
        self.assertIs(two["exact_match"], False)
        self.assertNotIn("exact_step", two)

    def test_a_plan_without_the_block_keeps_a_broad_grant_and_says_so(self):  # the probe's plain form
        digest, card = self.approved(self.TABLE.replace("run `analysis/x/fit.py`",
                                                         "run `python analysis/x/fit.py --model original`")
                                     + "Plan status: READY")
        self.assertIn("2 scripts (2 pinned) \u00b7 any arguments", card)  # the compact card still says so
        self.assertNotIn("exact:", card)
        self.assertIsNone(self.tool("python analysis/x/fit.py --model alternative", tool_use_id="t1"))
        self.post("python analysis/x/fit.py --model alternative", tool_use_id="t1")
        receipt, = self.receipts()
        self.assertNotIn("exact_match", receipt)
        self.assertNotIn("execution", self.approval(digest))

    def test_the_card_shows_each_declared_step_and_the_rest_as_broad(self):
        digest, card = self.approved(self.plan(self.step(), self.step(
            row="2", argv=["python", "analysis/x/plot.py"], env={"SEED": "1"})))
        self.assertIn("exact: row 1: " + self.DECLARED, card)
        self.assertIn("exact: row 2: python analysis/x/plot.py", card)
        self.assertIn("free flags: --threads", card)
        self.assertIn("SEED=1", card)
        self.assertIn("exact where listed", card)
        self.assertIn("broad grant: any arguments", card)
        record = self.approval(digest)
        self.assertEqual(record["execution"]["steps"][0]["argv"], self.FIT)
        instance, = os.listdir(self.path("approval-instances", digest))
        with open(self.path("approval-instances", digest, instance)) as handle:
            self.assertEqual(json.load(handle)["execution"], record["execution"])

    def test_an_exact_step_narrows_a_grant_and_never_widens_it(self):
        self.approved(self.plan(self.step(argv=["python", "analysis/x/other.py"])))
        self.write("analysis/x/other.py", "pass\n")
        self.assertTrue(self.denied(self.tool("python analysis/x/other.py")), "the table names only fit.py and plot.py")

    def invalid(self, text, expected):
        notice = self.show(text)
        self.assertIn(expected, notice)
        self.assertNotIn("approve plan ", notice)
        entry, = self.pending()
        self.assertFalse(entry["ready"])
        self.assertIn("Nothing was approved", self.prompt("approve plan " + entry["hash"]))

    def test_an_invalid_exact_block_is_not_approvable(self):
        self.invalid(self.plan(self.step(row="9")), "unknown plan row 9")

    def test_an_exact_block_with_a_substitution_is_not_approvable(self):
        self.invalid(self.plan(self.step(argv=["python", "analysis/x/fit.py", "$SEED"])), "substitution")

    def test_an_exact_block_with_an_unknown_key_is_not_approvable(self):
        self.invalid(self.plan(self.step(), shell="bash"), "unknown key shell")


class ReviewConsentPromptTest(unittest.TestCase):
    """C11 gate side: only the user's own prompt `send packet <digest prefix>` records consent to send a prepared
    review packet, and `review_packet.py verify` accepts that record."""
    entry = GATE
    setUp, tearDown, config, hook = GateTest.setUp, GateTest.tearDown, GateTest.config, GateTest.hook
    path = PreparationAndLaunchTest.path
    SCRIPT = os.path.join(os.path.dirname(GATE), "..", "skills", "plan-review", "scripts", "review_packet.py")

    def review_packet(self, *args):
        proc = subprocess.Popen([sys.executable, self.SCRIPT] + list(args) + ["--root", self.root],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate()
        return proc.returncode, (out + err).decode("utf-8")

    def prepared(self):
        packet = os.path.join(self.root, "packet-draft.txt")
        with open(packet, "w") as handle:
            handle.write('objective: "Test the day 28 change"\nredactions: []\n')
        code, out = self.review_packet("prepare", "--packet", packet)
        self.assertEqual(code, 0, out)
        return re.search(r"^digest: ([0-9a-f]{64})$", out, re.MULTILINE).group(1)

    def consent_files(self):
        folder = self.path("review-consent")
        return sorted(os.listdir(folder)) if os.path.isdir(folder) else []

    def send(self, prompt):
        result = self.hook("prompt", {"prompt": prompt})
        return (result or {}).get("systemMessage")

    def test_the_exact_prompt_records_consent_that_verify_accepts(self):
        digest = self.prepared()
        code, out = self.review_packet("verify", "--digest", digest[:12])
        self.assertEqual(code, 3, "no consent yet")
        self.assertIn("no consent record", out)
        message = self.send("send packet " + digest[:12])
        self.assertIn(digest, message)
        self.assertIn("review_packet.py verify", message)
        self.assertEqual(self.consent_files(), [digest + ".json"])
        with open(self.path("review-consent", digest + ".json")) as handle:
            record = json.load(handle)
        self.assertEqual(record["schema"], "mycelium-extra.review-consent.v1")
        self.assertEqual((record["digest"], record["session_id"], record["prompt"]),
                         (digest, "s1", "send packet " + digest[:12]))
        self.assertIsInstance(record["ts"], float)
        code, out = self.review_packet("verify", "--digest", digest[:12])
        self.assertEqual(code, 0, out)

    def test_case_whitespace_and_a_longer_prefix_are_accepted(self):
        digest = self.prepared()
        self.assertIn(digest, self.send("  SEND Packet {}\n".format(digest[:20].upper())))
        self.assertEqual(self.review_packet("verify", "--digest", digest[:12])[0], 0)
        with open(self.path("review-consent", digest + ".json")) as handle:
            self.assertEqual(json.load(handle)["prompt"], "  SEND Packet {}\n".format(digest[:20].upper()))

    def test_a_prompt_inside_longer_text_is_not_consent(self):
        digest = self.prepared()
        for prompt in ("please send packet {} now".format(digest[:12]), "send packet {}.".format(digest[:12]),
                       "ok. send packet {}".format(digest[:12]), "send packet {}\nthanks".format(digest[:12]),
                       "send  packet {}".format(digest[:12]), "send packet {} {}".format(digest[:12], digest[:12])):
            self.send(prompt)
            self.assertEqual(self.consent_files(), [], prompt)
        self.assertEqual(self.review_packet("verify", "--digest", digest[:12])[0], 3)

    def test_a_prefix_that_is_too_short_is_not_a_consent_prompt(self):
        digest = self.prepared()
        self.assertIsNone(self.send("send packet " + digest[:11]))
        self.assertEqual(self.consent_files(), [])

    def test_an_ambiguous_prefix_records_nothing_and_says_why(self):
        base = self.path("review-packets")
        for tail in ("a" * 52, "b" * 52):
            os.makedirs(os.path.join(base, "0123456789ab" + tail))
            with open(os.path.join(base, "0123456789ab" + tail, "manifest.json"), "w") as handle:
                handle.write("{}")
        message = self.send("send packet 0123456789ab")
        self.assertIn("2 prepared packets", message)
        self.assertIn("nothing was recorded", message)
        self.assertEqual(self.consent_files(), [])
        self.assertIn(("0123456789ab" + "a" * 4), self.send("send packet 0123456789ab" + "a" * 4) or "")  # a longer one is unique

    def test_an_unknown_digest_records_nothing_and_says_why(self):
        self.prepared()
        message = self.send("send packet " + "f" * 12)
        self.assertIn("no prepared review packet", message)
        self.assertEqual(self.consent_files(), [])

    def test_a_folder_without_a_manifest_is_not_a_packet(self):
        os.makedirs(self.path("review-packets", "c" * 64))
        self.assertIn("no prepared review packet", self.send("send packet " + "c" * 12))
        self.assertEqual(self.consent_files(), [])

    def test_consent_for_one_packet_does_not_cover_another(self):
        first = self.prepared()
        with open(os.path.join(self.root, "packet-draft.txt"), "a") as handle:
            handle.write("# a second packet\n")
        proc_code, out = self.review_packet("prepare", "--packet", os.path.join(self.root, "packet-draft.txt"))
        second = re.search(r"^digest: ([0-9a-f]{64})$", out, re.MULTILINE).group(1)
        self.send("send packet " + first[:12])
        self.assertEqual(self.review_packet("verify", "--digest", first[:12])[0], 0)
        self.assertEqual(self.review_packet("verify", "--digest", second[:12])[0], 3)


class ReceiptStartTimeTest(unittest.TestCase):
    """A receipt carries the start time of the launch it matched, so verify can detect overlapping attempts."""
    entry = GATE
    setUp, tearDown, config, hook, bash, denied = (
        GateTest.setUp, GateTest.tearDown, GateTest.config, GateTest.hook, GateTest.bash, GateTest.denied)
    path, write, prompt, receipts, tool, post = (
        PreparationAndLaunchTest.path, PreparationAndLaunchTest.write, PreparationAndLaunchTest.prompt,
        PreparationAndLaunchTest.receipts, PreparationAndLaunchTest.tool, PreparationAndLaunchTest.post)
    show = PreparationAndLaunchTest.show
    launch_records = AttemptEvidenceTest.launch_records

    def approve(self):
        self.prompt("approve plan " + self.show(PLAN))

    def test_a_matched_receipt_carries_the_launch_start_time(self):
        self.approve()
        before = time.time()
        self.tool(tool_use_id="t1")
        record, = self.launch_records()
        self.post(tool_use_id="t1")
        receipt, = self.receipts()
        self.assertEqual((receipt["launch_match"], receipt["started"]), ("matched", record["started"]))
        self.assertTrue(before <= receipt["started"] <= receipt["ts"])

    def test_unmatched_and_ambiguous_receipts_have_no_start_time(self):
        self.approve()
        self.post(tool_use_id="nobody")  # no launch record
        self.tool()
        self.tool()  # identical launches without a call id
        self.post()
        self.post()
        receipts = self.receipts()
        self.assertEqual([r["launch_match"] for r in receipts], ["unmatched", "ambiguous", "ambiguous"])
        self.assertEqual([r["started"] for r in receipts], [None, None, None])


class FolderOutputsTest(unittest.TestCase):
    """C05: a declared `Outputs:` folder is observed as the files inside it, within the glob cap."""
    entry = GATE
    setUp, tearDown, config, hook, bash, denied = (
        GateTest.setUp, GateTest.tearDown, GateTest.config, GateTest.hook, GateTest.bash, GateTest.denied)
    path, write, prompt, receipts, tool, post = (
        PreparationAndLaunchTest.path, PreparationAndLaunchTest.write, PreparationAndLaunchTest.prompt,
        PreparationAndLaunchTest.receipts, PreparationAndLaunchTest.tool, PreparationAndLaunchTest.post)
    show = PreparationAndLaunchTest.show
    launch_records = AttemptEvidenceTest.launch_records
    PLAN = "Outputs: analysis/a/outputs/\n\n" + PLAN

    def run_attempt(self, during):
        self.write("analysis/a.py", "pass\n")
        self.prompt("approve plan " + self.show(self.PLAN.replace("analysis/x.py", "analysis/a.py")))
        command = "python analysis/a.py"
        self.assertIsNone(self.tool(command, tool_use_id="t1"))
        during()
        self.post(command, tool_use_id="t1")
        receipt, = self.receipts()
        return receipt

    def test_a_file_created_in_a_declared_folder_is_listed_and_an_untouched_one_is_not(self):
        self.write("analysis/a/outputs/old.tsv", "old\n")
        self.write("analysis/a/outputs/sub/older.tsv", "older\n")
        receipt = self.run_attempt(lambda: self.write("analysis/a/outputs/sub/new.tsv", "new\n"))
        self.assertEqual(receipt["outputs_observation"], "observed")
        self.assertEqual(receipt["outputs_changed"], {"created": ["analysis/a/outputs/sub/new.tsv"],
                                                      "changed": [], "deleted": []})

    def test_the_launch_records_the_files_inside_the_folder_not_the_folder(self):
        self.write("analysis/a/outputs/old.tsv", "old\n")
        self.write("analysis/a.py", "pass\n")
        self.prompt("approve plan " + self.show(self.PLAN.replace("analysis/x.py", "analysis/a.py")))
        self.tool("python analysis/a.py", tool_use_id="t1")
        entry, = [e for r in self.launch_records() for es in r["runs"].values() for e in es]
        self.assertEqual(sorted(entry["outputs_before"]), ["analysis/a/outputs/old.tsv"])

    def test_a_folder_that_does_not_exist_yet_lists_only_the_files_created(self):
        receipt = self.run_attempt(lambda: self.write("analysis/a/outputs/fit.tsv", "x\n"))
        self.assertEqual(receipt["outputs_changed"]["created"], ["analysis/a/outputs/fit.tsv"])

    def test_an_edited_and_a_deleted_file_in_the_folder_are_listed(self):
        self.write("analysis/a/outputs/a.tsv", "1\n")
        self.write("analysis/a/outputs/b.tsv", "2\n")
        def during():
            self.write("analysis/a/outputs/a.tsv", "11111\n")
            os.remove(os.path.join(self.root, "analysis/a/outputs/b.tsv"))
        changed = self.run_attempt(during)["outputs_changed"]
        self.assertEqual((changed["changed"], changed["deleted"], changed["created"]),
                         (["analysis/a/outputs/a.tsv"], ["analysis/a/outputs/b.tsv"], []))

    def test_a_folder_over_the_cap_is_skipped_never_listed_partially(self):
        for number in range(201):
            self.write("analysis/a/outputs/f{}.tsv".format(number), "x\n")
        receipt = self.run_attempt(lambda: self.write("analysis/a/outputs/new.tsv", "x\n"))
        self.assertTrue(receipt["outputs_observation"].startswith("skipped: cap reached"), receipt["outputs_observation"])
        self.assertNotIn("outputs_changed", receipt)

    def test_a_folder_at_the_cap_is_observed(self):  # control
        for number in range(200):
            self.write("analysis/a/outputs/f{}.tsv".format(number), "x\n")
        receipt = self.run_attempt(lambda: None)
        self.assertEqual(receipt["outputs_observation"], "observed")
        self.assertEqual(receipt["outputs_changed"], {"created": [], "changed": [], "deleted": []})

class ScopedExploreTest(unittest.TestCase):
    """C09 gate side: `allow explore <hash>` bounds exploration to an active plan's analysis paths and declares its
    protected test and exact-execution files; `allow explore` alone is the unchanged session-wide grant."""
    entry = GATE
    setUp, tearDown, config, hook, bash, denied = (
        GateTest.setUp, GateTest.tearDown, GateTest.config, GateTest.hook, GateTest.bash, GateTest.denied)
    path, write, approval, pending, prompt, receipts, tool, post = (
        PreparationAndLaunchTest.path, PreparationAndLaunchTest.write, PreparationAndLaunchTest.approval,
        PreparationAndLaunchTest.pending, PreparationAndLaunchTest.prompt, PreparationAndLaunchTest.receipts,
        PreparationAndLaunchTest.tool, PreparationAndLaunchTest.post)
    launch_records = AttemptEvidenceTest.launch_records
    EXPECT = "analysis/x/tests/expect.tsv"
    TABLE = ValidationBindingsTest.TABLE
    EXPLORE = "MYCELIUM_EXTRA_EXPLORE=1 "
    CHECK = {"id": "V1", "plan_row": "2", "required": True, "defined_by": "researcher-approved",
             "test_paths": [EXPECT], "invocation": ["python", "analysis/x/tests/check.py"],
             "evidence_path": "analysis/x/outputs/check.json"}
    FIT = ["python", "analysis/x/fit.py", "--model", "original", "--threads", "4"]

    def setUp(self):  # noqa: F811
        GateTest.setUp(self)
        self.write(self.EXPECT, "rows\n24\n")
        for name in ("x/fit.py", "x/tests/check.py", "y/other.py"):
            self.write("analysis/" + name, "pass\n")

    def plan(self, exact=False):
        block = ("<!-- exact-execution {} -->\n\n".format(json.dumps({"version": 1, "steps": [
            {"row": "1", "argv": self.FIT, "cwd": ".", "env": {}, "operational": ["--threads"]}]}))
                 if exact else
                 "<!-- validation-bindings {} -->\n\n".format(json.dumps({"version": 1, "checks": [self.CHECK]})))
        return self.TABLE + block + "Plan status: READY"

    def approved(self, exact=False, session="s1"):
        digest = self.hook("stop", {"last_assistant_message": self.plan(exact)}, session=session)[
            "systemMessage"].split("approve plan ")[1][:8]
        self.hook("prompt", {"prompt": "approve plan " + digest}, session=session)
        return digest

    def scoped(self, exact=False):
        digest = self.approved(exact)
        reply = self.prompt("allow explore " + digest)
        return digest, reply

    def grant(self):
        with open(self.path("explore-grants", "s1.json")) as handle:
            return json.load(handle)

    def explore(self, command, **event):
        return self.tool(self.EXPLORE + command, **event)

    def reason(self, result):
        self.assertTrue(self.denied(result), result)
        return result["hookSpecificOutput"]["permissionDecisionReason"]

    def notice(self, result):
        self.assertFalse(self.denied(result), result)
        return json.dumps(result)

    def test_a_scoped_grant_names_the_instance_the_paths_and_the_protected_files(self):
        digest, reply = self.scoped()
        for text in (digest, "scoped", "analysis/x", "path and declared-file based", "advisory"):
            self.assertIn(text, reply)
        scope = self.grant()["scope"]
        self.assertEqual((scope["hash"], scope["instance_id"]), (digest, self.approval(digest)["instance_id"]))
        self.assertIn("analysis/x/fit.py", scope["analysis_paths"])
        self.assertEqual(sorted(scope["validation"]["checks"][0]["files"]), [self.EXPECT])

    def test_a_hash_that_is_not_an_active_approval_of_this_session_is_refused(self):
        self.approved()
        for wanted in ("deadbeef", self.hook("stop", {"last_assistant_message": "## Other\nPlan status: READY"})[
                "systemMessage"].split("approve plan ")[1][:8]):  # unknown, and shown but not approved
            self.assertIn("no active approved plan", self.prompt("allow explore " + wanted))
            self.assertFalse(os.path.exists(self.path("explore-grants", "s1.json")))
        other = self.approved(session="s2")  # approved, but in another session
        self.assertIn("no active approved plan", self.prompt("allow explore " + other))
        self.assertTrue(self.denied(self.explore("python analysis/x/fit.py")))

    def test_an_expired_approval_is_refused(self):
        digest = self.approved()
        PreparationAndLaunchTest.expire(self, digest)
        self.assertIn("no active approved plan", self.prompt("allow explore " + digest))

    def test_repeated_in_scope_runs_need_no_new_approval_and_no_prompt(self):
        self.scoped()
        for number, command in enumerate(["python analysis/x/fit.py", "python analysis/x/fit.py --model b",
                                          "python -u analysis/x/fit.py --threads 1", "python analysis/x/fit.py"]):
            self.assertIsNone(self.explore(command, tool_use_id="t{}".format(number)), command)

    def test_an_out_of_scope_path_is_denied_under_a_scoped_grant_but_not_under_a_plain_one(self):
        digest, _ = self.scoped()
        reason = self.reason(self.explore("python analysis/y/other.py"))
        for text in ("analysis/y/other.py", digest, "widen", "allow explore", "user"):
            self.assertIn(text, reason)
        self.assertTrue(self.denied(self.explore("python analysis/x/fit.py && python analysis/y/other.py")))
        self.hook("prompt", {"prompt": "stop explore"})
        self.prompt("allow explore")  # control: the broader session grant, unchanged
        self.assertIsNone(self.explore("python analysis/y/other.py"))
        self.assertIsNone(self.explore("python analysis/x/fit.py"))

    def test_the_scope_does_not_loosen_ordinary_gating(self):
        self.scoped()
        self.assertTrue(self.denied(self.tool("python analysis/y/other.py")))  # no explore prefix, no plan
        self.assertIsNone(self.tool("python analysis/x/fit.py"))  # the approved plan, as before

    def test_a_changed_protected_file_is_surfaced_not_denied(self):
        self.scoped()
        self.assertIsNone(self.explore("python analysis/x/fit.py"))
        self.write(self.EXPECT, "rows\n7\n")
        said = self.notice(self.explore("python analysis/x/fit.py"))
        for text in (self.EXPECT, "protected", "re-approval"):
            self.assertIn(text, said)

    def test_a_run_of_a_checks_invocation_and_a_write_to_its_file_are_surfaced(self):
        self.scoped()
        said = self.notice(self.explore("python analysis/x/tests/check.py"))
        for text in ("V1", "protected", "re-approval"):
            self.assertIn(text, said)
        edit = self.hook("tool", {"tool_name": "Edit", "tool_input": {"file_path": self.EXPECT}})
        self.assertIn("protected", self.notice(edit))
        self.assertIsNone(self.hook("tool", {"tool_name": "Edit", "tool_input": {"file_path": "analysis/x/fit.py"}}))

    def test_a_run_that_differs_from_a_frozen_exact_step_is_surfaced_not_denied(self):
        self.scoped(exact=True)
        self.assertIsNone(self.explore("python analysis/x/fit.py --model original --threads 8"))
        said = self.notice(self.explore("python analysis/x/fit.py --model alternative"))
        for text in ("exact-execution", "row 1", "re-approval"):
            self.assertIn(text, said)

    def test_stop_explore_revokes_a_scoped_grant(self):
        self.scoped()
        self.assertIsNone(self.explore("python analysis/x/fit.py"))
        self.assertIn("no longer allowed", self.prompt("stop explore"))
        self.assertTrue(self.denied(self.explore("python analysis/x/fit.py")))
        self.assertFalse(os.path.exists(self.path("explore-grants", "s1.json")))

    def test_the_scoped_grant_belongs_to_its_session(self):
        self.scoped()
        self.assertTrue(self.denied(self.hook("tool", {"tool_name": "Bash", "tool_input": {
            "command": self.EXPLORE + "python analysis/x/fit.py"}}, session="s2")))

    def test_explore_receipts_carry_scope_and_attempt_but_never_pins_checked_or_a_validation_check(self):
        digest, _ = self.scoped()
        instance = self.approval(digest)["instance_id"]
        command = "python analysis/x/tests/check.py"  # the declared invocation of check V1, run as exploration
        self.explore(command, tool_use_id="t1")
        self.explore("python analysis/x/fit.py", tool_use_id="t2")
        entries = [e for r in self.launch_records() for es in r["runs"].values() for e in es]
        self.assertTrue(all("validation_check" not in e and e["explore_scope"] == instance for e in entries), entries)
        self.post(self.EXPLORE + command, tool_use_id="t1")
        self.post(self.EXPLORE + "python analysis/x/fit.py", tool_use_id="t2")
        first, second = self.receipts()
        for receipt in (first, second):
            self.assertTrue(receipt["explore"])
            self.assertIs(receipt["pins_checked"], False)
            self.assertNotIn("validation_check", receipt)
            self.assertEqual(receipt["explore_scope"], instance)
            self.assertEqual(receipt["plans"], [digest])
            self.assertTrue(receipt["attempt_id"])
            self.assertIn("analysis/x/fit.py" if "fit" in receipt["command"] else "analysis/x/tests/check.py",
                          receipt["explore_script_pins"])
        self.assertNotEqual(first["attempt_id"], second["attempt_id"])

    def test_explore_log_lines_carry_the_scope_and_the_attempt(self):
        digest, _ = self.scoped()
        self.explore("python analysis/x/fit.py", tool_use_id="t1")
        with open(self.path("explore.log")) as handle:
            line, = [json.loads(row) for row in handle]
        self.assertEqual(line["explore_scope"], self.approval(digest)["instance_id"])
        self.assertTrue(line["attempt_id"])

    def test_a_plain_grant_leaves_receipts_and_log_as_before(self):  # control
        self.approved()
        self.assertIn("allowed for this session", self.prompt("allow explore"))
        self.assertNotIn("scope", self.grant())
        self.explore("python analysis/x/fit.py", tool_use_id="t1")
        self.post(self.EXPLORE + "python analysis/x/fit.py", tool_use_id="t1")
        receipt, = self.receipts()
        self.assertTrue(receipt["explore"])
        self.assertIs(receipt["pins_checked"], False)
        self.assertNotIn("explore_scope", receipt)
        with open(self.path("explore.log")) as handle:
            self.assertNotIn("explore_scope", handle.read())


if __name__ == "__main__":
    unittest.main()
