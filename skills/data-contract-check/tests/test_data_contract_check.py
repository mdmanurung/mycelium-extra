"""Run: python3 skills/data-contract-check/tests/test_data_contract_check.py"""

import csv
import importlib
import importlib.util
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
            out, err = proc.communicate()
    finally:
        os.unlink(handle.name)
    return proc.returncode, (out + (err if proc.returncode == 1 else b"")).decode("utf-8")


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
        code, out = invoke([{"kind": "schema", "columns": ["donor"], "severity": "warning"}])
        self.assertEqual(code, 1)  # rejected as an unknown key, never run as a softer check
        self.assertIn("does not accept: severity", out)

    def test_misspelled_key_in_a_classic_check_is_a_usage_error(self):
        code, out = invoke([{"kind": "cohort", "column": "cohort", "levles": ["A", "Z"], "min_rows": 1}])
        self.assertEqual(code, 1)
        self.assertIn("does not accept: levles", out)

    def test_all_empty_rows_are_no_samples_and_errors_name_the_file_line(self):
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, "t.csv"), "w") as handle:
                handle.write('id,g\ns1,A\ns2,None\ns3,B\n,\n,\n"q\nx",A,extra\n')
            code, out = invoke([{"kind": "cohort", "column": "g", "min_rows": 4}], table="t.csv", root=root)
            self.assertEqual(code, 2)
            self.assertIn("line 7 has more fields", out)  # the physical line, not the record number
            with open(os.path.join(root, "t.csv"), "w") as handle:
                handle.write("id,g\ns1,A\ns2,None\ns3,B\n,\n,\n")
            code, alerts = run([{"kind": "cohort", "column": "g", "min_rows": 4}], table="t.csv", root=root)
            self.assertEqual(code, 2)
            self.assertEqual(alerts[0]["observed"], "3")

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

    def test_malformed_checks_are_usage_errors_not_silent_relaxations(self):
        cases = [[], [None], ["cohort"], [{"kind": "cohort"}],
                 [{"kind": "cohort", "no_missing": []}],
                 [{"kind": "schema", "columns": "participant"}],
                 [{"kind": "pairing", "unit": "participant", "within": ["visit"]}],
                 [{"kind": "unit_of_replication", "unit": "participant", "group": "cohort",
                   "units_may_span_groups": "false"}],
                 [{"kind": "cohort", "rows": 8.9}],
                 [{"kind": "cohort", "min_rows": -1}],
                 [{"kind": "cohort", "levels": ["A"]}],
                 [{"kind": "pairing", "unit": "participant"}]]
        for checks in cases:
            code, out = invoke(checks)
            self.assertEqual(code, 1, checks)
            self.assertTrue(out.startswith("contract error:"), out)
            self.assertNotIn("Traceback", out)

    def test_nonobject_contracts_are_clear_usage_errors(self):
        for value in (None, [], "contract", 1):
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
                json.dump(value, handle)
            try:
                with open(SCRIPT) as source:
                    proc = subprocess.run([sys.executable, "-", "--contract", handle.name], stdin=source,
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                          universal_newlines=True)
            finally:
                os.unlink(handle.name)
            self.assertEqual(proc.returncode, 1, value)
            self.assertTrue(proc.stderr.startswith("contract error:"), proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

    def test_malformed_filters_are_usage_errors(self):
        for filters in ([{"column": "cohort", "in": "AB"}],
                        [{"column": "cohort", "equals": "A", "not_in": ["B"]}],
                        [None], "cohort"):
            code, out = invoke([{"kind": "cohort", "min_rows": 1}], filters)
            self.assertEqual(code, 1, filters)
            self.assertTrue(out.startswith("contract error:"), out)

    def test_scalar_cohort_level_and_empty_optional_columns_are_supported(self):
        code, alerts = run([{"kind": "cohort", "column": "cohort", "levels": "missing",
                             "no_missing": []}])
        self.assertEqual(code, 2)
        self.assertEqual(alerts[0]["expected"], "missing")
        code, _ = run([{"kind": "unit_of_replication", "unit": "participant", "group": "cohort",
                         "within": []}], KEEP)
        self.assertEqual(code, 2)  # repeated visits still count as repeated units

    def test_duplicate_headers_do_not_overwrite_a_required_column(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        with open(os.path.join(folder, "duplicate.tsv"), "w") as handle:
            handle.write("cohort\tcohort\nA\tB\n")
        code, out = invoke([{"kind": "cohort", "column": "cohort", "levels": ["B"]}],
                           root=folder, table="duplicate.tsv")
        self.assertEqual(code, 3)
        self.assertIn("duplicate", json.loads(out)["alerts"][0]["observed"])


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

    def test_malformed_categorical_codes_are_unreadable_gaps(self):
        import h5py
        import numpy as np
        path = os.path.join(self.root, "samples.h5ad")
        for codes in ([0.5], ["x"], [True], [-2], [2], [[0]], 0):
            with self.subTest(codes=codes):
                write_h5ad(path, ("sample", ["s1"]), [("cohort", "categorical", ["A"])])
                with h5py.File(path, "a") as handle:
                    del handle["obs/cohort/codes"]
                    handle["obs/cohort"].create_dataset("codes", data=np.array(codes,
                        dtype=h5py.string_dtype() if codes == ["x"] else None))
                code, out = invoke([{"kind": "cohort", "column": "cohort", "levels": ["A"]}],
                                   table="samples.h5ad", root=self.root)
                self.assertEqual(code, 3, out)
                self.assertEqual(json.loads(out)["alerts"][0]["severity"], "gap")

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


class ProfileOnlyTest(unittest.TestCase):
    """--profile-only describes one table. It is not a check: no pass word, no contract result, bounded, private."""
    META = os.path.join(HERE, "..", "..", "..", "tests", "fixtures", "validation-recipes", "sample_metadata.tsv")

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        shutil.copy(self.META, os.path.join(self.dir, "meta.tsv"))

    def write(self, name, data):
        with open(os.path.join(self.dir, name), "wb") as handle:
            handle.write(data if isinstance(data, bytes) else data.encode("utf-8"))

    def profile(self, table="meta.tsv", as_json=True, **spec):
        spec = dict({"schema": "mycelium-extra.data-profile-request.v1", "table": table}, **spec)
        self.write("spec.json", json.dumps(spec))
        with open(SCRIPT) as source:
            proc = subprocess.Popen([sys.executable, "-", "--profile-only", "--profile-spec",
                                     os.path.join(self.dir, "spec.json"), "--root", self.dir] + (["--json"] if as_json else []),
                                    stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = proc.communicate()
        self.assertNotIn(b"Traceback", err)
        return proc.returncode, out.decode("utf-8"), err.decode("utf-8")

    def test_a_complete_table_is_described_with_true_totals(self):  # P2-01
        code, out, _ = self.profile(unit_key="participant_id", row_key="sample_id", group_by=["group"],
                                    missingness_columns=["response", "batch"])
        result = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual((result["inspection"], result["coverage"]["rows_total"]), ("complete", 12))
        self.assertEqual(result["descriptive"]["distinct_units_inspected"], 6)
        self.assertEqual(result["descriptive"]["group_counts"], [{"group": "Control", "count": 6}, {"group": "Vaccine", "count": 6}])
        self.assertEqual([m["missing"] for m in result["descriptive"]["missingness"]], [1, 0])
        self.assertNotIn("status", result)

    def test_a_profile_never_says_passed_and_the_text_is_short(self):
        code, out, _ = self.profile(as_json=False, unit_key="participant_id", group_by=["group"], missingness_columns=["response"])
        self.assertEqual(code, 0)
        self.assertIn("descriptive, not a validation result", out)
        for word in ("pass", "CONFORMS", "qualified"):
            self.assertNotIn(word, out)
        self.assertLessEqual(len(out.splitlines()), 12)

    def test_a_row_budget_makes_the_profile_partial_and_the_total_unknown(self):  # P2-02
        result = json.loads(self.profile(max_rows_inspected=5, group_by=["group"])[1])
        self.assertEqual((result["inspection"], result["coverage"]["rows_inspected"], result["coverage"]["rows_total"]),
                         ("partial", 5, None))
        self.assertIn("PARTIAL", self.profile(as_json=False, max_rows_inspected=5)[1])

    def test_a_budget_equal_to_the_row_count_is_still_complete(self):
        self.assertEqual(json.loads(self.profile(max_rows_inspected=12)[1])["inspection"], "complete")

    def test_a_large_table_stops_at_the_budget(self):
        self.write("big.tsv", "id\tgroup\n" + "".join("s{}\tA\n".format(i) for i in range(50000)))
        result = json.loads(self.profile("big.tsv", max_rows_inspected=100, group_by=["group"])[1])
        self.assertEqual((result["inspection"], result["coverage"]["rows_inspected"]), ("partial", 100))

    def test_more_groups_than_the_cap_is_not_a_group_table(self):  # P2-03
        result = json.loads(self.profile(group_by=["sample_id"], max_groups=3)[1])
        self.assertIsNone(result["descriptive"]["group_counts"])
        self.assertIn("more than 3 groups", result["descriptive"]["group_counts_omitted"])

    def test_small_cells_and_the_group_names_behind_them_are_not_shown(self):  # P2-04
        code, out, _ = self.profile(as_json=False, group_by=["group", "visit"], missingness_columns=["response"])
        self.assertEqual(code, 0)
        for name in ("Control", "Vaccine"):
            self.assertNotIn(name, out)
        self.assertIn("omitted", out)

    def test_the_suppression_limit_is_what_hides_the_cells(self):
        shown = json.loads(self.profile(group_by=["group", "visit"], small_cell_suppression=1)[1])
        self.assertEqual(len(shown["descriptive"]["group_counts"]), 4)  # the guard removed: three-row cells appear
        self.assertIsNone(json.loads(self.profile(group_by=["group", "visit"], small_cell_suppression=5)[1])["descriptive"]["group_counts"])

    def test_one_hidden_cell_is_not_left_to_subtraction(self):
        rows = "id\tgroup\n" + "".join("a{}\tA\n".format(i) for i in range(20)) + "".join("b{}\tB\n".format(i) for i in range(2))
        self.write("t.tsv", rows)
        result = json.loads(self.profile("t.tsv", group_by=["group"])[1])
        self.assertIsNone(result["descriptive"]["group_counts"])
        self.assertNotIn('"B"', json.dumps(result))

    def test_missing_by_group_shows_only_when_no_count_is_small(self):
        rows = "id\tgroup\tresp\n" + "".join("a{}\tA\t1\n".format(i) for i in range(10)) + \
               "".join("b{}\tB\t{}\n".format(i, "NA" if i < 6 else "2") for i in range(10))
        self.write("t.tsv", rows)
        entry = json.loads(self.profile("t.tsv", group_by=["group"], missingness_columns=["resp"])[1])["descriptive"]["missingness"][0]
        self.assertEqual(entry["by_group"], [{"group": "A", "missing": 0}, {"group": "B", "missing": 6}])
        self.write("u.tsv", rows.replace("b0\tB\tNA", "b0\tB\t2").replace("b1\tB\tNA", "b1\tB\t2"))  # 4 missing is shown; fewer than 5 is not
        entry = json.loads(self.profile("u.tsv", group_by=["group"], missingness_columns=["resp"])[1])["descriptive"]["missingness"][0]
        self.assertIsNone(entry["by_group"])

    def test_a_group_per_unit_is_an_identifier_and_is_not_shown(self):  # P2-12
        self.write("t.tsv", "pid\tcopy\n" + "".join("p{}\tp{}\n".format(i % 4, i % 4) for i in range(40)))
        result = json.loads(self.profile("t.tsv", unit_key="pid", group_by=["copy"])[1])
        self.assertIsNone(result["descriptive"]["group_counts"])
        self.assertNotIn("p0", json.dumps(result))
        code, _, err = self.profile("t.tsv", unit_key="pid", group_by=["pid"])
        self.assertEqual(code, 1)
        self.assertIn("identify individuals", err)

    def test_nothing_unreadable_is_a_clean_profile(self):  # P2-05, P2-06, P2-07, P2-08
        self.write("bad_utf8.tsv", b"id\tg\nS\xff\tA\n")
        self.write("ragged.tsv", "id\tg\nS1\tA\tEXTRA\n")
        self.write("quote.tsv", 'id\tg\nS1\t"A\nS2\tB\n')
        self.write("dup.tsv", "id\tid\nS1\tA\n")
        self.write("empty.tsv", "")
        self.write("x.h5ad", b"not hdf5")
        self.write("x.xlsx", b"PK")
        for table in ("bad_utf8.tsv", "ragged.tsv", "quote.tsv", "dup.tsv", "empty.tsv", "x.h5ad", "x.xlsx", "absent.tsv"):
            code, out, _ = self.profile(table, group_by=["g"])
            result = json.loads(out)
            self.assertEqual((code, result["inspection"]), (3, "unavailable"), table)
            self.assertIn("reason", result)
            self.assertNotIn("descriptive", result)
        code, out, _ = self.profile(group_by=["nope"])
        self.assertEqual((code, json.loads(out)["inspection"]), (3, "unavailable"))
        self.assertIn("nope", json.loads(out)["reason"])

    def test_a_bad_request_is_a_usage_error_that_reads_nothing(self):  # P2-11
        for spec in ({"bogus": 1}, {"max_rows_inspected": -1}, {"max_rows_inspected": True}, {"max_rows_inspected": 10 ** 12},
                     {"max_groups": 0}, {"small_cell_suppression": "5"}, {"group_by": "group"}, {"group_by": ["a"] * 2},
                     {"group_by": list("abcde")}, {"table": ""}):
            code, out, err = self.profile(**spec)
            self.assertEqual((code, out), (1, ""), spec)
            self.assertIn("profile error", err)
        self.write("spec.json", json.dumps({"schema": "wrong", "table": "meta.tsv"}))
        self.write("notjson.json", "{")
        for name in ("spec.json", "notjson.json", "missing.json"):
            with open(SCRIPT) as source:
                proc = subprocess.run([sys.executable, "-", "--profile-only", "--profile-spec", os.path.join(self.dir, name)],
                                      stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(proc.returncode, 1, name)

    def test_the_ordinary_command_line_is_unchanged(self):  # P2-10
        with open(SCRIPT) as source:
            proc = subprocess.run([sys.executable, "-", "--root", self.dir], stdin=source,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stderr.splitlines()[0], "usage: - [-h] --contract CONTRACT [--root ROOT] [--json]"
                         " [--result-json PATH]")
        self.assertIn("the following arguments are required: --contract", proc.stderr)
        code, out = invoke([{"kind": "cohort", "column": "cohort", "levels": ["A", "B"]}])
        self.assertIn(code, (0, 2, 3))
        self.assertEqual(set(json.loads(out)), {"checks", "alerts"})


class TableReaderTest(unittest.TestCase):
    """CSV/TSV shape handling follows Mycelium's checker: malformed shape blocks, unreadable bytes are gaps."""

    SCHEMA = [{"kind": "schema", "columns": ["sample_id", "group"]}, {"kind": "cohort", "rows": 2}]

    def table(self, name, content):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        with open(os.path.join(folder, name), "wb") as handle:
            handle.write(content if isinstance(content, bytes) else content.encode("utf-8"))
        return folder

    def check(self, name, content, checks=None):
        code, out = invoke(checks or self.SCHEMA, root=self.table(name, content), table=name)
        self.assertIn(code, (0, 2, 3), out)  # never a crash (exit 1 is a usage error or traceback)
        return code, json.loads(out)

    def test_ragged_extra_field_blocks_every_check(self):  # roadmap F11
        code, result = self.check("ragged.tsv", "sample_id\tgroup\nS1\tA\textra\nS2\tB\n")
        self.assertEqual(code, 2)
        self.assertEqual([c["status"] for c in result["checks"]], ["block", "block"])
        self.assertIn("line 2 has more fields than the header (3 > 2)", result["alerts"][0]["observed"])

    def test_empty_extra_field_blocks_too(self):
        code, _ = self.check("trailing.csv", "sample_id,group\nS1,A,\nS2,B\n")
        self.assertEqual(code, 2)

    def test_short_row_is_padded_with_missing_values(self):
        checks = [{"kind": "cohort", "no_missing": ["group"]}]
        code, result = self.check("short.tsv", "sample_id\tgroup\nS1\tA\nS2\n", checks)
        self.assertEqual(code, 2)
        self.assertEqual(result["alerts"][0]["observed"], "1 of 2 rows")
        checks = [{"kind": "unit_of_replication", "unit": "sample_id", "group": "group"},
                  {"kind": "pairing", "unit": "sample_id", "within": "group"},
                  {"kind": "batch_confounding", "batch": "group", "contrast": "sample_id"}]
        code, result = self.check("short.tsv", "sample_id\tgroup\nS1\tA\nS2\n", checks)
        self.assertIn("warning", [a["severity"] for a in result["alerts"]])  # missing, not an AttributeError

    def test_invalid_utf8_is_a_gap_not_a_pass(self):
        code, result = self.check("bytes.tsv", b"sample_id\tgroup\np\xff\tA\np\xfe\tB\n")
        self.assertEqual(code, 3)
        self.assertEqual({c["status"] for c in result["checks"]}, {"gap"})
        self.assertIn("not valid UTF-8", result["alerts"][0]["observed"])

    def test_unterminated_quote_blocks(self):
        code, result = self.check("quote.csv", 'sample_id,group\nS1,"A\nS2,B\n')
        self.assertEqual(code, 2)
        self.assertIn("cannot be parsed", result["alerts"][0]["observed"])

    def test_unsupported_extension_is_a_gap(self):
        for name in ("table.xlsx", "table.dat", "table"):
            code, result = self.check(name, "sample_id\tgroup\nS1\tA\nS2\tB\n")
            self.assertEqual(code, 3, name)
            self.assertIn("unsupported table format", result["alerts"][0]["observed"])

    def test_valid_tables_pass(self):
        for name, delimiter in (("t.csv", ","), ("t.tsv", "\t"), ("t.tab", "\t"), ("t.TXT", "\t")):
            content = "\ufeffsample_id{0}group\n\nS1{0}A\nS2{0}B\n".format(delimiter)  # BOM and a blank line
            code, result = self.check(name, content)
            self.assertEqual((code, result["alerts"]), (0, []), name)

    def test_quoted_delimiter_and_newline_are_one_field(self):
        content = 'sample_id,group\n"S,1","A\nB"\nS2,C\n'
        code, result = self.check("quoted.csv", content, [{"kind": "cohort", "column": "group", "levels": ["A\nB"]}])
        self.assertEqual((code, result["alerts"]), (0, []))

    def test_date_like_identifiers_are_not_corruption(self):
        content = "sample_id\tgroup\n2024-01-05\tA\n01/02/2024\tB\nMar-1\tB\n"
        checks = [{"kind": "cohort", "column": "group", "levels": ["A", "B"], "rows": 3, "no_missing": ["sample_id"]}]
        code, result = self.check("dates.tsv", content, checks)
        self.assertEqual((code, result["alerts"]), (0, []))

    def test_blank_header_fields_are_not_duplicates(self):
        code, _ = self.check("blank.tsv", "sample_id\tgroup\t\t\nS1\tA\t\t\nS2\tB\t\t\n")
        self.assertEqual(code, 0)

    def test_h5ad_bytes_decode_strictly(self):
        spec = importlib.util.spec_from_file_location("data_contract_check_under_test", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.text(b"p1"), "p1")
        with self.assertRaises(module.TableGap):
            module.text(b"p\xff")  # a replacement character would merge p\xff and p\xfe


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


class TempTables(unittest.TestCase):
    """A scratch directory of tables, and a runner that also asks for the machine-readable result."""

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.root)

    def put(self, name, text):
        path = os.path.join(self.root, name)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        return path

    def result_run(self, checks, table="t.tsv", filters=None, env=None, contract=None):
        """Run the contract with --result-json; return (exit code, parsed result or None, stdout/stderr text)."""
        contract = contract or {"schema": "mycelium-extra.data_contract.v1", "table": table,
                                "filters": filters or [], "checks": checks}
        contract_path = self.put("contract.json", json.dumps(contract))
        result_path = os.path.join(self.root, "result.json")
        with open(SCRIPT) as source:
            proc = subprocess.Popen(
                [sys.executable, "-", "--contract", contract_path, "--root", self.root, "--result-json", result_path],
                stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            out, err = proc.communicate()
        result = None
        if os.path.exists(result_path):
            with open(result_path, encoding="utf-8") as handle:
                result = json.load(handle)
        return proc.returncode, result, (out + err).decode("utf-8")


def sha256_of(path):
    import hashlib
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


class ResultJsonTest(TempTables):
    TSV = "sample_id\tgroup\nS1\tA\nS2\tB\n"

    def test_a_blocking_run_records_identities_statuses_and_messages(self):
        table = self.put("t.tsv", self.TSV)
        code, result, _ = self.result_run([{"kind": "schema", "columns": ["sample_id"]},
                                           {"kind": "cohort", "rows": 3, "label": "three rows"}])
        self.assertEqual(code, 2)
        self.assertEqual(result["schema"], "mycelium-extra.contract_result.v1")
        self.assertEqual(result["contract"]["sha256"], sha256_of(os.path.join(self.root, "contract.json")))
        self.assertEqual(result["tables"][0]["role"], "table")
        self.assertEqual(result["tables"][0]["sha256"], sha256_of(table))
        self.assertEqual(result["tables"][0]["identity"], "sha256")
        self.assertEqual([c["status"] for c in result["checks"]], ["pass", "block"])
        self.assertEqual([c["id"] for c in result["checks"]], ["checks[0]", "checks[1]"])
        self.assertEqual(result["checks"][0]["message"], "passed on 2 rows")
        self.assertEqual(result["checks"][1]["message"], "row count differs from the plan")
        self.assertEqual(result["checks"][1]["alerts"][0]["observed"], "2")
        self.assertEqual((result["exit_code"], result["status"], result["runnable"]), (2, "block", "all_ran"))

    def test_a_warnings_only_run_keeps_each_warning_and_exit_zero(self):
        shutil.copy(os.path.join(FIXTURES, "imbalance.tsv"), self.root)
        code, result, _ = self.result_run([dict(IMBALANCE, table="imbalance.tsv", max_share=0.7),
                                           {"kind": "schema", "columns": ["batch"], "table": "imbalance.tsv"}])
        self.assertEqual(code, 0)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual([c["status"] for c in result["checks"]], ["warn", "pass"])
        warning = result["checks"][0]["alerts"][0]
        self.assertEqual((warning["severity"], warning["blocking"]), ("warning", False))
        self.assertIn("a batch holds more than 70%", warning["message"])
        self.assertEqual(result["status"], "warn")
        self.assertEqual(result["runnable"], "all_ran")

    def test_a_missing_table_is_not_a_pass_and_is_not_run(self):
        code, result, _ = self.result_run([{"kind": "schema", "columns": ["a"]}], table="gone.tsv")
        self.assertEqual(code, 2)
        self.assertEqual(result["checks"][0]["runnable"], "table_missing")
        self.assertEqual(result["tables"][0]["identity"], "absent")
        self.assertEqual((result["runnable"], result["not_run"]), ("incomplete", ["checks[0]"]))

    def test_an_unreadable_table_is_a_gap_distinct_from_pass(self):
        self.put("t.xlsx", "not a table")
        code, result, _ = self.result_run([{"kind": "schema", "columns": ["a"]}], table="t.xlsx")
        self.assertEqual(code, 3)
        self.assertEqual((result["checks"][0]["status"], result["checks"][0]["runnable"]),
                         ("gap", "table_unreadable"))
        self.assertEqual(result["status"], "gap")

    def test_a_missing_optional_reader_is_distinct_from_an_unreadable_table(self):
        self.put("h5py.py", "raise ImportError('h5py hidden by the test')\n")
        self.put("cells.h5ad", "\x89HDF")
        code, result, _ = self.result_run([{"kind": "schema", "columns": ["a"]}], table="cells.h5ad",
                                          env=dict(os.environ, PYTHONPATH=self.root))
        self.assertEqual(code, 3)
        self.assertEqual(result["checks"][0]["runnable"], "optional_reader_missing")
        self.assertEqual(result["checks"][0]["status"], "gap")

    def test_a_malformed_table_blocks_and_says_so(self):
        self.put("t.tsv", "a\tb\n1\t2\t3\n")
        code, result, _ = self.result_run([{"kind": "schema", "columns": ["a"]}])
        self.assertEqual((code, result["checks"][0]["runnable"]), (2, "table_malformed"))

    def test_a_contract_error_writes_an_error_result_and_exits_one(self):
        self.put("t.tsv", self.TSV)
        code, result, text = self.result_run([{"kind": "nonsense"}])
        self.assertEqual(code, 1)
        self.assertIn("unknown check kind", text)
        self.assertEqual((result["status"], result["exit_code"], result["runnable"]), ("error", 1, "contract_error"))
        self.assertIn("unknown check kind", result["error"])
        self.assertEqual(result["checks"], [])
        self.assertEqual(result["contract"]["sha256"], sha256_of(os.path.join(self.root, "contract.json")))

    def test_check_ids_are_declared_unique_and_reported(self):
        self.put("t.tsv", self.TSV)
        code, result, _ = self.result_run([{"kind": "cohort", "rows": 2, "id": "rows-24"}])
        self.assertEqual((code, result["checks"][0]["id"]), (0, "rows-24"))
        code, result, _ = self.result_run([{"kind": "cohort", "rows": 2, "id": "x"},
                                           {"kind": "schema", "columns": ["group"], "id": "x"}])
        self.assertEqual(code, 1)
        code, _, _ = self.result_run([{"kind": "cohort", "rows": 2, "id": ""}])
        self.assertEqual(code, 1)

    def test_no_result_file_without_the_flag(self):
        self.put("t.tsv", self.TSV)
        code, _ = run([{"kind": "cohort", "rows": 2}], table="t.tsv", root=self.root)
        self.assertEqual(code, 0)
        self.assertFalse(os.path.exists(os.path.join(self.root, "result.json")))

    def test_a_result_that_cannot_be_written_fails_loudly(self):
        self.put("t.tsv", self.TSV)
        contract = self.put("c.json", json.dumps({"schema": "mycelium-extra.data_contract.v1", "table": "t.tsv",
                                                  "checks": [{"kind": "cohort", "rows": 2}]}))
        with open(SCRIPT) as source:
            proc = subprocess.Popen([sys.executable, "-", "--contract", contract, "--root", self.root,
                                     "--result-json", os.path.join(self.root, "no", "such", "dir", "r.json")],
                                    stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _, err = proc.communicate()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("cannot write the result file", err.decode())

    def test_a_file_too_large_to_hash_gets_a_stated_weaker_identity(self):
        spec = importlib.util.spec_from_file_location("data_contract_check_identity", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        table = self.put("t.tsv", self.TSV)
        module.HASH_LIMIT = 4
        identity = module.file_identity(table)
        self.assertEqual((identity["sha256"], identity["identity"]), (None, "size+mtime_ns"))
        self.assertEqual(identity["size"], len(self.TSV))


class UniqueKeyTest(TempTables):
    def keys(self, text, columns=("sample_id",), filters=None):
        self.put("t.tsv", text)
        return run([{"kind": "unique_key", "columns": list(columns)}], filters, table="t.tsv", root=self.root)

    def test_unique_nonempty_keys_pass(self):
        code, alerts = self.keys("sample_id\tg\nS1\tA\nS2\tA\n")
        self.assertEqual((code, alerts), (0, []))

    def test_a_repeated_key_blocks_and_names_it(self):
        code, alerts = self.keys("sample_id\tg\nS1\tA\nS2\tA\nS1\tB\n")
        self.assertEqual(code, 2)
        self.assertEqual(alerts[0]["message"], "the key (sample_id) is not unique")
        self.assertEqual(alerts[0]["evidence"], ["S1 (2 rows)"])

    def test_an_empty_key_blocks_even_though_other_checks_drop_such_rows(self):
        code, alerts = self.keys("sample_id\tg\nS1\tA\n\tB\nNA\tC\n")
        self.assertEqual(code, 2)
        self.assertIn("has empty or missing values", alerts[0]["message"])
        self.assertEqual(alerts[0]["observed"], "2 of 3 rows")

    def test_a_composite_key_is_unique_as_a_whole(self):
        self.assertEqual(self.keys("a\tb\n1\tx\n1\ty\n2\tx\n", columns=("a", "b"))[0], 0)
        self.assertEqual(self.keys("a\tb\n1\tx\n1\tx\n", columns=("a", "b"))[0], 2)
        self.assertEqual(self.keys("a\tb\n1\tx\n1\ty\n", columns=("a",))[0], 2)

    def test_filters_decide_which_rows_must_be_unique(self):
        text = "sample_id\tkeep\nS1\tTRUE\nS1\tFALSE\n"
        self.assertEqual(self.keys(text)[0], 2)
        self.assertEqual(self.keys(text, filters=KEEP)[0], 0)

    def test_an_absent_key_column_blocks_and_bad_syntax_is_a_usage_error(self):
        self.assertEqual(self.keys("a\tb\n1\t2\n", columns=("nope",))[0], 2)
        self.assertEqual(run([{"kind": "unique_key"}], table="t.tsv", root=self.root)[0], 1)
        self.assertEqual(run([{"kind": "unique_key", "columns": []}], table="t.tsv", root=self.root)[0], 1)
        self.assertEqual(run([{"kind": "unique_key", "columns": ["a"], "severity": "warn"}],
                             table="t.tsv", root=self.root)[0], 1)


FIXTURE_PROJECT = os.path.join(HERE, "..", "..", "..", "tests", "fixtures", "mycelium-project")
FIXTURE_COUNTS = os.path.join(FIXTURE_PROJECT, "data", "processed", "vaccine-cohort", "counts.tsv")
SOFTENERS = [{"severity": "warn"}, {"blocking": False}, {"level": "warning"}]


def alignment(**extra):
    return dict({"kind": "sample_alignment", "key": "sample_id",
                 "reference": {"path": "meta.tsv", "column": "sample_id"}}, **extra)


class SampleAlignmentTest(TempTables):
    META = "sample_id\tdonor\nS1\tD1\nS2\tD2\nS3\tD3\n"

    def go(self, table_text, checks=None, **kwargs):
        self.put("meta.tsv", self.META)
        self.put("t.tsv", table_text)
        return self.result_run(checks or [alignment()], table="t.tsv", **kwargs)

    def test_a_mis_keyed_table_passes_every_existing_check_but_blocks_here(self):
        wrong = "sample_id\tdonor\nS1\tD1\nS2\tD2\nS9\tD3\n"
        existing = [{"kind": "schema", "columns": ["sample_id", "donor"]}, {"kind": "cohort", "rows": 3}]
        code, result, _ = self.go(wrong, existing)
        self.assertEqual(code, 0)  # the miss: nothing compares the keys with anything independent
        code, result, _ = self.go(wrong)
        self.assertEqual(code, 2)
        messages = [a["message"] for a in result["checks"][0]["alerts"]]
        self.assertIn("keys in the table but not in the independent list", messages)
        self.assertIn("keys in the independent list but not in the table", messages)
        evidence = [e for a in result["checks"][0]["alerts"] for e in a.get("evidence", [])]
        self.assertEqual(sorted(evidence), ["'S3'", "'S9'"])

    def test_the_same_keys_in_another_order_pass_and_the_limit_is_printed(self):
        code, result, _ = self.go("sample_id\tdonor\nS3\tD3\nS1\tD1\nS2\tD2\n")
        self.assertEqual((code, result["checks"][0]["status"]), (0, "pass"))
        note = result["checks"][0]["note"]
        self.assertIn("order is not compared", note)
        self.assertIn("no failure for keyed data", note)
        self.assertIn("shuffle-invariance", note)  # equal key sets do not show the analysis uses them correctly

    def test_a_different_count_blocks(self):
        code, result, _ = self.go("sample_id\tdonor\nS1\tD1\nS2\tD2\n")
        messages = [a["message"] for a in result["checks"][0]["alerts"]]
        self.assertEqual(code, 2)
        self.assertIn("the table and the independent list hold different numbers of keys", messages)

    def test_repeated_and_empty_keys_block_on_either_side(self):
        code, result, _ = self.go("sample_id\tdonor\nS1\tD1\nS1\tD2\n\tD3\nS2\tD2\nS3\tD3\n")
        messages = [a["message"] for a in result["checks"][0]["alerts"]]
        self.assertEqual(code, 2)
        self.assertIn("the table repeats keys", messages)
        self.assertIn("the table has empty or missing keys", messages)
        self.put("meta.tsv", self.META + "S3\tD3\n")
        code, result, _ = self.result_run([alignment()], table="t.tsv")
        self.assertIn("the independent list repeats keys", [a["message"] for a in result["checks"][0]["alerts"]])

    def test_header_keys_compare_a_matrix_header_with_the_list(self):
        self.put("meta.tsv", self.META)
        self.put("m.tsv", "gene\tS2\tS1\tS3\nG1\t1\t2\t3\n")
        check = {"kind": "sample_alignment", "header_keys": True, "exclude": ["gene"],
                 "reference": {"path": "meta.tsv", "column": "sample_id"}}
        self.assertEqual(self.result_run([check], table="m.tsv")[0], 0)
        self.put("m.tsv", "gene\tS2\tS1\tS4\nG1\t1\t2\t3\n")
        code, result, _ = self.result_run([check], table="m.tsv")
        self.assertEqual(code, 2)
        evidence = [e for a in result["checks"][0]["alerts"] for e in a.get("evidence", [])]
        self.assertEqual(sorted(evidence), ["'S3'", "'S4'"])

    def test_a_plain_list_and_reference_filters_are_supported(self):
        self.put("list.txt", "# keys\nS1\nS2\n\nS3\n")
        self.put("t.tsv", "sample_id\tdonor\nS1\tD1\nS2\tD2\nS3\tD3\n")
        check = alignment(reference={"path": "list.txt", "lines": True})
        self.assertEqual(self.result_run([check], table="t.tsv")[0], 0)
        self.put("meta.tsv", "sample_id\tkeep\nS1\tTRUE\nS2\tTRUE\nS3\tFALSE\n")
        check = alignment(reference={"path": "meta.tsv", "column": "sample_id", "filters": KEEP})
        code, result, _ = self.result_run([check], table="t.tsv")
        self.assertEqual(code, 2)  # S3 is excluded by the list's filter but present in the table

    def test_agreeing_values_catch_swapped_labels(self):
        swapped = "sample_id\tdonor\nS1\tD2\nS2\tD1\nS3\tD3\n"
        self.assertEqual(self.go(swapped)[0], 0)  # the key sets match, so the plain check passes
        code, result, _ = self.go(swapped, [alignment(agree_on=["donor"])])
        self.assertEqual(code, 2)
        self.assertEqual(result["checks"][0]["alerts"][0]["evidence"],
                         ["S1: donor is D2 in the table but D1 in the list",
                          "S2: donor is D1 in the table but D2 in the list"])
        self.assertEqual(self.go(self.META, [alignment(agree_on=["donor"])])[0], 0)

    def test_an_unusable_reference_is_never_a_pass(self):
        self.put("t.tsv", self.META)
        code, result, _ = self.result_run([alignment()], table="t.tsv")  # meta.tsv absent
        self.assertEqual((code, result["checks"][0]["runnable"]), (2, "reference_unusable"))
        self.put("meta.xlsx", "x")
        code, result, _ = self.result_run([alignment(reference={"path": "meta.xlsx", "column": "k"})],
                                          table="t.tsv")
        self.assertEqual((code, result["checks"][0]["status"], result["checks"][0]["runnable"]),
                         (3, "gap", "reference_unreadable"))
        self.put("meta.tsv", "other\nS1\n")
        code, result, _ = self.result_run([alignment()], table="t.tsv")
        self.assertEqual((code, result["checks"][0]["runnable"]), (2, "reference_unusable"))

    def test_a_reference_that_is_the_table_itself_is_a_usage_error(self):
        self.put("t.tsv", self.META)
        code, result, text = self.result_run([alignment(reference={"path": "t.tsv", "column": "sample_id"})],
                                             table="t.tsv")
        self.assertEqual(code, 1)
        self.assertIn("independent file", text)
        self.assertEqual((result["status"], result["checks"]), ("error", []))  # refused before anything ran

    def test_syntax_errors_and_softeners_are_usage_errors(self):
        self.put("t.tsv", self.META)
        bad = [{"kind": "sample_alignment", "reference": {"path": "meta.tsv", "column": "sample_id"}},
               alignment(header_keys=True), alignment(exclude=["x"]), alignment(agree_on="donor"),
               alignment(reference={"path": "meta.tsv"}),
               alignment(reference={"path": "meta.tsv", "column": "a", "lines": True}),
               alignment(reference={"path": "meta.tsv", "lines": True}, agree_on=["donor"]),
               {"kind": "sample_alignment", "key": "sample_id"}] + [alignment(**s) for s in SOFTENERS]
        for check in bad:
            self.assertEqual(self.result_run([check], table="t.tsv")[0], 1, check)

    @unittest.skipUnless(os.path.exists(FIXTURE_COUNTS), "the fixture project is not present")
    def test_the_fixture_counts_columns_against_its_metadata(self):
        meta = os.path.join(FIXTURE_PROJECT, "data", "processed", "vaccine-cohort", "sample_metadata.tsv")
        check = {"kind": "sample_alignment", "header_keys": True, "exclude": ["gene"],
                 "reference": {"path": meta, "column": "sample_id"}}
        code, result, _ = self.result_run([check], table=FIXTURE_COUNTS)
        self.assertEqual(code, 0)
        # the analysis keeps only preferred acquisitions: the matrix still holds the rerun column
        check["reference"]["filters"] = [{"column": "preferred_acquisition", "equals": "TRUE"}]
        code, result, _ = self.result_run([check], table=FIXTURE_COUNTS)
        self.assertEqual(code, 2)
        self.assertEqual([e for a in result["checks"][0]["alerts"] for e in a.get("evidence", [])],
                         ["'D03_day28_rerun'"])


class IdentifiersTest(TempTables):
    NAMESPACE = "MARCHF1\nSEPTIN7\nMX1\n"

    def go(self, table_text, check=None, namespace=NAMESPACE):
        self.put("ns.txt", namespace)
        self.put("t.tsv", table_text)
        check = check or {"kind": "identifiers", "column": "gene", "namespace": {"path": "ns.txt", "lines": True}}
        return self.result_run([check], table="t.tsv")

    def test_identifiers_inside_the_namespace_pass(self):
        code, result, _ = self.go("gene\tn\nMX1\t1\nSEPTIN7\t2\n")
        self.assertEqual((code, result["checks"][0]["status"]), (0, "pass"))

    def test_date_rewritten_symbols_outside_the_namespace_block_and_are_not_repaired(self):
        code, result, _ = self.go("gene\tn\nMX1\t1\n1-Mar\t2\n7-Sep\t3\n")
        alert_ = result["checks"][0]["alerts"][0]
        self.assertEqual(code, 2)
        self.assertEqual(alert_["message"], "identifiers that are not in the declared namespace")
        self.assertEqual(alert_["evidence"], ["'1-Mar'", "'7-Sep'"])
        self.assertNotIn("MARCHF1", json.dumps(result["checks"][0]["alerts"]))  # no guessed repair

    def test_a_date_like_string_the_namespace_lists_is_legitimate(self):
        self.assertEqual(self.go("gene\n1-Mar\n", namespace="1-Mar\nMX1\n")[0], 0)

    def test_matching_is_exact_not_case_or_space_folded(self):
        code, result, _ = self.go("gene\nmx1\n MX1\n")
        self.assertEqual(code, 2)
        self.assertEqual(result["checks"][0]["alerts"][0]["evidence"], ["' MX1'", "'mx1'"])

    def test_duplicates_and_empties_block_with_or_without_a_namespace(self):
        for check in (None, {"kind": "identifiers", "column": "gene"}):
            code, result, _ = self.go("gene\nMX1\nMX1\n\nNA\n", check)
            messages = [a["message"] for a in result["checks"][0]["alerts"]]
            self.assertEqual(code, 2)
            self.assertIn("'gene' repeats identifiers", messages)
            self.assertIn("'gene' has empty or missing identifiers", messages)

    def test_without_a_namespace_date_like_ids_are_a_suspicion_and_never_a_pass(self):
        code, result, _ = self.go("gene\nMX1\n1-Mar\nSep-7\n2020-03-01\n", {"kind": "identifiers", "column": "gene"})
        check = result["checks"][0]
        self.assertEqual((code, check["status"]), (3, "gap"))
        warning = [a for a in check["alerts"] if a["severity"] == "warning"][0]
        self.assertFalse(warning["blocking"])
        self.assertEqual(warning["evidence"], ["'1-Mar'", "'2020-03-01'", "'Sep-7'"])
        self.assertIn("cannot be told without a declared namespace", warning["message"])
        self.assertIn("no identifier namespace is declared", [a for a in check["alerts"]
                                                              if a["severity"] == "gap"][0]["message"])

    def test_clean_identifiers_without_a_namespace_are_still_only_a_gap(self):
        code, result, _ = self.go("gene\nMX1\nIFI27\n", {"kind": "identifiers", "column": "gene"})
        self.assertEqual((code, result["checks"][0]["status"], result["checks"][0]["runnable"]), (3, "gap", "ran"))

    def test_a_crosswalk_table_column_serves_as_the_namespace(self):
        self.put("xwalk.tsv", "old\tsymbol\nMARCH1\tMARCHF1\nSEPT7\tSEPTIN7\n")
        self.put("t.tsv", "gene\nMARCHF1\nSEPT7\n")
        check = {"kind": "identifiers", "column": "gene", "namespace": {"path": "xwalk.tsv", "column": "symbol"}}
        code, result, _ = self.result_run([check], table="t.tsv")
        self.assertEqual((code, result["checks"][0]["alerts"][0]["evidence"]), (2, ["'SEPT7'"]))

    def test_contract_filters_reach_a_table_that_lacks_their_column_and_block(self):
        # documented limit: a global filter on metadata columns also applies to a check on another table
        self.put("ns.txt", "MX1\n")
        self.put("t.tsv", "gene\nMX1\n")
        check = {"kind": "identifiers", "column": "gene", "namespace": {"path": "ns.txt", "lines": True}}
        code, result, _ = self.result_run([check], table="t.tsv", filters=KEEP)
        self.assertEqual((code, result["checks"][0]["runnable"]), (2, "columns_absent"))

    def test_an_unusable_namespace_is_never_a_pass(self):
        self.put("t.tsv", "gene\nMX1\n")
        spec = {"kind": "identifiers", "column": "gene", "namespace": {"path": "absent.txt", "lines": True}}
        code, result, _ = self.result_run([spec], table="t.tsv")
        self.assertEqual((code, result["checks"][0]["runnable"]), (2, "reference_unusable"))
        code, result, _ = self.go("gene\nMX1\n", namespace="# nothing\n\n")
        self.assertEqual((code, result["checks"][0]["status"]), (3, "gap"))

    def test_syntax_errors_and_softeners_are_usage_errors(self):
        self.put("t.tsv", "gene\nMX1\n")
        bad = [{"kind": "identifiers"}, {"kind": "identifiers", "column": "gene", "namespace": "ns.txt"},
               {"kind": "identifiers", "column": "gene", "namespace": {"lines": True}}]
        bad += [{"kind": "identifiers", "column": "gene", "namespace": {"path": "n", "lines": True}, **s}
                for s in SOFTENERS]
        for check in bad:
            self.assertEqual(self.result_run([check], table="t.tsv")[0], 1, check)

    @unittest.skipUnless(os.path.exists(FIXTURE_COUNTS), "the fixture project is not present")
    def test_the_fixtures_planted_date_symbols(self):
        with open(FIXTURE_COUNTS, encoding="utf-8") as handle:
            original = [line.split("\t")[0] for line in handle][1:]
        self.put("ns.txt", "\n".join(original) + "\n")  # stands in for an independent gene annotation
        with open(FIXTURE_COUNTS, encoding="utf-8") as handle:
            corrupted = handle.read().replace("\nMARCHF1\t", "\n1-Mar\t").replace("\nSEPTIN7\t", "\n7-Sep\t")
        check = {"kind": "identifiers", "column": "gene", "namespace": {"path": "ns.txt", "lines": True}}
        self.put("counts.tsv", corrupted)
        code, result, _ = self.result_run([check], table="counts.tsv")
        self.assertEqual((code, result["checks"][0]["alerts"][0]["evidence"]), (2, ["'1-Mar'", "'7-Sep'"]))
        with open(FIXTURE_COUNTS, encoding="utf-8") as handle:
            self.put("counts.tsv", handle.read())
        self.assertEqual(self.result_run([check], table="counts.tsv")[0], 0)
        del check["namespace"]  # no authority: a suspicion, not a verdict
        self.put("counts.tsv", corrupted)
        code, result, _ = self.result_run([check], table="counts.tsv")
        self.assertEqual(code, 3)
        warning = [a for a in result["checks"][0]["alerts"] if a["severity"] == "warning"][0]
        self.assertEqual(warning["evidence"], ["'1-Mar'", "'7-Sep'"])


def write_layers(path):
    """A minimal AnnData file with obs, X (integer counts), layers and obsm, with h5py alone."""
    import h5py
    import numpy as np
    counts = np.array([[0, 3, 5], [2, 0, 7], [1, 1, 4], [9, 0, 2]], dtype="int64")
    with h5py.File(path, "w") as handle:
        handle.attrs["encoding-type"] = "anndata"
        handle.attrs["encoding-version"] = "0.1.0"
        handle.create_dataset("X", data=counts)
        layers = handle.create_group("layers")
        layers.create_dataset("counts", data=counts)
        cp10k = counts / counts.sum(axis=1, keepdims=True) * 1e4
        layers.create_dataset("log_cp10k", data=np.log1p(cp10k))
        layers.create_dataset("log_cpm", data=np.log1p(counts / counts.sum(axis=1, keepdims=True) * 1e6))
        layers.create_dataset("negative", data=counts - 4.0)
        layers.create_dataset("with_nan", data=np.array([[1.0, np.nan], [2.0, 3.0]]))
        layers.create_dataset("words", data=np.array([b"a", b"b"]))
        csr = layers.create_group("csr")
        csr.attrs["encoding-type"] = "csr_matrix"
        csr.attrs["shape"] = np.array([2, 3])
        csr.create_dataset("data", data=np.array([4.0, 5.0, 6.0]))
        csr.create_dataset("indices", data=np.array([0, 2, 1]))
        csr.create_dataset("indptr", data=np.array([0, 2, 3]))
        odd = layers.create_group("odd")
        odd.attrs["encoding-type"] = "dataframe"
        handle.create_group("obsm").create_dataset("X_pca", data=np.ones((4, 2)))


def layer(h5_path, **properties):
    check = {"kind": "h5ad_layer", "h5_path": h5_path}
    sample_values = properties.pop("sample_values", None)
    if sample_values:
        check["sample_values"] = sample_values
    if properties:
        check["properties"] = properties
    return check


@unittest.skipUnless(HAVE_H5PY, NO_H5PY)
class H5adLayerTest(TempTables):
    def setUp(self):
        TempTables.setUp(self)
        write_layers(os.path.join(self.root, "cells.h5ad"))

    def go(self, check):
        code, result, _ = self.result_run([check], table="cells.h5ad")
        return code, result["checks"][0]

    def test_required_paths_that_exist_pass_without_reading_values(self):
        for path in ("X", "layers/counts", "/layers/log_cp10k", "obsm/X_pca"):
            self.assertEqual(self.go(layer(path))[0], 0, path)

    def test_a_missing_layer_or_obsm_blocks(self):
        for path in ("layers/raw", "obsm/X_umap"):
            code, check = self.go(layer(path))
            self.assertEqual((code, check["alerts"][0]["message"]), (2, "the required path is absent from the file"))

    def test_counts_that_hold_their_declared_properties_pass(self):
        code, check = self.go(layer("layers/counts", non_negative=True, integer_valued=True, max_at_most=9))
        self.assertEqual((code, check["status"], check["runnable"]), (0, "pass", "ran"))
        self.assertEqual(self.go(layer("X", non_negative=True, integer_valued=True))[0], 0)

    def test_normalised_values_fail_a_declared_integer_property(self):
        code, check = self.go(layer("layers/log_cp10k", non_negative=True, integer_valued=True))
        self.assertEqual(code, 2)
        self.assertEqual([a["message"] for a in check["alerts"]],
                         ["'layers/log_cp10k' violates a declared property: integer_valued"])
        self.assertIn("of 12 sampled values", check["alerts"][0]["observed"])

    def test_negative_values_and_a_too_large_maximum_block(self):
        code, check = self.go(layer("layers/negative", non_negative=True))
        self.assertEqual(code, 2)
        self.assertIn("min -4.0", check["alerts"][0]["observed"])
        code, check = self.go(layer("layers/counts", max_at_most=8))
        self.assertEqual((code, check["alerts"][0]["expected"]), (2, "max_at_most 8"))
        self.assertEqual(self.go(layer("layers/counts", max_at_most=9))[0], 0)
        self.assertEqual(self.go(layer("layers/counts", max_at_most=0))[0], 2)  # zero is a limit, not off

    def test_properties_switched_off_are_not_checked(self):
        self.assertEqual(self.go(layer("layers/negative", non_negative=False))[0], 0)

    def test_a_sparse_matrix_is_judged_by_its_stored_values(self):
        self.assertEqual(self.go(layer("layers/csr", non_negative=True, max_at_most=6))[0], 0)
        self.assertEqual(self.go(layer("layers/csr", integer_valued=True, max_at_most=5))[0], 2)

    def test_a_partial_sample_is_a_warning_never_a_clean_pass(self):
        # dense arrays are read by whole leading rows: 6 values are two rows of three
        code, check = self.go(layer("layers/counts", non_negative=True, max_at_most=8, sample_values=6))
        self.assertEqual((code, check["status"]), (0, "warn"))
        self.assertIn("first 6 of 12 stored values only", check["alerts"][0]["message"])
        # the 9 sits in the last row, beyond the declared cap: only the warning shows it was not looked at
        code, check = self.go(layer("layers/counts", non_negative=True, max_at_most=8))
        self.assertEqual(code, 2)

    def test_nan_and_non_numeric_values_are_gaps_and_a_violation_still_blocks(self):
        code, check = self.go(layer("layers/with_nan", non_negative=True))
        self.assertEqual((code, check["status"], check["runnable"]), (3, "gap", "values_not_judgeable"))
        code, check = self.go(layer("layers/with_nan", max_at_most=2))
        self.assertEqual((code, check["status"]), (2, "block"))
        self.assertEqual(sorted(a["severity"] for a in check["alerts"]), ["error", "gap"])
        for path in ("layers/words", "layers/odd"):
            code, check = self.go(layer(path, non_negative=True))
            self.assertEqual((code, check["status"], check["runnable"]), (3, "gap", "values_not_judgeable"), path)

    def test_two_different_normalizations_look_the_same_and_the_note_says_so(self):
        properties = {"non_negative": True, "max_at_most": 20}
        a = self.go(layer("layers/log_cp10k", **properties))
        b = self.go(layer("layers/log_cpm", **properties))
        self.assertEqual((a[0], a[1]["status"]), (0, "pass"))
        self.assertEqual((b[0], b[1]["status"]), (0, "pass"))
        self.assertIn("cannot tell which normalization algorithm produced the values", a[1]["note"])

    def test_a_file_that_is_not_hdf5_is_a_gap(self):
        self.put("bad.h5ad", "plain text")
        code, result, _ = self.result_run([layer("X")], table="bad.h5ad")
        self.assertEqual((code, result["checks"][0]["runnable"]), (3, "table_unreadable"))

    def test_the_layer_check_never_reads_obs_so_a_broken_obs_does_not_hide_it(self):
        self.assertEqual(self.go(layer("layers/counts", non_negative=True))[0], 0)  # the file has no obs at all

    def test_filters_do_not_apply_to_a_layer_and_a_local_one_is_refused(self):
        code, result, _ = self.result_run([layer("X")], table="cells.h5ad", filters=KEEP)
        self.assertEqual(code, 0)
        self.assertEqual(self.result_run([dict(layer("X"), filters=KEEP)], table="cells.h5ad")[0], 1)


class H5adLayerSyntaxTest(TempTables):
    """Runs without h5py: usage errors are found before any file is opened."""

    def test_bad_declarations_are_usage_errors(self):
        self.put("cells.h5ad", "x")
        bad = [{"kind": "h5ad_layer"}, layer("/"), layer("X", unknown=True),
               {"kind": "h5ad_layer", "h5_path": "X", "properties": ["non_negative"]},
               {"kind": "h5ad_layer", "h5_path": "X", "properties": {"non_negative": "yes"}},
               {"kind": "h5ad_layer", "h5_path": "X", "properties": {"max_at_most": True}},
               {"kind": "h5ad_layer", "h5_path": "X", "properties": {"max_at_most": float("nan")}},
               {"kind": "h5ad_layer", "h5_path": "X", "properties": {"max_at_most": float("inf")}},
               {"kind": "h5ad_layer", "h5_path": "X", "properties": {"non_negative": 1}},
               {"kind": "h5ad_layer", "h5_path": "X", "sample_values": 0},
               {"kind": "h5ad_layer", "h5_path": "X", "sample_values": True}]
        bad += [dict(layer("X"), **s) for s in SOFTENERS]
        for check in bad:
            self.assertEqual(self.result_run([check], table="cells.h5ad")[0], 1, check)
        self.put("t.tsv", "a\n1\n")
        self.assertEqual(self.result_run([layer("X")], table="t.tsv")[0], 1)  # not an .h5ad file

    def test_a_missing_h5ad_blocks(self):
        code, result, _ = self.result_run([layer("X")], table="gone.h5ad")
        self.assertEqual((code, result["checks"][0]["runnable"]), (2, "table_missing"))

    def test_without_h5py_the_layer_check_is_a_gap_that_says_which_reader_is_missing(self):
        self.put("h5py.py", "raise ImportError('h5py hidden by the test')\n")
        self.put("cells.h5ad", "\x89HDF")
        code, result, _ = self.result_run([layer("X", non_negative=True)], table="cells.h5ad",
                                          env=dict(os.environ, PYTHONPATH=self.root))
        check = result["checks"][0]
        self.assertEqual((code, check["status"], check["runnable"]), (3, "gap", "optional_reader_missing"))
        self.assertIn("h5py cannot be imported", check["alerts"][0]["observed"])


if __name__ == "__main__":
    unittest.main()
