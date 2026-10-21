"""Regressions for the nine defects documented in the 2026-10-21 adversarial audit."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / "hooks"), str(ROOT / "skills/plan-review/scripts")]
import confirm_write
import evidence
import gate
import review_packet
import stateio
import validation


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


contract = load("regression_contract", "skills/data-contract-check/scripts/data_contract_check.py")
verify = gate.load_verify()


class AdversarialRegressionTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_result_destination_preserves_every_declared_input_even_on_contract_errors(self):
        table = self.root / "samples.tsv"
        table.write_text("id\tgroup\ns1\tA\n")
        reference = self.root / "reference.tsv"
        reference.write_bytes(table.read_bytes())
        namespace = self.root / "namespace.txt"
        namespace.write_text("s1\n")
        other = self.root / "other.tsv"
        other.write_bytes(table.read_bytes())
        source = self.root / "contract.json"
        checks = [{"kind": "schema", "columns": ["id"]},
                  {"kind": "sample_alignment", "table": other.name, "key": "id",
                   "reference": {"path": reference.name, "column": "id"}},
                  {"kind": "identifiers", "column": "id", "namespace": {"path": namespace.name, "lines": True}}]
        for invalid in (False, True):
            source.write_text(json.dumps({"schema": contract.SCHEMA, "table": table.name,
                                          "checks": ([{"kind": "unknown"}] if invalid else []) + checks}))
            originals = {p: p.read_bytes() for p in (source, table, reference, namespace, other)}
            for target in originals:
                alias = self.root / "alias"
                alias.symlink_to(target)
                try:
                    for destination in (target, alias):
                        with self.subTest(invalid=invalid, target=target.name, alias=destination == alias):
                            result = subprocess.run([sys.executable, str(ROOT / "skills/data-contract-check/scripts/data_contract_check.py"),
                                                     "--contract", str(source), "--root", str(self.root),
                                                     "--result-json", str(destination)], capture_output=True, text=True)
                            self.assertEqual(result.returncode, 1)
                            self.assertIn("result path must differ", result.stderr)
                            self.assertEqual({p: p.read_bytes() for p in originals}, originals)
                            self.assertTrue(alias.is_symlink())
                finally:
                    alias.unlink()

    def test_result_writer_does_not_follow_a_predictable_temporary_symlink(self):
        original = self.root / "input.tsv"
        original.write_text("original input")
        destination = self.root / "result.json"
        trap = self.root / ("result.json.{}.tmp".format(os.getpid()))
        trap.symlink_to(original)
        contract.write_result(str(destination), {"status": "pass"})
        self.assertEqual(original.read_text(), "original input")
        self.assertEqual(json.loads(destination.read_text()), {"status": "pass"})
        self.assertTrue(trap.is_symlink())

    def test_result_writer_cleans_up_when_publication_fails(self):
        with patch.object(contract.os, "replace", side_effect=OSError("publication failed")):
            with self.assertRaises(OSError):
                contract.write_result(str(self.root / "result.json"), {})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_refused_state_writes_and_locks_create_nothing_outside_state(self):
        state = self.root / ".mycelium-extra"
        state.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        (state / "linked").symlink_to(outside, target_is_directory=True)
        target = str(state / "linked/new/nested/result.json")
        with self.assertRaises(ValueError):
            stateio.atomic(target, "{}")
        with self.assertRaises(ValueError):
            with stateio.locked(target):
                self.fail("symlinked lock acquired")
        self.assertEqual(list(outside.iterdir()), [])

    def test_pending_write_refuses_symlinks_and_cli_reports_the_refusal(self):
        state = self.root / ".mycelium-extra"
        state.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        (state / "write-pending").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            confirm_write.prepare(str(self.root), "harden", ["analysis/x.py"])
        proc = subprocess.run([sys.executable, str(ROOT / "hooks/confirm_write.py"), "prepare",
                               "--root", str(self.root), "--kind", "harden", "--target", "analysis/x.py"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("refusing a symlinked state target", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(list(outside.iterdir()), [])

    def test_evidence_withholds_sensitive_coordinates_and_cleans_other_strings(self):
        secret = "synthetic-sensitive"
        value = {"hash": "12345678", "analysis_dir": "analysis/" + secret, "status": "CONFORMS",
                 "receipts": [{"command_env": {"TOKEN": secret}}], "findings": [["gap", secret]],
                 "outputs": [{"path": "analysis/" + secret + ".tsv", "evidence_method": secret,
                              "record": {"skipped": secret}}]}
        projected = evidence.project(value, references={"report": secret + ".md"})
        self.assertNotIn(secret, json.dumps(projected))
        self.assertIsNone(projected["analysis_path"])
        self.assertIsNone(projected["outputs"][0]["path"])
        self.assertIsNone(projected["references"]["report"])
        self.assertEqual(projected["snapshot_digest"], evidence.identity(projected))
        value["analysis_dir"] = "analysis/safe"
        value["outputs"][0]["path"] = "analysis/safe/result.tsv"
        projected = evidence.project(value)
        self.assertEqual(projected["analysis_path"], "analysis/safe")
        self.assertEqual(projected["outputs"][0]["path"], "analysis/safe/result.tsv")

    def test_malformed_csv_cannot_verify_a_cell_or_row_count(self):
        table = self.root / "claim.csv"
        doc = self.root / "claims.md"
        doc.write_text("<!-- claims\n0.05 | claim.csv value x\n-->\n")
        for raw in ['id,value\nx,0.05,unexpected\n', 'id,value\nx,"0.05\n', 'id,value\nx\n']:
            table.write_text(raw)
            for column in ("value", "rows"):
                cell, why = verify.claim_cell(str(table), column, "x", 10000)
                self.assertIsNone(cell)
                self.assertTrue(why)
            rows = verify.check_claims(str(self.root), None, [{"path": "claim.csv"}],
                                       [str(doc)], verify.Report(), 10000)
            self.assertEqual(rows[0]["claims"][0]["verdict"], "unverified")
        table.write_text('id,value\nx,"0.05"\n')
        self.assertEqual(verify.claim_cell(str(table), "value", "x", 10000), ("0.05", None))
        self.assertEqual(verify.claim_cell(str(table), "rows", None, 10000), ("1", None))

    def test_unhashable_validation_ids_return_structured_errors_and_hook_notice(self):
        (self.root / "test.py").write_text("print(1)\n")
        for ident in ([], {}, 1, None):
            binding = {"version": 1, "checks": [{"id": ident, "plan_row": "1", "required": True,
                       "defined_by": "researcher-approved", "test_paths": ["test.py"],
                       "invocation": ["python", "test.py"], "evidence_path": "result.json"}]}
            plan = ("## Plan\n| 1 | run `analysis/x.py` | repo | check |\n\n" +
                    "<!-- validation-bindings " + json.dumps(binding) + " -->\nPlan status: READY")
            value, errors = validation.read_bindings(plan, ["1"], str(self.root))
            self.assertIsNone(value)
            self.assertTrue(any("`id` must be" in error for error in errors))
            state = self.root / ".mycelium-extra"
            state.mkdir(exist_ok=True)
            (state / "gate.json").write_text('{"on_error":"deny"}')
            proc = subprocess.run([sys.executable, str(ROOT / "hooks/gate_run.py"), "stop"],
                                  input=json.dumps({"cwd": str(self.root), "session_id": "regression",
                                                    "last_assistant_message": plan}), text=True, capture_output=True,
                                  env=dict(os.environ, MYCELIUM_EXTRA_PYTHON=sys.executable))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("id", proc.stdout)
            self.assertNotIn("TypeError", proc.stdout + proc.stderr)

    def test_nonfinite_consent_is_refused_but_finite_newer_consent_is_valid(self):
        digest = "a" * 64
        folder = self.root / ".mycelium-extra/review-consent"
        folder.mkdir(parents=True)
        for ts in (float("nan"), float("inf"), -float("inf"), True, 0, 9, 11):
            record = {"schema": review_packet.CONSENT_SCHEMA, "digest": digest, "session_id": "s",
                      "ts": ts, "prompt": "send packet " + digest[:12]}
            (folder / (digest + ".json")).write_text(json.dumps(record))
            if ts == 11:
                review_packet.check_consent(str(self.root), digest, {"created": 10})
            else:
                with self.assertRaises(review_packet.Refuse):
                    review_packet.check_consent(str(self.root), digest, {"created": 10})

    def test_categorical_codes_are_integer_indices_or_the_missing_sentinel(self):
        self.assertEqual(contract.decode_codes([0, -1, 1], ["A", "B"]), ["A", "", "B"])
        for codes in ([0.5], ["x"], [True], [-2], [2], [[0]], 0):
            with self.assertRaises(contract.TableGap):
                contract.decode_codes(codes, ["A", "B"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
