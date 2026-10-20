"""Capture concurrency and recoverability; real Mycelium updater is qualified separately."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPT = os.path.join(PLUGIN, "skills", "idea", "scripts", "capture.py")


class CaptureTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.helper = os.path.join(self.root, "upsert.py")
        with open(self.helper, "w") as handle:
            handle.write("import sys\np,k,row=sys.argv[1:4]\n"
                         "with open(p) as h: lines=h.readlines()\n"
                         "lines=[l for l in lines if k not in l]\n"
                         "with open(p,'w') as h: h.write(''.join(lines)+row+'\\n')\n")
        self.idea = os.path.join(self.root, "input.txt")
        with open(self.idea, "w") as handle:
            handle.write("Same title for two ideas\nVerbatim | content.")

    def cmd(self, recover=False, helper=None):
        return [sys.executable, SCRIPT, "--plugin-root", PLUGIN, "--root", self.root,
                "--helper", helper or self.helper, "--python", sys.executable] + (
                    ["--recover"] if recover else ["--text-file", self.idea])

    def run_capture(self, **kwargs):
        return subprocess.run(self.cmd(**kwargs), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_simultaneous_titles_retain_both_verbatim_ideas(self):
        jobs = [subprocess.Popen(self.cmd(), stdout=subprocess.PIPE, stderr=subprocess.PIPE) for i in range(2)]
        for job in jobs:
            out, err = job.communicate(timeout=15)
            self.assertEqual(job.returncode, 0, err)
        todo = os.path.join(self.root, "todo")
        files = [n for n in os.listdir(todo) if n.endswith(".md") and n != "TODO_REGISTRY.md"]
        self.assertEqual(len(files), 2)
        for name in files:
            with open(os.path.join(todo, name)) as handle:
                self.assertIn("Same title for two ideas\nVerbatim | content.", handle.read())
        with open(os.path.join(todo, "TODO_REGISTRY.md")) as handle:
            registry = handle.read()
        for name in files:
            self.assertEqual(registry.count("[{}]({})".format(name, name)), 1)

    def test_failed_publication_retains_text_and_recovery_is_idempotent(self):
        self.assertEqual(self.run_capture(helper="/missing/helper").returncode, 1)
        todo = os.path.join(self.root, "todo")
        note = next(os.path.join(todo, n) for n in os.listdir(todo) if n.endswith(".json"))
        with open(note) as handle:
            record = json.load(handle)
        self.assertFalse(record["published"])
        for i in range(2):
            self.assertEqual(self.run_capture(recover=True).returncode, 0)
        with open(os.path.join(todo, "TODO_REGISTRY.md")) as handle:
            self.assertEqual(handle.read().count(record["key"]), 1)

    def test_changed_item_is_not_overwritten_during_recovery(self):
        self.run_capture(helper="/missing/helper")
        todo = os.path.join(self.root, "todo")
        name = next(n for n in os.listdir(todo) if n.endswith(".md") and n != "TODO_REGISTRY.md")
        path = os.path.join(todo, name)
        with open(path, "w") as handle:
            handle.write("human edits")
        self.assertEqual(self.run_capture(recover=True).returncode, 1)
        with open(path) as handle:
            self.assertEqual(handle.read(), "human edits")

    def test_long_single_token_is_parked_with_a_bounded_filename(self):
        with open(self.idea, "w") as handle:
            handle.write("a" * 300 + " b c")
        result = self.run_capture()
        self.assertEqual(result.returncode, 0, result.stderr)
        name = result.stdout.decode().strip().split("/")[-1]
        self.assertLessEqual(len(name), 70)

    def test_corrupt_recovery_record_is_named_not_a_bare_parser_error(self):
        todo = os.path.join(self.root, "todo")
        os.makedirs(todo)
        open(os.path.join(todo, ".capture-bad.json"), "w").close()
        result = self.run_capture()
        self.assertEqual(result.returncode, 1)
        self.assertIn(".capture-bad.json", result.stderr.decode())


if __name__ == "__main__":
    unittest.main()
