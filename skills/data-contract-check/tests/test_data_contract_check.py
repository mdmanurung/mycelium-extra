"""Run: python3 skills/data-contract-check/tests/test_data_contract_check.py"""

import csv
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "data_contract_check.py")
FIXTURES = os.path.join(HERE, "fixtures")


def importable(name):
    try:
        importlib.import_module(name)
        return True
    except Exception:  # an install that fails to import counts as absent
        return False


HAVE_H5PY = importable("h5py")
NO_H5PY = "h5py is not installed; the .h5ad tests need it to build their fixture (uv pip install h5py)"


def invoke(checks, filters=None, table="samples.tsv", root=FIXTURES, as_json=True, env=None):
    """Run the checker from stdin, as the skill does; return (exit code, stdout text)."""
    contract = {"schema": "mycelium-extra.data_contract.v1", "table": table,
                "filters": filters or [], "checks": checks}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(contract, handle)
    try:
        with open(SCRIPT) as source:
            proc = subprocess.Popen(
                [sys.executable, "-", "--contract", handle.name, "--root", root] + (["--json"] if as_json else []),
                stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            out, _ = proc.communicate()
    finally:
        os.unlink(handle.name)
    return proc.returncode, out.decode("utf-8")


def run(checks, filters=None, **kwargs):
    code, out = invoke(checks, filters, **kwargs)
    alerts = json.loads(out)["alerts"] if code != 1 else None
    return code, alerts


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


IMBALANCE = {"kind": "batch_confounding", "batch": "batch", "contrast": "condition", "table": "imbalance.tsv"}


class GradedImbalanceTest(unittest.TestCase):
    """imbalance.tsv: b1 holds 8 of 10 A rows and 5 of 10 B rows; b2 the rest."""

    def test_max_share_warns_with_counts(self):
        code, alerts = run([dict(IMBALANCE, max_share=0.7)])
        self.assertEqual(code, 0)
        self.assertEqual(len(alerts), 1)
        self.assertFalse(alerts[0]["blocking"])
        self.assertEqual(alerts[0]["severity"], "warning")
        self.assertIn("more than 70%", alerts[0]["message"])
        self.assertEqual(alerts[0]["evidence"], ["b1 holds 8 of 10 A rows (80%)"])

    def test_max_share_warning_shows_the_table(self):
        code, out = invoke([dict(IMBALANCE, max_share=0.7)], as_json=False)
        self.assertEqual(code, 0)
        self.assertIn("WARN  checks[0] batch_confounding (20 rows)", out)
        lines = [line.split() for line in out.splitlines()]
        self.assertIn(["b1", "8", "(80%)", "5", "(50%)", "13"], lines)
        self.assertIn(["b2", "2", "(20%)", "5", "(50%)", "7"], lines)
        self.assertIn("warn: a batch holds more than 70%", out)

    def test_share_at_the_limit_does_not_warn(self):
        code, alerts = run([dict(IMBALANCE, max_share=0.8)])
        self.assertEqual((code, alerts), (0, []))

    def test_without_max_share_behaves_as_before_and_still_shows_the_table(self):
        code, out = invoke([IMBALANCE])
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["alerts"], [])
        self.assertEqual(result["checks"][0]["status"], "pass")
        self.assertEqual(result["checks"][0]["cross_table"]["counts"],
                         {"b1": {"A": 8, "B": 5}, "b2": {"A": 2, "B": 5}})
        code, out = invoke([IMBALANCE], as_json=False)
        self.assertIn("PASS  checks[0] batch_confounding (20 rows)", out)
        self.assertIn(["b1", "8", "(80%)", "5", "(50%)", "13"], [line.split() for line in out.splitlines()])

    def test_table_shown_when_the_check_blocks(self):
        code, out = invoke([{"kind": "batch_confounding", "batch": "participant", "contrast": "cohort"}],
                           as_json=False)
        self.assertEqual(code, 2)
        self.assertIn("rows by batch and contrast level", out)
        self.assertIn(["p1", "2", "(50%)", "0", "(0%)", "2"], [line.split() for line in out.splitlines()])

    def test_bad_max_share_is_usage_error(self):
        for bad in (70, 0, "0.7", True, -0.1):
            code, _ = run([dict(IMBALANCE, max_share=bad)])
            self.assertEqual(code, 1, bad)


