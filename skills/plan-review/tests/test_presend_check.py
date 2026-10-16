"""Unit tests for the pre-send packet check (roadmap C3).

Run: python3 skills/plan-review/tests/test_presend_check.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(SKILL))
SCRIPT = os.path.join(SKILL, "scripts", "presend_check.py")
FIXTURE = os.path.join(REPO, "tests", "fixtures", "mycelium-project")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
sys.dont_write_bytecode = True
import presend_check  # noqa: E402

# Built from parts so no secret-shaped literal sits in the repository for a scanner to find.
TOKEN = "gh" + "p_" + "A1b2C3d4" * 5
KEY = "AK" + "IA" + "ABCDEFGHIJKLMNOP"
BASE = """objective: "Test the day 28 minus day 0 change between arms"
data:
  sample_sizes: "12 donors x 2 visits"
proposed_plan: |
  Inputs: data/processed/vaccine-cohort/sample_metadata.tsv data/processed/vaccine-cohort/counts.tsv
  | 1 | run `analysis/vaccine-response/scripts/01_select_samples.py` | keep preferred | repo: .living/decisions.md | 24 rows |
{extra}
unknowns: []
redactions: {redactions}
"""


def packet(extra="", redactions="[]"):
    return BASE.format(extra=extra, redactions=redactions)


def run(text, *args):
    handle, path = tempfile.mkstemp()
    self_cleanup = [path]
    try:
        with os.fdopen(handle, "w") as out:
            out.write(text)
        with open(SCRIPT) as source:
            proc = subprocess.run([sys.executable, "-", "--packet", path] + list(args), stdin=source,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        return proc.returncode, proc.stdout
    finally:
        for p in self_cleanup:
            os.remove(p)


class PresendCheckTest(unittest.TestCase):
    def test_a_packet_from_the_fixture_with_no_identifiers_is_clean_and_says_what_that_means(self):
        code, out = run(packet(), "--repo", FIXTURE)
        self.assertEqual(code, 0, out)
        self.assertIn("nothing flagged", out)
        self.assertIn("pattern-based", out)
        self.assertIn("not evidence that nothing sensitive remains", out)

    def test_planted_identifiers_and_secrets_are_flagged_and_block_while_redactions_is_empty(self):
        extra = ("  The donors D07 and D12 (samples D07_day28, D12_day0) fail QC; token {} was used; "
                 "contact j.devries@example.org; script in /home/jdevries/proj; key {}.").format(TOKEN, KEY)
        code, out = run(packet(extra), "--repo", FIXTURE)
        self.assertEqual(code, 3, out)
        for kind in ("participant identifier", "GitHub token", "email address", "home path", "AWS access key"):
            self.assertIn(kind, out)
        self.assertIn("`redactions:` is empty, so do not send", out)
        for secret in (TOKEN, KEY, "D07_day28", "D12_day0", "jdevries@example.org", "/home/jdevries"):
            self.assertNotIn(secret, out, "a flag must not print the value it matched")

    def test_listed_redactions_leave_the_decision_to_the_user(self):
        extra = "  The donor D07 failed QC."
        for redactions in ('["participant IDs removed from the QC note"]',
                           "\n  - kind: participant id\n    field: proposed_plan"):
            code, out = run(packet(extra, redactions), "--repo", FIXTURE)
            self.assertEqual(code, 2, out)
            self.assertIn("they decide whether to send", out)

    def test_secret_shapes(self):
        for text in ("-----BEGIN OPENSSH PRIVATE KEY-----", "Authorization: Bearer abcdefgh12345678",
                     'password = "hunter2hunter2"', "api_key: 0123456789abcdef", "sk-" + "a" * 24,
                     "eyJ" + "a" * 12 + "." + "b" * 12 + "." + "c" * 12, "https://user:pw123456@host.example/x",
                     "xox" + "b-" + "1" * 12, "server 10.20.30.40", "C:\\Users\\jdoe\\data"):
            self.assertEqual(presend_check.check(text)[0] != [], True, text)

    def test_known_false_positives_are_flagged_and_documented(self):
        # A four-part version looks like an address; a password-like policy name looks like a credential.
        self.assertIn("IPv4 address", [f[1] for f in presend_check.check("scilintr 0.1.2.3")[0]])
        self.assertIn("secret assignment", [f[1] for f in presend_check.check("password: policy-v2-final")[0]])
        # A value of an ID column that is also a word in the packet is flagged as an identifier.
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        with open(os.path.join(folder, "meta.tsv"), "w") as handle:
            handle.write("sample\tarm\ncontrol\tplacebo\n")
        flags = presend_check.check("Inputs: meta.tsv\nthe control arm", folder)[0]
        self.assertIn("participant identifier", [f[1] for f in flags])

    def test_placeholders_and_empty_values_are_not_secrets(self):
        for text in ("token: none", "password = required", "api_key: <your key>", "secret: null",
                     "token: [REDACTED]", "token = $TOKEN", "auth: true"):
            self.assertEqual(presend_check.check(text)[0], [], text)

    def test_documented_misses(self):
        # Not caught, by design (see the module docstring): the check says so instead of claiming safety.
        misses = [
            "key bytes Zm9vYmFyYmF6cXV4MTIzNDU2Nzg5MDEyMzQ1Ng==",   # a secret with no keyword or known shape
            "the 54-year-old woman from Leiden with a rare variant",  # free-text re-identification
            "Jan de Vries reviewed the QC",                           # a name
        ]
        for text in misses:
            self.assertEqual(presend_check.check(text)[0], [], text)
        # An identifier in a table the plan does not name under Inputs: is not known to the check.
        flags = presend_check.check("Inputs: data/processed/vaccine-cohort/counts.tsv\ndonor D07", FIXTURE)[0]
        self.assertEqual(flags, [])
        code, out = run("Inputs: data/processed/vaccine-cohort/counts.tsv\nJan de Vries reviewed donor D07.\nredactions: []\n",
                        "--repo", FIXTURE)
        self.assertEqual(code, 0, "exit 0 is not a promise: the output says so")
        self.assertIn("not evidence that nothing sensitive remains", out)

    def test_redactions_field_parsing(self):
        listed = presend_check.redactions_listed
        for text in ("redactions: []", "redactions:", "redactions: [] # none needed", "x: 1", "",
                     "redactions:\n  # none\nunknowns: []", "redactions:\nunknowns: []"):
            self.assertFalse(listed(text), repr(text))
        for text in ('redactions: ["a"]', "redactions:\n  - IDs removed", "redactions:\n- kind: id"):
            self.assertTrue(listed(text), repr(text))

    def test_an_unreadable_packet_exits_1(self):
        with open(SCRIPT) as source:
            proc = subprocess.run([sys.executable, "-", "--packet", "/nonexistent/packet"], stdin=source,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("cannot read the packet", proc.stderr)


if __name__ == "__main__":
    unittest.main()
