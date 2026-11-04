"""Run: python3 skills/analysis-report/tests/test_artifact_check.py"""

import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "artifact_check.py")
FIX = os.path.join(HERE, "fixtures", "artifact")
GOOD = os.path.join(FIX, "good_page.html")
QMD = os.path.join(FIX, "demo.qmd")
NUMBERS = os.path.join(FIX, "numbers.json")
SLOP = os.path.join(HERE, "..", "..", "..", "tests", "slop_lint.py")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class ArtifactCheckTest(unittest.TestCase):
    def check(self, page_text, numbers=True):
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as handle:
            handle.write(page_text)
        self.addCleanup(os.unlink, handle.name)
        args = [sys.executable, "-", "--page=" + handle.name, "--report=" + QMD]
        if numbers:
            args.append("--numbers=" + NUMBERS)
        with open(SCRIPT, "rb") as script:  # stdin, as the skill runs it
            run = subprocess.run(args, stdin=script, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8")
        return run.returncode, run.stdout

    def test_good_page_is_clean(self):
        code, out = self.check(read(GOOD))
        self.assertEqual((code, out.count("\n")), (0, 1), out)

    def test_invented_number_fails_and_is_named(self):
        code, out = self.check(read(GOOD).replace("FDR 0.003", "FDR 0.004"))
        self.assertEqual(code, 1)
        self.assertIn("number: 0.004", out)
        self.assertNotIn("number: 0.003", out)

    def test_number_in_numbers_json_only_passes(self):
        page = read(GOOD).replace("<li>Dose effect", "<li>14,231 genes tested. Dose effect")
        self.assertEqual(self.check(page)[0], 0)
        page = read(GOOD).replace("<li>Dose effect", "<li>Seen in 7 plates. Dose effect")
        self.assertIn("number: 7 ", self.check(page)[1])

    def test_hash_style_and_data_uri_numbers_are_ignored(self):
        page = read(GOOD).replace('class="hash">a1b2c3d4', 'class="hash">20261104').replace("max-width: 920px", "max-width: 921px")
        self.assertEqual(self.check(page)[0], 0)

    def test_doctype_breaks_the_contract(self):
        code, out = self.check("<!DOCTYPE html>\n" + read(GOOD))
        self.assertEqual(code, 1)
        self.assertIn("contract:", out)
        self.assertIn("<!DOCTYPE>", out)

    def test_other_contract_breaks(self):
        good = read(GOOD)
        cases = {
            "title": good.replace("<title>IL6 evaluation</title>", ""),
            "dark": good.replace(':root[data-theme="dark"]', ":root.dark"),
            "background": good.replace("background: var(--paper); ", ""),
            "host": good + '<script src="https://evil.example/x.js"></script>',
            "unpinned": good + '<script src="https://unpkg.com/mermaid/dist/m.js"></script>',
            "colour": good.replace("color: var(--ink-2); font-size", "color: #ff0000; font-size"),
            "alert": good + "<script>alert(1)</script>",
        }
        for name, page in cases.items():
            with self.subTest(name):
                self.assertEqual(self.check(page)[0], 1, name)

    def test_banner_is_required(self):
        page = read(GOOD).replace("Evaluation copy.</strong> The record is", "Copy.</strong> The record is")
        self.assertIn("banner:", self.check(page)[1])
        page = read(GOOD).replace('<span class="pill pass">verified</span>', "")
        self.assertIn("verified / not verified", self.check(page)[1])

    def test_size_limit(self):
        code, out = self.check(read(GOOD) + "<!-- " + "x" * (16 * 1024 * 1024) + " -->")
        self.assertEqual(code, 1)
        self.assertIn("16 MB", out)

    @unittest.skipUnless(os.path.exists(SLOP), "tests/slop_lint.py is added by B5")
    def test_good_page_passes_slop_lint(self):
        run = subprocess.run([sys.executable, SLOP, GOOD], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8")
        self.assertEqual(run.returncode, 0, run.stdout)


if __name__ == "__main__":
    unittest.main()
