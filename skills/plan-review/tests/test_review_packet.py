"""Tests for the byte-bound review packet (roadmap C11): prepare, preview, verify.

The consent record is written by the approval gate after it observes the user type `send packet <digest>`.
These tests write that record directly to simulate the gate; no production path here or in review_packet.py does.

Run: python3 skills/plan-review/tests/test_review_packet.py
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(SKILL, "scripts", "review_packet.py")
PRESEND = os.path.join(SKILL, "scripts", "presend_check.py")
sys.dont_write_bytecode = True

TOKEN = "gh" + "p_" + "A1b2C3d4" * 5   # built from parts so no secret-shaped literal sits in the repository
EMAIL = "someone.private@example.org"
PACKET = 'objective: "Test the day 28 change"\nproposed_plan: "| 1 | run step | keep | repo: x | 24 rows |"\nredactions: []\n'


def write(path, text, mode="w"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode) as handle:
        handle.write(text)


class PacketTest(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        write(os.path.join(self.root, "src", "a.py"), "print('a')\n")
        write(os.path.join(self.root, "docs", "b.md"), "# b\n")
        write(os.path.join(self.root, "data", "raw.tsv"), "sample\tx\nD07\t1\n")
        self.packet = os.path.join(self.root, "packet-draft.txt")
        write(self.packet, PACKET)

    def run_cli(self, *args):
        proc = subprocess.run([sys.executable, SCRIPT] + list(args) + ["--root", self.root],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        return proc.returncode, proc.stdout + proc.stderr

    def prepare(self, *attach, **kw):
        args = ["prepare", "--packet", kw.get("packet", self.packet)]
        for a in attach:
            args += ["--attach", a]
        code, out = self.run_cli(*args)
        found = re.search(r"^digest: ([0-9a-f]{64})$", out, re.MULTILINE)
        return code, out, (found.group(1) if found else None)

    def folder(self, digest):
        return os.path.join(self.root, ".mycelium-extra", "review-packets", digest)

    def manifest(self, digest):
        with open(os.path.join(self.folder(digest), "manifest.json")) as handle:
            return json.load(handle)

    def consent(self, digest, ts=None, prompt=None, name=None, record_digest=None):
        """What the gate will write after the user types the prompt."""
        ts = self.manifest(digest)["created"] + 5 if ts is None else ts
        write(os.path.join(self.root, ".mycelium-extra", "review-consent", (name or digest) + ".json"),
              json.dumps({"schema": "mycelium-extra.review-consent.v1", "digest": record_digest or digest,
                          "session_id": "s1", "ts": ts,
                          "prompt": prompt or "send packet " + digest[:12]}))

    def ready(self):
        code, out, digest = self.prepare("src/a.py", "docs/b.md")
        self.assertEqual(code, 0, out)
        return digest

    # the gap this change closes
    def test_gap_a_scan_result_names_the_bytes_it_covered(self):
        def scan():
            proc = subprocess.run([sys.executable, PRESEND, "--packet", self.packet, "--json"],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            return json.loads(proc.stdout)
        first = scan()
        self.assertEqual(first["packet_sha256"], hashlib.sha256(PACKET.encode()).hexdigest())
        write(self.packet, PACKET.replace("28", "29"))
        self.assertNotEqual(scan()["packet_sha256"], first["packet_sha256"])

    def test_prepare_preview_consent_verify_succeeds_and_lists_one_file_set(self):
        digest = self.ready()
        code, out = self.run_cli("preview", "--digest", digest[:12])
        self.assertEqual(code, 0, out)
        self.assertIn(digest, out)
        self.assertIn("send packet " + digest[:12], out)
        self.assertIn("src/a.py", out)
        self.assertNotIn("raw.tsv", out)
        self.consent(digest)
        code, out = self.run_cli("verify", "--digest", digest)
        self.assertEqual(code, 0, out)
        listed = [l for l in out.splitlines() if l.startswith(self.folder(digest))]
        self.assertEqual(sorted(os.path.relpath(l, self.folder(digest)) for l in listed),
                         ["packet.txt", "workspace/docs/b.md", "workspace/src/a.py"])

    def test_manifest_digest_covers_the_packet_hash(self):
        digest = self.ready()
        with open(os.path.join(self.folder(digest), "manifest.json"), "rb") as handle:
            raw = handle.read()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)
        self.assertEqual(self.manifest(digest)["packet"]["sha256"], hashlib.sha256(PACKET.encode()).hexdigest())

    def test_no_consent_refuses_and_scripts_never_write_one(self):
        digest = self.ready()
        self.run_cli("preview", "--digest", digest)
        code, out = self.run_cli("verify", "--digest", digest)
        self.assertEqual(code, 3, out)
        self.assertIn("no consent", out)
        self.assertFalse(os.path.exists(os.path.join(self.root, ".mycelium-extra", "review-consent")))

    def test_edited_packet_after_consent_refuses(self):
        digest = self.ready()
        self.consent(digest)
        path = os.path.join(self.folder(digest), "packet.txt")
        os.chmod(path, 0o644)
        write(path, PACKET + "extra: sent without being reviewed\n")
        code, out = self.run_cli("verify", "--digest", digest)
        self.assertEqual(code, 3, out)
        self.assertIn("packet.txt", out)

    def test_changed_attachment_refuses(self):
        digest = self.ready()
        self.consent(digest)
        path = os.path.join(self.folder(digest), "workspace", "src", "a.py")
        os.chmod(path, 0o644)
        write(path, "print('changed')\n")
        code, out = self.run_cli("verify", "--digest", digest)
        self.assertEqual(code, 3, out)
        self.assertIn("src/a.py", out)

    def test_source_attachment_edited_after_prepare_refuses(self):
        digest = self.ready()
        self.consent(digest)
        write(os.path.join(self.root, "src", "a.py"), "print('edited after prepare')\n")
        code, out = self.run_cli("verify", "--digest", digest)
        self.assertEqual(code, 3, out)
        self.assertIn("changed since prepare", out)

    def test_consent_for_another_digest_refuses(self):
        digest = self.ready()
        other = "0" * 64
        self.consent(digest, record_digest=other)            # right file name, other digest inside
        code, out = self.run_cli("verify", "--digest", digest)
        self.assertEqual(code, 3, out)
        os.remove(os.path.join(self.root, ".mycelium-extra", "review-consent", digest + ".json"))
        write(os.path.join(self.root, ".mycelium-extra", "review-consent", other + ".json"),
              json.dumps({"schema": "mycelium-extra.review-consent.v1", "digest": other, "session_id": "s",
                          "ts": 9999999999, "prompt": "send packet " + other[:12]}))
        code, out = self.run_cli("verify", "--digest", digest)
        self.assertEqual(code, 3, out)
        self.assertIn("no consent", out)

    def test_consent_prompt_must_name_this_digest(self):
        digest = self.ready()
        for prompt in ("send packet " + digest[:11], "send packet " + "f" * 12, "yes send it", "send packet"):
            self.consent(digest, prompt=prompt)
            code, out = self.run_cli("verify", "--digest", digest)
            self.assertEqual(code, 3, (prompt, out))

    def test_consent_older_than_the_packet_refuses(self):
        digest = self.ready()
        self.consent(digest, ts=self.manifest(digest)["created"] - 60)
        code, out = self.run_cli("verify", "--digest", digest)
        self.assertEqual(code, 3, out)
        self.assertIn("before the packet", out)

    def test_unexpected_extra_file_in_the_packet_folder_is_reported(self):
        digest = self.ready()
        self.consent(digest)
        write(os.path.join(self.folder(digest), "workspace", "data", "leak.tsv"), "D07\t1\n")
        for command in ("preview", "verify"):
            code, out = self.run_cli(command, "--digest", digest)
            self.assertEqual(code, 3, out)
            self.assertIn("unexpected file: workspace/data/leak.tsv", out)

    def test_attachment_boundary(self):
        for bad in ("data/raw.tsv", "../outside.py", "missing.py"):
            code, out, digest = self.prepare(bad)
            self.assertEqual(code, 3, (bad, out))
            self.assertIsNone(digest)
        os.symlink(os.path.join(self.root, "data", "raw.tsv"), os.path.join(self.root, "src", "link.py"))
        code, out, digest = self.prepare("src/link.py")
        self.assertEqual(code, 3, out)

    def test_flagged_values_are_never_echoed(self):
        write(os.path.join(self.root, "src", "leak.py"), "k = '{}'\n# {}\n".format(TOKEN, EMAIL))
        packet = PACKET + "note: {} {}\n".format(TOKEN, EMAIL)
        write(self.packet, packet.replace("redactions: []",
              'redactions: [{"kind": "secret", "field": "note"}]'))
        code, out, digest = self.prepare("src/leak.py")
        self.assertEqual(code, 0, out)
        for text in (out, self.run_cli("preview", "--digest", digest)[1]):
            self.assertNotIn(TOKEN, text)
            self.assertNotIn(EMAIL, text)
            self.assertIn("flag", text)

    def test_unredacted_flag_in_the_packet_refuses_to_prepare(self):
        write(self.packet, PACKET + "note: {}\n".format(TOKEN))
        code, out, digest = self.prepare()
        self.assertEqual(code, 3, out)
        self.assertIsNone(digest)
        self.assertNotIn(TOKEN, out)


if __name__ == "__main__":
    unittest.main()
