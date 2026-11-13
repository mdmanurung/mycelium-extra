"""Which command forms open Mycelium's post-action cycle.

Mycelium's PostToolUse hook asks its detector (`extract_data_lineage_event.py
--check-post-action`) whether a Bash command ran an analysis. Exit 0 means the
cycle opens. This test asks the real detector about each form Extra uses or
could use, so a change in Mycelium shows up here.

The detector comes from the installed Mycelium plugin. Set MYCELIUM_UPSTREAM
to a checkout or a cache directory to use another copy. The test skips when
none is found. Tested against Mycelium 0.9.3.

Run: python3 tests/test_mycelium_detector.py
"""
import glob
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
RELATIVE = "skills/core/scripts/extract_data_lineage_event.py"


def version_key(path):
    """Sort key of a cache path by the numbers of its version folder, so 0.10.0 sorts after 0.9.3."""
    folder = os.path.basename(path[:-len(RELATIVE) - 1])
    return [int(n) for n in re.findall(r"\d+", folder)]


def find_detector():
    env = os.environ.get("MYCELIUM_UPSTREAM")
    if env:
        path = Path(env) / RELATIVE
        return path if path.is_file() else None
    pattern = os.path.expanduser("~/.claude/plugins/cache/mycelium/mycelium/*/" + RELATIVE)
    found = sorted(glob.glob(pattern), key=version_key)  # 0.10.0 after 0.9.3, not before
    return Path(found[-1]) if found else None


DETECTOR = find_detector()


@unittest.skipUnless(DETECTOR, "Mycelium is not installed; set MYCELIUM_UPSTREAM to test its detector")
class PostActionDetector(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        (self.project / "script.py").write_text("print(1)\n")
        (self.project / "run.sh").write_text("#!/bin/sh\npython script.py\n")
        (self.project / "Snakefile").write_text("rule all:\n    input: []\n")
        (self.project / "job.sbatch").write_text("#!/bin/sh\npython script.py\n")

    def opens_cycle(self, command):
        result = subprocess.run(
            [sys.executable, str(DETECTOR), "--cwd", str(self.project), "--ts", "2026-01-01T00:00:00Z",
             "--bash-cmd", command, "--bash-exit", "0", "--check-post-action"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return result.returncode == 0

    def test_extra_helper_form_currently_opens_the_cycle(self):
        # The form every Extra skill uses. This pins today's verdict, not a wish: if Mycelium exempts
        # Extra's helper, this test should flip. VERDICT 2026-11-13, Mycelium 0.9.3: it opens the cycle,
        # because the detector reads `sh <file>.sh` as a shell runner and does not exempt Extra's plugin root.
        skill = ROOT / "skills/verify"
        for command in (
            "sh {}/../../hooks/py.sh - --plugin-root {}/../.. status < {}/scripts/verify.py".format(skill, skill, skill),
            "sh {}/../../hooks/py.sh - status < script.py".format(skill),
            "sh {}/hooks/py.sh script.py status".format(ROOT),
        ):
            with self.subTest(command=command):
                self.assertTrue(self.opens_cycle(command))

    def test_forms_that_open_the_cycle(self):
        for command in ("bash run.sh", "snakemake -j1", "sbatch job.sbatch", "python script.py"):
            with self.subTest(command=command):
                self.assertTrue(self.opens_cycle(command))

    def test_extensionless_launcher_does_not_open_the_cycle(self):
        # A real extensionless executable: no .sh suffix, not an interpreter word, so the detector ignores it.
        launcher = self.project / "mxpy"
        launcher.write_text("#!/bin/sh\nexec python \"$@\"\n")
        launcher.chmod(0o755)
        for command in ("{}/mxpy - status < script.py".format(self.project), "./mxpy script.py status",
                        "mxpy script.py status"):
            with self.subTest(command=command):
                self.assertFalse(self.opens_cycle(command))

    def test_non_executing_forms_do_not_open_the_cycle(self):
        for command in ("snakemake -n", "bash -n run.sh", "sbatch --help"):
            with self.subTest(command=command):
                self.assertFalse(self.opens_cycle(command))


if __name__ == "__main__":
    unittest.main()
