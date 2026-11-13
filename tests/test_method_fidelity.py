"""Recorded method fidelity and its existing verify consumer; no fitted-model extraction claim."""
import copy
import hashlib
import json
import os
import subprocess
import sys
import shutil
import tempfile
import time
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/verify/scripts'))
sys.path.insert(0, str(ROOT / 'hooks'))
import gate
import validation
import method_fidelity
import verify

verify.gate = gate  # the module verify loads from --plugin-root, needed by judge_check

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


R5_EXPECTED = FIXTURES / 'r5_expected.json'
R5_TABLE_SHA = hashlib.sha256((FIXTURES / 'r5_samples.tsv').read_bytes()).hexdigest()


def r5(name):
    return json.loads((FIXTURES / ('r5_design_' + name + '.json')).read_text())


class DesignFidelity(unittest.TestCase):
    """R5: the design matrix and contrast the fitting code wrote, against the approved ones."""

    def check(self, observed, expected=None):
        with tempfile.TemporaryDirectory() as folder:
            expected_path, observed_path = Path(folder) / 'expected.json', Path(folder) / 'observed.json'
            expected_path.write_text(json.dumps(expected or json.loads(R5_EXPECTED.read_text())))
            observed_path.write_text(observed if isinstance(observed, str) else json.dumps(observed))
            return method_fidelity.compare(str(expected_path), str(observed_path))

    def statuses(self, result):
        return {c['id']: c['status'] for c in result['checks']}

    def test_known_direction_paired_design_passes(self):
        result = self.check(r5('pass'))
        self.assertEqual((result['status'], result['exit_code']), ('pass', 0))
        self.assertEqual(set(self.statuses(result).values()), {'pass'})
        self.assertEqual(result['schema'], 'mycelium-extra.contract_result.v1')

    def test_reversed_contrast_blocks_on_sign_only(self):
        result = self.check(r5('reversed'))
        self.assertEqual(result['exit_code'], 2)
        self.assertEqual([c['id'] for c in result['checks'] if c['status'] == 'block'], ['fit-contrast'])

    def test_condition_confounded_with_batch_blocks(self):
        result = self.check(r5('confounded'))
        self.assertEqual(result['exit_code'], 2)
        states = self.statuses(result)
        self.assertEqual((states['fit-estimable'], states['fit-batch-confounding']), ('block', 'block'))
        self.assertEqual(states['fit-contrast'], 'pass')
        estimable = [c for c in result['checks'] if c['id'] == 'fit-estimable'][0]
        self.assertTrue(estimable['estimable_without_batch'])
        self.assertIn('aliased with batch', estimable['message'])

    def test_fit_output_without_a_design_is_a_gap_with_a_reason(self):
        result = self.check(r5('missing'))
        self.assertEqual((result['status'], result['exit_code']), ('gap', 3))
        self.assertIn('no design matrix', result['checks'][0]['message'])

    def test_unreadable_or_malformed_fit_output_is_a_gap(self):
        good = r5('pass')
        bad = ['not json', '[]', json.dumps(dict(good, schema='other.v1')),
               json.dumps(dict(good, design=[[1, 0]])), json.dumps(dict(good, design=[[1, 0, 0, 0, 0, True]] * 8)),
               json.dumps(dict(good, design_columns=['a'] * 6)), json.dumps(dict(good, contrast={'nope': 1})),
               json.dumps(dict(good, contrast={})), json.dumps(dict(good, design=[]))]
        for observed in bad:
            with self.subTest(observed=observed[:50]):
                self.assertEqual(self.check(observed)['exit_code'], 3)
        result = method_fidelity.compare(str(R5_EXPECTED), str(FIXTURES / 'does_not_exist.json'))
        self.assertEqual(result['exit_code'], 3)
        self.assertIn('observed:', result['checks'][0]['message'])

    def test_malformed_expected_record_is_a_gap(self):
        base = json.loads(R5_EXPECTED.read_text())
        for expected in (dict(base, contrast={'conditionstimulated': 0}), dict(base, contrast={}),
                         dict(base, batch_columns='batchb2'), dict(base, surprise=1),
                         {k: v for k, v in base.items() if k != 'batch_columns'}):
            self.assertEqual(self.check(r5('pass'), expected)['exit_code'], 3)

    def test_formula_spacing_is_benign_and_a_changed_formula_blocks(self):
        self.assertEqual(self.check(dict(r5('pass'), formula='~condition+batch+donor'))['status'], 'pass')
        result = self.check(dict(r5('pass'), formula='~ condition + donor'))
        self.assertEqual([c['id'] for c in result['checks'] if c['status'] == 'block'], ['fit-formula'])

    def test_sample_table_hash_is_compared_when_the_approval_pins_it(self):
        expected = dict(json.loads(R5_EXPECTED.read_text()), sample_table_sha256=R5_TABLE_SHA)
        self.assertEqual(self.check(r5('pass'), expected)['status'], 'pass')
        other = hashlib.sha256((FIXTURES / 'r5_samples_confounded.tsv').read_bytes()).hexdigest()
        result = self.check(dict(r5('pass'), sample_table_sha256=other), expected)
        self.assertEqual([c['id'] for c in result['checks'] if c['status'] == 'block'], ['fit-sample-table'])

    def test_missing_batch_term_blocks_and_no_batch_is_allowed(self):
        good = r5('pass')
        drop = [0, 1, 3, 4, 5]
        no_batch = dict(good, design_columns=[good['design_columns'][i] for i in drop],
                        design=[[row[i] for i in drop] for row in good['design']])
        result = self.check(no_batch)
        self.assertEqual([c['id'] for c in result['checks'] if c['status'] == 'block'], ['fit-batch-term'])
        expected = dict(json.loads(R5_EXPECTED.read_text()), batch_columns=[])
        self.assertEqual(self.check(no_batch, expected)['status'], 'pass')

    def test_one_large_scale_column_does_not_hide_an_aliased_contrast(self):
        cond = [i % 2 for i in range(40)]
        columns = ['(Intercept)', 'a', 'b', 'depth']
        expected = {'schema': method_fidelity.DESIGN_EXPECTED, 'contrast': {'a': 1}, 'batch_columns': []}
        for depth in (1, 1e8):
            observed = {'schema': method_fidelity.FIT_DESIGN, 'design_columns': columns, 'contrast': {'a': 1},
                        'design': [[1, c, c, depth * (1 + i % 5)] for i, c in enumerate(cond)]}  # b copies a
            result = method_fidelity.compare_design([{'path': 'x', 'sha256': 'y', 'role': 'r'}], expected, observed, None)
            self.assertEqual(self.statuses(result)['fit-estimable'], 'block', depth)

    def test_rank_by_elimination(self):
        self.assertEqual(method_fidelity.rank([[1, 2], [2, 4], [0, 0]]), 1)
        self.assertEqual(method_fidelity.rank([[1, 0, 0], [0, 1, 0], [1, 1, 1e-14]]), 2)
        self.assertEqual(method_fidelity.rank(r5('pass')['design']), 6)
        self.assertEqual(method_fidelity.rank(r5('confounded')['design']), 5)
        self.assertEqual(method_fidelity.rank([[0, 0]]), 0)

    def test_cli_exit_codes_and_the_real_verify_judge(self):
        # Same path as a live run: a bound invocation, an attributable run record, verify.judge_check.
        for observed, code, outcome in (('pass', 0, 'passed'), ('reversed', 2, 'failed'),
                                        ('confounded', 2, 'failed'), ('missing', 3, 'not run')):
            with self.subTest(observed=observed), tempfile.TemporaryDirectory() as folder:
                os.makedirs(os.path.join(folder, 'checks'))
                script, contract = 'checks/method_fidelity.py', 'checks/r5_expected.json'
                shutil.copyfile(SCRIPT, os.path.join(folder, script))
                shutil.copyfile(R5_EXPECTED, os.path.join(folder, contract))
                shutil.copyfile(FIXTURES / ('r5_design_' + observed + '.json'), os.path.join(folder, 'fit_design.json'))
                declaration = {'id': 'fit-design', 'plan_row': '4', 'required': True, 'defined_by': 'researcher-approved',
                               'test_paths': [script, contract], 'evidence_path': 'result.json',
                               'invocation': [sys.executable, script, '--expected', contract, '--observed',
                                              'fit_design.json', '--result-json', 'result.json']}
                text = '<!-- validation-bindings ' + json.dumps({'version': 1, 'checks': [declaration]}) + ' -->'
                binding, errors = validation.read_bindings(text, ['4'], folder)
                self.assertEqual(errors, [])
                check = binding['checks'][0]
                proc = subprocess.run(check['invocation'], cwd=folder, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, universal_newlines=True)
                self.assertEqual(proc.returncode, code, proc.stderr)
                run = {'attempt_id': 'c' * 16, 'ts': time.time() + 1, 'exit_status': proc.returncode,
                       'outputs_observation': 'observed', 'outputs_changed': {'created': ['result.json']}}
                self.assertEqual(verify.judge_check(folder, check, [run], {}, False)['outcome'], outcome)
                if code == 0:
                    # A harmless whitespace edit after approval changes the pinned bytes; the next run is "changed".
                    with open(os.path.join(folder, contract), 'a') as target:
                        target.write('\n')
                    subprocess.run(check['invocation'], cwd=folder, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    self.assertEqual(verify.judge_check(folder, check, [run], {}, False)['outcome'], 'changed')

    def test_python_extraction_snippet_round_trips_through_the_checker(self):
        sys.path.insert(0, str(FIXTURES))
        try:
            from extract_design import extract_design
        finally:
            sys.path.remove(str(FIXTURES))
        good = r5('pass')
        with tempfile.TemporaryDirectory() as folder:
            out = os.path.join(folder, 'fit_design.json')
            extract_design(good['design'], {'conditionstimulated': 1, 'batchb2': 0}, '~ condition + batch + donor',
                           FIXTURES / 'r5_samples.tsv', out, columns=good['design_columns'],
                           coefficient='conditionstimulated')
            written = json.loads(Path(out).read_text())
            self.assertEqual(written['contrast'], {'conditionstimulated': 1.0})
            self.assertEqual(written['sample_table_sha256'], R5_TABLE_SHA)
            self.assertEqual(self.check(Path(out).read_text())['status'], 'pass')
            try:
                import numpy as np
                import patsy
            except ImportError:
                return  # the list path above is the portable one; patsy is optional
            table = {'condition': ['control', 'stimulated'] * 4, 'batch': ['b1', 'b2', 'b2', 'b1'] * 2,
                     'donor': [d for d in ('d1', 'd2', 'd3', 'd4') for _ in range(2)]}
            matrix = patsy.dmatrix('C(condition) + C(batch) + C(donor)', table)
            self.assertEqual(matrix.design_info.column_names[1], 'C(condition)[T.stimulated]')
            extract_design(np.asarray(matrix), {'C(condition)[T.stimulated]': 1}, 'patsy',
                           FIXTURES / 'r5_samples.tsv', out, columns=matrix.design_info.column_names)
            self.assertEqual(len(json.loads(Path(out).read_text())['design']), 8)

    def test_r_extraction_snippet_on_a_real_limma_fit(self):
        rscript = os.environ.get('RSCRIPT') or shutil.which('Rscript')
        if not rscript:
            self.skipTest('Rscript not available')
        probe = subprocess.run([rscript, '-e', 'for (p in c("limma","jsonlite","digest")) library(p, character.only = TRUE)'],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if probe.returncode:
            self.skipTest('limma, jsonlite or digest not installed')
        for flag, outcome in ((None, 'pass'), ('reverse', 'block')):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as folder:
                out = os.path.join(folder, 'fit_design.json')
                command = [rscript, str(FIXTURES / 'r5_fit_demo.R'), str(FIXTURES), out] + ([flag] if flag else [])
                proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                written = json.loads(Path(out).read_text())
                self.assertEqual(written['design'], r5('pass')['design'])  # hand-written fixture agrees with model.matrix
                self.assertEqual(self.check(Path(out).read_text())['status'], outcome)


if __name__ == '__main__':
    unittest.main()
