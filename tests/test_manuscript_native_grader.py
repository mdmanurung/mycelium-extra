"""The native runbook's plumbing and the grader, against a SIMULATED `claude` shim.

Run: python3 tests/test_manuscript_native_grader.py

The shim stands in for Claude Code only so the runbook (tests/e2e/run_manuscript_native.sh) and the
grader (tests/e2e/grade_manuscript_native.py) can be tested here: it dispatches the real gate the way
hooks/hooks.json registers it (`sh hooks/py.sh --hook hooks/gate_run.py <entry>`), really runs the
commands, and writes stream-json lines. It is labelled simulated in its version line, so the grader
must call its bundles `not-native` while every other check passes. This is not a native run.
"""

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "e2e"))
import grade_manuscript_native as grade  # noqa: E402
import harness  # noqa: E402
import manuscript_scenario as ms  # noqa: E402

RUNBOOK = os.path.join(harness.REPO, "tests", "e2e", "run_manuscript_native.sh")

SHIM = r'''#!/usr/bin/env python3
"""SIMULATED claude shim for tests only: not Claude Code."""
import json, os, re, subprocess, sys, uuid
args = sys.argv[1:]
if args == ["--version"]:
    print("0.0.0 (simulated claude shim, not Claude Code)"); sys.exit(0)
if args[:2] == ["plugin", "validate"]:
    print("simulated shim: plugin not validated"); sys.exit(0)
def opt(name):
    return args[args.index(name) + 1] if name in args else None
prompt, plugin, sid = opt("-p"), opt("--plugin-dir"), opt("--resume") or "sim-" + uuid.uuid4().hex[:12]
cwd = os.getcwd()
def out(obj):
    print(json.dumps(obj)); sys.stdout.flush()
def hook(entry, name, payload):
    event = dict(payload, session_id=sid, cwd=cwd, hook_event_name=name)
    proc = subprocess.run(["sh", os.path.join(plugin, "hooks", "py.sh"), "--hook",
                           os.path.join(plugin, "hooks", "gate_run.py"), entry],
                          input=json.dumps(event).encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=dict(os.environ, CLAUDE_PLUGIN_ROOT=plugin), cwd=cwd)
    text = proc.stdout.decode().strip()
    reply = json.loads(text) if text else None
    out({"type": "system", "subtype": "hook_response", "hook_event_name": name,
         "tool_use_id": payload.get("tool_use_id"), "output": reply})
    return reply
out({"type": "system", "subtype": "init", "session_id": sid})
hook("prompt", "UserPromptSubmit", {"prompt": prompt})
if prompt.startswith("Reply with exactly"):
    text = prompt.split("\nBEGIN\n", 1)[1].rsplit("\nEND", 1)[0]
elif prompt.startswith("Run exactly"):
    for n, command in enumerate(re.findall(r"^\d+\. `(.+)`$", prompt, re.M), 1):
        tid = "toolu_sim_{}_{}".format(sid[-6:], n)
        out({"type": "assistant", "session_id": sid, "message": {"content": [
            {"type": "tool_use", "id": tid, "name": "Bash", "input": {"command": command}}]}})
        pre = hook("tool", "PreToolUse", {"tool_name": "Bash", "tool_input": {"command": command}, "tool_use_id": tid})
        if ((pre or {}).get("hookSpecificOutput") or {}).get("permissionDecision") == "deny":
            continue
        proc = subprocess.run(["bash", "-c", command], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
        o, e = proc.stdout.decode(), proc.stderr.decode()
        if proc.returncode == 0:
            hook("post", "PostToolUse", {"tool_name": "Bash", "tool_input": {"command": command}, "tool_use_id": tid,
                                         "tool_response": {"stdout": o, "stderr": e, "interrupted": False, "isImage": False}})
        else:
            hook("post", "PostToolUseFailure", {"tool_name": "Bash", "tool_input": {"command": command},
                                                "tool_use_id": tid, "error": "Exit code {}\n{}".format(proc.returncode, e or o)})
    text = "Done."
else:
    text = "Noted."
out({"type": "assistant", "session_id": sid, "message": {"content": [{"type": "text", "text": text}]}})
hook("stop", "Stop", {"last_assistant_message": text, "stop_hook_active": False})
out({"type": "result", "session_id": sid})
'''


