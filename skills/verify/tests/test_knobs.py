"""Run: python3 skills/verify/tests/test_knobs.py

Knobs against plan rows (0.32): the top-level UPPER_SNAKE values of a planned R or Python script, which lucid-coder's
house style keeps in one block, are matched to the plan's Choice cells. A knob no Choice names is an info line.
"""

import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(PLUGIN, "hooks"))
sys.dont_write_bytecode = True
import gate  # noqa: E402

verify = gate.load_verify()

R_SCRIPT = """# Purpose: fit
ROOT <- here::here()
PADJ_MAX <- 0.05  # FDR cutoff for the DE call
MIN_COUNT <- 10   # genes below this are dropped
CONTRAST_LEVELS <- c("ctrl", "trt")
OUT_DIR <- here("outputs/03_fit")
SEED <- 7
if (SEED == 7) { x <- 1 }
fit <- function() {
  INNER <- 3
}
"""
PY_SCRIPT = """\"\"\"Fit.\"\"\"
ROOT = Path(__file__).resolve().parents[1]
FDR = 0.1  # cutoff
MODEL = "nb"
DATA_FILE = "data/x.tsv"
USE_BATCH = True


def main():
    LOCAL = 2
"""


def plan(*rows):
    lines = ["| # | Step | Choice | Source | Validation |", "|---|---|---|---|---|"]
    lines += ["| {} | `{}` | {} | user | ok |".format(i + 1, script, choice) for i, (script, choice) in enumerate(rows)]
    return "\n".join(lines)


