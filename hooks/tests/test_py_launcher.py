"""hooks/py.sh picks a Python 3.9 or later; gate_run.py reports an older one through on_error."""

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HOOKS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCHER = os.path.join(HOOKS, "py.sh")
GATE_RUN = os.path.join(HOOKS, "gate_run.py")
PYTHON36 = "/usr/bin/python3.6"
OLD_PYTHON3 = "#!/bin/sh\n[ \"$1\" = -c ] && exit 1\n[ \"$1\" = -V ] && { echo Python 3.6.8; exit 0; }\necho old \"$@\"\n"


class LauncherTest(unittest.TestCase):
    def setUp(self):
        self.bin = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.bin)

    def launch(self, args, env, stdin=""):
        return subprocess.run(["/bin/sh", LAUNCHER] + args, input=stdin, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)

    def test_the_override_runs_a_script_from_stdin(self):
        env = dict(os.environ, MYCELIUM_EXTRA_PYTHON=sys.executable)
        out = self.launch(["-", "a b"], env, "import sys; print(sys.argv[1:], sys.version_info >= (3, 9))")
        self.assertEqual((out.returncode, out.stdout), (0, "['a b'] True\n"), out.stderr)

    def test_an_old_python3_alone_is_refused_except_by_a_hook(self):
        fake = os.path.join(self.bin, "python3")
        with open(fake, "w") as handle:
            handle.write(OLD_PYTHON3)
        os.chmod(fake, 0o755)
        env = {"PATH": self.bin}
        out = self.launch(["-"], env)
        self.assertEqual(out.returncode, 1)
        self.assertIn("needs Python 3.9 or later, found Python 3.6.8; set MYCELIUM_EXTRA_PYTHON", out.stderr)
        self.assertEqual(self.launch(["--hook", "x.py", "tool"], env).stdout, "old x.py tool\n")  # gate_run decides

    def test_a_versioned_python_wins_over_an_old_python3(self):
        for name, body in (("python3", OLD_PYTHON3), ("python3.11", "#!/bin/sh\necho new \"$@\"\n")):
            with open(os.path.join(self.bin, name), "w") as handle:
                handle.write(body)
            os.chmod(os.path.join(self.bin, name), 0o755)
        for args in (["-"], ["--hook", "-"]):
            self.assertEqual(self.launch(args, {"PATH": self.bin}).stdout, "new -\n", args)


class OldPythonGateTest(unittest.TestCase):
    def test_gate_run_stays_parseable_by_python_3_6(self):
        with open(GATE_RUN, encoding="utf-8") as handle:
            ast.parse(handle.read(), feature_version=(3, 6))  # best effort; the 3.6 run below is the real check

    @unittest.skipUnless(os.path.exists(PYTHON36), "needs " + PYTHON36)
    def test_an_old_python_follows_on_error(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        event = json.dumps({"cwd": root, "hook_event_name": "PreToolUse", "tool_name": "Bash",
                            "tool_input": {"command": "ls"}})

        def hook():
            out = subprocess.run([PYTHON36, GATE_RUN, "tool"], input=event, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, universal_newlines=True,
                                 env=dict(os.environ, MYCELIUM_EXTRA_REEXEC="1"))  # no hand-off: on_error decides
            self.assertEqual(out.returncode, 0, out.stderr)
            return json.loads(out.stdout) if out.stdout.strip() else None

        self.assertIsNone(hook())  # no gate here: silent
        os.makedirs(os.path.join(root, ".mycelium-extra"))
        for policy, decision in ((None, None), ("deny", "deny")):
            with open(os.path.join(root, ".mycelium-extra", "gate.json"), "w") as handle:
                json.dump({"on_error": policy} if policy else {}, handle)
            result = hook()
            text = json.dumps(result)
            self.assertIn("needs Python 3.9 or later", text)
            self.assertEqual(result.get("hookSpecificOutput", {}).get("permissionDecision"), decision)

    @unittest.skipUnless(os.path.exists(PYTHON36), "needs " + PYTHON36)
    def test_a_registration_that_runs_python3_directly_is_handed_to_py_sh(self):
        root, bin_dir = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        self.addCleanup(shutil.rmtree, bin_dir)
        os.makedirs(os.path.join(root, ".mycelium-extra"))
        with open(os.path.join(root, ".mycelium-extra", "gate.json"), "w") as handle:
            handle.write("{}")
        with open(os.path.join(bin_dir, "python3.11"), "w") as handle:
            handle.write("#!/bin/sh\necho \"$@\"\n/bin/cat\n")  # a newer Python that reports what it was given
        os.chmod(os.path.join(bin_dir, "python3.11"), 0o755)
        event = json.dumps({"cwd": root, "hook_event_name": "PreToolUse", "tool_name": "Bash",
                            "tool_input": {"command": "caf\u00e9"}})
        out = subprocess.run([PYTHON36, GATE_RUN, "tool"], input=event.encode("utf-8"), stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, env={"PATH": bin_dir})
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.decode("utf-8"), GATE_RUN + " tool\n" + event)
        self.assertFalse(os.path.exists(os.path.join(root, ".mycelium-extra", "gate-errors.jsonl")))


if __name__ == "__main__":
    unittest.main()
