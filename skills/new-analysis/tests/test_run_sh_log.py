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
[ -z "${FAKE_PANELS:-}" ] || { mkdir -p outputs/panels outputs/scratch; echo x > outputs/panels/p.txt; echo x > outputs/scratch/s.txt; }
[ -z "${FAKE_NUMBERS:-}" ] || { mkdir -p outputs; echo "$FAKE_NUMBERS" > outputs/numbers.json; }
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

    def test_numbers_json_change_is_logged_and_a_same_run_is_not(self):
        # a run that rewrites only outputs/numbers.json (Mycelium's register_value) used to log "none"
        self.run_sh(FAKE_NUMBERS='{"values": []}')
        self.run_sh(FAKE_NUMBERS='{"values": []}')  # same bytes again: no change
        self.run_sh(FAKE_NUMBERS='{"values": [1]}')
        _, entries = self.entries()
        self.assertIn("- outputs/numbers.json: numbers.json changed", entries[0])  # absent before, present after
        self.assertNotIn("numbers.json", entries[1])
        self.assertIn("- outputs/numbers.json: numbers.json changed", entries[2])
        self.assertIn("outputs rewritten:\n- outputs/01_a/\n- outputs/numbers.json", entries[2])

    def test_numbers_json_alone_replaces_none(self):
        os.makedirs(os.path.join(self.dir, "outputs"))
        write(os.path.join(self.dir, "outputs", "numbers.json"), "{}")
        no_steps = os.path.join(self.dir, "fake_snakemake")
        write(no_steps, '#!/usr/bin/env bash\necho \'{"values": [1]}\' > outputs/numbers.json\n')
        os.chmod(no_steps, os.stat(no_steps).st_mode | stat.S_IXUSR)
        self.run_sh()
        _, entries = self.entries()
        self.assertIn("outputs rewritten:\n- outputs/numbers.json: numbers.json changed\n", entries[0])
        self.assertNotIn("outputs rewritten: none", entries[0])

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

    def test_failed_run_keeps_edits_for_the_next_entry(self):
        self.run_sh()
        time.sleep(1.1)
        write(os.path.join(self.dir, "code", "01_a.R"), "x <- 3\n")
        self.assertEqual(self.run_sh(FAKE_EXIT="2").returncode, 2)
        self.assertEqual(self.run_sh().returncode, 0)
        _, entries = self.entries()
        self.assertIn("- code/01_a.R: changed", entries[1])
        self.assertIn("- code/01_a.R: changed", entries[2])

    def test_short_flag_with_n_is_a_real_run(self):
        self.assertEqual(self.run_sh("-Rstep01_scan").returncode, 0)
        self.assertEqual(len(self.entries()[1]), 1)

    def test_untracked_script_marks_dirty(self):
        git = ["git", "-c", "user.email=a@b", "-c", "user.name=t"]
        subprocess.run(git + ["init", "-q"], cwd=self.dir, check=True)
        subprocess.run(git + ["add", "-A"], cwd=self.dir, check=True)
        subprocess.run(git + ["commit", "-q", "-m", "x"], cwd=self.dir, check=True)
        write(os.path.join(self.dir, "code", "03_new.R"), "z <- 3\n")
        self.run_sh()
        self.assertTrue(self.entries()[1][0].split("\n")[0].endswith(" dirty ok"), self.entries()[1][0])

    def test_two_runs_at_once_keep_two_whole_entries(self):
        procs = [subprocess.Popen(["bash", "run.sh"], cwd=self.dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env=dict(os.environ, SNAKEMAKE=os.path.join(self.dir, "fake_snakemake")))
                 for _ in range(2)]
        for proc in procs:
            proc.communicate()
        _, entries = self.entries()
        self.assertEqual(len(entries), 2)
        with open(os.path.join(self.dir, "logs", ".code-hashes.tsv")) as f:
            self.assertEqual(len(f.read().splitlines()), 2)

    def test_panels_folder_is_listed_but_other_folders_are_not(self):
        self.run_sh(FAKE_PANELS="1")
        _, entries = self.entries()
        self.assertIn("- outputs/panels/", entries[0])
        self.assertNotIn("outputs/scratch", entries[0])

    def test_snakefile_targets_every_step_output(self):
        # Snakemake with the last step's outputs alone says "Nothing to be done" after a middle step failed,
        # while run.sh exits 0 (found by tests/e2e_real.py). rule all must also request each rule's outputs.
        with open(os.path.join(HERE, "..", "templates", "Snakefile")) as f:
            text = f.read()
        head, rule_all = text.split("rule all:\n", 1)
        self.assertIn("for r in workflow.rules if r.name != \"all\" for out in r.output", head)
        self.assertIn("@@LAST_OUTPUTS@@\n        every_step_output,\n", rule_all)

    def test_dry_run_logs_nothing(self):
        for flag in ("-n", "--dry-run", "-np", "-pn"):
            self.assertEqual(self.run_sh(flag).returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "logs", "CHANGES.md")))


if __name__ == "__main__":
    unittest.main()
