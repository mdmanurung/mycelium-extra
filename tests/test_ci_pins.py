"""Run: python3 tests/test_ci_pins.py

The `gate-diff` job names one base commit and reads one oracle file, and `gate_diff.py --expect`
returns 1 when the file's `base` is not the commit `--base` resolves to. A re-base of the oracle
that leaves the workflow behind (or the reverse) is therefore red in CI for a reason no local test
named, and no suite here would say why. This test reads both, so the mismatch fails locally.
"""

import json
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = ".github/workflows/ci.yml"
EXPECTED = "hooks/tests/gate_diff_expected.json"
COMMAND = re.compile(r"gate_diff\.py --base (\S+) --expect (\S+)")


def read(rel):
    with open(os.path.join(REPO, rel), encoding="utf-8") as handle:
        return handle.read()


class WorkflowPinsTest(unittest.TestCase):
    def test_gate_diff_base_matches_the_committed_oracle(self):
        found = COMMAND.search(read(WORKFLOW))
        self.assertIsNotNone(found, "no `gate_diff.py --base … --expect …` in " + WORKFLOW)
        pin, oracle = found.groups()
        self.assertEqual(oracle, EXPECTED, "the job reads a different oracle file")
        base = json.loads(read(EXPECTED))["base"]
        # The oracle stores the resolved commit; the workflow may name it in full or abbreviated.
        self.assertGreaterEqual(len(pin), 7, pin)
        self.assertTrue(base.startswith(pin), "{} pins {}, the oracle is {}".format(WORKFLOW, pin, base))


if __name__ == "__main__":
    unittest.main()
