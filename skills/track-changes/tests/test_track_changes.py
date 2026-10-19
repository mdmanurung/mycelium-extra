"""Run: python3 skills/track-changes/tests/test_track_changes.py

Approvals, re-pins and receipts come from the real gate hooks; the collector then reads them. Case names carry
the acceptance IDs of docs/roadmap/10-focus-track-changes.md."""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
SCRIPT = os.path.join(PLUGIN, "skills", "track-changes", "scripts", "track_changes.py")
GATE = os.path.join(PLUGIN, "hooks", "gate.py")
sys.path.insert(0, os.path.join(PLUGIN, "hooks"))
sys.dont_write_bytecode = True

spec = importlib.util.spec_from_file_location("track_changes_under_test", SCRIPT)
tc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tc)
FIT = "analysis/a/scripts/01_fit.py"
PLOT = "analysis/a/scripts/02_plot.py"


def plan(choice, *extra, outputs="analysis/a/outputs/"):
    steps = ["run `{}`".format(FIT)] + list(extra)
    rows = ["| {} | {} | {} | user | ok |".format(i + 1, step, choice if i == 0 else "x") for i, step in enumerate(steps)]
    return "\n".join(["**Objective.** Fit the model.", "", "Outputs: " + outputs, "",
                      "| # | Step | Choice | Source | Validation |", "|---|---|---|---|---|"] + rows + ["", "Plan status: READY"])


class Base(unittest.TestCase):
    def setUp(self):
        saved = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(saved)))
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        os.environ["HOME"] = home
        os.environ["CLAUDE_CODE_SESSION_ID"] = "s1"  # the session the hooks below act as
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, ".mycelium-extra"))
        self.write(".mycelium-extra/gate.json", "{}")
        self.write(FIT, "min_cells = 500\n", mtime=time.time() - 3600)
        self.write("analysis/a/A.md", "Objective: Characterize interferon response.\n")
        os.makedirs(os.path.join(self.root, "analysis", "b"))
        self.calls = 0

    def write(self, rel, text, mtime=None):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write(text)
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def hook(self, event, payload, session="s1"):
        payload = dict(payload, session_id=session, cwd=self.root)
        proc = subprocess.run([sys.executable, GATE, event], input=json.dumps(payload).encode("utf-8"),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout.decode("utf-8")) if proc.stdout.strip() else None

    def approve(self, text):
        notice = self.hook("stop", {"last_assistant_message": text})["systemMessage"]
        digest = notice.split("approve plan ")[1][:8]
        self.hook("prompt", {"prompt": "approve plan " + digest})
        return digest

    def run_cmd(self, command, code=0, pre=True):
        self.calls += 1
        call = "toolu_{}".format(self.calls)
        if pre:
            reply = self.hook("tool", {"tool_name": "Bash", "tool_input": {"command": command}, "tool_use_id": call})
            self.assertNotEqual(((reply or {}).get("hookSpecificOutput") or {}).get("permissionDecision"), "deny", reply)
        event = {"tool_name": "Bash", "tool_input": {"command": command}, "tool_response": {"stdout": "", "exit_code": code}}
        if pre:
            event["tool_use_id"] = call
        self.hook("post", event)

    def cli(self, *args, fail=False, env=None):
        with open(SCRIPT) as source:
            proc = subprocess.run([sys.executable, "-", "--plugin-root", PLUGIN, "--repo", self.root] + list(args),
                                  stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.root,
                                  universal_newlines=True, env=env)
        if fail:
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            return proc.stderr
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def collect(self, **kw):
        args = argparse.Namespace(repo=self.root, analysis=kw.get("analysis"), original=kw.get("original"),
                                  current=kw.get("current"), transcript=kw.get("transcript"), session=kw.get("session"))
        gate, focus, verify = tc.load(PLUGIN)
        return tc.collect(args, gate, focus, verify)

    def items(self, data, kind=None):
        return [i for i in data["items"] if kind is None or i["kind"] == kind]

    def two_plans(self):
        """Original plan runs FIT once; FIT is edited (500 -> 200); an amended plan naming 200 is approved."""
        first = self.approve(plan("min_cells 500"))
        self.run_cmd("python " + FIT)
        self.write(FIT, "min_cells = 200\n", mtime=time.time() - 1800)
        second = self.approve(plan("min_cells 200", outputs="analysis/a/outputs2/"))
        return first, second

    def tree(self):
        found = {}
        top = os.path.join(self.root, ".mycelium-extra")
        for folder, dirs, files in os.walk(top):
            if os.path.join("", "track-changes") in folder.replace(top, ""):
                continue
            for name in files:
                path = os.path.join(folder, name)
                with open(path, "rb") as handle:
                    found[os.path.relpath(path, top)] = hashlib.sha256(handle.read()).hexdigest()
        return found


