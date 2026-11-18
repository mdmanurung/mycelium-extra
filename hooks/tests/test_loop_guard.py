"""Run: python3 hooks/tests/test_loop_guard.py

End to end with a temporary git repository: the loop guard as the host runs it (event JSON on stdin).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GUARD = os.path.join(PLUGIN, "hooks", "loop_guard.py")
TREE = os.path.join(PLUGIN, "skills", "iterate", "scripts", "tree.py")
ANALYSIS = "analysis/demo"


class LoopGuardTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.git("init", "-q", "-b", "main")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "init")
        os.makedirs(os.path.join(self.root, ".mycelium-extra"))
        self.loops("block")

    def git(self, *args):
        subprocess.run(["git", "-C", self.root] + list(args), check=True, stdout=subprocess.PIPE)

    def loops(self, value):
        config = {} if value is None else {"loops": value}
        with open(os.path.join(self.root, ".mycelium-extra", "gate.json"), "w") as handle:
            json.dump(config, handle)

    def tree(self, *args):
        out = subprocess.run([sys.executable, TREE, "--analysis", os.path.join(self.root, ANALYSIS)] + list(args),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        return out.returncode, out.stdout

    def freeze_a(self):
        self.tree("add", "base", "--run-cmd", "python code/run.py", "--readout", "auc",
                  "--repair-cap", "2", "--stop-after", "3", "--stop-rule", "stop after 3 not better")
        self.tree("add", "a", "--parent", "base")
        self.tree("run", "a", "--exit", "0")
        self.tree("answer", "a", "--outcome", "worse", "--summary", "no gain")
        self.git("checkout", "-q", "-b", "exp/a")

    def hook(self, action, env=None, **event):
        event.setdefault("cwd", self.root)
        out = subprocess.run([sys.executable, GUARD, action], input=json.dumps(event), stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, universal_newlines=True, env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout) if out.stdout.strip() else {}

    def bash(self, command, env=None, **extra):
        return self.hook("tool", env=env, tool_name="Bash", tool_input={"command": command}, **extra)

    def denied(self, reply):
        return reply.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_off_by_default_and_without_gate_json(self):
        self.freeze_a()
        self.loops(None)
        self.assertEqual(self.bash("git commit -m x"), {})
        self.assertEqual(self.hook("stop", session_id="s"), {})
        self.loops("off")
        self.assertEqual(self.bash("git commit -m x"), {})
        os.remove(os.path.join(self.root, ".mycelium-extra", "gate.json"))
        self.assertEqual(self.bash("git commit -m x"), {})

    def test_block_refuses_commit_on_a_frozen_branch_only(self):
        self.freeze_a()
        reply = self.bash("git commit -m x")
        self.assertTrue(self.denied(reply))
        self.assertIn("exp/a", reply["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertTrue(self.denied(self.bash("cd . && git -C . commit --amend")))
        self.assertEqual(self.bash("git status"), {})
        self.git("checkout", "-q", "-b", "exp/b")
        self.assertEqual(self.bash("git commit -m x"), {})

    def test_warn_notes_and_allows(self):
        self.freeze_a()
        self.loops("warn")
        reply = self.bash("git commit -m x")
        self.assertFalse(self.denied(reply))
        self.assertIn("frozen", reply["systemMessage"])

    def test_env_prefixed_fixed_command(self):
        self.freeze_a()
        self.git("checkout", "-q", "main")
        self.assertTrue(self.denied(self.bash("SEED=2 python code/run.py")))
        self.assertTrue(self.denied(self.bash("env SEED=2 python code/run.py --x")))
        self.assertEqual(self.bash("python code/run.py"), {})
        self.assertEqual(self.bash("SEED=2 python code/other.py"), {})
        self.loops("warn")
        self.assertFalse(self.denied(self.bash("SEED=2 python code/run.py")))
        self.assertIn("env", self.bash("SEED=2 python code/run.py")["systemMessage"])

    def test_stop_blocks_once_then_honours_stop_hook_active(self):
        self.freeze_a()
        first = self.hook("stop", session_id="s")
        self.assertEqual(first["decision"], "block")
        self.assertIn("tree.py", first["reason"])
        self.assertNotIn("--reason", first["reason"])  # the agent is not handed a self-escape
        self.assertIn("Ask the user", first["reason"])
        self.assertIn("warn", first["reason"])
        self.assertEqual(self.hook("stop", session_id="s", stop_hook_active=True), {})

    def test_stop_escapes(self):
        self.freeze_a()
        self.assertEqual(self.tree("stop", "--reason", "user")[0], 0)
        self.assertEqual(self.hook("stop", session_id="s"), {})

    def test_stop_warn_does_not_block_and_rule_met_passes(self):
        self.freeze_a()
        self.loops("warn")
        reply = self.hook("stop", session_id="s")
        self.assertNotIn("decision", reply)
        self.assertIn("research loop is not finished", reply["systemMessage"])
        self.loops("block")
        for slug in ("b", "c"):
            self.tree("add", slug, "--parent", "base")
            self.tree("run", slug, "--exit", "0")
            self.tree("answer", slug, "--outcome", "same", "--summary", "s")
        self.assertEqual(self.hook("stop", session_id="s"), {})

    def test_no_tree_and_unreadable_events_are_silent(self):
        self.assertEqual(self.hook("stop", session_id="s"), {})
        self.assertEqual(self.bash("git commit -m x"), {})
        out = subprocess.run([sys.executable, GUARD, "tool"], input="not json", stdout=subprocess.PIPE,
                             universal_newlines=True)
        self.assertEqual((out.returncode, out.stdout), (0, ""))

    def test_codex_and_opencode_shapes(self):
        self.freeze_a()
        shell = self.hook("tool", tool_name="exec_command", tool_input={"cmd": "git commit -m x"})
        self.assertTrue(self.denied(shell))
        out = subprocess.run([sys.executable, GUARD, "--host", "opencode", "tool"], universal_newlines=True,
                             input=json.dumps({"tool_name": "shell", "tool_input": {"command": "git commit -m x"},
                                               "cwd": self.root}), stdout=subprocess.PIPE)
        self.assertTrue(self.denied(json.loads(out.stdout)))

    def test_stop_blocks_once_per_tree_state_not_every_turn(self):
        self.freeze_a()
        self.assertEqual(self.hook("stop", session_id="s1")["decision"], "block")
        self.assertEqual(self.hook("stop", session_id="s2"), {})  # a later turn that left the tree alone
        self.tree("add", "b", "--parent", "base")
        self.assertEqual(self.hook("stop", session_id="s3")["decision"], "block")

    def test_commit_forms_on_a_frozen_branch(self):
        self.freeze_a()
        for command in ("sh -c 'git commit -m x'", 'bash -c "git commit -m x"', "{ git commit -m x; }",
                        "if true; then git commit -m x; fi", "env X=1 git commit -m x", "command git commit -m x",
                        "nohup git commit -m x", "git --git-dir .git commit -m x", "git --git-dir=.git commit",
                        "git merge other", "git cherry-pick HEAD", "git revert HEAD", "git rebase main",
                        "git am p.patch", "git -c alias.x=commit x -m y", "export A=1; git commit -m x"):
            self.assertTrue(self.denied(self.bash(command)), command)
        self.git("config", "alias.ci", "commit")
        self.git("config", "alias.sh", "!git commit")
        self.assertTrue(self.denied(self.bash("git ci -m x")))
        self.assertTrue(self.denied(self.bash("git sh -m x")))
        for command in ("git status", "git log", "git merge --abort", "git diff && echo commit"):
            self.assertEqual(self.bash(command), {}, command)

    def test_env_on_fixed_command(self):
        self.freeze_a()
        self.git("checkout", "-q", "main")
        for command in ("export A=1; python code/run.py", "A=1 python ./code/run.py", "A=1 python3 code/run.py",
                        "A=1 nohup python code/run.py", "A=1 sh -c 'python code/run.py'",
                        "A=1 python  code/run.py", "PYTHONUNBUFFERED=1 SEED=2 python code/run.py"):
            self.assertTrue(self.denied(self.bash(command)), command)
        for command in ("PYTHONUNBUFFERED=1 python code/run.py", "CUDA_VISIBLE_DEVICES=0 python code/run.py",
                        "env PYTHONHASHSEED_OK=1 python code/other.py"):
            self.assertEqual(self.bash(command), {}, command)

    def test_two_trees_sharing_a_run_command_give_one_sentence(self):
        for name in ("one", "two"):
            analysis = os.path.join(self.root, "analysis", name)
            out = subprocess.run([sys.executable, TREE, "--analysis", analysis, "add", "base", "--run-cmd",
                                  "python code/run.py", "--readout", "auc", "--repair-cap", "2", "--stop-after",
                                  "3", "--stop-rule", "s"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(out.returncode, 0, out.stderr)
        reply = self.bash("A=1 python code/run.py")
        reason = reply["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertEqual(reason.count("the fixed run command"), 1)

    def test_block_flow_end_to_end(self):
        self.freeze_a()
        self.assertTrue(self.denied(self.bash("git commit -m x")))
        self.assertEqual(self.hook("stop", session_id="s")["decision"], "block")
        self.assertEqual(self.tree("stop", "--reason", "user")[0], 0)
        self.assertEqual(self.hook("stop", session_id="s"), {})

    def test_checkout_in_the_command_sets_the_branch_the_commit_lands_on(self):
        self.freeze_a()  # HEAD is exp/a, which is frozen
        for command in ("git checkout main && git commit -m x", "git checkout -b exp/b && git commit -m x",
                        "git switch -c exp/c exp/a && git commit -am x", "git switch main && git merge exp/a",
                        "git checkout main; git pull", "git -C . switch main && git -C . commit -m x"):
            self.assertEqual(self.bash(command), {}, command)
        self.assertTrue(self.denied(self.bash("git commit -m x && git checkout main && git commit -m y")))
        self.git("checkout", "-q", "main")  # now the frozen branch is entered first
        for command in ("git checkout exp/a && git commit --allow-empty -m x", "git switch exp/a; git commit -m x",
                        "git checkout exp/a && git checkout main && git checkout exp/a && git commit -m x"):
            self.assertTrue(self.denied(self.bash(command)), command)
        for command in ("git checkout exp/a && git checkout main && git commit -m x",
                        "git checkout exp/a -- f.txt && git commit -m x", "git checkout nope && git commit -m x",
                        "git switch --detach && git commit -m x"):
            self.assertEqual(self.bash(command), {}, command)

    def test_ref_moves_of_a_frozen_branch_are_denied(self):
        self.freeze_a()
        self.git("checkout", "-q", "main")
        for command in ("git branch -f exp/a HEAD", "git update-ref refs/heads/exp/a HEAD", "git push . HEAD:exp/a",
                        "git fetch . main:exp/a", "git fetch . +main:refs/heads/exp/a", "git checkout -B exp/a",
                        "git switch -C exp/a main", "git branch -D exp/a", "git branch -m exp/a gone",
                        "git checkout main && git branch -f exp/a main"):
            reply = self.bash(command)
            self.assertTrue(self.denied(reply), command)
            self.assertIn("exp/a", reply["hookSpecificOutput"]["permissionDecisionReason"])
        for command in ("git branch -f other exp/a", "git branch --list", "git branch -c exp/a copy",
                        "git push origin HEAD:exp/a", "git update-ref refs/heads/other HEAD", "git reset --hard"):
            self.assertEqual(self.bash(command), {}, command)
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "next")
        self.git("checkout", "-q", "exp/a")  # main is now one commit ahead of exp/a
        self.assertTrue(self.denied(self.bash("git reset --soft main")))
        for command in ("git reset", "git reset HEAD", "git reset --hard", "git reset -- f.txt"):
            self.assertEqual(self.bash(command), {}, command)

    def test_wrappers_and_launchers_do_not_hide_a_commit_or_an_env_prefix(self):
        self.freeze_a()
        for command in ("env -i git commit -m x", "sudo -u me git commit -m x", "time -p git commit -m x",
                        "xargs git commit -m x", "srun git commit -m x", "uv run git commit -m x",
                        "conda run -n e git commit -m x", "apptainer exec img.sif git commit -m x",
                        "bash <<'EOF'\ngit commit -m x\nEOF", "timeout -s KILL 5 git commit -m x"):
            self.assertTrue(self.denied(self.bash(command)), command)
        self.git("checkout", "-q", "main")
        for command in ("env -i SEED=2 python code/run.py", "SEED=2 srun python code/run.py",
                        "SEED=2 conda run -n e python code/run.py", "SEED=2 uv run python code/run.py",
                        "SEED=2 apptainer exec img.sif python code/run.py", "SEED=2 python -u code/run.py",
                        "cd code && SEED=2 python run.py", "SEED=2 python %s/code/run.py" % self.root):
            self.assertTrue(self.denied(self.bash(command)), command)
        for command in ("srun python code/run.py", "cd code && python other.py", "SEED=2 srun python code/other.py"):
            self.assertEqual(self.bash(command), {}, command)

    def test_a_bare_shell_variable_is_not_an_env_var_of_the_run(self):
        self.freeze_a()
        self.git("checkout", "-q", "main")
        for command in ("LOG=run.log && python code/run.py 2>&1 | tee $LOG", "OUT=results/x; python code/run.py > $OUT",
                        "i=0; python code/run.py", "x=$(date +%s); python code/run.py; echo $x",
                        "rc=0; git status; python code/run.py", "(A=1; true); python code/run.py"):
            self.assertEqual(self.bash(command), {}, command)
        exported = dict(os.environ, MX_TEST_EXPORTED="1")
        self.assertTrue(self.denied(self.bash("MX_TEST_EXPORTED=2; python code/run.py", env=exported)))  # reaches the child
        self.assertTrue(self.denied(self.bash("export MX_LATER; MX_LATER=2; python code/run.py")))
        self.assertTrue(self.denied(self.bash("export A=1; python code/run.py")))

    def test_a_reset_that_leaves_the_frozen_branch_where_it_is_passes(self):
        self.freeze_a()
        with open(os.path.join(self.root, "f.txt"), "w") as handle:
            handle.write("x\n")
        self.git("add", "f.txt")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "second")  # HEAD~1 exists
        for command in ("git reset HEAD~1 -- f.txt", "git reset HEAD~1 f.txt", "git reset -p HEAD~1",
                        "git reset --hard exp/a", "git reset --hard @", "git reset --hard HEAD"):
            self.assertEqual(self.bash(command), {}, command)
        for command in ("git reset --hard HEAD~1", "git reset --soft main", "git reset HEAD~1"):
            self.assertTrue(self.denied(self.bash(command)), command)

    def test_a_checkout_followed_across_a_folder_an_alias_a_variable_and_the_previous_branch(self):
        self.freeze_a()
        os.makedirs(os.path.join(self.root, "sub"))
        self.git("config", "alias.co", "checkout")
        self.git("config", "alias.swm", "switch main")
        self.git("checkout", "-q", "main")
        for command in ("git -C sub checkout exp/a && git commit -m x",
                        "cd sub && git checkout exp/a && cd .. && git commit -m x",
                        "git checkout exp/a && cd sub && git commit -m x", "git co exp/a && git commit -m x",
                        "B=exp/a; git checkout $B && git commit -m x",
                        "B=exp/a; git checkout ${B} && git commit -m x",
                        "git -c alias.go=checkout go exp/a && git commit -m x"):
            self.assertTrue(self.denied(self.bash(command)), command)
        self.git("checkout", "-q", "exp/a")
        self.git("checkout", "-q", "main")  # the previous branch is exp/a
        self.assertTrue(self.denied(self.bash("git switch - && git commit -m x")))
        self.assertTrue(self.denied(self.bash("git checkout - && git commit -m x")))
        self.assertEqual(self.bash("git checkout exp/a && git swm && git commit -m x"), {})
        self.assertEqual(self.bash("B=main; git checkout $B && git commit -m x"), {})

    def test_an_assignment_exported_later_or_under_set_a_reaches_the_run(self):
        self.freeze_a()
        self.git("checkout", "-q", "main")
        for command in ("SEED=2; export SEED; python code/run.py", "set -a; SEED=2; python code/run.py",
                        "set -o allexport; SEED=2; python code/run.py",
                        "export SEED; SEED=2; python code/run.py"):
            self.assertTrue(self.denied(self.bash(command)), command)
        for command in ("N=3; echo $N; python code/run.py", "SEED=2; export OTHER; python code/run.py",
                        "set -a; set +a; SEED=2; python code/run.py", "set -e; SEED=2; python code/run.py"):
            self.assertEqual(self.bash(command), {}, command)

    def test_git_calls_that_commit_nothing_pass_on_a_frozen_branch(self):
        self.freeze_a()
        for command in ("git commit --dry-run", "git commit --help", "git pull --help", "git commit -h",
                        "git merge --abort", "git rebase --quit"):
            self.assertEqual(self.bash(command), {}, command)
        self.assertTrue(self.denied(self.bash("git commit -m --help")))  # a message, not an option
        self.assertTrue(self.denied(self.bash("git commit -m x")))


if __name__ == "__main__":
    unittest.main()
