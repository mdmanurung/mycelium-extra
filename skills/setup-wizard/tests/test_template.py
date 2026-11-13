#!/usr/bin/env python3
"""Tests for templates/template.sh. Run: python3.11 skills/setup-wizard/tests/test_template.py

Runs bash only. Slurm commands are stubs on PATH. MX_WIZARD_YES=1 is test-only.
"""
import os
import shutil
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

BASH = shutil.which("bash") or "bash"
TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "template.sh"
MARKER = "# STAGES:"


def library_text() -> str:
    text = TEMPLATE.read_text(encoding="utf-8")
    return text[: text.index(MARKER)]


class Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.lib = self.dir / "lib.sh"
        self.lib.write_text(library_text(), encoding="utf-8")
        self.bin = self.dir / "bin"
        self.bin.mkdir()
        self.work = self.dir / "work"
        self.work.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)

    def bash(self, snippet, stdin="", env=None):
        e = dict(os.environ)
        e.update(
            {
                "MX_WIZARD_YES": "1",
                "MX_POLL_SECS": "1",
                "HOME": str(self.dir / "home"),
                "PATH": f"{self.bin}:{os.environ['PATH']}",
                "SETUP_LOG": str(self.work / "logs" / "SETUP.md"),
                "SECRETS_FILE": str(self.dir / "home" / "secrets.env"),
            }
        )
        e.update(env or {})
        script = f"source {self.lib}\n{snippet}\n"
        return subprocess.run(
            [BASH, "-c", script],
            input=stdin,
            text=True,
            capture_output=True,
            cwd=self.work,
            env=e,
            timeout=60,
        )

    @property
    def log(self):
        return (self.work / "logs" / "SETUP.md").read_text(encoding="utf-8")


