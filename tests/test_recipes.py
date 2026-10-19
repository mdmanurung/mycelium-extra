"""The validation-bindings blocks in docs/validation-recipes.md parse with the gate's own reader, and the outcome
`verify` records for a check command matches the return-code table the page documents."""

import json
import os
import re
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "hooks"))
import gate  # noqa: E402
import validation  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "skills", "verify", "scripts"))
import verify  # noqa: E402

verify.gate = gate  # the module verify loads from --plugin-root, needed by judge_check

PAGE = os.path.join(HERE, "..", "docs", "validation-recipes.md")
BLOCK = re.compile(r"<!--\s*validation-bindings\b.*?-->", re.DOTALL)
EVIDENCE = "analysis/a/outputs/contrast_direction_check.json"
CHECK = {"id": "contrast-direction", "plan_row": "4", "required": True, "defined_by": "researcher-approved",
         "invocation": ["python3", "analysis/a/checks/check_contrast_direction.py"],
         "evidence_path": EVIDENCE, "definition_sha256": "0" * 64, "files": {}}
CONTRACT = "mycelium-extra.contract_result.v1"


class Recipes(unittest.TestCase):
    def test_every_binding_in_the_page_is_valid(self):
        with open(PAGE, encoding="utf-8") as handle:
            blocks = BLOCK.findall(handle.read())
        self.assertEqual(len(blocks), 3, "one binding block per recipe")
        for text in blocks:
            checks = json.loads(re.search(r"\{.*\}", text, re.DOTALL).group(0))["checks"]
            with tempfile.TemporaryDirectory() as root:
                for check in checks:
                    for rel in check["test_paths"]:
                        os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
                        with open(os.path.join(root, rel), "w") as handle:
                            handle.write("x\n")
                rows = sorted({c["plan_row"] for c in checks})
                found, errors = validation.read_bindings(text, rows, root)
                self.assertEqual(errors, [], text)
                self.assertEqual(len(found["checks"]), len(checks))


class RecipeOutcomes(unittest.TestCase):
    """The return-code table in "How a result is read", judged by verify's own code rather than by a restatement."""

    def judge(self, code, result, attributable=True):
        """The outcome verify records for one check command that exited `code` and wrote `result`."""
        with tempfile.TemporaryDirectory() as root:
            full = os.path.join(root, EVIDENCE)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            if result is not None:
                with open(full, "w", encoding="utf-8") as handle:
                    handle.write(result if isinstance(result, str) else json.dumps(result))
            run = {"attempt_id": "a" * 16, "ts": time.time() + 1, "exit_status": code}
            if attributable:
                run.update(outputs_observation="observed", outputs_changed={"created": [EVIDENCE]})
            return verify.judge_check(root, dict(CHECK), [run], {}, False)["outcome"]

    def test_the_documented_return_code_outcome_pairs(self):
        for code, result, expected in [
                (0, {"status": "passed"}, "passed"),
                (1, {"status": "failed", "message": "contrast direction: UP has log2fc -2.43"}, "failed"),
                (1, {"status": "failed", "message": "reordering the metadata rows changed log2fc"}, "failed"),
                (0, {"status": "unsupported", "message": "scilintr not available"}, "unsupported")]:
            self.assertEqual(self.judge(code, result), expected, (code, result))

    def test_a_result_file_never_turns_a_non_zero_exit_into_a_pass(self):
        self.assertEqual(self.judge(1, {"status": "passed"}), "failed")

    def test_a_gap_in_a_contract_result_overrides_a_non_zero_exit(self):
        self.assertEqual(self.judge(3, {"schema": CONTRACT, "status": "gap", "exit_code": 3, "checks": [],
                                        "contract": {}}), "not run")
        self.assertEqual(self.judge(2, {"schema": CONTRACT, "status": "block", "exit_code": 2, "contract": {},
                                        "checks": [{"id": "complete-table", "status": "block",
                                                    "message": "the table and the list hold different numbers of keys"}]}),
                         "failed")
        self.assertEqual(self.judge(0, {"schema": CONTRACT, "status": "warn", "exit_code": 0, "contract": {},
                                        "checks": [{"id": "batch-confounding", "status": "warn", "message": "one block"}]}),
                         "passed")

    def test_an_unrecorded_exit_status_is_unsupported_not_a_pass(self):
        self.assertEqual(self.judge(None, {"status": "passed"}), "unsupported")

    def test_an_unattributable_pass_is_not_a_pass(self):
        self.assertEqual(self.judge(0, {"status": "passed"}, attributable=False), "unattributable")

    def test_a_result_file_that_says_nothing_usable_is_unsupported(self):
        for result in ({"status": "other"}, ["passed"], "not json at all"):
            self.assertEqual(self.judge(0, result), "unsupported", result)

    def test_a_vanished_result_file_is_unattributable_and_no_matched_run_is_not_run(self):
        # The attempt is recorded as having created it, so a file that is gone is unattributable, not unsupported.
        self.assertEqual(self.judge(0, None), "unattributable")
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(verify.judge_check(root, dict(CHECK), [], {}, False)["outcome"], "not run")
            elsewhere = verify.judge_check(root, dict(CHECK), [], {}, True)
            self.assertEqual(elsewhere["outcome"], "not run")
            self.assertIn("another approval instance", elsewhere["reason"])

    def test_the_page_documents_every_outcome_the_judge_can_return(self):
        with open(PAGE, encoding="utf-8") as handle:
            page = handle.read()
        section = page[page.index("## How a result is read"):page.index("## Contract kinds")]
        for outcome in ("passed", "failed", "not run", "changed", "unsupported", "unattributable"):
            self.assertIn(outcome, section, outcome + " is not documented")
        self.assertIn("never turn a non-zero exit into a pass", section)
        self.assertIn("random effect", page)


if __name__ == "__main__":
    unittest.main()
