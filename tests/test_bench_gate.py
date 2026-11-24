#!/usr/bin/env python3
"""Tests for tests/bench/score_gate.py, the gate classifier benchmark.

Run: python3 tests/test_bench_gate.py
"""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH = os.path.join(ROOT, "tests", "bench")
CORPUS = os.path.join(BENCH, "gate_corpus")
sys.path.insert(0, BENCH)
import score_gate  # noqa: E402


def write_corpus(cases):
    handle = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    with handle:
        for case in cases:
            handle.write(json.dumps(case) + "\n")
    return handle.name


def run(*argv):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        score_gate.main(list(argv))
    return buffer.getvalue()


class ScorerTest(unittest.TestCase):
    def test_counts_both_error_classes(self):
        path = write_corpus([
            {"id": "ok", "family": "f", "command": "python analysis/a.py", "expect": ["analysis/a.py"]},
            {"id": "miss", "family": "f", "command": "cat analysis/a.py", "expect": ["analysis/a.py"]},
            {"id": "extra", "family": "g", "command": "python analysis/a.py", "expect": []},
        ])
        self.addCleanup(os.remove, path)
        report = json.loads(run(path, "--json"))[os.path.basename(path)]
        self.assertEqual((report["n"], report["false_pass"], report["false_deny"]), (3, 1, 1))
        self.assertEqual(sorted(r["id"] for r in report["failures"]), ["extra", "miss"])
        self.assertEqual(report["families"]["g"], {"n": 1, "n_run": 0, "false_pass": 0, "false_deny": 1})

    def test_sealed_prints_no_case_text(self):
        path = write_corpus([
            {"id": "secret-id", "family": "f", "command": "cat analysis/secret.py", "expect": ["analysis/secret.py"]},
        ])
        self.addCleanup(os.remove, path)
        log = path + ".looks"
        self.addCleanup(os.remove, log)
        out = run(path, "--sealed", "--looks-log", log) + run(path, "--sealed", "--json", "--looks-log", log)
        self.assertNotIn("secret", out)
        self.assertIn("false_pass=1", out)
        with open(log, encoding="utf-8") as handle:
            looks = handle.read()
        self.assertEqual(looks.count("\n"), 2)
        self.assertNotIn("secret", looks)

    def test_refuses_duplicate_ids_and_missing_fields(self):
        dup = write_corpus([{"id": "a", "family": "f", "command": "ls", "expect": []}] * 2)
        bad = write_corpus([{"id": "a", "family": "f", "command": "ls"}])
        self.addCleanup(os.remove, dup)
        self.addCleanup(os.remove, bad)
        with self.assertRaises(ValueError):
            score_gate.read_cases(dup)
        with self.assertRaises(ValueError):
            score_gate.read_cases(bad)

    def test_shipped_corpora_parse(self):
        for name in ("seeds.jsonl", "mined.jsonl"):
            self.assertTrue(score_gate.read_cases(os.path.join(CORPUS, name)))

    def test_mined_corpus_matches_the_classifier(self):
        # mined labels are today's decisions; a change here is a decision change to review, then remine
        report = json.loads(run(os.path.join(CORPUS, "mined.jsonl"), "--json"))["mined.jsonl"]
        self.assertEqual((report["false_pass"], report["false_deny"], report["errors"]), (0, 0, 0),
                         report["failures"][:5])


if __name__ == "__main__":
    unittest.main()
