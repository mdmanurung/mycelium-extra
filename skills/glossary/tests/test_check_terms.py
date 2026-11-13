"""Run: python3 skills/glossary/tests/test_check_terms.py"""

import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "check_terms.py")
spec = importlib.util.spec_from_file_location("check_terms", SCRIPT)
ct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ct)

GLOSSARY = """# demo: glossary

Words for the demo.

## Language

**Donor**:
A person who gave blood.
_Avoid_: patient, subject (too clinical)

**Batch**:
Libraries prepared together.
_Avoid_: run, `lane`
"""


def put(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(text)


class CheckTerms(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "demo")
        put(self.root, "GLOSSARY.md", GLOSSARY)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_main(self, *extra):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = ct.main(["--analysis", self.root, *extra])
        return code, buf.getvalue()

    def test_parse(self):
        terms = ct.parse_glossary(GLOSSARY)
        self.assertEqual([t["term"] for t in terms], ["Donor", "Batch"])
        self.assertEqual(terms[0]["avoid"], ["patient", "subject"])
        self.assertEqual(terms[1]["avoid"], ["run", "lane"])

    def test_clean_exit_0(self):
        put(self.root, "README.md", "Each donor has one batch.\n")
        code, out = self.run_main()
        self.assertEqual(code, 0, out)
        self.assertIn("no drift found", out)

    def test_drift_in_doc_comment_and_header(self):
        put(self.root, "README.md", "The patient list.\n```\nsubject here is fenced\n```\n")
        put(self.root, "code/01_prep.R", "x <- 1  # one row per Subject\nsubject <- 2\n")
        put(self.root, "outputs/01_prep/tables/01_prep.tsv", "run_id\tdonor\n1\tpatient\n")
        code, out = self.run_main()
        self.assertEqual(code, 1, out)
        self.assertIn("avoid 'patient': 1 hit", out)  # header cell values are not read, doc line is
        self.assertIn("README.md:1", out)
        self.assertIn("code/01_prep.R:1 (code)", out)
        self.assertNotIn("code/01_prep.R:2", out)  # code outside a comment is not read
        self.assertIn("avoid 'run'", out)
        self.assertIn("01_prep.tsv:1 (header)", out)
        self.assertNotIn("README.md:3", out)  # fenced

    def test_underscore_is_a_word_break_and_substring_is_not(self):
        put(self.root, "outputs/s/a.tsv", "batch_run\trunway\n")
        code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("avoid 'run': 1 hit", out)

    def test_missing_glossary_is_exit_2(self):
        os.remove(os.path.join(self.root, "GLOSSARY.md"))
        code, _ = self.run_main()
        self.assertEqual(code, 2)

    def test_empty_glossary_is_exit_2_with_gap(self):
        put(self.root, "GLOSSARY.md", "# t\n\n## Language\n")
        put(self.root, "README.md", "A patient.\n")
        code, out = self.run_main()
        self.assertEqual(code, 2)
        self.assertIn("no terms", out)

    def test_one_line_terms_parse(self):
        text = "# g\n\n**Donor**: a person.\n_Avoid_: patient\n"
        self.assertEqual(ct.parse_glossary(text), [{"term": "Donor", "avoid": ["patient"]}])
        put(self.root, "GLOSSARY.md", text)
        put(self.root, "README.md", "we saw patient here\n")
        code, out = self.run_main()
        self.assertEqual(code, 1, out)

    def test_missing_analysis_doc_is_not_a_pass(self):
        code, out = self.run_main()
        self.assertEqual(code, 2, out)
        self.assertIn("no analysis doc", out)

    def test_truncated_scan_is_not_a_pass(self):
        put(self.root, "README.md", "Each donor has one batch.\n")
        for i in range(ct.MAX_FILES + 5):
            put(self.root, "code/s%03d.py" % i, "# donor\n")
        code, out = self.run_main()
        self.assertEqual(code, 2, out)
        self.assertIn("scanned the first", out)

    def test_code_spans_and_paths_are_not_prose(self):
        put(self.root, "README.md", "See `run_id` and outputs/run_20261112_v2/ and the sample/run.sh file.\n")
        self.assertEqual(self.run_main()[0], 0)
        code, out = self.run_main("--include-code-spans")
        self.assertEqual(code, 1, out)
        put(self.root, "README.md", "Each run is slow; donor/run pairs.\n")
        self.assertEqual(self.run_main()[0], 1)

    def test_avoid_word_that_is_a_term_is_a_clash(self):
        put(self.root, "GLOSSARY.md", GLOSSARY + "\n**Run**:\nOne call of run.sh.\n_Avoid_: job\n\n**Lane**:\nA flow cell lane.\n")
        code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("clash", out)

    def test_doc_named_after_folder(self):
        put(self.root, "DEMO.md", "A patient.\n")
        code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("DEMO.md:1", out)

    def test_read_only_and_stdin_form(self):
        put(self.root, "README.md", "A patient.\n")
        before = sorted(os.listdir(self.root))
        with open(SCRIPT) as handle:
            proc = subprocess.run([sys.executable, "-", "--analysis", self.root, "--json"], stdin=handle, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn('"status": 1', proc.stdout)
        self.assertEqual(sorted(os.listdir(self.root)), before)


if __name__ == "__main__":
    unittest.main()
