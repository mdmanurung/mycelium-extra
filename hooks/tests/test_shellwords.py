"""Run: python3 hooks/tests/test_shellwords.py

hooks/shellwords.py: the shell tokenizer, folder moves and word tables the gate reads commands with.
Every name must also stay reachable as `gate.<name>`, the same object."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.dont_write_bytecode = True
import gate  # noqa: E402
import shellwords as sw  # noqa: E402

CONFIG = {"gated_paths": ["analysis/**"], "gated_commands": ["sbatch", "snakemake", "nextflow"]}


class Tokenize(unittest.TestCase):
    def test_quotes_and_operators(self):
        self.assertEqual(sw.tokenize("python 'a b.py' && echo \"x y\" | cat"),
                         ["python", "a b.py", "&&", "echo", "x y", "|", "cat"])

    def test_substitution_stays_in_one_word(self):
        self.assertEqual(sw.tokenize("x=$(ls a | head -1) python y.py"), ["x=$(ls a | head -1)", "python", "y.py"])

    def test_heredoc_body_is_not_a_token(self):
        bodies = []
        tokens = sw.tokenize("cat <<EOF\npython hidden.py\nEOF\necho done", bodies)
        self.assertEqual(tokens, ["cat", "<<", "EOF", ";", "echo", "done"])
        self.assertNotIn("hidden.py", tokens)
        self.assertEqual(bodies, ["python hidden.py"])

    def test_line_continuation_joins_lines(self):
        self.assertEqual(sw.tokenize("python \\\n x.py"), ["python", "x.py"])

    def test_ansi_c_quote(self):
        self.assertEqual(sw.tokenize("cat $'a\\tb'"), ["cat", "a\tb"])
        self.assertEqual(sw.ansi_literal("\\x41"), "A")
        self.assertEqual(sw.ansi_literal("\\x80"), "$<unresolved-ansi-c>")

    def test_segments_split_on_separators(self):
        self.assertEqual(list(sw.segments("a b; c | d && (e)")), [["a", "b"], ["c"], ["d"], ["e"]])

    def test_scoped_segments_keep_parentheses(self):
        found = [(tokens, opened, closed) for tokens, opened, closed, _, _ in sw.scoped_segments("(cd D); cmd")]
        self.assertEqual(found, [(["cd", "D"], 1, 0), (["cmd"], 0, 1)])

    def test_words_and_separators(self):
        self.assertTrue(sw.is_separator("&&"))
        self.assertFalse(sw.is_separator(">"))
        self.assertTrue(sw.is_assignment("A=1"))
        self.assertFalse(sw.is_assignment("=1"))
        self.assertEqual(sw.substitutions("a$(b c)d`e`"), ["b c", "e"])
        self.assertTrue(sw.reads_code(["/bin/bash", "-s"]))
        self.assertFalse(sw.reads_code(["python3", "-"]))


class Folders(unittest.TestCase):
    def test_split_option_forms(self):
        flags = ("-C", "--chdir")
        self.assertEqual(sw.split_option("-C", flags), ("-C", None))
        self.assertEqual(sw.split_option("-Cdir", flags), ("-C", "dir"))
        self.assertEqual(sw.split_option("--chdir=dir", flags), ("--chdir", "dir"))
        self.assertEqual(sw.split_option("--other=dir", flags), (None, None))

    def test_move_folder_resolves_pwd_and_flags_unknowns(self):
        self.assertEqual(sw.move_folder("/r", "a/b"), "/r/a/b")
        self.assertEqual(sw.move_folder("/r", "$PWD/a"), "/r/a")
        moved = sw.move_folder("/r", "$X/a")
        self.assertIsInstance(moved, sw.UnknownFolder)
        self.assertEqual((str(moved), moved.raw), ("/r", "$X/a"))

    def test_cd_target(self):
        self.assertEqual(sw.cd_target("/r", ["cd", "-P", "--", "a"]), "/r/a")
        self.assertIsInstance(sw.cd_target("/r", ["cd", "-"]), sw.UnknownFolder)


class Paths(unittest.TestCase):
    def test_repo_relative(self):
        self.assertEqual(sw.repo_relative("/r", "/r/analysis", "x.py"), "analysis/x.py")
        self.assertIsNone(sw.repo_relative("/r", "/r", "/elsewhere/x.py"))
        self.assertIsNone(sw.repo_relative("/r", "/r", "."))

    def test_gated_rel_follows_the_config(self):
        self.assertEqual(sw.gated_rel("/r", "/r", "analysis/x.py", CONFIG), "analysis/x.py")
        self.assertIsNone(sw.gated_rel("/r", "/r", "data/x.py", CONFIG))

    def test_paths_in_text(self):
        self.assertEqual(sw.paths_in_text("/r", "/r", "source('analysis/x.R')", CONFIG), ["analysis/x.R"])
        self.assertEqual(sw.paths_in_text("/r", "/r", "setwd('analysis')", CONFIG), ["analysis"])
        self.assertEqual(sw.paths_in_text("/r", "/r", "print('analysis/readme')", CONFIG), [])


class Tables(unittest.TestCase):
    def test_word_tables(self):
        self.assertTrue(sw.RUNNERS.match("python3.11"))
        self.assertTrue(sw.MYCELIUM_SEES.match("./run.sh"))
        self.assertFalse(sw.MYCELIUM_SEES.match("julia"))
        self.assertTrue(sw.SCRIPT_EXT.search("a/Snakefile"))
        self.assertTrue(sw.SHELL_C.match("-lc"))
        self.assertIn("env", sw.WRAPPERS)
        self.assertIn("-C", sw.WRAPPER_OPTIONS["env"][1])
        self.assertTrue(sw.DURATION.match("1.5s"))


class GateReExports(unittest.TestCase):
    def test_every_public_name_is_the_same_object(self):
        names = [n for n in dir(sw) if not n.startswith("_") and n not in ("fnmatch", "os", "re")]
        self.assertGreater(len(names), 30)
        for name in names:
            with self.subTest(name=name):
                self.assertIs(getattr(gate, name), getattr(sw, name))


if __name__ == "__main__":
    unittest.main()
