"""hooks/mxpy is the launcher agent Bash calls use: executable, no .sh suffix, same interpreter choice as py.sh."""

import os
import subprocess
import sys
import unittest

HOOKS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MXPY = os.path.join(HOOKS, "mxpy")


class MxpyTest(unittest.TestCase):
    def test_it_is_executable_and_has_no_sh_suffix(self):
        self.assertTrue(os.access(MXPY, os.X_OK))
        self.assertFalse(MXPY.endswith(".sh"))

    @unittest.skipIf(sys.version_info < (3, 9), "the override runs the launcher under the test interpreter")
    def test_it_runs_python_directly(self):
        env = dict(os.environ, MYCELIUM_EXTRA_PYTHON=sys.executable)
        out = subprocess.run([MXPY, "-c", "print(1)"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             universal_newlines=True)
        self.assertEqual((out.returncode, out.stdout), (0, "1\n"), out.stderr)

    @unittest.skipIf(sys.version_info < (3, 9), "the override runs the launcher under the test interpreter")
    def test_py_sh_delegates_to_it(self):
        env = dict(os.environ, MYCELIUM_EXTRA_PYTHON=sys.executable)
        out = subprocess.run(["sh", os.path.join(HOOKS, "py.sh"), "-c", "print(2)"], env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual((out.returncode, out.stdout), (0, "2\n"), out.stderr)


if __name__ == "__main__":
    unittest.main()