class PlansAndCodeTest(Base):
    def test_two_plans_name_the_folder_so_the_original_must_be_chosen(self):  # F10
        first, second = self.two_plans()
        message = self.cli("--analysis", "analysis/a", fail=True)
        self.assertIn(first, message)
        self.assertIn(second, message)
        self.assertIn("--original", message)
        self.assertFalse(os.path.isdir(os.path.join(self.root, ".mycelium-extra", "track-changes")))
        self.assertIn("no approved plan deadbeef", self.cli("--analysis", "analysis/a", "--original", "deadbeef", fail=True))
        self.assertRegex(message, r"{} \(approved \d\d-\d\d \d\d:\d\d; Fit the model".format(second))

    def test_a_long_list_of_candidate_plans_is_capped(self):  # F10
        for i in range(10):
            self.approve(plan("min_cells {}".format(100 + i)))
        message = self.cli("--analysis", "analysis/a", fail=True)
        self.assertIn("10 approved plans name paths inside analysis/a", message)
        self.assertIn("and 2 more (`verify list` shows them all)", message)
        self.assertEqual(message.count("(approved "), 8)

    def test_a_later_approved_amendment_is_not_called_unauthorized(self):  # F09
        first, second = self.two_plans()
        data = self.collect(analysis="analysis/a", original=first)
        self.assertEqual((data["baselines"]["original_plan"], data["baselines"]["current_plan"], data["baselines"]["relation"]),
                         (first, second, "explicit"))
        plan_item = [i for i in self.items(data, "plan") if "Choice" in i["title"] or "choice" in i["title"]][0]
        self.assertEqual((plan_item["authorization_relation"], plan_item["historical"]), ("covered_current", "different_original"))
        self.assertIn("500", plan_item["title"])
        self.assertIn("200", plan_item["title"])
        self.assertIn("later authorized revision", plan_item["authorization"])
        self.assertNotIn("unauthorized", json.dumps(data).lower().replace("not unauthorized", ""))

    def test_edit_after_the_current_approval_is_unfrozen_with_a_diff(self):
        first, second = self.two_plans()
        self.write(FIT, "min_cells = 50\nalpha = 0.01\n", mtime=time.time())
        data = self.collect(analysis="analysis/a", original=first)
        code = self.items(data, "code")[0]
        self.assertEqual((code["bucket"], code["authorization_relation"], code["difference"]), ("attention", "not_established", "observed"))
        self.assertIn("edited since approval " + second, code["title"])
        self.assertEqual(code["historical"], "different_original")
        self.assertTrue(any(d[0] == "add" and "alpha" in d[1] for d in code["diff"]))
        self.assertTrue(any(d[0] == "del" and "500" in d[1] for d in code["diff"]))  # against the ORIGINAL pin
        self.assertIn("Potential analytical implication", code["potential"])  # 50 and 0.01 are not in the plan
        self.assertEqual(code["consequence"], "potential")
        self.assertIn("freeze " + second, " ".join(code["next"]))

    def test_a_change_whose_numbers_the_plan_already_holds_claims_no_implication(self):  # F11
        first, second = self.two_plans()
        data = self.collect(analysis="analysis/a", original=first)
        code = self.items(data, "code")[0]
        self.assertEqual(code["bucket"], "authorized")  # 200 is in the amended plan and frozen into it
        self.assertEqual(code["potential"], "")
        self.assertEqual(code["authorization_relation"], "covered_current")

    def test_repin_count_and_no_invented_baseline(self):  # F08, F20
        first, second = self.two_plans()
        self.write(PLOT, "print(1)\n", mtime=time.time() - 100)
        third = self.approve(plan("min_cells 200", "run `{}`".format(PLOT), outputs="analysis/a/outputs3/"))
        self.write(PLOT, "print(2)\n", mtime=time.time())
        self.run_cmd("python " + PLOT)  # a run after the edit re-pins it as working code
        data = self.collect(analysis="analysis/a", original=first, current=third)
        item = [i for i in self.items(data, "code") if i["file"] == PLOT][0]
        self.assertIn("re-pinned 1x since approval", item["unknown"])
        self.assertIn("not available (script absent from the original approval)", item["baseline"])
        self.assertEqual(item["historical"], "no_baseline")

    def test_missing_snapshot_is_unavailable_not_fabricated(self):  # F08
        first, second = self.two_plans()
        shutil.rmtree(os.path.join(self.root, ".mycelium-extra", "scripts"))
        self.write(FIT, "min_cells = 7\n", mtime=time.time())
        data = self.collect(analysis="analysis/a", original=first)
        code = self.items(data, "code")[0]
        self.assertEqual((code["difference"], code["diff"]), ("unavailable", []))
        self.assertIn("no line diff exists", code["observed"])
        self.assertTrue(any("no kept baseline snapshot" in l for l in data["coverage"]["limitations"]))

    def test_secret_like_strings_never_reach_any_artifact(self):  # F24
        first, second = self.two_plans()
        secret = "sk-abcdefghijklmnopqrstuvwxyz0123"
        self.write(FIT, 'min_cells = 200\nAPI_KEY = "{}"\npassword = hunter2xyz\n'.format(secret), mtime=time.time())
        out = self.cli("--analysis", "analysis/a", "--original", first)
        folder = os.path.join(self.root, ".mycelium-extra", "track-changes", "analysis-a")
        blob = out
        for name in ("snapshot.json", "brief.md", "report.html"):
            with open(os.path.join(folder, name)) as handle:
                blob += handle.read()
        self.assertNotIn(secret, blob)
        self.assertNotIn("hunter2xyz", blob)
        self.assertIn("[redacted]", blob)
        self.assertIn("replaced with [redacted]", blob)


