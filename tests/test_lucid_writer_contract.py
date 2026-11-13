"""Pin what lucid-writer reads from mycelium-extra.

lucid-writer reads Extra's files by name and by column. A rename here breaks
it without a failing test on either side, so this test pins the names.
The parts that read lucid-writer's own text skip when it is not installed;
set LUCID_WRITER to a checkout or cache directory to point at another copy.

Run: python3 tests/test_lucid_writer_contract.py
"""
import glob
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "skills/verify/scripts/verify.py"
AUDIT = ROOT / "skills/manuscript-audit/scripts/manuscript_audit.py"


def find_lucid_writer():
    """The installed lucid-writer directory, or None."""
    env = os.environ.get("LUCID_WRITER")
    if env:
        ready = (Path(env) / "skills/lucid-writer/SKILL.md").is_file() and (
            Path(env) / "agents/lucid-manuscript-preflight.md").is_file()
        return Path(env) if ready else None
    cache = os.path.expanduser("~/.claude/plugins/cache/lucid-writer/lucid-writer/*/skills/lucid-writer/SKILL.md")
    # By version number, so 1.10.0 sorts after 1.4.0; a copy without the files the test reads is skipped.
    found = sorted(glob.glob(cache), key=lambda p: [int(n) for n in re.findall(r"\d+", Path(p).parents[2].name)])
    found = [p for p in found if (Path(p).parents[2] / "agents/lucid-manuscript-preflight.md").is_file()]
    return Path(found[-1]).parents[2] if found else None


WRITER = find_lucid_writer()


def load_audit():
    spec = importlib.util.spec_from_file_location("manuscript_audit_contract", str(AUDIT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VERIFY_TESTS = ROOT / "skills/verify/tests"
sys.path[:0] = [str(VERIFY_TESTS), str(ROOT / "hooks")]
import test_verify  # noqa: E402


class Harness(test_verify.VerifyTest):
    """The verify harness (approve, run, write), without re-running its own tests."""


for _name in [name for name in dir(Harness) if name.startswith("test_")]:
    setattr(Harness, _name, None)  # inherited tests belong to test_verify.py


class ExtraSideContract(Harness):
    """What Extra writes, seen by running verify on a small fixture. No lucid-writer needed."""

    def written(self):
        self.write("analysis/a/README.md", "# A\n")
        digest = self.approve(test_verify.plan("run `{}`".format(test_verify.FIT)))
        self.run_cmd("python " + test_verify.FIT)
        self.verify("write", digest, "--analysis-dir", "analysis/a")
        return digest, os.path.join(self.root, "analysis", "a", "provenance")

    def test_write_leaves_the_files_lucid_writer_reads(self):
        digest, folder = self.written()
        names = set(os.listdir(folder))
        for name in ("verify-{}.md", "outputs-{}.tsv"):
            self.assertIn(name.format(digest), names)
        self.assertIn("PROVENANCE.md", names)
        with open(os.path.join(folder, "outputs-{}.tsv".format(digest)), encoding="utf-8") as handle:
            header = handle.readline().rstrip("\n").split("\t")
        self.assertEqual(header[:4], ["path", "written", "size", "sha256"])
        for column in ("written_by", "evidence_method", "strength"):
            self.assertIn(column, header)
        with open(os.path.join(folder, "PROVENANCE.md"), encoding="utf-8") as handle:
            index = handle.read()
        self.assertIn("| Plan | Approved | Verified | Status | Files |", index)
        self.assertRegex(index, r"\| %s \|" % digest)

    def test_numbers_json_keys_read_from_values_computed_at(self):
        digest, _ = self.written()
        self.write("analysis/a/outputs/numbers.json", json.dumps({"namespace": "a", "values": [
            {"key": "n_gone", "value": 1, "computed_at": "code/99_gone.R:L3"}]}))
        self.assertIn("n_gone", self.verify("report", digest))

    def test_skill_documents_the_names_and_flags(self):
        skill = (ROOT / "skills/verify/SKILL.md").read_text(encoding="utf-8")
        for text in ("`verify-<hash>.md`", "`PROVENANCE.md`", "`value | file column [row]`", "<!-- claims",
                     "--claims", "--resolve-citations", "--contact"):
            self.assertIn(text, skill)
        result = subprocess.run([sys.executable, str(VERIFY), "--help"], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        for flag in ("--claims", "--resolve-citations", "--contact"):
            self.assertIn(flag, result.stdout)


class ManuscriptAuditStatus(unittest.TestCase):
    """The top-level status lucid-writer maps: block to Blocker, gap to cannot verify."""

    def run_audit(self, mutate):
        audit = load_audit()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for d in ("outputs", "data"):
                (root / d).mkdir()
            (root / "data/README.md").write_text("Synthetic.\n")
            (root / "outputs/freq.tsv").write_text("sample_id\tfraction\nS1\t0.25\n")
            config = {"schema": audit.SCHEMA, "data_manifest": "data/README.md",
                      "tables": [{"id": "freq", "file": "outputs/freq.tsv", "key_columns": ["sample_id"],
                                  "finite_numeric_columns": ["fraction"]}]}
            mutate(root, config)
            (root / "checks.json").write_text(json.dumps(config))
            return audit.evaluate(root, "checks.json")

    def test_pass(self):
        result = self.run_audit(lambda root, config: None)
        self.assertEqual((result["status"], result["exit_code"]), ("pass", 0))
        self.assertIsInstance(result["checks"], list)
        for check in result["checks"]:
            self.assertIn(check["status"], ("pass", "gap", "block"))

    def test_gap_when_input_missing(self):
        result = self.run_audit(lambda root, config: (root / "data/README.md").unlink())
        self.assertEqual((result["status"], result["exit_code"]), ("gap", 3))

    def test_block_when_declared_column_missing(self):
        result = self.run_audit(lambda root, config: config["tables"][0].update(required_columns=["absent"]))
        self.assertEqual((result["status"], result["exit_code"]), ("block", 2))


@unittest.skipUnless(WRITER, "lucid-writer is not installed; set LUCID_WRITER to test its side")
class LucidWriterSide(unittest.TestCase):
    """lucid-writer's own text still names what Extra writes."""

    @classmethod
    def setUpClass(cls):
        cls.skill = (WRITER / "skills/lucid-writer/SKILL.md").read_text(encoding="utf-8")
        cls.agent = (WRITER / "agents/lucid-manuscript-preflight.md").read_text(encoding="utf-8")
        cls.both = cls.skill + cls.agent

    def test_names_extra_files(self):
        for name in ("verify-<hash>.md", "outputs-<hash>.tsv", "PROVENANCE.md", "numbers.json"):
            self.assertIn(name, self.both)

    def test_names_extra_flags_that_exist(self):
        for flag in ("--claims", "--resolve-citations"):
            self.assertIn(flag, self.skill)
            self.assertIn(flag, (ROOT / "skills/verify/SKILL.md").read_text(encoding="utf-8"))

    def test_maps_audit_status_words(self):
        for word in ("block", "gap"):
            self.assertIn(word, self.agent)
        self.assertIn("manuscript-audit", self.both)


if __name__ == "__main__":
    unittest.main()
