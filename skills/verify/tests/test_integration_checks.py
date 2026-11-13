"""Run: python3 skills/verify/tests/test_integration_checks.py

The info-only lines verify prints for the sibling plugins (0.28): lucid-coder learned rules (L4), the
formatter count (L6), causal wording (W2), a leftover numbers.json key (M5) and a decision that
.living/decisions.md lacks (M7). Each is called directly, so no approved plan is needed.
"""

import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(PLUGIN, "hooks"))
sys.dont_write_bytecode = True
import gate  # noqa: E402

verify = gate.load_verify()


def write(path, text, mode=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(text)
    if mode:
        os.chmod(path, mode)


def infos(report):
    return [text for level, text in report.findings if level == "info"]


class Tmp(unittest.TestCase):
    def setUp(self):
        self.dir = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)


class CausalWording(unittest.TestCase):
    def test_compounds_and_nouns_are_not_claims(self):
        for text in ("Uses a data-driven approach to find markers", "Cell-cycle-driven genes were removed",
                     "The causes of the shift were unclear", "Several drives of the signal"):
            self.assertEqual(verify.causal_words(text), [], text)
        self.assertEqual(verify.causal_words("Loss of X causes the shift"), ["causes"])

    def test_fires_on_each_listed_verb(self):
        for verb in verify.CAUSAL_VERBS:
            self.assertEqual(verify.causal_words("Drug X {} IL6 in monocytes [agent-derived: `a.tsv`]".format(verb)), [verb])

    def test_case_and_several_verbs_once_each_in_order(self):
        self.assertEqual(verify.causal_words("Loss Mediates the effect and protects; it also protects"),
                         ["mediates", "protects"])

    def test_association_wording_never_fires(self):
        for text in ("IL6 is associated with drug X [agent-derived: `a.tsv`]",
                     "IL6 rises after drug X in 5 of 6 donors, which is consistent with a drug effect",
                     "Higher IL6 was accompanied by lower CD3E",
                     "The model does not prove a cause",
                     "Drug X drive and cause are not on the list"):
            self.assertEqual(verify.causal_words(text), [], text)

    def test_quotes_code_links_and_the_tag_are_not_read(self):
        self.assertEqual(verify.causal_words('The paper says "X drives Y" but we only saw a rise'), [])
        self.assertEqual(verify.causal_words("The column `causes` holds counts"), [])
        self.assertEqual(verify.causal_words("A rise ([figure](outputs/drives.png), panel B)"), [])
        self.assertEqual(verify.causal_words("A rise [agent-derived: `outputs/drives.tsv`]"), [])
        self.assertEqual(verify.causal_words("A rise [agent-asserted: Smith says it regulates Y]"), [])
        self.assertEqual(verify.causal_words("The “drives” label is ours"), [])
        self.assertEqual(verify.causal_words("It drives Y, not \"drives\" in quotes"), ["drives"])

    def test_fact_tags_adds_one_info_line_per_bullet(self):
        report = verify.Report()
        items = [(5, "IL6 rises [agent-derived: `a.tsv`]"),
                 (6, "Drug X drives IL6 [agent-derived: `a.tsv`]"),
                 (7, "Loss protects and mediates risk [human-stated]"),
                 (8, "IL6 is associated with drug X [agent-derived: `a.tsv`]")]
        verify.fact_tags("the plan's Evidence", items, report)
        lines = infos(report)
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("Fact tags in the plan's Evidence"))
        self.assertIn("L6 uses `drives`", lines[1])
        self.assertIn("L7 uses `protects`, `mediates`", lines[2])
        self.assertEqual([level for level, _ in report.findings], ["info"] * 3)

    def test_untagged_facts_still_get_the_wording_line(self):
        report = verify.Report()
        verify.fact_tags("Key Findings", [(3, "X causes Y"), (4, "Z is up")], report)
        lines = infos(report)
        self.assertEqual(len(lines), 2)
        self.assertIn("none tagged", lines[0])
        self.assertIn("L3 uses `causes`", lines[1])

    def test_lines_are_capped(self):
        report = verify.Report()
        verify.fact_tags("Key Findings", [(i, "X drives Y{} [human-stated]".format(i)) for i in range(12)], report)
        lines = infos(report)
        self.assertEqual(len(lines), 1 + verify.WORDING_MAX + 1)
        self.assertIn("4 more bullet(s)", lines[-1])


