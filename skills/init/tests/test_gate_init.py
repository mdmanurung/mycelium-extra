"""Run: python3 skills/init/tests/test_gate_init.py"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "gate_init.py")
GATE = os.path.join(HERE, "..", "..", "..", "hooks", "gate.py")


def run(root, *args):
    with open(SCRIPT) as source:
        return subprocess.check_output([sys.executable, "-", "--root", root] + list(args),
                                       stdin=source, universal_newlines=True)


def read(path):
    with open(path) as handle:
        return handle.read()


class GateInitTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.gate_json = os.path.join(self.root, ".mycelium-extra", "gate.json")
        self.ignore = os.path.join(self.root, ".gitignore")

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_defaults_write_empty_config_and_ignore_line(self):
        os.mkdir(os.path.join(self.root, "analysis"))
        out = run(self.root)
        self.assertEqual(json.loads(read(self.gate_json)), {})
        self.assertIn(".mycelium-extra/\n", read(self.ignore))
        self.assertNotIn("WARNING", out)

    def test_second_run_changes_nothing(self):
        run(self.root, "--hours", "12")
        before = (read(self.gate_json), read(self.ignore))
        out = run(self.root, "--hours", "9999", "--paths", "nothing/**")
        self.assertIn("already gated", out)
        self.assertEqual((read(self.gate_json), read(self.ignore)), before)

    def test_nested_repo_under_gated_parent_is_already_gated(self):
        run(self.root)
        child = os.path.join(self.root, "sub")
        os.mkdir(child)
        self.assertIn("already gated", run(child))
        self.assertFalse(os.path.exists(os.path.join(child, ".mycelium-extra")))

    def test_gitignore_without_trailing_newline(self):
        with open(self.ignore, "w") as handle:
            handle.write("*.pyc")
        run(self.root)
        lines = read(self.ignore).splitlines()
        self.assertEqual(lines[0], "*.pyc")
        self.assertIn(".mycelium-extra/", lines)

    def test_existing_ignore_line_not_duplicated(self):
        with open(self.ignore, "w") as handle:
            handle.write(".mycelium-extra\n")
        run(self.root)
        self.assertEqual(read(self.ignore), ".mycelium-extra\n")

    def test_options_and_warning(self):
        out = run(self.root, "--paths", "scripts/**", "--commands", "sbatch", "--hours", "8")
        self.assertEqual(json.loads(read(self.gate_json)),
                         {"gated_paths": ["scripts/**"], "gated_commands": ["sbatch"],
                          "approval_hours": 8})
        self.assertIn("WARNING", out)

    def test_dry_run_writes_nothing(self):
        run(self.root, "--dry-run")
        self.assertEqual(os.listdir(self.root), [])

    def test_gate_denies_after_init(self):
        os.mkdir(os.path.join(self.root, "analysis"))
        with open(os.path.join(self.root, "analysis", "x.py"), "w") as handle:
            handle.write("print(1)\n")
        run(self.root)
        event = {"cwd": self.root, "hook_event_name": "PreToolUse", "tool_name": "Bash",
                 "tool_input": {"command": "python3 analysis/x.py"}}
        out = subprocess.run([sys.executable, GATE, "tool"], input=json.dumps(event),
                             stdout=subprocess.PIPE, universal_newlines=True).stdout
        self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