class ExecutionAndOutputsTest(Base):
    def test_failed_then_successful_retry_keeps_both(self):  # F17
        digest = self.approve(plan("min_cells 500"))
        self.run_cmd("python " + FIT, code=1)
        self.run_cmd("python " + FIT, code=0)
        item = self.items(self.collect(analysis="analysis/a"), "execution")[0]
        self.assertEqual(item["bucket"], "attention")
        self.assertIn("exited 1; a later run of the same path", item["observed"])
        self.assertIn("(both kept)", item["observed"])
        self.assertIn("2 run(s), 1 failed", item["title"])

    def test_unmatched_launch_and_sbatch_claim_nothing_about_completion(self):  # F18, F19
        digest = self.approve(plan("min_cells 500"))
        self.run_cmd("python " + FIT, pre=False)  # no Pre: the gate never saw the launch
        with open(os.path.join(self.root, ".mycelium-extra", "receipts.jsonl"), "a") as handle:
            handle.write(json.dumps({"ts": time.time(), "plans": [digest], "kind": "sbatch", "paths": [FIT], "exit_status": "unknown",
                                     "launch_match": "matched", "explore": False}) + "\n")
        item = self.items(self.collect(analysis="analysis/a"), "execution")[0]
        self.assertEqual(item["bucket"], "attention")
        self.assertIn("Execution evidence gap", item["summary"])
        self.assertIn("1 sbatch submission(s) show submission only, not that the job finished", item["unknown"])
        self.assertIn("1 run(s) had no matched launch record", item["unknown"])
        self.assertNotIn("verified", json.dumps(item).lower())

    def test_outputs_older_than_the_code_are_flagged_never_called_current(self):
        first, second = self.two_plans()
        self.write("analysis/a/outputs2/result.tsv", "x\n", mtime=time.time() - 7200)
        self.write(FIT, "min_cells = 200\n# touched\n", mtime=time.time())
        self.write("analysis/a/outputs2/result.tsv", "x\n", mtime=time.time() - 7200)
        plan_text = plan("min_cells 200", outputs="analysis/a/outputs2/result.tsv")
        third = self.approve(plan_text)
        self.write(FIT, "min_cells = 201\n", mtime=time.time())
        self.write("analysis/a/outputs2/result.tsv", "x\n", mtime=time.time() - 7200)
        data = self.collect(analysis="analysis/a", original=first, current=third)
        out = self.items(data, "output")
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0]["currency"], out[0]["bucket"]), ("older_than_change", "attention"))
        self.assertIn("modification time", out[0]["unknown"])


