"""Tests for hooks/validation.py: the `validation-bindings` and `exact-execution` plan blocks and argv matching."""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import validation  # noqa: E402

ROWS = ["1", "2", "3"]


def check(**changes):
    base = {"id": "V1", "plan_row": "3", "required": True, "defined_by": "researcher-approved",
            "test_paths": ["analysis/x/tests/expect.tsv"], "invocation": ["python", "analysis/x/tests/check.py"],
            "evidence_path": "analysis/x/outputs/check.json"}
    base.update(changes)
    return dict((k, v) for k, v in base.items() if v is not None)


def bindings(*checks, **top):
    body = dict({"version": 1, "checks": list(checks)}, **top)
    return "## Plan\n\n<!-- validation-bindings {} -->\n".format(json.dumps(body))


def step(**changes):
    base = {"row": "2", "argv": ["python", "analysis/x/fit.py", "--seed", "1", "--threads", "4"], "cwd": ".",
            "env": {}, "operational": ["--threads"]}
    base.update(changes)
    return base


def exact(*steps, **top):
    return "<!-- exact-execution {} -->".format(json.dumps(dict({"version": 1, "steps": list(steps)}, **top)))


class BlockTest(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, "analysis/x/tests"))
        with open(os.path.join(self.root, "analysis/x/tests/expect.tsv"), "w") as handle:
            handle.write("gene\trows\nA\t24\n")

    def read(self, text, rows=ROWS):
        return validation.read_bindings(text, rows, self.root)

    def errors(self, text, rows=ROWS):
        value, errors = self.read(text, rows)
        self.assertIsNone(value)
        self.assertTrue(errors)
        return "\n".join(errors)

    def test_no_block_is_no_binding_and_no_error(self):
        self.assertEqual(self.read("## Plan\n| 1 | run |\n"), (None, []))
        self.assertEqual(validation.read_exact("no block", ROWS, self.root), (None, []))

    def test_a_valid_block_is_read_and_its_files_pinned(self):
        value, errors = self.read(bindings(check()))
        self.assertEqual(errors, [])
        one, = value["checks"]
        self.assertEqual((one["id"], one["plan_row"], one["required"], one["defined_by"]),
                         ("V1", "3", True, "researcher-approved"))
        self.assertEqual(one["invocation"], ["python", "analysis/x/tests/check.py"])
        self.assertEqual(list(one["files"]), ["analysis/x/tests/expect.tsv"])
        self.assertEqual(len(one["files"]["analysis/x/tests/expect.tsv"]), 64)
        self.assertEqual(one["definition_sha256"], validation.definition_sha256(one, one["files"]))

    def test_an_invocation_may_be_a_string_and_required_defaults_to_true(self):
        value, errors = self.read(bindings(check(invocation="python analysis/x/tests/check.py", required=None)))
        self.assertEqual(errors, [])
        self.assertEqual(value["checks"][0]["invocation"], ["python", "analysis/x/tests/check.py"])
        self.assertTrue(value["checks"][0]["required"])

    def test_malformed_json_and_shape(self):
        self.assertIn("not valid JSON", self.errors("<!-- validation-bindings {not json} -->"))
        self.assertIn("must be a JSON object", self.errors("<!-- validation-bindings [] -->"))
        self.assertIn("`checks` must be a list", self.errors('<!-- validation-bindings {"version": 1, "checks": {}} -->'))
        self.assertIn("must be an object", self.errors(bindings("V1")))
        self.assertIn("2 blocks", self.errors(bindings(check()) + bindings(check())))

    def test_unsupported_version(self):
        for version in (2, 0, "1", None, True):
            text = bindings(check()).replace('"version": 1', '"version": {}'.format(json.dumps(version)))
            self.assertIn("unsupported version", self.errors(text), version)

    def test_unknown_keys_are_errors(self):
        self.assertIn("unknown key `owner`", self.errors(bindings(check(owner="me"))))
        self.assertIn("unknown key `extra`", self.errors(bindings(check(), extra=1)))

    def test_missing_fields_are_errors(self):
        for key in ("id", "plan_row", "defined_by", "test_paths", "invocation", "evidence_path"):
            self.assertIn("missing `{}`".format(key), self.errors(bindings(check(**{key: None}))), key)

    def test_duplicate_check_ids(self):
        self.assertIn("duplicate check id", self.errors(bindings(check(), check(plan_row="2"))))

    def test_unknown_or_ambiguous_plan_row(self):
        self.assertIn("unknown plan row 9", self.errors(bindings(check(plan_row="9"))))
        self.assertIn("the plan has no step table", self.errors(bindings(check()), rows=[]))
        self.assertIn("ambiguous", self.errors(bindings(check()), rows=["1", "3", "3"]))
        value, errors = self.read(bindings(check(plan_row=3)))  # a number is the same row
        self.assertEqual((errors, value["checks"][0]["plan_row"]), ([], "3"))

    def test_defined_by_must_be_one_of_the_three(self):
        self.assertIn("`defined_by` must be one of", self.errors(bindings(check(defined_by="the model"))))
        for kind in validation.DEFINED_BY:
            self.assertEqual(self.read(bindings(check(defined_by=kind)))[1], [])

    def test_missing_test_file_is_an_error_but_a_missing_evidence_file_is_not(self):
        self.assertIn("cannot be pinned", self.errors(bindings(check(test_paths=["analysis/x/tests/nope.tsv"]))))
        self.assertIn("cannot be pinned", self.errors(bindings(check(test_paths=["analysis/x/tests"]))))  # a folder
        self.assertEqual(self.read(bindings(check(evidence_path="analysis/x/outputs/not-yet.json")))[1], [])

    def test_unsafe_paths(self):
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside)
        with open(os.path.join(outside, "e.tsv"), "w") as handle:
            handle.write("x")
        os.symlink(outside, os.path.join(self.root, "escape"))
        for path in ("/etc/passwd", os.path.join(outside, "e.tsv"), "../elsewhere/e.tsv", "analysis/../../e.tsv",
                     "escape/e.tsv", "~/e.tsv", "$HOME/e.tsv", ".mycelium-extra/gate.json", ""):
            self.assertTrue(self.errors(bindings(check(test_paths=[path]))), path)
            self.assertTrue(self.errors(bindings(check(evidence_path=path))), path)

    def test_an_absolute_path_inside_the_repository_is_made_relative(self):
        absolute = os.path.join(self.root, "analysis/x/tests/expect.tsv")
        value, errors = self.read(bindings(check(test_paths=[absolute, "analysis/x/../x/tests/expect.tsv"])))
        self.assertEqual(errors, [])
        self.assertEqual(value["checks"][0]["test_paths"], ["analysis/x/tests/expect.tsv"] * 2)

    def test_the_definition_changes_with_the_expectation_and_not_with_unrelated_files(self):
        first = self.read(bindings(check()))[0]["checks"][0]
        with open(os.path.join(self.root, "analysis/x/other.py"), "w") as handle:
            handle.write("unrelated edit\n")
        self.assertEqual(self.read(bindings(check()))[0]["checks"][0]["definition_sha256"], first["definition_sha256"])
        with open(os.path.join(self.root, "analysis/x/tests/expect.tsv"), "w") as handle:
            handle.write("gene\trows\nA\t7\n")
        second = self.read(bindings(check()))[0]["checks"][0]
        self.assertNotEqual(second["definition_sha256"], first["definition_sha256"])
        self.assertNotEqual(validation.definition_sha256(check(id="V2"), first["files"]), first["definition_sha256"])

    def test_changes_lists_a_changed_or_missing_pinned_file_only(self):
        value = self.read(bindings(check()))[0]
        self.assertEqual(validation.changes(self.root, value), [])
        path = os.path.join(self.root, "analysis/x/tests/expect.tsv")
        with open(path, "a") as handle:
            handle.write("B\t1\n")
        self.assertEqual(validation.changes(self.root, value), [("V1", "analysis/x/tests/expect.tsv", "changed")])
        os.remove(path)
        self.assertEqual(validation.changes(self.root, value), [("V1", "analysis/x/tests/expect.tsv", "missing")])
        self.assertEqual(validation.changes(self.root, None), [])

    # exact-execution blocks

    def exact(self, *steps, **top):
        return validation.read_exact(exact(*steps, **top), ROWS, self.root)

    def test_a_valid_exact_block(self):
        value, errors = self.exact(step())
        self.assertEqual(errors, [])
        self.assertEqual(value["steps"][0]["argv"][:2], ["python", "analysis/x/fit.py"])
        self.assertEqual((value["steps"][0]["cwd"], value["steps"][0]["operational"]), (".", ["--threads"]))
        value, errors = self.exact({"row": 1, "argv": ["Rscript", "analysis/x/fit.R"]})  # defaults
        self.assertEqual((errors, value["steps"][0]["cwd"], value["steps"][0]["env"]), ([], ".", {}))

    def test_exact_block_errors(self):
        def bad(expected, *steps, **top):
            value, errors = self.exact(*steps, **top)
            self.assertIsNone(value)
            self.assertIn(expected, "\n".join(errors))
        bad("unsupported version", step(), version=2)
        bad("unknown key `extra`", step(), extra=1)
        bad("unknown key `shell`", step(shell="bash"))
        bad("unknown plan row 7", step(row="7"))
        bad("missing `argv`", {"row": "2"})
        bad("non-empty list", step(argv=[]))
        bad("non-empty list", step(argv="python x.py"))
        bad("substitution", step(argv=["python", "x.py", "$SEED"]))
        bad("substitution", step(argv=["python", "`date`"]))
        bad("start with the program", step(argv=["--seed", "1"]))
        bad("leaves the repository", step(cwd="../elsewhere"))
        bad("leaves the repository", step(cwd="/tmp"))
        bad("`operational` must list flag names", step(operational=["threads"]))
        bad("`operational` must list flag names", step(operational=["--threads=4"]))
        bad("`env` must map", step(env={"SEED": 1}))
        bad("`env` must map", step(env={"SEED": "$X"}))
        bad("`env` must map", step(env={"bad name": "1"}))

    def test_exact_cwd_is_normalised(self):
        for cwd, want in ((".", "."), ("./", "."), ("analysis/x", "analysis/x"), ("analysis/../analysis/x", "analysis/x"),
                          (os.path.join(self.root, "analysis"), "analysis")):
            value, errors = self.exact(step(cwd=cwd))
            self.assertEqual((errors, value["steps"][0]["cwd"]), ([], want), cwd)


