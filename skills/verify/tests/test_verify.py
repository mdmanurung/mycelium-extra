"""Run: python3 skills/verify/tests/test_verify.py

Approvals and receipts are made by the real gate hooks, so the tests follow the
receipt format the gate actually writes.
"""

import base64
import glob
import hashlib
import json
import os
import pickle
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "verify.py")
PLUGIN = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
GATE = os.path.join(PLUGIN, "hooks", "gate.py")
sys.path.insert(0, os.path.join(PLUGIN, "hooks"))
sys.dont_write_bytecode = True
import gate  # noqa: E402

FIT = "analysis/a/scripts/01_fit.py"


def hermetic(test):
    """Hide the host's env variables and ~/.conda from the gate and verify for one test."""
    saved = dict(os.environ)
    test.addCleanup(lambda: (os.environ.clear(), os.environ.update(saved)))
    for key in gate.HOOK_ENV + ("CLAUDE_CODE_SESSION_ID",):
        os.environ.pop(key, None)
    home = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, home)
    os.environ["HOME"] = home


def plan(*rows, outputs="analysis/a/outputs/", inputs=None):
    lines = ["**Objective.** Fit the model; see `analysis/a/scripts/old.py` for the previous attempt.", ""]
    if inputs:
        lines.append("Inputs: " + inputs)
    if outputs is not None:
        lines.append("Outputs: " + outputs)
    lines += ["", "| # | Step | Choice | Source | Validation |", "|---|---|---|---|---|"]
    lines += ["| {} | {} | x | user | ok |".format(i + 1, row) for i, row in enumerate(rows)]
    return "\n".join(lines + ["", "Plan status: READY"])


