"""handoff-resume chain: request, stop block, arm, stamp, resume in another session, once."""
import json, os, subprocess, sys, tempfile, time, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, "..", "resume_run.py")


def run(cwd, *args, event=None):
    out = subprocess.run([sys.executable, RUN, *args], cwd=cwd, input=json.dumps(event or {}),
                         capture_output=True, text=True)
    return out.returncode, out.stdout.strip()


def hook(cwd, kind, **event):
    event.setdefault("cwd", cwd)
    code, out = run(cwd, "--hook", kind, event=event)
    return json.loads(out) if out else {}


class Chain(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        subprocess.run(["git", "init", "-q", self.d])
        self.d = os.path.realpath(self.d)

    def write(self, text="# Handoff\n\n## Next action\nrun x\n"):
        open(os.path.join(self.d, "HANDOFF.md"), "w").write(text)

    def test_silent_without_marker(self):
        self.assertEqual(hook(self.d, "stop", session_id="a"), {})
        self.assertEqual(hook(self.d, "prompt", session_id="b"), {})

    def request(self, sid="a"):
        run(self.d, "request")
        hook(self.d, "post", session_id=sid, tool_input={"command": "sh py.sh resume_run.py request"})

    def test_full_chain(self):
        self.request()
        self.assertEqual(hook(self.d, "stop", session_id="other"), {})  # another session is not held
        self.assertEqual(hook(self.d, "stop", session_id="a")["decision"], "block")  # no HANDOFF.md yet
        self.assertEqual(hook(self.d, "stop", session_id="a", stop_hook_active=True), {})  # no loop
        time.sleep(0.05); self.write()
        self.assertEqual(hook(self.d, "stop", session_id="a")["decision"], "block")  # written, not armed
        self.assertEqual(run(self.d, "arm")[0], 0)
        self.assertIn("systemMessage", hook(self.d, "stop", session_id="a"))
        self.assertEqual(hook(self.d, "prompt", session_id="a"), {})  # arming session: no resume
        out = hook(self.d, "prompt", session_id="b")
        self.assertIn("Read HANDOFF.md", out["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(hook(self.d, "prompt", session_id="c"), {})  # delivered once
        self.assertEqual(hook(self.d, "prompt", session_id="b"), {})  # no repeat in b
        hook(self.d, "stop", session_id="b")  # b ended its first turn: marker gone
        self.assertEqual(run(self.d, "status")[1], "no marker")

    def test_no_session_id_does_nothing(self):
        self.request(); self.write(); run(self.d, "arm")
        self.assertEqual(hook(self.d, "prompt"), {})
        self.assertEqual(hook(self.d, "stop"), {})

    def test_stale_request_stops_holding(self):
        self.request()
        p = os.path.join(self.d, ".mycelium-extra", "resume.json")
        d = json.load(open(p)); d["requested"] = 1; json.dump(d, open(p, "w"))
        self.assertEqual(hook(self.d, "stop", session_id="a"), {})

    def test_arm_refuses(self):
        self.assertEqual(run(self.d, "arm")[0], 1)  # no file
        self.write("# Handoff\nno section\n")
        self.assertEqual(run(self.d, "arm")[0], 1)

    def test_old_handoff_not_armed(self):
        run(self.d, "request"); self.write()
        os.utime(os.path.join(self.d, "HANDOFF.md"), (1, 1))
        self.assertEqual(run(self.d, "arm")[0], 1)

    def test_pending_plan_and_cancel(self):
        self.request(); self.write("# H\n## Next action\nx\n## Pending plan\n- `abc`\n")
        run(self.d, "arm")
        text = hook(self.d, "prompt", session_id="b")["hookSpecificOutput"]["additionalContext"]
        self.assertIn("pending plan", text)
        run(self.d, "cancel")
        self.assertEqual(hook(self.d, "prompt", session_id="b"), {})


if __name__ == "__main__":
    unittest.main()