class Tmp(unittest.TestCase):
    def setUp(self):
        self.dir = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)

    def write(self, rel, text):
        path = os.path.join(self.dir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write(text)
        return path


class Parse(Tmp):
    def test_r_knobs_are_read_with_values_lines_and_reasons(self):
        knobs = {k[0]: k for k in verify.script_knobs(self.write("a/fit.R", R_SCRIPT))}
        self.assertEqual(knobs["PADJ_MAX"][1:], ("0.05", 3, "FDR cutoff for the DE call"))
        self.assertEqual(knobs["MIN_COUNT"][1], "10")
        self.assertEqual(knobs["SEED"][1], "7")
        self.assertIn("CONTRAST_LEVELS", knobs)

    def test_paths_roots_comparisons_and_indented_names_are_not_knobs(self):
        names = {k[0] for k in verify.script_knobs(self.write("a/fit.R", R_SCRIPT))}
        self.assertNotIn("ROOT", names)
        self.assertNotIn("OUT_DIR", names)
        self.assertNotIn("INNER", names)  # inside a function: indented

    def test_python_knobs(self):
        names = {k[0] for k in verify.script_knobs(self.write("a/fit.py", PY_SCRIPT))}
        self.assertEqual(names, {"FDR", "MODEL", "USE_BATCH"})  # ROOT and DATA_FILE are paths; LOCAL is indented

    def test_short_names_digit_names_annotations_and_r_integers_are_knobs(self):  # planted break: missed knobs
        body = "K = 30\nFC = 2\nTOP50 = True\nSEED: int = 1\nLOG2FC <- 1\nN_PC <- 10L\nALPHA = 1/20\nSUBSET = \"CD4/CD8\"\n"
        knobs = {k[0]: k[1] for k in verify.script_knobs(self.write("a/k.py", body))}
        self.assertEqual(knobs, {"K": "30", "FC": "2", "TOP50": "True", "SEED": "1", "LOG2FC": "1", "N_PC": "10L",
                                 "ALPHA": "1/20", "SUBSET": "\"CD4/CD8\""})

    def test_only_path_looking_values_are_dropped(self):  # control
        body = "A = \"./x\"\nB = \"data/x.tsv\"\nC = Path(\"x\")\nD <- file.path(\"a\", \"b\")\nE <- \"~/y\"\nF = \"nb\"\n"
        self.assertEqual({k[0] for k in verify.script_knobs(self.write("a/p.py", body))}, {"F"})

    def test_mixed_case_and_comparisons_are_not_knobs(self):
        body = "Fit = 3\nX == 3\nx = 3\n"
        self.assertEqual(verify.script_knobs(self.write("a/m.py", body)), [])

    def test_another_language_and_a_missing_file_give_nothing(self):
        self.assertEqual(verify.script_knobs(self.write("a/x.sh", "FDR=0.1\n")), [])
        self.assertEqual(verify.script_knobs(os.path.join(self.dir, "nope.R")), [])


class Coverage(Tmp):
    def run_check(self, text, script="a/fit.R", body=R_SCRIPT):
        self.write(script, body)
        report = verify.Report()
        found = verify.knob_coverage(self.dir, [script], text, report)
        return report, found

    def test_a_knob_the_plan_never_names_is_an_info_line(self):  # planted break: an unplanned knob
        report, found = self.run_check(plan(("a/fit.R", "edgeR quasi-likelihood fit")))
        self.assertEqual({f["name"] for f in found}, {"PADJ_MAX", "MIN_COUNT", "CONTRAST_LEVELS", "SEED"})
        self.assertEqual([l for l, _ in report.findings], ["info"])
        self.assertEqual(report.status(), "CONFORMS")
        self.assertIn("PADJ_MAX = 0.05 (line 3)", report.findings[0][1])

    def test_a_knob_named_by_name_by_number_or_by_text_is_covered(self):  # control
        choice = "padj max cutoff; keep genes with at least 10 counts; contrast ctrl vs trt; seed 7"
        report, found = self.run_check(plan(("a/fit.R", choice)))
        self.assertEqual(found, [])
        self.assertEqual(report.findings, [])

    def test_a_short_name_is_matched_as_a_whole_word(self):  # planted break: "knockout" named K
        self.assertFalse(verify.knob_named(("K", "30"), "knockout of genes", by_number=False))
        self.assertFalse(verify.knob_named(("N", "20"), "normalise counts", by_number=False))
        self.assertTrue(verify.knob_named(("K", "30"), "k neighbours", by_number=False))  # control
        self.assertTrue(verify.knob_named(("MIN_CELLS", "10"), "min cells per donor", by_number=False))
        self.assertTrue(verify.knob_named(("TOP50", "50"), "top 50 genes", by_number=False))

    def test_the_number_alone_covers_a_knob(self):
        _, found = self.run_check(plan(("a/fit.R", "FDR 0.05, min 10, ctrl trt, seed 7")))
        self.assertEqual(found, [])

    def test_a_different_number_does_not_cover_it(self):  # planted break: the plan says 0.01, the script 0.05
        _, found = self.run_check(plan(("a/fit.R", "FDR 0.01, min 10, ctrl trt, seed 7")))
        self.assertEqual([f["name"] for f in found], ["PADJ_MAX"])

    def test_a_script_no_row_names_is_matched_by_name_only(self):
        _, found = self.run_check(plan(("a/other.R", "FDR 0.05, min 10, ctrl trt, seed 7")))
        self.assertEqual({f["name"] for f in found}, {"PADJ_MAX", "MIN_COUNT", "CONTRAST_LEVELS"})  # SEED named
        _, found = self.run_check(plan(("a/other.R", "padj max, min count, contrast levels, seed")))
        self.assertEqual(found, [])

    def test_a_number_in_another_scripts_row_does_not_cover_a_knob(self):  # planted break: "top 10 genes" over-match
        body = "MIN_CELLS <- 10\n"
        _, found = self.run_check(plan(("a/fit.R", "edgeR fit"), ("a/plot.R", "label top 10 genes")), "a/fit.R", body)
        self.assertEqual([f["name"] for f in found], ["MIN_CELLS"])

    def test_a_number_in_the_scripts_own_row_covers_it(self):  # control
        body = "MIN_CELLS <- 10\n"
        _, found = self.run_check(plan(("a/fit.R", "keep at least 10 cells"), ("a/plot.R", "x")), "a/fit.R", body)
        self.assertEqual(found, [])

    def test_an_r_integer_and_an_arithmetic_value_are_covered_by_their_numbers(self):
        body = "K <- 30L\nALPHA <- 1/20\n"
        _, found = self.run_check(plan(("a/fit.R", "30 neighbours, level 1/20")), "a/fit.R", body)
        self.assertEqual(found, [])
        _, found = self.run_check(plan(("a/fit.R", "30 neighbours, level 1/10")), "a/fit.R", body)
        self.assertEqual([f["name"] for f in found], ["ALPHA"])

    def test_python_boolean_knob_needs_its_name(self):
        _, found = self.run_check(plan(("a/fit.py", "FDR 0.1 with model nb")), "a/fit.py", PY_SCRIPT)
        self.assertEqual([f["name"] for f in found], ["USE_BATCH"])

    def test_no_plan_table_or_no_knobs_is_quiet(self):
        report, found = self.run_check("no table here")
        self.assertEqual((found, report.findings), ([], []))
        report, found = self.run_check(plan(("a/x.R", "x")), "a/x.R", "x <- 1\n")
        self.assertEqual((found, report.findings), ([], []))

    def test_many_missing_knobs_are_capped_in_the_line(self):
        body = "".join("KNOB_{} <- {}\n".format(i, i) for i in range(9))
        report, found = self.run_check(plan(("a/fit.R", "something else")), "a/fit.R", body)
        self.assertEqual(len(found), 9)
        self.assertIn("and 3 more", report.findings[0][1])


class Render(Tmp):
    def test_the_knobs_listing_names_each_value_and_reason(self):
        text = verify.render_knobs([self.write("a/fit.R", R_SCRIPT)])
        self.assertIn("`PADJ_MAX` = `0.05` (line 3) - FDR cutoff for the DE call", text)
        self.assertNotIn("OUT_DIR", text)


if __name__ == "__main__":
    unittest.main()
