"""Run: python3 skills/new-analysis/tests/test_run_sh_log.py"""

import os
import shutil
import stat
import subprocess
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_SH = os.path.join(HERE, "..", "templates", "run.sh")

FAKE = """#!/usr/bin/env bash
mkdir -p outputs/01_a outputs/02_b
echo x > outputs/01_a/x.txt
exit "${FAKE_EXIT:-0}"
"""


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as out:
        out.write(text)


class RunShLog(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        shutil.copy(RUN_SH, os.path.join(self.dir, "run.sh"))
        fake = os.path.join(self.dir, "fake_snakemake")
        write(fake, FAKE)
        os.chmod(fake, os.stat(fake).st_mode | stat.S_IXUSR)
        write(os.path.join(self.dir, "code", "01_a.R"), "x <- 1\n")
        write(os.path.join(self.dir, "code", "02_b.R"), "y <- 2\n")
        write(os.path.join(self.dir, "code", ".hidden"), "skip\n")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_sh(self, *args, **env):
        e = dict(os.environ, SNAKEMAKE=os.path.join(self.dir, "fake_snakemake"), **env)
        return subprocess.run(["bash", "run.sh"] + list(args), cwd=self.dir, env=e,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True)

    def entries(self):
        with open(os.path.join(self.dir, "logs", "CHANGES.md")) as f:
            text = f.read()
        return text, text.split("\n## ")[1:]

    def test_two_runs_log_changes_and_rewrites(self):
        self.assertEqual(self.run_sh().returncode, 0)
        time.sleep(1.1)
        write(os.path.join(self.dir, "code", "01_a.R"), "x <- 2\n")
        self.assertEqual(self.run_sh().returncode, 0)
        text, entries = self.entries()
        self.assertTrue(text.startswith("# Change log"))
        self.assertEqual(len(entries), 2)
        first, second = entries
        self.assertTrue(first.split("\n")[0].endswith(" nogit ok"), first)
        self.assertIn("- code/01_a.R: new", first)
        self.assertIn("- code/02_b.R: new", first)
        self.assertNotIn(".hidden", first)
        self.assertIn("- outputs/01_a/", first)
        self.assertIn("- code/01_a.R: changed\n", second)
        self.assertNotIn("02_b.R", second)
        self.assertIn("- outputs/01_a/", second)
        self.assertNotIn("outputs/02_b", second)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "logs", ".run-stamp")))
        self.assertTrue(os.path.exists(os.path.join(self.dir, "logs", ".code-hashes.tsv")))

    def test_removed_file(self):
        self.run_sh()
        os.remove(os.path.join(self.dir, "code", "02_b.R"))
        self.run_sh()
        _, entries = self.entries()
        self.assertIn("- code/02_b.R: removed", entries[1])

    def test_failure_is_logged_and_exit_kept(self):
        proc = self.run_sh(FAKE_EXIT="3")
        self.assertEqual(proc.returncode, 3)
        _, entries = self.entries()
        self.assertTrue(entries[0].split("\n")[0].endswith(" failed"), entries[0])

    def test_dry_run_logs_nothing(self):
        for flag in ("-n", "--dry-run", "-np"):
            self.assertEqual(self.run_sh(flag).returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "logs", "CHANGES.md")))


if __name__ == "__main__":
    unittest.main()