class ArgvTest(unittest.TestCase):
    declared = ["python", "analysis/x/fit.py", "--model", "original", "--threads", "4"]

    def match(self, actual, **kw):
        kw.setdefault("operational", ["--threads"])
        return validation.argv_matches(self.declared, actual, **kw)

    def test_the_same_command_matches(self):
        self.assertEqual(self.match(list(self.declared)), (True, ""))
        self.assertTrue(self.match(["python", "./analysis/x/fit.py", "--model", "original", "--threads", "4"])[0])
        self.assertTrue(self.match(["/usr/bin/python", "analysis/x/fit.py", "--model", "original",
                                    "--threads", "4"])[0])

    def test_a_changed_analytical_argument_is_a_mismatch(self):
        for actual in (["python", "analysis/x/fit.py", "--model", "alternative", "--threads", "4"],
                       ["python", "analysis/x/fit.py", "--model", "original", "--threads", "4", "--alpha", "0.1"],
                       ["python", "analysis/x/fit.py", "--threads", "4"],
                       ["python", "analysis/x/other.py", "--model", "original", "--threads", "4"],
                       ["python3", "analysis/x/fit.py", "--model", "original", "--threads", "4"]):
            ok, reason = self.match(actual)
            self.assertFalse(ok, actual)
            self.assertTrue(reason)

    def test_an_operational_flag_may_differ_move_vanish_or_be_added(self):
        for actual in (["python", "analysis/x/fit.py", "--model", "original", "--threads", "16"],
                       ["python", "analysis/x/fit.py", "--threads", "1", "--model", "original"],
                       ["python", "analysis/x/fit.py", "--model", "original"],
                       ["python", "analysis/x/fit.py", "--model", "original", "--threads=8"]):
            self.assertTrue(self.match(actual)[0], actual)

    def test_a_flag_that_is_not_operational_may_not_differ(self):
        self.assertFalse(self.match(["python", "analysis/x/fit.py", "--model", "original", "--threads", "4"],
                                    operational=[], cwd="analysis")[0])
        self.assertFalse(self.match(["python", "analysis/x/fit.py", "--model", "original", "--threads", "8"],
                                    operational=[])[0])

    def test_a_boolean_operational_flag_cannot_swallow_a_positional(self):
        declared = ["python", "a.py", "in.tsv"]
        for actual in (["python", "a.py", "--verbose", "extra.tsv", "in.tsv"],
                       ["python", "a.py", "--verbose", "in.tsv", "extra.tsv"]):
            self.assertFalse(validation.argv_matches(declared, actual, operational=["--verbose"])[0], actual)
        self.assertTrue(validation.argv_matches(declared, ["python", "a.py", "--verbose", "in.tsv"],
                                                operational=["--verbose"])[0])
        self.assertTrue(validation.argv_matches(declared, ["python", "a.py", "--jobs=8", "in.tsv"],
                                                operational=["--jobs"])[0])

    def test_the_folder_must_be_the_declared_one(self):
        ok, reason = self.match(list(self.declared), cwd="analysis")
        self.assertFalse(ok)
        self.assertIn("folder differs", reason)
        self.assertTrue(self.match(list(self.declared), cwd="analysis/x", declared_cwd="analysis/x/")[0])

    def test_a_shell_substitution_never_matches(self):
        ok, reason = self.match(["python", "analysis/x/fit.py", "--model", "$(cat m.txt)"])
        self.assertFalse(ok)
        self.assertIn("substitution", reason)
        self.assertFalse(validation.argv_matches(["python", "a.py", "$X"], ["python", "a.py", "$X"])[0])

    def test_output_redirection_is_ignored_and_input_redirection_is_not(self):
        base = list(self.declared)
        self.assertTrue(self.match(base + [">", "log.txt"])[0])
        self.assertTrue(self.match(base + [">>", "log.txt", "2", ">&1"])[0])
        self.assertTrue(self.match(base + ["2", ">&1"])[0])
        self.assertTrue(self.match(base + ["1", ">", "out.txt"])[0])
        self.assertFalse(self.match(base + ["<", "other.tsv"])[0])
        self.assertTrue(validation.argv_matches(["python", "a.py", "2"], ["python", "a.py", "2"])[0])  # a real 2

    def test_inline_environment_must_be_declared(self):
        self.assertTrue(self.match(list(self.declared), env={"SEED": "1"}, actual_env={"SEED": "1"})[0])
        self.assertTrue(self.match(list(self.declared), env={"SEED": "1"})[0])  # not inline: not visible here
        for env in ({"SEED": "2"}, {"OTHER": "1"}):
            ok, reason = self.match(list(self.declared), env={"SEED": "1"}, actual_env=env)
            self.assertFalse(ok)
            self.assertIn("inline variable", reason)


if __name__ == "__main__":
    unittest.main()