def read_tsv(name):
    with open(os.path.join(FIXTURES, name), newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_h5ad(path, index, columns):
    """Write a minimal AnnData file (obs only) in anndata >= 0.8's on-disk encoding, with h5py alone.

    columns: list of (name, kind, values); kind is "strings", "categorical", or "int".
    Missing categorical values (NA in the TSV) are code -1, as anndata writes them.
    """
    import h5py
    import numpy as np
    strings = h5py.special_dtype(vlen=str)

    def string_array(group, name, values):
        node = group.create_dataset(name, data=np.array(values, dtype=object), dtype=strings)
        node.attrs["encoding-type"] = "string-array"
        node.attrs["encoding-version"] = "0.2.0"

    with h5py.File(path, "w") as handle:
        handle.attrs["encoding-type"] = "anndata"
        handle.attrs["encoding-version"] = "0.1.0"
        obs = handle.create_group("obs")
        obs.attrs["encoding-type"] = "dataframe"
        obs.attrs["encoding-version"] = "0.2.0"
        obs.attrs["_index"] = index[0]
        obs.attrs["column-order"] = np.array([c[0] for c in columns], dtype=object)
        string_array(obs, index[0], index[1])
        for name, kind, values in columns:
            if kind == "strings":
                string_array(obs, name, values)
            elif kind == "int":
                node = obs.create_dataset(name, data=np.array([int(v) for v in values], dtype="int64"))
                node.attrs["encoding-type"] = "array"
                node.attrs["encoding-version"] = "0.2.0"
            else:
                categories = sorted({v for v in values if v != "NA"})
                group = obs.create_group(name)
                group.attrs["encoding-type"] = "categorical"
                group.attrs["encoding-version"] = "0.2.0"
                group.attrs["ordered"] = False
                group.create_dataset("codes", data=np.array(
                    [-1 if v == "NA" else categories.index(v) for v in values], dtype="int8"))
                string_array(group, "categories", categories)


def samples_h5ad(path):
    rows = read_tsv("samples.tsv")
    write_h5ad(path, ("sample", [r["sample"] for r in rows]), [
        ("participant", "strings", [r["participant"] for r in rows]),
        ("cohort", "categorical", [r["cohort"] for r in rows]),
        ("visit", "int", [r["visit"] for r in rows]),
        ("batch", "categorical", [r["batch"] for r in rows]),
        ("keep", "categorical", [r["keep"] for r in rows]),
    ])


# Every contract the TSV tests above run against samples.tsv.
CASES = [
    ([{"kind": "schema", "columns": ["sample", "participant", "donor"]}], None),
    ([{"kind": "unit_of_replication", "unit": "participant", "group": "cohort", "within": ["visit"]}], None),
    ([{"kind": "unit_of_replication", "unit": "participant", "group": "cohort", "within": ["visit"]}], KEEP),
    ([{"kind": "pairing", "unit": "participant", "within": "visit"}], KEEP),
    ([{"kind": "batch_confounding", "batch": "batch", "contrast": "cohort"}], KEEP),
    ([{"kind": "batch_confounding", "batch": "participant", "contrast": "cohort"}], None),
    ([{"kind": "cohort", "column": "cohort", "levels": ["A", "C"], "rows": 8, "no_missing": ["batch"]}], KEEP),
    ([{"kind": "unit_of_replication", "unit": "participant", "group": "cohort"}],
     [{"column": "keep", "equals": "True"}]),
    ([{"kind": "schema", "columns": ["participant"]}], [{"column": "preferred", "equals": "TRUE"}]),
]


@unittest.skipUnless(HAVE_H5PY, NO_H5PY)
class H5adTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_existing_checks_run_unchanged_on_h5ad(self):
        shutil.copy(os.path.join(FIXTURES, "samples.tsv"), self.root)
        samples_h5ad(os.path.join(self.root, "samples.h5ad"))
        for checks, filters in CASES:
            tsv = invoke(checks, filters, table="samples.tsv", root=self.root)
            h5ad = invoke(checks, filters, table="samples.h5ad", root=self.root)
            self.assertEqual(tsv[0], h5ad[0], checks)
            expected, observed = json.loads(tsv[1]), json.loads(h5ad[1])
            for result in (expected, observed):
                for record in result["alerts"] + result["checks"]:
                    record.pop("table")
            self.assertEqual(expected, observed, checks)

    def test_max_share_on_h5ad_warns_and_shows_the_table(self):
        rows = read_tsv("imbalance.tsv")
        write_h5ad(os.path.join(self.root, "cells.h5ad"), ("sample", [r["sample"] for r in rows]), [
            ("batch", "categorical", [r["batch"] for r in rows]),
            ("condition", "categorical", [r["condition"] for r in rows])])
        check = dict(IMBALANCE, table="cells.h5ad", max_share=0.7)
        code, out = invoke([check], root=self.root, as_json=False)
        self.assertEqual(code, 0)
        self.assertIn("warn: a batch holds more than 70% of a 'condition' level", out)
        self.assertIn("- b1 holds 8 of 10 A rows (80%)", out)
        self.assertIn(["b1", "8", "(80%)", "5", "(50%)", "13"], [line.split() for line in out.splitlines()])

    def test_unrecognised_column_encoding_is_a_gap_for_checks_that_name_it(self):
        import h5py
        path = os.path.join(self.root, "odd.h5ad")
        samples_h5ad(path)
        with h5py.File(path, "a") as handle:
            handle["obs/batch"].attrs["encoding-type"] = "awkward-array"
        code, out = invoke([{"kind": "schema", "columns": ["batch"]},
                            {"kind": "batch_confounding", "batch": "batch", "contrast": "cohort"},
                            {"kind": "pairing", "unit": "participant", "within": "visit"}],
                           KEEP, table="odd.h5ad", root=self.root)
        self.assertEqual(code, 2)  # the pairing check still runs and blocks
        statuses = [c["status"] for c in json.loads(out)["checks"]]
        self.assertEqual(statuses, ["pass", "gap", "block"])
        gap = [a for a in json.loads(out)["alerts"] if a["severity"] == "gap"][0]
        self.assertFalse(gap["blocking"])
        self.assertIn("unrecognised encoding 'awkward-array'", gap["evidence"][0])

    def test_unrecognised_obs_encoding_is_a_gap_not_a_pass(self):
        import h5py
        import numpy as np
        path = os.path.join(self.root, "old.h5ad")
        with h5py.File(path, "w") as handle:  # anndata < 0.7 wrote obs as one compound dataset
            handle.create_dataset("obs", data=np.array([(b"c1", 1)], dtype=[("index", "S2"), ("n", "i4")]))
        code, out = invoke([{"kind": "schema", "columns": ["index"]}], table="old.h5ad", root=self.root)
        self.assertEqual(code, 3)
        result = json.loads(out)
        self.assertEqual(result["checks"][0]["status"], "gap")
        self.assertIn("not in a recognised AnnData encoding", result["alerts"][0]["observed"])

    def test_not_hdf5_is_a_gap(self):
        with open(os.path.join(self.root, "broken.h5ad"), "w") as handle:
            handle.write("not hdf5")
        code, out = invoke([{"kind": "schema", "columns": ["x"]}], table="broken.h5ad", root=self.root)
        self.assertEqual(code, 3)
        self.assertIn("not readable as HDF5", json.loads(out)["alerts"][0]["observed"])

    def test_anndata_07_categorical_reference_is_read(self):
        import h5py
        import numpy as np
        path = os.path.join(self.root, "v07.h5ad")
        strings = h5py.special_dtype(vlen=str)
        with h5py.File(path, "w") as handle:
            obs = handle.create_group("obs")
            obs.attrs["encoding-type"] = "dataframe"
            obs.attrs["encoding-version"] = "0.1.0"
            obs.attrs["_index"] = "_index"
            obs.attrs["column-order"] = np.array(["cohort"], dtype=object)
            obs.create_dataset("_index", data=np.array(["c1", "c2", "c3"], dtype=object), dtype=strings)
            categories = obs.create_dataset("__categories/cohort", data=np.array(["A", "B"], dtype=object),
                                            dtype=strings)
            codes = obs.create_dataset("cohort", data=np.array([0, 1, 1], dtype="int8"))
            codes.attrs["categories"] = categories.ref
        code, alerts = run([{"kind": "cohort", "column": "cohort", "levels": ["A", "B"], "rows": 3}],
                           table="v07.h5ad", root=self.root)
        self.assertEqual((code, alerts), (0, []))

    @unittest.skipUnless(importable("anndata"), "anndata is not installed; the round trip through its writer "
                                                "is optional")
    def test_reads_a_file_anndata_wrote(self):
        import anndata
        import pandas
        rows = read_tsv("imbalance.tsv")
        obs = pandas.DataFrame({"batch": pandas.Categorical([r["batch"] for r in rows]),
                                "condition": [r["condition"] for r in rows]},
                               index=[r["sample"] for r in rows])
        anndata.AnnData(obs=obs).write_h5ad(os.path.join(self.root, "real.h5ad"))
        code, alerts = run([dict(IMBALANCE, table="real.h5ad", max_share=0.7)], root=self.root)
        self.assertEqual(code, 0)
        self.assertEqual(alerts[0]["evidence"], ["b1 holds 8 of 10 A rows (80%)"])


class WithoutH5pyTest(unittest.TestCase):
    """Runs whether or not h5py is installed: a stub on PYTHONPATH makes `import h5py` fail."""

    def test_h5ad_without_h5py_is_a_gap(self):
        root = tempfile.mkdtemp()
        try:
            with open(os.path.join(root, "h5py.py"), "w") as handle:
                handle.write("raise ImportError('h5py hidden by the test')\n")
            with open(os.path.join(root, "cells.h5ad"), "wb") as handle:
                handle.write(b"\x89HDF\r\n\x1a\n")
            env = dict(os.environ, PYTHONPATH=root)
            checks = [{"kind": "schema", "columns": ["batch"]}, dict(IMBALANCE, table="cells.h5ad", max_share=0.7)]
            code, out = invoke(checks, table="cells.h5ad", root=root, env=env)
            self.assertEqual(code, 3)
            result = json.loads(out)
            self.assertEqual([c["status"] for c in result["checks"]], ["gap", "gap"])
            self.assertTrue(all(a["severity"] == "gap" and not a["blocking"] for a in result["alerts"]))
            self.assertIn("h5py cannot be imported", result["alerts"][0]["observed"])
            code, out = invoke(checks, table="cells.h5ad", root=root, env=env, as_json=False)
            self.assertIn("GAP   checks[1] batch_confounding (0 rows)", out)
            self.assertIn("2 gaps", out.splitlines()[0])
        finally:
            shutil.rmtree(root)


if __name__ == "__main__":
    unittest.main()
