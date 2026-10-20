"""Run: python3 skills/verify/tests/test_audit_fixes.py

Regression tests for the verify findings in docs/roadmap/13-function-audit.md: a gap must never
read as a pass, and a bad input must say so instead of silently dropping a check.
"""

import decimal
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(PLUGIN, "hooks"))
sys.dont_write_bytecode = True
import gate  # noqa: E402
import test_verify  # noqa: E402


class Harness(test_verify.VerifyTest):
    """The verify harness (approve, run, write), without re-running its own tests."""


for _name in [name for name in dir(Harness) if name.startswith("test_")]:
    setattr(Harness, _name, None)  # inherited tests belong to test_verify.py


class AuditFixTest(Harness):
    # X13: a match by leading digits is stated, so "verified" is not read as "equal"
    def test_how_a_claim_matches_is_stated(self):
        verify = gate.load_verify()
        self.assertTrue(verify.agrees(decimal.Decimal("8"), "", decimal.Decimal("8.9")))
        digest, _ = self.claims_run("- 1.234 | outputs/de.tsv log2fc IL7R")
        out = self.verify("report", digest)
        self.assertIn("or its leading digits", out)

    # C19 + X10: a linter that never ran is not reported as clean
    def test_lint_that_did_not_run_is_not_clean(self):
        digest = self.approve(test_verify.plan("run `{}`".format(test_verify.FIT)))
        self.run_cmd("python " + test_verify.FIT)
        missing = os.path.join(self.root, "bin", "no-such-scilintr")
        summary = self.verify("report", digest, scilintr=missing)
        self.assertNotIn("lint clean", summary)
        self.assertIn("not checked: Python", summary)
        out = self.verify("disclose", digest, scilintr=missing)
        self.assertIn("[BLANK: scilintr did not run", out)
        self.assertNotIn("No lint finding was open", out)

    # X9: a wrong --analysis-dir is refused, not silently unchecked
    def test_wrong_analysis_dir_is_refused(self):
        digest = self.approve(test_verify.plan("run `{}`".format(test_verify.FIT)))
        error = self.verify("report", digest, "--analysis-dir", "analysis/not-here", fails=True)
        self.assertIn("is not a folder", error)
        self.assertIn("claims", error)

    # C20: provenance inside a folder the repository ignores is still found
    def test_provenance_in_an_ignored_folder_is_found(self):
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=self.root, check=True)
        self.write(".gitignore", "analysis/\n")
        rel = "analysis/a/provenance/receipts-0123abcd.jsonl"
        self.write(rel, "{}\n")
        verify = gate.load_verify()
        self.assertIn(rel, verify.provenance_receipts(self.root))

    # X11: a same-size rewrite still changes a run's content id
    def test_run_id_covers_mtime_as_well_as_size(self):
        verify = gate.load_verify()
        folder = os.path.join(self.root, "run_20260101_alpha")
        path = self.write("run_20260101_alpha/out.txt", "abcd")
        os.makedirs(folder, exist_ok=True)
        first = verify.scan_run(folder)[1]
        with open(path, "w") as handle:
            handle.write("abce")  # same size
        os.utime(path, ns=(1, 2 * 10 ** 9 + 123456789))
        second = verify.scan_run(folder)[1]
        self.assertNotEqual(first, second)

    # X12: a label whose status contradicts superseded_by is a finding
    def test_status_contradictions_are_findings(self):
        verify = gate.load_verify()
        results = os.path.join(self.root, "analysis", "a", "results")
        self.write("analysis/a/results/run_20260101_a/RUN.txt",
                   "run: run_20260101_a\nversion: 1\nkind: model\nstatus: current\n"
                   "superseded_by: run_20260101_b\n")
        self.write("analysis/a/results/run_20260101_b/RUN.txt",
                   "run: run_20260101_b\nversion: 2\nkind: model\nstatus: superseded\n")
        runs = [verify.label_run(os.path.join(results, name)) for name in sorted(os.listdir(results))]
        texts = [f["text"] for f in verify.run_findings(self.root, results, runs, []) if f["severity"] == "gap"]
        self.assertTrue(any("status `current` but `superseded_by" in text for text in texts), texts)
        self.assertTrue(any("status `superseded` but no `superseded_by`" in text for text in texts), texts)

    # X14: a write failure is a `verify:` error, not a traceback
    def test_write_failure_is_a_verify_error(self):
        digest = self.approve(test_verify.plan("run `{}`".format(test_verify.FIT)))
        self.run_cmd("python " + test_verify.FIT)
        folder = os.path.join(self.root, "analysis", "a")
        os.chmod(folder, 0o555)
        try:
            error = self.verify("write", digest, "--analysis-dir", "analysis/a", fails=True)
        finally:
            os.chmod(folder, 0o755)  # before tearDown removes the tree
        self.assertIn("verify: could not write", error)
        self.assertNotIn("Traceback", error)


if __name__ == "__main__":
    unittest.main(verbosity=2)
