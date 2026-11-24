#!/usr/bin/env python3
"""Run: python3 hooks/tests/test_gate_launchers.py

A covered script started through a launcher the gate does not name, through a payload option, or by
import is a covered run (roadmap 19, choice C3); a launcher with no runner after it, and a program that
only reads its operands, runs nothing.
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import gate  # noqa: E402


class LauncherTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        for rel in ("analysis/a.py", "analysis/__init__.py", "scripts/ok.py"):
            os.makedirs(os.path.join(self.root, os.path.dirname(rel)), exist_ok=True)
            open(os.path.join(self.root, rel), "w").close()
        self.config = dict(gate.DEFAULTS, _notices=[])

    def covered(self, command):
        found = set()
        for result in gate.analyse_command(command, self.root, self.root, self.config):
            found.update(result[2])
        return found

    def test_launched_runs_are_covered(self):
        for command in [
            "mpirun -n 4 python analysis/a.py",
            "mpiexec -n 2 python analysis/a.py",
            "torchrun --nproc_per_node 2 analysis/a.py",
            "accelerate launch analysis/a.py",
            "sudo -u bob python analysis/a.py",
            "doas python analysis/a.py",
            "runuser -u bob -- python analysis/a.py",
            "su bob -c 'python analysis/a.py'",
            "flock /tmp/lock python analysis/a.py",
            "numactl --cpunodebind=0 python analysis/a.py",
            "taskset -c 0-3 python analysis/a.py",
            "strace -f python analysis/a.py",
            "script -q -c 'python analysis/a.py' /dev/null",
            "systemd-run --user python analysis/a.py",
            "git bisect run python analysis/a.py",
            "git rebase -x 'python analysis/a.py' HEAD~2",
            "builtin exec python analysis/a.py",
            "pypy3 analysis/a.py",
            "ipython analysis/a.py",
            "python -c 'import analysis.a'",
            "python -c 'from analysis import a'",
            "mpirun -n 4 ./analysis/a.py",
            "valgrind ./analysis/a.py",
            "chrt 10 analysis/a.py",
            "flock /tmp/lock ./analysis/a.py",
            "taskset -c 0 ./analysis/a.py",
            "perf stat ./analysis/a.py",
        ]:
            self.assertEqual(self.covered(command), {"analysis/a.py"}, command)

    def test_launchers_and_readers_with_no_covered_run(self):
        for command in [
            "mpirun -n 4 hostname",
            "sudo ls analysis",
            "strace -c ls analysis",
            "echo python analysis/a.py",
            "grep -rn python analysis/",
            "git log -- analysis/a.py",
            "git commit -m 'python analysis/a.py'",
            "flock /tmp/lock echo done",
            "sudo python scripts/ok.py",
            "python -c 'import numpy'",
            "sudo cat analysis/a.py",
            "bat -l python analysis/a.py",
            "pygmentize -l python analysis/a.py",
            "shellcheck -s bash analysis/a.py",
        ]:
            self.assertEqual(self.covered(command), set(), command)


if __name__ == "__main__":
    unittest.main()