class Formatter(Tmp):
    def setUp(self):
        super().setUp()
        self.bin = os.path.join(self.dir, "bin")
        self.folder = os.path.join(self.dir, "analysis", "a")
        os.makedirs(self.folder)
        self.exec = stat.S_IRWXU

    def fake(self, name, body):
        write(os.path.join(self.bin, name), "#!/bin/sh\n" + body, self.exec)

    def run_check(self, timeout=10):
        report = verify.Report()
        verify.formatter_lines(self.dir, "analysis/a", report, timeout=timeout, path=self.bin)
        self.assertEqual({level for level, _ in report.findings} - {"info"}, set())
        return infos(report)

    def test_air_count(self):
        write(os.path.join(self.folder, "air.toml"), "")
        self.fake("air", 'echo "Would reformat: a.R"; echo "Would reformat: b.R"; exit 1\n')
        self.assertEqual(self.run_check(), ["formatter: 2 files would change (air)"])

    def test_ruff_count_from_summary_and_zero(self):
        write(os.path.join(self.dir, "ruff.toml"), "")  # at the repository root
        self.fake("ruff", 'echo "1 file would be reformatted, 3 files already formatted"; exit 1\n')
        self.assertEqual(self.run_check(), ["formatter: 1 files would change (ruff)"])
        self.fake("ruff", 'echo "4 files already formatted"; exit 0\n')
        self.assertEqual(self.run_check(), ["formatter: 0 files would change (ruff)"])

    def test_nothing_without_config_or_tool(self):
        self.fake("air", 'echo "Would reformat: a.R"; exit 1\n')
        self.assertEqual(self.run_check(), [])  # tool, no config
        write(os.path.join(self.folder, "air.toml"), "")
        shutil.rmtree(self.bin)
        self.assertEqual(self.run_check(), [])  # config, no tool

    def test_a_tool_error_or_timeout_prints_nothing(self):
        write(os.path.join(self.folder, "air.toml"), "")
        self.fake("air", 'echo boom >&2; exit 2\n')
        self.assertEqual(self.run_check(), [])
        self.fake("air", "sleep 5\n")
        self.assertEqual(self.run_check(timeout=0.5), [])


class LearnedRules(Tmp):
    RULES = [
        {"id": "r-0002", "topic": "user.report_embedded_figures", "scope": {"kind": "global"}, "status": "active"},
        {"id": "r-0017", "topic": "fig.theme", "scope": {"kind": "language", "language": "r"}, "status": "active"},
        {"id": "r-0020", "topic": "py.thing", "scope": {"kind": "language", "language": "python"}, "status": "active"},
        {"id": "r-0021", "topic": "repo.thing", "scope": {"kind": "repo", "repo": "x/y"}, "status": "active"},
        {"id": "r-0022", "topic": "glob.thing", "scope": {"kind": "file-glob", "glob": "*.qmd"}, "status": "active"},
    ]

    def plugin(self, body=None):
        root = os.path.join(self.dir, "lucid-coder")
        body = body or ("if (process.argv.slice(2).join(' ') !== 'list --status active --json') process.exit(1);\n"
                        "console.log(JSON.stringify({}));\n".format(json.dumps(self.RULES)))
        write(os.path.join(root, "scripts", "rules.js"), body)
        return root

    def line(self, files, root):
        report = verify.Report()
        with mock.patch.dict(os.environ, {"MX_LUCID_CODER_ROOT": root}):
            verify.learned_rules_line(self.dir, files, report)
        self.assertEqual({level for level, _ in report.findings} - {"info"}, set())
        return infos(report)

    def setUp(self):
        super().setUp()
        if not shutil.which("node"):
            self.skipTest("node is not installed")

    def test_lists_the_rules_that_apply(self):
        (line,) = self.line(["code/01_a.R", "reports/a.qmd"], self.plugin())
        self.assertIn("(3)", line)
        for rid in ("r-0002 user.report_embedded_figures", "r-0017 fig.theme", "r-0022 glob.thing"):
            self.assertIn(rid, line)
        for rid in ("r-0020", "r-0021"):
            self.assertNotIn(rid, line)
        self.assertIn("not enforced", line)

    def test_python_files_pick_the_python_rule(self):
        (line,) = self.line(["code/01_a.py"], self.plugin())
        self.assertIn("r-0020 py.thing", line)
        self.assertNotIn("r-0017", line)

    def test_fails_open(self):
        self.assertEqual(self.line(["a.R"], os.path.join(self.dir, "missing")), [])
        self.assertEqual(self.line(["a.R"], self.plugin("process.exit(1);\n")), [])
        self.assertEqual(self.line(["a.R"], self.plugin("console.log('not json');\n")), [])
        self.assertEqual(self.line(["a.R"], self.plugin("console.log('{\"a\": 1}');\n")), [])
        self.assertEqual(self.line(["a.R"], self.plugin("setTimeout(() => {}, 1000);\n process.exit(3);\n")), [])

    def test_no_node_is_not_a_finding(self):
        report = verify.Report()
        with mock.patch.dict(os.environ, {"MX_LUCID_CODER_ROOT": self.plugin()}), \
                mock.patch.object(verify.shutil, "which", return_value=None):
            verify.learned_rules_line(self.dir, ["a.R"], report)
        self.assertEqual(report.findings, [])

    def test_root_comes_from_installed_plugins(self):
        home = os.path.join(self.dir, "home")
        root = self.plugin()
        write(os.path.join(home, ".claude", "plugins", "installed_plugins.json"), json.dumps({"version": 2, "plugins": {
            "lucid-coder@lucid-coder": [{"scope": "project", "installPath": os.path.join(self.dir, "nope")},
                                        {"scope": "user", "installPath": root}]}}))
        with mock.patch.dict(os.environ, {"HOME": home}):
            os.environ.pop("MX_LUCID_CODER_ROOT", None)
            self.assertEqual(verify.lucid_coder_root(), root)


