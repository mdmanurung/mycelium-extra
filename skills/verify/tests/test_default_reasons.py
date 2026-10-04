"""verify reports unexplained defaults in the frozen plan (roadmap D9).

Run: python3 skills/verify/tests/test_default_reasons.py

Approvals and receipts are made by the real gate hooks, as in test_verify.py. The
helpers are copied rather than imported, so this file runs on its own.
"""

import json
import os
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
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(PLUGIN, "hooks"))
import gate  # noqa: E402

FIT = "analysis/a/scripts/01_fit.py"
BH = "default: BH, since the tests are not strongly dependent and no weighting is planned"


def plan(*sources):
    lines = ["**Objective.** Fit the model.", "", "Outputs: analysis/a/outputs/", "",
             "| # | Step | Choice | Source | Validation |", "|---|---|---|---|---|"]
    lines += ["| {} | run `{}` step {} | x | {} | ok |".format(i + 1, FIT, i + 1, s) for i, s in enumerate(sources)]
    return "\n".join(lines + ["", "Plan status: READY"])


def hermetic(test):
    """Hide the host's env variables and ~/.conda from the gate and verify for one test."""
    saved = dict(os.environ)
    test.addCleanup(lambda: (os.environ.clear(), os.environ.update(saved)))
    for key in gate.HOOK_ENV + ("CLAUDE_CODE_SESSION_ID",):
        os.environ.pop(key, None)
    home = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, home)
    os.environ["HOME"] = home


class VerifyDefaultReasonsTest(unittest.TestCase):
    def setUp(self):
        hermetic(self)
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, ".mycelium-extra"))
        self.write(".mycelium-extra/gate.json", "{}")
        self.write(FIT, "print(1)\n", mtime=time.time() - 3600)
        self.tools = {name: self.tool("bin/" + name) for name in ("sacct", "scilintr", "Rscript")}

    def tearDown(self):
        shutil.rmtree(self.root)

    def write(self, rel, text, mtime=None, root=None):
        path = os.path.join(root or self.root, rel)
        if not os.path.isdir(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        with open(path, "w") as handle:
            handle.write(text)
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def tool(self, rel):
        path = self.write(rel, "#!/bin/sh\nexit 0\n")
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    def hook(self, event, payload):
        payload = dict(payload, session_id="s1", cwd=self.root)
        proc = subprocess.Popen([sys.executable, GATE, event], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate(json.dumps(payload).encode("utf-8"))
        self.assertEqual(proc.returncode, 0, err)
        return json.loads(out.decode("utf-8")) if out.strip() else None

    def approve_and_run(self, text):
        notice = self.hook("stop", {"last_assistant_message": text})["systemMessage"]
        digest = notice.split("approve plan ")[1][:8]
        self.hook("prompt", {"prompt": "approve plan " + digest})
        self.hook("post", {"tool_name": "Bash", "tool_input": {"command": "python " + FIT},
                           "tool_response": {"stdout": "", "exit_code": 0}})
        self.write("analysis/a/outputs/fit.tsv", "x\n")
        return digest

    def verify(self, digest, plugin=PLUGIN, json_out=False):
        with open(SCRIPT) as source:
            proc = subprocess.Popen([sys.executable, "-", "--plugin-root", plugin, "--repo", self.root,
                                     "--sacct", self.tools["sacct"], "--scilintr", self.tools["scilintr"],
                                     "--rscript", self.tools["Rscript"], "report", digest]
                                    + (["--json"] if json_out else []),
                                    stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.root)
            out, err = proc.communicate()
        self.assertEqual(proc.returncode, 0, err.decode("utf-8"))
        return out.decode("utf-8")

    def plugin_without_checker(self, broken=None):
        """A plugin root with the real hooks and no (or a broken) plan-review checker."""
        plugin = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, plugin)
        shutil.copytree(os.path.join(PLUGIN, "hooks"), os.path.join(plugin, "hooks"),
                        ignore=shutil.ignore_patterns("tests", "__pycache__"))
        if broken is not None:
            self.write("skills/plan-review/scripts/default_reasons.py", broken, root=plugin)
        return plugin

    def test_unexplained_defaults_are_named_by_row_and_status_is_unchanged(self):
        digest = self.approve_and_run(plan("default:", "default: standard", BH, "user"))
        out = self.verify(digest)
        self.assertIn("- **info**: Default without a usable reason (advisory): row 1 (run `{}` step 1): "
                      "\"default:\" is no reason.".format(FIT), out)
        self.assertIn("- **info**: Default without a usable reason (advisory): row 2 (run `{}` step 2): "
                      "\"default: standard\" is an empty phrase, not a reason.".format(FIT), out)
        self.assertNotIn("row 3", out)
        self.assertNotIn("row 4", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)
        result = json.loads(self.verify(digest, json_out=True))
        self.assertEqual(result["status"], "CONFORMS")
        self.assertEqual(sum("Default without a usable reason" in text for _, text in result["findings"]), 2)

    def test_explained_defaults_add_nothing(self):
        digest = self.approve_and_run(plan(BH, "default: matches step 2"))
        out = self.verify(digest)
        self.assertNotIn("Default", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)

    def test_missing_checker_is_a_gap(self):
        digest = self.approve_and_run(plan(BH))
        out = self.verify(digest, plugin=self.plugin_without_checker())
        self.assertIn("- **gap**: Default reasons not checked:", out)
        self.assertRegex(out, r"(ModuleNotFound|Import)Error")
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)

    def test_broken_checker_is_a_gap(self):
        digest = self.approve_and_run(plan(BH))
        out = self.verify(digest, plugin=self.plugin_without_checker("def check_plan(:\n"))
        self.assertIn("- **gap**: Default reasons not checked:", out)
        self.assertIn("SyntaxError", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)


if __name__ == "__main__":
    unittest.main()
