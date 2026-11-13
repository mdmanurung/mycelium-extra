"""Run: python3 hooks/tests/test_whereami.py

`where` (hooks/whereami.py): the ADHD card for one analysis, read from files, plus the typed word through the gate."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
GATE = os.path.join(HERE, "..", "gate.py")

import whereami as wh  # noqa: E402

DOC = "# demo\n\n## Objective\n\nGive each cell a timepoint from its own donor's hashtags.\n"
TRACKER = ("| ID | Item | Status | Depends on | Verify |\n|---|---|---|---|---|\n"
           "| T1 | check the 03 figure | todo | | |\n| T2 | fill claim | in progress | | |\n"
           "| T3 | old thing | done | | |\n")


def touch(path, text="x", mtime=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(text)
    if mtime is not None:
        os.utime(path, (mtime, mtime))


class WhereTest(unittest.TestCase):
    def setUp(self):
        saved = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(saved)))
        self.root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, ".mycelium-extra"))
        self.rel = "analysis/demo"
        self.folder = os.path.join(self.root, self.rel)
        self.t0 = time.time() - 7200
        for n, name in enumerate(("01_prep.R", "02_fit.py", "03_show.R")):
            touch(self.p("code", name), mtime=self.t0 + n)
        touch(self.p("DEMO.md"), DOC)
        self.snake(("01_prep", "02_fit", "03_show"))

    def snake(self, stems):
        touch(self.p("Snakefile"), "".join('rule r{0}:\n    output: "outputs/{0}/{0}.tsv"\n'.format(t) for t in stems))

    def p(self, *parts):
        return os.path.join(self.folder, *parts)

    def run_step(self, stem, mtime, benchmark=None):
        touch(self.p("outputs", stem, stem + ".tsv"), mtime=mtime)
        if benchmark is not None:
            touch(self.p("outputs", stem, "logs", stem + ".benchmark.tsv"), "s\th:m:s\n{}\t0:01:00\n".format(benchmark),
                  mtime=mtime)

    def run_all(self):
        for n, stem in enumerate(("01_prep", "02_fit", "03_show")):
            self.run_step(stem, self.t0 + 100 + n, benchmark=120)

    def verified(self, when, cell=None, folder=None):
        """Write provenance/PROVENANCE.md the way verify does, with the Verified cell at `when`."""
        stamp = cell or time.strftime("%Y-%m-%d %H:%M", time.localtime(when))
        header = ("# Provenance\n\nText.\n\n| Plan | Approved | Verified | Status | Files |\n|---|---|---|---|---|\n"
                  "| aaaa | 2026-10-01 09:00 | 2026-10-01 10:00 | pass | [plan](x) |\n"
                  "| bbbb | 2026-10-02 09:00 | {} | pass | [plan](y) |\n").format(stamp)
        touch(os.path.join(folder or self.folder, "provenance", "PROVENANCE.md"), header)

    def card(self, mode=None):
        return wh.answer(self.root, self.folder, mode, write=False)

    def test_fresh_scaffold_with_marker_shows_all_steps_not_run(self):
        touch(self.p("outputs", ".layout"), "layout: steps\nversion: 1\n")
        touch(self.p("outputs", ".gitkeep"), "")
        card = self.card()
        self.assertIn("  [ ] 01_prep\n  [ ] 02_fit\n  [ ] 03_show", card)
        self.assertIn("1. bash run.sh", card)

    def test_not_run_shows_all_todo_and_bash_run(self):
        card = self.card()
        self.assertTrue(card.startswith("WHERE YOU ARE: demo\n"))
        self.assertIn("AIM\n  Give each cell a timepoint", card)
        self.assertIn("  [ ] 01_prep\n  [ ] 02_fit\n  [ ] 03_show", card)
        self.assertIn("1. bash run.sh", card)
        self.assertIn("(time unknown)", card)

    def test_all_current_uses_tracker_then_verify(self):
        self.run_all()
        touch(self.p("plans", "TRACKER.md"), TRACKER)
        card = self.card()
        self.assertIn("3 of 3 steps current.", card)
        self.assertIn("  [x] 03_show", card)
        self.assertIn("1. T1: check the 03 figure", card)
        self.assertIn("LATER\n  - T2: fill claim", card)
        self.assertNotIn("T3", card)
        os.remove(self.p("plans", "TRACKER.md"))
        self.assertIn("1. Run /mycelium-extra:verify", self.card())
        os.makedirs(self.p("provenance"))
        self.assertIn("1. Run /mycelium-extra:verify", self.card())  # a folder alone is no record
        self.verified(time.time() - 60)
        self.assertIn("Nothing pending.", self.card())

    def test_edited_script_makes_it_and_later_steps_stale_with_minutes(self):
        self.run_all()
        touch(self.p("code", "02_fit.py"), "y", mtime=time.time() - 300)
        card = self.card()
        self.assertIn("  [x] 01_prep\n  [~] 02_fit\n  [~] 03_show", card)
        self.assertIn("02_fit.py changed 5 min ago. Stale: 02, 03.", card)
        self.assertIn("DO NEXT  (about 4 min)", card)  # two 120 s benchmarks
        self.assertIn("RIGHT NOW\n  Step 2 of 3. 1 of 3 steps current.", card)

    def test_failed_run_points_at_the_log(self):
        self.run_step("01_prep", self.t0 + 100, benchmark=1)
        touch(self.p("logs", "CHANGES.md"), "# Change log\n\n## 2026-11-12 22:13 abc1234 failed\ncode changed: none\n")
        card = self.card()
        self.assertIn("  [!] 02_fit", card)
        self.assertIn("1. Read outputs/02_fit/logs/02_fit.log\n  2. Fix the cause, then: bash run.sh", card)

    def test_watch_out_figure_without_source_data_and_empty_folder(self):
        self.run_all()
        touch(self.p("outputs", "03_show", "figures", "03_show.png"), mtime=self.t0 + 200)
        os.makedirs(self.p("outputs", "02_fit", "empty-check"))
        card = self.card()
        self.assertIn("WATCH OUT\n  - figure 03_show has no source data", card)
        touch(self.p("outputs", "03_show", "source_data", "03_show.tsv"), mtime=self.t0 + 200)
        self.assertNotIn("WATCH OUT", self.card())

    def test_lists_are_capped_at_five(self):
        rows = "".join("| T{0} | item {0} | todo | | |\n".format(i) for i in range(1, 10))
        touch(self.p("plans", "TRACKER.md"), TRACKER.split("| T1")[0] + rows)
        self.run_all()
        card = self.card()
        later = card.split("LATER\n")[1]
        self.assertIn("  - T6: item 6", later)  # T2..T6 are shown; T1 is in DO NEXT
        self.assertNotIn("T7", later)
        self.assertIn("  - +3 more", later)

    def test_verify_state_verified_changed_interrupted_never(self):
        self.run_all()
        now = time.time()
        self.assertEqual(wh.verify_state(self.folder, now)["line"], "Never verified.")
        card = self.card()
        self.assertIn("3 of 3 steps current.\n  No run log (logs/CHANGES.md).\n  Never verified.\n", card)
        self.assertIn("DO NEXT\n  1. Run /mycelium-extra:verify", card)
        self.assertNotIn("WATCH OUT", card)
        self.verified(now - 7200)
        for name in ("01_prep.R", "02_fit.py", "03_show.R"):
            os.utime(self.p("code", name), (now - 9000,) * 2)
        for stem in ("01_prep", "02_fit", "03_show"):
            for name in (stem + ".tsv", os.path.join("logs", stem + ".benchmark.tsv")):
                os.utime(self.p("outputs", stem, name), (now - 8000,) * 2)
        card = self.card()
        self.assertIn("  Verified 2 h ago.\n", card)
        self.assertIn("Nothing pending.", card)
        self.assertEqual(wh.verify_state(self.folder, now)["state"], "verified")
        touch(self.p("code", "helpers.R"), mtime=now - 300)  # code edited after verify
        state = wh.verify_state(self.folder, now)
        self.assertEqual((state["state"], state["changed"]), ("changed", "code"))
        card = self.card()
        self.assertIn("  Changed since verify: code, 5 min ago.\n", card)
        self.assertIn("1. Run /mycelium-extra:verify", card)
        self.assertIn("WATCH OUT\n  - Changed since verify: code, 5 min ago.", card)
        touch(self.p("outputs", "panels", "p.png"), mtime=now - 120)
        self.assertEqual(wh.verify_state(self.folder, now)["changed"], "outputs")
        touch(self.p("logs", "CHANGES.md"), "# Change log\n\n## {} abc1234 ok\n".format(
            time.strftime("%Y-%m-%d %H:%M", time.localtime(now - 30))))
        log = wh.verify_state(self.folder, now, log=wh.ap.last_change(self.folder))
        self.assertEqual(log["changed"], "log")
        touch(self.p("provenance", ".transactions", "pending.json"), "{}")
        card = self.card()
        self.assertIn("  Verify was interrupted.\n", card)
        self.assertIn("WATCH OUT\n  - Verify was interrupted.", card)
        self.assertIn("1. Run /mycelium-extra:verify", card)

    def test_verify_line_shows_failed_status_and_cut_walks(self):
        self.run_all()
        now = time.time()
        self.verified(now - 7200)
        for name in ("01_prep.R", "02_fit.py", "03_show.R"):
            os.utime(self.p("code", name), (now - 9000,) * 2)
        for stem in ("01_prep", "02_fit", "03_show"):
            for name in (stem + ".tsv", os.path.join("logs", stem + ".benchmark.tsv")):
                os.utime(self.p("outputs", stem, name), (now - 8000,) * 2)
        path = self.p("provenance", "PROVENANCE.md")
        with open(path) as handle:
            text = handle.read().replace("| pass | [plan](y)", "| DOES_NOT_CONFORM | [plan](y)")
        touch(path, text)
        state = wh.verify_state(self.folder, now)
        self.assertEqual((state["state"], state["line"]), ("nonconforming", "Verified 2 h ago: DOES_NOT_CONFORM."))
        self.assertIn("Run /mycelium-extra:verify", self.card())
        touch(path, text.replace("DOES_NOT_CONFORM", "CONFORMS"))
        budget = wh.Budget()
        budget.count = budget.cap  # the step walks used it up
        state = wh.verify_state(self.folder, now, budget)
        self.assertEqual(state["line"], "Verified 2 h ago; not every file was checked.")

    def test_verify_same_minute_counts_as_verified(self):
        self.run_all()
        minute = int(time.time() // 60) * 60 - 600
        self.verified(minute)
        touch(self.p("code", "03_show.R"), mtime=minute + 59)
        for stem in ("01_prep", "02_fit", "03_show"):
            for name in (stem + ".tsv", os.path.join("logs", stem + ".benchmark.tsv")):
                os.utime(self.p("outputs", stem, name), (minute,) * 2)
        self.assertEqual(wh.verify_state(self.folder, time.time())["state"], "verified")
        os.utime(self.p("code", "03_show.R"), (minute + 60,) * 2)
        self.assertEqual(wh.verify_state(self.folder, time.time())["state"], "changed")

    def test_root_level_provenance_file_is_ignored(self):
        self.run_all()
        self.verified(time.time(), folder=self.folder)
        os.rename(self.p("provenance", "PROVENANCE.md"), self.p("PROVENANCE.md"))
        os.rmdir(self.p("provenance"))
        self.assertEqual(wh.verify_state(self.folder, time.time())["line"], "Never verified.")

    def test_unparseable_verified_cell_says_record_unreadable(self):
        self.run_all()
        self.verified(0, cell="yesterday")
        card = self.card()
        self.assertIn("  Verify record unreadable.\n", card)
        self.assertIn("WATCH OUT\n  - Verify record unreadable.", card)

    def test_verify_line_in_short_card_and_legacy_layout(self):
        self.run_all()
        self.assertIn("STATE  3 of 3 steps current. Never verified.", self.card("short"))
        shutil.rmtree(self.p("outputs"))
        touch(self.p("outputs", "run_20261101_base", "RUN.txt"), "run: x\nkind: analysis\nstatus: done\n")
        touch(self.p("outputs", "run_20261101_base", "x.tsv"))
        card = self.card()
        self.assertIn("Old run-folder layout", card)
        self.assertIn("  Never verified.", card)
        self.assertNotIn("Run /mycelium-extra:verify", card)

    def test_where_all_skips_the_verify_walk(self):
        self.run_all()
        calls = []
        saved = wh.verify_state
        wh.verify_state = lambda *a, **k: calls.append(1) or saved(*a, **k)
        self.addCleanup(setattr, wh, "verify_state", saved)
        wh.render_all(self.root, None, self.folder)
        self.assertEqual(calls, [])

    def test_short_form_has_six_lines(self):
        self.run_all()
        lines = self.card("short").splitlines()
        self.assertEqual([l.split()[0] for l in lines[1:]], ["AIM", "STATE", "NEXT", "THEN", "BLOCK"])
        self.assertEqual(lines[0], "demo")

    def test_scaffold_placeholder_is_no_aim(self):
        touch(self.p("DEMO.md"), "# demo\n\n## Objective\n\n[What question does this analysis answer?]\n")
        self.assertIn("not written: open analysis/demo/DEMO.md", self.card())

    def test_legacy_run_folder_layout_has_no_step_marks(self):
        touch(self.p("outputs", "run_20261101_base", "RUN.txt"), "run: x\nkind: analysis\nstatus: done\n")
        touch(self.p("outputs", "run_20261101_base", "x.tsv"))
        card = self.card()
        self.assertIn("Old run-folder layout: no per-step state. Latest run: run_20261101_base (done).", card)
        self.assertIn("  - 01_prep", card)
        self.assertNotIn("bash run.sh", card)

    def test_no_analysis_here(self):
        other = os.path.join(self.root, "elsewhere")
        os.makedirs(other)
        self.assertIn("No analysis found here", wh.answer(self.root, other, None, write=False))

    def test_all_lists_one_line_per_analysis(self):
        self.run_all()
        touch(self.p("..", "second", "code", "01_a.R"))
        out = wh.answer(self.root, self.root, "all", write=False)
        self.assertTrue(out.startswith("ANALYSES"))
        self.assertEqual(len(out.splitlines()), 3)
        self.assertIn("demo", out)
        self.assertIn("not run", out)

    def test_now_file_is_written_once_atomically_and_no_write_skips_it(self):
        wh.answer(self.root, self.folder, None, write=False)
        self.assertFalse(os.path.exists(os.path.join(self.root, ".mycelium-extra", "now")))
        out = wh.answer(self.root, self.folder, "short")
        path = os.path.join(self.root, ".mycelium-extra", "now", "analysis__demo.md")
        self.assertIn("Saved: .mycelium-extra/now/analysis__demo.md", out)
        with open(path) as handle:
            body = handle.read()
        self.assertIn("WHERE YOU ARE: demo", body)  # NOW.md always holds the full card
        self.assertEqual(os.listdir(os.path.dirname(path)), ["analysis__demo.md"])

    def test_nothing_is_written_into_the_analysis_folder(self):
        before = sorted(os.path.join(h, n) for h, _, fs in os.walk(self.folder) for n in fs)
        wh.answer(self.root, self.folder, None)
        after = sorted(os.path.join(h, n) for h, _, fs in os.walk(self.folder) for n in fs)
        self.assertEqual(before, after)


    # --- review fixes: robust walks, failed step, state words, labels, discovery, tracker, gate errors

    def test_broken_symlink_and_vanished_file_do_not_break_the_card(self):
        self.run_all()
        os.symlink(self.p("nowhere"), self.p("outputs", "02_fit", "dangling"))
        os.utime(self.p("outputs", "02_fit", "dangling"), (self.t0, self.t0), follow_symlinks=False)
        os.symlink(self.p("nowhere"), self.p("code", "dangling.txt"))
        card = self.card()
        self.assertIn("3 of 3 steps current.", card)
        self.assertEqual(wh.mtime_or_zero(self.p("nowhere")), 0.0)
        self.assertTrue(wh.answer(self.root, self.root, "all", write=False).startswith("ANALYSES"))

    def test_file_cap_sets_truncated_and_prints_the_warning(self):
        self.run_all()
        for n in range(6):
            touch(self.p("outputs", "03_show", "f{}.tsv".format(n)), mtime=self.t0 + 100)
        f = wh.facts(self.root, self.rel, wh.Budget(30, 4))
        self.assertTrue(f["truncated"])
        self.assertEqual(f["watch"][0], "stopped counting at 4 files; state may be wrong")
        self.assertIn("WATCH OUT\n  - stopped counting at 4 files; state may be wrong", wh.render_card(f))
        self.assertFalse(wh.facts(self.root, self.rel)["truncated"])

    def test_deadline_stops_the_walk(self):
        self.run_all()
        budget = wh.Budget(0.0, 5000)
        time.sleep(0.01)
        self.assertTrue(wh.facts(self.root, self.rel, budget)["truncated"])

    def test_where_all_stops_scanning_and_says_so(self):
        self.run_all()
        touch(self.p("..", "second", "code", "01_a.R"))
        out = wh.render_all(self.root, None, self.root, wh.Budget(30, 0))
        self.assertIn("not scanned", out)
        many = self.root
        for n in range(9):
            touch(os.path.join(many, "analysis", "a{}".format(n), "code", "01_a.R"))
        self.assertIn("+3 not scanned", wh.render_all(self.root, None, self.root))

    def test_failed_step_is_the_one_with_only_a_log(self):
        self.run_step("01_prep", self.t0 + 100, benchmark=1)
        touch(self.p("outputs", "02_fit", "logs", "02_fit.log"), "Traceback", mtime=self.t0 + 110)
        touch(self.p("logs", "CHANGES.md"), "# Change log\n\n## 2026-11-12 22:13 abc1234 failed\n")
        card = self.card()
        self.assertIn("  [x] 01_prep\n  [!] 02_fit\n  [ ] 03_show", card)
        self.assertIn("1. Read outputs/02_fit/logs/02_fit.log", card)
        self.assertNotIn("empty output folder", card)
        self.assertIn("failed", wh.answer(self.root, self.root, "all", write=False))

    def test_failed_step_is_the_log_only_one_even_after_an_unrun_step(self):
        touch(self.p("outputs", "03_show", "logs", "03_show.log"), "Traceback", mtime=self.t0 + 110)
        touch(self.p("logs", "CHANGES.md"), "# Change log\n\n## 2026-11-12 22:13 abc1234 failed\n")
        card = self.card()
        self.assertIn("  [ ] 01_prep\n  [ ] 02_fit\n  [!] 03_show", card)
        self.assertIn("1. Read outputs/03_show/logs/03_show.log", card)

    def test_snakefile_is_read_once_per_card(self):
        touch(self.p("Snakefile"), "rule a:\n    output: 'outputs/01_prep/x'\n")
        reads = []
        real = wh.ap.read
        wh.ap.read = lambda path, *a, **k: (reads.append(path), real(path, *a, **k))[1]
        try:
            self.card()
        finally:
            wh.ap.read = real
        self.assertEqual(sum(1 for r in reads if r.endswith("Snakefile")), 1)

    def test_log_only_folder_is_not_output(self):
        touch(self.p("outputs", "01_prep", "logs", "01_prep.log"), mtime=self.t0 + 100)
        self.assertIn("  [ ] 01_prep", self.card())

    def test_partial_state_word(self):
        self.run_step("01_prep", self.t0 + 100, benchmark=1)
        self.assertEqual(wh.facts(self.root, self.rel)["state"], "partial")
        self.assertIn("partial", wh.answer(self.root, self.root, "all", write=False))

    def test_state_words(self):
        self.assertEqual(wh.facts(self.root, self.rel)["state"], "not run")
        self.run_all()
        self.assertEqual(wh.facts(self.root, self.rel)["state"], "current")
        touch(self.p("code", "02_fit.py"), "y", mtime=time.time() - 300)
        self.assertEqual(wh.facts(self.root, self.rel)["state"], "stale")
        touch(self.p("code", "02_fit.py"), "y", mtime=self.t0 + 1)
        os.remove(self.p("code", "01_prep.R"))
        os.remove(self.p("code", "02_fit.py"))
        os.remove(self.p("code", "03_show.R"))
        self.assertEqual(wh.facts(self.root, self.rel)["state"], "no steps")

    def test_stale_line_carries_the_order_caveat(self):
        self.run_all()
        touch(self.p("code", "02_fit.py"), "y", mtime=time.time() - 300)
        self.assertIn("Stale: 02, 03.\n  Assumes steps run in number order.", self.card())
        self.assertIn("Assumes steps run in number order.", self.card("short"))

    def test_step_with_no_rule_in_the_snakefile_has_no_mark(self):
        self.snake(("01_prep", "02_fit"))
        card = self.card()
        self.assertIn("  [ ] 01_prep\n  [ ] 02_fit\n      03_show", card)
        self.assertEqual(wh.facts(self.root, self.rel)["state"], "not run")

    def test_qmd_html_in_the_step_folder_and_old_reports_count_as_output(self):
        touch(self.p("code", "04_page.qmd"), mtime=self.t0 + 5)
        self.snake(("01_prep", "02_fit", "03_show", "04_page"))
        self.run_all()
        touch(self.p("outputs", "04_page", "04_page.html"), mtime=self.t0 + 200)
        self.assertIn("  [x] 04_page", self.card())
        os.remove(self.p("outputs", "04_page", "04_page.html"))
        os.rmdir(self.p("outputs", "04_page"))
        touch(self.p("reports", "04_page.html"), mtime=self.t0 + 200)
        self.assertIn("  [x] 04_page", self.card())

    def test_pending_plan_matches_the_path_not_a_prefix(self):
        self.run_all()
        os.makedirs(os.path.join(self.root, ".mycelium-extra", "pending"))
        text = "Plan status: pending\nfolder analysis/demo-extra and analysis/demo2/code"
        with open(os.path.join(self.root, ".mycelium-extra", "pending", "s.json"), "w") as handle:
            json.dump([{"hash": "ab12", "text": text}], handle)
        self.assertNotIn("approve", self.card())
        self.assertEqual(wh.pending_plan(self.rel, [text + " and analysis/demo."]), True)
        self.assertEqual(wh.pending_plan(self.rel, [text]), False)

    def test_run_log_labels(self):
        self.run_all()
        self.assertEqual(wh.facts(self.root, self.rel)["ran"], "no run log")
        self.assertIn("No run log", self.card())
        self.assertIn("no run log", wh.answer(self.root, self.root, "all", write=False))
        touch(self.p("logs", "CHANGES.md"), "# Change log\n\n## 20xx-bad abc1234 ok\n")
        f = wh.facts(self.root, self.rel)
        self.assertEqual(f["ran"], "run time unreadable")
        self.assertIn("Last run ok: run time unreadable.", wh.render_card(f))

    def test_where_all_outside_the_gated_roots(self):
        shutil.move(self.folder, os.path.join(self.root, "work_demo_tmp"))
        os.makedirs(os.path.join(self.root, "work"))
        shutil.move(os.path.join(self.root, "work_demo_tmp"), os.path.join(self.root, "work", "demo"))
        empty = wh.answer(self.root, self.root, "all", write=False)
        self.assertIn("No analysis folders under analysis/, nbs/", empty)
        out = wh.answer(self.root, os.path.join(self.root, "work", "demo"), "all", write=False)
        self.assertTrue(out.startswith("ANALYSES"))
        self.assertIn("demo", out)

    def test_where_all_looks_one_level_below_a_gated_root(self):
        shutil.rmtree(self.folder)
        touch(os.path.join(self.root, "analysis", "group", "deep", "code", "01_a.R"))
        out = wh.answer(self.root, self.root, "all", write=False)
        self.assertIn("deep", out)

    def test_current_analysis_skips_scaffold_tracker_rows(self):
        self.run_all()
        touch(self.p("plans", "TRACKER.md"), TRACKER.split("| T1")[0]
              + "| S01 | code/01_prep.R | todo | | |\n| S02 | code/02_fit.py | todo | | |\n")
        self.verified(time.time() + 60)
        card = self.card()
        self.assertIn("Nothing pending.", card)
        self.assertNotIn("LATER", card)
        self.assertIn("tracker rows S01, S02 say open but their steps are current", card)

    # ---- Mycelium analyses (0.28.0)

    def mycelium_folder(self, name="vax-study"):
        """A Mycelium-style analysis: scripts/ with numbered files and a <NAME>.md doc, no code/."""
        rel = "analysis/" + name
        folder = os.path.join(self.root, rel)
        for n, script in enumerate(("01_load.py", "02_test.R")):
            touch(os.path.join(folder, "scripts", script), mtime=self.t0 + n)
        touch(os.path.join(folder, name.upper().replace("-", "_") + ".md"), DOC)
        return rel, folder

    def test_scripts_folder_is_an_analysis_with_steps(self):
        rel, folder = self.mycelium_folder()
        card = wh.answer(self.root, folder, None, write=False)
        self.assertIn("WHERE YOU ARE: vax-study", card)
        self.assertIn("01_load", card)
        self.assertIn("02_test", card)

    def test_where_all_lists_scripts_and_doc_only_analyses(self):
        self.mycelium_folder("vax-study")
        os.makedirs(os.path.join(self.root, "analysis", "doc-only", "outputs"))
        touch(os.path.join(self.root, "analysis", "doc-only", "DOC_ONLY.md"), DOC)
        os.makedirs(os.path.join(self.root, "analysis", "ideas"))  # a container: its doc alone is no analysis
        touch(os.path.join(self.root, "analysis", "ideas", "IDEAS.md"), DOC)
        shutil.rmtree(self.folder)
        out = wh.answer(self.root, self.root, "all", write=False)
        self.assertIn("vax-study", out)
        self.assertIn("doc-only", out)
        self.assertNotIn("ideas", out)

    def test_where_all_shows_the_manifest_status_word(self):
        self.mycelium_folder("vax-study")
        touch(os.path.join(self.root, "analysis", "ANALYSIS_MANIFEST.md"),
              "## vax-study\n\n**Path**: `analysis/vax-study/`\n**Status**: active \u2014 ran today\n")
        out = wh.answer(self.root, self.root, "all", write=False)
        line = next(l for l in out.splitlines() if "vax-study" in l)
        self.assertIn("[manifest: active]", line)
        self.assertNotIn("manifest", next(l for l in out.splitlines() if "demo" in l))

    def test_where_all_reads_roots_from_the_repo_gate_json_and_the_manifest_folder(self):
        shutil.move(self.folder, os.path.join(self.root, "demo_tmp"))
        os.makedirs(os.path.join(self.root, "nbs_integrated"))
        shutil.move(os.path.join(self.root, "demo_tmp"), os.path.join(self.root, "nbs_integrated", "demo"))
        touch(self.p("..", "..", ".mycelium-extra", "gate.json"), json.dumps({"gated_paths": ["nbs_integrated/**"]}))
        out = wh.answer(self.root, self.root, "all", write=False)  # no config handed in: read from gate.json
        self.assertIn("demo", out)
        os.remove(os.path.join(self.root, ".mycelium-extra", "gate.json"))
        touch(os.path.join(self.root, "nbs_integrated", "ANALYSIS_MANIFEST.md"), "# m\n")
        self.assertIn("demo", wh.answer(self.root, self.root, "all", write=False))  # found by its manifest

    def numbers(self, folder, entries):
        touch(os.path.join(folder, "outputs", "numbers.json"), json.dumps({"namespace": "x", "values": entries}))

    def test_leftover_numbers_keys_are_a_watch_out_line(self):
        rel, folder = self.mycelium_folder()
        self.numbers(folder, [
            {"key": "n_ok", "value": 1, "provenance": "p", "computed_at": "scripts/01_load.py:L4"},
            {"key": "n_gone", "value": 2, "provenance": "p", "computed_at": "scripts/09_removed.py:L8"},
            {"key": "n_none", "value": 3, "provenance": "p"}])
        card = wh.answer(self.root, folder, None, write=False)
        self.assertIn("numbers.json keys with a missing script: n_gone", card)
        self.assertNotIn("n_ok,", card)
        self.assertNotIn("n_none", card)

    def test_numbers_keys_from_a_notebook_stdin_or_outside_the_root_are_not_leftovers(self):
        rel, folder = self.mycelium_folder()
        self.numbers(folder, [
            {"key": "k1", "computed_at": "<stdin>:L3"}, {"key": "k2", "computed_at": "/tmp/ipykernel_1/55.py:L2"},
            {"key": "k3", "computed_at": "scripts/gone.py:L10-L20"}, {"key": "k4", "computed_at": "scripts/gone.py:7"}])
        self.assertEqual(wh.numbers_leftovers(folder, None), ["k3", "k4"])

    def test_leftover_numbers_keys_are_capped_at_five(self):
        rel, folder = self.mycelium_folder()
        self.numbers(folder, [{"key": "k{}".format(i), "value": i, "computed_at": "scripts/gone.py:L1"} for i in range(8)])
        card = wh.answer(self.root, folder, None, write=False)
        self.assertIn("k0, k1, k2, k3, k4 +3 more", card)
        self.assertNotIn("k5", card)

    def test_numbers_json_of_another_shape_or_bad_json_gives_no_line(self):
        rel, folder = self.mycelium_folder()
        touch(os.path.join(folder, "outputs", "numbers.json"), json.dumps({"a": {"value": 1}, "b": 2}))
        self.assertNotIn("numbers.json keys", wh.answer(self.root, folder, None, write=False))
        touch(os.path.join(folder, "outputs", "numbers.json"), "{not json")
        self.assertNotIn("numbers.json keys", wh.answer(self.root, folder, None, write=False))

    def test_loose_files_next_to_the_layout_marker_are_a_watch_out_line(self):
        touch(self.p("outputs", ".layout"), "layout: steps\nversion: 1\n")
        touch(self.p("outputs", "numbers.json"), "{}")
        self.assertNotIn("loose file", self.card())  # numbers.json is Mycelium's own and fine
        touch(self.p("outputs", "summary.tsv"))
        touch(self.p("outputs", "plot.png"))
        self.assertIn("2 loose files in outputs/ (plot.png, summary.tsv); steps write outputs/<stem>/", self.card())

    def test_loose_files_without_the_marker_are_not_flagged(self):
        touch(self.p("outputs", "summary.tsv"))
        self.assertNotIn("loose file", self.card())

    def test_scripts_folder_next_to_code_is_a_watch_out_line(self):
        self.assertNotIn("scripts/ sits next to code/", self.card())
        touch(self.p("scripts", "01_x.py"))
        self.assertIn("scripts/ sits next to code/; steps belong in code/", self.card())
        self.assertIn("01_prep", self.card())  # code/ still gives the steps

    def gate_json(self, **keys):
        touch(os.path.join(self.root, ".mycelium-extra", "gate.json"), json.dumps(keys))

    def registries(self):
        touch(os.path.join(self.root, "todo", "TODO_REGISTRY.md"),
              "# TODO registry\n\n| ID | Item | Status |\n|----|------|--------|\n"
              "| T-001 | Re-check `analysis/demo` at day 90 | open |\n"
              "| T-002 | Old thing in analysis/demo | done |\n"
              "| T-003 | Something for analysis/other | open |\n"
              "| T-004 | Longer path analysis/demo-two | open |\n")
        touch(os.path.join(self.root, ".living", "findings", "FINDINGS_REGISTRY.md"),
              "# Findings registry\n\n| ID | Topic | Claim | Status |\n|----|-------|-------|--------|\n"
              "| F-001 | demo | Genes rise after the shot | preliminary |\n"
              "| F-002 | [other](other.md) | Cited in the doc | supported |\n"
              "| F-003 | other | Not ours | supported |\n")
        touch(self.p("DEMO.md"), DOC + "\nSee F-002.\n")

    def test_mycelium_later_rows_are_off_by_default_and_read_nothing(self):
        self.registries()
        self.gate_json()
        opened = []
        real_read = wh.ap.read
        wh.ap.read = lambda path, *a, **k: (opened.append(path), real_read(path, *a, **k))[1]
        self.addCleanup(setattr, wh.ap, "read", real_read)
        card = self.card()
        self.assertNotIn("T-001", card)
        self.assertNotIn("F-001", card)
        self.assertFalse([p for p in opened if p.endswith("REGISTRY.md")])

    def test_mycelium_later_rows_when_the_key_is_on(self):
        self.registries()
        self.gate_json(where_mycelium=True)
        later = self.card().split("LATER")[1]
        self.assertIn("T-001: Re-check analysis/demo at day 90 (open)", later)
        self.assertIn("F-001 (preliminary): Genes rise after the shot", later)  # its Topic is this analysis
        self.assertIn("F-002 (supported): Cited in the doc", later)  # cited by the analysis doc
        for absent in ("T-002", "T-003", "T-004", "F-003"):
            self.assertNotIn(absent, later)

    def test_mycelium_later_skips_wont_do_rows(self):
        self.registries()
        self.gate_json(where_mycelium=True)
        touch(os.path.join(self.root, "todo", "TODO_REGISTRY.md"),
              "| ID | Item | Status |\n|----|------|--------|\n"
              "| T-010 | fix analysis/demo thing | wont-do |\n| T-011 | fix analysis/demo other | open |\n")
        later = self.card().split("LATER")[1]
        self.assertNotIn("T-010", later)
        self.assertIn("T-011", later)

    def test_mycelium_later_rows_are_capped_and_where_all_skips_them(self):
        self.registries()
        self.gate_json(where_mycelium=True)
        touch(self.p("plans", "TRACKER.md"), TRACKER + "| T5 | more | todo | | |\n| T6 | even more | todo | | |\n")
        later = self.card().split("LATER")[1].split("\n\n")[0]
        self.assertIn("  - +2 more", later)  # four tracker rows plus three registry rows, five shown
        self.assertNotIn("T-001", wh.answer(self.root, self.root, "all", write=False))

    def test_mycelium_registries_missing_is_fine_and_gate_json_garbage_is_off(self):
        self.gate_json(where_mycelium=True)
        self.assertIn("WHERE YOU ARE", self.card())
        touch(os.path.join(self.root, ".mycelium-extra", "gate.json"), "[1,")
        self.registries()
        self.assertNotIn("T-001", self.card())
        self.gate_json(where_mycelium="yes")
        self.assertNotIn("T-001", self.card())

    def test_gate_returns_a_block_naming_the_error_not_none(self):
        import gate
        event = {"cwd": self.folder, "session_id": "s1"}
        self.assertIsNone(gate.where_card(event, self.root, {}, "where is the table"))
        original = wh.facts
        wh.facts = lambda *a, **k: (_ for _ in ()).throw(ValueError("boom"))
        self.addCleanup(setattr, wh, "facts", original)
        reply = gate.where_card(event, self.root, {}, "where")
        self.assertIn("could not build the card for analysis/demo (ValueError: boom)", reply)


class WhereGateTest(unittest.TestCase):
    def setUp(self):
        saved = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(saved)))
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        os.environ["HOME"] = home
        self.root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, ".mycelium-extra"))
        with open(os.path.join(self.root, ".mycelium-extra", "gate.json"), "w") as handle:
            json.dump({}, handle)
        self.folder = os.path.join(self.root, "analysis", "demo")
        touch(os.path.join(self.folder, "code", "01_prep.R"))
        touch(os.path.join(self.folder, "Snakefile"))
        touch(os.path.join(self.folder, "DEMO.md"), DOC)

    def say(self, prompt, cwd=None):
        payload = {"prompt": prompt, "cwd": cwd or self.folder, "session_id": "s1"}
        proc = subprocess.run([sys.executable, GATE, "prompt"], input=json.dumps(payload).encode("utf-8"),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout.decode("utf-8")) if proc.stdout.strip() else None

    def test_typed_where_answers_without_the_model(self):
        for prompt in ("where", "Where am I?", "where short", "where all"):
            result = self.say(prompt)
            self.assertEqual(result["decision"], "block", prompt)
            self.assertTrue(result["reason"].strip(), prompt)
        self.assertIn("WHERE YOU ARE: demo", self.say("where")["reason"])
        self.assertTrue(self.say("where short")["reason"].startswith("demo\nAIM"))

    def test_where_inside_a_sentence_is_not_a_command(self):
        self.assertIsNone(self.say("where is the donor table kept?"))
        self.assertIsNone(self.say("where do the outputs go"))

    def test_typed_where_changes_no_gate_state(self):
        before = sorted(os.listdir(os.path.join(self.root, ".mycelium-extra")))
        self.say("where")
        after = sorted(os.listdir(os.path.join(self.root, ".mycelium-extra")))
        self.assertEqual(sorted(set(after) - set(before)), ["now"])


if __name__ == "__main__":
    unittest.main()
