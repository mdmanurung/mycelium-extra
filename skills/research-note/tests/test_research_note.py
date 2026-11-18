"""Run: python3.11 skills/research-note/tests/test_research_note.py"""

import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPT = os.path.join(SKILL, "scripts", "check_note.py")
FIXTURES = os.path.join(HERE, "fixtures")


def run(*args):
    done = subprocess.run([sys.executable, SCRIPT] + list(args), capture_output=True, text=True)
    return done.returncode, done.stdout


def fixture(name):
    return os.path.join(FIXTURES, name)


class CheckNote(unittest.TestCase):
    def test_good_note_passes(self):
        code, out = run(fixture("good.md"))
        self.assertEqual(code, 0, out)
        self.assertIn("fits the format", out)

    def test_each_bad_note_fails_with_its_reason(self):
        cases = {
            "bad_empty_cell.md": "empty `quote or value` cell",
            "bad_undefined_source.md": "S9 is not defined",
            "bad_no_pinned.md": "missing `Pinned:` line",
            "bad_uncited.md": "names no reference id",
            "bad_missing_section.md": "missing section `## Not established`",
            "bad_unpinned_reference.md": "reference S1 has no version",
            "bad_long_answer.md": "format allows two",
            "bad_no_log.md": "missing section `## Retrieval log`",
            "bad_id_not_logged.md": "reference S2 cites DOI 10.1016/j.cell.2019.05.031, which is not in the `## Retrieval log`",
            "bad_no_window.md": "has no `Window:` line",
        }
        for name, reason in cases.items():
            with self.subTest(name):
                code, out = run(fixture(name))
                self.assertEqual(code, 1, out)
                self.assertIn(reason, out)

    def test_unsupported_row_needs_low_confidence(self):
        with open(fixture("good.md"), encoding="utf-8") as handle:
            text = handle.read().replace("| none | low |", "| none | high |")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "n.md")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            code, out = run(path)
        self.assertEqual(code, 1)
        self.assertIn("unsupported claim must have confidence low", out)

    def edited(self, old, new):
        with open(fixture("good.md"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn(old, text)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "n.md")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text.replace(old, new))
            return run(path)

    def test_doi_or_bare_number_is_not_a_version(self):
        s1 = "- S1 scanpy 1.10.3 documentation, `scanpy.pp.highly_variable_genes`, https://scanpy.readthedocs.io/en/1.10.3/, read 2026-11-13."
        for line in ("- S1 Fabricated, A. Nothing at all, 10.1234/fake.",
                     "- S1 scanpy docs, https://scanpy.readthedocs.io/en/stable/ 10"):
            code, out = self.edited(s1, line)
            self.assertEqual(code, 1, out)
            self.assertIn("reference S1 has no version", out)
        code, out = self.edited("Pinned: scanpy 1.10.3 (active env, 2026-11-13); Ensembl release 110 (GRCh38)",
                                "Pinned: scanpy latest 2")
        self.assertEqual(code, 1, out)
        self.assertIn("`Pinned:` has no version", out)

    def test_section_order_and_duplicate_ids(self):
        code, out = self.edited("## Question\n\nDoes `sc.pp.highly_variable_genes` with `flavor=\"seurat_v3\"` drop genes with zero counts first?\n\n", "")
        self.assertEqual(code, 1, out)
        code, out = self.edited("- S2 Stuart", "- S1 Stuart")
        self.assertEqual(code, 1, out)
        self.assertIn("reference S1 is already defined", out)
        with open(fixture("good.md"), encoding="utf-8") as handle:
            text = handle.read()
        a, b = text.index("## Question"), text.index("## Answer")
        c = text.index("## Evidence")
        swapped = text[:a] + text[c:text.index("## Not established")] + text[a:c] + text[text.index("## Not established"):]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "n.md")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(swapped)
            code, out = run(path)
        self.assertEqual(code, 1, out)
        self.assertIn("out of order", out)

    def test_missing_file_is_a_failure_not_a_pass(self):
        code, out = run(fixture("no-such-note.md"))
        self.assertEqual(code, 1)
        self.assertIn("cannot read", out)

    def test_log_matches_ids_ignoring_case_and_trailing_punctuation(self):
        code, out = self.edited("kept doi:10.1016/j.cell.2019.05.031", "kept DOI 10.1016/J.CELL.2019.05.031.")
        self.assertEqual(code, 0, out)

    def test_pmid_and_arxiv_must_be_logged(self):
        base = "- S2 Stuart T, Comprehensive integration of single-cell data. Cell 2019. doi:10.1016/j.cell.2019.05.031"
        pm = base + " PMID 31178118 arXiv:1907.12345"
        code, out = self.edited(base, pm)
        self.assertEqual(code, 1, out)
        self.assertIn("cites PMID 31178118", out)
        self.assertIn("cites arXiv 1907.12345", out)
        code, out = self.edited("kept doi:10.1016/j.cell.2019.05.031", "kept doi:10.1016/j.cell.2019.05.031, PMID 31178118, 1907.12345 arXiv:1907.12345")
        self.assertEqual(code, 0, out)
        code, out = self.edited(base, pm.replace("arXiv:1907.12345", ""))
        self.assertEqual(code, 1, out)
        self.assertIn("cites PMID 31178118", out)

    def test_doi_suffix_in_log_is_not_a_pmid(self):
        base = "- S2 Stuart T, Comprehensive integration of single-cell data. Cell 2019. doi:10.1016/j.cell.2019.05.031"
        code, out = self.edited(
            "kept doi:10.1016/j.cell.2019.05.031",
            "kept doi:10.1016/j.cell.2019.05.031, doi:10.1101/2020.01.01.123456",
        )
        self.assertEqual(code, 0, out)
        code, out = self.edited(base, base + " PMID 123456")
        self.assertEqual(code, 1, out)
        self.assertIn("cites PMID 123456", out)

    def test_log_before_references_fails(self):
        with open(fixture("good.md"), encoding="utf-8") as handle:
            text = handle.read()
        a, b = text.index("## References"), text.index("## Retrieval log")
        swapped = text[:a] + text[b:] + "\n" + text[a:b]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "n.md")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(swapped)
            code, out = run(path)
        self.assertEqual(code, 1, out)
        self.assertIn("must come after `## References`", out)

    def test_ids_lists_identifiers(self):
        code, out = run(fixture("good.md"), "--ids")
        self.assertEqual(code, 0)
        self.assertIn("ID S2 doi 10.1016/j.cell.2019.05.031", out)


class SkillFiles(unittest.TestCase):
    def test_frontmatter(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as handle:
            text = handle.read()
        head = text.split("---")[1]
        self.assertIn("name: research-note", head)
        self.assertIn("disable-model-invocation: true", head)
        desc = re.search(r'^description: "?(.*?)"?$', head, re.M).group(1)
        self.assertLessEqual(len(desc.split(". ")[0]), 150)
        self.assertLessEqual(len(desc.split()), 60)
        self.assertLessEqual(len(text.splitlines()), 100)
        self.assertIn("Adapted from Matt Pocock's research skill (MIT)", text)

    def test_openai_yaml_matches_focus(self):
        path = os.path.join(SKILL, "agents", "openai.yaml")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("allow_implicit_invocation: false", text)
        for key in ("display_name", "short_description", "default_prompt"):
            self.assertIn(key + ":", text)

    def test_pointers_exist(self):
        for name in ("agent-brief.md", "note-format.md", "sources.md", "lit-policy.md"):
            self.assertTrue(os.path.isfile(os.path.join(SKILL, "references", name)), name)


if __name__ == "__main__":
    unittest.main()
