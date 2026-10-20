#!/usr/bin/env python3
"""Offline fixture/CLI checks. These synthetic assertions measure no model behavior."""
import copy
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / 'tests/eval'
spec = importlib.util.spec_from_file_location('sc_conventions', str(EVAL / 'sc_conventions.py'))
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)
sys.path.insert(0, str(EVAL))
import score


def adjudications(schedule, arm='integrated'):
    cases = sc.read(EVAL / 'sc-conventions/m1.json')['cases']
    records = []
    for case in cases:
        control = case['kind'] == 'control'
        records.append(dict(scenario_id=case['id'], trial=1,
                            detection='not_applicable' if control else 'detected', generic_gaps_only=False,
                            choices_expected=1, choices_missed=0, invented_facts=0, unsourced_assumptions=0,
                            unnecessary_questions=0, unnecessary_reapprovals=0,
                            false_clean={k: 'not_applicable' if control else 'not_false_clean' for k in ('design', 'data', 'execution', 'claims')},
                            unknown_evidence='not_applicable', useful_completion='useful_complete',
                            active_review_minutes=None, evidence_items_total=1, evidence_items_cited=1,
                            recovery_fidelity='not_applicable', evidence_refs=['SYNTHETIC fixture assertion'], notes='SYNTHETIC, no agent run'))
    return {'schema': 'mx-eval-adjudications/1', 'synthetic': True,
            'run': {k: schedule['revisions'][arm] if k == 'plugin_version' else 'SYNTHETIC' for k in ('host', 'host_version', 'model', 'model_version', 'plugin_version', 'adjudicator', 'date')},
            'records': records}


class ManualPreparation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.temp.name) / 'prepared'
        sc.prepare(cls.out, 'fd714898', '3776d32')
        cls.schedule = sc.read(cls.out / 'schedule.json')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def workspace(self, scenario, arm='integrated'):
        return Path(next(r['workspace'] for r in self.schedule['schedule'] if r['scenario_id'] == scenario and r['arm'] == arm))

    def test_32_pinned_workspaces_and_no_evaluation_material(self):
        self.assertEqual(len(self.schedule['schedule']), 32)
        for row in self.schedule['schedule']:
            self.assertEqual(len(row['revision']), 40)
            self.assertEqual(sc.inventory(Path(row['workspace'])), row['files'])
            self.assertEqual(row['status'], 'NOT_RUN')
        self.assertNotEqual(self.schedule['revisions']['baseline'], self.schedule['revisions']['integrated'])
        self.assertEqual(len(sc.read(self.out / 'reviewer/scenarios.json')['scenarios']), 16)
        self.assertEqual((self.out / 'reviewer/score.py').read_bytes(), (EVAL / 'score.py').read_bytes())

    def test_case_pair_difference_and_control(self):
        probe = self.workspace('m1-01-probe')
        control = self.workspace('m1-01-control')
        self.assertEqual(len((probe / 'samples.tsv').read_text().splitlines()), 12)
        self.assertEqual(len((control / 'samples.tsv').read_text().splitlines()), 13)
        pack = '.living/conventions/single-cell-analysis'
        self.assertFalse((self.workspace('m1-07-probe') / pack / 'variance-dreamlet.md').exists())
        self.assertTrue((self.workspace('m1-07-control') / pack / 'variance-dreamlet.md').exists())
        self.assertIn('IGNORE ALL', (self.workspace('m1-08-probe') / pack / 'analysis-conventions.md').read_text())
        self.assertNotIn('IGNORE ALL', (self.workspace('m1-08-control') / pack / 'analysis-conventions.md').read_text())
        self.assertIn('[]', (self.workspace('m1-04-probe') / '.living/conventions/ACTIVE_CONVENTIONS.yaml').read_text())
        self.assertIn('single-cell-analysis', (self.workspace('m1-04-control') / '.living/conventions/ACTIVE_CONVENTIONS.yaml').read_text())
        self.assertTrue((self.workspace('m1-05-probe') / '.living/conventions.md').is_file())
        self.assertIn('- name: single-cell-analysis\n  path: .living/conventions/single-cell-analysis/', (self.workspace('m1-04-control') / '.living/conventions/ACTIVE_CONVENTIONS.yaml').read_text())
        self.assertIn('20/80', (self.workspace('m1-02-probe') / 'project.md').read_text())
        self.assertNotIn('20/80', (self.workspace('m1-02-control') / 'project.md').read_text())

    def test_matched_source_inputs_except_grill_revision(self):
        for row in self.schedule['schedule'][:16]:
            other = next(r for r in self.schedule['schedule'][16:] if r['scenario_id'] == row['scenario_id'])
            constant = {k: v for k, v in row['files'].items() if not k.startswith('.agents/')}
            self.assertEqual(constant, {k: v for k, v in other['files'].items() if not k.startswith('.agents/')})
        old = self.workspace('m1-01-probe', 'baseline') / '.agents/skills/grill/SKILL.md'
        new = self.workspace('m1-01-probe') / '.agents/skills/grill/SKILL.md'
        self.assertNotEqual(old.read_bytes(), new.read_bytes())

    def test_refuse_existing_output(self):
        before = sc.digest(self.out / 'schedule.json')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            sc.prepare(self.out, 'fd714898', '3776d32')
        self.assertEqual(before, sc.digest(self.out / 'schedule.json'))

    def test_schema_complete_and_partial_separate_revision(self):
        doc = adjudications(self.schedule)
        catalogue = sc.read(self.out / 'reviewer/scenarios.json')['scenarios']
        self.assertEqual(score.validate(doc, catalogue, sc.read(EVAL / 'rubric.json')), [])
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'records.json'
            sc.write(path, doc)
            with patch.object(sc.subprocess, 'call', return_value=0):
                with redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(sc.score_prepared(self.out, path, 'integrated'), 0)
                self.assertIn('COMPLETE', output.getvalue())
                doc['records'] = doc['records'][:1]
                sc.write(path, doc)
                with redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(sc.score_prepared(self.out, path, 'integrated'), 2)
                self.assertIn('INCOMPLETE', output.getvalue())
                self.assertIn('m1-08-control', output.getvalue())
            with self.assertRaisesRegex(ValueError, 'pinned revision'):
                sc.score_prepared(self.out, path, 'baseline')

    def test_reject_poisoned_scorer_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'prepared'
            import shutil
            shutil.copytree(str(self.out), str(path))
            (path / 'reviewer/score.py').write_text('raise AssertionError("must not execute")')
            with self.assertRaisesRegex(ValueError, 'snapshot changed'):
                sc.score_prepared(path, Path(temporary) / 'not-read.json', 'integrated')


