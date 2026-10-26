"""Run: python3 skills/manuscript-audit/tests/test_manuscript_audit.py

Red/green fixtures for the lightweight manuscript artifact contracts, plus
compatibility checks against verify's actual contract-result reader.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
TOOL = os.path.join(REPO, "skills", "manuscript-audit", "scripts", "manuscript_audit.py")
FIXTURE = os.path.join(REPO, "tests", "fixtures", "manuscript-project")

spec = importlib.util.spec_from_file_location("manuscript_audit", TOOL)
audit = importlib.util.module_from_spec(spec)
sys.dont_write_bytecode = True
spec.loader.exec_module(audit)

sys.path.insert(0, os.path.join(REPO, "hooks"))
import gate  # noqa: E402


class ManuscriptAuditTests(unittest.TestCase):
    def project(self, root, *, data="sample_id\tcondition\tfraction\nS1\tA\t0.25\n", counts="sample_id\tcell_type\tcell_count\ttotal_count\tfraction\nS1\tT\t1\t4\t0.25\n"):
        for d in ["config", "script", "figures/source_data", "outputs", "data"]:
            (root / d).mkdir(parents=True, exist_ok=True)
        (root / "script/Figure1.py").write_text("# script\n")
        (root / "figures/source_data/Fig1a.tsv").write_text(data)
        (root / "outputs/freq.tsv").write_text(counts)
        (root / "data/README.md").write_text("Synthetic examples; no patient data.\n")
        cfg = {"schema": audit.SCHEMA, "data_manifest": "data/README.md",
               "figures": [{"id": "Fig1a", "script": "script/Figure1.py", "source_data": "figures/source_data/Fig1a.tsv", "required_columns": ["sample_id", "condition", "fraction"]}],
               "tables": [{"id": "freq", "file": "outputs/freq.tsv", "key_columns": ["sample_id", "cell_type"], "nonnegative_integer_columns": ["cell_count", "total_count"], "finite_numeric_columns": ["fraction"], "ratio_invariant": {"numerator": "cell_count", "denominator": "total_count", "fraction": "fraction"}}]}
        (root / "config/checks.json").write_text(json.dumps(cfg))
        return cfg

    # --- bundle red/green cases -------------------------------------------------

    def test_green(self):
        with tempfile.TemporaryDirectory() as x:
            root = Path(x); self.project(root)
            res = audit.evaluate(root, "config/checks.json")
            self.assertEqual(res["status"], "pass")
            self.assertEqual(res["exit_code"], 0)
            self.assertTrue(all(x["status"] == "pass" for x in res["checks"]))

    def test_missing_plot_column_red(self):
        with tempfile.TemporaryDirectory() as x:
            root = Path(x); cfg = self.project(root, data="sample_id\tcondition\nS1\tA\n")
            res = audit.evaluate(root, "config/checks.json")
            self.assertEqual(res["status"], "block")
            self.assertIn("fraction", str(res["checks"]))

    def test_missing_source_is_gap_not_pass(self):
        with tempfile.TemporaryDirectory() as x:
            root = Path(x); self.project(root)
            (root / "figures/source_data/Fig1a.tsv").unlink()
            self.assertEqual(audit.evaluate(root, "config/checks.json")["status"], "gap")

    def test_duplicate_keys_red(self):
        with tempfile.TemporaryDirectory() as x:
            root = Path(x)
            self.project(root, counts="sample_id\tcell_type\tcell_count\ttotal_count\tfraction\nS1\tT\t1\t4\t0.25\nS1\tT\t1\t4\t0.25\n")
            res = audit.evaluate(root, "config/checks.json")
            self.assertEqual(res["status"], "block")
            self.assertIn("duplicate key", str(res["checks"]))

    def test_counts_and_ratio_red(self):
        for num, den, frac in [("1.5", "4", "0.375"), ("-1", "4", "-0.25"), ("1", "4", "0.5"), ("1", "0", "0.25")]:
            with self.subTest(num=num, den=den, frac=frac), tempfile.TemporaryDirectory() as x:
                root = Path(x)
                self.project(root, counts=f"sample_id\tcell_type\tcell_count\ttotal_count\tfraction\nS1\tT\t{num}\t{den}\t{frac}\n")
                self.assertEqual(audit.evaluate(root, "config/checks.json")["status"], "block")

    def test_path_escape_is_gap(self):
        with tempfile.TemporaryDirectory() as x:
            root = Path(x); cfg = self.project(root)
            cfg["figures"][0]["source_data"] = "../../private.csv"
            (root / "config/checks.json").write_text(json.dumps(cfg))
            self.assertEqual(audit.evaluate(root, "config/checks.json")["status"], "gap")

    def test_duplicate_json_fields_gap(self):
        with tempfile.TemporaryDirectory() as x:
            root = Path(x); self.project(root)
            (root / "config/checks.json").write_text('{"schema":"x","schema":"y"}')
            self.assertEqual(audit.evaluate(root, "config/checks.json")["status"], "gap")

    def test_undeclared_output_is_not_claimed_as_reproduced(self):
        with tempfile.TemporaryDirectory() as x:
            root = Path(x); cfg = self.project(root)
            cfg["figures"][0]["outputs"] = ["figures/Fig1a.pdf"]
            (root / "config/checks.json").write_text(json.dumps(cfg))
            self.assertEqual(audit.evaluate(root, "config/checks.json")["status"], "gap")

    # --- corrections found in the integration review ----------------------------

    def test_usage_error_exits_1_not_2(self):
        # A usage error must never share the "block" exit code: verify reads 2 as a
        # failed check and 1 as "not run".
        with tempfile.TemporaryDirectory() as x:
            with self.assertRaises(SystemExit) as ctx:
                audit.main(["--root", x])  # missing required --config
            self.assertEqual(ctx.exception.code, 1)

    def test_result_json_collision_is_refused(self):
        # The result must never overwrite the contract or a declared input.
        for victim in ("config/checks.json", "outputs/freq.tsv", "figures/source_data/Fig1a.tsv"):
            with self.subTest(victim=victim), tempfile.TemporaryDirectory() as x:
                root = Path(x); self.project(root)
                before = (root / victim).read_bytes()
                code = audit.main(["--root", x, "--config", "config/checks.json", "--result-json", victim])
                self.assertEqual(code, 1)
                self.assertEqual((root / victim).read_bytes(), before)

    def test_result_json_writes_benign_destination(self):
        with tempfile.TemporaryDirectory() as x:
            root = Path(x); self.project(root)
            code = audit.main(["--root", x, "--config", "config/checks.json", "--result-json", "outputs/manuscript_audit.json"])
            self.assertEqual(code, 0)
            saved = json.loads((root / "outputs/manuscript_audit.json").read_text())
            self.assertEqual(saved["schema"], audit.RESULT_SCHEMA)
            self.assertEqual(saved["status"], "pass")

    def test_malformed_tolerance_is_gap(self):
        for tol in ("-1", "0.0.1", "1e999"):
            with self.subTest(tol=tol), tempfile.TemporaryDirectory() as x:
                root = Path(x); cfg = self.project(root)
                cfg["tables"][0]["ratio_invariant"]["tolerance"] = tol
                (root / "config/checks.json").write_text(json.dumps(cfg))
                res = audit.evaluate(root, "config/checks.json")
                self.assertEqual(res["status"], "gap")
                self.assertIn("tolerance", str(res["checks"]))

    def test_zero_tolerance_is_accepted(self):
        with tempfile.TemporaryDirectory() as x:
            root = Path(x); cfg = self.project(root)
            cfg["tables"][0]["ratio_invariant"]["tolerance"] = "0"
            (root / "config/checks.json").write_text(json.dumps(cfg))
            self.assertEqual(audit.evaluate(root, "config/checks.json")["status"], "pass")

    def test_symlink_escape_is_gap(self):
        with tempfile.TemporaryDirectory() as x:
            outside = tempfile.mkdtemp()
            secret = Path(outside) / "private.tsv"
            secret.write_text("sample_id\tcondition\tfraction\nS1\tA\t0.25\n")
            root = Path(x); self.project(root)
            (root / "figures/source_data/Fig1a.tsv").unlink()
            (root / "figures/source_data/Fig1a.tsv").symlink_to(secret)
            res = audit.evaluate(root, "config/checks.json")
            self.assertEqual(res["status"], "gap")
            self.assertIn("outside project", str(res["checks"]))

    def test_malformed_column_declarations_are_gap(self):
        for field, value in [("required_columns", "sample_id"), ("key_columns", ["sample_id", "sample_id"]), ("nonnegative_integer_columns", "cell_count")]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as x:
                root = Path(x); cfg = self.project(root)
                if field == "required_columns":
                    cfg["figures"][0][field] = value
                else:
                    cfg["tables"][0][field] = value
                (root / "config/checks.json").write_text(json.dumps(cfg))
                res = audit.evaluate(root, "config/checks.json")
                self.assertEqual(res["status"], "gap")

    def test_outputs_string_is_gap(self):
        with tempfile.TemporaryDirectory() as x:
            root = Path(x); cfg = self.project(root)
            cfg["figures"][0]["outputs"] = "figures/Fig1a.pdf"
            (root / "config/checks.json").write_text(json.dumps(cfg))
            res = audit.evaluate(root, "config/checks.json")
            self.assertEqual(res["status"], "gap")

    # --- committed fixture is green ---------------------------------------------

    def test_committed_fixture_passes(self):
        res = audit.evaluate(FIXTURE, "config/manuscript_checks.json")
        self.assertEqual(res["status"], "pass", str(res["checks"]))
        self.assertEqual(res["exit_code"], 0)

    # --- compatibility with verify's actual reader -------------------------------

    def verify_reader(self, result, files=None):
        verify = gate.load_verify()
        path = Path(tempfile.mkdtemp()) / "result.json"
        path.write_text(json.dumps(result))
        return verify.read_result(str(path), {"files": files or {}})

    def test_verify_reader_maps_green_to_passed(self):
        with tempfile.TemporaryDirectory() as x:
            root = Path(x); self.project(root)
            outcome, reason, _ = self.verify_reader(audit.evaluate(root, "config/checks.json"))
            self.assertEqual(outcome, "passed")

    def test_verify_reader_maps_block_to_failed(self):
        with tempfile.TemporaryDirectory() as x:
            root = Path(x); self.project(root, data="sample_id\tcondition\nS1\tA\n")
            outcome, reason, _ = self.verify_reader(audit.evaluate(root, "config/checks.json"))
            self.assertEqual(outcome, "failed")

    def test_verify_reader_maps_gap_to_not_run(self):
        with tempfile.TemporaryDirectory() as x:
            root = Path(x); self.project(root)
            (root / "figures/source_data/Fig1a.tsv").unlink()
            outcome, reason, _ = self.verify_reader(audit.evaluate(root, "config/checks.json"))
            self.assertEqual(outcome, "not run")

    def test_verify_reader_detects_changed_contract(self):
        with tempfile.TemporaryDirectory() as x:
            root = Path(x); self.project(root)
            result = audit.evaluate(root, "config/checks.json")
            pinned = result["contract"]["sha256"]
            outcome, _, _ = self.verify_reader(result, files={"config/checks.json": pinned})
            self.assertEqual(outcome, "passed")
            outcome, reason, _ = self.verify_reader(result, files={"config/checks.json": "0" * 64})
            self.assertEqual(outcome, "changed")


if __name__ == "__main__":
    unittest.main()
