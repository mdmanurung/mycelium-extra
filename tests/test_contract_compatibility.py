"""Run: python3 tests/test_contract_compatibility.py

A fixed corpus of small tables run through this repository's data-contract
checker and, when a Mycelium checkout is available, through Mycelium's
skills/core/scripts/data_contract_check.py (the checkout path comes from
$MYCELIUM_UPSTREAM; the default is the commit this repo was last aligned to).
Each case must give the same pass / gap / block outcome in both. Without the
checkout only the upstream half is skipped; the local expectations still run.

Upstream is only ever loaded from that path, read-only, and only by this test:
the shipped checker never imports an installed Mycelium.

Intentional differences, none of which is an outcome difference on this corpus
except the one in DIFFERENCES:
  - contract schema: Extra's "mycelium-extra.data_contract.v1" is accepted by
    upstream, which also accepts its own "mycelium.data_contract.v1";
  - alert schema: "mycelium-extra.contract_alert.v1" here, "mycelium.contract_alert.v1" there;
  - upstream also rejects unknown contract keys and treats "n/a" and "#n/a" as
    missing; this corpus uses neither;
  - the checks themselves have diverged (upstream is stricter on missing
    values and whitespace variants), so the corpus exercises table reading
    with schema and row-count checks, not the statistical checks.
"""

import importlib.util
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL = os.path.join(HERE, "..", "skills", "data-contract-check", "scripts", "data_contract_check.py")
UPSTREAM = os.path.join(
    os.environ.get("MYCELIUM_UPSTREAM", "/exports/para-lipg-hpc/mdmanurung/mycelium-upstream-8f8b167"),
    "skills", "core", "scripts", "data_contract_check.py")
NO_UPSTREAM = "no Mycelium checkout at {} (set MYCELIUM_UPSTREAM)".format(UPSTREAM)


def load(name, path):
    keep, sys.dont_write_bytecode = sys.dont_write_bytecode, True  # never write into a checkout
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.dont_write_bytecode = keep


SCHEMA = [{"kind": "schema", "columns": ["sample_id", "group"]}, {"kind": "cohort", "rows": 2}]
DATES = [{"kind": "cohort", "column": "group", "levels": ["A", "B"], "rows": 3, "no_missing": ["sample_id"]}]
NO_MISSING = [{"kind": "cohort", "no_missing": ["group"]}]
TSV = "sample_id\tgroup\nS1\tA\nS2\tB\n"
# (name, file, content, checks, expected status of every check)
CORPUS = [
    ("valid tsv", "t.tsv", TSV, SCHEMA, "pass"),
    ("valid csv", "t.csv", TSV.replace("\t", ","), SCHEMA, "pass"),
    ("tab extension", "t.tab", TSV, SCHEMA, "pass"),
    ("txt extension", "t.txt", TSV, SCHEMA, "pass"),
    ("bom and blank line", "t.tsv", "﻿sample_id\tgroup\n\nS1\tA\nS2\tB\n", SCHEMA, "pass"),
    ("quoted newline", "t.csv", 'sample_id,group\n"S,1","A\nB"\nS2,C\n', SCHEMA, "pass"),
    ("date-like ids", "t.tsv", "sample_id\tgroup\n2024-01-05\tA\n01/02/2024\tB\nMar-1\tB\n", DATES, "pass"),
    ("blank header fields", "t.tsv", "sample_id\tgroup\t\t\nS1\tA\t\t\nS2\tB\t\t\n", SCHEMA, "pass"),
    ("ragged extra field (F11)", "ragged.tsv", "sample_id\tgroup\nS1\tA\textra\nS2\tB\n", SCHEMA, "block"),
    ("empty extra field", "t.csv", "sample_id,group\nS1,A,\nS2,B\n", SCHEMA, "block"),
    ("unterminated quote", "t.csv", 'sample_id,group\nS1,"A\nS2,B\n', SCHEMA, "block"),
    ("short row is missing, not None", "t.tsv", "sample_id\tgroup\nS1\tA\nS2\n", NO_MISSING, "block"),
    ("invalid utf-8", "t.tsv", b"sample_id\tgroup\np\xff\tA\np\xfe\tB\n", SCHEMA, "gap"),
    ("unsupported extension", "t.xlsx", TSV, SCHEMA, "gap"),
    ("no extension", "table", TSV, SCHEMA, "gap"),
]
# Extra keeps its documented gap for a repeated header; Mycelium blocks it.
DIFFERENCES = [("duplicate header", "d.tsv", "cohort\tcohort\nA\tB\n",
                [{"kind": "cohort", "column": "cohort", "levels": ["B"]}], "gap", "block")]


def outcomes(module, name, content, checks, table):
    folder = tempfile.mkdtemp()
    try:
        with open(os.path.join(folder, table), "wb") as handle:
            handle.write(content if isinstance(content, bytes) else content.encode("utf-8"))
        contract = {"schema": "mycelium-extra.data_contract.v1", "table": table, "checks": checks}
        summaries, _ = module.run_contract(contract, folder)
        return sorted({s["status"] for s in summaries})
    finally:
        shutil.rmtree(folder)


class CompatibilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.local = load("extra_data_contract_check", LOCAL)
        cls.upstream = load("upstream_data_contract_check", UPSTREAM) if os.path.isfile(UPSTREAM) else None

    def test_local_expectations(self):
        for name, table, content, checks, expected in CORPUS:
            self.assertEqual(outcomes(self.local, name, content, checks, table), [expected], name)
        for name, table, content, checks, local, _ in DIFFERENCES:
            self.assertEqual(outcomes(self.local, name, content, checks, table), [local], name)

    def test_upstream_agrees(self):
        if self.upstream is None:
            self.skipTest(NO_UPSTREAM)
        for name, table, content, checks, expected in CORPUS:
            self.assertEqual(outcomes(self.upstream, name, content, checks, table), [expected],
                             "upstream differs on " + name)
        for name, table, content, checks, _, upstream in DIFFERENCES:
            self.assertEqual(outcomes(self.upstream, name, content, checks, table), [upstream], name)

    def test_alert_namespaces_differ_on_purpose(self):
        self.assertEqual(self.local.SCHEMA, "mycelium-extra.data_contract.v1")
        self.assertEqual(self.local.ALERT_SCHEMA, "mycelium-extra.contract_alert.v1")
        if self.upstream is None:
            self.skipTest(NO_UPSTREAM)
        self.assertEqual(self.upstream.ALERT_SCHEMA, "mycelium.contract_alert.v1")
        self.assertIn(self.local.SCHEMA, self.upstream.ACCEPTED_SCHEMAS)


if __name__ == "__main__":
    unittest.main()
