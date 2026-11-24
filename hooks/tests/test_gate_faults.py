#!/usr/bin/env python3
"""Run: python3 hooks/tests/test_gate_faults.py

Fault injection for three review findings (roadmap 19, row B8). Each test failed at 789d7d6.

1. Hook time limit: the PreToolUse hook is killed at 10 s and a killed hook lets the call through, so the
   pin re-check of a Bash call must end in time, whatever `pin_seconds` says, and say what it skipped.
2. Freeze against stop: `freeze <hash>` rewrites `pending/<session>.json` under the same lock as the stop
   hook, so a plan a parallel stop adds is kept.
3. Same-second pin: a pin without a sha256 tells a same-size edit in the same second apart by nanoseconds.
"""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import gate  # noqa: E402

PLAN = "## Plan\nInputs: data/big.bin\n\n| 1 | run `analysis/x.py` | repo | check |\n\nPlan status: READY"
HOOK_TIMEOUT = 10  # hooks/hooks.json, PreToolUse


class FaultTest(unittest.TestCase):
    def setUp(self):
        saved = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(saved)))
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        os.environ["HOME"] = home
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, ".mycelium-extra"))
        os.makedirs(os.path.join(self.root, "analysis"))
        os.makedirs(os.path.join(self.root, "data"))
        open(os.path.join(self.root, "analysis", "x.py"), "w").close()
        self.config({})
        gate.clear_scan_memo()
        self.addCleanup(gate.clear_scan_memo)

    def config(self, data):
        with open(os.path.join(self.root, ".mycelium-extra", "gate.json"), "w") as handle:
            json.dump(data, handle)

    def hook(self, name, payload, session="s1"):
        text = json.dumps(dict(payload, session_id=session, cwd=self.root))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            gate.main(["gate.py", name], text=text, root=self.root)
        return json.loads(out.getvalue()) if out.getvalue().strip() else None


class HookTimeLimitTest(FaultTest):
    def test_a_slow_pin_recheck_ends_before_the_hook_is_killed(self):
        # 40 MiB of sparse zeros: 40 hash blocks, cheap on disk
        with open(os.path.join(self.root, "data", "big.bin"), "wb") as handle:
            handle.truncate(40 << 20)
        self.config({"pin_seconds": 30})
        notice = self.hook("stop", {"last_assistant_message": PLAN})
        digest = notice["systemMessage"].split("approve plan ")[1][:8]
        self.hook("prompt", {"prompt": "approve plan " + digest})
        gate.clear_scan_memo()

        # a slow network filesystem: each 1 MiB block the hash reads costs half a second; other work is free
        start = time.time()
        blocks = [0]

        def clock():
            if sys._getframe(1).f_code.co_name == "sha256_file":
                blocks[0] += 1
            return start + 0.5 * blocks[0]

        with mock.patch.object(gate.time, "time", clock):
            result = self.hook("tool", {"tool_name": "Bash", "tool_input": {"command": "python analysis/x.py"}})
            elapsed = clock() - start
        self.assertLess(elapsed, HOOK_TIMEOUT, "the hook would be killed and the call let through")
        decision = (result or {}).get("hookSpecificOutput", {}).get("permissionDecision")
        self.assertNotEqual(decision, "deny")
        self.assertIn("not re-checked", (result or {}).get("systemMessage", ""))
        self.assertIn("data/big.bin", result["systemMessage"])

    def test_a_long_pin_seconds_still_applies_outside_a_tool_call(self):
        budget = gate.hash_budget(dict(gate.DEFAULTS, pin_seconds=20))  # the Stop hook has 30 s
        self.assertGreater(budget["deadline"] - time.time(), gate.TOOL_HASH_SECONDS)
        capped = gate.hash_budget(dict(gate.DEFAULTS, pin_seconds=20), gate.TOOL_HASH_SECONDS)
        self.assertLessEqual(capped["deadline"] - time.time(), gate.TOOL_HASH_SECONDS)


class FreezeAgainstStopTest(FaultTest):
    def test_a_plan_a_parallel_stop_adds_survives_a_freeze(self):
        path = gate.state_path(self.root, "pending", "s1.json")
        os.makedirs(os.path.dirname(path))
        with open(path, "w") as handle:
            json.dump([{"hash": "cccccccc", "ready": True}], handle)
        frozen = {"hash": "aaaaaaaa", "ready": True, "freeze": True}
        real_write = gate.write_json
        racers = []

        def parallel_stop():  # what on_stop does, under its lock
            with gate.state_lock(self.root, "pending-s1"):
                plans = gate.read_json(path, [])
                real_write(path, plans + [{"hash": "bbbbbbbb", "ready": True}])

        def write_json(target, data):
            if target == path and not racers:  # the freeze has read the file and is about to write it
                racers.append(threading.Thread(target=parallel_stop))
                racers[0].start()
                racers[0].join(1.0)  # under 2 s: state_lock gives up and goes ahead unlocked after 2 s
            real_write(target, data)

        with mock.patch.object(gate, "freeze_entry", return_value=(frozen, "card")), \
                mock.patch.object(gate, "write_json", write_json):
            self.hook("prompt", {"prompt": "freeze aaaaaaaa"})
            racers[0].join(5)
        with open(path) as handle:
            kept = {plan["hash"] for plan in json.load(handle)}
        self.assertEqual(kept, {"aaaaaaaa", "bbbbbbbb", "cccccccc"})


class SameSecondPinTest(FaultTest):
    def test_a_same_size_edit_in_the_same_second_is_a_change(self):
        target = os.path.join(self.root, "data", "in.tsv")
        with open(target, "w") as handle:
            handle.write("a\t1\n")
        second = int(time.time()) * 10 ** 9
        os.utime(target, ns=(second, second + 100_000_000))
        no_hash = {"bytes": 0, "deadline": time.time() + 5}  # past the byte budget: size and mtime only
        pin = gate.fingerprint(target, no_hash)
        self.assertNotIn("sha256", pin)
        with open(target, "w") as handle:
            handle.write("a\t2\n")
        os.utime(target, ns=(second, second + 600_000_000))
        now = gate.fingerprint(target, no_hash, pin)
        self.assertFalse(gate.unchanged(pin, now))

    def test_a_pin_from_before_this_fix_still_compares_by_seconds(self):
        target = os.path.join(self.root, "data", "in.tsv")
        with open(target, "w") as handle:
            handle.write("a\t1\n")
        old = {"size": 4, "mtime": int(os.stat(target).st_mtime)}
        now = gate.fingerprint(target, {"bytes": 0, "deadline": time.time() + 5}, old)
        self.assertTrue(gate.unchanged(old, now))
        self.assertTrue(gate.valid_fingerprint(now))


if __name__ == "__main__":
    unittest.main()
