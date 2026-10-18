"""Exact differential expectations must reject a missing, new or changed guard decision, and the
normalization must erase the interpreter's own noise without erasing a decision's output."""

import copy
import unittest

from gate_diff import VOLATILE, expectation_errors

# One line of what python3.14.5 prints on stderr for the frozen 0.10.2 gate; 3.12 prints nothing.
# Recorded from the failing CI job, so the pattern is checked against the text it must erase.
POSITIONAL_MAXSPLIT = (
    "<GATE>:<LINE>: DeprecationWarning: 'maxsplit' is passed as positional argument\n"
    '  reason = re.split(r"(?<=[.;])\\s", str(specific.get("permissionDecisionReason", "")), 1)[0]\n')


def normalized(text):
    for pattern, repl in VOLATILE:
        text = pattern.sub(repl, text)
    return text


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


class VolatileTextTest(unittest.TestCase):
    def test_positional_maxsplit_warning_is_erased(self):
        self.assertEqual(normalized(POSITIONAL_MAXSPLIT), "")
        self.assertEqual(normalized(POSITIONAL_MAXSPLIT.replace("<GATE>:<LINE>:", "<GATE>:2520:")), "")
        # A decision's own stderr survives next to it, and another warning is not this warning.
        self.assertEqual(normalized(POSITIONAL_MAXSPLIT + "mycelium-extra gate: deny\n"),
                         "mycelium-extra gate: deny\n")
        other = "<GATE>:<LINE>: DeprecationWarning: some other api\n"
        self.assertEqual(normalized(other), other)


if __name__ == "__main__":
    unittest.main()
