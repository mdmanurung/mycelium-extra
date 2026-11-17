"""Run: python3 skills/verify/tests/test_evidence_allowlist.py

The read-only allowlist for plan evidence and `reproduce` (evidence_command): bypasses that run code or write a
file are refused, a quoted ">" is an argument, and ordinary read-only commands pass.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(PLUGIN, "hooks"))
sys.dont_write_bytecode = True
import gate  # noqa: E402

verify = gate.load_verify()


class Refused(unittest.TestCase):
    def check(self, command):
        ok, why = verify.evidence_command(command)
        self.assertFalse(ok, command)

    def test_git_global_option_value_as_subcommand(self):
        self.check("git --namespace log -c alias.z='!touch pwned' z")
        self.check("git --namespace log clean -fdx")
        self.check("git -C . log --oneline")
        self.check("git --git-dir=.git log")

    def test_sort_bundled_short_flag(self):
        self.check("sort -ro out in")
        self.check("sort -nro out in")
        self.check("sort -oout in")

    def test_sort_long_abbreviation(self):
        self.check("sort --outp=out in")
        self.check("sort --o=out in")
        self.check("sort --compress=sh in")
        self.check("rg --pr=sh x f")

    def test_redirect_glued_to_word(self):
        self.check("cat a.txt >&2x")
        self.check("cat a.txt > out")
        self.check("cat a.txt 2>out")
        self.check("cat a.txt >out")

    def test_brace_expansion_builds_a_writer_flag(self):  # bash turns {--output=o,} into --output=o
        self.check("git log {--output=o2,}")
        self.check("sort {-o,}x in")

    def test_git_pager_flag_bundled_attached_or_abbreviated(self):
        self.check("git grep -Otouch\\ o6 hello")
        self.check("git grep -nO'touch o7' hello")
        self.check("git grep --open-f='touch o8' hello")
        self.check("git log --outp=o")

    def test_rg_hostname_bin_runs_a_program(self):
        self.check("rg --hostname-bin=cmd x")


class Allowed(unittest.TestCase):
    def check(self, command):
        ok, why = verify.evidence_command(command)
        self.assertTrue(ok, "{}: {}".format(command, why))

    def test_ordinary_read_only(self):
        self.check("git log --oneline")
        self.check("git diff --stat HEAD~1")
        self.check("sort -r file")
        self.check("sort -n -k2 file")
        self.check("rg -c x f")
        self.check("cat f | wc -l")

    def test_quoted_redirect_character_is_an_argument(self):
        self.check('grep -c ">" seqs.fa')
        self.check("grep -c '>' seqs.fa")
        self.check('grep -c ">>" seqs.fa')
        self.check('rg ">chr1" seqs.fa')

    def test_a_quoted_brace_is_an_argument(self):  # control for the brace refusal
        self.check("jq '{a: .x}' f.json")
        self.check('grep -c "{" f')
        self.check("git log --oneline -n 5")


if __name__ == "__main__":
    unittest.main()
