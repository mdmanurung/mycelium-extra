"""Recorded method fidelity and its existing verify consumer; no fitted-model extraction claim."""
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/verify/scripts'))
import method_fidelity
import verify

FIXTURES = ROOT / 'tests/fixtures/sc-conventions'
SCRIPT = ROOT / 'skills/verify/scripts/method_fidelity.py'
EXPECTED = json.loads((FIXTURES / 'r3_expected.json').read_text())
OBSERVED = json.loads((FIXTURES / 'r3_observed.json').read_text())


class MethodFidelity(unittest.TestCase):
    def run_check(self, expected=EXPECTED, observed=OBSERVED):
        with tempfile.TemporaryDirectory() as folder:
            expected_path, observed_path = Path(folder) / 'expected.json', Path(folder) / 'observed.json'
            expected_path.write_text(json.dumps(expected))
            observed_path.write_text(json.dumps(observed))
            result = method_fidelity.compare(str(expected_path), str(observed_path))
            self.assertEqual(result['contract']['sha256'], hashlib.sha256(expected_path.read_bytes()).hexdigest())
            self.assertEqual(result['inputs'][1]['sha256'], hashlib.sha256(observed_path.read_bytes()).hexdigest())
            return result

    def test_all_fields_agree_and_explicit_empty_lists_are_allowed(self):
        self.assertEqual(self.run_check()['exit_code'], 0)
        expected, observed = copy.deepcopy(EXPECTED), copy.deepcopy(OBSERVED)
        for field in method_fidelity.LISTS:
            expected[field] = observed[field] = []
        self.assertEqual(self.run_check(expected, observed)['status'], 'pass')

    def test_each_field_drift_blocks(self):
        changes = {'formula': '~ condition', 'contrast': dict(OBSERVED['contrast'], sign=-1),
                   'random_effects': [], 'covariates': ['condition'], 'assay': 'X', 'exclusions': []}
        for field, value in changes.items():
            with self.subTest(field=field):
                result = self.run_check(observed=dict(OBSERVED, **{field: value}))
                self.assertEqual(result['exit_code'], 2)
                self.assertEqual([c['id'] for c in result['checks'] if c['status'] == 'block'], ['method-' + field])
        for field in ('numerator', 'denominator'):
            contrast = dict(OBSERVED['contrast'], **{field: 'other'})
            self.assertEqual(self.run_check(observed=dict(OBSERVED, contrast=contrast))['status'], 'block')

    def test_list_order_and_json_key_order_are_benign(self):
        observed = dict(reversed(list(OBSERVED.items())))
        observed['covariates'] = list(reversed(observed['covariates']))
        self.assertEqual(self.run_check(observed=observed)['status'], 'pass')

    def test_missing_null_and_unknown_fields_in_either_record_are_gaps(self):
        for which in ('expected', 'observed'):
            base = EXPECTED if which == 'expected' else OBSERVED
            for field in method_fidelity.FIELDS:
                for missing in (True, False):
                    record = copy.deepcopy(base)
                    if missing:
                        del record[field]
                    else:
                        record[field] = None
                    with self.subTest(which=which, field=field, missing=missing):
                        self.assertEqual(self.run_check(**{which: record})['status'], 'gap')
            for record in (dict(base, surprise='ignored?'), dict(base, schema='unknown.v2')):
                self.assertEqual(self.run_check(**{which: record})['exit_code'], 3)

    def test_malformed_types_and_contrast_are_gaps(self):
        bad = [dict(OBSERVED, formula=''), dict(OBSERVED, assay=12), [], None]
        for field in method_fidelity.LISTS:
            bad.extend(dict(OBSERVED, **{field: value}) for value in ('donor', [None], ['x', 'x'], [{}]))
        for contrast in ({}, {'numerator': 'a', 'denominator': 'a', 'sign': 1},
                         dict(OBSERVED['contrast'], sign=True), dict(OBSERVED['contrast'], sign=0),
                         dict(OBSERVED['contrast'], sign=1.0), dict(OBSERVED['contrast'], extra=1)):
            bad.append(dict(OBSERVED, contrast=contrast))
        for observed in bad:
            self.assertEqual(self.run_check(observed=observed)['status'], 'gap')

    def test_unreadable_invalid_utf8_json_and_duplicate_keys_are_gaps(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'record.json'
            for content in (b'not json', b'\xff', b'{"schema":1,"schema":2}'):
                path.write_bytes(content)
                self.assertEqual(method_fidelity.compare(str(FIXTURES / 'r3_expected.json'), str(path))['exit_code'], 3)
            path.unlink()
            self.assertEqual(method_fidelity.compare(str(path), str(path))['status'], 'gap')
            self.assertEqual(method_fidelity.compare(folder, folder)['status'], 'gap')

    def test_cli_red_green_and_existing_verify_changed_pin_and_gap(self):
        with tempfile.TemporaryDirectory() as folder:
            result_path = Path(folder) / 'result.json'
            expected = FIXTURES / 'r3_expected.json'
            pinned = {'files': {str(expected): hashlib.sha256(expected.read_bytes()).hexdigest()}}
            for observed, code, outcome in (('r3_wrong_sign.json', 2, 'failed'), ('r3_observed.json', 0, 'passed')):
                proc = subprocess.run([sys.executable, str(SCRIPT), '--expected', str(expected), '--observed',
                                       str(FIXTURES / observed), '--result-json', str(result_path)],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                self.assertEqual(proc.returncode, code, proc.stderr)
                self.assertEqual(verify.read_result(str(result_path), pinned)[0], outcome)
            changed = Path(folder) / 'changed.json'
            changed.write_text(json.dumps(dict(EXPECTED, assay='X')))
            result = method_fidelity.compare(str(changed), str(FIXTURES / 'r3_observed.json'))
            result_path.write_text(json.dumps(result))
            self.assertEqual(verify.read_result(str(result_path), pinned)[0], 'changed')
            result_path.write_text(json.dumps(method_fidelity.compare(str(expected), str(changed))))
            self.assertEqual(verify.read_result(str(result_path), pinned)[0], 'not run')

    def test_cli_preserves_inputs_and_reports_unwritable_output(self):
        with tempfile.TemporaryDirectory() as folder:
            expected = Path(folder) / 'expected.json'
            expected.write_text(json.dumps(EXPECTED))
            before = expected.read_bytes()
            for output in (str(expected), str(Path(folder) / 'missing/result.json')):
                proc = subprocess.run([sys.executable, str(SCRIPT), '--expected', str(expected), '--observed',
                                       str(FIXTURES / 'r3_observed.json'), '--result-json', output],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                self.assertEqual(proc.returncode, 3)
                self.assertEqual(expected.read_bytes(), before)
            link = Path(folder) / 'link.json'
            link.symlink_to(expected)
            proc = subprocess.run([sys.executable, str(SCRIPT), '--expected', str(expected), '--observed',
                                   str(FIXTURES / 'r3_observed.json'), '--result-json', str(link)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(proc.returncode, 3)
            self.assertEqual(expected.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