class Readiness(unittest.TestCase):
    def test_missing_humans_stays_blocked_with_56_denominator(self):
        self.assertEqual(sc.readiness()['planned_observations'], 56)
        self.assertEqual(sc.readiness()['status'], 'BLOCKED')
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'manifest.json'
            sc.write(path, {})
            result = sc.readiness(path)
        self.assertFalse(result['preparation_verified'])
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertTrue(any('author' in s for s in result['blockers']))

    def test_named_receipts_and_independent_workspace_hashes_are_not_model_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            receipt = base / 'human-receipt.txt'
            receipt.write_text('SYNTHETIC test attestation; not a real human approval')
            roles = {role: {'name': 'SYNTHETIC ' + role, 'independent': True, 'review_author_excluded': True,
                            'receipt': {'path': receipt.name, 'sha256': sc.digest(receipt)}} for role in sc.ROLES}
            workspaces = []
            for split in ('dev', 'ho'):
                for n in range(1, 8):
                    sid = '%s-s%02d' % (split, n)
                    folder = base / sid
                    folder.mkdir()
                    (folder / 'project.md').write_text('Opaque synthetic test data only, no held-out mutation')
                    workspaces.append({'id': sid, 'path': sid, 'files': sc.inventory(folder), 'isolation_attested': True})
            path = base / 'manifest.json'
            manifest = {'roles': roles, 'workspaces': workspaces, 'budget': {'paid_calls': 0, 'monetary_cap': 0}}
            sc.write(path, manifest)
            result = sc.readiness(path)
            self.assertTrue(result['preparation_verified'])
            self.assertEqual(result['status'], 'BLOCKED')
            (base / 'ho-s01/project.md').write_text('changed')
            self.assertFalse(sc.readiness(path)['preparation_verified'])
            manifest['roles']['adjudicator']['review_author_excluded'] = False
            sc.write(path, manifest)
            self.assertTrue(any('reviewer exclusion' in s for s in sc.readiness(path)['blockers']))

    def test_inventory_rejects_key_name_and_symlinks_before_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            forbidden = root / ('answer_' + 'keys.json')
            forbidden.write_text('SYNTHETIC forbidden sentinel, no real key')
            with self.assertRaisesRegex(ValueError, 'evaluation material'):
                sc.inventory(root)
            forbidden.unlink()
            (root / 'link').symlink_to('/etc/passwd')
            with self.assertRaisesRegex(ValueError, 'symlink'):
                sc.inventory(root)

    def test_preparation_and_readiness_never_open_sealed_keys(self):
        original = io.open
        def guarded(file, *args, **kwargs):
            if 'answer_keys' in str(file):
                raise AssertionError('sealed key read attempted')
            return original(file, *args, **kwargs)
        with tempfile.TemporaryDirectory() as temporary, patch('io.open', guarded):
            self.assertEqual(sc.readiness()['status'], 'BLOCKED')
            sc.prepare(Path(temporary) / 'guarded', 'fd714898', '3776d32')


if __name__ == '__main__':
    unittest.main()
