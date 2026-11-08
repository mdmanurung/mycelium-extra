"""Run: python3 hooks/tests/test_hook_limits.py

Stress-test regressions: a hook answers inside its time limit (watchdog), never hashes a FIFO,
caps Stop blocks for hosts without stop_hook_active, and survives a bad MYCELIUM_EXTRA_PYTHON.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HOOKS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HOOKS)
sys.dont_write_bytecode = True
import gate  # noqa: E402
import gate_run  # noqa: E402


class HookLimitsTest(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.base)

    def test_watchdog_stops_a_hang_even_when_an_inner_handler_swallows_exceptions(self):
        old_run, old_limit = gate_run.run, dict(gate_run.LIMITS)

        def hang(argv):
            try:
                time.sleep(5)
            except Exception:
                pass

        gate_run.run, gate_run.LIMITS["stop"] = hang, 1
        self.addCleanup(setattr, gate_run, "run", old_run)
        self.addCleanup(gate_run.LIMITS.update, old_limit)
        start = time.time()
        with open(os.devnull, "w") as sink:
            stdout, sys.stdout = sys.stdout, sink
            try:
                code = gate_run.main(["gate_run.py", "stop"])
            finally:
                sys.stdout = stdout
        self.assertEqual(code, 0)
        self.assertLess(time.time() - start, 3)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "needs mkfifo")
    def test_a_fifo_is_not_hashed(self):
        fifo = os.path.join(self.base, "fifo")
        os.mkfifo(fifo)
        self.assertIsNone(gate.sha256_file(fifo))

    def test_a_bad_python_override_is_ignored_in_hook_mode(self):
        launcher = os.path.join(HOOKS, "py.sh")
        env = dict(os.environ, MYCELIUM_EXTRA_PYTHON=os.path.join(self.base, "missing"))
        result = subprocess.run(["sh", launcher, "--hook", "-c", "print('ok')"], env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=20)
        self.assertNotIn(result.returncode, (126, 127))

    def test_a_deleted_cwd_does_not_crash_the_hook(self):
        gone = os.path.join(self.base, "gone")
        os.mkdir(gone)
        script = "import os,sys; sys.path.insert(0, %r); os.chdir(%r); os.rmdir(%r); import gate_run; " \
                 "print(gate_run.safe_cwd())" % (HOOKS, gone, gone)
        result = subprocess.run([sys.executable, "-c", script], stdout=subprocess.PIPE, timeout=20)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.decode().strip(), "/")

    def test_stop_blocks_are_capped_without_stop_hook_active(self):
        root = os.path.join(self.base, "repo")
        os.makedirs(os.path.join(root, ".mycelium-extra", "pending"))
        counter = os.path.join(root, ".mycelium-extra", "pending", "s.lint-stop-count")
        gate.write_json(counter, {"n": 2, "ts": time.time()})
        event = {"session_id": "s"}
        self.assertIsNone(gate.lint_stop_block(root, event, {"lint_before_stop": True}))


if __name__ == "__main__":
    unittest.main()
