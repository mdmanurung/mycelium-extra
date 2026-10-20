"""The validation-bindings blocks in docs/validation-recipes.md parse with the gate's own reader, and the outcome
`verify` records for a check command matches the return-code table the page documents."""

import json
import subprocess
import shutil
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
        self.assertEqual(len(blocks), 4, "three original recipe blocks and one R1-R3 binding example")
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


class SingleCellRecipes(unittest.TestCase):
    """Run shipped R1/R2 entry points and consume their actual results with verify."""
    root = os.path.abspath(os.path.join(HERE, '..'))
    fixtures = 'tests/fixtures/sc-conventions/'

    def invoke(self, contract_name, folder, root=None):
        result = os.path.join(folder, 'result.json')
        contract = os.path.join(self.root, self.fixtures, contract_name)
        command = [sys.executable, os.path.join(self.root, 'skills/data-contract-check/scripts/data_contract_check.py'),
                   '--contract', contract, '--root', root or self.root, '--result-json', result, '--json']
        proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        with open(result) as handle:
            data = json.load(handle)
        return proc, result, data

    def test_design_red_green_with_real_checker_and_verify(self):
        for contract, code in [('r1_missing_pair.json', 2), ('r1_aliased.json', 2), ('r1_design.json', 0)]:
            with tempfile.TemporaryDirectory() as folder:
                proc, path, data = self.invoke(contract, folder)
                self.assertEqual(proc.returncode, code, proc.stderr)
                self.assertEqual(verify.read_result(path, {'files': {}})[0], 'failed' if code else 'passed')
                self.assertTrue(data['tables'])
                self.assertTrue(all(t['sha256'] for t in data['tables']))

    def test_keys_red_green_and_reordering_control_with_real_checker(self):
        for contract, code in [('r2_wrong_keys.json', 2), ('r2_keys.json', 0)]:
            with tempfile.TemporaryDirectory() as folder:
                proc, path, _ = self.invoke(contract, folder)
                self.assertEqual(proc.returncode, code, proc.stderr)
                self.assertEqual(verify.read_result(path, {'files': {}})[0], 'failed' if code else 'passed')
        with tempfile.TemporaryDirectory() as folder:
            target = os.path.join(folder, self.fixtures)
            os.makedirs(target)
            for name in ('samples.tsv', 'keys.tsv'):
                shutil.copyfile(os.path.join(self.root, self.fixtures, name), os.path.join(target, name))
            samples = os.path.join(target, 'samples.tsv')
            with open(samples) as handle:
                lines = handle.readlines()
            with open(samples, 'w') as handle:
                handle.writelines(lines[:1] + list(reversed(lines[1:])))
            proc, _, _ = self.invoke('r2_keys.json', folder, folder)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_existing_verify_judges_changed_approved_r1_and_r2_contracts(self):
        for name in ('r1_design.json', 'r2_keys.json'):
            with tempfile.TemporaryDirectory() as folder:
                os.makedirs(os.path.join(folder, 'checks'))
                script = 'checks/data_contract_check.py'
                contract = 'checks/contract.json'
                shutil.copyfile(os.path.join(self.root, 'skills/data-contract-check/scripts/data_contract_check.py'),
                                os.path.join(folder, script))
                shutil.copyfile(os.path.join(self.root, self.fixtures, name), os.path.join(folder, contract))
                declaration = dict(CHECK, test_paths=[script, contract], evidence_path='result.json',
                    invocation=[sys.executable, script, '--contract', contract, '--root', self.root,
                                '--result-json', 'result.json'])
                for key in ('files', 'definition_sha256'):
                    declaration.pop(key)
                text = '<!-- validation-bindings ' + json.dumps({'version': 1, 'checks': [declaration]}) + ' -->'
                binding, errors = validation.read_bindings(text, ['4'], folder)
                self.assertEqual(errors, [])
                check = binding['checks'][0]
                # A semantically harmless whitespace edit still changes the approved bytes.
                with open(os.path.join(folder, contract), 'a') as target:
                    target.write('\n')
                proc = subprocess.run(check['invocation'], cwd=folder, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, universal_newlines=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                run = {'attempt_id': 'b' * 16, 'ts': time.time() + 1, 'exit_status': proc.returncode,
                       'outputs_observation': 'observed', 'outputs_changed': {'created': ['result.json']}}
                judged = verify.judge_check(folder, check, [run], {}, False)
                self.assertEqual(judged['outcome'], 'changed')
                self.assertIn('not the pinned one', judged['reason'])

    def test_layer_dependency_is_an_explicit_gap_or_real_red_green(self):
        try:
            import h5py
            import numpy as np
        except ImportError:
            with tempfile.TemporaryDirectory() as folder:
                target = os.path.join(folder, self.fixtures)
                os.makedirs(target)
                with open(os.path.join(target, 'counts.h5ad'), 'wb') as handle:
                    handle.write(b'backend-unavailable-fixture')
                proc, path, data = self.invoke('r2_layer.json', folder, folder)
                self.assertNotEqual(proc.returncode, 0)
                self.assertEqual(verify.read_result(path, {'files': {}})[0], 'not run')
            self.skipTest('h5py unavailable: backend gap verified; real HDF5 red/green requires h5py')
        with tempfile.TemporaryDirectory() as folder:
            target = os.path.join(folder, self.fixtures)
            os.makedirs(target)
            matrix = os.path.join(target, 'counts.h5ad')
            for values, code in (([1.5, -1], 2), ([1, 0], 0)):
                with h5py.File(matrix, 'w') as handle:
                    handle.create_dataset('layers/counts', data=np.asarray([values]))
                proc, path, _ = self.invoke('r2_layer.json', folder, folder)
                self.assertEqual(proc.returncode, code, proc.stderr)
                self.assertEqual(verify.read_result(path, {'files': {}})[0], 'failed' if code else 'passed')


if __name__ == "__main__":
    unittest.main()