class Syntax(Case):
    def test_bash_n(self):
        r = subprocess.run(["bash", "-n", str(TEMPLATE)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_marker_and_attribution(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn(MARKER, text)
        self.assertIn("Matt Pocock", text)
        self.assertIn("MIT", text)

    def test_full_run_with_example_stage(self):
        r = subprocess.run(
            ["bash", str(TEMPLATE)],
            input="acct-lab\n",
            text=True,
            capture_output=True,
            cwd=self.work,
            env={
                **os.environ,
                "MX_WIZARD_YES": "1",
                "SETUP_LOG": str(self.work / "logs" / "SETUP.md"),
            },
            timeout=60,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("SLURM account is acct-lab", self.log)
        self.assertIn("DONE cluster-account", self.log)


class Log(Case):
    def test_log_and_done(self):
        r = self.bash('log_setup "hello"; mark_done "env"; was_done env && echo yes')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("yes", r.stdout)
        self.assertIn("hello", self.log)

    def test_skip_if_done_under_yes(self):
        r = self.bash('mark_done "env"; skip_if_done env && echo skipped')
        self.assertIn("skipped", r.stdout)

    def test_record_access(self):
        r = self.bash(
            'record_access "EGA study X"',
            env={"ACCESS_APPROVER": "DAC chair", "ACCESS_DATE": "2026-11-01"},
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("approved_by=DAC chair approved_on=2026-11-01", self.log)
        self.assertIn("access terms are yours", r.stdout)


class Secrets(Case):
    def test_secret_hidden_mode_600_and_never_logged(self):
        r = self.bash(
            'ask_secret API_KEY "Key:"; write_secret API_KEY "$API_KEY"',
            stdin="s3cr3t-value\n",
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("s3cr3t-value", r.stdout + r.stderr)
        f = self.dir / "home" / "secrets.env"
        self.assertIn("API_KEY='s3cr3t-value'", f.read_text())
        self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o600)
        self.assertNotIn("s3cr3t-value", self.log)
        self.assertIn("secret API_KEY stored", self.log)

    def test_upsert_is_idempotent(self):
        r = self.bash('write_secret K "a"; write_secret K "b"; write_secret K "b"')
        self.assertEqual(r.returncode, 0, r.stderr)
        text = (self.dir / "home" / "secrets.env").read_text()
        self.assertEqual(text.count("K="), 1)
        self.assertIn("K='b'", text)

    def test_log_refuses_a_secret_value(self):
        r = self.bash('write_secret K "topsecret"; log_setup "pasted topsecret here"')
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("topsecret", self.log)

    def test_refuses_unignored_file_in_repo(self):
        subprocess.run(["git", "init", "-q", str(self.work)], check=True)
        inside = self.work / "secrets.env"
        r = self.bash('write_secret K "value-123456"', env={"SECRETS_FILE": str(inside)})
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(inside.exists())
        (self.work / ".gitignore").write_text("secrets.env\n")
        r = self.bash('write_secret K "value-123456"', env={"SECRETS_FILE": str(inside)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(stat.S_IMODE(inside.stat().st_mode), 0o600)


class Checksums(Case):
    def test_match_and_mismatch(self):
        d = self.work / "data"
        d.mkdir()
        (d / "a.txt").write_text("alpha\n")
        sums = subprocess.run(
            ["sha256sum", "a.txt"], cwd=d, capture_output=True, text=True, check=True
        ).stdout
        (d / "SHA256SUMS").write_text(sums)
        r = self.bash("verify_checksums data/SHA256SUMS")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("checksums OK", self.log)
        (d / "a.txt").write_text("changed\n")
        r = self.bash("verify_checksums data/SHA256SUMS")
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue((d / "a.txt").exists(), "must not delete data")
        self.assertIn("checksums FAILED", self.log)

    def test_malformed_manifest_line_fails(self):
        d = self.work / "data"
        d.mkdir()
        (d / "a.txt").write_text("alpha\n")
        sums = subprocess.run(
            ["sha256sum", "a.txt"], cwd=d, capture_output=True, text=True, check=True
        ).stdout
        (d / "SUMS").write_text(sums + "garbage line here\n")
        r = self.bash("verify_checksums data/SUMS")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("checksums match", r.stdout)

    def test_dir_argument_other_than_manifest_folder(self):
        d, o = self.work / "data", self.work / "other"
        d.mkdir()
        o.mkdir()
        (d / "a.txt").write_text("alpha\n")
        sums = subprocess.run(
            ["sha256sum", "a.txt"], cwd=d, capture_output=True, text=True, check=True
        ).stdout
        (o / "M").write_text(sums)
        r = self.bash("verify_checksums other/M data")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("checksums OK", self.log)


class DoneStages(Case):
    def test_was_done_matches_whole_stage_name(self):
        r = self.bash("mark_done data-download; was_done data && echo WRONG; was_done data-download && echo RIGHT")
        self.assertNotIn("WRONG", r.stdout)
        self.assertIn("RIGHT", r.stdout)


class Sbatch(Case):
    def stubs(self, final_state, sacct_state=None):
        counter = self.dir / "n"
        self.stub(
            "sbatch",
            f'''for a; do last="$a"; done
d=$(dirname "$last"); n=$(basename "$last" .sbatch)
echo "hello from node" > "$d/$n-4242.log"
echo 4242
''',
        )
        self.stub(
            "squeue",
            f'''n=$(cat {counter} 2>/dev/null || echo 0); echo $((n+1)) > {counter}
[ "$n" -lt 1 ] && echo RUNNING
exit 0
''',
        )
        self.stub("sacct", f"echo {sacct_state or final_state}\n")

    def test_completed(self):
        self.stubs("COMPLETED")
        r = self.bash('sbatch_test smoke 20 "echo hi"')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("hello from node", r.stdout)
        self.assertIn("COMPLETED", self.log)
        self.assertTrue((self.work / "logs" / "setup-jobs" / "smoke.sbatch").exists())

    def test_failed_job_returns_nonzero(self):
        self.stubs("FAILED")
        r = self.bash('sbatch_test smoke 20 "false" || echo rc=$?')
        self.assertIn("rc=1", r.stdout)
        self.assertIn("FAILED", self.log)

    def test_preempted_returns_without_waiting_for_timeout(self):
        self.stub("sbatch", "echo 78\n")
        self.stub("squeue", "exit 0\n")
        self.stub("sacct", "echo PREEMPTED\n")
        start = time.time()
        r = self.bash('sbatch_test p 600 "true" || echo rc=$?')
        self.assertLess(time.time() - start, 30)
        self.assertIn("rc=1", r.stdout)
        self.assertIn("PREEMPTED", self.log)

    def test_timeout_does_not_cancel(self):
        self.stub("sbatch", "echo 77\n")
        self.stub("squeue", "echo RUNNING\n")
        self.stub("sacct", "exit 0\n")
        self.stub("scancel", f"touch {self.dir}/cancelled\n")
        r = self.bash('sbatch_test slow 2 "sleep 100" || echo rc=$?')
        self.assertIn("rc=1", r.stdout)
        self.assertIn("scancel 77", r.stdout)
        self.assertFalse((self.dir / "cancelled").exists())

    def test_no_sbatch_is_a_skip(self):
        # A PATH of symlinks to basic tools only, so a real sbatch is never found.
        bare = self.dir / "bare"
        bare.mkdir()
        for tool in ("mkdir", "dirname", "sed", "date", "hostname", "cat", "tail"):
            real = subprocess.run(
                ["which", tool], capture_output=True, text=True
            ).stdout.strip()
            if real:
                (bare / tool).symlink_to(real)
        r = self.bash('sbatch_test x 5 "true" || echo rc=$?', env={"PATH": str(bare)})
        self.assertIn("rc=1", r.stdout)
        self.assertIn("sbatch not found", r.stdout)


if __name__ == "__main__":
    unittest.main()
