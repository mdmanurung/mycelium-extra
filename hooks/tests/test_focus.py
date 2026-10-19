"""Run: python3 hooks/tests/test_focus.py

`focus` (hooks/focus.py through gate.py on_prompt): per-session, typed-command-only, advisory. Cases are
named for the spec's acceptance IDs (docs/roadmap/10-focus-track-changes.md)."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(HERE, "..", "gate.py")
PLAN = "## Plan\n| 1 | run `analysis/a/run.py` | repo | check |\n\nPlan status: READY"


class FocusTest(unittest.TestCase):
    def setUp(self):
        saved = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(saved)))
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        os.environ["HOME"] = home
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, ".mycelium-extra"))
        with open(os.path.join(self.root, ".mycelium-extra", "gate.json"), "w") as handle:
            json.dump({}, handle)
        for name in ("a", "b"):
            os.makedirs(os.path.join(self.root, "analysis", name))
        with open(os.path.join(self.root, "analysis", "a", "run.py"), "w") as handle:
            handle.write("print(1)\n")
        with open(os.path.join(self.root, "analysis", "a", "A.md"), "w") as handle:
            handle.write("# A\n\nObjective: Characterize interferon response in PBMC.\n")

    def hook(self, event, payload, session="s1"):
        payload = dict(payload, cwd=self.root)
        if session is not None:
            payload["session_id"] = session
        proc = subprocess.run([sys.executable, GATE, event], input=json.dumps(payload).encode("utf-8"),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout.decode("utf-8")) if proc.stdout.strip() else None

    def say(self, prompt, session="s1"):
        return self.hook("prompt", {"prompt": prompt}, session)

    def text(self, result):
        return (result or {}).get("reason") or (result or {}).get("systemMessage") or ""

    def approve_text(self, text, session="s1"):
        notice = self.hook("stop", {"last_assistant_message": text}, session)
        digest = notice["systemMessage"].split("approve plan ")[1][:8]
        self.say("approve plan " + digest, session)
        return digest

    def approve(self, session="s1"):
        notice = self.hook("stop", {"last_assistant_message": PLAN}, session)
        digest = notice["systemMessage"].split("approve plan ")[1][:8]
        self.say("approve plan " + digest, session)
        return digest

    def slurp(self, *parts):
        with open(os.path.join(self.root, *parts)) as handle:
            return handle.read()

    def record(self, session="s1"):
        with open(os.path.join(self.root, ".mycelium-extra", "focus", session + ".json")) as handle:
            return json.load(handle)

    def test_start_status_switch_end_keeps_history(self):  # F05
        self.assertIn("focus started on analysis/a", self.text(self.say("focus analysis/a")))
        card = self.text(self.say("focus status"))
        self.assertIn("focus analysis/a", card)
        self.assertIn("Characterize interferon response in PBMC. (analysis/a/A.md)", card)
        self.assertIn("focus switched on analysis/b (was analysis/a)", self.text(self.say("focus switch analysis/b")))
        self.assertIn("ended", self.text(self.say("focus end")))
        episodes = self.record()["episodes"]
        self.assertEqual([e["analysis_path"] for e in episodes], ["analysis/a", "analysis/b"])
        self.assertTrue(all(e["ended_at"] for e in episodes))
        self.assertIn("focus none (last: analysis/b)", self.text(self.say("focus status")))
        self.assertEqual(oct(os.stat(os.path.join(self.root, ".mycelium-extra", "focus", "s1.json")).st_mode & 0o777), "0o600")

    def test_status_is_for_the_user_only(self):
        result = self.say("focus status")
        self.assertEqual(result["decision"], "block")  # the agent never sees it

    def test_two_sessions_do_not_share_a_focus(self):  # F03
        self.say("focus analysis/a", "s1")
        self.say("focus analysis/b", "s2")
        self.assertEqual(self.record("s1")["episodes"][0]["analysis_path"], "analysis/a")
        self.assertEqual(self.record("s2")["episodes"][0]["analysis_path"], "analysis/b")
        self.say("focus end", "s1")
        self.assertIn("focus analysis/b", self.text(self.say("focus status", "s2")))

    def test_focus_without_an_approval_grants_nothing(self):  # F01
        self.say("focus analysis/a")
        self.assertIn("not authorized: no approved plan names this folder", self.text(self.say("focus status")))
        denied = self.hook("tool", {"tool_name": "Bash", "tool_input": {"command": "python analysis/a/run.py"}})
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertFalse(os.path.isdir(os.path.join(self.root, ".mycelium-extra", "approvals")))

    def test_runs_row_names_the_session_that_holds_the_approval(self):  # F28
        digest = self.approve("s1")
        self.say("focus analysis/a", "s1")
        self.say("focus analysis/a", "s2")
        self.assertIn("is active in this session (focus did not grant it", self.text(self.say("focus status", "s1")))
        self.assertIn("belongs to another session", self.text(self.say("focus status", "s2")))
        path = os.path.join(self.root, ".mycelium-extra", "approvals", digest + ".json")
        with open(path) as handle:
            record = json.load(handle)
        record["approved_at"] = time.time() - 3 * 86400
        with open(path, "w") as handle:
            json.dump(record, handle)
        self.assertIn("steps name paths in or above this folder has expired", self.text(self.say("focus status", "s1")))
        self.assertTrue(self.record("s1")["episodes"][0]["ended_at"] is None)  # still focused, no re-approval

    def test_missing_or_unsafe_target_is_refused(self):  # F02, F07
        os.symlink("/tmp", os.path.join(self.root, "analysis", "out"))
        for prompt in ("focus analysis/nope", "focus analysis/../x", "focus analysis/a/../../etc", "focus analysis/out",
                       "focus analysis/.hidden", "focus analysis//a", "focus analysis/a;rm"):
            result = self.say(prompt)
            self.assertEqual(result["decision"], "block", prompt)
            self.assertIn("no focus", result["reason"], prompt)
        self.assertIn("there are: analysis/a, analysis/b", self.text(self.say("focus analysis/nope")))
        self.assertFalse(os.path.isdir(os.path.join(self.root, ".mycelium-extra", "focus")))

    def test_no_session_id_is_never_a_shared_focus(self):  # F07
        for session in (None, "", "unknown"):
            result = self.hook("prompt", {"prompt": "focus analysis/a"}, session)
            self.assertIn("no session id", result["reason"])
        self.assertFalse(os.path.isdir(os.path.join(self.root, ".mycelium-extra", "focus")))

    def test_odd_session_ids_get_their_own_safe_file(self):
        self.say("focus analysis/a", "../../evil")
        files = os.listdir(os.path.join(self.root, ".mycelium-extra", "focus"))
        self.assertEqual(len(files), 1)
        self.assertRegex(files[0], r"^______evil-[0-9a-f]{8}\.json$")  # a hash keeps two odd ids from sharing a file

    def test_prose_and_other_commands_do_not_match(self):  # F06
        for prompt in ("focus on QC today", "please focus analysis/a", "focus", "focus analysis/a and more",
                       "approve plan deadbeef", "freeze deadbeef"):
            result = self.say(prompt)
            self.assertNotIn("focus started", self.text(result), prompt)
        self.assertFalse(os.path.isdir(os.path.join(self.root, ".mycelium-extra", "focus")))

    def test_second_start_asks_for_switch(self):
        self.say("focus analysis/a")
        self.assertIn("Type `focus switch analysis/b`", self.say("focus analysis/b")["reason"])
        self.assertIn("no focus is active", self.say("focus end", "other")["reason"])

    def test_context_line_only_while_open_and_only_for_that_session(self):
        self.assertIsNone(self.say("what is the weather"))
        self.say("focus analysis/a")
        context = self.say("let's talk about QC")["hookSpecificOutput"]["additionalContext"]
        self.assertIn("analysis/a", context)
        self.assertIn("grants no permission", context)
        self.assertIsNone(self.say("let's talk about QC", "s2"))
        self.say("focus end")
        self.assertIsNone(self.say("let's talk about QC"))

    def test_context_line_joins_a_hint_not_an_approval(self):
        self.say("focus analysis/a")
        self.say("hints on")
        result = self.say("let's hand off now")
        self.assertTrue(result["systemMessage"].startswith("mycelium-extra hint"), result)  # the hint did fire
        extra = result["hookSpecificOutput"]["additionalContext"]
        self.assertIn("mycelium-extra focus: analysis/a", extra)
        self.assertIn("request fits", extra)

    def test_plan_option_needs_a_plan_that_names_the_folder(self):
        digest = self.approve()
        self.assertIn("no approved plan deadbeef", self.say("focus analysis/a plan deadbeef")["reason"])
        self.assertIn("names no path inside analysis/b", self.say("focus analysis/b plan " + digest)["reason"])
        self.assertFalse(os.path.isdir(os.path.join(self.root, ".mycelium-extra", "focus")))
        self.say("focus analysis/a plan " + digest)
        episode = self.record()["episodes"][0]
        self.assertEqual((episode["original_plan_hash"], episode["plan_selection"]), (digest, "explicit"))
        self.assertIn("original {} (selected)".format(digest), self.text(self.say("focus status")))

    def test_a_focus_command_changes_no_approval_state(self):
        digest = self.approve()
        folder = os.path.join(self.root, ".mycelium-extra", "approvals")
        before = {n: self.slurp(folder, n) for n in os.listdir(folder)}
        self.say("focus analysis/a plan " + digest)
        self.say("focus switch analysis/b")
        self.say("focus end")
        after = {n: self.slurp(folder, n) for n in os.listdir(folder)}
        self.assertEqual(before, after)

    def test_malformed_record_is_reported_not_repaired(self):
        self.say("focus analysis/a")
        path = os.path.join(self.root, ".mycelium-extra", "focus", "s1.json")
        data = self.record()
        data["episodes"].append(dict(data["episodes"][0], focus_id="second"))  # two open episodes
        with open(path, "w") as handle:
            json.dump(data, handle)
        before = self.slurp(path)
        self.assertIn("more than one open episode", self.say("focus status")["reason"])
        self.assertIn("more than one open episode", self.say("focus switch analysis/b")["reason"])
        self.assertIsNone(self.say("an ordinary prompt"))  # a bad record never blocks a prompt
        self.assertEqual(before, self.slurp(path))
        with open(path, "w") as handle:
            handle.write("{not json")
        self.assertIn("malformed", self.say("focus status")["reason"])

    def test_a_crashed_session_leaves_no_focus_for_the_next_one(self):  # F06 crash case
        self.say("focus analysis/a", "old")
        self.assertIsNone(self.say("hello", "new"))
        self.assertIn("focus none", self.text(self.say("focus status", "new")))

    def test_any_gated_root_works_not_only_analysis(self):  # real repos keep analyses under nbs/
        os.makedirs(os.path.join(self.root, "nbs", "09_factorizations"))
        self.assertIn("focus started on nbs/09_factorizations", self.text(self.say("focus nbs/09_factorizations.")))
        self.assertIn("focus nbs/09_factorizations", self.text(self.say("focus status")))
        self.assertIn("(was nbs/09_factorizations)", self.text(self.say("focus switch analysis/a")))
        for outside in ("src/tools", "notes/x", ".mycelium-extra/focus", "README.md/x"):
            result = self.say("focus switch " + outside)
            self.assertIn("no focus", result["reason"], outside)
        self.assertIn("not under a gated folder (analysis/, nbs/)", self.say("focus switch src/tools")["reason"])

    def test_gated_roots_follow_gate_json(self):
        os.makedirs(os.path.join(self.root, "work", "a"))
        with open(os.path.join(self.root, ".mycelium-extra", "gate.json"), "w") as handle:
            json.dump({"gated_paths": ["work/**"]}, handle)
        self.assertIn("started on work/a", self.text(self.say("focus work/a")))
        self.assertIn("not under a gated folder (work/)", self.say("focus switch analysis/a")["reason"])

    def test_a_busy_lock_is_a_message_and_changes_nothing(self):
        import fcntl
        folder = os.path.join(self.root, ".mycelium-extra", "locks")
        os.makedirs(folder)
        fd = os.open(os.path.join(folder, "focus-s1.lock"), os.O_CREAT | os.O_RDWR, 0o600)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX)  # another process holds the focus record
        result = self.say("focus analysis/a")
        self.assertEqual(result["decision"], "block")
        self.assertIn("could not lock the focus record", result["reason"])
        self.assertFalse(os.path.exists(os.path.join(self.root, ".mycelium-extra", "focus", "s1.json")))

    def test_runs_row_asks_the_gates_question_not_just_whether_a_plan_names_the_folder(self):
        choice_only = ("## Plan\n| # | Step | Choice | Source | Validation |\n|---|---|---|---|---|\n"
                       "| 1 | run the fit | uses `analysis/a/run.py` | user | ok |\n\nPlan status: READY")
        self.approve_text(choice_only)
        self.say("focus analysis/a")
        card = self.text(self.say("focus status"))
        self.assertIn("only outside its Step column, which grants nothing", card)
        self.assertNotIn("is active in this session", card)

    def test_a_parent_folder_in_a_step_cell_covers_a_nested_focus(self):
        parent = ("## Plan\n| # | Step | Choice | Source | Validation |\n|---|---|---|---|---|\n"
                  "| 1 | run every script under `analysis/a/` | x | user | ok |\n\nPlan status: READY")
        self.approve_text(parent)
        os.makedirs(os.path.join(self.root, "analysis", "a", "sub"))
        self.say("focus analysis/a/sub")
        self.assertIn("steps name paths in or above this folder is active in this session", self.text(self.say("focus status")))

    def test_two_session_ids_that_sanitise_alike_do_not_collide(self):
        self.say("focus analysis/a", "x/y")
        self.assertIn("focus started on analysis/b", self.text(self.say("focus analysis/b", "x_y")))
        self.assertEqual(len(os.listdir(os.path.join(self.root, ".mycelium-extra", "focus"))), 2)
        before = sorted(os.path.join(d, f) for d, _, fs in os.walk(self.root) for f in fs)
        os.makedirs(os.path.join(self.root, "nbs", "t1"))
        out = subprocess.run([sys.executable, os.path.join(HERE, "..", "focus.py"), "list", "--repo", self.root],
                             stdout=subprocess.PIPE, universal_newlines=True).stdout
        self.assertEqual(out.split(), ["analysis/a", "analysis/b", "nbs/t1"])
        self.assertEqual(sorted(os.path.join(d, f) for d, _, fs in os.walk(self.root) for f in fs), before)  # no file written
        refused = subprocess.run([sys.executable, os.path.join(HERE, "..", "focus.py"), "start", "analysis/a"],
                                 stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(refused.returncode, 2)  # no command line can change a focus


if __name__ == "__main__":
    unittest.main()
