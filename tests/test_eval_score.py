#!/usr/bin/env python3
"""Tests for tests/eval/score.py and the leakage rules of the evaluation scaffold.

Every adjudication used here is SYNTHETIC. Nothing in this file measures the product.
Stdlib only, Python 3.6 grammar.
"""

import copy
import io
import json
import os
import re
import subprocess
import sys
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL = os.path.join(ROOT, "tests", "eval")
sys.path.insert(0, EVAL)
import score  # noqa: E402


def load(*parts):
    with open(os.path.join(EVAL, *parts), encoding="utf-8") as handle:
        return json.load(handle)


SCENARIOS = load("scenarios.json")["scenarios"]
RUBRIC = load("rubric.json")
SYNTH = os.path.join(EVAL, "examples", "synthetic-adjudications.json")


def doc():
    return copy.deepcopy(load("examples", "synthetic-adjudications.json"))


def errors_of(d):
    return score.validate(d, SCENARIOS, RUBRIC)


def run_main(args):
    out = io.StringIO()
    with redirect_stdout(out):
        code = score.main(args)
    return code, out.getvalue()


class Schema(unittest.TestCase):
    def test_public_classes_never_open_answer_keys(self):
        # A fresh interpreter guards import as well as every other public test.
        script = r'''import builtins
import io
import os
import runpy
import sys
import unittest

def guard(original):
    def checked(path, *args, **kwargs):
        if not isinstance(path, int) and os.path.basename(os.fsdecode(path)) == "answer_keys.json":
            raise AssertionError("public tests attempted sealed-key access")
        return original(path, *args, **kwargs)
    return checked

builtins.open = guard(builtins.open)
io.open = guard(io.open)
os.open = guard(os.open)
try:
    open("answer_keys.json")
except AssertionError:
    pass
else:
    raise AssertionError("sealed-key guard did not fire")
module = runpy.run_path(sys.argv[1], run_name="public_eval_test_guard")
suite = unittest.TestSuite()
for name in ("Schema", "Totals", "Banner"):
    cls = module[name]
    for method in unittest.defaultTestLoader.getTestCaseNames(cls):
        if method != "test_public_classes_never_open_answer_keys":
            suite.addTest(cls(method))
expected_count = suite.countTestCases()
assert expected_count > 0
result = unittest.TextTestRunner().run(suite)
assert result.testsRun == expected_count, result.testsRun
sys.exit(not result.wasSuccessful())
'''
        result = subprocess.run([sys.executable, "-c", script, os.path.abspath(__file__)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_synthetic_example_is_valid(self):
        self.assertEqual(errors_of(doc()), [])

    def test_missing_record_field_refused(self):
        d = doc()
        del d["records"][0]["detection"]
        self.assertIn("record 0: missing field 'detection'", errors_of(d))

    def test_unknown_record_field_refused(self):
        d = doc()
        d["records"][0]["score"] = 1
        self.assertIn("record 0: unknown field 'score'", errors_of(d))

    def test_unknown_top_level_and_run_fields_refused(self):
        d = doc()
        d["verdict"] = "pass"
        d["run"]["temperature"] = "0"
        errs = errors_of(d)
        self.assertIn("unknown top-level field 'verdict'", errs)
        self.assertIn("run: unknown field 'temperature'", errs)

    def test_missing_top_level_field_refused(self):
        d = doc()
        del d["synthetic"]
        self.assertEqual(errors_of(d), ["missing top-level field 'synthetic'"])

    def test_bad_values_refused(self):
        for field, value in [("detection", "mostly"), ("choices_expected", True), ("unnecessary_questions", -1),
                             ("generic_gaps_only", "yes"), ("evidence_refs", []), ("active_review_minutes", "10")]:
            d = doc()
            d["records"][0][field] = value
            self.assertTrue(errors_of(d), field)

    def test_false_clean_dimension_set_is_exact(self):
        d = doc()
        del d["records"][0]["false_clean"]["claims"]
        d["records"][0]["false_clean"]["style"] = "false_clean"
        errs = errors_of(d)
        self.assertTrue(any("missing 'claims'" in e for e in errs))
        self.assertTrue(any("unknown key 'style'" in e for e in errs))

    def test_unknown_scenario_and_duplicate_refused(self):
        d = doc()
        d["records"][0]["scenario_id"] = "dev-s99"
        self.assertTrue(any("unknown scenario_id" in e for e in errors_of(d)))
        d = doc()
        d["records"].append(copy.deepcopy(d["records"][0]))
        self.assertTrue(any("duplicate scenario_id" in e for e in errors_of(d)))

    def test_generic_gap_is_not_detection(self):
        d = doc()
        d["records"][0]["generic_gaps_only"] = True  # dev-s01 is "detected"
        self.assertTrue(any("not detection" in e for e in errors_of(d)))

    def test_control_and_defect_consistency(self):
        d = doc()
        d["records"][5]["detection"] = "missed"  # dev-s06 is a control
        self.assertTrue(any("wrong for a control" in e for e in errors_of(d)))
        d = doc()
        d["records"][0]["detection"] = "not_applicable"
        self.assertTrue(any("wrong for a defect" in e for e in errors_of(d)))
        d = doc()
        d["records"][5]["false_clean"]["data"] = "not_false_clean"
        self.assertTrue(any("must be not_applicable" in e for e in errors_of(d)))

    def test_count_pair_and_recovery_rules(self):
        d = doc()
        d["records"][0]["choices_missed"] = 2
        d["records"][0]["evidence_items_cited"] = 9
        errs = errors_of(d)
        self.assertTrue(any("choices_missed exceeds" in e for e in errs))
        self.assertTrue(any("evidence_items_cited exceeds" in e for e in errs))
        d = doc()
        d["records"][9]["recovery_fidelity"] = "not_applicable"  # ho-s06 has recovery=true
        self.assertTrue(any("recovery_fidelity" in e for e in errors_of(d)))

    def test_refused_file_prints_errors_and_no_scores(self):
        d = doc()
        del d["records"][0]["detection"]
        path = os.path.join(os.environ.get("TMPDIR", "/tmp"), "mx-eval-bad-%d.json" % os.getpid())
        with open(path, "w") as handle:
            json.dump(d, handle)
        try:
            code, out = run_main([path])
        finally:
            os.remove(path)
        self.assertEqual(code, 1)
        self.assertIn("REFUSED", out)
        self.assertNotIn("protection", out)


class Totals(unittest.TestCase):
    """Totals below were worked out by hand from examples/synthetic-adjudications.json."""

    def setUp(self):
        self.out = score.aggregate(doc(), SCENARIOS, RUBRIC)

    def test_development_totals(self):
        p, b = self.out["development"]["protection"], self.out["development"]["burden"]
        self.assertEqual(p["detected"], {"n": 2, "of": 5, "ratio": 0.4})
        self.assertEqual((p["unresolved"]["n"], p["missed"]["n"]), (2, 1))
        self.assertEqual(p["false_clean_any_dimension"]["n"], 2)
        self.assertEqual(p["false_clean_by_dimension"]["design"], {"n": 0, "of": 4, "ratio": 0.0})
        self.assertEqual(p["false_clean_by_dimension"]["execution"]["n"], 1)
        self.assertEqual((p["choices_missed"]["n"], p["choices_missed"]["of"]), (2, 5))
        self.assertEqual((p["invented_facts"], p["unsourced_assumptions"], p["unknown_evidence_treated_as_known"]), (1, 3, 2))
        self.assertEqual((b["unnecessary_questions"], b["unnecessary_reapprovals"]), (4, 2))
        self.assertEqual((b["useful_completion_defect"]["n"], b["useful_completion_control"]["n"]), (4, 1))
        self.assertEqual(b["control_generic_gaps_only"]["n"], 1)
        self.assertEqual(b["active_review_minutes"], {"total": 65, "records_observed": 6, "records": 7})
        self.assertEqual((b["evidence_coverage"]["n"], b["evidence_coverage"]["of"]), (19, 24))
        self.assertIsNone(b["recovery_fidelity"]["ratio"])

    def test_held_out_totals_and_coverage(self):
        h = self.out["held-out"]
        self.assertEqual(h["protection"]["detected"]["n"], 1)
        self.assertEqual(h["protection"]["missed"]["n"], 1)
        self.assertEqual(h["burden"]["recovery_fidelity"], {"n": 1, "of": 1, "ratio": 1.0})
        self.assertEqual(h["burden"]["unnecessary_reapprovals"], 2)
        self.assertEqual(h["coverage"]["not_adjudicated"], ["ho-s02", "ho-s04", "ho-s05"])

    def test_deterministic(self):
        again = score.aggregate(doc(), SCENARIOS, RUBRIC)
        self.assertEqual(json.dumps(self.out, sort_keys=True), json.dumps(again, sort_keys=True))
        self.assertEqual(run_main([SYNTH, "--json"]), run_main([SYNTH, "--json"]))

    def test_splits_are_separate(self):
        self.assertEqual(sorted(self.out), ["development", "held-out"])
        d = doc()
        d["records"] = [r for r in d["records"] if r["scenario_id"].startswith("dev-")]
        out = score.aggregate(d, SCENARIOS, RUBRIC)
        self.assertEqual(out["held-out"]["coverage"]["records"], 0)
        self.assertEqual(out["held-out"]["protection"]["defect_records"], 0)
        self.assertEqual(out["development"], self.out["development"])  # held-out records never leak into development

    def test_protection_and_burden_reported_together(self):
        for split in self.out.values():
            self.assertIn("protection", split)
            self.assertIn("burden", split)


class Banner(unittest.TestCase):
    def test_synthetic_banner(self):
        code, out = run_main([SYNTH])
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith(score.BANNER))
        self.assertIn("[SYNTHETIC]", out)

    def test_no_banner_when_not_synthetic(self):
        d = doc()
        d["synthetic"] = False
        path = os.path.join(os.environ.get("TMPDIR", "/tmp"), "mx-eval-real-%d.json" % os.getpid())
        with open(path, "w") as handle:
            json.dump(d, handle)
        try:
            code, out = run_main([path])
        finally:
            os.remove(path)
        self.assertEqual(code, 0)
        self.assertNotIn("SYNTHETIC DATA", out)

    def test_example_is_labelled_synthetic(self):
        d = doc()
        self.assertIs(d["synthetic"], True)
        self.assertIn("SYNTHETIC", json.dumps(d["run"]))


class Leakage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys = load("answer_keys.json")["keys"]

    def test_scenario_fields_and_split(self):
        allowed = {"id", "split", "family", "kind", "recovery", "workspace", "prompt"}
        ids = [s["id"] for s in SCENARIOS]
        self.assertEqual(len(ids), len(set(ids)))
        for s in SCENARIOS:
            self.assertEqual(set(s), allowed)
            self.assertIn(s["split"], ("development", "held-out"))
            self.assertIn(s["kind"], ("defect", "control"))
        self.assertEqual(set(ids), set(self.keys))
        for split in ("development", "held-out"):
            fams = set(s["family"] for s in SCENARIOS if s["split"] == split and s["kind"] == "defect")
            self.assertEqual(len(fams), 5, split)

    def test_no_answer_key_text_in_scenarios(self):
        with open(os.path.join(EVAL, "scenarios.json"), encoding="utf-8") as handle:
            text = handle.read().lower()
        for sid, key in self.keys.items():
            for field in ("consequential_choice", "expected_finding", "workspace_variant", "unnecessary_interruptions", "not_detection"):
                self.assertNotIn(key[field].lower(), text, "%s.%s appears in scenarios.json" % (sid, field))
        for s in SCENARIOS:
            prompt = s["prompt"].lower()
            for term in self.keys[s["id"]]["leak_terms"]:
                self.assertNotIn(term.lower(), prompt, "%s prompt contains key term %r" % (s["id"], term))
            for field in ("consequential_choice", "expected_finding"):
                self.assertNotIn(prompt, self.keys[s["id"]][field].lower())
        defects = [k for s in SCENARIOS if s["kind"] == "defect" for k in [self.keys[s["id"]]]]
        self.assertTrue(all(k["leak_terms"] for k in defects))

    def test_prompts_do_not_name_the_defect_cases(self):
        for s in SCENARIOS:
            self.assertIsNone(re.search(r"\b(DC|V|G|S|KB|M)-\d+", s["prompt"]), s["id"])

    def test_fixture_project_has_no_answer_key(self):
        fixture = os.path.join(ROOT, "tests", "fixtures", "mycelium-project")
        self.assertTrue(os.path.isdir(fixture))
        bad = re.compile(r"answer[_-]?key|rubric|adjudicat|scenarios\.json|truth\.json|mx-eval", re.I)
        for base, dirs, files in os.walk(fixture):
            for name in dirs + files:
                self.assertIsNone(bad.search(name), os.path.join(base, name))
            for name in files:
                with open(os.path.join(base, name), "rb") as handle:
                    self.assertNotIn(b"mx-eval-", handle.read(), os.path.join(base, name))

    def test_score_never_reads_answer_keys(self):
        with open(os.path.join(EVAL, "score.py"), encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("answer_keys.json", source.split('"""', 2)[2])


if __name__ == "__main__":
    unittest.main()
