"""Run: python3 skills/data-contract-check/tests/test_data_contract_check.py"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "data_contract_check.py")
FIXTURES = os.path.join(HERE, "fixtures")


def run(checks, filters=None):
    contract = {"schema": "mycelium-extra.data_contract.v1", "table": "samples.tsv",
                "filters": filters or [], "checks": checks}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(contract, handle)
    try:
        with open(SCRIPT) as source:
            proc = subprocess.Popen(
                [sys.executable, "-", "--contract", handle.name, "--root", FIXTURES, "--json"],
                stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, _ = proc.communicate()
    finally:
        os.unlink(handle.name)
    alerts = json.loads(out.decode("utf-8"))["alerts"] if proc.returncode != 1 else None
    return proc.returncode, alerts


KEEP = [{"column": "keep", "equals": "TRUE"}]


class DataContractCheckTest(unittest.TestCase):
    def test_missing_column_blocks(self):
        code, alerts = run([{"kind": "schema", "columns": ["sample", "participant", "donor"]}])
        self.assertEqual(code, 2)
        self.assertEqual(alerts[0]["observed"], "missing: donor")

    def test_repeated_unit_in_cell_blocks(self):
        code, alerts = run([{"kind": "unit_of_replication", "unit": "participant",
                             "group": "cohort", "within": ["visit"]}])
        self.assertEqual(code, 2)
        blocking = [a for a in alerts if a["blocking"]]
        self.assertEqual(blocking[0]["observed"], "1 repeated cells")
        self.assertIn("participant=p4", blocking[0]["evidence"][0])

    def test_filter_removes_repeat(self):
        code, alerts = run([{"kind": "unit_of_replication", "unit": "participant",
                             "group": "cohort", "within": ["visit"]}], KEEP)
        self.assertEqual(code, 0)
        self.assertEqual(alerts, [])

    def test_pairing_lists_incomplete_units(self):
        code, alerts = run([{"kind": "pairing", "unit": "participant", "within": "visit"}], KEEP)
        self.assertEqual(code, 2)
        self.assertEqual(alerts[0]["observed"], "2 of 5 units incomplete")

    def test_missing_values_warn_and_are_excluded(self):
        code, alerts = run([{"kind": "batch_confounding", "batch": "batch", "contrast": "cohort"}], KEEP)
        self.assertEqual(code, 0)
        messages = [a["message"] for a in alerts]
        self.assertTrue(any("missing value" in m for m in messages))
        self.assertTrue(any("only one 'cohort' level" in m for m in messages))

    def test_fully_nested_batch_blocks(self):
        code, alerts = run([{"kind": "batch_confounding", "batch": "participant", "contrast": "cohort"}])
        self.assertEqual(code, 2)
        self.assertIn("fully nested", alerts[-1]["message"])

    def test_cohort_levels_and_rows(self):
        code, alerts = run([{"kind": "cohort", "column": "cohort", "levels": ["A", "C"],
                             "rows": 8, "no_missing": ["batch"]}], KEEP)
        self.assertEqual(code, 2)
        observed = sorted(a["observed"] for a in alerts)
        self.assertEqual(observed, ["1 of 8 rows", "absent: C"])

    def test_contract_cannot_downgrade_severity(self):
        code, _ = run([{"kind": "schema", "columns": ["donor"], "severity": "warning"}])
        self.assertEqual(code, 2)

    def test_zero_rows_after_filter_blocks(self):
        code, alerts = run([{"kind": "unit_of_replication", "unit": "participant", "group": "cohort"}],
                           [{"column": "keep", "equals": "True"}])
        self.assertEqual(code, 2)
        self.assertIn("vacuously", alerts[0]["message"])

    def test_missing_filter_column_blocks_not_usage_error(self):
        code, alerts = run([{"kind": "schema", "columns": ["participant"]}],
                           [{"column": "preferred", "equals": "TRUE"}])
        self.assertEqual(code, 2)
        self.assertEqual(alerts[0]["observed"], "missing: preferred")

    def test_missing_table_blocks(self):
        code, _ = run([{"kind": "schema", "columns": ["x"], "table": "absent.tsv"}])
        self.assertEqual(code, 2)

    def test_isolated_contrast_level_blocks(self):
        code, alerts = run([{"kind": "batch_confounding", "batch": "batch", "contrast": "visit",
                             "table": "isolated.tsv"}])
        self.assertEqual(code, 2)
        self.assertEqual([a["observed"] for a in alerts if a["blocking"]], ["56"])

    def test_bad_contract_is_usage_error(self):
        code, _ = run([{"kind": "nonsense"}])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
