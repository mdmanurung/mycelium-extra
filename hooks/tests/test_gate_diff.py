"""Exact differential expectations must reject a missing, new or changed guard decision."""

import copy
import unittest

from gate_diff import expectation_errors


class DifferentialOracleTest(unittest.TestCase):
    def test_exact_expectations_reject_mutations(self):
        observed = {"guard": {"old": {"out": "allow"}, "new": {"out": "deny"}}}
        expected = copy.deepcopy(observed)
        expected["guard"]["rationale"] = "repaired boundary"
        self.assertEqual(expectation_errors(observed, expected), [])
        self.assertTrue(expectation_errors({}, expected))
        self.assertTrue(expectation_errors(dict(observed, extra=observed["guard"]), expected))
        mutation = copy.deepcopy(observed)
        mutation["guard"]["new"]["out"] = "allow"
        self.assertTrue(expectation_errors(mutation, expected))


if __name__ == "__main__":
    unittest.main()
