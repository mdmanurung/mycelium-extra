"""Run: python3.11 skills/verify/tests/test_crate.py

The crate is built from a real bundle: approvals and receipts come from the real gate hooks and the
bundle from `verify write`, so the tests follow the formats the gate and verify write.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import test_verify as tv  # noqa: E402

PLUGIN = tv.PLUGIN
sys.path.insert(0, os.path.join(PLUGIN, "skills", "verify", "scripts"))
import crate  # noqa: E402

FIT, OUT, ORPHAN, DATA = tv.FIT, "analysis/a/outputs/fit.tsv", "analysis/a/outputs/orphan.tsv", "analysis/a/data/in.tsv"
CRATE_DIR = "analysis/a/provenance/crate-{}"


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


class CrateTest(unittest.TestCase):
    # the real fixtures' helpers, borrowed so the bundle is made the way verify makes it
    for _name in ("setUp", "tearDown", "write", "fake_sacct", "fake_tool", "hook", "approve", "run_cmd",
                  "post_only", "verify"):
        locals()[_name] = getattr(tv.VerifyTest, _name)

    def bundle(self):
        self.write(DATA, "id\tx\n1\t2\n", mtime=time.time() - 7200)
        digest = self.approve(tv.plan("run `{}`".format(FIT), outputs="analysis/a/outputs/", inputs="`{}`".format(DATA)))
        receipt = self.run_cmd("python " + FIT, writes={OUT: "x\n"})
        self.write(ORPHAN, "y\n", mtime=receipt["ts"] - 1)  # written by something the gate did not observe
        self.verify("write", digest, "--analysis-dir", "analysis/a")
        return digest

    def crate_path(self, digest):
        return os.path.join(self.root, CRATE_DIR.format(digest), "ro-crate-metadata.json")

    def make(self, digest):
        out = self.verify("crate", digest, "--analysis-dir", "analysis/a")
        self.assertIn("wrote " + CRATE_DIR.format(digest) + "/ro-crate-metadata.json", out)
        with open(self.crate_path(digest)) as handle:
            return json.load(handle)

    def entities(self, doc):
        return {e["@id"]: e for e in doc["@graph"]}

    def file_of(self, digest, entity_id):
        return os.path.normpath(os.path.join(self.root, CRATE_DIR.format(digest), urllib.parse.unquote(entity_id)))

    def test_structure_context_root_and_every_reference_resolves(self):
        digest = self.bundle()
        doc = self.make(digest)
        self.assertEqual(doc["@context"][:2], [crate.CRATE_CONTEXT, crate.WFRUN_CONTEXT])
        ents = self.entities(doc)
        descriptor, root = ents["ro-crate-metadata.json"], ents["./"]
        self.assertEqual(descriptor["about"], {"@id": "./"})
        self.assertEqual(descriptor["conformsTo"], {"@id": "https://w3id.org/ro/crate/1.3"})
        self.assertEqual(root["conformsTo"], {"@id": "https://w3id.org/ro/wfrun/process/0.6"})
        self.assertRegex(root["datePublished"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertTrue(root["name"] and root["description"])

        def refs(value):
            if isinstance(value, dict):
                if set(value) == {"@id"}:
                    yield value["@id"]
                else:
                    for v in value.values():
                        yield from refs(v)
            elif isinstance(value, list):
                for v in value:
                    yield from refs(v)

        for entity in doc["@graph"]:
            for ref in refs({k: v for k, v in entity.items() if k != "@id"}):
                self.assertIn(ref, ents, "{} points at {}, which is not an entity".format(entity["@id"], ref))
        self.assertEqual(len(ents), len(doc["@graph"]), "an @id is used twice")

    def test_actions_link_script_inputs_and_supported_outputs(self):
        digest = self.bundle()
        doc = self.make(digest)
        ents = self.entities(doc)
        actions = [e for e in doc["@graph"] if e["@type"] == "CreateAction"]
        action, = actions
        script = ents[action["instrument"]["@id"]]
        self.assertEqual(script["mx:repositoryPath"], FIT)
        self.assertEqual(script["sha256"], sha(os.path.join(self.root, FIT)))
        self.assertEqual([ents[o["@id"]]["mx:repositoryPath"] for o in action["object"]], [DATA])
        self.assertEqual([ents[o["@id"]]["mx:repositoryPath"] for o in action["result"]], [OUT])
        self.assertEqual(action["actionStatus"], "http://schema.org/CompletedActionStatus")
        self.assertNotIn("command", json.dumps(action))

    def test_recorded_hashes_match_the_files_on_disk(self):
        digest = self.bundle()
        doc = self.make(digest)
        checked = 0
        for entity in doc["@graph"]:
            if "sha256" in entity and entity["@id"] not in (crate.CRATE_SPEC,):
                path = self.file_of(digest, entity["@id"])
                self.assertTrue(os.path.isfile(path), path)
                self.assertEqual(entity["sha256"], sha(path), entity["@id"])
                checked += 1
        self.assertGreaterEqual(checked, 4)  # script, input, output, plan or receipts

    def test_an_unresolved_producer_stays_as_an_explicit_gap(self):
        digest = self.bundle()
        doc = self.make(digest)
        ents = self.entities(doc)
        orphan = next(e for e in ents.values() if e.get("mx:repositoryPath") == ORPHAN)
        self.assertIn(orphan["mx:producerAttribution"], ("unresolved", "candidate"))
        self.assertTrue(orphan["mx:producerGap"])
        self.assertIn({"@id": orphan["@id"]}, ents["./"]["hasPart"])  # kept, not dropped
        self.assertNotIn(orphan["@id"], [r["@id"] for a in doc["@graph"] if a["@type"] == "CreateAction"
                                         for r in a.get("result", [])])
        self.assertTrue(any("no established producer" in g for g in ents["./"]["mx:gaps"]))

    def test_output_is_deterministic(self):
        digest = self.bundle()
        self.make(digest)
        with open(self.crate_path(digest), "rb") as handle:
            first = handle.read()
        self.make(digest)
        with open(self.crate_path(digest), "rb") as handle:
            self.assertEqual(first, handle.read())
        built = crate.render(crate.build(self.root, os.path.join(self.root, "analysis/a/provenance"), digest,
                                         json.loads(first)["@graph"][1]["mx:generatedBy"] and
                                         self.entities(json.loads(first))["#mycelium-extra"]["softwareVersion"]))
        self.assertEqual(built.encode(), first)
        self.assertEqual(json.loads(first), json.loads(built))

    def test_needs_the_folder_and_a_complete_bundle(self):
        digest = self.bundle()
        self.assertIn("--analysis-dir", self.verify("crate", digest, fails=True))
        shutil.rmtree(os.path.join(self.root, "analysis/a/provenance"))
        self.assertIn("run `verify write", self.verify("crate", digest, "--analysis-dir", "analysis/a", fails=True))

    def test_confirm_writes_needs_consent_like_write(self):
        digest = self.bundle()
        self.write(".mycelium-extra/gate.json", json.dumps({"confirm_writes": True}))
        self.assertIn("confirmation", self.verify("crate", digest, "--analysis-dir", "analysis/a", fails=True))
        self.assertFalse(os.path.exists(self.crate_path(digest)))

    def test_official_validator_when_installed(self):
        import importlib.util
        if importlib.util.find_spec("rocrate_validator") is None and shutil.which("rocrate-validator") is None:
            self.skipTest("rocrate-validator is not installed; only the structural checks above ran")
        digest = self.bundle()
        self.make(digest)
        exe = shutil.which("rocrate-validator") or "rocrate-validator"
        proc = subprocess.run([exe, "validate", os.path.dirname(self.crate_path(digest)), "-p", "process-run-crate"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


class SyntheticBundleTest(unittest.TestCase):
    """crate.build on a hand-made bundle, to reach branches the real gate fixtures do not."""

    D = "a" * 16

    def make(self, outputs, receipts, approval):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        folder = os.path.join(root, "analysis", "a", "provenance")
        os.makedirs(folder)
        header = "path\twritten\tsize\tsha256\tfingerprint\tproducer_attempt\twritten_by\tevidence_method\tstrength\tapproval_instance\n"
        with open(os.path.join(folder, "outputs-{}.tsv".format(self.D)), "w") as handle:
            handle.write(header + "".join("\t".join(r) + "\n" for r in outputs))
        with open(os.path.join(folder, "receipts-{}.jsonl".format(self.D)), "w") as handle:
            handle.write("".join(json.dumps(r) + "\n" for r in receipts))
        row = "| {} | 2026-01-01 10:00 | 2026-01-02 10:00 |".format(self.D)
        with open(os.path.join(folder, "complete-{}.json".format(self.D)), "w") as handle:
            json.dump({"index_row": row, "sha256": {}}, handle)
        if approval is not None:
            os.makedirs(os.path.join(root, ".mycelium-extra", "approvals"))
            with open(os.path.join(root, ".mycelium-extra", "approvals", self.D + ".json"), "w") as handle:
                json.dump(approval, handle)
        return crate.build(root, folder, self.D)

    def receipt(self, **extra):
        base = {"plans": [self.D], "launch_match": "matched", "paths": ["code/fit.py"], "attempt_id": "att1",
                "started": 1000, "ts": 1010, "exit_status": 0}
        base.update(extra)
        return base

    def out(self, path, strength="supported", sha="", fingerprint="size and time only"):
        return [path, "2026-01-01", "5", sha, fingerprint, "att1", "code/fit.py", "mtime", strength, ""]

    SCRIPT = {"code/fit.py": {"sha256": "b" * 64, "size": 3}}

    def ents(self, doc):
        return {e["@id"]: e for e in doc["@graph"]}

    def test_failed_run_has_failed_status_and_exit_code(self):
        doc = self.make([self.out("out/x.tsv")], [self.receipt(exit_status=2)], {"scripts": self.SCRIPT})
        action, = [e for e in doc["@graph"] if e["@type"] == "CreateAction"]
        self.assertEqual(action["actionStatus"], "http://schema.org/FailedActionStatus")
        self.assertEqual(action["mx:exitStatus"], 2)

    def test_no_pinned_inputs_gives_an_action_without_objects(self):
        doc = self.make([self.out("out/x.tsv")], [self.receipt()], {"scripts": self.SCRIPT})
        action, = [e for e in doc["@graph"] if e["@type"] == "CreateAction"]
        self.assertEqual(action["object"], [])

    def test_folder_input_is_a_dataset_with_a_trailing_slash(self):
        pins = {"data/raw": {"folder": True, "listing_sha256": "c" * 64, "files": 3}}
        doc = self.make([self.out("out/x.tsv")], [self.receipt()], {"scripts": self.SCRIPT, "pins": pins})
        folder, = [e for e in doc["@graph"] if e.get("mx:repositoryPath") == "data/raw"]
        self.assertEqual(folder["@type"], "Dataset")
        self.assertTrue(folder["@id"].endswith("/"))
        self.assertEqual(folder["mx:fingerprint"], "folder listing")
        self.assertEqual(folder["mx:listingSha256"], "c" * 64)

    def test_candidate_output_is_a_gap_not_a_result(self):
        doc = self.make([self.out("out/x.tsv", strength="candidate")], [self.receipt()], {"scripts": self.SCRIPT})
        entity, = [e for e in doc["@graph"] if e.get("mx:repositoryPath") == "out/x.tsv"]
        self.assertEqual(entity["mx:producerAttribution"], "candidate")
        self.assertIn("candidate", entity["mx:producerGap"])
        action, = [e for e in doc["@graph"] if e["@type"] == "CreateAction"]
        self.assertNotIn("result", action)

    def test_output_without_hash_carries_a_fingerprint_note_not_sha256(self):
        doc = self.make([self.out("out/x.tsv")], [self.receipt()], {"scripts": self.SCRIPT})
        entity, = [e for e in doc["@graph"] if e.get("mx:repositoryPath") == "out/x.tsv"]
        self.assertNotIn("sha256", entity)
        self.assertEqual(entity["mx:fingerprint"], "size and time only")

    def test_missing_approval_record_is_named_as_a_gap(self):
        doc = self.make([self.out("out/x.tsv")], [self.receipt()], None)
        gaps = self.ents(doc)["./"]["mx:gaps"]
        self.assertTrue(any("No approval record was found" in g for g in gaps))
        self.assertTrue(any("no run action" in g for g in gaps))
        self.assertFalse([e for e in doc["@graph"] if e["@type"] == "CreateAction"])


if __name__ == "__main__":
    unittest.main()
