"""Run: python3 hooks/tests/test_gate_scan_fixes.py

Regression tests for the gate findings in docs/roadmap/13-function-audit.md: the spellings an
honest agent types (command substitution, a wrapper's unknown options, `cd` options, stdin code)
must be read like their plain form, and the look-alikes must stay allowed.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(HERE, "..", "gate.py")
LAUNCHER = os.path.join(HERE, "..", "gate_run.py")
sys.path.insert(0, os.path.join(HERE, ".."))
import gate  # noqa: E402

PLAN = "## Plan\n| 1 | run `analysis/x.py` | repo | check |\n\nPlan status: READY"


class ScanFixTest(unittest.TestCase):
    entry = GATE

    def setUp(self):
        saved = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(saved)))
        for key in ("CONDA_DEFAULT_ENV", "CONDA_PREFIX", "VIRTUAL_ENV", "PIXI_ENVIRONMENT_NAME"):
            os.environ.pop(key, None)
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        os.environ["HOME"] = home
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, ".mycelium-extra"))
        self.config({})

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

    def test_ansi_c_escapes_name_the_same_unapproved_script(self):
        for operand in [r"$'analys\151s/x.py'", r"$'\x61nalysis/x.py'", r"$'analysis/\170.py'",
                        r"$'\u0061nalysis/x.py'", r"$'\U00000061nalysis/x.py'",
                        r"$'analysis/x.py\0ignored'", r"$'analysis/it\'s.py'",
                        r"$'analysis/\cA.py'", r"$'analysis/\xff.py'"]:
            self.assertTrue(self.denied(self.bash("python " + operand)), operand)
        self.assertEqual(gate.tokenize(r"python $'analys\151s/x.py'"), ["python", "analysis/x.py"])
        self.assertEqual(gate.tokenize(r"echo $'it\'s café'"), ["echo", "it's café"])
        for command in [r"echo $'python analys\151s/x.py'", r"python $'tools/\170.py'"]:
            self.assertIsNone(self.bash(command), command)

    def test_ionice_and_setsid_wrappers_do_not_hide_the_run(self):
        for wrapper in ["ionice", "ionice -c 3", "ionice --class idle", "ionice -c2 -n7",
                        "ionice -t", "setsid", "setsid -f", "setsid --wait",
                        "setsid ionice -c 3", "/usr/bin/setsid /usr/bin/ionice -c 3"]:
            self.assertTrue(self.denied(self.bash(wrapper + " python analysis/x.py")), wrapper)
            self.assertIsNone(self.bash(wrapper + " echo analysis/x.py"), wrapper)

    @unittest.skipUnless(shutil.which("bash"), "Bash required for ANSI-C equivalence")
    def test_supported_ansi_c_literals_match_bash_bytes(self):
        for operand in [r"$'analys\151s/x.py'", r"$'\x61nalysis/x.py'", r"$'\u0061nalysis/x.py'",
                        r"$'\U00000061nalysis/x.py'", r"$'analysis/x.py\0ignored'",
                        r"$'it\'s café'", r"$'a\nb\tc\\d'", r"pre$'\141'post"]:
            actual = subprocess.check_output(["bash", "-c", "printf '%s' " + operand])
            self.assertEqual(gate.tokenize(operand), [actual.decode("utf-8")], operand)

    # C0: command substitution runs the command inside it
    def test_command_substitution_is_read(self):
        for command in [
            "x=$(Rscript analysis/x.R)",
            'echo "$(python analysis/x.py)"',
            "x=`Rscript analysis/x.R`",
            "echo start && x=$(python analysis/x.py) && echo done",
        ]:
            self.assertTrue(self.denied(self.bash(command)), command)
        for command in ["echo $(date)", "x=$(pwd) && echo $x", "echo `date`"]:
            self.assertIsNone(self.bash(command), command)

    # C1: a heredoc or a pipe into a shell runs that text as code
    def test_stdin_code_is_read(self):
        for command in [
            "bash <<EOF\nRscript analysis/x.R\nEOF",
            "bash <<'EOF'\nRscript analysis/x.R\nEOF",
            "cat <<EOF | bash\nRscript analysis/x.R\nEOF",
            "echo 'Rscript analysis/x.R' | bash",
            "sh -s <<EOF\npython analysis/x.py\nEOF",
        ]:
            self.assertTrue(self.denied(self.bash(command)), command)
        for command in [
            "cat > notes.md <<EOF\nRscript analysis/x.R\nEOF",  # data written to a file, not run
            "cat <<'END OF FILE'\nRscript analysis/x.R\nEND OF FILE",
            "echo hello | grep bash",
            "python3 - <<EOF\nimport os\nEOF",
            # another language's stdin is not shell: scanning it as shell would deny plain data
            "echo \"open('analysis/x.py','w')\" | python3",
            "Rscript - <<EOF\nsource('analysis/x.R')\nEOF",
        ]:
            self.assertIsNone(self.bash(command), command)

    # C2: `env VAR=/path ...` names a variable, not the command
    def test_env_assignment_value_is_not_the_command(self):
        for command in [
            "env VAR=/tmp/x python analysis/x.py",
            "env A=/tmp/a B=/tmp/b python analysis/x.py",
            "FOO=/tmp/x python analysis/x.py",
        ]:
            self.assertTrue(self.denied(self.bash(command)), command)
        for command in ["env VAR=/tmp/x true", "FOO=/tmp/x true"]:
            self.assertIsNone(self.bash(command), command)

    # C3: a wrapper's unknown options do not hide the run behind them
    def test_srun_unknown_options_do_not_hide_the_run(self):
        for command in [
            "srun --unknown1 x --unknown2 y python analysis/x.py",
            "srun --mpi=pmix --unknown python analysis/x.py",
            "srun -q --unknown x python analysis/x.py",
        ]:
            self.assertTrue(self.denied(self.bash(command)), command)
        self.assertIsNone(self.bash("srun --unknown1 x true"))

    # C4: `cd` options come before the folder
    def test_cd_options_do_not_hide_the_folder(self):
        for command in [
            "cd -P analysis && python x.py",
            "cd -- analysis && python x.py",
            "cd -L analysis && python x.py",
            "cd -P -- analysis && python x.py",
        ]:
            self.assertTrue(self.denied(self.bash(command)), command)
        self.assertIsNone(self.bash("cd -P -- tools && python y.py"))

    # C5: a line continuation joins the command with its path
    def test_line_continuation_is_not_a_separator(self):
        self.assertTrue(self.denied(self.bash("python \\\nanalysis/x.py")))
        self.assertTrue(self.denied(self.bash("Rscript \\\n  analysis/x.R")))
        self.assertIsNone(self.bash("echo hi \\\nthere"))

    # C7: every redirect form and `sed --in-place`
    def test_state_folder_writes_are_read(self):
        for command in [
            "echo hi >| .mycelium-extra/receipts.jsonl",
            "echo hi >& .mycelium-extra/receipts.jsonl",
            "echo hi &> .mycelium-extra/receipts.jsonl",
            "echo hi 1>&2 .mycelium-extra/receipts.jsonl",
            "sed --in-place s/a/b/ .mycelium-extra/gate.json",
            "sed --in-place=.bak s/a/b/ .mycelium-extra/gate.json",
            "sed -i s/a/b/ .mycelium-extra/gate.json",
        ]:
            self.assertTrue(self.denied(self.bash(command)), command)
        for command in ["cat .mycelium-extra/gate.json", "echo hi >| /tmp/notes.txt",
                        "sed --in-place s/a/b/ notes.md"]:
            self.assertIsNone(self.bash(command), command)

    # C8: package-manager runners are wrappers
    def test_package_manager_runners_are_wrappers(self):
        for command in [
            "poetry run python analysis/x.py",
            "pipx run python analysis/x.py",
            "rye run python analysis/x.py",
            "pdm run python analysis/x.py",
        ]:
            self.assertTrue(self.denied(self.bash(command)), command)
        for command in ["poetry install", "pipx list", "pdm add pandas"]:
            self.assertIsNone(self.bash(command), command)

    # C9: `python -m <gated command>`
    def test_python_dash_m_reads_gated_commands(self):
        for command in ["python3 -m snakemake", "python -m snakemake.cli", "python3 -m sbatch"]:
            self.assertTrue(self.denied(self.bash(command)), command)
        for command in ["python3 -m pytest tests", "python3 -m pip list"]:
            self.assertIsNone(self.bash(command), command)

    # C10: a bare folder name after a folder change names a folder
    def test_inline_code_bare_folder_names(self):
        for command in [
            "Rscript -e \"setwd('analysis'); source('x.R')\"",
            "python3 -c \"import os; os.chdir('analysis'); exec(open('x.py').read())\"",
        ]:
            self.assertTrue(self.denied(self.bash(command)), command)
        self.assertIsNone(self.bash("Rscript -e \"setwd('tools'); source('y.R')\""))

    # C11: a quoted heredoc delimiter may hold spaces
    def test_quoted_heredoc_delimiter_with_spaces(self):
        self.assertTrue(self.denied(self.bash("cat <<'END OF FILE'\ntext\nEND OF FILE\nRscript analysis/x.R")))
        self.assertIsNone(self.bash("cat <<'END OF FILE'\nRscript analysis/x.R\nEND OF FILE"))

    # C12: a subshell and popd restore the outer folder
    def test_subshell_and_popd_scope(self):
        for command in ["(cd analysis && python x.py)", "(cd analysis; python x.py)"]:
            self.assertTrue(self.denied(self.bash(command)), command)
        for command in ["(cd analysis; true); python x.py",
                        "pushd analysis; true; popd; python x.py"]:
            self.assertIsNone(self.bash(command), command)

    # C13: `timeout` durations
    def test_timeout_durations(self):
        for command in ["timeout 1.5s python analysis/x.py", "timeout 0.5 python analysis/x.py",
                        "timeout 2m python analysis/x.py", "timeout 90 python analysis/x.py"]:
            self.assertTrue(self.denied(self.bash(command)), command)
        self.assertIsNone(self.bash("timeout 5s true"))

    # X0: `$'...'` keeps its path
    def test_ansi_c_quoted_path(self):
        self.assertTrue(self.denied(self.bash("Rscript $'analysis/x.R'")))
        self.assertIsNone(self.bash("Rscript $'tools/y.R'"))  # read as a path, not as an expansion
        self.assertIsNone(self.bash("echo $'hi'"))

    # G1: a huge number in gate.json does not make the gate fail open
    def test_huge_config_number_does_not_fail_open(self):
        self.config({"approval_hours": 10 ** 400})
        self.assertTrue(self.denied(self.bash("python analysis/x.py")))

    # X5: a crash-truncated receipts tail does not swallow the next receipt
    def test_truncated_receipt_tail_does_not_swallow_the_next(self):
        path = os.path.join(self.root, ".mycelium-extra", "receipts.jsonl")
        with open(path, "w") as handle:
            handle.write('{"ts": 1, "call_id": "a"}')  # no newline: a crash mid-write
        gate.append_line(path, {"ts": 2, "call_id": "b"})
        with open(path) as handle:
            lines = handle.read().splitlines()
        self.assertTrue(json.loads(lines[-1])["call_id"] == "b")
        self.assertEqual(len(lines), 2)

    # C18: a receipt larger than the old 1 MB window is still found
    def test_duplicate_callback_found_beyond_one_megabyte(self):
        path = os.path.join(self.root, ".mycelium-extra", "receipts.jsonl")
        gate.append_line(path, {"ts": 1, "call_id": "c1", "session_id": "s1", "output": "x" * (1 << 20)})
        gate.append_line(path, {"ts": 2, "call_id": "c2", "session_id": "s1"})
        self.assertTrue(gate.reported_call(self.root, {"session_id": "s1", "tool_use_id": "c1"}))
        self.assertFalse(gate.reported_call(self.root, {"session_id": "s1", "tool_use_id": "c9"}))

    # C14: the reply's last status line governs
    def test_last_plan_status_governs(self):
        ready_then_required = (PLAN.replace("\n\nPlan status: READY", "")
                               + "\n\nPlan status: READY\n\nMore prose.\n\nPlan status: DECISION_REQUIRED")
        result = self.hook("stop", {"last_assistant_message": ready_then_required})
        self.assertNotIn("approve plan", json.dumps(result or {}))
        required_then_ready = ("## Plan\n| 1 | run `analysis/x.py` | repo | check |\n\n"
                               "Plan status: DECISION_REQUIRED\n\nSettled.\n\nPlan status: READY")
        result = self.hook("stop", {"last_assistant_message": required_then_ready})
        self.assertIn("approve plan", json.dumps(result or {}))

    # C16: a denied command leaves no explore entry
    def test_denied_command_leaves_no_explore_entry(self):
        self.hook("prompt", {"prompt": "allow explore"})
        command = "MYCELIUM_EXTRA_EXPLORE=1 python analysis/x.py && sbatch job.sh"
        self.assertTrue(self.denied(self.bash(command)))
        log = os.path.join(self.root, ".mycelium-extra", "explore.log")
        text = open(log).read() if os.path.isfile(log) else ""
        self.assertNotIn("analysis/x.py", text)

    # C6: an event whose cwd is outside the repository still finds the gate
    def test_event_outside_the_repository_still_finds_the_gate(self):
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside)

        def call(command):
            payload = {"session_id": "s1", "cwd": outside, "tool_name": "Bash",
                       "tool_input": {"command": command}}
            proc = subprocess.run([sys.executable, LAUNCHER, "tool"], input=json.dumps(payload).encode("utf-8"),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return json.loads(proc.stdout.decode("utf-8")) if proc.stdout.strip() else None

        self.assertTrue(self.denied(call("python " + os.path.join(self.root, "analysis", "x.py"))))
        relative = os.path.relpath(os.path.join(self.root, "analysis", "x.py"), outside)
        self.assertTrue(self.denied(call("python " + relative)))
        self.assertIsNone(call("python /tmp/elsewhere/y.py"))

    # X24: an unreadable OpenCode tool_input is not read as an empty, allowed command
    def test_unreadable_opencode_tool_input_is_reported(self):
        payload = {"cwd": self.root, "session_id": "s1", "tool_name": "shell", "tool_input": "python analysis/x.py"}
        proc = subprocess.run([sys.executable, LAUNCHER, "--host", "opencode", "tool"],
                              input=json.dumps(payload).encode("utf-8"), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout.decode("utf-8")) if proc.stdout.strip() else None
        self.assertTrue(result)
        self.assertIn("did not run", json.dumps(result))

    # 0.18.2 adversarial review: shell spellings the tokenizer or the reader mis-split, each a silent allow before
    def test_quoting_that_hid_a_run_is_read(self):
        for command in [
            'git commit -m "fix \\"quote\\"" && python analysis/x.py',  # `\"` inside double quotes
            'echo "a\\"" ; python analysis/x.py',
            'echo $(echo ")"); python analysis/x.py',  # a quoted `)` inside `$(...)`
            "echo $(echo ')'); python analysis/x.py",
            "bash <<< 'python analysis/x.py'",  # a here-string is the shell's stdin
            "python3 <<< \"exec(open('analysis/x.py').read())\"",
            'eval "python analysis/x.py"',
            "function f { python analysis/x.py; }; f",
            "coproc python analysis/x.py",
            "cat analysis/x.py | python",  # a script piped into a runner that names none
            "head -n 3 analysis/x.py | python3 -",
            "CDPATH=. cd analysis && python x.py",
            "cd analy*s && python x.py",  # a globbed folder is unresolved, like `cd $DIR`
        ]:
            self.assertTrue(self.denied(self.bash(command)), command)
        for command in [
            'git commit -m "fix \\"quote\\""',
            'echo $(echo ")")',
            "echo 'python analysis/x.py' | grep python",
            "ls |& grep x",
        ]:
            self.assertIsNone(self.bash(command), command)

    def test_launchers_that_took_the_run_elsewhere_are_read(self):
        for command in [
            "echo analysis/x.py | xargs python",  # the script arrives on stdin
            "parallel python ::: analysis/x.py",
            "watch -n 5 python analysis/x.py",
            "screen -dmS fit python analysis/x.py",
            "tmux new -d 'python analysis/x.py'",
            "tmux send-keys -t fit 'python analysis/x.py' Enter",
            "ssh -p 22 node01 python analysis/x.py",  # a shared filesystem: the same repository path
            "find analysis -name '*.py' -exec python {} \\;",  # `{}` is unresolved, like `$f`
            "p=python; $p analysis/x.py",  # an unresolved command on a gated script
        ]:
            self.assertTrue(self.denied(self.bash(command)), command)
        for command in ["find analysis -name '*.py'", "ssh node01 ls", "tmux ls", "echo x | xargs echo",
                        "$EDITOR notes.md"]:
            self.assertIsNone(self.bash(command), command)

    def test_an_option_value_that_names_state_is_a_state_write(self):
        self.assertTrue(self.denied(self.bash("python tools/y.py --out=.mycelium-extra/x.json")))
        self.assertIsNone(self.bash("python tools/y.py --out=outputs/x.json"))

    def test_list_settings_of_the_wrong_type_fall_back_with_a_notice(self):
        for config in ({"gated_paths": "analysis/**"}, {"gated_paths": None}, {"gated_paths": [1]},
                       {"gated_commands": "sbatch"}):
            self.config(config)
            result = self.bash("python analysis/x.py")
            self.assertTrue(self.denied(result), config)  # the default still gates
            notice = self.hook("prompt", {"prompt": "hello"})
            self.assertIn("must be a list of strings", notice["systemMessage"], config)
        self.config({"gated_commands": ["sbatch"]})
        self.assertIsNone(self.bash("s analysis/x"))  # no substring match on a string setting

    def test_a_pending_file_of_the_wrong_shape_holds_no_plan(self):
        folder = os.path.join(self.root, ".mycelium-extra", "pending")
        os.makedirs(folder)
        for content in ('{"x": 1}', '["a", 1]', '[{"ts": 0}]', '[{"hash": 5}]'):
            with open(os.path.join(folder, "s1.json"), "w") as handle:
                handle.write(content)
            reply = self.hook("prompt", {"prompt": "approve plan 12345678"})
            self.assertIn("no pending plan 12345678", reply["systemMessage"], content)
            self.assertNotIn("gate error", reply["systemMessage"], content)
            stop = self.hook("stop", {"last_assistant_message": PLAN})
            self.assertNotIn("gate error", json.dumps(stop), content)

    def test_a_crash_keeps_the_root_the_event_named(self):
        self.config({"on_error": "deny"})
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside)
        payload = {"session_id": {"x": 1}, "cwd": outside, "tool_name": "Bash",  # the session id makes the gate raise
                   "tool_input": {"command": "python " + os.path.join(self.root, "analysis", "x.py")}}
        proc = subprocess.run([sys.executable, LAUNCHER, "tool"], input=json.dumps(payload).encode("utf-8"),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=outside)
        result = json.loads(proc.stdout.decode("utf-8"))
        self.assertTrue(self.denied(result), result)
        self.assertTrue(os.path.isfile(os.path.join(self.root, ".mycelium-extra", "gate-errors.jsonl")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
