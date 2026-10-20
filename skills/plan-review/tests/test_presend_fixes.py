"""Run: python3 skills/plan-review/tests/test_presend_fixes.py

Regression tests for the plan-review findings in docs/roadmap/13-function-audit.md: an `Inputs:` line
the packet really contains must be read whatever its Markdown shape, a table whose delimiter or ID
column is unfamiliar must be reported unchecked rather than clean, and the input-coverage gap the
skill documents as consentable must be consentable.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(SKILL))
PRESEND = os.path.join(SKILL, "scripts", "presend_check.py")
PACKET_CLI = os.path.join(SKILL, "scripts", "review_packet.py")
FIXTURE = os.path.join(REPO, "tests", "fixtures", "mycelium-project")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
sys.dont_write_bytecode = True
import presend_check  # noqa: E402


def packet(extra, inputs="data/processed/vaccine-cohort/sample_metadata.tsv", shape="  Inputs: {}"):
    return ("objective: \"Test the day 28 change\"\nproposed_plan: |\n" + shape.format(inputs) + "\n" + extra
            + "\nunknowns: []\nredactions: []\n")


class InputLineTest(unittest.TestCase):
    # C35: the shapes an author really writes
    def test_inputs_line_is_read_as_a_bullet_or_in_bold(self):
        for line in ("- Inputs: `data/a.tsv`", "* **Inputs:** data/b.csv",
                     "**Inputs:** data/c.tsv", "  Inputs: data/d.tsv"):
            found = presend_check.packet_inputs(line + "\n")
            self.assertEqual(len(found), 1, (line, found))
            self.assertRegex(found[0], r"^data/[a-d]\.")

    def test_a_bulleted_inputs_line_still_yields_identifier_flags(self):
        text = packet("  The donor D07 failed QC.", shape="- Inputs: {}")
        flags, _ = presend_check.check(text, FIXTURE)
        self.assertTrue(any(f[1] == "participant identifier" for f in flags), flags)


class InputTableTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write(text)

    # C36: a delimiter that is not comma-or-tab
    def test_semicolon_delimited_table_is_read(self):
        self.write("cohort.csv", "donor;arm\nD07;vaccine\n")
        text = packet("  The donor D07 failed QC.", inputs="cohort.csv")
        flags, unread = presend_check.check(text, self.root)
        self.assertEqual(unread, [])
        self.assertTrue(any(f[1] == "participant identifier" for f in flags), flags)

    # C36: a table with no ID-like column cannot be checked, so it must be said, not left as clean
    def test_table_without_an_id_column_is_reported_not_checked(self):
        self.write("metrics.csv", "x,y\n1,2\n")
        text = packet("  Nothing to see.", inputs="metrics.csv")
        flags, unread = presend_check.check(text, self.root)
        self.assertEqual((flags, unread), ([], []))
        quiet = []
        presend_check.check(text, self.root, quiet)
        self.assertEqual(quiet, ["metrics.csv"])
        result = presend_check.analyse(text.encode(), self.root)
        self.assertEqual(result["inputs_without_id_column"], [presend_check.mask("metrics.csv")])
        self.assertIn("no recognised identifier column",
                      presend_check.render(result["flags"], result["unread"], result["redactions_listed"],
                                           result["inputs_without_id_column"]))

    # C36: a column name with a space is still an identifier column
    def test_spaced_identifier_column_is_recognised(self):
        self.write("cohort.csv", "donor id,arm\nD07,vaccine\n")
        text = packet("  The donor D07 failed QC.", inputs="cohort.csv")
        flags, unread = presend_check.check(text, self.root)
        self.assertEqual(unread, [])
        self.assertTrue(any(f[1] == "participant identifier" for f in flags), flags)

    def test_table_with_no_recognisable_delimiter_is_reported_unchecked(self):
        self.write("notes.csv", "just some prose\nno table here\n")
        text = packet("  Nothing to see.", inputs="notes.csv")
        _, unread = presend_check.check(text, self.root)
        self.assertEqual(unread, ["notes.csv"])


class ConsentTest(unittest.TestCase):
    """C37: the coverage gap SKILL.md says the user may accept is accepted by `prepare`."""

    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.path = os.path.join(self.root, "packet.txt")

    def write(self, text):
        with open(self.path, "w") as handle:
            handle.write(text)

    def prepare(self, *args):
        proc = subprocess.run([sys.executable, PACKET_CLI, "prepare", "--packet", self.path,
                               "--root", self.root] + list(args),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        return proc.returncode, proc.stdout + proc.stderr

    def manifest(self, out):
        digest = re.search(r"^digest: ([0-9a-f]{64})$", out, re.MULTILINE).group(1)
        with open(os.path.join(self.root, ".mycelium-extra", "review-packets", digest, "manifest.json")) as handle:
            return json.load(handle)

    def test_a_missing_input_refuses_then_prepares_with_consent(self):
        self.write(packet("  Nothing sensitive here.", inputs="data/missing.tsv"))
        code, out = self.prepare()
        self.assertEqual(code, 3, out)
        self.assertIn("Do not send", out)
        self.assertIn("--consent-unread-inputs", out)
        code, out = self.prepare("--consent-unread-inputs")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.manifest(out)["scan"]["consented_unread_inputs"])
        self.assertEqual(self.manifest(out)["scan"]["inputs_unread"], 1)

    def test_consent_does_not_cover_an_undisclosed_flag(self):
        token = "gh" + "p_" + "A1b2C3d4" * 5
        self.write(packet("  Use token {}.".format(token), inputs="data/missing.tsv"))
        code, out = self.prepare("--consent-unread-inputs")
        self.assertEqual(code, 3, out)
        self.assertIn("redactions", out)

    def test_clean_packet_records_no_consent(self):
        shutil.copytree(os.path.join(FIXTURE, "data"), os.path.join(self.root, "data"))
        self.write(packet("  Nothing sensitive here."))
        code, out = self.prepare()
        self.assertEqual(code, 0, out)
        self.assertFalse(self.manifest(out)["scan"]["consented_unread_inputs"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