class NumbersLeftovers(Tmp):
    def setUp(self):
        super().setUp()
        self.folder = os.path.join(self.dir, "analysis", "a")
        write(os.path.join(self.folder, "code", "02_de.R"), "1\n")
        self.path = os.path.join(self.folder, "outputs", "numbers.json")

    def lines(self):
        report = verify.Report()
        verify.numbers_leftovers(self.dir, "analysis/a", report)
        return infos(report)

    def test_names_a_key_whose_script_is_gone_and_leaves_the_file_alone(self):
        text = json.dumps({"namespace": "a", "values": [
            {"key": "n_old", "value": 3, "computed_at": "code/01_gone.R:L12"},
            {"key": "n_kept", "value": 4, "computed_at": "code/02_de.R:L7"},
            {"key": "n_bare", "value": 5},
            {"key": "n_py", "value": 6, "computed_at": "scripts/old.py:L3"}]})
        write(self.path, text)
        (line,) = self.lines()
        self.assertIn("2 key(s)", line)
        self.assertIn("n_old (code/01_gone.R)", line)
        self.assertIn("n_py (scripts/old.py)", line)
        self.assertNotIn("n_kept", line)
        self.assertNotIn("n_bare", line)
        with open(self.path) as handle:
            self.assertEqual(handle.read(), text)

    def test_line_ranges_and_non_file_sites_are_not_leftovers(self):
        write(self.path, json.dumps({"values": [
            {"key": "a", "computed_at": "code/02_de.R:L10-L20"}, {"key": "b", "computed_at": "code/02_de.R:3-9"},
            {"key": "c", "computed_at": "<stdin>:L3"}, {"key": "d", "computed_at": "/tmp/ipykernel_1/55.py:L2"}]}))
        self.assertEqual(self.lines(), [])

    def test_nothing_when_every_script_exists_or_the_file_is_odd(self):
        write(self.path, json.dumps({"values": [{"key": "k", "computed_at": "code/02_de.R:L7"}]}))
        self.assertEqual(self.lines(), [])
        write(self.path, json.dumps({"qc": {"n": 48}}))
        self.assertEqual(self.lines(), [])
        write(self.path, "[1, 2")
        self.assertEqual(self.lines(), [])
        os.remove(self.path)
        self.assertEqual(self.lines(), [])


class DecisionsRecorded(Tmp):
    PLAN = ("# Plan\n\n## Decisions to record\n\n- Pairing by donor, not by visit [agent-asserted: none]\n"
            "- FDR family is the 2 contrasts\n\n## Next\n")

    def lines(self, decisions, plan=None, digest="abcdef0123456789"):
        if decisions is not None:
            write(os.path.join(self.dir, ".living", "decisions.md"), decisions)
        report = verify.Report()
        verify.decisions_recorded(self.dir, plan or self.PLAN, digest, report)
        self.assertEqual({level for level, _ in report.findings} - {"info"}, set())
        return infos(report)

    def test_absent_bullets_are_named(self):
        (line,) = self.lines("# Decisions\n\n- Pairing by donor, not by visit (D-12)\n")
        self.assertIn("1 of 2 bullet(s)", line)
        self.assertIn("abcdef01", line)
        self.assertIn(".living/decisions.md", line)

    def test_nothing_when_every_bullet_is_there(self):
        self.assertEqual(self.lines("- Pairing by donor, not by visit\n- **FDR family** is the 2 contrasts\n"), [])

    def test_the_plan_hash_covers_the_bullets(self):
        self.assertEqual(self.lines("Plan abcdef01 settled these.\n"), [])

    def test_no_file_no_bullets_no_line(self):
        self.assertEqual(self.lines(None), [])
        write(os.path.join(self.dir, ".living", "decisions.md"), "x\n")
        self.assertEqual(self.lines(None, plan="# Plan\n\n## Next\n"), [])
        self.assertEqual(self.lines(None, plan="# Plan\n\n## Decisions to record\n\n- none\n"), [])

    def test_a_huge_file_is_read_by_its_last_two_megabytes(self):
        big = "- Pairing by donor, not by visit\n" + "x" * (3 * 1024 * 1024) + "\n- FDR family is the 2 contrasts\n"
        (line,) = self.lines(big)
        self.assertIn("1 of 2 bullet(s)", line)  # the early bullet fell outside the tail
        self.assertEqual(self.lines("- Pairing by donor, not by visit\n" + "x" * 100 + "\n"
                                    "- FDR family is the 2 contrasts\n"), [])


if __name__ == "__main__":
    unittest.main()