class FocusAndTranscriptTest(Base):
    def transcript(self, lines):
        path = os.path.join(self.root, "session.jsonl")
        with open(path, "w") as handle:
            for line in lines:
                handle.write((line if isinstance(line, str) else json.dumps(line)) + "\n")
        return path

    def tool(self, name, side=False, **inp):
        return {"type": "assistant", "isSidechain": side, "timestamp": tc.iso(time.time() + 20),
                "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]}}

    def focused(self, lines):
        path = self.transcript(lines)
        self.hook("prompt", {"prompt": "focus analysis/a", "transcript_path": path})
        return path

    def test_direct_edit_to_another_analysis_is_shown_with_its_uncertainty(self):  # F14, F13, F15, F16, F24
        secret = "hunter2-do-not-copy"
        self.focused([
            {"type": "user", "timestamp": tc.iso(time.time() + 1), "message": {"content": "my key is " + secret}},
            self.tool("Edit", file_path=os.path.join(self.root, "analysis/b/model.py")),
            self.tool("Write", side=True, file_path=os.path.join(self.root, "analysis/b/extra.py")),
            self.tool("Edit", file_path=os.path.join(self.root, FIT)),
            self.tool("Edit", file_path=os.path.join(self.root, "tools/helper.py")),
            self.tool("Bash", command="python analysis/b/model.py --token " + secret),
            "{not json at all tool_use",
        ])
        data = self.collect()
        self.assertEqual(data["analysis_path"], "analysis/a")
        far = [i for i in self.items(data, "focus") if i["file"].startswith("analysis/b")][0]
        self.assertEqual((far["bucket"], far["focus_relation"], far["semantic_relation"]), ("attention", "outside_path", "unassessed"))
        self.assertEqual(far["attribution"], "contextual")  # one of the two edits came from a subagent
        self.assertIn("Relationship to current focus not established", far["summary"])
        self.assertIn("may be a supporting dependency", far["unknown"])
        shared = [i for i in self.items(data, "focus") if i["bucket"] == "routine"][0]
        self.assertEqual(shared["focus_relation"], "unknown")
        self.assertFalse([i for i in data["items"] if FIT in i["file"] and i["kind"] == "focus"])  # inside the focus: not drift
        self.assertEqual(data["coverage"]["claude_transcript"], "partial")
        self.assertIn("`focus switch analysis/b`", tc.card(data).splitlines()[-1])  # the target, not a word of the title
        self.assertTrue(any("shell commands mention other analyses (analysis/b x1)" in l for l in data["coverage"]["limitations"]))
        self.assertNotIn(secret, json.dumps(data))  # no prompt or command text is kept

    def test_siblings_under_nbs_are_other_analyses_too(self):  # real repos keep analyses under nbs/
        for name in ("topic_a", "topic_b"):
            os.makedirs(os.path.join(self.root, "nbs", name))
        path = self.transcript([
            self.tool("Edit", file_path=os.path.join(self.root, "nbs/topic_b/fit.py")),
            self.tool("Edit", file_path=os.path.join(self.root, "nbs/topic_a/inside.py")),
            self.tool("Edit", file_path=os.path.join(self.root, "analysis/a/elsewhere.py")),
            self.tool("Bash", command="python nbs/topic_b/fit.py"),
        ])
        self.hook("prompt", {"prompt": "focus nbs/topic_a", "transcript_path": path})
        data = self.collect()
        self.assertEqual(data["analysis_path"], "nbs/topic_a")
        far = [i for i in self.items(data, "focus") if i["bucket"] == "attention"]
        self.assertEqual([i["target"] for i in far], ["nbs/topic_b"])
        self.assertIn("`focus switch nbs/topic_b`", tc.card(data).splitlines()[-1])
        shared = [i for i in self.items(data, "focus") if i["bucket"] == "routine"][0]
        self.assertIn("outside nbs/ during the focus", shared["title"])
        self.assertTrue(any("nbs/topic_b x1" in l for l in data["coverage"]["limitations"]))

    def test_edits_before_the_focus_started_are_not_counted(self):
        old = self.tool("Edit", file_path=os.path.join(self.root, "analysis/b/old.py"))
        old["timestamp"] = tc.iso(time.time() - 3600)
        self.focused([old])
        self.assertEqual(self.items(self.collect(), "focus"), [])

    def test_a_large_transcript_is_read_in_part_and_says_so(self):  # F22
        lines = [self.tool("Edit", file_path=os.path.join(self.root, "analysis/b/m{}.py".format(i))) for i in range(400)]
        self.focused(lines)
        tc.CAP_TRANSCRIPT_BYTES, saved = 20000, tc.CAP_TRANSCRIPT_BYTES
        self.addCleanup(setattr, tc, "CAP_TRANSCRIPT_BYTES", saved)
        data = self.collect()
        self.assertEqual(data["coverage"]["claude_transcript"], "partial")
        self.assertIn("only the last 19 KB of the transcript was read", data["coverage"]["transcript_note"])
        self.assertLess(len(self.items(data, "focus")[0]["evidence"]), 400)  # a part of the edits, not all of them

    def test_no_observation_is_not_reported_as_staying_on_task(self):  # F30
        self.hook("prompt", {"prompt": "focus analysis/a"})
        data = self.collect()
        self.assertEqual(data["items"], [])
        text = tc.card(data) + tc.brief(data)
        self.assertIn("Unknown", tc.card(data))
        self.assertIn("shell-made edits", text)
        self.assertNotRegex(text.lower(), r"on task|stayed focused|no drift|no issues")

    def test_item_ids_survive_a_regeneration(self):
        first, second = self.two_plans()
        a = self.collect(analysis="analysis/a", original=first)
        time.sleep(1.1)
        b = self.collect(analysis="analysis/a", original=first)
        self.assertNotEqual(a["generated_at"], b["generated_at"])
        self.assertEqual([i["id"] for i in a["items"]], [i["id"] for i in b["items"]])


class SafetyTest(Base):
    def test_the_report_changes_nothing_but_its_own_folder(self):  # F25
        first, second = self.two_plans()
        self.hook("prompt", {"prompt": "focus analysis/a"})
        before = self.tree()
        mtimes = {p: os.path.getmtime(os.path.join(self.root, ".mycelium-extra", p)) for p in before}
        scripts = os.path.getmtime(os.path.join(self.root, FIT))
        self.cli("--original", first)
        self.assertEqual(self.tree(), before)
        self.assertEqual({p: os.path.getmtime(os.path.join(self.root, ".mycelium-extra", p)) for p in before}, mtimes)
        self.assertEqual(os.path.getmtime(os.path.join(self.root, FIT)), scripts)
        folder = os.path.join(self.root, ".mycelium-extra", "track-changes", "analysis-a")
        self.assertEqual(sorted(os.listdir(folder)), ["brief.md", "report.html", "snapshot.json"])
        self.assertTrue(all(oct(os.stat(os.path.join(folder, n)).st_mode & 0o777) == "0o600" for n in os.listdir(folder)))

    def test_a_linked_output_folder_is_refused(self):
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside)
        os.symlink(outside, os.path.join(self.root, ".mycelium-extra", "track-changes"))
        self.assertIn("refusing to write", self.cli("--analysis", "analysis/a", fail=True))
        self.assertEqual(os.listdir(outside), [])

    def test_html_is_inert_for_hostile_values(self):  # F23, F29
        evil = "</script><img src=x onerror=alert(1)> \"'&"
        first = self.approve(plan("min_cells 500"))
        self.write(FIT, "min_cells = 500\n", mtime=time.time() - 3600)
        second = self.approve(plan(evil, outputs="analysis/a/outputs2/"))
        self.cli("--analysis", "analysis/a", "--original", first)
        with open(os.path.join(self.root, ".mycelium-extra", "track-changes", "analysis-a", "report.html"), encoding="utf-8") as handle:
            page = handle.read()
        self.assertEqual(page.count("</script>"), 2)  # the data block and the viewer: nothing inside a value can end one
        self.assertNotIn("<img", page)
        payload = re.search(r'<script type="application/json" id="data">(.*?)</script>', page, re.S).group(1)
        data = json.loads(payload)
        self.assertTrue(any("</script>" in i["observed"] for i in data["items"]))  # the value survives, as text
        self.assertIn("Content-Security-Policy", page)
        for banned in ("innerHTML", "eval(", "fetch(", "XMLHttpRequest", "http://", "https://", "outerHTML", "document.write"):
            self.assertNotIn(banned, page)

    def test_embedded_data_escapes_line_separators_and_markup(self):  # F23
        render = tc.load_render(PLUGIN)
        hostile = "</script><!-- \u2028 \u2029 \"' & <b>"
        data = {"analysis_path": hostile, "items": [{"title": hostile}], "evidence": [], "timeline": [], "counts": {}}
        page = render.render(data, "brief " + hostile)
        self.assertEqual(page.count("</script>"), 2)
        payload = page.split('id="data">')[1].split("</script>")[0]
        for raw in ("<!--", "\u2028", "\u2029", "<b>"):
            self.assertNotIn(raw, payload)
        self.assertEqual(json.loads(payload)["items"][0]["title"], hostile)  # and it decodes back exactly

    def test_viewer_runs_and_every_control_clicks(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        first, second = self.two_plans()
        self.write(FIT, "min_cells = 50\nalpha = 0.01\n", mtime=time.time())
        self.cli("--analysis", "analysis/a", "--original", first)
        page = os.path.join(self.root, ".mycelium-extra", "track-changes", "analysis-a", "report.html")
        proc = subprocess.run([node, os.path.join(HERE, "viewer_smoke.js"), page], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("OK clicks=", proc.stdout)

    def test_viewer_script_parses(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        js = os.path.join(PLUGIN, "skills", "track-changes", "assets", "viewer.js")
        proc = subprocess.run([node, "--check", js], stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_no_focus_needs_an_explicit_analysis_when_several_exist(self):  # F32
        message = self.cli(fail=True)
        self.assertIn("pass --analysis <folder>", message)
        self.assertIn("analysis/a", message)
        self.assertIn("Attention", self.cli("--analysis", "analysis/a", "--no-write"))

    def test_unsafe_analysis_path_is_refused(self):  # F07
        for bad in ("analysis/../etc", "/etc", "analysis/nope"):
            self.assertIn("no focus", self.cli("--analysis", bad, fail=True))

    def test_each_session_uses_only_its_own_focus(self):  # F03
        self.hook("prompt", {"prompt": "focus analysis/a"}, "s1")
        self.hook("prompt", {"prompt": "focus analysis/b"}, "s2")
        self.assertIn("track-changes analysis/a", self.cli("--no-write"))  # $CLAUDE_CODE_SESSION_ID is s1
        self.assertIn("track-changes analysis/b", self.cli("--session", "s2", "--no-write"))
        bare = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_SESSION_ID"}
        message = self.cli("--no-write", fail=True, env=bare)
        self.assertIn("no session id", message)
        self.assertIn("pass --analysis", message)

    def test_a_focus_left_open_by_an_earlier_session_is_not_this_sessions(self):  # F06
        self.hook("prompt", {"prompt": "focus analysis/b"}, "old-session")  # never ended
        message = self.cli(fail=True)  # this session (s1) has no focus
        self.assertIn("this session has no open focus", message)
        data = self.collect(analysis="analysis/a")
        self.assertFalse(data["focus"]["active_at_snapshot"])
        self.assertEqual(data["coverage"]["claude_transcript"], "not_requested")
        self.assertFalse(self.collect(analysis="analysis/b")["focus"]["active_at_snapshot"])  # old-session's focus is not s1's

    def test_without_a_gate_it_still_reports_what_it_cannot_read(self):  # F26
        bare = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, bare)
        os.makedirs(os.path.join(bare, "analysis", "x"))
        with open(SCRIPT) as source:
            proc = subprocess.run([sys.executable, "-", "--plugin-root", PLUGIN, "--repo", bare, "--analysis", "analysis/x",
                                   "--no-write", "--json"], stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  cwd=bare, universal_newlines=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertTrue(any("no .mycelium-extra/gate.json" in l for l in data["coverage"]["limitations"]))
        self.assertEqual(data["coverage"]["mycelium"], "absent")

    def test_card_shape(self):
        first, second = self.two_plans()
        card = self.cli("--analysis", "analysis/a", "--original", first)
        lines = card.splitlines()
        self.assertTrue(lines[0].startswith("mycelium-extra · track-changes analysis/a · snapshot "))
        self.assertTrue(lines[1].startswith("Baseline   original {} · current {}".format(first, second)))
        self.assertTrue(any(l.startswith("Attention  ") for l in lines))
        self.assertTrue(any(l.startswith("Unknown    ") for l in lines))
        self.assertTrue(any(l.startswith("▶ ") for l in lines))
        self.assertIn("(newest approved plan naming this folder; --current to choose)", lines[1])
        explicit = self.cli("--analysis", "analysis/a", "--original", first, "--current", second, "--no-write")
        self.assertNotIn("--current to choose", explicit)


if __name__ == "__main__":
    unittest.main()
