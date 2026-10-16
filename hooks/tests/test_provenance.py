"""Fault injection checks both saved bytes and independently computed completion hashes."""

import hashlib
import json
import multiprocessing
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import provenance as p


def build(folder, digest, text):
    names = ["{}-{}.{}".format(prefix, digest, ext) for prefix, ext in
             (("plan", "md"), ("receipts", "jsonl"), ("outputs", "tsv"),
              ("verify", "md"), ("lint", "txt"))]
    for name in names:
        p.atomic(os.path.join(folder, name), text)
    index = os.path.join(folder, "PROVENANCE.md")
    previous = ""
    if os.path.exists(index):
        with open(index) as handle:
            previous = "".join(line for line in handle if not line.startswith("| " + digest + " |"))
    p.atomic(index, previous + "| {} | {} |\n".format(digest, text))
    return names + ["PROVENANCE.md"]


def publish(folder, digest, text):
    p.publish(folder, digest, lambda stage: build(stage, digest, text))


class ProvenanceTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder)

    def verify_bytes(self, digest, text):
        self.assertEqual(p.bundle_state(self.folder, digest), "complete")
        value = p.load(os.path.join(self.folder, "complete-" + digest + ".json"))
        for name, expected in value["sha256"].items():
            with open(os.path.join(self.folder, name), "rb") as handle:
                data = handle.read()
            self.assertEqual(data, text.encode())
            self.assertEqual(hashlib.sha256(data).hexdigest(), expected)

    def test_interrupt_every_publication_stage(self):
        stages = ["staged", "pending", "lint-aaaaaaaa.txt", "outputs-aaaaaaaa.tsv",
                  "plan-aaaaaaaa.md", "receipts-aaaaaaaa.jsonl", "verify-aaaaaaaa.md",
                  "complete-aaaaaaaa.json", "PROVENANCE.md", "done"]
        for stage in stages:
            publish(self.folder, "aaaaaaaa", "old")
            def fault(at):
                if at == stage:
                    raise RuntimeError("interruption")
            with self.assertRaises(RuntimeError):
                p.publish(self.folder, "aaaaaaaa", lambda f: build(f, "aaaaaaaa", "new"), fault)
            expected = "new" if stage in ("PROVENANCE.md", "done") else "old"
            if stage not in ("staged", "done"):
                self.assertEqual(p.bundle_state(self.folder, "aaaaaaaa"), "interrupted")
            with p.locked(os.path.join(self.folder, ".publish.lock")):
                p.recover(self.folder)
                p.recover(self.folder)
            self.verify_bytes("aaaaaaaa", expected)

    def test_first_save_interruption_restores_absence(self):
        def fail(stage):
            if stage == "receipts-aaaaaaaa.jsonl":
                raise RuntimeError()
        with self.assertRaises(RuntimeError):
            p.publish(self.folder, "aaaaaaaa", lambda f: build(f, "aaaaaaaa", "new"), fail)
        p.recover(self.folder)
        self.assertFalse(os.path.exists(os.path.join(self.folder, "receipts-aaaaaaaa.jsonl")))

    def test_legacy_preserved_and_ambiguous_damage_retained(self):
        build(self.folder, "aaaaaaaa", "legacy")
        self.assertEqual(p.bundle_state(self.folder, "aaaaaaaa"), "legacy")
        def fail(stage):
            if stage == "pending":
                raise RuntimeError()
        with self.assertRaises(RuntimeError):
            p.publish(self.folder, "aaaaaaaa", lambda f: build(f, "aaaaaaaa", "new"), fail)
        p.atomic(os.path.join(self.folder, "plan-aaaaaaaa.md"), "external edit")
        with self.assertRaisesRegex(ValueError, "recovery gap"):
            p.recover(self.folder)
        self.assertTrue(os.path.exists(os.path.join(self.folder, ".transactions", "pending.json")))
        self.assertEqual(p.bundle_state(self.folder, "aaaaaaaa"), "interrupted")

    def test_competing_same_and_different_plan_writers(self):
        jobs = [multiprocessing.get_context("fork").Process(target=publish, args=(self.folder, digest, text))
                for digest, text in (("aaaaaaaa", "one"), ("bbbbbbbb", "two"),
                                     ("aaaaaaaa", "three"), ("cccccccc", "four"))]
        for job in jobs:
            job.start()
        for job in jobs:
            job.join(10)
            self.assertEqual(job.exitcode, 0)
        for digest in ("aaaaaaaa", "bbbbbbbb", "cccccccc"):
            self.assertEqual(p.bundle_state(self.folder, digest), "complete")
        with open(os.path.join(self.folder, "PROVENANCE.md")) as handle:
            lines = handle.readlines()
        self.assertEqual(len(lines), 3)

    def test_corrupt_completion_or_member_is_never_complete(self):
        publish(self.folder, "aaaaaaaa", "old")
        p.atomic(os.path.join(self.folder, "plan-aaaaaaaa.md"), "changed")
        self.assertEqual(p.bundle_state(self.folder, "aaaaaaaa"), "interrupted")
        p.atomic(os.path.join(self.folder, "complete-aaaaaaaa.json"), "[]")
        self.assertEqual(p.bundle_state(self.folder, "aaaaaaaa"), "interrupted")


if __name__ == "__main__":
    unittest.main()
