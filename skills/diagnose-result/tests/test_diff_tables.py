"""Run: python3.11 skills/diagnose-result/tests/test_diff_tables.py"""

import contextlib
import gzip
import io
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
sys.dont_write_bytecode = True
import diff_tables  # noqa: E402

BASE = "donor\tgene\tlfc\tn\nd1\tA\t1.0\t5\nd1\tB\t2.0\t6\nd2\tA\tNA\t7\n"


class DiffTables(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, text):
        path = os.path.join(self.dir.name, name)
        opener = gzip.open if name.endswith(".gz") else open
        with opener(path, "wt") as handle:
            handle.write(text)
        return path

    def run_cli(self, old, new, *extra):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = diff_tables.main([old, new, "--key", "donor,gene", *extra])
        return code, out.getvalue()

    def test_identical_including_gz_and_nan(self):
        old = self.write("a.tsv", BASE)
        new = self.write("b.tsv.gz", BASE.replace("NA", "nan"))
        code, out = self.run_cli(old, new)
        self.assertEqual(code, 0, out)
        self.assertIn("IDENTICAL", out)

    def test_small_float_noise_within_tolerance(self):
        old = self.write("a.tsv", BASE)
        new = self.write("b.tsv", BASE.replace("1.0", "1.0000000001"))
        self.assertEqual(self.run_cli(old, new)[0], 0)

    def test_numeric_difference_beyond_tolerance(self):
        old = self.write("a.tsv", BASE)
        new = self.write("b.tsv", BASE.replace("2.0", "2.5"))
        code, out = self.run_cli(old, new)
        self.assertEqual(code, 1)
        self.assertIn("donor=d1,gene=B lfc: 2.0 -> 2.5", out)
        code, out = self.run_cli(old, new, "--rtol", "0.5")
        self.assertEqual(code, 0, out)

    def test_row_and_column_set_differences(self):
        old = self.write("a.tsv", BASE)
        new = self.write("b.tsv", "donor\tgene\tlfc\textra\nd1\tA\t1.0\tx\nd3\tA\t1.0\tx\n")
        code, out = self.run_cli(old, new)
        self.assertEqual(code, 1)
        self.assertIn("rows only in OLD: 2; only in NEW: 1", out)
        self.assertIn("only in NEW: ['extra']", out)
        self.assertIn("only in OLD: ['n']", out)

    def test_type_like_change(self):
        old = self.write("a.tsv", BASE)
        new = self.write("b.tsv", BASE.replace("\t5\n", "\tfive\n"))
        code, out = self.run_cli(old, new)
        self.assertEqual(code, 1)
        self.assertIn("n: integer -> mixed", out)
        new = self.write("c.tsv", BASE.replace("\t5\n", "\tfive\n").replace("\t6\n", "\tsix\n").replace("\t7\n", "\tseven\n"))
        code, out = self.run_cli(old, new)
        self.assertIn("n: integer -> text", out)

    def test_missing_versus_value_differs(self):
        old = self.write("a.tsv", BASE)
        new = self.write("b.tsv", BASE.replace("NA", "3"))
        self.assertEqual(self.run_cli(old, new)[0], 1)

    def test_redact_keys_hides_values(self):
        old = self.write("a.tsv", BASE)
        new = self.write("b.tsv", BASE.replace("2.0", "9"))
        code, out = self.run_cli(old, new, "--redact-keys")
        self.assertEqual(code, 1)
        self.assertNotIn("d1", out)
        self.assertIn("row 2 (OLD) column 3 (OLD): 2.0 -> 9", out)

    def test_max_rows_limits_listing(self):
        old = self.write("a.csv", "k,v\n" + "".join(f"{i},1\n" for i in range(30)))
        new = self.write("b.csv", "k,v\n" + "".join(f"{i},2\n" for i in range(30)))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = diff_tables.main([old, new, "--key", "k", "--max-rows", "3"])
        self.assertEqual(code, 1)
        self.assertIn("30 cell(s) differ", out.getvalue())
        self.assertEqual(out.getvalue().count("v: 1 -> 2"), 3)

    def test_unusable_inputs(self):
        old = self.write("a.tsv", BASE)
        self.assertEqual(self.run_cli(old, os.path.join(self.dir.name, "nope.tsv"))[0], 2)
        dup = self.write("d.tsv", BASE + "d1\tA\t9\t9\n")
        code, out = self.run_cli(old, dup)
        self.assertEqual(code, 2)
        self.assertIn("duplicate key", out)
        nokey = self.write("k.tsv", "x\ty\n1\t2\n")
        code, out = self.run_cli(old, nokey)
        self.assertEqual(code, 2)
        self.assertIn("key column not found", out)
        empty = self.write("e.tsv", "")
        self.assertEqual(self.run_cli(old, empty)[0], 2)

    def csv_pair(self, old_text, new_text, *extra, key="donor"):
        old, new = self.write("o.csv", old_text), self.write("n.csv", new_text)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = diff_tables.main([old, new, "--key", key, *extra])
        return code, out.getvalue()

    def test_infinite_values_are_differences(self):
        for a, b in [("5", "inf"), ("inf", "-inf"), ("inf", "5"), ("-Inf", "Infinity")]:
            code, out = self.csv_pair(f"donor,x\nd1,{a}\n", f"donor,x\nd1,{b}\n")
            self.assertEqual(code, 1, (a, b, out))
        self.assertEqual(self.csv_pair("donor,x\nd1,inf\n", "donor,x\nd1,Inf\n")[0], 0)

    def test_tolerance_is_symmetric(self):
        a, b = "donor,x\nd1,1.0\n", "donor,x\nd1,1.000002\n"
        forward = self.csv_pair(a, b, "--rtol", "1.9e-6", "--atol", "0")[0]
        backward = self.csv_pair(b, a, "--rtol", "1.9e-6", "--atol", "0")[0]
        self.assertEqual(forward, backward)

    def test_duplicate_column_names_are_unusable(self):
        code, out = self.csv_pair("donor,x,x\nd1,1,2\n", "donor,x,x\nd1,1,9\n")
        self.assertEqual(code, 2)
        self.assertIn("duplicate column name", out)

    def test_extra_cells_are_unusable_short_rows_pad(self):
        code, out = self.csv_pair("donor,x\nd1,1,EXTRA\n", "donor,x\nd1,1,OTHER\n")
        self.assertEqual(code, 2)
        self.assertIn("more", out.replace("has 3 cells but", "more"))
        self.assertEqual(self.csv_pair("donor,x\nd1\n", "donor,x\nd1,\n")[0], 0)

    def test_blank_lines_and_key_spaces(self):
        text = "donor,gene,x\nd1,a,1\nd2,b,2\n\n\n"
        self.assertEqual(self.csv_pair(text, text, key="donor, gene")[0], 0)
        code, out = self.csv_pair(text, text, key=" , ")
        self.assertEqual(code, 2)
        self.assertIn("names no column", out)

    def test_text_compares_exactly(self):
        cases = [
            ("007", "7"),
            ("9007199254740993", "9007199254740992"),
            ("NA", ""),
            ("None", "NA"),
            ("null", ""),
            ("a", "a "),
            ("1_0", "10"),
        ]
        for a, b in cases:
            code, out = self.csv_pair(f"donor,x\nd1,{a}\n", f"donor,x\nd1,{b}\n")
            self.assertEqual(code, 1, (a, b, out))
        self.assertEqual(self.csv_pair("donor,x\nd1,NA\n", "donor,x\nd1,nan\n")[0], 0)
        self.assertEqual(self.csv_pair("donor,x\nd1,1.5\n", "donor,x\nd1,1.50\n")[0], 0)

    def test_column_order_reported(self):
        code, out = self.csv_pair("donor,a,b\nd1,1,2\n", "donor,b,a\nd1,2,1\n")
        self.assertEqual(code, 1)
        self.assertIn("column order differs", out)

    def test_header_only_files_are_identical(self):
        self.assertEqual(self.csv_pair("donor,x\n", "donor,x\n")[0], 0)

    def test_bad_gzip_is_unusable(self):
        good = self.write("a.csv", "donor,x\nd1,1\n")
        bad = os.path.join(self.dir.name, "bad.csv.gz")
        with open(bad, "wb") as handle:
            handle.write(b"not gzip at all")
        self.assertEqual(self.run_cli(good, bad)[0], 2)
        trunc = os.path.join(self.dir.name, "trunc.csv.gz")
        with gzip.open(trunc, "wt") as handle:
            handle.write("donor,x\n" + "d1,1\n" * 5000)
        with open(trunc, "rb") as handle:
            data = handle.read()
        with open(trunc, "wb") as handle:
            handle.write(data[: len(data) // 2])
        self.assertEqual(self.run_cli(good, trunc)[0], 2)

    def test_unusable_output_format(self):
        code, out = self.csv_pair("donor,x\nd1,1\nd1,2\n", "donor,x\nd1,1\n")
        self.assertEqual((code, out.startswith("UNUSABLE: ")), (2, True))

    def test_redaction_hides_text_cells_columns_and_labels_sides(self):
        old = "donor,gene,x,lab\nd1,a,1,P001\nd2,a,1,P002\n"
        new = "donor,gene,x,lab\nd1,a,1,P009\nd3,a,1,P003\n"
        code, out = self.csv_pair(old, new, "--redact-keys", key="donor,gene")
        self.assertEqual(code, 1)
        for secret in ("d1", "d2", "d3", "P001", "P009", "lab"):
            self.assertNotIn(secret, out)
        self.assertIn("only in OLD: row 2 (OLD)", out)
        self.assertIn("only in NEW: row 2 (NEW)", out)
        self.assertIn("<text> -> <text>", out)
        wide_old, wide_new = "donor,P001\nd1,1\n", "donor,P002\nd1,1\n"
        code, out = self.csv_pair(wide_old, wide_new, "--redact-keys")
        self.assertNotIn("P00", out)


if __name__ == "__main__":
    unittest.main()
