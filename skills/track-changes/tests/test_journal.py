"""Historical acceptance fixture, collected by the existing CI skill-test glob."""
import copy
import importlib.util
import glob
import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_track_changes import Base, PLUGIN, FIT, tc
from journal_fixture import history
sys.path.insert(0, os.path.join(PLUGIN, "skills", "track-changes", "scripts"))
tc.load(PLUGIN)
import journal
import evidence
import provenance

spec = importlib.util.spec_from_file_location("consumer", os.path.join(PLUGIN, "examples", "read_evidence.py"))
consumer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(consumer)


def save_child(root, value):
    journal.save(root, value)


class JournalTest(Base):
    def setUp(self):
        super().setUp()
        self.gate, self.focus, self.verify = tc.load(PLUGIN)

    def collect_journal(self, notes=()):
        return journal.collect(self.root, "analysis/a", self.gate, self.focus, notes)

    def saved_verification(self, h, fault=lambda stage: None):
        self.verify.PLUGIN_ROOT = PLUGIN
        result = self.verify.check(self.root, h, "analysis/a", sacct="/nonexistent/sacct",
                                   scilintr="/nonexistent/scilintr", rscript="/nonexistent/Rscript")
        result["qualification"] = self.verify.qualify(self.root, result)
        self.verify.PLUGIN_ROOT = PLUGIN
        folder = os.path.join(self.root, "analysis/a/provenance")
        provenance.publish(folder, h, lambda stage: self.verify._write_bundle(self.root, result, stage), fault)
        return result, consumer.read(folder, h)

    def test_multisession_history_no_cap_instances_retries_and_conflicts(self):
        first, second, third = history(self)
        for h in (first, third):
            self.saved_verification(h)
        data = self.collect_journal()
        self.assertEqual({e["references"].get("plan") for e in data["events"] if e["kind"] == "approval"}, {first, second, third})
        self.assertEqual(len([e for e in data["events"] if e["kind"] == "instance" and e["references"]["plan"] == first]), 2)
        attempts = [e for e in data["events"] if e["kind"] == "attempt"]
        self.assertEqual(len(attempts), 51)
        self.assertTrue(any(e["summary"] == "failed attempt" for e in attempts))
        self.assertTrue(any(e["summary"] == "exit 0 recorded" for e in attempts))
        self.assertEqual(len([e for e in data["events"] if e["kind"] == "verification"]), 2)
        submit = [e for e in attempts if e["detail"]["submission"]][0]
        self.assertIn("completion not recorded", submit["summary"])
        self.assertEqual(len([e for e in data["events"] if e["kind"] == "focus"]), 2)
        receipts = self.gate.read_receipts(self.root)
        changed = dict(receipts[0], exit_status=99)
        saved = "analysis/a/provenance/receipts-" + first + ".jsonl"
        with open(os.path.join(self.root, saved), "a") as out:
            out.write(json.dumps(changed) + "\n{damaged\n")
        newer = self.collect_journal()
        variants = [e for e in newer["events"] if e["references"].get("attempt") == changed["attempt_id"]]
        self.assertEqual(len(variants), 2)
        self.assertTrue(all(any("Conflicting" in l for l in e["limitations"]) for e in variants))
        self.assertIn(newer["coverage"]["handoffs"], ("partial", "interrupted"))
        self.assertEqual(newer["coverage"]["saved_receipts"], "partial")

    def test_portable_checkpoint_survives_replacement_state_removal_and_relocation(self):
        first, _, third = history(self, count=2)
        _, old = self.saved_verification(first)
        data = self.collect_journal(["notes/interpretation.md#research"])
        first_save = journal.save(self.root, data)
        same = journal.save(self.root, self.collect_journal())
        self.assertEqual(first_save["digest"], same["digest"])
        self.assertEqual(first_save["saved_at"], same["saved_at"])
        self.saved_verification(third)
        self.run_cmd("python " + FIT, code=2)
        self.saved_verification(first)
        shutil.rmtree(os.path.join(self.root, ".mycelium-extra"))
        relocated = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, relocated)
        if not shutil.which("git"):
            self.skipTest("git required for literal fresh-clone acceptance")
        def git(*args, cwd=self.root):
            return subprocess.run(["git"] + list(args), cwd=cwd, check=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        git("init", "-q")
        git("add", "analysis")
        git("-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "-qm", "Synthetic journal history")
        git("clone", "--no-hardlinks", self.root, relocated)
        moved = journal.collect(relocated, "analysis/a", self.gate, self.focus)
        snapshots = [e["detail"]["projection"]["snapshot_digest"] for e in moved["events"] if e["kind"] == "verification"]
        self.assertIn(old["snapshot_digest"], snapshots)
        self.assertEqual(moved["coverage"]["approvals"], "absent")
        self.assertTrue(any("unavailable" in e["original_evidence"] for e in moved["events"]))
        self.assertEqual(moved["note_observations"][0]["current_status"], "absent")
        self.assertTrue({e["id"] for e in first_save["payload"]["events"]}.issubset({e["id"] for e in moved["events"]}))
        self.assertFalse(any("payload" in e for e in moved["events"]))
        rendered = json.loads(self.cli("--journal", "--analysis", "analysis/a", "--no-write", "--json", repo=relocated))
        self.assertEqual({e["id"] for e in moved["events"]}, {e["id"] for e in rendered["events"]})
        self.assertFalse(os.path.exists(os.path.join(relocated, ".mycelium-extra")))

    def test_concurrent_saves_interruption_and_no_recursive_growth(self):
        history(self, count=1)
        data = self.collect_journal()
        context = multiprocessing.get_context("fork")
        jobs = [context.Process(target=save_child, args=(self.root, data)) for _ in range(4)]
        for job in jobs: job.start()
        for job in jobs:
            job.join(8)
            self.assertEqual(job.exitcode, 0)
        saved = journal.save(self.root, data)
        again = self.collect_journal()
        self.assertEqual(saved["digest"], journal.save(self.root, again)["digest"])
        self.assertEqual(len(again["checkpoints"]), 1)
        modified = copy.deepcopy(data)
        modified["objective"]["text"] = "Correction"
        with self.assertRaises(RuntimeError):
            journal.save(self.root, modified, lambda stage: (_ for _ in ()).throw(RuntimeError("interruption")))
        self.assertEqual(len(self.collect_journal()["checkpoints"]), 1)
        journal.save(self.root, modified)
        self.assertEqual(len(self.collect_journal()["checkpoints"]), 2)
        path = "analysis/a/journal/checkpoints/" + saved["digest"] + ".json"
        with open(os.path.join(self.root, path)) as handle: value = json.load(handle)
        value["payload"]["objective"]["text"] = "tampered"
        self.write(path, json.dumps(value))
        self.assertEqual(self.collect_journal()["coverage"]["checkpoints"], "partial")

    def test_no_write_flags_notes_hostile_content_and_unknown_time(self):
        history(self, count=1)
        notes = "# Note\n<script>alert(1)</script> `$(touch stolen)`\n"
        self.write("notes/interpretation.md", notes)
        before = self.tree()
        out = json.loads(self.cli("--journal", "--analysis", "analysis/a", "--no-write", "--json", "--note", "notes/interpretation.md#anchor"))
        self.assertEqual(out["schema"], journal.SCHEMA)
        self.assertEqual(before, self.tree())
        with open(os.path.join(self.root, "notes/interpretation.md")) as handle: self.assertEqual(handle.read(), notes)
        for flags in (("--save-checkpoint",), ("--journal", "--save-checkpoint", "--no-write"),
                      ("--journal", "--save-checkpoint", "--explain", "x"), ("--note", "notes/x.md")):
            self.cli(*flags, fail=True)
            self.assertEqual(before, self.tree())
        for ref in ("../outside.md", "/tmp/a.md", "https://bad/a.md", "javascript:bad.md", "notes/../../x.md"):
            self.cli("--journal", "--analysis", "analysis/a", "--no-write", "--note", ref, fail=True)
        legacy = dict(self.gate.read_receipts(self.root)[0])
        for k in ("attempt_id", "ts", "started"): legacy.pop(k, None)
        with open(os.path.join(self.root, ".mycelium-extra/receipts.jsonl"), "a") as handle:
            handle.write(json.dumps(legacy) + "\n")
        event = [e for e in self.collect_journal()["events"] if e["kind"] == "attempt" and e["occurred_at"] is None][0]
        self.assertIsNone(event["observed_at"])
        self.assertEqual(event["id"], [e for e in self.collect_journal()["events"] if e["occurred_at"] is None][0]["id"])

    def test_manifest_parity_allowlist_identity_and_publication_failure(self):
        h, _, _ = history(self, count=1)
        result, handoff = self.saved_verification(h)
        self.assertEqual(handoff["conformity"], result["status"])
        self.assertEqual(handoff["qualification"], result["qualification"])
        folder = os.path.join(self.root, "analysis/a/provenance")
        for stage in ("pending", "evidence-" + h + ".json", "complete-" + h + ".json"):
            def fault(at):
                if at == stage: raise RuntimeError("injected")
            with self.assertRaises(RuntimeError): self.saved_verification(h, fault)
            with self.assertRaises(ValueError): consumer.read(folder, h)
            with provenance.locked(os.path.join(folder, ".publish.lock")): provenance.recover(folder)
            consumer.read(folder, h)
        legacy = copy.deepcopy(result)
        legacy["instance"] = None
        legacy["qualification"] = None
        legacy["outputs"] = [{"path": "analysis/a/out.tsv", "record": {"size": 3, "mtime": 7},
                              "producer_attempt": None, "evidence_method": "timing-only", "strength": "candidate"}]
        legacy["receipts"] = [{"command": "python secret.py --password TOPSECRET", "command_env": {"TOKEN": "PRIVATE_VALUE"}}]
        legacy["findings"] = [["gap", "python secret.py --password TOPSECRET PRIVATE_VALUE /home/private/out"],
                               ["gap", "Other instance ran `custom-program --private PRIVATE_ARG`"]]
        projected = evidence.project(legacy, generated_at="one")
        self.assertIsNone(projected["approval_instance"])
        self.assertIsNone(projected["qualification"])
        self.assertNotIn("sha256", projected["outputs"][0]["fingerprint"])
        self.assertEqual(projected["outputs"][0]["strength"], "candidate")
        self.assertNotIn("TOPSECRET", json.dumps(projected))
        self.assertNotIn("PRIVATE_VALUE", json.dumps(projected))
        self.assertNotIn("PRIVATE_ARG", json.dumps(projected))
        self.assertEqual(projected["snapshot_digest"], evidence.project(legacy, version="different", generated_at="two")["snapshot_digest"])

    def test_offline_journal_hierarchy_navigation_and_search(self):
        node = shutil.which("node")
        if not node:
            if os.environ.get("MX_REQUIRE_NODE"):
                self.fail("Node required for Journal acceptance")
            self.skipTest("Node not installed; real browser checks remain separate")
        first, _, _ = history(self, count=47)
        self.cli("--journal", "--analysis", "analysis/a", "--original", first)
        html = os.path.join(self.root, ".mycelium-extra/track-changes/analysis__a/report.html")
        result = subprocess.run([node, os.path.join(PLUGIN, "skills/track-changes/tests/viewer_smoke.js"), html],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK journal", result.stdout)

    def test_shared_paths_are_not_ownership_and_malformed_sources_are_visible(self):
        history(self, count=1)
        self.write("analysis/b/helper.py", "print('synthetic')\n")
        from test_track_changes import plan
        h = self.approve(plan("joint", "run `analysis/b/helper.py`", outputs="none"))
        self.run_cmd("python " + FIT)
        data = self.collect_journal()
        event = [e for e in data["events"] if e["kind"] == "approval" and e["references"]["plan"] == h][0]
        self.assertEqual(event["attribution"], "multi-analysis")

        before = self.collect_journal()
        unrelated = dict(self.gate.read_receipts(self.root)[0], plans=[], attempt_id="shared-only")
        unrelated.pop("focus_folder", None)
        unrelated.pop("focus_id", None)
        with open(os.path.join(self.root, ".mycelium-extra/receipts.jsonl"), "a") as handle:
            handle.write(json.dumps(unrelated) + "\n")
            handle.write(json.dumps(dict(unrelated, plans=[{}])) + "\n")
            handle.write('{"plans": [], "ts": NaN}\n')
        data = self.collect_journal()
        self.assertFalse(any(e["references"].get("attempt") == "shared-only" for e in data["events"]))
        self.assertEqual(len(data["events"]), len(before["events"]))
        self.assertEqual(data["coverage"]["receipts"], "partial")

    def test_notes_change_without_rewriting_bytes_and_checkpoint_retains_detection(self):
        history(self, count=1)
        data = self.collect_journal(["notes/interpretation.md#research"])
        old = journal.save(self.root, data)
        content = "# New researcher text\n<svg onload=alert(1)>\n"
        self.write("notes/interpretation.md", content)
        current = self.collect_journal()
        self.assertTrue(current["note_observations"][0]["changed"])
        updated = journal.save(self.root, current)
        self.assertNotEqual(old["digest"], updated["digest"])
        self.assertTrue(updated["payload"]["note_observations"][0]["changed"])
        with open(os.path.join(self.root, "notes/interpretation.md")) as handle:
            self.assertEqual(handle.read(), content)
        os.symlink("/tmp", os.path.join(self.root, "notes/escape"))
        with self.assertRaises(ValueError): journal.note(self.root, "notes/escape/unread.md")

    def test_supported_output_export_preserves_native_attribution_and_collector_runs_nothing(self):
        from test_track_changes import plan
        output = "analysis/a/outputs/result.tsv"
        h = self.approve(plan("synthetic", outputs=output))
        payload = {"tool_name": "Bash", "tool_input": {"command": "python " + FIT}, "tool_use_id": "observed-output"}
        self.hook("tool", payload)
        self.write(output, "value\n42\n")
        self.hook("post", dict(payload, tool_response={"stdout": "", "exit_code": 0}))
        result, exported = self.saved_verification(h)
        self.assertEqual(len(exported["outputs"]), 1)
        row, actual = result["outputs"][0], exported["outputs"][0]
        self.assertEqual(row["strength"], "supported")
        for key in ("path", "producer_attempt", "evidence_method", "strength", "explore"):
            self.assertEqual(actual[key], row[key], key)
        for key in ("size", "mtime", "sha256"):
            self.assertEqual(actual["fingerprint"][key], row["record"][key], key)
        with patch("subprocess.run", side_effect=AssertionError("collector launched an external process")):
            data = self.collect_journal()
        self.assertEqual(len([e for e in data["events"] if e["kind"] == "verification"]), 1)

    def test_native_outstanding_launch_without_focus_is_retained(self):
        from test_track_changes import plan
        h = self.approve(plan("launch", outputs="none"))
        self.hook("tool", {"tool_name": "Bash", "tool_input": {"command": "python " + FIT},
                           "tool_use_id": "no-post"})
        data = self.collect_journal()
        launches = [e for e in data["events"] if e["kind"] == "launch"]
        self.assertEqual(len(launches), 1)
        self.assertEqual(launches[0]["references"]["plan"], h)
        self.assertIn("without a completion", launches[0]["summary"])
        self.assertEqual(data["coverage"]["receipts"], "absent")

    def test_malformed_nested_fields_degrade_instead_of_crashing(self):
        from test_track_changes import plan
        h = self.approve(plan("nested", outputs="none"))
        self.hook("tool", {"tool_name": "Bash", "tool_input": {"command": "python " + FIT}, "tool_use_id": "bad-nested"})
        launch = glob.glob(os.path.join(self.root, ".mycelium-extra/launches/*.json"))[0]
        with open(launch) as handle:
            record = json.load(handle)
        for rows in record["runs"].values():
            for row in rows:
                row["plans"] = None
        with open(launch, "w") as handle:
            json.dump(record, handle)
        self.collect_journal()  # must not raise
        data = self.collect_journal()
        self.assertTrue(data["events"])
        cp = journal.save(self.root, data)
        bad = json.loads(json.dumps(cp))
        bad["payload"]["events"] = [dict(e, kind="verification", detail={"projection": {"findings": "gap"}}) for e in bad["payload"]["events"][:1]]
        with self.assertRaises(ValueError):
            journal.validate_checkpoint(bad, bad["payload"]["analysis_path"])
        self.assertFalse(journal.findings_ok({"findings": None}))
        self.assertTrue(journal.findings_ok({"findings": [["gap", "x"]]}))


if __name__ == "__main__": unittest.main()
