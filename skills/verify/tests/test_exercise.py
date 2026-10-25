"""Synthetic exercises must stay out of genuine verification and project state."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

PLUGIN = Path(__file__).resolve().parents[3]
SCRIPT = PLUGIN / "skills/verify/scripts/verify.py"
spec = importlib.util.spec_from_file_location("exercise_verify", SCRIPT)
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class ExerciseTest(unittest.TestCase):
    def test_fixture_contains_one_numeric_discrepancy_and_reveals_it(self):
        shown = verify.review_exercise()
        self.assertIn("SYNTHETIC REVIEW EXERCISE", shown)
        observed = float(shown.split("MX1\t")[1].splitlines()[0])
        claimed = float(shown.split("MX1 log2fc is ")[1].splitlines()[0].rstrip("."))
        self.assertNotEqual(observed, claimed)
        self.assertEqual(abs(observed), abs(claimed))
        self.assertNotIn("ANSWER -", shown)
        answer = verify.review_exercise(True)
        self.assertIn("ANSWER - SYNTHETIC EXERCISE ONLY", answer)
        self.assertIn("claims {}; the MX1 output cell holds {}".format(claimed, observed), answer)
        self.assertIn("Exit 0 shows completion only", answer)

    def test_exercise_does_not_load_gate_or_project_state(self):
        with mock.patch.object(verify, "load_gate", side_effect=AssertionError("loaded gate")):
            with mock.patch("sys.stdout"):
                self.assertEqual(verify.main(["--plugin-root", "absent", "exercise"]), 0)

    def test_cli_runs_from_stdin_without_writes_or_changing_real_records(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            state = root / ".mycelium-extra"
            state.mkdir()
            (state / "gate.json").write_text("{}")
            (state / "receipts.jsonl").write_text('{"exit_status": 0}\n')
            (root / "PROVENANCE.md").write_text("genuine record\n")
            before = {p.relative_to(root): (p.read_bytes(), p.stat().st_mtime_ns)
                      for p in root.rglob("*") if p.is_file()}
            for args, code in (([], 0), (["reveal"], 0), (["unknown"], 2),
                               (["--json"], 2), (["--resolve-citations"], 2)):
                result = subprocess.run([sys.executable, "-", "--plugin-root", str(PLUGIN),
                                         "exercise"] + args, input=SCRIPT.read_text(), text=True,
                                        cwd=root, capture_output=True)
                self.assertEqual(result.returncode, code, result.stderr)
                if code == 0:
                    self.assertTrue(result.stdout.startswith("SYNTHETIC REVIEW EXERCISE"))
            after = {p.relative_to(root): (p.read_bytes(), p.stat().st_mtime_ns)
                     for p in root.rglob("*") if p.is_file()}
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
