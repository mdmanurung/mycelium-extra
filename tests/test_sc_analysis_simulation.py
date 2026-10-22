"""Check real-package synthetic outputs; set MX_SC_SIMULATION to the R run directory.

Run sc_analysis_simulation.R with R4_51 first. These checks never launch a model,
install a package, read sealed keys, or claim scientific calibration.
"""
import copy
import csv
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SIMULATION = Path(os.environ.get('MX_SC_SIMULATION', '/nonexistent-sc-simulation'))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless((SIMULATION / 'receipt.json').is_file(), 'set MX_SC_SIMULATION to an actual R simulation run')
class RealPackageSimulation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.checker = load('simulation_contracts', ROOT / 'skills/data-contract-check/scripts/data_contract_check.py')
        cls.method = load('simulation_method', ROOT / 'skills/verify/scripts/method_fidelity.py')
        with (SIMULATION / 'samples.tsv').open() as handle:
            cls.samples = list(csv.DictReader(handle, delimiter='\t'))

    def test_actual_metadata_passes_and_missing_pair_or_aliased_batch_blocks(self):
        checks = [{'kind': 'unit_of_replication', 'unit': 'donor', 'group': 'condition',
                   'within': [], 'min_units_per_group': 8, 'units_may_span_groups': True},
                  {'kind': 'pairing', 'unit': 'donor', 'within': 'condition',
                   'levels': ['control', 'stimulated']},
                  {'kind': 'batch_confounding', 'batch': 'batch', 'contrast': 'condition'}]
        for scenario in ('valid', 'missing-pair', 'aliased'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as tmp:
                samples = copy.deepcopy(self.samples)
                if scenario == 'missing-pair':
                    samples = samples[:-1]
                if scenario == 'aliased':
                    for row in samples:
                        row['batch'] = row['condition']
                table = Path(tmp) / 'samples.tsv'
                with table.open('w', newline='') as handle:
                    writer = csv.DictWriter(handle, fieldnames=list(samples[0]), delimiter='\t')
                    writer.writeheader()
                    writer.writerows(samples)
                contract = {'schema': self.checker.SCHEMA, 'table': table.name, 'checks': checks}
                summaries, _ = self.checker.run_contract(contract, tmp)
                statuses = {row['kind']: row['status'] for row in summaries}
                if scenario == 'valid':
                    self.assertEqual(set(statuses.values()), {'pass'})
                else:
                    failed = 'pairing' if scenario == 'missing-pair' else 'batch_confounding'
                    self.assertEqual(statuses[failed], 'block')

    def test_actual_counts_survive_h5ad_and_normalized_X_is_rejected_as_counts(self):
        try:
            import anndata
            import numpy as np
            import pandas as pd
        except ImportError as error:
            self.skipTest('AnnData interoperability dependencies absent: ' + str(error))
        with (SIMULATION / 'counts.tsv').open() as handle:
            records = list(csv.reader(handle, delimiter='\t'))
        genes = [row[0] for row in records[1:]]
        cells = records[0][1:]
        counts = np.array([[int(value) for value in row[1:]] for row in records[1:]], dtype=np.int64).T
        self.assertEqual(counts.shape, (len(cells), len(genes)))
        original = counts.copy()
        normalized = np.log1p(counts)
        data = anndata.AnnData(X=normalized, dtype=normalized.dtype,
                              obs=pd.DataFrame(index=cells), var=pd.DataFrame(index=genes))
        data.layers['counts'] = counts
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'simulation.h5ad'
            data.write_h5ad(path)
            reread = anndata.read_h5ad(path)
            np.testing.assert_array_equal(reread.layers['counts'], original)
            self.assertEqual(list(reread.obs_names), cells)
            self.assertEqual(list(reread.var_names), genes)
            for layer, expected in [('layers/counts', 'pass'), ('X', 'block')]:
                contract = {'schema': self.checker.SCHEMA, 'table': path.name,
                            'checks': [{'kind': 'h5ad_layer', 'h5_path': layer,
                                        'sample_values': counts.size,
                                        'properties': {'integer_valued': True, 'non_negative': True}}]}
                summaries, _ = self.checker.run_contract(contract, tmp)
                self.assertEqual([row['status'] for row in summaries], [expected])
        np.testing.assert_array_equal(counts, original)

    def test_actual_fitted_formula_passes_and_fitted_omitted_donor_blocks(self):
        expected = str(SIMULATION / 'method-expected.json')
        matching = self.method.compare(expected, str(SIMULATION / 'method-observed.json'))
        self.assertEqual(matching['status'], 'pass', matching)
        omitted = self.method.compare(expected, str(SIMULATION / 'method-omitted-donor.json'))
        self.assertEqual(omitted['status'], 'block', omitted)
        failures = {row['id'] for row in omitted['checks'] if row['status'] == 'block'}
        self.assertTrue({'method-formula', 'method-random_effects'} <= failures)


if __name__ == '__main__':
    unittest.main()
