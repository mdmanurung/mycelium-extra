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
PLUGIN = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GATE = os.path.join(PLUGIN, "hooks", "gate.py")


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

    def mycelium(self, version):
        """A Mycelium plugin root of `version` (None: no manifest) that the repository's `.mycelium/plugin-root` names."""
        plugin = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, plugin)
        if version:
            os.mkdir(os.path.join(plugin, ".claude-plugin"))
            with open(os.path.join(plugin, ".claude-plugin", "plugin.json"), "w") as handle:
                json.dump({"name": "mycelium", "version": version}, handle)
        os.mkdir(os.path.join(self.root, ".mycelium"))
        with open(os.path.join(self.root, ".mycelium", "plugin-root"), "w") as handle:
            handle.write(plugin + "\n")

    def test_tested_mycelium_versions_add_no_notice(self):
        for version in ("0.6.0", "0.7.2"):
            shutil.rmtree(os.path.join(self.root, ".mycelium"), ignore_errors=True)
            self.mycelium(version)
            self.assertNotIn("Mycelium", run(self.root, "--dry-run"), version)

    def test_untested_mycelium_version_is_named_once_with_the_tested_ones(self):
        self.mycelium("0.8.1")
        out = run(self.root)
        self.assertEqual(out.count("note: Mycelium 0.8.1 is installed here; mycelium-extra was tested with "
                                   "0.6.0, 0.7.2."), 1, out)
        self.assertIn("note: Mycelium 0.8.1", run(self.root), "also when the gate is already on")

    def test_no_mycelium_says_nothing(self):
        self.assertNotIn("Mycelium", run(self.root))

    def test_unreadable_mycelium_version_is_said_not_assumed_fine(self):
        self.mycelium(None)
        self.assertIn("could not read Mycelium's version", run(self.root))
        self.assertFalse(os.path.exists(os.path.join(self.root, ".mycelium", "anything-else")))

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

    def test_glob_free_folder_pattern_is_warned_about(self):
        os.makedirs(os.path.join(self.root, "analysis", "x"))
        self.assertIn("without a glob", run(self.root, "--paths", "analysis", "--dry-run"))
        self.assertNotIn("without a glob", run(self.root, "--paths", "analysis/**", "--dry-run"))

    def test_non_utf8_gitignore_does_not_abort_init(self):
        with open(self.ignore, "wb") as handle:
            handle.write(b"# caf\xe9\n*.pyc")
        run(self.root)
        with open(self.ignore, "rb") as handle:
            self.assertEqual(handle.read(), b"# caf\xe9\n*.pyc\n# mycelium-extra approval gate: "
                             b"short-lived execution state\n.mycelium-extra/\n")

    def test_dry_run_writes_nothing(self):
        run(self.root, "--dry-run")
        self.assertEqual(os.listdir(self.root), [])

    def test_zero_hours_is_accepted(self):
        run(self.root, "--hours", "0")
        with open(os.path.join(self.root, ".mycelium-extra", "gate.json")) as handle:
            self.assertEqual(json.load(handle)["approval_hours"], 0)

    def test_invalid_hours_are_usage_errors_without_writes(self):
        for hours in ("nan", "inf", "-inf", "-1"):
            with open(SCRIPT) as source:
                proc = subprocess.run([sys.executable, "-", "--root", self.root,
                                       "--hours=" + hours], stdin=source,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      universal_newlines=True)
            self.assertEqual(proc.returncode, 2, hours)
            self.assertIn("--hours must be finite and 0 or more", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertEqual(os.listdir(self.root), [], hours)

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

    def fake(self, name, output, code=0):
        path = os.path.join(self.root, name)
        with open(path, "w") as handle:
            handle.write("#!/bin/sh\nprintf '%s' '{}'\nexit {}\n".format(output, code))
        os.chmod(path, 0o755)
        return path

    def test_tools_are_recorded_beside_an_existing_gate(self):
        run(self.root)
        gate_before = read(self.gate_json)
        python, rscript = self.fake("lint", ""), self.fake("rs", "0.1.1")
        out = run(self.root, "--tools", "--scilintr", python, "--rscript", rscript)
        self.assertIn("already gated", out)
        self.assertEqual(json.loads(read(os.path.join(self.root, ".mycelium-extra", "tools.json"))),
                         {"scilintr": python, "rscript": rscript, "scilintr_r": "0.1.1"})
        self.assertEqual(read(self.gate_json), gate_before)

    def test_nonobject_gate_is_reported_without_overwriting_it(self):
        os.mkdir(os.path.dirname(self.gate_json))
        for value in (None, [], "enabled"):
            with open(self.gate_json, "w") as handle:
                json.dump(value, handle)
            with open(SCRIPT) as source:
                proc = subprocess.run([sys.executable, "-", "--root", self.root], stdin=source,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      universal_newlines=True)
            self.assertEqual(proc.returncode, 1, value)
            self.assertIn("gate.json unreadable", proc.stdout)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertEqual(json.loads(read(self.gate_json)), value)
            self.assertFalse(os.path.exists(self.ignore))

    def test_nonobject_tools_are_reported_and_replaced_with_checked_tools(self):
        run(self.root)
        path = os.path.join(self.root, ".mycelium-extra", "tools.json")
        for value in (None, [], "tools"):
            with open(path, "w") as handle:
                json.dump(value, handle)
            out = run(self.root, "--tools", "--scilintr", self.fake("lint", ""),
                      "--rscript", self.fake("rs", "0.1.1"))
            self.assertIn("tools.json", out)
            self.assertIn("not a JSON object", out)
            self.assertEqual(json.loads(read(path))["scilintr_r"], "0.1.1")

    def test_a_tool_that_does_not_work_is_reported_and_not_recorded(self):
        run(self.root)
        broken, no_package = self.fake("lint", "boom", 1), self.fake("rs", "there is no package", 1)
        out = run(self.root, "--tools", "--scilintr", broken, "--rscript", no_package)
        self.assertIn("scilintr (Python) not found or not working", out)
        self.assertIn("scilintr (R) not found or not working", out)
        self.assertFalse(os.path.exists(os.path.join(self.root, ".mycelium-extra", "tools.json")))

    def test_working_tool_keeps_the_other_recorded_path(self):
        run(self.root)
        python, rscript = self.fake("lint", ""), self.fake("rs", "0.1.1")
        run(self.root, "--tools", "--scilintr", python, "--rscript", rscript)
        run(self.root, "--tools", "--scilintr", python, "--rscript", self.fake("bad", "", 1))
        tools = json.loads(read(os.path.join(self.root, ".mycelium-extra", "tools.json")))
        self.assertEqual(tools["rscript"], rscript)

    def test_fresh_init_with_tools_and_dry_run(self):
        python = self.fake("lint", "")
        out = run(self.root, "--tools", "--scilintr", python, "--rscript", self.fake("bad", "", 1), "--dry-run")
        self.assertIn("would write", out)
        self.assertFalse(os.path.exists(os.path.join(self.root, ".mycelium-extra")))


class DiagnoseTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.state = os.path.join(self.root, ".mycelium-extra")

    def diagnose(self, *args, **env):
        with open(SCRIPT) as source:
            return subprocess.check_output(
                [sys.executable, "-", "--root", self.root, "--diagnose", "--plugin-root", PLUGIN] + list(args),
                stdin=source, universal_newlines=True, env=dict(os.environ, **env))

    def listing(self):
        found = {}
        for folder, dirs, files in os.walk(self.root):
            for name in dirs + files:
                path = os.path.join(folder, name)
                found[path] = os.lstat(path).st_mtime_ns
        return found

    def state_file(self, name, text):
        os.makedirs(self.state, exist_ok=True)
        with open(os.path.join(self.state, name), "w") as handle:
            handle.write(text)

    def test_defaults_mirror_the_gate_and_cover_every_key(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("gate_init_under_test", SCRIPT)
        init = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(init)
        spec = importlib.util.spec_from_file_location("gate_under_test", GATE)
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        self.assertEqual(set(init.DEFAULTS), set(init.CONFIG_RULES))
        for key, value in gate.DEFAULTS.items():
            self.assertEqual(init.DEFAULTS[key], value, key)
        # defaults the gate applies inline (config.get(key, default)), not in gate.DEFAULTS
        for key, value in {"card_lint": True, "lint_on_write": True, "focus_notices": False,
                           "on_error": "allow"}.items():
            self.assertEqual(init.DEFAULTS[key], value, key)

    def test_diagnose_shows_every_key_with_its_default(self):
        out = self.diagnose()
        for key in ("card_coverage", "card_lint", "lint_on_write", "pin_scripts", "focus_notices"):
            self.assertIn("  " + key + ": ", out)
        self.assertIn("card_coverage: true  (default)", out)
        self.assertIn("focus_notices: false  (default)", out)

    def test_an_invalid_confirm_writes_is_flagged_and_false_is_the_default(self):
        self.assertIn("confirm_writes: false  (default)", self.diagnose())
        self.state_file("gate.json", json.dumps({"confirm_writes": "yes"}))
        self.assertIn('PROBLEM confirm_writes: "yes" is invalid; the gate wants true or false, and uses off.',
                      self.diagnose())

    def test_diagnose_writes_nothing_with_or_without_state(self):
        before = self.listing()
        out = self.diagnose()
        self.assertIn("gate: off here", out)
        self.assertEqual(self.listing(), before)
        self.assertFalse(os.path.exists(self.state))
        self.state_file("gate.json", "{}")
        self.state_file("receipts.jsonl", json.dumps({"host": "codex", "exit_status": 0, "kind": "sbatch"}) + "\n")
        self.state_file("gate-errors.jsonl", json.dumps({"event": "tool", "error": "boom", "decision": "allow"}) + "\n")
        before = self.listing()
        out = self.diagnose()
        self.assertEqual(self.listing(), before)
        self.assertIn("gate: on", out)
        self.assertIn("host codex; exit_status present: 0", out)
        self.assertIn("last gate error: tool hook, decision allow: boom", out)

    def test_invalid_config_value_and_unknown_key_are_flagged(self):
        self.state_file("gate.json", json.dumps({"approval_hours": -3, "lint_before_run": "sometimes",
                                                 "gated_pahts": ["x"], "pin_scripts": False}))
        out = self.diagnose()
        self.assertIn("PROBLEM approval_hours: -3 is invalid; the gate wants a number of 0 or more, and uses the default.", out)
        self.assertIn('PROBLEM lint_before_run: "sometimes" is invalid', out)
        self.assertIn("and uses off.", out)
        self.assertIn("PROBLEM gated_pahts: not a key this gate reads", out)
        self.assertNotIn("PROBLEM pin_scripts", out)
        self.assertIn("gated_paths: [\"analysis/**\", \"nbs/**\"]  (default)", out)

    def test_huge_integer_and_unchecked_list_keys_are_reported_honestly(self):
        self.state_file("gate.json", '{"approval_hours": 1' + "0" * 400 + ', "gated_commands": 5}')
        out = self.diagnose()
        self.assertIn("PROBLEM approval_hours:", out)
        self.assertIn("integer this large makes the gate error", out)
        self.assertIn("PROBLEM gated_commands: 5 is invalid; the gate wants a list of strings, and uses nothing: "
                      "the gate does not check it", out)

    def test_unreadable_gate_json_is_reported_with_exit_zero(self):
        self.state_file("gate.json", "[1]")
        self.assertIn("gate.json unreadable: expected a JSON object", self.diagnose())

    def test_missing_linter_is_reported(self):
        out = self.diagnose(PATH=self.root)
        self.assertIn("scilintr: not on PATH", out)
        self.assertIn("sacct: not on PATH", out)
        self.assertIn("Rscript: not on PATH", out)

    def test_works_without_mycelium_and_with_one(self):
        self.assertIn("mycelium: none found here", self.diagnose())
        plugin = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, plugin)
        os.mkdir(os.path.join(plugin, ".claude-plugin"))
        with open(os.path.join(plugin, ".claude-plugin", "plugin.json"), "w") as handle:
            json.dump({"version": "0.7.2"}, handle)
        os.mkdir(os.path.join(self.root, ".mycelium"))
        with open(os.path.join(self.root, ".mycelium", "plugin-root"), "w") as handle:
            handle.write(plugin)
        self.assertIn("mycelium: 0.7.2 at " + plugin + " (tested)", self.diagnose())

    def test_missing_plugin_root_is_said_and_the_caveat_always_printed(self):
        with open(SCRIPT) as source:
            out = subprocess.check_output([sys.executable, "-", "--root", self.root, "--diagnose"], stdin=source,
                                          universal_newlines=True,
                                          env={k: v for k, v in os.environ.items()
                                               if k not in ("CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT")})
        self.assertIn("hooks: plugin root not found", out)
        self.assertIn("does not prove the host has enabled or trusted the hooks", out)

    def test_diagnose_with_a_changing_option_is_a_usage_error(self):
        with open(SCRIPT) as source:
            proc = subprocess.run([sys.executable, "-", "--root", self.root, "--diagnose", "--hours", "5"],
                                  stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  universal_newlines=True)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(os.listdir(self.root), [])


if __name__ == "__main__":
    unittest.main()