class VerifyTest(unittest.TestCase):
    def test_write_lint_deadline_covers_both_languages_and_waiver_passes(self):
        verify = gate.load_verify()
        report = verify.Report()
        result = {"findings": [], "waivers": [(FIT, 1, "waiver")], "output": []}
        clock, limits = [100.0], []

        def run(command, **kwargs):
            limits.append(kwargs["timeout"])
            clock[0] += min(6, kwargs["timeout"])
            if kwargs["timeout"] < 6:
                raise subprocess.TimeoutExpired(command, kwargs["timeout"])
            return subprocess.CompletedProcess(command, 0, stdout="")

        with mock.patch.object(verify.time, "monotonic", side_effect=lambda: clock[0]), \
                mock.patch.object(verify.subprocess, "run", side_effect=run):
            verify.lint_languages(self.root, {"Python": [FIT], "R": ["analysis/a/x.R"]}, {}, report,
                                  result, self.scilintr, [self.rscript, "-e", "lint"], 8, deadline=116)
        self.assertEqual(limits, [8, 8, 4])
        self.assertEqual(report.status(), "CONFORMS_WITH_GAPS")

    def setUp(self):
        hermetic(self)
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, ".mycelium-extra"))
        self.write(".mycelium-extra/gate.json", "{}")
        self.write(FIT, "print(1)\n", mtime=time.time() - 3600)  # scripts predate their plan
        self.sacct = self.fake_sacct("")
        self.scilintr = self.fake_tool("bin/scilintr", "", 0)
        self.rscript = self.fake_tool("bin/Rscript", "", 0)

    def tearDown(self):
        shutil.rmtree(self.root)

    def write(self, rel, text, mtime=None):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write(text)
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def fake_sacct(self, line):
        path = self.write("bin/sacct", "#!/bin/sh\necho '{}'\n".format(line))
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    def fake_tool(self, rel, output, code):
        path = self.write(rel, "#!/bin/sh\nprintf '%s' '{}'\nexit {}\n".format(output, code))
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    def hook(self, event, payload):
        payload = dict(payload, session_id="s1", cwd=self.root)
        proc = subprocess.Popen([sys.executable, GATE, event], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate(json.dumps(payload).encode("utf-8"))
        self.assertEqual(proc.returncode, 0, err)
        return json.loads(out.decode("utf-8")) if out.strip() else None

    def approve(self, text):
        notice = self.hook("stop", {"last_assistant_message": text})["systemMessage"]
        digest = notice.split("approve plan ")[1][:8]
        self.hook("prompt", {"prompt": "approve plan " + digest})
        return digest

    def run_cmd(self, command, exit_code=0, stdout="", writes=None):
        """A run the gate saw from start to end: its Pre callback, which must allow it, then its
        Post with the same tool_use_id (as Claude Code and Codex send them). `writes` ({path: text})
        are files the run itself writes, between its Pre and its Post, so the gate sees them change.
        Returns the receipt."""
        self.calls = getattr(self, "calls", 0) + 1
        call_id = "toolu_test_{}".format(self.calls)
        reply = self.hook("tool", {"tool_name": "Bash", "tool_input": {"command": command}, "tool_use_id": call_id})
        decision = ((reply or {}).get("hookSpecificOutput") or {}).get("permissionDecision")
        self.assertNotEqual(decision, "deny", "the gate denied `{}`; use post_only for a run it blocks: {}".format(
            command, reply))
        for rel, text in sorted((writes or {}).items()):
            self.write(rel, text)
        return self.post_only(command, exit_code, stdout, call_id=call_id)

    def post_only(self, command, exit_code=0, stdout="", call_id=None):
        """A Post callback with no Pre before it: a run the gate never launched (a denied or missed
        call, or a host that sends no Pre). Returns the receipt."""
        event = {"tool_name": "Bash", "tool_input": {"command": command},
                 "tool_response": {"stdout": stdout, "exit_code": exit_code}}
        if call_id:
            event["tool_use_id"] = call_id
        self.hook("post", event)
        receipts = gate.state_path(self.root, "receipts.jsonl")
        with open(receipts) as handle:
            return json.loads(handle.readlines()[-1])

    def verify(self, *args, **kwargs):
        with open(SCRIPT) as source:
            proc = subprocess.Popen([sys.executable, "-", "--plugin-root", PLUGIN, "--repo", self.root,
                                     "--sacct", kwargs.get("sacct", self.sacct),
                                     "--scilintr", kwargs.get("scilintr", self.scilintr),
                                     "--rscript", kwargs.get("rscript", self.rscript)] + list(args),
                                    stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    cwd=self.root)
            out, err = proc.communicate()
        if kwargs.get("fails"):
            self.assertNotEqual(proc.returncode, 0)
            return err.decode("utf-8")
        self.assertEqual(proc.returncode, 0, err.decode("utf-8"))
        return out.decode("utf-8")

    def test_plan_naming_scripts_by_absolute_and_relative_path(self):
        second = "analysis/a/scripts/02_plot.py"
        self.write(second, "print(2)\n", mtime=time.time() - 3600)
        digest = self.approve(plan("run `{}/{}`".format(self.root, FIT), "run `{}`".format(second)))
        self.run_cmd("python " + FIT)
        out = self.verify("report", digest)
        self.assertIn("| `{}` | ran".format(FIT), out)  # reported root-relative, once
        self.assertNotIn("`{}/".format(self.root), out)
        self.assertIn(digest, self.verify("status"))

    def edited_after_run(self, pins=True):
        """Plan 1 runs FIT; the script is then edited. Returns plan 1's hash."""
        if not pins:
            self.write(".mycelium-extra/gate.json", json.dumps({"pin_scripts": False}))
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.run_cmd("python " + FIT)
        return digest

    def age(self, digest):
        """Plan `digest` falls out of the gate's 24 h window, so a later run is not credited to it."""
        path = os.path.join(self.root, ".mycelium-extra", "approvals", digest + ".json")
        with open(path) as handle:
            record = json.load(handle)
        record["approved_at"] -= 3 * 86400
        with open(path, "w") as handle:
            json.dump(record, handle)

    def second_plan(self):
        return self.approve(plan("run `{}`".format(FIT), outputs="analysis/a/outputs2/"))

    def test_edited_script_never_run_since_has_no_approval(self):
        digest = self.edited_after_run()
        self.write(FIT, "print(1)\nprint(2)\n", mtime=time.time() + 100)  # a different size, as most edits are
        out = self.verify("report", digest)
        self.assertIn("`{}` was edited after its run".format(FIT), out)
        self.assertIn("has not run under any plan, so no approval covers it", out)
        self.assertIn("Verify status: DOES_NOT_CONFORM", out)

    def test_edited_script_pinned_by_a_later_plan_is_covered(self):
        digest = self.edited_after_run()
        self.write(FIT, "print(2)\n", mtime=time.time() - 60)
        later = self.second_plan()
        out = self.verify("report", digest)
        self.assertIn("Plan {} pinned this version".format(later), out)
        self.assertIn("Verify status: DOES_NOT_CONFORM", out)

    def test_edited_script_run_after_a_later_approval_is_covered_by_file_time(self):
        digest = self.edited_after_run(pins=False)
        self.age(digest)
        self.write(FIT, "print(2)\n", mtime=time.time() - 60)
        later = self.second_plan()
        self.run_cmd("python " + FIT)
        out = self.verify("report", digest)
        self.assertIn("ran under plan {}".format(later), out)
        self.assertIn("after the file was last modified, so an approval covers it by file time", out)

    def test_edited_script_run_under_an_older_approval_is_not_covered(self):
        digest = self.edited_after_run(pins=False)
        self.age(digest)
        later = self.second_plan()
        self.write(FIT, "print(2)\n", mtime=time.time() + 100)  # edited after plan 2 approved
        self.run_cmd("python " + FIT)
        out = self.verify("report", digest)
        self.assertIn("ran under plan {}, but that plan was approved before the file was last modified".format(later), out)
        self.assertIn("no approval covers it", out)

    def test_conforming_run(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})  # the run writes its declared output between Pre and Post
        out = self.verify("report", digest)
        self.assertIn("| `{}` | ran |".format(FIT), out)
        self.assertIn("`python {}`".format(FIT), out)
        self.assertIn("analysis folder `analysis/a`", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)

    def conforming_run(self):
        """A conforming run of FIT. Returns (plan hash, approval time)."""
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        return digest, gate.read_json(gate.state_path(self.root, "approvals", digest + ".json"), {})["approved_at"]

    def gate_errors(self, *errors, raw=None):
        self.write(".mycelium-extra/gate-errors.jsonl",
                   raw if raw is not None else "".join(json.dumps(e) + "\n" for e in errors))

    def test_gate_error_in_window_prevents_clean_observation(self):
        digest, approved = self.conforming_run()
        now = int(time.time())
        self.gate_errors({"ts": now, "event": "tool", "decision": "allow", "session_id": "s1", "error": "boom"})
        out = self.verify("report", digest)
        self.assertIn("Gate error at {} (event `tool`, decision allow, session s1)".format(time.strftime(
            "%Y-%m-%d %H:%M", time.localtime(now))), out)
        self.assertIn("observation is incomplete there", out)
        self.assertIn("not a record that any specific action went unobserved", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)

    def test_gate_error_without_session_is_still_a_gap(self):  # the journal's earlier record shape
        digest, approved = self.conforming_run()
        self.gate_errors({"ts": int(time.time()), "event": "post", "error": "x"}, {"ts": "garbage"})
        out = self.verify("report", digest)
        self.assertIn("Gate error at", out)
        self.assertIn("(event `post`)", out)
        self.assertIn("observation history unavailable", out)  # the malformed line is reported, not skipped
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)

    def test_gate_error_before_approval_or_other_session_is_ignored(self):
        digest, approved = self.conforming_run()
        self.gate_errors({"ts": int(approved) - 100, "event": "tool", "session_id": "s1", "error": "old"},
                         {"ts": int(time.time()), "event": "post", "session_id": "another-session", "error": "else"})
        out = self.verify("report", digest)
        self.assertNotIn("Gate error at", out)
        self.assertNotIn("observation history", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)

    def test_corrupt_gate_error_journal_is_a_gap(self):
        digest, approved = self.conforming_run()
        self.gate_errors(raw="not json\n")
        out = self.verify("report", digest)
        self.assertIn("observation history unavailable", out)
        self.assertIn("gate-errors.jsonl", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)

    def test_run_cmd_sends_pre_then_post_and_post_only_sends_no_pre(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        launches = gate.state_path(self.root, "launches")
        self.post_only("python " + FIT)
        self.assertFalse(os.path.isdir(launches))  # no Pre ever wrote a launch record
        receipt = self.run_cmd("python " + FIT)
        self.assertTrue(os.path.isdir(launches))  # Pre wrote one, and the matching Post took it
        self.assertEqual(os.listdir(launches), [])
        self.assertEqual(receipt["plans"], [digest])
        self.run_cmd("python " + FIT)  # each call has its own id, so a second run finds its own launch
        self.assertEqual(os.listdir(launches), [])

    def test_competing_timestamp_writers_are_a_gap(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        first = self.run_cmd("python " + FIT)
        self.run_cmd("python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=first["ts"])
        out = self.verify("report", digest)
        self.assertIn("competing timestamp-compatible writers", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)

    def test_metadata_only_input_fingerprints_never_prove_content(self):
        self.write("data/huge.tsv", "value\n")
        digest = self.approve(plan("run `{}`".format(FIT), inputs="data/huge.tsv"))
        path = gate.state_path(self.root, "approvals", digest + ".json")
        with open(path) as handle:
            record = json.load(handle)
        record["pins"]["data/huge.tsv"].pop("sha256", None)
        with open(path, "w") as handle:
            json.dump(record, handle)
        self.run_cmd("python " + FIT)
        out = self.verify("report", digest)
        self.assertIn("metadata-only fingerprint", out)

    def test_interrupted_first_save_is_visible_to_status_and_stale(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        folder = os.path.join(self.root, "analysis", "a", "provenance")
        os.makedirs(os.path.join(folder, ".transactions"))
        self.write("analysis/a/provenance/.transactions/pending.json", json.dumps({
            "transaction": "txn-interrupted", "members": {"receipts-" + digest + ".jsonl": {}}}))
        self.assertIn("interrupted", self.verify("status"))
        self.assertIn("interrupted", self.verify("stale"))
        self.assertIn("Saved provenance bundle is interrupted", self.verify("report", digest))

    def test_unknown_exit_status_is_a_gap(self):
        # Claude Code's Bash result may carry no exit status; the run is then not a success.
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.hook("post", {"tool_name": "Bash", "tool_input": {"command": "python " + FIT},
                           "tool_response": {"stdout": "", "stderr": "", "interrupted": False}})
        receipts = gate.state_path(self.root, "receipts.jsonl")
        with open(receipts) as handle:
            receipt = json.loads(handle.readlines()[-1])
        self.assertEqual(receipt["exit_status"], "unknown")
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        out = self.verify("report", digest)
        self.assertIn("| `{}` | ran (exit status unknown) |".format(FIT), out)
        self.assertIn("carried no exit status, so the run is not counted as a success", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)
        with open(receipts, "a") as handle:  # older gates wrote null
            handle.write(json.dumps(dict(receipt, exit_status=None, ts=receipt["ts"] + 0.01)) + "\n")
        out = self.verify("report", digest)
        self.assertIn("| `{}` | ran (exit status unknown) |".format(FIT), out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)
        self.run_cmd("python " + FIT)  # a later run that reports exit 0 conforms
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=time.time())
        repeated = self.verify("report", digest)
        self.assertIn("competing timestamp-compatible writers", repeated)
        self.assertTrue(repeated.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"))

    def test_compound_command_exit_does_not_prove_each_step_ran(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        receipt = self.run_cmd("python " + FIT)
        receipt.update(exit_status="unknown", exit_source=None, command_exit_status=0,
                       command_exit_source="response")
        path = gate.state_path(self.root, "receipts.jsonl")
        for status, expected in [(0, "CONFORMS_WITH_GAPS"), (1, "DOES_NOT_CONFORM"),
                                 ("failed", "DOES_NOT_CONFORM"), ("interrupted", "DOES_NOT_CONFORM")]:
            with self.subTest(command_exit_status=status):
                receipt["command_exit_status"] = status
                with open(path, "w") as handle:
                    handle.write(json.dumps(receipt) + "\n")
                out = self.verify("report", digest)
                self.assertIn("execution not attributable (compound command)", out)
                self.assertTrue(out.rstrip().endswith("Verify status: " + expected), out)
                if status != 0:
                    self.assertIn("**block**: Compound command", out)

    def test_damaged_receipts_are_reported_as_gaps(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        receipt = self.run_cmd("python " + FIT)
        damaged = ['{"truncated":', 'null', '[]', '42', '{}',
                   json.dumps(dict(receipt, ts="yesterday")),
                   json.dumps(dict(receipt, ts=1e300)),
                   json.dumps(dict(receipt, command=3)),
                   json.dumps(dict(receipt, paths="not a list"))]
        with open(gate.state_path(self.root, "receipts.jsonl"), "a") as handle:
            handle.write("\n".join(damaged) + "\n")
        out = self.verify("report", digest)
        self.assertIn("9 malformed receipt record(s)", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)
        for action in [("list",), ("status",), ("explore", "--all"), ("multiplicity", digest)]:
            self.verify(*action)

    def test_exit_status_from_the_hook_event(self):
        # PostToolUse fires only after success: an event-inferred 0 conforms.
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        command = {"command": "python " + FIT}
        ok = {"stdout": "", "stderr": "", "interrupted": False}
        self.hook("tool", {"tool_name": "Bash", "tool_input": command, "tool_use_id": "t1"})  # the launch is checked
        self.write(self.OUT, "x\n")
        self.hook("post", {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": command,
                           "tool_response": ok, "tool_use_id": "t1"})
        out = self.verify("report", digest)
        self.assertIn("| `{}` | ran (exit 0 from hook event) |".format(FIT), out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)
        # PostToolUseFailure: the same finding as a failed run with an exit code.
        self.hook("post", {"hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "tool_input": command,
                           "error": "Exit code 2\nTraceback ..."})
        out = self.verify("report", digest)
        self.assertIn("| `{}` | failed (exit 2) |".format(FIT), out)
        self.assertIn("`{}` failed (exit 2) at".format(FIT), out)
        self.assertTrue(out.rstrip().endswith("Verify status: DOES_NOT_CONFORM"), out)
        for extra, row, finding in (
                ({"error": "Command timed out after 2m 0s"}, "failed (no exit code)",
                 "failed without an exit code at {}: Command timed out after 2m 0s"),
                ({"error": "Exit code 130", "is_interrupt": True}, "interrupted", "was interrupted at {}")):
            self.hook("post", dict(extra, hook_event_name="PostToolUseFailure", tool_name="Bash",
                                   tool_input=command))
            out = self.verify("report", digest)
            self.assertIn("| `{}` | {} |".format(FIT, row), out)
            self.assertRegex(out, re.escape("`{}` ".format(FIT)) + finding.format(".*"))
            self.assertTrue(out.rstrip().endswith("Verify status: DOES_NOT_CONFORM"), out)
        # A background start or a payload with no event name is unknown: a gap, not a success.
        self.hook("post", {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_response": ok,
                           "tool_input": dict(command, run_in_background=True)})
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=time.time())
        out = self.verify("report", digest)
        self.assertIn("| `{}` | started in the background (exit status unknown) |".format(FIT), out)
        self.assertIn("so its exit status is not known", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)
        self.hook("post", {"tool_name": "Bash", "tool_input": command, "tool_response": ok})
        out = self.verify("report", digest)
        self.assertIn("| `{}` | ran (exit status unknown) |".format(FIT), out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)

    def test_output_never_repeats_the_plan_status_line(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.run_cmd("python " + FIT)
        for args in (("report", digest), ("report", digest, "--json"), ("list",),
                     ("write", digest, "--analysis-dir", "analysis/a")):
            self.assertIsNone(gate.PLAN_STATUS.search(self.verify(*args)), args)
        with open(os.path.join(self.root, "analysis/a/provenance/plan-{}.md".format(digest))) as handle:
            self.assertIn("Plan status: READY", handle.read())

    def test_explore_run_of_a_planned_script_does_not_count(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.hook("prompt", {"prompt": "allow explore"})
        receipt = self.run_cmd("MYCELIUM_EXTRA_EXPLORE=1 python " + FIT)
        self.assertEqual(receipt["plans"], [digest])  # the gate still names the covering plan
        out = self.verify("report", digest)
        self.assertIn("| `{}` | no receipt |".format(FIT), out)
        self.assertIn("Explore run in the analysis folder", out)
        self.assertIn("(explore, not reportable)", out)
        self.assertIn("0 run(s) under this plan", out)
        self.assertIn("not a git repository", out)

    def test_failed_run_and_edited_script_block(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.run_cmd("python " + FIT, exit_code=1)
        out = self.verify("report", digest)
        self.assertIn("failed (exit 1)", out)
        self.assertIn("Verify status: DOES_NOT_CONFORM", out)
        self.run_cmd("python " + FIT)
        self.write(FIT, "print(2)\n")
        out = self.verify("report", digest)
        self.assertIn("was edited after its run", out)
        self.assertIn("Verify status: DOES_NOT_CONFORM", out)

    def test_outputs_older_than_approval_or_untied(self):
        self.write("analysis/a/outputs/old.tsv", "x\n", mtime=time.time() - 3600)
        digest = self.approve(plan("run `{}`".format(FIT),
                                   outputs="analysis/a/outputs/old.tsv, analysis/a/outputs/"))
        receipt = self.run_cmd("python " + FIT)
        self.write("analysis/a/outputs/late.tsv", "x\n", mtime=receipt["ts"] + 600)
        out = self.verify("report", digest)
        self.assertIn("**block**: Output `analysis/a/outputs/old.tsv` was written", out)
        self.assertIn("Output `analysis/a/outputs/late.tsv` (written", out)
        self.assertIn("not tied to any recorded run", out)

    def stamp_last_receipt(self, ts):
        path = gate.state_path(self.root, "receipts.jsonl")
        with open(path) as handle:
            lines = [json.loads(line) for line in handle]
        lines[-1]["ts"] = ts
        with open(path, "w") as handle:
            handle.write("".join(json.dumps(line) + "\n" for line in lines))

    def other_plan_runs(self, *scripts):
        """Approve a plan for FIT, then run `scripts` under another plan, 100 s apart; return their ts."""
        digest = self.approve(plan("run `{}`".format(FIT)))
        for script in scripts:
            self.write(script, "print(3)\n", mtime=time.time() - 3600)
        self.approve(plan(*["run `{}`".format(s) for s in scripts]))
        stamps = []
        for i, script in enumerate(scripts):
            self.run_cmd("python " + script)
            stamps.append(time.time() + 100 * (i + 1))
            self.stamp_last_receipt(stamps[-1])
        return digest, stamps

    def test_outputs_of_one_foreign_run_are_one_gap_naming_the_script(self):
        extra = "analysis/a/scripts/02_extra.py"
        digest, (ts,) = self.other_plan_runs(extra)
        for name in ("a.tsv", "b.tsv", "c.tsv", "d.tsv"):
            self.write("analysis/a/outputs/" + name, "x\n", mtime=ts - 1)
        out = self.verify("report", digest)
        self.assertEqual(out.count("was likely written by"), 0)
        self.assertEqual(out.count("likely written by"), 1)
        self.assertIn("4 files in `analysis/a/outputs/` were likely written by", out)
        self.assertIn("`python " + extra, out)
        self.assertIn("`a.tsv`, `b.tsv`, `c.tsv` and 1 more", out)
        self.assertIn("| `analysis/a/outputs/d.tsv` |", out)  # the Outputs table still lists every file

    def test_two_foreign_runs_give_two_gaps_and_a_single_output_keeps_its_text(self):
        first, second = "analysis/a/scripts/02_extra.py", "analysis/a/scripts/03_more.py"
        digest, (ts1, ts2) = self.other_plan_runs(first, second)
        self.write("analysis/a/outputs/a.tsv", "x\n", mtime=ts1 - 1)
        self.write("analysis/a/outputs/b.tsv", "x\n", mtime=ts1 - 1)
        self.write("analysis/a/outputs/c.tsv", "x\n", mtime=ts2 - 1)
        out = self.verify("report", digest)
        self.assertEqual(out.count("likely written by"), 2)
        self.assertIn("2 files in `analysis/a/outputs/` were likely written by", out)
        self.assertIn("`python " + first, out)
        self.assertIn("Output `analysis/a/outputs/c.tsv` was likely written by `python " + second, out)

    def test_a_long_interpreter_path_still_shows_the_script(self):
        extra = "analysis/a/scripts/02_extra.py"
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.write(extra, "print(3)\n", mtime=time.time() - 3600)
        self.approve(plan("run `{}`".format(extra)))
        python = self.write("envs/" + "very_long_environment_name/" * 4 + "bin/python", "")
        os.chmod(python, os.stat(python).st_mode | stat.S_IEXEC)
        self.run_cmd(python + " " + extra)
        self.write("analysis/a/outputs/a.tsv", "x\n", mtime=time.time() + 100)
        self.stamp_last_receipt(time.time() + 101)
        out = self.verify("report", digest)
        self.assertIn("(script `{}`)".format(extra), out)

    def test_untied_outputs_group_by_folder(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        for name in ("a.tsv", "b.tsv"):
            self.write("analysis/a/outputs/" + name, "x\n", mtime=time.time() + 600)
        out = self.verify("report", digest)
        self.assertIn("2 files in `analysis/a/outputs/` (written", out)
        self.assertIn("not tied to any recorded run", out)

    def test_earlier_runs_files_in_an_output_folder_are_not_blocking(self):
        self.write("analysis/a/results/run_0930/old.tsv", "x\n", mtime=time.time() - 3600)
        digest = self.approve(plan("run `{}`".format(FIT), outputs="analysis/a/results/run_*/*.tsv"))
        self.run_cmd("python " + FIT, writes={"analysis/a/results/run_1001/new.tsv": "x\n"})
        out = self.verify("report", digest)
        self.assertIn("1 file(s) under `analysis/a/results/run_*/*.tsv` predate this plan", out)
        self.assertNotIn("run_0930/old.tsv`", out)
        self.assertIn("| `analysis/a/results/run_1001/new.tsv` |", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)

    def test_reapproving_the_same_plan_keeps_its_earlier_runs(self):
        text = plan("run `{}`".format(FIT), outputs=self.OUT)
        digest = self.approve(text)
        receipt = self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        path = gate.state_path(self.root, "approvals", digest + ".json")
        record = gate.read_json(path, None)
        record["approved_at"] = receipt["ts"] + 86400  # approved again a day later
        with open(path, "w") as handle:
            json.dump(record, handle)
        out = self.verify("report", digest)
        self.assertIn("| `{}` | ran |".format(FIT), out)
        self.assertIn("re-approved; first run", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)

    def test_output_lists_are_read_and_shorthand_is_one_gap(self):
        # B2: `{a,b}` lists and `<name>` placeholders are read; a `…` word names no path.
        digest = self.approve(plan("run `{}`".format(FIT), outputs=(
            "analysis/a/outputs/fit_{a,b}_{x,y}.rds, analysis/a/outputs/scope_<subset>.csv, `\u2026_meta.csv`")))
        receipt = self.run_cmd("python " + FIT)
        for name in ("fit_a_x", "fit_a_y", "fit_b_x", "fit_b_y"):
            self.write("analysis/a/outputs/{}.rds".format(name), "x\n", mtime=receipt["ts"] + 1)
        self.write("analysis/a/outputs/scope_bcells.csv", "x\n", mtime=receipt["ts"] + 1)
        out = self.verify("report", digest)
        # the report escapes what the locale cannot print (backslashreplace), so accept either form
        self.assertTrue(any("Output `{}_meta.csv` is shorthand that names no path".format(dots) in out
                            for dots in ("\u2026", "\\u2026")), out)
        self.assertEqual(out.count("does not exist"), 0, out)
        self.assertIn("| `analysis/a/outputs/fit_b_y.rds` |", out)
        self.assertIn("| `analysis/a/outputs/scope_bcells.csv` |", out)

    def test_plan_without_outputs_line_is_a_gap(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs=None))
        self.run_cmd("python " + FIT)
        out = self.verify("report", digest)
        self.assertIn("no `Outputs:` line", out)
        self.assertIn("Verify status: CONFORMS_WITH_GAPS", out)

    def test_changed_pinned_input_blocks(self):
        self.write("data/samples.tsv", "a\n")
        digest = self.approve(plan("run `{}`".format(FIT), inputs="data/samples.tsv"))
        self.run_cmd("python " + FIT)
        self.write("data/samples.tsv", "a\nb\n")
        out = self.verify("report", digest)
        self.assertIn("Input `data/samples.tsv` changed since the approval", out)
        self.assertIn("(changed)", out)

    def test_script_outside_the_table_that_ran(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.write("analysis/a/scripts/02_extra.py", "print(3)\n")
        self.write("analysis/a/scripts/old.py", "print(0)\n")
        self.run_cmd("python " + FIT)
        other = self.approve(plan("run `analysis/a/scripts/02_extra.py`"))
        self.run_cmd("python analysis/a/scripts/02_extra.py")
        out = self.verify("report", digest)
        self.assertIn("`analysis/a/scripts/02_extra.py` ran since the approval but is not in the plan", out)
        self.assertIn("(under plan {})".format(other), out)
        self.assertIn("1 other script(s) in the analysis folder", out)  # old.py, cited only in prose

    def snakemake_record(self, output, rule, start, inputs, shellcmd, folder="analysis/a", code=None):
        name = base64.urlsafe_b64encode(output.encode("utf-8")).decode("ascii")
        self.write(folder + "/.snakemake/metadata/" + name, json.dumps({
            "rule": rule, "starttime": start, "endtime": start + 1, "incomplete": False,
            "input": inputs, "shellcmd": shellcmd, "code": code}))

    def test_snakemake_script_rules_and_inputs(self):
        # A rule input is read, not run. A `script:` rule's path is in `code`: base64 of a pickled
        # code object before Snakemake 9, the rule's source text in 9.x.
        def pickle_code(code):  # Snakemake 8's persistence.pickle_code
            consts = [(pickle_code(c) if type(c) == type(code) else c) for c in code.co_consts]
            return pickle.dumps((code.co_code, code.co_varnames, consts, code.co_names), protocol=4)
        scope = {}
        exec("def run(input, output, basedir):\n    script('01_step.py', basedir, input, output)\n", scope)
        old = base64.b64encode(pickle_code(scope["run"].__code__)).decode("ascii")
        steps = ["analysis/a/01_step.py", "analysis/a/02_step.py", "analysis/a/03_helper.py"]
        for path in steps:
            self.write(path, "x\n", mtime=time.time() - 60)
        digest = self.approve(plan(*["`{}`".format(p) for p in steps]))
        start = time.time()
        self.snakemake_record("outputs/1.tsv", "s01", start, ["data/in.tsv"], None, code=old)
        self.snakemake_record("outputs/2.tsv", "s02", start, ["02_step.py"], None,
                              code='    script: "02_step.py"\n')
        self.snakemake_record("outputs/3.tsv", "s03", start, ["03_helper.py"],
                              "python other.py > outputs/3.tsv")
        out = self.verify("report", digest)
        self.assertIn("| `analysis/a/01_step.py` | ran in Snakemake rule `s01` |", out)
        self.assertIn("| `analysis/a/02_step.py` | ran in Snakemake rule `s02` |", out)
        self.assertIn("| `analysis/a/03_helper.py` | no receipt |", out)
        self.assertIn("`analysis/a/03_helper.py`: no run under this plan was recorded.", out)

    def test_steps_inside_a_snakemake_wrapper(self):
        # The rule shapes new-analysis generates: the step file is the `script=` or `notebook=` input,
        # and later steps take the previous step's output as `prev=`.
        step, notebook = "analysis/a/01_step.R", "analysis/a/02_plot.ipynb"
        for path in (step, notebook, "analysis/a/run.sh"):
            self.write(path, "x\n", mtime=time.time() - 60)
        digest = self.approve(plan("`analysis/a/run.sh`", "`{}`".format(step), "`{}`".format(notebook),
                                   outputs="analysis/a/outputs/01_table.tsv analysis/a/outputs/02_plot.pdf"))
        start = time.time()
        self.snakemake_record("outputs/01_table.tsv", "s01_step", start, ["01_step.R", "data/in.tsv"],
                              "Rscript 01_step.R data/in.tsv outputs/01_table.tsv > logs/01_step.log 2>&1")
        self.snakemake_record("outputs/02_plot.pdf", "s02_plot", start, ["02_plot.ipynb", "outputs/01_table.tsv"],
                              "jupyter nbconvert --to notebook --execute 02_plot.ipynb --output-dir logs "
                              "--output 02_plot.ipynb")
        self.run_cmd("bash analysis/a/run.sh", writes={"analysis/a/outputs/01_table.tsv": "x\n",
                                                       "analysis/a/outputs/02_plot.pdf": "x\n"})
        out = self.verify("report", digest)
        self.assertIn("| `{}` | ran in Snakemake rule `s01_step` |".format(step), out)
        self.assertIn("| `{}` | ran in Snakemake rule `s02_plot` |".format(notebook), out)
        self.assertIn("wrapper: 2 Snakemake job(s) ran inside", out)
        self.assertIn("via Snakemake rule `s01_step`", out)
        self.assertIn("via Snakemake rule `s02_plot`", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)

    def test_snakemake_records_beside_a_planned_script(self):
        # run.sh `cd`s into its own folder, so Snakemake writes its records there, below the
        # analysis folder; the Snakefile counts as run by the rules it defines.
        top, step, snakefile = "analysis/p/top.R", "analysis/p/a/01_step.R", "analysis/p/a/Snakefile"
        for path in (top, step):
            self.write(path, "x\n", mtime=time.time() - 60)
        self.write(snakefile, "rule s01_step:\n    input: script='01_step.R'\n", mtime=time.time() - 60)
        digest = self.approve(plan("`{}`".format(top), "`{}`".format(step), "`{}`".format(snakefile)))
        self.snakemake_record("outputs/t.tsv", "s01_step", time.time(), ["01_step.R"], "Rscript 01_step.R",
                              folder="analysis/p/a")
        out = self.verify("report", digest)
        self.assertIn("analysis folder `analysis/p`", out)
        self.assertIn("| `{}` | ran in Snakemake rule `s01_step` |".format(step), out)
        self.assertIn("| `{}` | ran in Snakemake rule `s01_step` |".format(snakefile), out)
        os.remove(os.path.join(self.root, step))
        out = self.verify("report", digest)
        self.assertIn("`{}` was deleted after its Snakemake run".format(step), out)
        self.assertIn("Verify status: DOES_NOT_CONFORM", out)

    def test_a_named_log_is_not_a_script(self):
        # B3: a Step cell names a log to read; the rule writing it mentions it, then rewrites it.
        # A shebang `.sbatch` and a `Snakefile.x` have no script extension but are still scripts.
        log, job, snakefile = "analysis/a/logs/fit.log", "analysis/a/02_job.sbatch", "analysis/a/Snakefile.fit"
        texts = {log: "x\n", job: "#!/bin/bash\nRscript 01_step.R\n",
                 snakefile: "rule fit:\n    shell: 'bash 02_job.sbatch'\n"}
        for path, text in texts.items():
            self.write(path, text, mtime=time.time() - 60)
        digest = self.approve(plan("`{}`".format(snakefile), "`{}`".format(job), "read `{}`".format(log)))
        start = time.time()
        self.snakemake_record("outputs/fit.tsv", "fit", start, [], "bash 02_job.sbatch > logs/fit.log 2>&1")
        for path, text in texts.items():
            self.write(path, text + "# edited\n", mtime=start + 60)
        out = self.verify("report", digest)
        self.assertNotIn(log, out)  # no script row, finding, or Folder line
        self.assertIn("`{}` was edited after its Snakemake run".format(job), out)
        self.assertIn("`{}` was edited after its Snakemake run".format(snakefile), out)

    def test_paths_only_passed_to_other_code_are_not_runs(self):
        digest = self.approve(plan("run `{}`".format(FIT), "sbatch job.sh"))
        self.run_cmd("python3 -c 'import ast' " + FIT)  # a parse check
        self.run_cmd("python3 - --code={} < /tmp/tool.py".format(FIT))  # another tool's script
        with open(gate.state_path(self.root, "receipts.jsonl"), "a") as handle:  # older gates recorded these
            handle.write(json.dumps({"command": "command -v sbatch", "kind": "sbatch", "paths": [],
                                     "plans": [digest], "ts": time.time(), "cwd": "."}) + "\n")
        out = self.verify("report", digest)
        self.assertIn("| `{}` | not run: only passed to other code |".format(FIT), out)
        self.assertIn("lint and parse calls look like this", out)
        self.assertIn("0 run(s) under this plan", out)
        self.assertIn("2 receipt(s) under this plan only passed planned paths", out)
        self.assertIn("The plan names `sbatch`, but no `sbatch` run under it was recorded.", out)
        self.run_cmd("python3 - < " + os.path.join(self.root, FIT))  # the script itself read from stdin runs
        self.assertIn("| `{}` | ran ".format(FIT), self.verify("report", digest))

    def test_deleted_script_and_code_in_an_output_folder(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs="outputs/"))
        receipt = self.run_cmd("python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        self.write("analysis/a/outputs/helper.py", "x\n", mtime=receipt["ts"] - 1)
        os.remove(os.path.join(self.root, FIT))
        out = self.verify("report", digest)
        self.assertIn("deleted since it ran", out)
        self.assertNotIn("edited", out)
        self.assertIn("Output `outputs/` read as `analysis/a/outputs/`", out)
        self.assertIn("analysis/a/outputs/fit.tsv", out)
        self.assertNotIn("helper.py", out)

    def test_sbatch_state_comes_from_sacct(self):
        self.write("analysis/a/job.sh", "#!/bin/bash\n#SBATCH -t 1:00:00\npython analysis/a/scripts/01_fit.py\n")
        digest = self.approve(plan("`sbatch analysis/a/job.sh`"))
        self.run_cmd("sbatch analysis/a/job.sh", stdout="Submitted batch job 4242")
        done = self.fake_sacct("4242|COMPLETED|0:0|2026-09-30T10:00:00|2026-09-30T10:05:00")
        self.assertIn("job 4242 COMPLETED", self.verify("report", digest, sacct=done))
        failed = self.fake_sacct("4242|FAILED|1:0|2026-09-30T10:00:00|2026-09-30T10:05:00")
        out = self.verify("report", digest, sacct=failed)
        self.assertIn("Slurm job 4242 ended FAILED", out)
        self.assertIn("Verify status: DOES_NOT_CONFORM", out)
        missing = self.verify("report", digest, sacct=os.path.join(self.root, "no-sacct"))
        self.assertIn("state unknown (no sacct)", missing)

    def test_sbatch_job_is_matched_by_its_sacct_submit_line(self):
        # `$F` hides the script from the gate; Slurm records the expanded line.
        digest = self.approve(plan("`sbatch --wrap \"python {}\"`".format(FIT)))
        self.run_cmd('sbatch -J a --wrap "python $F"', stdout="Submitted batch job 4243")
        line = "4243|{}|0:0|2026-09-30T10:00:00|2026-09-30T10:05:00|" + self.root + "|sbatch --wrap=python {}"
        out = self.verify("report", digest, sacct=self.fake_sacct(line.format("COMPLETED", FIT)))
        self.assertIn("job 4243 COMPLETED | ", out)
        self.assertIn("matched by its sacct submit line", out)
        out = self.verify("report", digest, sacct=self.fake_sacct(line.format("FAILED", "other.py")))
        self.assertIn("`sbatch -J a --wrap python $F`: Slurm job 4243 ended FAILED", out)  # a command receipt
        array = self.write("bin/sacct-array", "#!/bin/sh\nprintf '4243_1|COMPLETED|0:0|||\\n4243_2|TIMEOUT|0:0|||\\n'\n")
        os.chmod(array, os.stat(array).st_mode | stat.S_IEXEC)
        self.assertIn("Slurm job 4243 ended TIMEOUT", self.verify("report", digest, sacct=array))
        self.run_cmd('sbatch -J b --wrap "python $F"', stdout="Submitted batch job 4243")  # one shared output
        out = self.verify("report", digest, sacct=self.fake_sacct(line.format("COMPLETED", FIT)))
        self.assertIn("job 4243 (state not attributable)", out)

    def test_invalid_external_timestamps_do_not_crash_verification(self):
        verify = gate.load_verify()
        for stamp in ["2026-02-30T10:00:00Z", "2026-10-16T99:00:00Z", 42]:
            with self.subTest(stamp=stamp):
                self.assertIsNone(verify.parse_iso(stamp))
        sacct = self.fake_sacct("4242|COMPLETED|0:0|2026-09-30T10:00:00|2026-02-30T10:05:00")
        self.assertIsNone(verify.sacct_state(sacct, 4242, time.time())["end"])

    def test_malformed_snakemake_metadata_does_not_prove_a_run(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        name = base64.urlsafe_b64encode(b"outputs/table.tsv").decode("ascii")
        for data in [[], {"starttime": "yesterday"}, {"endtime": "NaN"}, {"shellcmd": ["python", FIT]}]:
            with self.subTest(metadata=data):
                self.write("analysis/a/.snakemake/metadata/" + name, json.dumps(data))
                out = self.verify("report", digest)
                self.assertIn("no run under this plan was recorded", out)
                self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)

    def test_lineage_shows_computation_the_gate_did_not_see(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.run_cmd("python " + FIT)
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.write(".living/log/data-lineage/2026-10-01-001.json", json.dumps({
            "session_id": "2026-10-01-001",
            "actions": [{"ts": stamp, "script": "/tmp/scratchpad/smoke.R"},
                        {"ts": stamp, "script": os.path.join(self.root, FIT)},
                        {"ts": stamp, "script": None, "bash_cmd": "python3 -c 'print(1)'"}]}))
        out = self.verify("report", digest)
        self.assertIn("lineage saw `/tmp/scratchpad/smoke.R`", out)
        self.assertNotIn("lineage saw `{}`".format(FIT), out)
        self.assertIn("1 inline command(s)", out)

    def test_write_provenance_and_rewrite(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs="analysis/a/"))
        receipt = self.run_cmd("python " + FIT)
        self.run_cmd("python3 -c 'import ast' " + FIT)  # kept in provenance, marked as not a run
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        out = self.verify("write", digest, "--analysis-dir", "analysis/a")
        folder = os.path.join(self.root, "analysis/a/provenance")
        for name in ("PROVENANCE.md", "plan-{}.md", "receipts-{}.jsonl", "outputs-{}.tsv", "verify-{}.md"):
            self.assertTrue(os.path.isfile(os.path.join(folder, name.format(digest))), name)
            self.assertIn("wrote analysis/a/provenance/" + name.format(digest), out)
        with open(os.path.join(folder, "receipts-{}.jsonl".format(digest))) as handle:
            ran, handed = [json.loads(line) for line in handle]
        self.assertEqual(ran["command"], "python " + FIT)
        self.assertNotIn("not_a_run", ran)
        self.assertIn("other code", handed["not_a_run"])
        with open(os.path.join(folder, "outputs-{}.tsv".format(digest))) as handle:
            rows = [line.rstrip("\n").split("\t") for line in handle][1:]
        self.assertEqual([r[0] for r in rows], ["analysis/a/outputs/fit.tsv"])  # the script predates the plan
        self.assertEqual(len(rows[0][3]), 64)  # the full sha256
        self.verify("write", digest, "--analysis-dir", "analysis/a")
        with open(os.path.join(folder, "PROVENANCE.md")) as handle:
            self.assertEqual(sum(line.startswith("| {} |".format(digest)) for line in handle), 1)
        self.assertNotIn("provenance/", self.verify("report", digest).split("## Outputs")[1].split("##")[0])

    def test_write_needs_the_folder_and_list_shows_plans(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.assertIn("--analysis-dir", self.verify("write", digest, fails=True))
        self.assertIn("| {} |".format(digest), self.verify("list"))
        self.run_cmd("python " + FIT)
        self.run_cmd("python " + FIT)
        self.run_cmd("python3 -c 'import ast' " + FIT)  # a parse check is not a run
        row, = [line for line in self.verify("list").splitlines() if digest in line]
        self.assertTrue(row.endswith("| 2 |"), row)
        self.assertIn("no approved plan", self.verify("report", "deadbeef", fails=True))

    def test_diff_shows_changed_rows_and_flags_choice(self):
        old = self.approve(plan("run `{}`".format(FIT), "run `analysis/a/scripts/02_plot.py`",
                                inputs="data/samples.tsv"))
        changed = plan("run `{}`".format(FIT), "run `analysis/a/scripts/03_report.py`", "run `analysis/a/run.sh`",
                       inputs="data/samples.tsv, analysis/a/Snakefile").replace(
            "| 1 | run `{}` | x |".format(FIT), "| 1 | run `{}` | donor-level |".format(FIT))
        notice = self.hook("stop", {"last_assistant_message": changed})["systemMessage"]
        new = notice.split("approve plan ")[1][:8]  # shown, not yet approved: the moment to diff
        out = self.verify("diff", old, new)
        self.assertIn("Step 1, choice: `x` -> `donor-level`. **Possible scientific change.**", out)
        self.assertIn("Step 2, step: `run `analysis/a/scripts/02_plot.py`` -> "
                      "`run `analysis/a/scripts/03_report.py``.", out)
        self.assertNotIn("Step 2, step: `run `analysis/a/scripts/02_plot.py`` -> "
                         "`run `analysis/a/scripts/03_report.py``. **Possible", out)
        self.assertIn("Step 3: added:", out)
        self.assertIn("- Inputs: + analysis/a/Snakefile", out)
        self.assertIn("No plan-table row", self.verify("diff", old, old))
        self.assertIn("needs the old and the new", self.verify("diff", old, fails=True))

    def shown(self, text):
        """The hash of a plan the gate showed but nobody approved, so `diff` can read it."""
        return self.hook("stop", {"last_assistant_message": text})["systemMessage"].split("approve plan ")[1][:8]

    def diff_of(self, old, new):
        return self.verify("diff", self.shown(old), self.shown(new))

    def test_diff_reports_a_change_after_a_long_shared_prefix(self):
        prefix = "a long shared rationale " * 12  # well past 200 characters
        base = plan("run `{}`".format(FIT))
        out = self.diff_of(base.replace("| x |", "| {}alpha |".format(prefix)),
                           base.replace("| x |", "| {}beta |".format(prefix)))
        self.assertIn("Step 1, choice: `{}alpha` -> `{}beta`. **Possible scientific change.**".format(prefix, prefix), out)

    def test_diff_reports_removed_row_and_removed_input(self):
        out = self.diff_of(plan("run `{}`".format(FIT), "run `analysis/a/scripts/02_plot.py`",
                                inputs="data/a.tsv, data/b.tsv"),
                           plan("run `{}`".format(FIT), inputs="data/a.tsv"))
        self.assertIn("- Step 2: removed (was: ", out)
        self.assertIn("- Inputs: - data/b.tsv", out)

    def test_diff_reports_reordered_steps(self):
        first, second = "run `{}`".format(FIT), "run `analysis/a/scripts/02_plot.py`"
        rows = plan(first, second).splitlines()
        swapped = "\n".join(rows[:-4] + [rows[-3], rows[-4]] + rows[-2:])  # rows keep their IDs, change position
        self.assertLess(swapped.index("| 2 |"), swapped.index("| 1 |"))
        out = self.diff_of(plan(first, second), swapped)
        self.assertIn("Step order changed: 1 2 -> 2 1", out)
        self.assertNotIn("removed", out)
        self.assertNotIn("added", out)

    def test_diff_reports_removed_column(self):
        old = plan("run `{}`".format(FIT))
        new = old.replace("| # | Step | Choice | Source | Validation |", "| # | Step | Choice | Source |").replace(
            "|---|---|---|---|---|", "|---|---|---|---|").replace("| x | user | ok |", "| x | user |")
        self.assertIn("- Column `validation` removed.", self.diff_of(old, new))

    def test_diff_cannot_compare_duplicate_ids(self):
        old = plan("run `{}`".format(FIT), "run `analysis/a/scripts/02_plot.py`")
        new = old.replace("| 2 | run `analysis/a/scripts/02_plot.py` | x |", "| 1 | run `analysis/a/scripts/02_plot.py` | y |")
        out = self.diff_of(old, new)
        self.assertIn("- Step 1: cannot compare (duplicate ID in the new plan)", out)
        self.assertIn("- Step 2: removed", out)
        self.assertNotIn("Step 1, choice", out)  # the overwritten row is not silently compared

    def test_diff_reads_id_headers_in_any_column_and_rows_without_one(self):
        verify = gate.load_verify()
        table = "| Step | {} | Choice |\n|---|---|---|\n| run a | 7 | x |\n| run b | 8 | y |\n"
        for header in ("ID", "id", "No.", "no", "#"):
            rows, unusable, columns = verify.plan_rows(table.format(header))
            self.assertEqual(list(rows), ["7", "8"], header)
            self.assertEqual(rows["8"]["choice"], "y")
        rows, unusable, columns = verify.plan_rows("| ID | Step |\n|---|---|\n| | run a |\n| 1 | run b |\n")
        self.assertEqual(list(rows), ["1"])
        self.assertIn("(no ID)", unusable)

    def test_diff_reports_a_long_changed_objective(self):
        prefix = "Estimate the effect of treatment on expression, adjusting for batch " * 5
        base = plan("run `{}`".format(FIT))
        old = base.replace("Fit the model; see", prefix + "in donors; see")
        out = self.diff_of(old, old.replace("in donors; see", "in all samples; see"))
        self.assertIn("- Objective changed: ", out)
        self.assertIn("in donors; see", out)
        self.assertIn("in all samples; see", out)
        self.assertIn("**Possible scientific change.**", out)

    def test_diff_reports_outputs_bindings_exact_execution_and_scope(self):
        old = plan("run `{}`".format(FIT), outputs="analysis/a/outputs/fit.tsv")
        new = plan("run `{}`".format(FIT), "run `analysis/a/scripts/02_plot.py`", outputs="analysis/a/outputs/fit2.tsv")
        bindings = '\n<!-- validation-bindings {"version": 1, "checks": []} -->\n'
        exact = '\n<!-- exact-execution {"version": 1, "steps": []} -->\n'
        out = self.diff_of(old, new + bindings + exact)
        self.assertIn("- Outputs: + analysis/a/outputs/fit2.tsv", out)
        self.assertIn("- Outputs: - analysis/a/outputs/fit.tsv", out)
        self.assertIn("- Validation bindings: added", out)
        self.assertIn("- Exact execution: added", out)
        self.assertIn("- Scope: + analysis/a/scripts/02_plot.py", out)
        changed = self.diff_of(new + bindings + exact, new + bindings.replace("[]", '[{"id": "V-1", "plan_row": "1", "required": true, '
                                '"defined_by": "agent-proposed", "test_paths": ["analysis/a/scripts/01_fit.py"], '
                                '"invocation": ["python", "analysis/a/scripts/01_fit.py"], '
                                '"evidence_path": "analysis/a/outputs/v1.json"}]') + exact)
        self.assertIn("- Validation bindings: changed", changed)
        self.assertNotIn("Exact execution", changed)

    def test_diff_treats_formatting_only_changes_as_no_change(self):
        old = plan("run `{}`".format(FIT), inputs="data/a.tsv")
        new = old.replace("| 1 | run", "|   1   |   run").replace("**Objective.** Fit the model;",
                                                                  "**Objective.**   Fit  the\tmodel;").replace(
            "\n\n|", "\n\n\n|") + "\n\n"
        self.assertIn("No plan-table row, objective, `Inputs:`, `Outputs:`, binding block or scope changed.",
                      self.diff_of(old, new))

    def test_multiplicity_lists_revisions_and_runs_before_the_selected_plan(self):
        def choice(text, value):
            return plan("run `{}`".format(FIT)).replace("| x |", "| {} |".format(value)) + "\n" + text
        other = self.approve(plan("run `analysis/b/scripts/01_other.py`", outputs="analysis/b/outputs/"))
        gone = self.approve(choice("Moved away.", "BH 0.2"))
        self.run_cmd("python " + FIT)
        os.remove(gate.state_path(self.root, "approvals", gone + ".json"))
        first = self.approve(choice("", "BH 0.1"))
        self.hook("prompt", {"prompt": "allow explore"})
        self.run_cmd("MYCELIUM_EXTRA_EXPLORE=1 python " + FIT)
        self.run_cmd("MYCELIUM_EXTRA_EXPLORE=1 python {} --fdr 0.2".format(FIT))
        self.write(FIT, "print(2)\n")
        self.run_cmd("MYCELIUM_EXTRA_EXPLORE=1 python " + FIT, exit_code=1)
        second = self.approve(choice("Second try.", "BH 0.05"))
        self.run_cmd("python " + FIT)
        self.write(FIT, "print(3)\n")
        digest = self.approve(choice("", "paired t; BH 0.05"))
        self.hook("post", {"tool_name": "Bash", "tool_input": {"command": "python " + FIT},
                           "tool_response": {"stdout": ""}})
        out = self.verify("multiplicity", digest)
        self.assertIn("2 earlier plan revision(s), 3 explore run(s) before the approval, 1 run(s) under "
                      "earlier plans, 1 run(s) under this plan. 1 run(s) under a plan whose approval is not on file "
                      "(gap). 2 of 2 plan change(s) edited a Choice cell.", out)
        self.assertIn("| plan {} | first plan |".format(first), out)
        self.assertIn("| plan {} | step 1 choice: `BH 0.1` -> `BH 0.05` |".format(second), out)
        self.assertIn("| plan {} | approved (selected); step 1 choice: `BH 0.05` -> `paired t; BH 0.05` |"
                      .format(digest), out)
        self.assertIn("| explore run | `MYCELIUM_EXTRA_EXPLORE=1 python {} --fdr 0.2` (other code version) | 0 |"
                      .format(FIT), out)
        self.assertIn("| run (plan {}) | `python {}` (other code version) | 0 |".format(second, FIT), out)
        self.assertIn("| run | `python {}` | not recorded |".format(FIT), out)
        self.assertNotIn(other, out)
        self.assertIn("| run (plan {}, approval not on file) |".format(gone), out)
        order = [out.index(x) for x in (first, "--fdr 0.2", "| 1 |", second, "| run | ")]
        self.assertEqual(order, sorted(order))
        data = json.loads(self.verify("multiplicity", digest, "--json"))
        self.assertEqual((data["revisions"], data["counts"]["explore before"]), (2, 3))
        self.assertIn("no approved plan", self.verify("multiplicity", "0" * 8, fails=True))

    def test_stale_lists_what_changed_since_provenance(self):
        self.assertIn("No verified plans", self.verify("stale"))
        self.write("data/samples.tsv", "a\n")
        digest = self.approve(plan("run `{}`".format(FIT), outputs="analysis/a/outputs/", inputs="data/samples.tsv"))
        receipt = self.run_cmd("python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        self.write("analysis/a/outputs/keep.tsv", "y\n", mtime=receipt["ts"] - 1)
        self.verify("write", digest, "--analysis-dir", "analysis/a")
        self.assertIn("0 of 1 verified plans stale", self.verify("stale"))
        self.write(FIT, "print(2)\n")
        self.write("data/samples.tsv", "a\nb\n")
        self.write("analysis/a/outputs/fit.tsv", "x2\n")
        os.remove(os.path.join(self.root, "analysis/a/outputs/keep.tsv"))
        os.remove(os.path.join(self.root, ".mycelium-extra", "gate.json"))  # provenance alone suffices
        out = self.verify("stale")
        self.assertIn("## Plan {} - `analysis/a`".format(digest), out)
        self.assertIn("script `{}` edited since it ran".format(FIT), out)
        self.assertIn("input `data/samples.tsv` changed", out)
        self.assertIn("output `analysis/a/outputs/fit.tsv` rewritten", out)
        self.assertIn("output `analysis/a/outputs/keep.tsv` deleted", out)
        self.assertIn("sessions: s1", out)
        self.assertIn("findings: `rg -n 's1|plan {}' .living/findings/`".format(digest), out)
        self.assertIn("1 of 1 verified plans stale", out)
        self.assertNotIn("Plan status", out)
        self.assertEqual(json.loads(self.verify("stale", "--json"))["stale"][0]["hash"], digest)
        subprocess.check_call(["git", "-C", self.root, "init", "-q"])  # git lists untracked provenance too
        self.assertIn("1 of 1 verified plans stale", self.verify("stale"))
        self.write(".gitignore", "analysis/\n")  # ignored provenance is not swept
        self.assertIn("No verified plans", self.verify("stale"))

    def test_scilintr_findings_block_and_missing_linter_is_a_gap(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        self.write("analysis/a/scripts/02_plot.R", "x <- 1  # ANALYSIS_OK[magic-threshold]: fixed by design\n",
                   mtime=time.time() - 3600)
        self.write("analysis/a/outputs/junk.py", "pass\n")  # outputs are not linted
        clean = self.verify("report", digest)
        self.assertIn("scilintr: 1 Python file(s) clean", clean)
        self.assertIn("scilintr: 1 R file(s) clean", clean)
        self.assertIn("`analysis/a/scripts/02_plot.R:1` x <- 1", clean)
        self.assertTrue(clean.rstrip().endswith("Verify status: CONFORMS"), clean)
        broken = self.write("analysis/a/scripts/03_broken.py", "def f(:\n    pass\n", mtime=time.time() - 3600)
        out = self.verify("report", digest)  # scilintr passes code that does not parse, silently
        self.assertIn("`analysis/a/scripts/03_broken.py` does not parse under Python", out)
        self.assertIn("scilintr: 1 Python file(s) clean", out)
        self.assertIn("Verify status: CONFORMS_WITH_GAPS", out)
        os.remove(broken)
        finding = FIT + ":3:0: [broad-exception] broad except"
        dirty = self.fake_tool("bin/scilintr-dirty", finding + "\\n", 1)
        out = self.verify("report", digest, scilintr=dirty)
        self.assertIn("1 scilintr finding(s) remain in Python code (1 broad-exception)", out)
        self.assertIn("`{}:3` [broad-exception]".format(FIT), out)
        self.assertIn("Verify status: DOES_NOT_CONFORM", out)
        missing = self.verify("report", digest, scilintr=os.path.join(self.root, "no-scilintr"))
        self.assertIn("scilintr (Python) not checked", missing)
        self.assertIn("gate_init.py --tools --scilintr PATH", missing)
        self.assertIn("Verify status: CONFORMS_WITH_GAPS", missing)
        broken = self.fake_tool("bin/Rscript-broken", "there is no package called scilintr", 1)
        self.assertIn("scilintr (R) not checked: exit 1", self.verify("report", digest, rscript=broken))
        self.verify("write", digest, "--analysis-dir", "analysis/a", scilintr=dirty)
        with open(os.path.join(self.root, "analysis/a/provenance/lint-{}.txt".format(digest))) as handle:
            text = handle.read()
        self.assertIn("[broad-exception]", text)
        self.assertIn("ANALYSIS_OK waivers (1)", text)

    def notebook(self, rel, cells, language="python"):
        self.write(rel, json.dumps({
            "metadata": {"kernelspec": {"language": language}},
            "cells": [{"cell_type": kind, "source": source.splitlines(True)} for kind, source in cells]}),
            mtime=time.time() - 3600)

    def test_notebook_code_cells_are_linted(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        receipt = self.run_cmd("python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        flagger = self.write("bin/flagger", "#!{}\nimport os, sys\nhits = 0\nfor path in sys.argv[1:]:\n"
                             "    if os.path.isfile(path):\n        for n, line in enumerate(open(path), 1):\n"
                             "            if 'FLAG' in line and not line.lstrip().startswith('#'):\n                hits += 1\n"
                             "                print('{{}}:{{}}:0: [magic-threshold] flagged'.format(path, n))\n"
                             "sys.exit(1 if hits else 0)\n".format(sys.executable))
        os.chmod(flagger, os.stat(flagger).st_mode | stat.S_IEXEC)
        self.notebook("analysis/a/03_explore.ipynb", [
            ("markdown", "# FLAG in prose is ignored"), ("code", "%matplotlib inline\nimport os"),
            ("code", "%%bash\nls FLAG"), ("code", "x = 1\ny = x  # FLAG")])
        self.notebook("analysis/a/04_plot.ipynb", [("code", "FLAG <- 1")], language="R")
        rmd = ["---", "title: FLAG", "---", "FLAG in prose", "```{r setup, include=FALSE}", "x <- 1", "```",
               "```r", "FLAG in a display block", "```", "```{bash}", "echo FLAG", "```",
               "````markdown", "```{r}", "FLAG in a shown example", "```", "````",
               "```{R label}", "y <- FLAG", "```", "Inline `r FLAG` is skipped."]
        self.write("analysis/a/05_notes.Rmd", "\n".join(rmd) + "\n")
        qmd = ["```{python}", "#| echo: false", "%matplotlib inline", "!echo FLAG", "w = FLAG", "```",
               "```{.python}", "FLAG", "```", "```{r}", "v <- FLAG", "```"]
        self.write("analysis/a/06_mixed.qmd", "\n".join(qmd) + "\n")
        self.write("analysis/a/07_prose.qmd", "Prose only, FLAG.\n")
        out = self.verify("report", digest, scilintr=flagger, rscript=flagger)
        self.assertIn("`analysis/a/03_explore.ipynb[code cell 3]:2` [magic-threshold]", out)
        self.assertIn("2 scilintr finding(s) remain in Python code", out)
        self.assertIn("`analysis/a/04_plot.ipynb[code cell 1]:1` [magic-threshold]", out)
        self.assertIn("`analysis/a/05_notes.Rmd:{}` [magic-threshold]".format(rmd.index("y <- FLAG") + 1), out)
        self.assertIn("`analysis/a/06_mixed.qmd:{}` [magic-threshold]".format(qmd.index("w = FLAG") + 1), out)
        self.assertIn("`analysis/a/06_mixed.qmd:{}` [magic-threshold]".format(qmd.index("v <- FLAG") + 1), out)
        self.assertIn("3 scilintr finding(s) remain in R code", out)
        self.assertIn("1 notebook(s) not linted: analysis/a/07_prose.qmd", out)
        self.assertNotIn("mycelium-extra-lint-", out)
        self.notebook("analysis/a/08_broken.ipynb", [("code", "def f(:\n    pass")])
        self.write("analysis/a/09_broken.qmd", "Text\n```{python}\ndef f(:\n```\n")
        out = self.verify("report", digest)
        self.assertIn("scilintr (Python) not checked: `analysis/a/08_broken.ipynb` does not parse", out)
        self.assertIn("scilintr (Python) not checked: `analysis/a/09_broken.qmd` does not parse", out)
        self.assertIn("line 3", out)
        self.assertIn("Verify status: CONFORMS_WITH_GAPS", out)

    def test_chunk_lint_parked_cases(self):
        """E5: a document-level `eval: false` is linted like chunk-level `eval=FALSE`; `engine=` picks the
        language and other engines are skipped; `child=` and `read_chunk()` files are linted under their own
        paths, even outside the analysis folder, and a path that is not a quoted string or is missing is a gap."""
        digest = self.approve(plan("run `{}`".format(FIT)))
        receipt = self.run_cmd("python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        flagger = self.write("bin/flagger", "#!{}\nimport os, sys\nhits = 0\nfor path in sys.argv[1:]:\n"
                             "    if os.path.isfile(path):\n        for n, line in enumerate(open(path), 1):\n"
                             "            if 'FLAG' in line and not line.lstrip().startswith('#'):\n                hits += 1\n"
                             "                print('{{}}:{{}}:0: [magic-threshold] flagged'.format(path, n))\n"
                             "sys.exit(1 if hits else 0)\n".format(sys.executable))
        os.chmod(flagger, os.stat(flagger).st_mode | stat.S_IEXEC)
        off = ["---", "execute:", "  eval: false", "---", "```{r}", "z <- FLAG", "```"]
        self.write("analysis/a/10_off.qmd", "\n".join(off) + "\n")
        engines = ["```{r engine=\"bash\"}", "echo FLAG", "```", "```{r, engine='python'}", "u = FLAG", "```"]
        self.write("analysis/a/11_engines.Rmd", "\n".join(engines) + "\n")
        self.write("shared/_methods.Rmd", "Methods\n```{r}\nm <- FLAG\n```\n")
        self.write("shared/helpers.R", "## ---- load\nh <- FLAG\n")
        parent = ["```{r, child='../../shared/_methods.Rmd'}", "```", "```{r}", "knitr::read_chunk('../../shared/helpers.R')",
                  "```", "```{r load}", "```", "```{r child=params$doc}", "```", "```{r}",
                  "knitr::read_chunk(\"missing.R\")", "```"]
        self.write("analysis/a/12_parent.Rmd", "\n".join(parent) + "\n")
        self.write("analysis/a/13_only_child.Rmd", "```{r child='../../shared/_methods.Rmd'}\n```\n")
        self.write("analysis/a/14_prose.Rmd", "Prose only.\n")
        out = self.verify("report", digest, scilintr=flagger, rscript=flagger)
        self.assertIn("`analysis/a/10_off.qmd:{}` [magic-threshold]".format(off.index("z <- FLAG") + 1), out)
        self.assertIn("`analysis/a/11_engines.Rmd:{}` [magic-threshold]".format(engines.index("u = FLAG") + 1), out)
        self.assertIn("1 scilintr finding(s) remain in Python code", out)
        self.assertNotIn("11_engines.Rmd:2", out)
        self.assertNotIn("11_engines.Rmd` does not parse", out)
        self.assertIn("`shared/_methods.Rmd:3` [magic-threshold]", out)
        self.assertIn("`shared/helpers.R:2` [magic-threshold]", out)
        self.assertIn("scilintr not checked: `analysis/a/12_parent.Rmd:{}` pulls in code through a path that is "
                      "not a quoted string.".format(parent.index("```{r child=params$doc}") + 1), out)
        self.assertIn("scilintr not checked: `analysis/a/12_parent.Rmd:{}` pulls in `missing.R`, which was not "
                      "found next to the document.".format(parent.index("knitr::read_chunk(\"missing.R\")") + 1), out)
        self.assertIn("1 notebook(s) not linted: analysis/a/14_prose.Rmd.", out)  # a child-only document is linted

    LINTER = """#!PYTHON
import sys
args = sys.argv[1:]
off = '--no-waivers' in args or any('assignInNamespace' in a for a in args)
hits = 0
for path in args:
    if path.endswith(('.py', '.R')):
        lines = open(path).read().splitlines()
        for n, line in enumerate(lines, 1):
            if 'FLAG' not in line:
                continue
            if not off and any('ANALYSIS_OK[' in l and (REACH) for w, l in enumerate(lines, 1)):
                continue
            hits += 1
            print('{}:{}:{}: [{}] flagged'.format(path, n, 1 if path.endswith('.R') else 0,
                                                 'R002' if path.endswith('.R') else 'magic-threshold'))
sys.exit(1 if hits else 0)
"""

    def waiver_aware_linter(self, name, language):
        """A linter that flags each FLAG line unless a waiver is near it and waivers are on (`--no-waivers` for
        Python, scilintr's waiver functions replaced in the R expression), with scilintr's reach for each."""
        reach = "-8 <= n - w <= 8" if language == "R" else "0 <= n - w <= 4"
        path = self.write("bin/" + name, self.LINTER.replace("PYTHON", sys.executable).replace("REACH", reach))
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    def test_waived_findings_are_listed_with_their_reason(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        receipt = self.run_cmd("python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        self.write("analysis/a/scripts/02_plot.py", "# ANALYSIS_OK[threshold]: alpha is fixed by the protocol\n"
                   "FLAG = 1\nx = 1\nx = 2\nx = 3\nx = 4\nFLAG = 2\n", mtime=time.time() - 3600)
        linter = self.waiver_aware_linter("py-waivers", "Python")
        out = self.verify("report", digest, scilintr=linter)
        self.assertIn("1 scilintr finding(s) remain in Python code", out)  # line 7 is past the waiver's reach
        self.assertIn("1 finding(s) waived", out)
        self.assertIn("`analysis/a/scripts/02_plot.py:2` [magic-threshold] by `analysis/a/scripts/02_plot.py:1`: "
                      "alpha is fixed by the protocol", out)
        self.verify("write", digest, "--analysis-dir", "analysis/a", scilintr=linter)
        with open(os.path.join(self.root, "analysis/a/provenance/lint-{}.txt".format(digest))) as handle:
            text = handle.read()
        self.assertIn("# Waived findings (", text)
        self.assertIn("analysis/a/scripts/02_plot.py:2 [magic-threshold] <- analysis/a/scripts/02_plot.py:1: "
                      "alpha is fixed by the protocol", text)

    def test_an_r_waiver_with_no_reason_blocks(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        receipt = self.run_cmd("python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        rscript = self.waiver_aware_linter("Rscript-waivers", "R")
        self.write("analysis/a/scripts/02_plot.R", "# ANALYSIS_OK[threshold]:\ny <- FLAG\n", mtime=time.time() - 3600)
        out = self.verify("report", digest, rscript=rscript)
        self.assertIn("`analysis/a/scripts/02_plot.R:1` waives R002 with no reason", out)
        self.assertIn("Verify status: DOES_NOT_CONFORM", out)
        self.write("analysis/a/scripts/02_plot.R", "# ANALYSIS_OK[threshold]:\n# alpha is fixed by the protocol\n"
                   "y <- FLAG\n", mtime=time.time() - 3600)  # the reason may continue on the next comment line
        out = self.verify("report", digest, rscript=rscript)
        self.assertNotIn("with no reason", out)
        self.assertIn("`analysis/a/scripts/02_plot.R:3` [R002] by `analysis/a/scripts/02_plot.R:1`: alpha is fixed by the protocol", out)

    def test_a_failed_unwaived_run_is_only_an_info_line(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        receipt = self.run_cmd("python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        self.write("analysis/a/scripts/02_plot.py", "# ANALYSIS_OK[x]: y\nFLAG = 1\n", mtime=time.time() - 3600)
        picky = self.write("bin/picky", "#!/bin/sh\ncase \"$*\" in *--no-waivers*) echo boom; exit 2;; esac\nexit 0\n")
        os.chmod(picky, os.stat(picky).st_mode | stat.S_IEXEC)
        out = self.verify("report", digest, scilintr=picky)
        self.assertIn("Waived Python findings were not listed", out)
        self.assertIn("scilintr: 2 Python file(s) clean", out)

    def test_r_code_is_linted_as_one_folder(self):
        """E6: R code goes to `lint_project()` as one copied folder (scilintr 0.1.1's `main()` lints only
        its first argument), `.r` files included, and findings cite the original file. Code that does
        not parse is a gap even when a nearby `ANALYSIS_OK` would drop lintr's parse-error finding."""
        digest = self.approve(plan("run `{}`".format(FIT)))
        receipt = self.run_cmd("python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        self.write("analysis/a/scripts/02_plot.r", "x <- 1\ny <- FLAG\n", mtime=time.time() - 3600)
        rscript = self.write("bin/Rscript-project", "#!{}\nimport os, sys\n"
                             "flag, expr, folder = sys.argv[1:4]\n"
                             "assert flag == '-e' and 'scilintr::lint_project(' in expr and os.path.isdir(folder)\n"
                             "hits = 0\nfor path in sorted(os.path.join(d, n) for d, _, ns in os.walk(folder) for n in ns):\n"
                             "    assert path.endswith('.R'), path\n"
                             "    if 'BROKEN' in open(path).read():\n"
                             "        print('unparseable: {{0}}: {{0}}:3:0: unexpected end of input'.format(path))\n"
                             "    for n, line in enumerate(open(path), 1):\n"
                             "        if 'FLAG' in line:\n            hits += 1\n"
                             "            print('{{}}:{{}}:1: [R030] flagged'.format(path, n))\n"
                             "sys.exit(1 if hits else 0)\n".format(sys.executable))
        os.chmod(rscript, os.stat(rscript).st_mode | stat.S_IEXEC)
        out = self.verify("report", digest, rscript=rscript)
        self.assertIn("1 scilintr finding(s) remain in R code (1 R030)", out)
        self.assertIn("`analysis/a/scripts/02_plot.r:2` [R030]", out)
        self.assertNotIn("mycelium-extra-lint-", out)
        self.write("analysis/a/scripts/02_plot.r", "x <- 1\n", mtime=time.time() - 3600)
        self.assertIn("scilintr: 1 R file(s) clean", self.verify("report", digest, rscript=rscript))
        self.write("analysis/a/scripts/03_broken.R", "# ANALYSIS_OK[x]: y\nBROKEN <- function(\n",
                   mtime=time.time() - 3600)
        out = self.verify("report", digest, rscript=rscript)
        self.assertIn("scilintr (R) not checked: `analysis/a/scripts/03_broken.R` does not parse "
                      "(unexpected end of input)", out)
        self.assertIn("scilintr: 1 R file(s) clean", out)
        self.assertNotIn("mycelium-extra-lint-", out)

    def conda_env(self):
        """A fake conda env named fakeenv, listed in a fake ~/.conda/environments.txt."""
        prefix = os.path.join(self.root, "envs", "fakeenv")
        self.write("envs/fakeenv/conda-meta/b-2-0.json", json.dumps({"url": "https://x/b-2-0.conda", "md5": "bb"}))
        self.write("envs/fakeenv/conda-meta/a-1-0.json", json.dumps({"url": "https://x/a-1-0.conda", "md5": "aa"}))
        self.write("envs/fakeenv/conda-meta/history", "==> 2024 <==\n", mtime=time.time() - 7200)
        self.write("envs/fakeenv/bin/python", "")
        self.write("home/.conda/environments.txt", prefix + "\n/elsewhere/envs/other\n")
        home = os.environ.get("HOME")
        os.environ["HOME"] = os.path.join(self.root, "home")
        self.addCleanup(lambda: os.environ.__setitem__("HOME", home) if home else os.environ.pop("HOME"))
        return prefix

    def test_conda_env_is_recorded_into_provenance(self):
        self.conda_env()
        digest = self.approve(plan("run `{}`".format(FIT)))
        receipt = self.run_cmd("conda run -n fakeenv python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        self.assertIn("Conda env `fakeenv` (`conda run`): 2 packages recorded", self.verify("report", digest))
        self.verify("write", digest, "--analysis-dir", "analysis/a")
        with open(os.path.join(self.root, "analysis/a/provenance/env-{}.txt".format(digest))) as handle:
            self.assertIn("@EXPLICIT\nhttps://x/a-1-0.conda#aa\nhttps://x/b-2-0.conda#bb\n", handle.read())
        with open(os.path.join(self.root, "analysis/a/provenance/PROVENANCE.md")) as handle:
            self.assertIn("[conda env](env-{}.txt)".format(digest), handle.read())
        history = os.path.join(self.root, "envs/fakeenv/conda-meta/history")
        os.utime(history, (receipt["ts"] + 100, receipt["ts"] + 100))
        out = self.verify("report", digest)
        self.assertIn("Conda env `fakeenv` changed", out)
        self.assertIn("Verify status: CONFORMS_WITH_GAPS", out)

    def test_conda_env_from_interpreter_path_and_missing_env(self):
        prefix = self.conda_env()
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.run_cmd("{}/bin/python {}".format(prefix, FIT))
        self.run_cmd("conda run -n nosuch python " + FIT)
        out = self.verify("report", digest)
        self.assertIn("Conda env `fakeenv` (interpreter path): 2 packages recorded", out)
        self.assertIn("Conda env `nosuch` (`conda run`) was not found", out)

    def test_conda_env_from_prefix_and_job_script(self):
        self.conda_env()
        self.write("job.sh", "#!/bin/bash\n#SBATCH -p cpu\nconda activate fakeenv\npython {}\n".format(FIT))
        digest = self.approve(plan("run `{}`".format(FIT), "sbatch `job.sh`"))
        self.run_cmd("sbatch job.sh", stdout="Submitted batch job 4242\n")
        self.assertIn("Conda env `fakeenv` (`activate` in the job script): 2 packages recorded",
                      self.verify("report", digest))
        self.run_cmd("conda run -p envs/fakeenv python " + FIT)  # one env, two sources: first one named
        out = self.verify("report", digest)
        self.assertEqual(out.count("Conda env "), 1, out)

    def test_session_env_only_when_the_job_declares_none(self):
        prefix = self.conda_env()
        self.write("job.sh", "#!/bin/bash\nmodule load R/4.3\nRscript analysis/a/x.R\n")
        digest = self.approve(plan("sbatch `job.sh`"))
        os.environ["CONDA_PREFIX"] = prefix  # the gate's hook records the session's env
        self.addCleanup(os.environ.pop, "CONDA_PREFIX")
        self.run_cmd("sbatch job.sh", stdout="Submitted batch job 4243\n")
        self.assertNotIn("Conda env", self.verify("report", digest))
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.run_cmd("python " + FIT)
        self.assertIn("Conda env `fakeenv` (session `CONDA_PREFIX`)", self.verify("report", digest))

    def test_conda_lock_means_no_snapshot(self):
        self.conda_env()
        self.write("conda-lock.yml", "version: 1\n")
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.run_cmd("conda run -n fakeenv python " + FIT)
        self.assertNotIn("Conda env", self.verify("report", digest))

    def pip_env(self):
        """fakeenv plus site-packages: two conda-owned folders (one reinstalled by pip at the same
        version), a pip-only package, a pip upgrade over a conda one, an editable uv install, and a
        plain-file egg-info. Every folder is older than the run."""
        prefix = self.conda_env()
        site = "envs/fakeenv/lib/python3.12/site-packages/"
        for name, version in [("anndata", "0.10.9"), ("scipy", "1.11.0"), ("numpy", "1.26.0")]:
            files = ["lib/python3.12/site-packages/{}-{}.dist-info/METADATA".format(name, version)]
            self.write("envs/fakeenv/conda-meta/{}-{}-0.json".format(name, version), json.dumps(
                {"name": name, "version": version, "url": "https://x/{}.conda".format(name), "files": files}))
        meta = "Metadata-Version: 2.1\nName: {}\nVersion: {}\n\nName: not-a-header\n"
        for folder, name, version, installer in [
                ("anndata-0.10.9", "anndata", "0.10.9", "conda"), ("scipy-1.11.0", "scipy", "1.11.0", "pip"),
                ("loguru-0.7.2", "loguru", "0.7.2", "pip"), ("numpy-1.26.4", "numpy", "1.26.4", "pip"),
                ("my_tool-0.1", "my_tool", "0.1", "uv")]:
            self.write(site + folder + ".dist-info/METADATA", meta.format(name, version))
            self.write(site + folder + ".dist-info/INSTALLER", installer)
        self.write(site + "my_tool-0.1.dist-info/direct_url.json",
                   json.dumps({"url": "file:///home/me/my-tool", "dir_info": {"editable": True}}))
        self.write(site + "loguru-0.7.2.dist-info/direct_url.json", json.dumps(
            {"url": "https://github.com/Delgan/loguru", "vcs_info": {"vcs": "git", "commit_id": "abc123"}}))
        self.write(site + "old-2.egg-info", meta.format("old", "2"))
        for path in glob.glob(os.path.join(prefix, "lib/python3.12/site-packages/*")):
            os.utime(path, (time.time() - 7200, time.time() - 7200))
        return prefix

    def test_pip_packages_are_recorded_beside_conda_ones(self):
        self.pip_env()
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        self.run_cmd("conda run -n fakeenv python " + FIT, writes={self.OUT: "x\n"})
        out = self.verify("report", digest)
        self.assertIn("Conda env `fakeenv` (`conda run`): 5 packages recorded; 5 pip packages "
                      "(2 also in conda-meta).", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)
        self.verify("write", digest, "--analysis-dir", "analysis/a")
        with open(os.path.join(self.root, "analysis/a/provenance/pip-{}.txt".format(digest))) as handle:
            text = handle.read()
        self.assertIn("# env: fakeenv\n", text)
        self.assertIn("\nloguru @ git+https://github.com/Delgan/loguru@abc123\n# my_tool==0.1  # installer: uv; editable: file:///home/me/my-tool\n"
                      "numpy==1.26.4  # also in conda-meta as 1.26.0\nold==2\n"
                      "scipy==1.11.0  # also in conda-meta as 1.11.0\n", text)
        self.assertNotIn("anndata", text)
        with open(os.path.join(self.root, "analysis/a/provenance/PROVENANCE.md")) as handle:
            self.assertIn("[conda env](env-{0}.txt) - [pip](pip-{0}.txt) |".format(digest), handle.read())

    def test_conda_lock_still_records_pip_packages(self):
        self.pip_env()
        self.write("conda-lock.yml", "version: 1\n")
        digest = self.approve(plan("run `{}`".format(FIT)))
        receipt = self.run_cmd("conda run -n fakeenv python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        self.assertIn("Conda env `fakeenv` (`conda run`): conda packages pinned by `conda-lock.yml`; 5 pip "
                      "packages (2 also in conda-meta) recorded.", self.verify("report", digest))
        self.verify("write", digest, "--analysis-dir", "analysis/a")
        provenance = os.path.join(self.root, "analysis/a/provenance")
        self.assertTrue(os.path.isfile(os.path.join(provenance, "pip-{}.txt".format(digest))))
        self.assertFalse(os.path.exists(os.path.join(provenance, "env-{}.txt".format(digest))))
        self.run_cmd("conda run -n nosuch python " + FIT)
        self.assertIn("Conda env `nosuch` (`conda run`) was not found, so its pip packages were not recorded",
                      self.verify("report", digest))

    def test_pip_install_after_the_run_and_unreadable_metadata_are_gaps(self):
        prefix = self.pip_env()
        digest = self.approve(plan("run `{}`".format(FIT)))
        receipt = self.run_cmd("conda run -n fakeenv python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        late = os.path.join(prefix, "lib/python3.12/site-packages/loguru-0.7.2.dist-info")
        os.utime(late, (receipt["ts"] + 100, receipt["ts"] + 100))
        self.write("envs/fakeenv/lib/python3.12/site-packages/broken-1.dist-info/INSTALLER", "pip")
        os.utime(os.path.dirname(late) + "/broken-1.dist-info", (receipt["ts"] - 100, receipt["ts"] - 100))
        out = self.verify("report", digest)
        self.assertIn("Pip packages in conda env `fakeenv` changed", out)
        self.assertIn("1 pip package folder(s) have no readable name and version, so they were not recorded: "
                      "`broken-1.dist-info`", out)
        self.assertIn("Verify status: CONFORMS_WITH_GAPS", out)

    def test_env_without_site_packages_has_no_pip_line(self):
        self.conda_env()
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.run_cmd("conda run -n fakeenv python " + FIT)
        out = self.verify("report", digest)
        self.assertIn("Conda env `fakeenv` (`conda run`): 2 packages recorded.", out)
        self.assertNotIn("pip package", out)

    def test_explore_lists_this_sessions_runs_for_a_plan(self):
        self.hook("prompt", {"prompt": "allow explore"})
        first = self.run_cmd("MYCELIUM_EXTRA_EXPLORE=1 python " + FIT)
        self.run_cmd("MYCELIUM_EXTRA_EXPLORE=1 python " + FIT)
        self.run_cmd("MYCELIUM_EXTRA_EXPLORE=1 python -c 'import x' " + FIT)  # path handed to code: no run
        other = dict(first, session_id="s2", command="MYCELIUM_EXTRA_EXPLORE=1 python analysis/a/other.py")
        with open(gate.state_path(self.root, "receipts.jsonl"), "a") as handle:
            handle.write(json.dumps(other) + "\n")
        self.write(FIT, "print(2)\n")
        session = os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        self.addCleanup(lambda: session and os.environ.__setitem__("CLAUDE_CODE_SESSION_ID", session))
        os.environ["CLAUDE_CODE_SESSION_ID"] = "s1"
        out = self.verify("explore")
        self.assertIn("# Explore runs (session s1)", out)
        self.assertIn("1. `python {}`".format(FIT), out)
        self.assertIn("(2 runs)", out)
        self.assertIn("script `{}` edited since this run".format(FIT), out)
        self.assertNotIn("other.py", out)
        self.assertNotIn("2. ", out)
        self.assertIn("other.py", self.verify("explore", "--all"))
        del os.environ["CLAUDE_CODE_SESSION_ID"]
        self.assertIn("no session ID found, so every session is shown", self.verify("explore"))
        self.assertEqual(len(json.loads(self.verify("explore", "--session", "s2", "--json"))), 1)

    def test_status_and_list_mark_an_approval_that_reached_its_run_limit(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        self.run_cmd("python " + FIT)
        self.run_cmd("python " + FIT)
        self.assertNotIn("limit", self.verify("status"))
        self.write(".mycelium-extra/gate.json", json.dumps({"max_runs_per_approval": 2}))
        row = {r["hash"]: r for r in json.loads(self.verify("status", "--json"))}[digest]
        self.assertEqual(row["runs"], 2)
        self.assertEqual(row["expired"], "limit 2 reached (2 since approval)")
        self.assertIn("| 2 (limit 2 reached (2 since approval)) |", self.verify("status"))
        self.assertIn("| 2 (limit 2 reached (2 since approval)) |", self.verify("list"))
        for ignored in ("2", 0, True):  # the gate ignores these too
            self.write(".mycelium-extra/gate.json", json.dumps({"max_runs_per_approval": ignored}))
            self.assertNotIn("limit", self.verify("status"))
        self.write(".mycelium-extra/gate.json", json.dumps({"max_runs_per_approval": 3}))
        self.assertNotIn("expired", json.loads(self.verify("status", "--json"))[0])

    def test_status_lists_plans_with_verify_lint_stale_and_manifest(self):
        self.assertIn("No plans", self.verify("status"))
        verified = self.approve(plan("run `{}`".format(FIT)))
        receipt = self.run_cmd("python " + FIT)
        self.write("analysis/a/outputs/fit.tsv", "x\n", mtime=receipt["ts"] - 1)
        dirty = self.fake_tool("bin/scilintr-dirty", FIT + ":3:0: [broad-exception] broad except\\n", 1)
        self.verify("write", verified, "--analysis-dir", "analysis/a", scilintr=dirty)
        self.write("analysis/b/scripts/01_x.py", "print(1)\n", mtime=time.time() - 3600)
        pending = self.approve(plan("run `analysis/b/scripts/01_x.py`"))
        out = self.verify("status")
        self.assertIn("| {} | `analysis/a` |".format(verified), out)
        self.assertIn("| 1 | DOES_NOT_CONFORM (complete) | no | 1 finding(s) | not listed |", out)
        self.assertIn("| {} | `analysis/b` |".format(pending), out)
        self.assertIn("| 0 | not verified | - | - | not listed |", out)
        shapes = {  # Mycelium's YAML template and the shapes real manifests use
            "# Analysis Manifest\n\n### a\n```yaml\nname: a\n# a comment\nstatus: active\n```\n\n### b\n": "listed: active",
            "| Analysis | Location | Status |\n|---|---|---|\n| A | `analysis/a/` | Complete 2026-09-25 in x |\n":
                "listed: complete",
            "## Fit\n\n**Status**: draft — 2026-07-21\nLives in `analysis/a`.\n": "listed: draft",
            "| # | Name | Status |\n|---|---|---|\n| A1 | `analysis/a` | ✅\U0001F7E1 **Primary** x |\n":
                "listed: primary",
            "Folder `analysis/a` holds the fit.\n": "listed",
            "See `analysis/ab/` and analysis/a.old\n": "not listed",
        }
        for text, expected in shapes.items():
            with open(os.path.join(self.root, "analysis/ANALYSIS_MANIFEST.md"), "w", encoding="utf-8") as handle:
                handle.write(text)
            rows = {r["hash"]: r for r in json.loads(self.verify("status", "--json"))}
            self.assertEqual(rows[verified]["manifest"], expected, text)
        self.write("analysis/a/scripts/02_plot.R", "x <- 1\n", mtime=time.time() - 3600)
        self.verify("write", verified, "--analysis-dir", "analysis/a",  # R clean, Python linter missing
                    scilintr=os.path.join(self.root, "no-scilintr"))
        rows = {r["hash"]: r for r in json.loads(self.verify("status", "--json"))}
        self.assertEqual(rows[verified]["lint"], "gap: Python not checked")
        self.write(FIT, "print(2)\n")
        os.remove(os.path.join(self.root, ".mycelium-extra", "gate.json"))  # provenance alone suffices
        out = self.verify("status")
        self.assertIn("| 1 change(s) |", out)
        self.assertNotIn(pending, out)

    def claims_run(self, block, prose=""):
        """One planned run writing two outputs, and the analysis doc carrying `block`."""
        digest = self.approve(plan("run `{}`".format(FIT),
                                   outputs="analysis/a/outputs/de.tsv analysis/a/outputs/numbers.json"))
        receipt = self.run_cmd("python " + FIT, writes={
            "analysis/a/outputs/de.tsv": "gene\tlog2fc\tpadj\tshare\nIL7R\t1.23456\t0.0412\t0.344\n"
                                         "CD3E\t-0.5\t0.05\t0.1\nCD3E\t2\t0.9\t0.2\n",
            "analysis/a/outputs/numbers.json": '{"qc": {"n": 48, "kept": [40, 8]}}'})
        self.write("analysis/a/A.md", "# a\n\n## Key Findings\n\n{}\n<!-- claims\n{}\n-->\n\n## Next\n\n"
                                      "Run 5 more.\n".format(prose, block))
        return digest, receipt

    def test_claims_verified_by_rounding_transform_inequality_rows_and_json(self):
        digest, _ = self.claims_run("\n".join([
            "- 1.235 | outputs/de.tsv log2fc IL7R", "- 1.234 | outputs/de.tsv log2fc IL7R",
            "- 34% | outputs/de.tsv share IL7R", "- < 0.05 | outputs/de.tsv padj IL7R",
            "- 3 | outputs/de.tsv rows", "- 48 | outputs/numbers.json qc.n | donors",
            "- 8 | analysis/a/outputs/numbers.json qc.kept.1"]),
            prose="IL7R rose 1.235 log2 units in 48 donors (padj 0.0412, n = 3).")
        out = self.verify("report", digest)
        self.assertIn("`analysis/a/A.md`: 7 verified (1 via transform), 0 mismatch, 0 unverified", out)
        # "log2" and the "5" of "Run 5 more", in the next section, are not listed.
        self.assertIn("1 number(s) in `analysis/a/A.md` near its claims block are not claims, so not checked: "
                      "L5 `0.0412`.", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)
        self.assertEqual(json.loads(self.verify("report", digest, "--json"))["claims"][0]["counts"],
                         {"verified": 6, "verified-transform": 1})

    def test_non_finite_claim_cells_are_gaps(self):
        values = ["NaN", "nan", "sNaN", "-NaN", "Infinity", "-Infinity", "Inf", "+inf", "-inf"]
        rows, claims, expected = [], [], []
        for i, value in enumerate(values):
            label = "CELL{}".format(i)
            rows.append("{}\t{}".format(label, value))
            for qualifier in ("<", ">", "<=", ">=", "=", ""):
                claims.append("- {} 0.05 | outputs/de.tsv value {}".format(qualifier, label))
                expected.append((value, label))
            claims.append("- < 5% | outputs/de.tsv value {}".format(label))
            expected.append((value, label))
        claims.append("- < 0.05 | outputs/numbers.json qc.value")
        expected.append(("NaN", None))
        digest, receipt = self.claims_run("\n".join(claims))
        self.write("analysis/a/outputs/de.tsv", "gene\tvalue\n" + "\n".join(rows) + "\n",
                   mtime=receipt["ts"] - 1)
        self.write("analysis/a/outputs/numbers.json", '{"qc": {"value": "NaN"}}',
                   mtime=receipt["ts"] - 1)
        out = self.verify("report", digest)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)
        self.assertNotIn("**block**", out)
        result = json.loads(self.verify("report", digest, "--json"))
        document = result["claims"][0]
        self.assertEqual(document["counts"], {"unverified": len(expected)})
        self.assertEqual(len(document["claims"]), len(expected))
        for claim, (value, label) in zip(document["claims"], expected):
            self.assertEqual((claim["verdict"], claim["observed"], claim["row"]),
                             ("unverified", value, label))
            self.assertIn("holds `{}`, not a finite number".format(value), claim["reason"])
            self.assertIn(claim["file"], claim["reason"])
            if label:
                self.assertIn("row " + label, claim["reason"])

    def test_non_finite_claim_does_not_hide_a_finite_mismatch(self):
        digest, receipt = self.claims_run("- < 0.05 | outputs/de.tsv padj IL7R\n"
                                         "- 2 | outputs/de.tsv log2fc IL7R")
        self.write("analysis/a/outputs/de.tsv", "gene\tlog2fc\tpadj\nIL7R\t1.23456\tNaN\n",
                   mtime=receipt["ts"] - 1)
        out = self.verify("report", digest)
        self.assertIn("claim <0.05 is unverified", out)
        self.assertIn("claims 2, but", out)
        self.assertTrue(out.rstrip().endswith("Verify status: DOES_NOT_CONFORM"), out)
        result = json.loads(self.verify("report", digest, "--json"))
        self.assertEqual(result["claims"][0]["counts"], {"unverified": 1, "mismatch": 1})

    def test_claims_mismatch_blocks(self):
        digest, _ = self.claims_run("- 1.3 | outputs/de.tsv log2fc IL7R\n- > 0.05 | outputs/de.tsv padj IL7R")
        out = self.verify("report", digest)
        self.assertIn("**block**: `analysis/a/A.md:7` claims 1.3, but `analysis/a/outputs/de.tsv` log2fc row "
                      "IL7R holds 1.23456.", out)
        self.assertIn("`analysis/a/A.md:8` claims >0.05", out)
        self.assertIn("Verify status: DOES_NOT_CONFORM", out)

    def test_empty_or_ambiguous_claim_tables_are_gaps(self):
        digest, receipt = self.claims_run("- 1 | outputs/de.tsv value")
        for text, reason in [("gene\tvalue\n", "the table has no data rows"),
                             ("gene\tvalue\tvalue\nIL7R\t1\t2\n", "2 columns are named `value`")]:
            with self.subTest(table=text):
                self.write("analysis/a/outputs/de.tsv", text, mtime=receipt["ts"] - 1)
                result = json.loads(self.verify("report", digest, "--json"))
                self.assertEqual(result["status"], "CONFORMS_WITH_GAPS")
                claim = result["claims"][0]["claims"][0]
                self.assertEqual(claim["verdict"], "unverified")
                self.assertIn(reason, claim["reason"])

    def test_extreme_decimal_claim_does_not_crash_or_hide_mismatch(self):
        digest, _ = self.claims_run("- 1e999999999999999999 | outputs/de.tsv log2fc IL7R\n"
                                   "- 2 | outputs/de.tsv log2fc IL7R")
        result = json.loads(self.verify("report", digest, "--json"))
        self.assertEqual(result["status"], "DOES_NOT_CONFORM")
        self.assertEqual(result["claims"][0]["counts"], {"mismatch": 2})

    def test_unrepresentable_claim_and_percentage_overflow_are_gaps(self):
        digest, receipt = self.claims_run("- 1e999999999999999999999 | outputs/de.tsv value\n"
                                         "- < 1% | outputs/de.tsv value")
        self.write("analysis/a/outputs/de.tsv", "gene\tvalue\nIL7R\t1e999999\n",
                   mtime=receipt["ts"] - 1)
        result = json.loads(self.verify("report", digest, "--json"))
        self.assertEqual(result["status"], "CONFORMS_WITH_GAPS")
        self.assertEqual(result["claims"][0]["counts"], {"unverified": 2})

    def test_fact_tags_counted_and_flagged_in_plan_and_key_findings(self):
        evidence = "\n".join([
            "", "**Evidence**", "- 48 donors [agent-derived: `data/meta.tsv:1`]",
            "- the contrast is day 28 [human-stated]", "- BH suits independent tests [agent-asserted: none]",
            "- an untagged fact", "  that wraps", "- a derived fact [agent-derived]", "",
            "Facts: 2 agent-derived, 1 human-stated, 1 agent-asserted (1 unsourced).", ""])
        digest = self.approve(plan("run `{}`".format(FIT)).replace("\nOutputs:", evidence + "\nOutputs:"))
        self.run_cmd("python " + FIT)
        self.write("analysis/a/A.md", "# a\n\n## Key Findings\n\n<!-- one bullet per result -->\n"
                                      "- IL7R rises [agent-derived: `outputs/de.tsv`].\n- CD3E falls\n\n## Next\n")
        out = self.verify("report", digest)
        self.assertIn("Fact tags in the plan's Evidence: 2 agent-derived, 1 human-stated, 1 agent-asserted, "
                      "1 untagged; flagged: L6 agent-asserted without a source; L7 untagged `an untagged fact "
                      "that wraps`; L9 agent-derived without its artifact.", out)
        self.assertIn("Fact tags in `analysis/a/A.md` Key Findings: 1 agent-derived, 1 untagged; "
                      "flagged: L7 untagged `CD3E falls`.", out)
        self.assertEqual(re.findall(r"\*\*(?:gap|block)\*\*: (?:Fact|Default)", out), [])  # advisory

    def test_untagged_or_absent_facts(self):
        digest = self.approve(plan("run `{}`".format(FIT)).replace(
            "\nOutputs:", "\nEvidence:\n- one\n- two\n\nOutputs:"))
        self.run_cmd("python " + FIT)
        out = self.verify("report", digest)
        self.assertIn("Fact tags: 2 fact(s) in the plan's Evidence, none tagged (written before D7, "
                      "or untagged).", out)
        self.assertNotIn("Key Findings", out)  # no analysis doc, no line
        digest = self.approve(plan("run `{}`".format(FIT), outputs="analysis/a/outputs/x"))
        self.assertNotIn("Fact tags", self.verify("report", digest))

    def test_section_bullets_layouts(self):
        sys.path.insert(0, os.path.dirname(SCRIPT))
        import verify
        for label in ("## Evidence", "**Evidence**", "Evidence:", "- **Evidence**:", "**Evidence.**"):
            self.assertEqual(verify.section_bullets("x\n{}\n\n- a [human-stated]\n* b\n1. c\nnext\n- d"
                                                    .format(label), "Evidence"),
                             [(4, "a [human-stated]"), (5, "b"), (6, "c")], label)
        self.assertEqual(verify.section_bullets("Evidence suggests x\n- a\n", "Evidence"), [])

    def test_unlocated_claims_are_gaps(self):
        # 0.05 is in the padj column, but no row is named: a common value never verifies by itself.
        digest, _ = self.claims_run("\n".join([
            "- 0.05 | outputs/de.tsv padj", "- 2 | outputs/de.tsv log2fc CD3E", "- 1 | outputs/missing.tsv x",
            "- 1 | outputs/de.tsv pval IL7R", "- 1 | outputs/de.tsv log2fc GAPDH", "- 1 | outputs/de.tsv gene IL7R",
            "- about 2 | outputs/de.tsv log2fc IL7R"]))
        self.write("analysis/a/notes.md", "1.2\n")
        out = self.verify("report", digest, "--claims", "analysis/a/notes.md", "--claims", "nope.md")
        for text in ["claim 0.05 is unverified: 3 rows match; name one by its first-column label",
                     "claim 2 is unverified: 2 rows are labelled `CD3E`",
                     "cites `analysis/a/outputs/missing.tsv`, but it does not exist", "no column `pval`",
                     "no row `GAPDH`", "row IL7R holds `IL7R`, not a finite number", "claims line does not parse",
                     "Claims not checked in `analysis/a/notes.md`: it has no `<!-- claims -->` block",
                     "Claims not checked in `nope.md`: it does not exist"]:
            self.assertIn(text, out)
        self.assertNotIn("**block**", out)
        self.assertIn("Verify status: CONFORMS_WITH_GAPS", out)

    def test_claim_from_an_explore_output_blocks(self):
        digest, receipt = self.claims_run("- 1.235 | outputs/de.tsv log2fc IL7R")
        self.hook("prompt", {"prompt": "allow explore"})
        explore = self.run_cmd("MYCELIUM_EXTRA_EXPLORE=1 python " + FIT)
        mtime = explore["ts"] + 4.99  # past the planned run's 5 s tolerance, within the explore run's
        self.assertGreater(mtime, receipt["ts"] + 5)
        os.utime(os.path.join(self.root, "analysis/a/outputs/de.tsv"), (mtime, mtime))
        out = self.verify("report", digest)
        self.assertIn("claims 1.235 from `analysis/a/outputs/de.tsv` log2fc row IL7R, which an explore run "
                      "wrote", out)
        self.assertIn("1 explore-only", out)
        self.assertIn("Verify status: DOES_NOT_CONFORM", out)

    def test_failed_command_receipt_blocks_and_unknown_exit_is_a_gap(self):
        digest = self.approve(plan("`snakemake -j1`"))
        self.run_cmd("snakemake -j1", exit_code=7)
        out = self.verify("report", digest)
        self.assertIn("`snakemake -j1` failed (exit 7)", out)
        self.assertIn("Verify status: DOES_NOT_CONFORM", out)
        self.run_cmd("snakemake -j1")  # a later success supersedes the failed try
        out = self.verify("report", digest)
        self.assertNotIn("`snakemake -j1` failed (exit 7)", out)  # no longer a finding ...
        self.assertNotIn("**block**", out)
        self.assertIn("`snakemake -j1`: failed (exit 7)", out.split("## Recovery")[1])  # ... but still in the history
        self.assertIn("recovered: equivalent retry", out)
        self.hook("post", {"tool_name": "Bash", "tool_input": {"command": "snakemake -j1"},
                           "tool_response": {"stdout": "", "stderr": "", "interrupted": False}})
        out = self.verify("report", digest)
        self.assertIn("`snakemake -j1` ran at", out)
        self.assertIn("carried no exit status, so the run is not counted as a success", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)

    def test_folder_plan_with_no_runs_is_a_gap_and_a_run_conforms(self):
        self.write("analysis/a/outputs/old.tsv", "x\n", mtime=time.time() - 3600)
        digest = self.approve(plan("run the scripts in `analysis/a/scripts/`", outputs="analysis/a/outputs/*.tsv"))
        out = self.verify("report", digest)
        self.assertIn("grants running the scripts in `analysis/a/scripts/`, but no run in it", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})  # old outputs beside a real run do not block
        out = self.verify("report", digest)
        self.assertNotIn("grants running", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)
        self.run_cmd("python " + FIT, exit_code=3)  # and a failed run of the folder blocks
        self.assertIn("failed (exit 3)", self.verify("report", digest))

    def test_failed_slurm_job_of_a_command_only_plan_blocks(self):
        self.write("jobs/fit.job", "#!/bin/bash\n", mtime=time.time() - 3600)
        digest = self.approve(plan("`sbatch jobs/fit.job`"))
        self.run_cmd("sbatch jobs/fit.job", stdout="Submitted batch job 4242")
        line = "4242|{}|0:0|2026-09-30T10:00:00|2026-09-30T10:05:00"
        for state in ("FAILED", "CANCELLED", "TIMEOUT"):
            out = self.verify("report", digest, sacct=self.fake_sacct(line.format(state)))
            self.assertIn("`sbatch jobs/fit.job`: Slurm job 4242 ended " + state, out)
            self.assertIn("Verify status: DOES_NOT_CONFORM", out)
        out = self.verify("report", digest, sacct=self.fake_sacct(line.format("COMPLETED")))
        self.assertNotIn("**block**", out)
        self.assertNotIn("Slurm job 4242", out)
        out = self.verify("report", digest, sacct=os.path.join(self.root, "no-sacct"))
        self.assertIn("Slurm job 4242 is of unknown state", out)
        self.assertNotIn("**block**", out)

    def test_unknown_exit_with_a_job_id_is_judged_by_the_job(self):
        self.write("jobs/fit.job", "#!/bin/bash\n", mtime=time.time() - 3600)
        digest = self.approve(plan("`sbatch jobs/fit.job`"))
        self.run_cmd("sbatch jobs/fit.job", stdout="Submitted batch job 4242")
        path = gate.state_path(self.root, "receipts.jsonl")
        with open(path) as handle:
            receipt = json.loads(handle.readlines()[-1])
        receipt["exit_status"] = "unknown"
        with open(path, "w") as handle:
            handle.write(json.dumps(receipt) + "\n")
        out = self.verify("report", digest, sacct=self.fake_sacct(
            "4242|COMPLETED|0:0|2026-09-30T10:00:00|2026-09-30T10:05:00"))
        self.assertNotIn("carried no exit status", out)
        self.assertNotIn("Slurm job", out)
        self.assertNotIn("**block**", out)

    def test_compound_command_receipt_gets_the_compound_gap(self):
        self.write("analysis/a/Snakefile", "rule all:\n  input: 'x'\n", mtime=time.time() - 3600)
        digest = self.approve(plan("`snakemake -j1`"))
        self.run_cmd("cd analysis/a && snakemake -j1")
        out = self.verify("report", digest)
        self.assertIn("`snakemake -j1` was named in a compound command at", out)
        self.assertIn("cannot be attributed to this step", out)
        self.assertNotIn("carried no exit status", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)
        self.run_cmd("cd analysis/a && snakemake -j1", exit_code=2)
        out = self.verify("report", digest)
        self.assertIn("Compound command containing `snakemake -j1` failed", out)
        self.assertNotIn("carried no exit status", out)
        self.assertIn("Verify status: DOES_NOT_CONFORM", out)

    def test_a_retry_with_other_arguments_supersedes_the_failed_try(self):
        self.write("jobs/fit.job", "#!/bin/bash\n", mtime=time.time() - 3600)
        digest = self.approve(plan("`snakemake -j1`", "`sbatch jobs/fit.job`"))
        done = self.fake_sacct("4242|COMPLETED|0:0|2026-09-30T10:00:00|2026-09-30T10:05:00")
        self.run_cmd("snakemake -j1", exit_code=1)
        self.run_cmd("sbatch -p wrong jobs/fit.job", exit_code=1)
        out = self.verify("report", digest, sacct=done)
        self.assertIn("`snakemake -j1` failed (exit 1)", out)
        self.assertIn("`sbatch -p wrong jobs/fit.job` failed (exit 1)", out)
        self.run_cmd("snakemake -j1 --rerun-incomplete")
        self.run_cmd("sbatch -p cpu jobs/fit.job", stdout="Submitted batch job 4242")
        out = self.verify("report", digest, sacct=done)
        self.assertNotIn("failed (exit", out.split("## Findings")[1])  # the failures are no longer findings ...
        self.assertNotIn("**block**", out)
        recovery = out.split("## Recovery")[1]  # ... but both stay visible, with the changed command named
        self.assertIn("`snakemake -j1`: failed (exit 1)", recovery)
        self.assertIn("`sbatch -p wrong jobs/fit.job`: failed (exit 1)", recovery)
        self.assertIn("added `--rerun-incomplete`", recovery)
        self.assertIn("removed `wrong`, added `cpu`", recovery)
        self.assertEqual(out.count("recovered with a changed command: equivalence not established"), 4)  # two findings, two verdicts
        self.assertIn("Verify status: CONFORMS_WITH_GAPS", out)  # a changed command is a gap, never a clean recovery
        self.run_cmd("snakemake -j1 --rerun-incomplete", exit_code=4)  # a later failure of the step shows
        self.assertIn("failed (exit 4)", self.verify("report", digest, sacct=done))

    def test_a_later_failure_of_another_step_is_not_hidden_by_an_earlier_success(self):
        self.write("jobs/fit.job", "#!/bin/bash\n", mtime=time.time() - 3600)
        self.write("jobs/plot.job", "#!/bin/bash\n", mtime=time.time() - 3600)
        digest = self.approve(plan("`sbatch jobs/fit.job`", "`sbatch jobs/plot.job`"))
        self.run_cmd("sbatch jobs/fit.job", stdout="Submitted batch job 4242")
        self.run_cmd("sbatch jobs/plot.job", exit_code=1)
        out = self.verify("report", digest, sacct=self.fake_sacct(
            "4242|COMPLETED|0:0|2026-09-30T10:00:00|2026-09-30T10:05:00"))
        self.assertIn("`sbatch jobs/plot.job` failed (exit 1)", out)
        self.assertIn("Verify status: DOES_NOT_CONFORM", out)

    def test_folder_run_by_cd_and_snakemake_is_not_a_zero_run_gap(self):
        self.write("analysis/a/scripts/Snakefile", "rule all:\n  input: 'x'\n", mtime=time.time() - 3600)
        digest = self.approve(plan("run the scripts in `analysis/a/scripts/`", "`snakemake -j1`"))
        self.run_cmd("cd analysis/a/scripts && snakemake -j1")
        out = self.verify("report", digest)
        self.assertNotIn("grants running", out)
        self.assertIn("1 run(s) in it", out)

    def test_plan_that_runs_nothing_stays_valid(self):
        self.write("analysis/a/outputs/old.tsv", "x\n", mtime=time.time() - 3600)
        digest = self.approve(plan("read the tables in `analysis/a/outputs/`", outputs="none"))
        out = self.verify("report", digest)
        self.assertNotIn("grants running", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)

    def test_gate_must_be_on(self):
        os.remove(os.path.join(self.root, ".mycelium-extra", "gate.json"))
        self.assertIn("not on", self.verify("list", fails=True))

    def test_malformed_approval_records_fail_cleanly_across_actions(self):
        digest = self.approve(plan("run `{}`".format(FIT)))
        path = gate.state_path(self.root, "approvals", digest + ".json")
        with open(path) as handle:
            record = json.load(handle)
        for invalid in [[], True, 42, dict(record, approved_at=float("nan")),
                        dict(record, plan=[]), dict(record, pins=[])]:
            with self.subTest(approval=invalid):
                with open(path, "w") as handle:
                    json.dump(invalid, handle)
                for action in [("list",), ("status",), ("report", digest),
                               ("write", digest, "--analysis-dir", "analysis/a"),
                               ("diff", digest, digest), ("multiplicity", digest), ("runs",)]:
                    error = self.verify(*action, fails=True)
                    self.assertIn("invalid approval state", error)
                    self.assertNotIn("Traceback", error)
                self.verify("explore", "--all")
                self.verify("stale")

    # ---- `runs`: run labels and cross-folder citations (read-only)

    def label(self, folder, status, kind="model", version="1", extra="", mtime=None):
        """A run folder holding one output, and its RUN.txt label."""
        name = os.path.basename(folder)
        self.write(folder + "/out.tsv", "x\n" + folder, mtime=mtime or time.time() - 7200)
        self.write(folder + "/RUN.txt", "# Run label\nrun: {}\nversion: {}\nkind: {}\nstatus: {}\n"
                   "why: {}\n{}\nNotes\nrun_99999999_prose is only prose.\n".format(
                       name, version, kind, status, "why " + name, extra))

    def snapshot(self):
        found = {}
        for folder, dirs, names in os.walk(self.root):
            for name in dirs + names:
                info = os.lstat(os.path.join(folder, name))
                found[os.path.join(folder, name)] = (info.st_mtime, info.st_size)
        return found

    def runs_folder(self):
        res = "analysis/a/results/"
        self.label(res + "run_20261001_alpha", "current")
        self.label(res + "run_20261002_alpha_v02", "current", version="2")
        self.write(res + "run_20261003_nolabel/out.tsv", "x")
        self.write(res + "run_20261004_frozen/out.tsv", "x")
        self.write(res + "run_20261004_frozen.RUN.txt", "run: run_20261004_frozen\nstatus: superseded\n"
                   "kind: rerun\nsuperseded_by: -\n")
        self.write(res + "run_20261005_bad/out.tsv", "x")
        self.write(res + "run_20261005_bad/RUN.txt", "# c\nrun: run_20261005_bad\noops\nstatus: weird\n")
        self.label(res + "run_20261006_gone", "superseded", kind="data",
                   extra="superseded_by: run_20269999_nowhere\nreads: run_20261001_alpha, run_20260101_missing")
        self.label(res + "run_20261007_final_smoke", "scratch", kind="smoke")
        os.symlink("run_20261002_alpha_v02", os.path.join(self.root, res + "current"))
        self.write(res + "run_20261001_alpha.log", "not a run")
        return os.path.join(self.root, res)

    def test_runs_lists_labels_findings_and_writes_nothing(self):
        res = self.runs_folder()
        newest = time.time() - 5000
        self.write("analysis/a/results/run_20261001_alpha/late.tsv", "y", mtime=newest)
        with open(res + "run_20261001_alpha/RUN.txt") as handle:
            label = handle.read()
        self.write("analysis/a/results/run_20261001_alpha/RUN.txt", label, mtime=time.time())  # labelling a run later must not move its `updated`
        before = self.snapshot()
        out = self.verify("runs", res)
        self.assertEqual(before, self.snapshot())
        self.assertIn("| Run | Version | Kind | Status | Updated | Id | Why |", out)
        row = [l for l in out.splitlines() if l.startswith("| run_20261001_alpha |")][0]
        self.assertIn("| 1 | model | current | {} | ".format(time.strftime("%Y-%m-%d %H:%M", time.localtime(newest))), row)
        self.assertRegex(row, r"\| [0-9a-f]{8} \| why run_20261001_alpha \|$")
        names = [l.split("|")[1].strip() for l in out.splitlines() if l.startswith("| run_")]
        self.assertEqual(names, sorted(names))
        self.assertEqual(len(names), 7)  # `current` and the `.log` are not runs; the frozen sibling label is not one
        self.assertIn("| run_20261003_nolabel | - | - | unlabelled |", out)
        self.assertIn("| run_20261004_frozen | - | rerun | superseded |", out)
        self.assertIn("`current` -> `run_20261002_alpha_v02` (a pointer, not a run)", out)
        for finding in [
                "- gap `run_20261003_nolabel`: no label",
                "- info `run_20261004_frozen`: labelled by the sibling file `run_20261004_frozen.RUN.txt`",
                "- gap `run_20261005_bad`: malformed label (line 3): not a `key: value` line.",
                "- gap `run_20261005_bad`: malformed label (line 4): `status: weird` is not one of",
                "- gap `run_20261006_gone`: superseded_by `run_20269999_nowhere` does not exist.",
                "- gap `run_20261006_gone`: reads `run_20260101_missing`, which does not exist.",
                "- info `run_20261007_final_smoke`: the name has a state word (final, smoke)",
                "- suggestion `run_20261002_alpha_v02`: `run_20261001_alpha`, `run_20261002_alpha_v02` all say `current` for slug `alpha`"]:
            self.assertIn(finding, out)
        self.assertNotIn("reads `run_20261001_alpha`", out)  # an existing run
        self.assertNotIn("run_99999999_prose", out)  # prose in the notes is never parsed
        self.assertNotIn("Traceback", out)
        self.assertEqual(self.verify("runs", res + "/"), out)  # a trailing slash changes nothing
        self.assertEqual(json.loads(self.verify("runs", res, "--json"))["runs"][0]["run"], "run_20261001_alpha")

    def test_runs_id_ignores_the_label_and_follows_the_files(self):
        res = self.runs_folder()
        first = self.verify("runs", res)
        self.write("analysis/a/results/run_20261001_alpha/RUN.txt", "run: run_20261001_alpha\nstatus: side\n")
        again = self.verify("runs", res)
        pick = lambda out: [l for l in out.splitlines() if l.startswith("| run_20261001_alpha |")][0].split("|")[6]
        self.assertEqual(pick(first), pick(again))
        self.write("analysis/a/results/run_20261001_alpha/more.tsv", "z")
        self.assertNotEqual(pick(first), pick(self.verify("runs", res)))

    def test_runs_default_folder_comes_from_the_newest_approval(self):
        err = self.verify("runs", fails=True)
        self.assertIn("pass the results folder", err)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.runs_folder()
        self.approve(plan("run `{}`".format(FIT)))
        self.assertIn("# Runs in `analysis/a/results`", self.verify("runs"))
        err = self.verify("runs", os.path.join(self.root, "analysis/a/nothing"), fails=True)
        self.assertIn("pass the analysis's results folder", err)
        self.assertNotIn("Traceback", err)
        shutil.rmtree(os.path.join(self.root, "analysis/a/results"))
        self.assertIn("is not a folder", self.verify("runs", fails=True))

    def test_runs_citations_of_other_analyses(self):
        other = "analysis/b/results/"
        self.label(other + "run_20261001_ok", "current")
        self.label(other + "run_20261002_old", "superseded", extra="superseded_by: run_20261003_new")
        self.label(other + "run_20261003_new", "current", mtime=time.time() + 600)  # changed after the approval
        self.label(other + "run_20261004_bad", "failed")
        self.write(other + "run_20261005_nolabel/out.tsv", "x")
        os.symlink("run_20261001_ok", os.path.join(self.root, other + "current"))
        os.makedirs(os.path.join(self.root, "analysis/a/data"))
        os.makedirs(os.path.join(self.root, "analysis/a/code"))
        here = os.path.join(self.root, "analysis/a/")
        for link, target in [("data/cur", "../../b/results/current"), ("data/old", "../../b/results/run_20261002_old"),
                             ("data/new", "../../b/results/run_20261003_new/out.tsv"),
                             ("data/bad", "../../b/results/run_20261004_bad"),
                             ("code/nolabel", "../../b/results/run_20261005_nolabel"),
                             ("data/dangling", "../../b/results/run_20269999_gone"),
                             ("data/plain", "../../b/results"),  # not a run: ignored
                             ("data/mine", "../results/run_20261001_own")]:  # this analysis's own run: ignored
            os.symlink(target, os.path.join(here, link))
        self.label("analysis/a/results/run_20261001_own", "current")
        self.approve(plan("run `{}`".format(FIT)))
        before = self.snapshot()
        out = self.verify("runs", here + "results")
        self.assertEqual(before, self.snapshot())
        cited = out.split("## Citations")[1]
        for line in [
                "- info `data/cur` -> `analysis/b/results/run_20261001_ok` (current, id ",
                "- gap `data/old` -> `analysis/b/results/run_20261002_old` (superseded, id ",
                "the cited run is superseded (by run_20261003_new).",
                "- gap `data/bad` -> `analysis/b/results/run_20261004_bad` (failed, id ",
                "- gap `code/nolabel` -> `analysis/b/results/run_20261005_nolabel` (unlabelled, id ",
                "the cited run has no label.",
                "- gap `data/dangling`: dangling: points to `../../b/results/run_20269999_gone`"]:
            self.assertIn(line, cited)
        self.assertRegex(cited, r"- info `data/new` -> `analysis/b/results/run_20261003_new` \(current, id [0-9a-f]{8}\): "
                         r"the cited run is current\.")
        self.assertRegex(cited, r"- info `data/new` .*: the cited run changed .*, after the newest approval")
        self.assertNotIn("data/cur` -> `analysis/b/results/run_20261001_ok` (current, id ", out.split("## Citations")[0])
        self.assertNotIn("data/plain", cited)
        self.assertNotIn("data/mine", cited)
        self.assertEqual(cited.count("changed"), 1)
        self.assertNotIn("Citations", self.verify("status"))  # `check` and `status` never show citations
        self.assertNotIn("data/old", self.verify("report", self.approve(plan("run `{}`".format(FIT), outputs="analysis/a/o2/"))))

    # F01/C05: a producer is named only from qualified evidence, never from timing alone

    OUT = "analysis/a/outputs/fit.tsv"
    LAUNCH_FIELDS = ("launch_match", "attempt_id", "approval_instance", "outputs_observation", "outputs_changed",
                     "launch_note", "attempt_candidates")

    def read_receipts(self):
        with open(gate.state_path(self.root, "receipts.jsonl")) as handle:
            return [json.loads(line) for line in handle]

    def rewrite_receipts(self, change):
        records = self.read_receipts()
        for record in records:
            change(record)
        with open(gate.state_path(self.root, "receipts.jsonl"), "w") as handle:
            handle.write("".join(json.dumps(record) + "\n" for record in records))

    def make_legacy(self, digest):
        """What an older gate wrote: receipts with no launch link, attempt, instance or output observation, and an
        approval with no instance id."""
        self.rewrite_receipts(lambda r: [r.pop(key, None) for key in self.LAUNCH_FIELDS])
        path = gate.state_path(self.root, "approvals", digest + ".json")
        record = gate.read_json(path, {})
        record.pop("instance_id", None)
        with open(path, "w") as handle:
            json.dump(record, handle)

    def outputs_of(self, digest, *args):
        return json.loads(self.verify("report", digest, "--json", *args))["outputs"]

    def output_row(self, out, path):
        return [line for line in out.splitlines() if line.startswith("| `{}` |".format(path))][0]

    def test_single_timestamp_candidate_is_not_a_producer(self):  # F01
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        receipt = self.run_cmd("python " + FIT)  # a print-only script: its attempt saw no output change
        self.write(self.OUT, "x\n", mtime=receipt["ts"] - 1)  # an independent writer, one second before its report
        out = self.verify("report", digest)
        by = self.output_row(out, self.OUT).split("|")[3].strip()
        self.assertEqual(by, "unresolved")
        self.assertIn("timing evidence only", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)
        entry, = self.outputs_of(digest)
        self.assertEqual((entry["evidence_method"], entry["strength"], entry["producer_attempt"]),
                         ("timing-only", "candidate", None))
        self.assertEqual(len(entry["candidates"]), 1)
        self.assertIn("did not see this one change", entry["reason"])

    def test_a_matched_run_that_writes_the_declared_output_is_supported(self):  # control
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        receipt = self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        self.assertEqual(receipt["outputs_changed"]["created"], [self.OUT])  # the gate saw it appear
        out = self.verify("report", digest)
        entry, = self.outputs_of(digest)
        self.assertEqual((entry["evidence_method"], entry["strength"], entry["producer_attempt"]),
                         ("attempt-observed", "supported", receipt["attempt_id"]))
        self.assertIn("`python " + FIT, self.output_row(out, self.OUT).split("|")[3])
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)

    def test_legacy_receipts_never_support_a_producer(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        self.make_legacy(digest)
        out = self.verify("report", digest)
        entry, = self.outputs_of(digest)
        self.assertEqual((entry["evidence_method"], entry["strength"]), ("timing-only", "candidate"))
        self.assertIn("launch link not recorded", entry["reason"])
        self.assertIn("1 receipt(s) predate launch matching", out)
        self.assertNotIn("no checked launch", out)  # not a gap of its own: only the producer stays a gap
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)

    def rival(self, receipt, start_offset, end_offset, **changes):
        """An exploratory run whose attempt lasted from receipt ts + start_offset to + end_offset."""
        rival = dict(receipt, command="python analysis/a/scratch.py", paths=["analysis/a/scratch.py"],
                     explore=True, plans=[], attempt_id="ee" * 8, call_id=None, ts=receipt["ts"] + end_offset,
                     started=receipt["ts"] + start_offset, outputs_observation="skipped: no declared outputs")
        rival.pop("outputs_changed", None)
        rival.update(changes)
        with open(gate.state_path(self.root, "receipts.jsonl"), "a") as handle:
            handle.write(json.dumps(rival) + "\n")

    def test_an_overlapping_attempt_makes_the_observed_producer_unresolved(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        receipt = self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        self.rewrite_receipts(lambda r: r.update(started=r["ts"] - 3))
        self.rival(receipt, -2, 1)  # an exploratory run in the same seconds could have written it too
        out = self.verify("report", digest)
        entry, = self.outputs_of(digest)
        self.assertEqual((entry["evidence_method"], entry["strength"], entry["producer_attempt"]),
                         ("attempt-observed", "unresolved", None))
        self.assertEqual(len(entry["candidates"]), 2)
        self.assertTrue(any("scratch.py" in c for c in entry["candidates"]), entry)
        self.assertEqual(self.output_row(out, self.OUT).split("|")[3].strip(), "unresolved")
        self.assertIn("an overlapping attempt could also have written it", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)

    def test_a_later_attempt_does_not_make_an_observed_producer_unresolved(self):  # control
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        receipt = self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        self.rewrite_receipts(lambda r: r.update(started=r["ts"] - 3))
        self.rival(receipt, 60, 61)  # an exploratory run a minute later
        entry, = self.outputs_of(digest)
        self.assertEqual((entry["evidence_method"], entry["strength"]), ("attempt-observed", "supported"))

    def test_two_runs_of_one_plan_each_keep_their_own_output(self):  # control: a sibling that watched and did not list it
        other = "analysis/a/outputs/other.tsv"
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT + " " + other))
        self.run_cmd("python " + FIT + " --part a", writes={self.OUT: "x\n"})
        self.run_cmd("python " + FIT + " --part b", writes={other: "y\n"})
        out = self.verify("report", digest)
        self.assertEqual(sorted((e["path"], e["strength"]) for e in self.outputs_of(digest)),
                         [(self.OUT, "supported"), (other, "supported")])
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)

    def test_a_file_inside_a_declared_folder_is_observed_during_its_attempt(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs="analysis/a/outputs/"))
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})  # the gate lists the files in the declared folder
        entry, = self.outputs_of(digest)
        self.assertEqual((entry["evidence_method"], entry["strength"]), ("attempt-observed", "supported"))

    def test_a_snakemake_record_with_one_wrapper_is_only_a_candidate(self):
        step = "analysis/a/01_step.R"
        for path in (step, "analysis/a/run.sh"):
            self.write(path, "x\n", mtime=time.time() - 60)
        digest = self.approve(plan("`analysis/a/run.sh`", "`{}`".format(step), outputs=self.OUT))
        self.write(self.OUT, "x\n", mtime=time.time() + 1)
        self.snakemake_record("outputs/fit.tsv", "s01_step", time.time(), ["01_step.R"], "Rscript 01_step.R")
        self.run_cmd("bash analysis/a/run.sh")
        out = self.verify("report", digest)
        entry, = self.outputs_of(digest)
        self.assertEqual((entry["evidence_method"], entry["strength"]), ("workflow-record", "candidate"))
        self.assertEqual(entry["rule"], "Snakemake rule `s01_step`")
        by = self.output_row(out, self.OUT).split("|")[3]
        self.assertIn("unresolved", by)
        self.assertNotIn("bash analysis/a/run.sh", by)
        self.assertIn("likely written by", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)

    def test_a_snakemake_record_with_two_compatible_wrappers_is_unresolved(self):
        step = "analysis/a/01_step.R"
        for path in (step, "analysis/a/run.sh"):
            self.write(path, "x\n", mtime=time.time() - 60)
        digest = self.approve(plan("`analysis/a/run.sh`", "`{}`".format(step), outputs=self.OUT))
        self.write(self.OUT, "x\n", mtime=time.time() + 1)
        self.snakemake_record("outputs/fit.tsv", "s01_step", time.time(), ["01_step.R"], "Rscript 01_step.R")
        self.run_cmd("bash analysis/a/run.sh")
        self.run_cmd("bash analysis/a/run.sh --again")
        entry, = self.outputs_of(digest)
        self.assertEqual((entry["evidence_method"], entry["strength"]), ("workflow-record", "unresolved"))
        self.assertEqual(len(entry["candidates"]), 2)

    # C01: launch evidence

    def test_a_post_without_pre_is_a_gap_not_a_checked_launch(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        self.post_only("python " + FIT)
        out = self.verify("report", digest)
        self.assertIn("no checked launch: Post without matching Pre", out)
        self.assertIn("1 unmatched", out.split("## Planned scripts")[0])
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)

    def test_identical_launches_without_call_ids_are_an_ambiguous_gap(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        event = {"tool_name": "Bash", "tool_input": {"command": "python " + FIT}}
        self.hook("tool", event)
        self.hook("tool", event)  # the same call again before the first one reported back
        self.post_only("python " + FIT)
        self.post_only("python " + FIT)
        out = self.verify("report", digest)
        self.assertIn("ambiguous launch", out)
        self.assertIn("2 ambiguous", out.split("## Planned scripts")[0])
        self.assertNotIn("no checked launch", out)

    def abandon_a_launch(self):
        """A Pre whose Post never came, older than the gate's 24 h expiry; a later Pre moves it aside."""
        self.hook("tool", {"tool_name": "Bash", "tool_input": {"command": "python " + FIT}, "tool_use_id": "gone"})
        for path in glob.glob(os.path.join(gate.state_path(self.root, "launches"), "*.json")):
            os.utime(path, (time.time() - 2 * 86400,) * 2)
            with open(path) as handle:
                record = json.load(handle)
            record["started"] = record["ts"] = time.time() - 2 * 86400
            with open(path, "w") as handle:
                json.dump(record, handle)
            os.utime(path, (record["ts"],) * 2)
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        return glob.glob(os.path.join(gate.state_path(self.root, "launches", "abandoned"), "*.json"))

    def test_an_abandoned_attempt_of_this_plan_is_a_gap(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        kept, = self.abandon_a_launch()
        out = self.verify("report", digest)
        self.assertRegex(out, r"Attempt started at .* has no completion record")
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS_WITH_GAPS"), out)
        with open(kept) as handle:  # kept, not deleted
            self.assertEqual(json.load(handle)["call_id"], "gone")

    def test_an_abandoned_attempt_of_another_plan_is_not_this_plans_gap(self):  # control
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        kept, = self.abandon_a_launch()
        with open(kept) as handle:
            record = json.load(handle)
        for entries in record["runs"].values():
            for entry in entries:
                entry["plans"] = ["deadbeef"]
                entry["instance_ids"] = {"deadbeef": "0" * 16}
        with open(kept, "w") as handle:
            json.dump(record, handle)
        out = self.verify("report", digest)
        self.assertNotIn("no completion record", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)

    def test_the_report_opens_with_what_was_checked(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        self.post_only("python " + FIT)
        self.stamp_last_receipt(time.time() + 60)  # a minute on, so it cannot have written the output
        out = self.verify("report", digest)
        scope = out.split("## Scope")[1].split("## Planned scripts")[0]
        self.assertIn("2 run(s)", scope)
        self.assertIn("1 matched", scope)
        self.assertIn("1 unmatched", scope)
        self.assertIn("0 legacy", scope)
        self.assertIn("1 of 1 output(s) have a supported producer", scope)

    # C04/F04: one approval instance at a time

    def reapproved_with_new_input(self):
        """The same plan text approved twice with its input edited between: two instances. Returns
        (hash, first instance, second instance); one run happened under the first."""
        self.write("data/in.tsv", "a\n", mtime=time.time() - 3600)
        text = plan("run `{}`".format(FIT), inputs="data/in.tsv", outputs=self.OUT)
        digest = self.approve(text)
        approvals = gate.state_path(self.root, "approvals", digest + ".json")
        first = gate.read_json(approvals, {})["instance_id"]
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        self.write("data/in.tsv", "b changed\n", mtime=time.time() - 3000)
        self.assertEqual(self.approve(text), digest)
        second = gate.read_json(approvals, {})["instance_id"]
        self.assertNotEqual(first, second)
        return digest, first, second

    def test_a_run_under_an_older_instance_does_not_establish_the_current_freeze(self):
        digest, first, second = self.reapproved_with_new_input()
        out = self.verify("report", digest)
        self.assertIn("No run is recorded under approval instance {}".format(second), out)
        self.assertIn("1 run(s) of this plan ran under other approval instance(s)", out)
        self.assertIn("approval instance {}".format(second), out.split("## Planned scripts")[0])
        self.assertIn("| `{}` | no receipt |".format(FIT), out)
        self.assertNotIn("Verify status: CONFORMS\n", out)

    def test_a_run_under_the_current_instance_is_the_evidence(self):  # control
        digest, first, second = self.reapproved_with_new_input()
        self.rewrite_receipts(lambda r: r.update(ts=r["ts"] - 120))  # the first run was minutes earlier
        self.run_cmd("python " + FIT, writes={self.OUT: "again\n"})
        out = self.verify("report", digest)
        self.assertNotIn("No run is recorded under approval instance", out)
        self.assertIn("1 run(s) of this plan ran under other approval instance(s)", out)  # history stays visible
        self.assertIn("| `{}` | ran |".format(FIT), out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)

    def test_an_older_instance_can_be_selected_and_is_checked_against_its_own_pins(self):
        digest, first, second = self.reapproved_with_new_input()
        out = self.verify("report", digest, "--instance", first)
        self.assertIn("approval instance {} (an earlier freeze".format(first), out)
        self.assertIn("| `{}` | ran |".format(FIT), out)
        self.assertIn("Input `data/in.tsv` changed since the approval", out)  # the file moved on since that freeze
        self.assertNotIn("No run is recorded under approval instance", out)
        self.assertIn("no approval instance", self.verify("report", digest, "--instance", "0" * 16, fails=True))
        self.assertIn("`write` records the current approval instance ({})".format(second), self.verify(
            "write", digest, "--analysis-dir", "analysis/a", "--instance", first, fails=True))  # one bundle per hash

    def test_reapproving_an_unchanged_freeze_keeps_one_instance(self):  # control
        text = plan("run `{}`".format(FIT), outputs=self.OUT)
        digest = self.approve(text)
        approvals = gate.state_path(self.root, "approvals", digest + ".json")
        first = gate.read_json(approvals, {})["instance_id"]
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        self.approve(text)
        self.assertEqual(gate.read_json(approvals, {})["instance_id"], first)
        out = self.verify("report", digest)
        self.assertNotIn("other approval instance", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)

    def test_a_legacy_approval_is_read_as_before_with_an_info_line(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        path = gate.state_path(self.root, "approvals", digest + ".json")
        record = gate.read_json(path, {})
        record.pop("instance_id")
        with open(path, "w") as handle:
            json.dump(record, handle)
        out = self.verify("report", digest)
        self.assertIn("predates approval instances", out)
        self.assertNotIn("No run is recorded under approval instance", out)
        self.assertTrue(out.rstrip().endswith("Verify status: CONFORMS"), out)

    def test_the_bundle_keeps_evidence_method_attempt_and_instance(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        receipt = self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        instance = gate.read_json(gate.state_path(self.root, "approvals", digest + ".json"), {})["instance_id"]
        self.verify("write", digest, "--analysis-dir", "analysis/a")
        with open(os.path.join(self.root, "analysis/a/provenance/outputs-{}.tsv".format(digest))) as handle:
            header, row = [line.rstrip("\n").split("\t") for line in handle][:2]
        self.assertEqual(header[:6], ["path", "written", "size", "sha256", "fingerprint", "written_by"])
        self.assertEqual(header[6:], ["producer_attempt", "evidence_method", "strength", "approval_instance"])
        self.assertEqual(row[6:], [receipt["attempt_id"], "attempt-observed", "supported", instance])

    def test_a_reapproval_while_a_run_is_in_flight_leaves_that_run_under_the_old_instance(self):  # F04 probe shape
        self.write("data/in.tsv", "a\n", mtime=time.time() - 3600)
        text = plan("run `{}`".format(FIT), inputs="data/in.tsv", outputs=self.OUT)
        digest = self.approve(text)
        approvals = gate.state_path(self.root, "approvals", digest + ".json")
        first = gate.read_json(approvals, {})["instance_id"]
        command = {"command": "python " + FIT}
        self.hook("tool", {"tool_name": "Bash", "tool_input": command, "tool_use_id": "long"})  # still running
        self.write("data/in.tsv", "b changed\n", mtime=time.time() - 3000)
        self.assertEqual(self.approve(text), digest)
        second = gate.read_json(approvals, {})["instance_id"]
        self.write(self.OUT, "x\n")
        self.post_only("python " + FIT, call_id="long")
        receipt = self.read_receipts()[-1]
        self.assertEqual((receipt["approval_instance"], receipt["launch_match"]), (first, "matched"))
        out = self.verify("report", digest)
        self.assertIn("No run is recorded under approval instance {}".format(second), out)
        self.assertIn("1 run(s) of this plan ran under other approval instance(s) ({}: 1)".format(first), out)
        entry, = self.outputs_of(digest)
        self.assertNotEqual(entry["strength"], "supported")  # a run of the old freeze names no producer for the new one

    def test_an_older_bundle_without_evidence_columns_is_labelled_legacy(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        self.verify("write", digest, "--analysis-dir", "analysis/a")
        row, = json.loads(self.verify("status", "--json"))
        self.assertEqual(row["verified"], "CONFORMS (complete)")  # a new bundle needs no label
        folder = os.path.join(self.root, "analysis/a/provenance")
        table = os.path.join(folder, "outputs-{}.tsv".format(digest))
        with open(table) as handle:  # the table as the verify before this change wrote it: six columns
            old = "".join("\t".join(line.rstrip("\n").split("\t")[:6]) + "\n" for line in handle)
        with open(table, "w") as handle:
            handle.write(old)
        marker = os.path.join(folder, "complete-{}.json".format(digest))
        with open(marker) as handle:  # still a checksummed, complete bundle
            record = json.load(handle)
        record["sha256"]["outputs-{}.tsv".format(digest)] = hashlib.sha256(old.encode("utf-8")).hexdigest()
        with open(marker, "w") as handle:
            json.dump(record, handle)
        row, = json.loads(self.verify("status", "--json"))
        self.assertEqual(row["verified"], "CONFORMS (complete, legacy producers)")

    # C05: a Slurm submission is not a completion

    def sbatch_plan(self):
        self.write("jobs/fit.job", "#!/bin/bash\n", mtime=time.time() - 3600)
        digest = self.approve(plan("`sbatch jobs/fit.job`", outputs=self.OUT))
        self.run_cmd("sbatch jobs/fit.job", stdout="Submitted batch job 4242")
        return digest

    def test_slurm_job_states_and_exit_codes_are_judged_not_assumed(self):
        digest = self.sbatch_plan()
        line = "4242|{}|{}|2026-09-30T10:00:00|2026-09-30T10:05:00"
        for state, code, level, text in [
                ("PENDING", "0:0", "gap", "Slurm job 4242 is PENDING"),  # submitted
                ("RUNNING", "0:0", "gap", "Slurm job 4242 is RUNNING"),
                ("FAILED", "1:0", "block", "Slurm job 4242 ended FAILED"),
                ("COMPLETED", "1:0", "block", "Slurm job 4242 reports COMPLETED but its ExitCode is 1:0"),
                ("COMPLETED", "0:9", "block", "Slurm job 4242 reports COMPLETED but its ExitCode is 0:9"),  # killed by a signal
                ("COMPLETED", "garbage", "gap", "Slurm job 4242 reports COMPLETED but its ExitCode `garbage` is not readable"),
                ("NOT_FOUND", "", "gap", "Slurm job 4242 is NOT_FOUND")]:
            with self.subTest(state=state, code=code):
                out = self.verify("report", digest, sacct=self.fake_sacct(line.format(state, code)
                                                                          if state != "NOT_FOUND" else ""))
                self.assertIn("**{}**: `sbatch jobs/fit.job`: {}".format(level, text), out)
        out = self.verify("report", digest, sacct=self.fake_sacct(line.format("COMPLETED", "0:0")))  # control
        self.assertNotIn("Slurm job 4242", out)
        out = self.verify("report", digest, sacct=os.path.join(self.root, "no-sacct"))
        self.assertIn("**gap**: `sbatch jobs/fit.job`: Slurm job 4242 is of unknown state", out)

    def test_a_slurm_array_with_an_unfinished_or_failed_task_is_not_complete(self):
        digest = self.sbatch_plan()
        rows = "4242_1|COMPLETED|0:0|||\n4242_2|{}|{}|||"
        for state, code, level, text in [
                ("RUNNING", "0:0", "gap", "Slurm job 4242 is RUNNING"),
                ("PENDING", "0:0", "gap", "Slurm job 4242 is PENDING"),
                ("COMPLETED", "2:0", "block", "Slurm job 4242 reports COMPLETED but its ExitCode is 2:0"),
                ("COMPLETED", "0:0", None, None)]:  # control: every task finished cleanly
            with self.subTest(state=state, code=code):
                out = self.verify("report", digest, sacct=self.fake_sacct(rows.format(state, code)))
                if level:
                    self.assertIn("**{}**: `sbatch jobs/fit.job`: {}".format(level, text), out)
                else:
                    self.assertNotIn("Slurm job 4242", out)

    # C06/F06: an approved validation binding is reconciled with the result of its matched run

    CHECK = "analysis/a/scripts/02_check.py"
    EXPECT = "analysis/a/tests/expect.json"
    EVID = "analysis/a/outputs/check.json"
    CONTRACT_SCHEMA = "mycelium-extra.contract_result.v1"

    def binding(self, **changes):
        base = {"id": "V1", "plan_row": "2", "required": True, "defined_by": "researcher-approved",
                "test_paths": [self.EXPECT], "invocation": ["python", self.CHECK], "evidence_path": self.EVID}
        base.update(changes)
        return base

    def bound_plan(self, *checks, **kwargs):
        """FIT and the check script as plan rows 1 and 2, the binding block, and the evidence as the declared output."""
        self.write(self.CHECK, "print('check')\n", mtime=time.time() - 3600)
        self.write(self.EXPECT, '{"rows": 60}\n', mtime=time.time() - 3600)
        text = plan("run `{}`".format(FIT), "run `{}`".format(self.CHECK), outputs=self.EVID,
                    inputs=kwargs.get("inputs"))
        block = "<!-- validation-bindings {} -->\n\n".format(json.dumps({"version": 1, "checks": list(checks or [self.binding()])}))
        return text.replace("Plan status: READY", block + "Plan status: READY")

    def run_check(self, evidence, **kwargs):
        """The check script run as a matched attempt that writes `evidence` (a dict, or text) as its result."""
        text = evidence if isinstance(evidence, str) else json.dumps(evidence)
        return self.run_cmd("python " + self.CHECK, writes={self.EVID: text}, **kwargs)

    def validation_of(self, digest, *args):
        return dict((v["id"], v) for v in json.loads(self.verify("report", digest, "--json", *args))["validation"])

    def ends(self, out, status):
        self.assertTrue(out.rstrip().endswith("Verify status: " + status), out)

    def contract_result(self, status, code, checks):
        return {"schema": self.CONTRACT_SCHEMA, "status": status, "exit_code": code, "runnable": "all_ran", "not_run": [],
                "contract": {"path": "x", "sha256": None}, "checks": checks}

    def test_a_check_that_exited_zero_with_a_failed_result_blocks(self):  # F06: the 60-row expectation, one row found
        digest = self.approve(self.bound_plan())
        self.run_cmd("python " + FIT)
        self.run_check({"status": "failed", "message": "1 row found, 60 expected"})  # the script itself exits 0
        out = self.verify("report", digest)
        self.assertIn("**block**: Validation `V1` (plan row 2, required; declared researcher-approved, not verified) "
                      "failed: the result says failed (1 row found, 60 expected)", out)
        self.assertIn("Verify status: DOES_NOT_CONFORM", out)
        self.assertEqual(self.validation_of(digest)["V1"]["outcome"], "failed")

    def test_a_required_check_that_never_ran_is_not_established(self):
        digest = self.approve(self.bound_plan())
        self.run_cmd("python " + FIT)
        out = self.verify("report", digest)
        self.assertIn("**gap**: Validation `V1` (plan row 2, required; declared researcher-approved, not verified) was "
                      "not run: no matched run of `python {}` under this approval".format(self.CHECK), out)
        self.assertIn("not established", out)
        self.assertNotIn("Verify status: CONFORMS\n", out)
        self.assertEqual(self.validation_of(digest)["V1"]["outcome"], "not run")

    def test_an_approved_expectation_with_a_matched_passing_run_conforms(self):  # control
        digest = self.approve(self.bound_plan())
        self.run_cmd("python " + FIT)
        receipt = self.run_check({"status": "passed"})
        out = self.verify("report", digest)
        self.assertIn("## Validation", out)
        self.assertIn("- `V1` (plan row 2, required; declared researcher-approved, not verified): passed", out)
        self.assertNotIn("Validation `V1`", out.split("## Findings")[1])  # no finding for a pass
        self.ends(out, "CONFORMS")
        one = self.validation_of(digest)["V1"]
        self.assertEqual((one["outcome"], one["attempt_id"]), ("passed", receipt["attempt_id"]))
        self.assertEqual(one["evidence_sha256"], hashlib.sha256(b'{"status": "passed"}').hexdigest())

    def test_a_pass_written_outside_the_attempt_is_unattributable(self):  # forged or self-asserted
        digest = self.approve(self.bound_plan())
        self.run_cmd("python " + FIT)
        self.write(self.EVID, '{"status": "passed"}')  # the agent writes the result itself
        self.run_cmd("python " + self.CHECK)  # the check runs and writes nothing
        out = self.verify("report", digest)
        self.assertIn("**gap**: Validation `V1`", out)
        self.assertIn("has unattributable evidence: the matched attempt did not create or change `{}`".format(self.EVID), out)
        self.assertNotIn("Verify status: CONFORMS\n", out)
        self.assertEqual(self.validation_of(digest)["V1"]["outcome"], "unattributable")

    def test_a_result_rewritten_after_its_attempt_is_unattributable(self):
        digest = self.approve(self.bound_plan())
        self.run_cmd("python " + FIT)
        receipt = self.run_check({"status": "failed"})
        self.write(self.EVID, '{"status": "passed"}', mtime=receipt["ts"] + 600)  # edited afterwards to excuse the run
        out = self.verify("report", digest)
        self.assertIn("has unattributable evidence: `{}` was modified after the attempt".format(self.EVID), out)
        self.assertNotIn("Verify status: DOES_NOT_CONFORM", out)  # the edited pass is not read at all

    def test_a_result_from_an_earlier_approval_instance_is_not_carried_over(self):  # old result, new inputs
        self.write("data/in.tsv", "a\n", mtime=time.time() - 3600)
        text = self.bound_plan(inputs="data/in.tsv")
        digest = self.approve(text)
        self.run_cmd("python " + FIT)
        self.run_check({"status": "passed"})
        self.write("data/in.tsv", "b changed\n", mtime=time.time() - 3000)
        self.assertEqual(self.approve(text), digest)  # new pins: a second instance of the same plan text
        out = self.verify("report", digest)
        self.assertIn("**gap**: Validation `V1`", out)
        self.assertIn("was not run: no matched run of `python {}` under this approval instance; it ran under another "
                      "approval instance only".format(self.CHECK), out)
        self.assertNotIn("Verify status: CONFORMS\n", out)

    def test_an_expectation_edited_after_approval_loses_its_authority(self):
        digest = self.approve(self.bound_plan())
        self.run_cmd("python " + FIT)
        self.run_check({"status": "passed"})
        self.write(self.EXPECT, '{"rows": 10}\n')  # the expected value is edited to excuse the analysis
        out = self.verify("report", digest)
        self.assertIn("**gap**: Validation `V1`", out)
        self.assertIn("changed since approval: pinned `{}` is no longer the approved file".format(self.EXPECT), out)
        self.assertNotIn("Verify status: CONFORMS\n", out)
        self.assertEqual(self.validation_of(digest)["V1"]["outcome"], "changed")

    def test_an_unrelated_edit_does_not_change_the_check(self):  # control
        digest = self.approve(self.bound_plan())
        self.run_cmd("python " + FIT)
        self.run_check({"status": "passed"})
        self.write("analysis/a/notes.md", "unrelated\n")
        self.ends(self.verify("report", digest), "CONFORMS")

    def unsupported(self, text):
        digest = self.approve(self.bound_plan())
        self.run_cmd("python " + FIT)
        self.run_check(text)
        out = self.verify("report", digest)
        self.assertIn("**gap**: Validation `V1`", out)
        self.assertIn("has unsupported evidence", out)
        self.assertNotIn("Verify status: CONFORMS\n", out)
        self.assertEqual(self.validation_of(digest)["V1"]["outcome"], "unsupported")

    def test_a_result_with_no_status_is_unsupported(self):
        self.unsupported('{"result": "ok"}')

    def test_a_result_that_is_not_json_is_unsupported(self):
        self.unsupported("all fine\n")

    def test_a_result_with_an_unknown_status_is_unsupported(self):
        self.unsupported('{"status": "maybe"}')

    def test_a_result_that_is_not_an_object_is_unsupported(self):
        self.unsupported("[1, 2]")

    def test_a_contract_result_is_judged_by_its_exit_code_and_blocks(self):
        digest = self.approve(self.bound_plan())
        self.run_cmd("python " + FIT)
        blocked = {"id": "de-rowcount", "status": "block", "runnable": "ran", "message": "row count differs from the plan",
                   "alerts": [{"expected": "60", "observed": "10"}]}
        self.run_check(self.contract_result("block", 2, [blocked]), exit_code=2)  # a runner that returns the checker's code
        out = self.verify("report", digest)
        self.assertIn("failed: the check command exited 2 at ", out)
        self.assertIn("; the data-contract result is block (exit 2); `de-rowcount`: row count differs from the "
                      "plan (expected 60, observed 10)", out)
        self.assertIn("Verify status: DOES_NOT_CONFORM", out)

    def test_a_contract_result_with_warnings_only_passes_and_keeps_them(self):
        digest = self.approve(self.bound_plan())
        self.run_cmd("python " + FIT)
        warned = {"id": "balance", "status": "warn", "runnable": "ran", "message": "x",
                  "alerts": [{"message": "a batch holds more than 70%", "blocking": False}]}
        self.run_check(self.contract_result("warn", 0, [warned]))
        out = self.verify("report", digest)
        self.assertIn("passed with 1 warning(s): `balance`: a batch holds more than 70%", out)
        self.assertEqual(self.validation_of(digest)["V1"]["outcome"], "passed")
        self.assertEqual(self.validation_of(digest)["V1"]["warnings"], ["`balance`: a batch holds more than 70%"])
        self.ends(out, "CONFORMS")

    def test_a_contract_result_that_could_not_run_is_not_run(self):
        digest = self.approve(self.bound_plan())
        self.run_cmd("python " + FIT)
        gap = {"id": "c", "status": "gap", "runnable": "table_unreadable", "message": "unreadable", "alerts": []}
        self.run_check(self.contract_result("gap", 3, [gap]))
        out = self.verify("report", digest)
        self.assertIn("**gap**: Validation `V1`", out)
        self.assertIn("was not run: the data-contract result is gap (exit 3)", out)
        self.assertEqual(self.validation_of(digest)["V1"]["outcome"], "not run")

    def test_a_contract_that_could_not_run_stays_a_gap_when_the_runner_returns_the_checkers_exit_code(self):
        for code, status, runnable in ((3, "gap", "table_unreadable"), (1, "error", "contract_error")):
            with self.subTest(exit_code=code):
                self.tearDown()
                self.setUp()
                digest = self.approve(self.bound_plan())
                self.run_cmd("python " + FIT)
                gap = {"id": "c", "status": status, "runnable": runnable, "message": "x", "alerts": []}
                self.run_check(self.contract_result(status, code, [gap]), exit_code=code)
                out = self.verify("report", digest)
                self.assertIn("was not run: the data-contract result is {} (exit {})".format(status, code), out)
                self.assertNotIn("**block**: Validation", out)  # the validation finding is a gap ...
                self.assertIn("**block**: `{}` failed (exit {})".format(self.CHECK, code), out)  # ... the failed run blocks as any run does
                self.assertEqual(self.validation_of(digest)["V1"]["outcome"], "not run")

    def test_a_contract_result_from_another_contract_is_changed(self):
        self.write("analysis/a/tests/contract.json", "{}\n", mtime=time.time() - 3600)
        digest = self.approve(self.bound_plan(self.binding(test_paths=["analysis/a/tests/contract.json"])))
        self.run_cmd("python " + FIT)
        result = self.contract_result("pass", 0, [])
        result["contract"]["sha256"] = "0" * 64  # produced from a contract that is not the pinned one
        self.run_check(result)
        out = self.verify("report", digest)
        self.assertIn("changed since approval: the result was produced from a contract that is not the pinned one", out)

    def test_an_optional_check_never_blocks(self):
        digest = self.approve(self.bound_plan(self.binding(required=False)))
        self.run_cmd("python " + FIT)
        self.run_check({"status": "failed"})
        out = self.verify("report", digest)
        self.assertIn("**info**: Validation `V1` (plan row 2, optional;", out)
        self.assertNotIn("**block**", out)
        self.ends(out, "CONFORMS")

    def test_the_bundle_keeps_the_binding_each_outcome_and_the_raw_evidence_hash(self):
        digest = self.approve(self.bound_plan())
        self.run_cmd("python " + FIT)
        receipt = self.run_check({"status": "passed"})
        self.verify("write", digest, "--analysis-dir", "analysis/a")
        folder = os.path.join(self.root, "analysis/a/provenance")
        with open(os.path.join(folder, "validation-{}.json".format(digest))) as handle:
            record = json.load(handle)
        one, = record["binding"]["checks"]
        self.assertEqual((one["id"], sorted(one["files"]), len(one["definition_sha256"])), ("V1", [self.EXPECT], 64))
        result, = record["results"]
        self.assertEqual((result["outcome"], result["attempt_id"], result["evidence_path"]),
                         ("passed", receipt["attempt_id"], self.EVID))
        self.assertEqual(result["evidence_sha256"], hashlib.sha256(b'{"status": "passed"}').hexdigest())
        with open(os.path.join(folder, "complete-{}.json".format(digest))) as handle:
            self.assertIn("validation-{}.json".format(digest), json.load(handle)["sha256"])
        import provenance
        self.assertEqual(provenance.bundle_state(folder, digest), "complete")
        self.assertIn("[validation](validation-{}.json)".format(digest), open(os.path.join(folder, "PROVENANCE.md")).read())

    # C07/F08: every attempt of a step stays visible; a recovery is judged on what changed

    def recovery(self, out):
        self.assertIn("## Recovery", out)
        return out.split("## Recovery")[1].split("\n## ")[0]

    def findings(self, out):
        return out.split("## Findings")[1].split("## Not visible")[0]

    def fit_plan(self):
        return self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))

    def test_a_success_after_a_changed_argument_keeps_the_earlier_failure_visible(self):  # F08
        digest = self.fit_plan()
        self.run_cmd("python {} --model original".format(FIT), exit_code=1)
        self.run_cmd("python {} --model alternative".format(FIT), writes={self.OUT: "x\n"})
        out = self.verify("report", digest)
        recovery = self.recovery(out)
        self.assertIn("`python {} --model original`: failed (exit 1)".format(FIT), recovery)
        self.assertIn("`python {} --model alternative`: succeeded (exit 0); changed from the previous attempt: "
                      "removed `original`, added `alternative`".format(FIT), recovery)
        self.assertIn("**gap**: Step `{}` recovered with a changed command: equivalence not established".format(FIT), out)
        self.assertNotIn("**block**", out)  # a recovery is not a failure
        self.assertIn("| `{}` | ran |".format(FIT), out)  # the row keeps its latest outcome
        self.ends(out, "CONFORMS_WITH_GAPS")

    def test_a_retry_of_the_same_command_is_an_equivalent_recovery(self):  # control
        digest = self.fit_plan()
        self.run_cmd("python " + FIT, exit_code=1)
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        out = self.verify("report", digest)
        recovery = self.recovery(out)
        self.assertIn("`python {}`: failed (exit 1)".format(FIT), recovery)
        self.assertIn("recovered: equivalent retry", recovery)
        self.assertIn("**info**: Step `{}` recovered: equivalent retry".format(FIT), out)
        self.assertNotIn("**block**", out)
        self.assertNotIn("**gap**", out)
        self.ends(out, "CONFORMS")

    def exact_plan(self, argv, operational, second=False):
        step = {"row": "1", "argv": argv, "cwd": ".", "env": {}, "operational": operational}
        rows = ["run `{}`".format(FIT)] + (["run `analysis/a/scripts/02_plot.py`"] if second else [])
        block = "<!-- exact-execution {} -->\n\n".format(json.dumps({"version": 1, "steps": [step]}))
        return plan(*rows, outputs=self.OUT).replace("Plan status: READY", block + "Plan status: READY")

    def test_a_retry_that_differs_only_in_an_operational_flag_is_an_equivalent_recovery(self):
        digest = self.approve(self.exact_plan(["python", FIT, "--threads", "1"], ["--threads"]))
        self.run_cmd("python {} --threads 1".format(FIT), exit_code=1)
        self.run_cmd("python {} --threads 4".format(FIT), writes={self.OUT: "x\n"})
        out = self.verify("report", digest)
        self.assertIn("recovered: equivalent retry", self.recovery(out))
        self.assertNotIn("outside the exact reportable contract", out)
        self.ends(out, "CONFORMS")

    def test_a_run_no_exact_step_names_is_outside_the_exact_contract(self):
        self.write("analysis/a/scripts/02_plot.py", "print(2)\n", mtime=time.time() - 3600)
        digest = self.approve(self.exact_plan(["python", FIT], [], second=True))
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})  # the declared step
        self.run_cmd("python analysis/a/scripts/02_plot.py")  # covered by the table, named by no exact step
        out = self.verify("report", digest)
        gap, = [line for line in self.findings(out).splitlines() if "outside the exact reportable contract" in line]
        self.assertIn("**gap**", gap)
        self.assertIn("`python analysis/a/scripts/02_plot.py`", gap)
        self.assertNotIn("`python {}`".format(FIT), gap)  # the matched step is not in it
        self.ends(out, "CONFORMS_WITH_GAPS")

    def test_a_plan_without_exact_execution_never_reports_exact_match(self):  # control
        digest = self.fit_plan()
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        self.assertNotIn("exact reportable contract", self.verify("report", digest))

    def test_the_same_command_after_the_script_changed_is_not_an_equivalent_retry(self):
        digest = self.fit_plan()
        self.run_cmd("python " + FIT, exit_code=1)
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        records = self.read_receipts()
        records[0]["script"] = dict(records[0]["script"], sha256="0" * 64)  # the first attempt ran other code
        with open(gate.state_path(self.root, "receipts.jsonl"), "w") as handle:
            handle.write("".join(json.dumps(r) + "\n" for r in records))
        out = self.verify("report", digest)
        self.assertIn("script `{}` content changed".format(FIT), self.recovery(out))
        self.assertIn("**gap**: Step `{}` recovered after changed code or inputs: equivalence not established".format(FIT), out)
        self.assertNotIn("recovered: equivalent retry", out)

    def test_two_successful_attempts_with_different_arguments_are_listed_without_a_finding(self):
        other = "analysis/a/outputs/other.tsv"
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT + " " + other))
        self.run_cmd("python {} --part a".format(FIT), writes={self.OUT: "x\n"})
        self.run_cmd("python {} --part b".format(FIT), writes={other: "y\n"})
        out = self.verify("report", digest)
        self.assertIn("removed `a`, added `b`", self.recovery(out))
        self.assertNotIn("recovered", self.findings(out))
        self.ends(out, "CONFORMS")

    def test_a_step_run_once_has_no_recovery_section(self):  # control
        digest = self.fit_plan()
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        self.assertNotIn("## Recovery", self.verify("report", digest))


class LineageAndExploreHistoryTest(unittest.TestCase):
    """C05 lineage join and C09 verify side: Mycelium's lineage is candidate producer evidence only, never
    `supported`; explore history keeps every attempt, and an explore run never owns an output or validates."""
    setUp, tearDown, write, fake_sacct, fake_tool, hook, approve, run_cmd, post_only, verify = (
        VerifyTest.setUp, VerifyTest.tearDown, VerifyTest.write, VerifyTest.fake_sacct, VerifyTest.fake_tool,
        VerifyTest.hook, VerifyTest.approve, VerifyTest.run_cmd, VerifyTest.post_only, VerifyTest.verify)
    read_receipts, rewrite_receipts, outputs_of, output_row, ends = (
        VerifyTest.read_receipts, VerifyTest.rewrite_receipts, VerifyTest.outputs_of, VerifyTest.output_row,
        VerifyTest.ends)
    CHECK, EXPECT, EVID, binding, bound_plan, run_check, validation_of = (
        VerifyTest.CHECK, VerifyTest.EXPECT, VerifyTest.EVID, VerifyTest.binding, VerifyTest.bound_plan,
        VerifyTest.run_check, VerifyTest.validation_of)
    OUT = "analysis/a/outputs/fit.tsv"
    EXPLORE = "MYCELIUM_EXTRA_EXPLORE=1 "

    # ---- lineage as candidate producer evidence

    def iso(self, ts):
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))

    def lineage(self, *actions, session="s1", warnings=(), raw=None):
        text = raw if raw is not None else json.dumps({"session_id": session, "actions": list(actions),
                                                       "extraction_warnings": list(warnings)})
        self.write(".living/log/data-lineage/{}.json".format(session), text)

    def act(self, receipt, outputs=(), script=FIT, io="static", exit=0, missing=False, sha=None, command=None, **extra):
        """One lineage action as Mycelium's tracker writes it for `receipt`'s command."""
        outs = []
        for rel in outputs:
            rec = {"path": os.path.join(self.root, rel)}
            if missing:
                rec["_missing"] = True
            else:
                rec["sha256"] = sha or self.sha(rel)
            outs.append(rec)
        action = {"ts": self.iso(receipt["ts"]), "agent_id": None, "agent_type": None,
                  "bash_cmd": command or receipt["command"], "bash_exit": exit,
                  "script": os.path.join(self.root, script) if script else None, "script_sha256": "ab" * 32,
                  "inputs": [], "outputs": outs, "io_detection": io, "lineage_warnings": []}
        action.update(extra)
        return action

    def unobserved_run(self, command="python " + FIT):
        """A matched run whose gate observation of outputs was skipped, so only time and lineage speak for it."""
        receipt = self.run_cmd(command)
        self.rewrite_receipts(lambda r: r.get("command") == command and (
            r.update(outputs_observation="skipped: test") or r.pop("outputs_changed", None)))
        return receipt

    def candidate_case(self):
        """A plan whose one matched, unobserved run reported at ts; OUT is written a second before it."""
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        receipt = self.unobserved_run()
        self.write(self.OUT, "x\n", mtime=receipt["ts"] - 1)
        return digest, receipt

    def producer(self, digest):
        entry, = self.outputs_of(digest)
        return entry

    def test_lineage_alone_is_a_joined_candidate_never_supported(self):
        digest, receipt = self.candidate_case()
        self.lineage(self.act(receipt, [self.OUT]))
        out = self.verify("report", digest)
        entry = self.producer(digest)
        self.assertEqual((entry["evidence_method"], entry["strength"]), ("lineage-record", "candidate"))
        self.assertEqual(self.output_row(out, self.OUT).split("|")[3].strip(), "unresolved")  # By is not filled
        self.assertIn("inferred", entry["reason"])
        for word in ("session", "command", "script", "static"):
            self.assertIn(word, entry["reason"])
        self.assertIn("a candidate, not an established producer", out)
        self.ends(out, "CONFORMS_WITH_GAPS")

    def test_an_explicit_attempt_id_joins_without_the_session(self):
        digest, receipt = self.candidate_case()
        self.lineage(self.act(receipt, [self.OUT], attempt_id=receipt["attempt_id"]), session="2026-10-01-001")
        entry = self.producer(digest)
        self.assertEqual((entry["evidence_method"], entry["strength"]), ("lineage-record", "candidate"))
        self.assertIn("explicit", entry["reason"])
        self.assertNotIn("inferred", entry["reason"])

    def test_a_static_path_the_attempt_did_not_write_is_not_producer_evidence(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        receipt = self.run_cmd("python " + FIT)  # a print-only script: its attempt saw no output change
        self.write(self.OUT, "x\n", mtime=receipt["ts"] - 1)  # an independent writer
        self.lineage(self.act(receipt, [self.OUT]))  # the static scan names a path the script never wrote
        out = self.verify("report", digest)
        entry = self.producer(digest)
        self.assertEqual((entry["evidence_method"], entry["strength"]), ("timing-only", "candidate"))
        self.assertIn("Mycelium's lineage lists `{}` as a static output".format(self.OUT), out)
        self.assertIn("did not see it change", out)

    def test_lineage_that_cannot_be_trusted_or_joined_is_not_used(self):
        cases = [
            ("unresolved I/O detection", {"io": "unresolved"}, {}, "io_detection"),
            ("a nonzero exit", {"exit": 1}, {}, "exit"),
            ("a path missing when the action was recorded", {"missing": True}, {}, "missing"),
            ("a hash that is not the file's now", {"sha": "0" * 64}, {}, "hash"),
            ("another session", {}, {"session": "2026-10-01-001"}, "session"),
            ("another command", {"command": "python analysis/a/scripts/other.py"}, {}, "command"),
            ("another script", {"script": "analysis/a/scripts/other.py"}, {}, "script"),
            ("no script (inline code)", {"script": None}, {}, "script"),
        ]
        for label, changes, manifest, word in cases:
            with self.subTest(label):
                self.tearDown()
                self.setUp()
                digest, receipt = self.candidate_case()
                self.lineage(self.act(receipt, [self.OUT], **changes), **manifest)
                out = self.verify("report", digest)
                entry = self.producer(digest)
                self.assertEqual((entry["evidence_method"], entry["strength"]), ("timing-only", "candidate"))
                self.assertIn("lineage", out.lower())
                self.assertIn(word, json.dumps(entry["lineage"]))
                self.ends(out, "CONFORMS_WITH_GAPS")

    def test_two_attempts_that_fit_the_lineage_record_are_not_a_join(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        first = self.unobserved_run()
        second = self.unobserved_run()  # the same command, a moment later
        self.write(self.OUT, "x\n", mtime=second["ts"] - 1)
        self.lineage(self.act(second, [self.OUT]))
        entry = self.producer(digest)
        self.assertNotEqual(entry["evidence_method"], "lineage-record")
        self.assertIn("no unique", json.dumps(entry["lineage"]))
        self.assertNotEqual(entry["strength"], "supported")

    def test_lineage_agreeing_with_an_observed_attempt_is_noted_and_the_producer_stays_supported(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        receipt = self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        self.lineage(self.act(receipt, [self.OUT]))
        out = self.verify("report", digest)
        entry = self.producer(digest)
        self.assertEqual((entry["evidence_method"], entry["strength"], entry["producer_attempt"]),
                         ("attempt-observed", "supported", receipt["attempt_id"]))
        self.assertIn("lineage agrees", entry["reason"])
        self.ends(out, "CONFORMS")

    def test_lineage_without_the_observed_attempt_does_not_lower_the_producer(self):  # control: lineage lists another path
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        receipt = self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        self.lineage(self.act(receipt, ["analysis/a/outputs/other.tsv"], missing=True))
        entry = self.producer(digest)
        self.assertEqual((entry["evidence_method"], entry["strength"]), ("attempt-observed", "supported"))
        self.assertNotIn("lineage agrees", entry["reason"])

    def test_lineage_naming_another_attempt_as_producer_is_a_conflict(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        first = self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        second = self.run_cmd("python {} --again".format(FIT))
        records = self.read_receipts()
        mtime = first["ts"] - 1
        os.utime(os.path.join(self.root, self.OUT), (mtime, mtime))
        records[1].update(started=first["ts"] + 1, ts=first["ts"] + 2, outputs_observation="skipped: test")
        records[1].pop("outputs_changed", None)
        with open(gate.state_path(self.root, "receipts.jsonl"), "w") as handle:
            handle.write("".join(json.dumps(r) + "\n" for r in records))
        self.lineage(self.act(dict(second, ts=first["ts"] + 2), [self.OUT]))
        out = self.verify("report", digest)
        entry = self.producer(digest)
        self.assertEqual((entry["strength"], entry["producer_attempt"]), ("unresolved", None))
        self.assertEqual(self.output_row(out, self.OUT).split("|")[3].strip(), "unresolved")
        self.assertIn("two producers", out)
        self.assertEqual(len(entry["candidates"]), 2)
        self.ends(out, "CONFORMS_WITH_GAPS")

    def test_lineage_warnings_are_shown(self):
        digest, receipt = self.candidate_case()
        self.lineage(self.act(receipt, [self.OUT], lineage_warnings=["dynamic path guessed"]),
                     warnings=[os.path.join(self.root, FIT) + ": the runner moved"])
        out = self.verify("report", digest)
        self.assertIn("dynamic path guessed", out)
        self.assertIn("the runner moved", out)
        self.assertIn("a hash read from disk is not proof", out)

    def test_absent_lineage_in_an_active_session_leaves_the_timing_candidate(self):  # control
        digest, receipt = self.candidate_case()
        out = self.verify("report", digest)  # the manifest is written at Stop, so none exists yet
        entry = self.producer(digest)
        self.assertEqual((entry["evidence_method"], entry["strength"]), ("timing-only", "candidate"))
        self.assertEqual(entry["lineage"], [])
        self.assertNotIn("lineage names", out)
        self.ends(out, "CONFORMS_WITH_GAPS")

    def test_malformed_lineage_is_a_gap_as_before_and_never_crashes(self):
        for label, raw in [("not json", "{oops"), ("a list", "[1, 2]"), ("no actions", '{"actions": 3}'),
                           ("bad actions", json.dumps({"session_id": "s1", "actions": [
                               "x", 7, {"ts": "never", "outputs": "x"},
                               {"ts": self.iso(time.time()), "outputs": [3, {"path": 4}, "a"], "bash_exit": "zero",
                                "io_detection": ["static"], "lineage_warnings": "w"}]}))]:
            with self.subTest(label):
                self.tearDown()
                self.setUp()
                digest, receipt = self.candidate_case()
                self.lineage(raw=raw)
                out = self.verify("report", digest)
                entry = self.producer(digest)
                self.assertEqual((entry["evidence_method"], entry["strength"]), ("timing-only", "candidate"))
                self.ends(out, "CONFORMS_WITH_GAPS")

    def test_lineage_still_finds_unreceipted_scripts(self):  # control: the existing use survives the extension
        digest, receipt = self.candidate_case()
        self.lineage(self.act(receipt, [], script="/tmp/scratchpad/smoke.R"), self.act(receipt, [self.OUT]))
        out = self.verify("report", digest)
        self.assertIn("lineage saw `/tmp/scratchpad/smoke.R`", out)

    # ---- exploration history and promotion

    def scoped(self, text=None):
        digest = self.approve(text or plan("run `{}`".format(FIT), outputs=self.OUT))
        self.assertIn("scoped", self.hook("prompt", {"prompt": "allow explore " + digest})["systemMessage"])
        return digest, gate.read_json(gate.state_path(self.root, "approvals", digest + ".json"), {})["instance_id"]

    def sha(self, rel):
        with open(os.path.join(self.root, rel), "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()

    def test_explore_keeps_every_attempt_with_its_code_version_and_scope(self):
        digest, instance = self.scoped()
        first = self.sha(FIT)
        self.run_cmd(self.EXPLORE + "python " + FIT, exit_code=1)
        self.write(FIT, "print(2)\n")
        self.run_cmd(self.EXPLORE + "python " + FIT)
        runs = json.loads(self.verify("explore", "--session", "s1", "--json"))
        run, = runs
        self.assertEqual(run["runs"], 2)
        failed, fixed = run["attempts"]
        self.assertEqual((failed["exit_status"], fixed["exit_status"]), (1, 0))
        self.assertEqual((failed["script_sha256"], fixed["script_sha256"]), (first, self.sha(FIT)))
        self.assertNotEqual(failed["script_sha256"], fixed["script_sha256"])
        self.assertEqual((failed["scope"], fixed["scope"]), (instance, instance))
        self.assertTrue(failed["attempt_id"] and failed["attempt_id"] != fixed["attempt_id"])
        out = self.verify("explore", "--session", "s1")
        self.assertIn("exit 1", out)
        self.assertIn(first[:12], out)
        self.assertIn(self.sha(FIT)[:12], out)
        self.assertIn("scope " + instance, out)

    def test_a_plain_grant_attempt_is_shown_as_the_session_wide_grant(self):  # control
        self.hook("prompt", {"prompt": "allow explore"})
        self.run_cmd(self.EXPLORE + "python " + FIT)
        run, = json.loads(self.verify("explore", "--session", "s1", "--json"))
        attempt, = run["attempts"]
        self.assertIsNone(attempt["scope"])
        self.assertEqual(attempt["script_sha256"], self.sha(FIT))
        self.assertIn("session-wide grant", self.verify("explore", "--session", "s1"))

    def test_explore_states_that_promotion_needs_an_approved_rerun(self):
        self.hook("prompt", {"prompt": "allow explore"})
        self.run_cmd(self.EXPLORE + "python " + FIT)
        out = self.verify("explore", "--session", "s1")
        self.assertIn("approved rerun", out)
        self.assertIn("fresh output identity", out)
        self.assertIn("not re-run under approval", out)

    def test_an_explore_receipt_that_wrote_a_declared_output_does_not_own_it(self):
        digest, instance = self.scoped()
        receipt = self.run_cmd(self.EXPLORE + "python " + FIT, writes={self.OUT: "x\n"})
        self.assertTrue(receipt["explore"])
        out = self.verify("report", digest)
        entry = self.producer(digest)
        self.assertNotEqual(entry["strength"], "supported")
        self.assertIsNone(entry["producer_attempt"])
        self.assertEqual(self.output_row(out, self.OUT).split("|")[3].strip(), "unresolved")
        self.assertEqual(entry["promotion"], "not re-run under approval")
        self.assertIn("not re-run under approval", out)
        self.assertNotIn("Verify status: CONFORMS\n", out)

    def test_an_approved_rerun_that_saw_the_output_change_is_a_fresh_identity(self):  # control
        digest, instance = self.scoped()
        self.run_cmd(self.EXPLORE + "python " + FIT, writes={self.OUT: "x\n"})
        time.sleep(1.1)
        rerun = self.run_cmd("python " + FIT, writes={self.OUT: "y\n"})
        out = self.verify("report", digest)
        entry = self.producer(digest)
        self.assertEqual((entry["strength"], entry["producer_attempt"]), ("supported", rerun["attempt_id"]))
        self.assertNotIn("promotion", entry)
        self.assertNotIn("not re-run under approval", out)

    def test_an_approved_run_that_left_the_explore_output_untouched_is_not_a_promotion(self):
        digest, instance = self.scoped()
        explored = self.run_cmd(self.EXPLORE + "python " + FIT, writes={self.OUT: "x\n"})
        time.sleep(1.1)
        self.run_cmd("python " + FIT)  # approved, matched, but it did not write the output: same bytes, same file
        out = self.verify("report", digest)
        entry = self.producer(digest)
        self.assertNotEqual(entry["strength"], "supported")
        self.assertEqual(entry["promotion"], "not re-run under approval")
        self.assertIn(explored["attempt_id"], json.dumps(entry["explore_attempts"]))
        self.assertNotIn("Verify status: CONFORMS\n", out)

    def test_an_explore_run_of_a_checks_invocation_is_never_a_validation_result(self):  # control: holds today
        digest, instance = self.scoped(self.bound_plan())
        self.run_cmd("python " + FIT)
        self.run_cmd(self.EXPLORE + "python " + self.CHECK, writes={self.EVID: json.dumps({"status": "passed"})})
        self.rewrite_receipts(lambda r: r.get("explore") and r.update(validation_check="V1"))  # even if it claimed it
        one = self.validation_of(digest)["V1"]
        self.assertEqual(one["outcome"], "not run")
        out = self.verify("report", digest)
        self.assertNotIn("Verify status: CONFORMS\n", out)


class QualificationTest(unittest.TestCase):
    """C10: reportable qualification, content staleness, claim coverage, prose validation, rerun evidence.
    Borrows VerifyTest's helpers rather than subclassing it, so the 155 tests above do not run again."""

    for _name in ("setUp", "tearDown", "write", "fake_sacct", "fake_tool", "hook", "approve", "run_cmd", "post_only",
                  "verify", "ends", "read_receipts", "rewrite_receipts", "bound_plan", "binding", "run_check",
                  "sbatch_plan", "OUT", "CHECK", "EXPECT", "EVID", "CONTRACT_SCHEMA"):
        locals()[_name] = VerifyTest.__dict__[_name]
    del _name

    def qual(self, digest, *args):
        """{dimension: (state, reason)} and the whole record, from `report --json`."""
        record = json.loads(self.verify("report", digest, "--json", *args))["qualification"]
        return dict((d["dimension"], (d["state"], d["reason"])) for d in record["dimensions"]), record

    def established(self, dims, *names):
        for name in names:
            self.assertEqual(dims[name][0], "established", (name, dims[name]))

    # ---- qualification

    def test_a_fully_matched_run_qualifies_without_extra_prompts(self):  # positive control
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        dims, record = self.qual(digest)
        self.assertEqual(record["overall"], "qualified")
        self.established(dims, "authorization", "completion", "code and input identity", "lineage")
        self.assertEqual(dims["required validation"][0], "not applicable")
        self.assertEqual(dims["claim linkage"][0], "not applicable")
        out = self.verify("report", digest, "--require-reportable")  # exits 0
        self.assertIn("Qualification: **qualified**", out)
        self.assertNotIn("score", out.lower().split("## planned scripts")[0])  # no composite score
        self.ends(out, "CONFORMS")  # the legacy status is separate and unchanged

    def test_a_required_check_that_never_ran_leaves_the_run_unqualified(self):
        digest = self.approve(self.bound_plan())
        self.run_cmd("python " + FIT)
        dims, record = self.qual(digest)
        self.assertEqual(record["overall"], "not qualified")
        self.assertEqual(dims["required validation"][0], "not established")
        self.assertIn("V1", dims["required validation"][1])
        out = self.verify("report", digest)  # without the flag: same exit, same three status names
        self.assertIn("Qualification: **not qualified**", out)
        self.assertIn("Limitation:", out.split("## Planned scripts")[0])
        self.ends(out, "CONFORMS_WITH_GAPS")
        err = self.verify("report", digest, "--require-reportable", fails=True)
        self.assertIn("required validation", err)

    def test_a_passed_required_check_is_established(self):  # control
        digest = self.approve(self.bound_plan())
        self.run_cmd("python " + FIT)
        self.run_check({"status": "passed"})
        dims, record = self.qual(digest)
        self.assertEqual(dims["required validation"][0], "established")

    def test_a_run_only_submitted_to_slurm_is_not_complete(self):
        digest = self.sbatch_plan()
        pending = self.fake_sacct("4242|PENDING|0:0|2026-09-30T10:00:00|2026-09-30T10:05:00")
        record = json.loads(self.verify("report", digest, "--json", sacct=pending))["qualification"]
        dims = dict((d["dimension"], (d["state"], d["reason"])) for d in record["dimensions"])
        self.assertEqual(dims["completion"][0], "not established")
        self.assertIn("PENDING", dims["completion"][1])
        done = self.fake_sacct("4242|COMPLETED|0:0|2026-09-30T10:00:00|2026-09-30T10:05:00")  # control
        record = json.loads(self.verify("report", digest, "--json", sacct=done))["qualification"]
        self.assertEqual([d["state"] for d in record["dimensions"] if d["dimension"] == "completion"], ["established"])

    def test_an_unmatched_run_is_not_an_authorized_one(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        self.write(self.OUT, "x\n")
        self.post_only("python " + FIT)  # a Post with no Pre
        dims, _ = self.qual(digest)
        self.assertEqual(dims["authorization"][0], "not established")
        self.assertIn("unmatched", dims["authorization"][1])

    def test_an_unresolved_producer_leaves_lineage_unestablished(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        receipt = self.run_cmd("python " + FIT)  # print-only
        self.write(self.OUT, "x\n", mtime=receipt["ts"] - 1)  # an independent writer
        dims, record = self.qual(digest)
        self.established(dims, "authorization", "completion")
        self.assertEqual(dims["lineage"][0], "not established")
        self.assertIn(self.OUT, dims["lineage"][1])
        self.assertIn("candidate producer (timing-only)", dims["lineage"][1])
        self.assertEqual(record["overall"], "not qualified")

    def test_a_declared_output_that_does_not_exist_leaves_lineage_unestablished(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT + " analysis/a/outputs/missing.tsv"))
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        dims, _ = self.qual(digest)
        self.assertEqual(dims["lineage"][0], "not established")
        self.assertIn("missing.tsv", dims["lineage"][1])

    def test_outputs_none_makes_lineage_not_applicable(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs="none"))
        self.run_cmd("python " + FIT)
        dims, _ = self.qual(digest)
        self.assertEqual(dims["lineage"][0], "not applicable")

    def claim_plan(self, written_in_run):
        digest = self.approve(plan("run `{}`".format(FIT), outputs="analysis/a/outputs/de.tsv"))
        table = "gene\tlog2fc\nIL7R\t1.235\n"
        receipt = self.run_cmd("python " + FIT, writes={"analysis/a/outputs/de.tsv": table} if written_in_run else None)
        if not written_in_run:
            self.write("analysis/a/outputs/de.tsv", table, mtime=receipt["ts"] - 1)
        self.write("analysis/a/A.md", "# a\n\n<!--\nclaims\n- 1.235 | outputs/de.tsv log2fc IL7R\n-->\n".replace("<!--\nclaims", "<!-- claims"))
        return digest

    def test_a_matched_claim_cell_with_an_unresolved_producer_shows_both_facts(self):
        digest = self.claim_plan(written_in_run=False)
        dims, record = self.qual(digest)
        reason = dims["claim linkage"][1]
        self.assertEqual(dims["claim linkage"][0], "not established")
        self.assertIn("matched", reason)
        self.assertIn("not supported", reason)
        self.assertIn("(candidate)", reason)  # a timing-only candidate is not an established producer
        self.assertEqual(dims["lineage"][0], "not established")
        out = self.verify("report", digest)
        self.assertIn("1 verified", out)  # the cell match itself is still reported

    def test_a_matched_claim_cell_with_a_supported_producer_is_linked(self):  # control
        digest = self.claim_plan(written_in_run=True)
        dims, record = self.qual(digest)
        self.assertEqual(dims["claim linkage"][0], "established", dims["claim linkage"])
        self.assertEqual(record["overall"], "qualified")

    def test_a_metadata_only_pin_is_not_counted_as_strong(self):
        self.write("data/in.tsv", "a\n", mtime=time.time() - 3600)
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT, inputs="data/in.tsv"))
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        dims, _ = self.qual(digest)
        self.established(dims, "code and input identity")  # control: a hashed pin
        path = gate.state_path(self.root, "approvals", digest + ".json")
        record = gate.read_json(path, {})
        record["pins"]["data/in.tsv"].pop("sha256")
        with open(path, "w") as handle:
            json.dump(record, handle)
        dims, overall = self.qual(digest)
        self.assertEqual(dims["code and input identity"][0], "not established")
        self.assertIn("metadata only", dims["code and input identity"][1])
        self.assertEqual(overall["overall"], "not qualified")

    def test_a_changed_input_is_not_established(self):
        self.write("data/in.tsv", "a\n", mtime=time.time() - 3600)
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT, inputs="data/in.tsv"))
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        self.write("data/in.tsv", "bb\n")
        dims, _ = self.qual(digest)
        self.assertEqual(dims["code and input identity"][0], "not established")

    def test_write_saves_an_honest_record_even_when_reportable_is_required(self):
        digest = self.approve(self.bound_plan())
        self.run_cmd("python " + FIT)
        err = self.verify("write", digest, "--analysis-dir", "analysis/a", "--require-reportable", fails=True)
        self.assertIn("required validation", err)
        self.assertTrue(os.path.isfile(os.path.join(self.root, "analysis/a/provenance/verify-{}.md".format(digest))))
        row, = json.loads(self.verify("status", "--json"))
        self.assertEqual(row["verified"], "CONFORMS_WITH_GAPS (complete)")
        self.assertEqual(row["reportable"], "not qualified")
        self.assertIn("| not qualified |", self.verify("status"))

    def test_status_reads_a_qualified_record_back(self):
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        self.verify("write", digest, "--analysis-dir", "analysis/a")
        row, = json.loads(self.verify("status", "--json"))
        self.assertEqual(row["reportable"], "qualified")

    # ---- stale --content

    def verified_output(self, name="fit.tsv", text="x\n"):
        rel = "analysis/a/outputs/" + name
        digest = self.approve(plan("run `{}`".format(FIT), outputs=rel))
        self.run_cmd("python " + FIT, writes={rel: text})
        self.verify("write", digest, "--analysis-dir", "analysis/a")
        return digest, rel

    def mutate_in_place(self, rel, text):
        path = os.path.join(self.root, rel)
        info = os.stat(path)
        with open(path, "w") as handle:
            handle.write(text)
        os.utime(path, (info.st_atime, info.st_mtime))

    def test_content_checking_catches_a_same_size_same_mtime_mutation(self):
        digest, rel = self.verified_output()
        self.mutate_in_place(rel, "y\n")
        out = self.verify("stale")
        self.assertTrue(out.startswith("0 of 1 verified plans stale"), out)  # metadata cannot see it
        self.assertIn("metadata checked", out)
        content = self.verify("stale", "--content")
        self.assertIn("output `{}` content differs from the SHA256 verify saved".format(rel), content)
        self.assertTrue(content.strip().endswith("1 of 1 verified plans stale."), content)
        data = json.loads(self.verify("stale", "--content", "--json"))
        self.assertEqual(data["mode"], "content")
        self.assertEqual(data["stale"][0]["content_checked"], 1)

    def test_an_unchanged_output_passes_content_checking(self):  # control
        digest, rel = self.verified_output()
        out = self.verify("stale", "--content")
        self.assertTrue(out.startswith("0 of 1 verified plans stale"), out)
        self.assertIn("content checked", out)
        self.assertNotIn("content not checked", out)

    def test_default_stale_is_labelled_metadata_checked(self):
        digest, rel = self.verified_output()
        self.assertEqual(json.loads(self.verify("stale", "--json"))["mode"], "metadata")
        self.assertIn("metadata checked", self.verify("stale"))

    def test_an_exhausted_budget_says_content_not_checked(self):
        digest, rel = self.verified_output()
        self.mutate_in_place(rel, "y\n")
        out = self.verify("stale", "--content", "--hash-mb", "0")
        self.assertIn("content not checked", out)
        self.assertNotIn("content differs", out)
        self.assertNotIn("content checked for", out)

    def test_a_notebook_output_is_identified_by_its_raw_bytes(self):
        def notebook(value):
            return json.dumps({"cells": [{"cell_type": "code", "source": ["print(1)"], "metadata": {}, "execution_count": 1,
                                          "outputs": [{"output_type": "stream", "name": "stdout", "text": [value]}]}],
                               "metadata": {}, "nbformat": 4, "nbformat_minor": 5})
        digest, rel = self.verified_output("nb.ipynb", notebook("AAAA"))
        out = self.verify("stale")  # the code cells' length is not the file's size: this was "rewritten" before
        self.assertTrue(out.startswith("0 of 1 verified plans stale"), out)
        self.mutate_in_place(rel, notebook("BBBB"))  # same code cells, same size, same mtime, different result
        self.assertIn("1 of 1 verified plans stale", self.verify("stale", "--content"))

    # ---- claim coverage

    def claim_doc(self, block, prose=""):
        digest = self.approve(plan("run `{}`".format(FIT),
                                   outputs="analysis/a/outputs/de.tsv analysis/a/outputs/numbers.json"))
        self.run_cmd("python " + FIT, writes={
            "analysis/a/outputs/de.tsv": "gene\tlog2fc\nIL7R\t1.23456\n",
            "analysis/a/outputs/numbers.json": '{"qc": {"n": 48}}'})
        self.write("analysis/a/A.md", "# a\n\n## Key Findings\n\n{}\n<!-- claims\n{}\n-->\n".format(prose, block))
        return digest

    def test_claim_coverage_counts_and_the_registered_value_caveat(self):
        digest = self.claim_doc("- 1.235 | outputs/de.tsv log2fc IL7R\n- 9 | outputs/de.tsv log2fc IL7R\n"
                                "- 48 | outputs/numbers.json qc.n\n- 7 | outputs/missing.tsv x\nnot a claim line",
                                prose="IL7R rose by 1.235 in 48 donors, n = 12.")
        doc, = json.loads(self.verify("report", digest, "--json"))["claims"]
        self.assertEqual(doc["coverage"], {"blocks": 1, "claim_lines": 5, "unparsed_lines": 1, "cells_checked": 3,
                                           "matched": 2, "mismatched": 1, "unverified": 1, "registered": 1,
                                           "prose_numbers_listed": 1})
        out = self.verify("report", digest)
        self.assertIn("Coverage: 1 block(s), 5 claim line(s) (1 unparsed); 3 cell(s) checked, 2 matched, 1 mismatched, "
                      "1 unverified; 1 prose number(s) listed, not checked", out)
        self.assertIn("registered `numbers.json` value", out)
        self.assertIn("not which run wrote it", out)
        self.assertIn("**info**: 1 claim(s) cite a registered", out)

    def test_no_registered_value_means_no_caveat(self):  # control
        digest = self.claim_doc("- 1.235 | outputs/de.tsv log2fc IL7R")
        self.assertNotIn("registered", self.verify("report", digest))

    # ---- prose Validation cells (F06 residual)

    def test_prose_validation_cells_are_counted_as_info(self):
        digest = self.approve(plan("run `{}`".format(FIT), "run `{}`".format(FIT), outputs=self.OUT))
        out = self.verify("report", digest)
        self.assertIn("**info**: 2 Validation cells are prose only; nothing checks them", out)
        self.assertNotIn("**gap**: 2 Validation", out)

    def test_a_validation_binding_covers_its_row(self):  # control
        digest = self.approve(self.bound_plan())  # row 2 is bound, row 1 is not
        out = self.verify("report", digest)
        self.assertIn("**info**: 1 Validation cell is prose only; nothing checks it", out)

    def test_empty_validation_cells_are_not_prose(self):  # control
        text = plan("run `{}`".format(FIT), outputs=self.OUT).replace("| user | ok |", "| user | - |")
        out = self.verify("report", self.approve(text))
        self.assertNotIn("prose only", out)

    # ---- rerun evidence

    RUN = "analysis/a/run.sh"

    def entry_plan(self):
        self.write(self.RUN, "echo hi\n", mtime=time.time() - 3600)
        digest = self.approve(plan("run `{}`".format(self.RUN), outputs=self.OUT))
        self.run_cmd("bash " + self.RUN, writes={self.OUT: "x\n"})
        return digest

    def rerun_of(self, digest):
        return json.loads(self.verify("report", digest, "--json"))["rerun"]

    def test_an_entry_point_that_was_declared_but_not_rerun(self):
        digest = self.entry_plan()
        entry, = self.rerun_of(digest)
        self.assertEqual((entry["path"], entry["state"]), (self.RUN, "declared"))
        self.assertIn("entry point declared", self.verify("report", digest))

    def test_a_plan_with_no_entry_point_has_no_rerun_section(self):  # control
        digest = self.approve(plan("run `{}`".format(FIT), outputs=self.OUT))
        self.run_cmd("python " + FIT, writes={self.OUT: "x\n"})
        self.assertEqual(self.rerun_of(digest), [])
        self.assertNotIn("## Rerun", self.verify("report", digest))

    def saved_then_rerun(self, text):
        digest = self.entry_plan()
        self.verify("write", digest, "--analysis-dir", "analysis/a")
        time.sleep(1.1)
        self.run_cmd("bash " + self.RUN, writes={self.OUT: text})
        return digest

    def test_a_rerun_with_different_content_is_attempted_not_reproduced(self):
        entry, = self.rerun_of(self.saved_then_rerun("different\n"))
        self.assertEqual(entry["state"], "rerun attempted")
        self.assertIn(self.OUT, entry["reason"])

    def test_a_rerun_with_equal_content_reproduced_the_saved_artifacts(self):
        digest = self.saved_then_rerun("x\n")
        entry, = self.rerun_of(digest)
        self.assertEqual(entry["state"], "rerun reproduced specified artifacts")
        self.assertIn("rerun reproduced specified artifacts", self.verify("report", digest))

    def test_a_rerun_before_any_saved_record_cannot_be_compared(self):
        digest = self.entry_plan()
        self.run_cmd("bash " + self.RUN, writes={self.OUT: "x\n"})
        entry, = self.rerun_of(digest)
        self.assertEqual(entry["state"], "declared")
        self.assertIn("no saved", entry["reason"])


if __name__ == "__main__":
    unittest.main()