def plan_digest():
    """The plan hash is a function of the plan text; read it off a throwaway gated project."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import test_manuscript_verify_e2e as oracle
    project = oracle.ManuscriptProject.for_scenario("S1")
    try:
        return project.approve(ms.plan_text())[0]
    finally:
        project.close()


@unittest.skipUnless(harness.git_available() and shutil.which("bash"), "git or bash is not installed")
class NativeRunbookWithShim(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="mx-native-shim-")
        cls.bin = os.path.join(cls.tmp, "bin")
        os.makedirs(cls.bin)
        with open(os.path.join(cls.bin, "claude"), "w") as handle:
            handle.write(SHIM.replace("#!/usr/bin/env python3", "#!" + sys.executable, 1))
        os.chmod(os.path.join(cls.bin, "claude"), 0o755)
        cls.digest = plan_digest()
        cls.bundles = {}
        for scenario in ms.NATIVE:
            cls.bundles[scenario] = cls.run_runbook(scenario)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def run_runbook(cls, scenario, approval=None):
        work = tempfile.mkdtemp(prefix="work-", dir=cls.tmp)
        home = tempfile.mkdtemp(prefix="home-", dir=cls.tmp)
        env = {k: v for k, v in os.environ.items() if k not in harness.SCRUB}
        env.update(harness.IDENTITY)
        env.update({"PATH": cls.bin + os.pathsep + env.get("PATH", "/usr/bin:/bin"), "HOME": home, "TZ": "UTC",
                    # a fresh HOME drops CI's global safe.directory; the container runs as root over a checkout
                    # another uid owns, and the runbook reads the plugin's git state
                    "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory", "GIT_CONFIG_VALUE_0": "*"})
        line = (approval if approval is not None else "approve plan " + cls.digest) + "\n"
        proc = subprocess.run(["sh", RUNBOOK, scenario, work], input=line.encode(), env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return {"code": proc.returncode, "out": proc.stdout.decode(), "err": proc.stderr.decode(),
                "bundle": os.path.join(work, scenario + ".tar.gz")}

    def graded(self, scenario):
        run = self.bundles[scenario]
        self.assertEqual(run["code"], 0, run["out"] + run["err"])
        result = grade.grade_bundle(run["bundle"])
        failing = sorted(k for k, c in result["checks"].items() if not c["ok"])
        return result, failing

    def test_runbook_shows_the_card_and_contract_before_asking(self):
        out = self.bundles["S1"]["out"]
        self.assertIn("approve plan " + self.digest, out)
        self.assertIn('"required_columns"', out)
        self.assertLess(out.index("approve plan " + self.digest), out.index("> "))

    def test_a_simulated_bundle_is_not_native_but_otherwise_consistent(self):
        for scenario, outcome in (("S1", "passed"), ("S2", "failed"), ("S3", "not run")):
            result, failing = self.graded(scenario)
            self.assertEqual(result["verdict"], "not-native", result)
            self.assertEqual(failing, ["host"], result)  # only the simulated version line fails
            self.assertEqual(result["observed"]["outcome"], outcome, result)

    def test_anything_but_an_approval_line_stops_the_runbook(self):
        run = self.run_runbook("S1", approval="yes")
        self.assertNotEqual(run["code"], 0)
        self.assertIn("not approved; stopping", run["err"])
        self.assertFalse(os.path.exists(run["bundle"]))

    def tampered(self, scenario, change):
        """Unpack a bundle, apply change(folder), grade the folder."""
        dest = tempfile.mkdtemp(prefix="tamper-", dir=self.tmp)
        with tarfile.open(self.bundles[scenario]["bundle"]) as tar:
            tar.extractall(dest)
        folder = os.path.join(dest, scenario)
        change(folder)
        result = grade.grade_folder(folder, "tampered")
        return result, sorted(k for k, c in result["checks"].items() if not c["ok"])

    def test_an_edited_contract_in_the_bundle_fails_the_project_check(self):
        def edit(folder):
            path = os.path.join(folder, "project", ms.CONTRACT)
            with open(path, "a") as handle:
                handle.write(" ")
        _, failing = self.tampered("S1", edit)
        self.assertIn("project", failing)

    def test_an_edited_verify_outcome_fails_the_outcome_check(self):
        def edit(folder):
            path = os.path.join(folder, "host", "verify_report.json")
            with open(path) as handle:
                report = json.load(handle)
            for v in report["validation"]:
                v["outcome"] = "passed"
            report["status"] = "CONFORMS"
            with open(path, "w") as handle:
                json.dump(report, handle)
        _, failing = self.tampered("S2", edit)
        self.assertIn("outcome", failing)

    def test_a_receipt_without_a_host_call_id_fails_dispatch(self):
        def edit(folder):
            path = os.path.join(folder, "project", ".mycelium-extra", "receipts.jsonl")
            with open(path) as handle:
                rows = [json.loads(line) for line in handle if line.strip()]
            for row in rows:
                row["call_id"] = None
            with open(path, "w") as handle:
                handle.write("".join(json.dumps(r) + "\n" for r in rows))
        _, failing = self.tampered("S1", edit)
        self.assertIn("dispatch", failing)


if __name__ == "__main__":
    unittest.main()
