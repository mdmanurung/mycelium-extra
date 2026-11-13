"""Run: python3 skills/verify/tests/test_audit_fixes.py

Regression tests for the verify findings in docs/roadmap/13-function-audit.md: a gap must never
read as a pass, and a bad input must say so instead of silently dropping a check.
"""

import decimal
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(PLUGIN, "hooks"))
sys.dont_write_bytecode = True
import gate  # noqa: E402
import test_verify  # noqa: E402


class Harness(test_verify.VerifyTest):
    """The verify harness (approve, run, write), without re-running its own tests."""


for _name in [name for name in dir(Harness) if name.startswith("test_")]:
    setattr(Harness, _name, None)  # inherited tests belong to test_verify.py


class AuditFixTest(Harness):
    # journal.py loads verify with gate.load_verify() and never calls load_gate(); _paths() must still work
    def test_paths_resolve_when_verify_is_loaded_like_journal_does(self):
        verify = gate.load_verify()
        folder = os.path.join(self.root, "analysis", "lazy")
        os.makedirs(folder)
        with open(os.path.join(folder, "README.md"), "w") as handle:
            handle.write("# doc\n")
        self.assertEqual(verify._paths().find_doc(folder), os.path.join(folder, "README.md"))

    # X13: a match by leading digits is stated, so "verified" is not read as "equal"
    def test_how_a_claim_matches_is_stated(self):
        verify = gate.load_verify()
        self.assertTrue(verify.agrees(decimal.Decimal("8"), "", decimal.Decimal("8.9")))
        digest, _ = self.claims_run("- 1.234 | outputs/de.tsv log2fc IL7R")
        out = self.verify("report", digest)
        self.assertIn("or its leading digits", out)

    # C19 + X10: a linter that never ran is not reported as clean
    def test_lint_that_did_not_run_is_not_clean(self):
        digest = self.approve(test_verify.plan("run `{}`".format(test_verify.FIT)))
        self.run_cmd("python " + test_verify.FIT)
        missing = os.path.join(self.root, "bin", "no-such-scilintr")
        summary = self.verify("report", digest, scilintr=missing)
        self.assertNotIn("lint clean", summary)
        self.assertIn("not checked: Python", summary)
        out = self.verify("disclose", digest, scilintr=missing)
        self.assertIn("[BLANK: scilintr did not run", out)
        self.assertNotIn("No lint finding was open", out)

    # X9: a wrong --analysis-dir is refused, not silently unchecked
    def test_wrong_analysis_dir_is_refused(self):
        digest = self.approve(test_verify.plan("run `{}`".format(test_verify.FIT)))
        error = self.verify("report", digest, "--analysis-dir", "analysis/not-here", fails=True)
        self.assertIn("is not a folder", error)
        self.assertIn("claims", error)

    # C20: provenance inside a folder the repository ignores is still found
    def test_provenance_in_an_ignored_folder_is_found(self):
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=self.root, check=True)
        self.write(".gitignore", "analysis/\n")
        rel = "analysis/a/provenance/receipts-0123abcd.jsonl"
        self.write(rel, "{}\n")
        verify = gate.load_verify()
        self.assertIn(rel, verify.provenance_receipts(self.root))

    # X11: a same-size rewrite still changes a run's content id
    def test_run_id_covers_mtime_as_well_as_size(self):
        verify = gate.load_verify()
        folder = os.path.join(self.root, "run_20260101_alpha")
        path = self.write("run_20260101_alpha/out.txt", "abcd")
        os.makedirs(folder, exist_ok=True)
        first = verify.scan_run(folder)[1]
        with open(path, "w") as handle:
            handle.write("abce")  # same size
        os.utime(path, ns=(1, 2 * 10 ** 9 + 123456789))
        second = verify.scan_run(folder)[1]
        self.assertNotEqual(first, second)

    # X12: a label whose status contradicts superseded_by is a finding
    def test_status_contradictions_are_findings(self):
        verify = gate.load_verify()
        results = os.path.join(self.root, "analysis", "a", "results")
        self.write("analysis/a/results/run_20260101_a/RUN.txt",
                   "run: run_20260101_a\nversion: 1\nkind: model\nstatus: current\n"
                   "superseded_by: run_20260101_b\n")
        self.write("analysis/a/results/run_20260101_b/RUN.txt",
                   "run: run_20260101_b\nversion: 2\nkind: model\nstatus: superseded\n")
        runs = [verify.label_run(os.path.join(results, name)) for name in sorted(os.listdir(results))]
        texts = [f["text"] for f in verify.run_findings(self.root, results, runs, []) if f["severity"] == "gap"]
        self.assertTrue(any("status `current` but `superseded_by" in text for text in texts), texts)
        self.assertTrue(any("status `superseded` but no `superseded_by`" in text for text in texts), texts)

    # X14: a write failure is a `verify:` error, not a traceback
    def test_write_failure_is_a_verify_error(self):
        digest = self.approve(test_verify.plan("run `{}`".format(test_verify.FIT)))
        self.run_cmd("python " + test_verify.FIT)
        # CI containers run as root, which can write through chmod(0555).
        path = self.write("analysis/a/provenance", "existing file\n")
        error = self.verify("write", digest, "--analysis-dir", "analysis/a", fails=True)
        self.assertIn("verify: could not write", error)
        self.assertNotIn("Traceback", error)
        with open(path) as handle:
            self.assertEqual(handle.read(), "existing file\n")


    # stress-test fixes: malformed receipts are skipped and counted, never a traceback
    def test_malformed_receipts_are_skipped_not_crashes(self):
        digest = self.approve(test_verify.plan("run `{}`".format(test_verify.FIT)))
        self.run_cmd("python " + test_verify.FIT)
        path = os.path.join(self.root, ".mycelium-extra", "receipts.jsonl")
        with open(path, "rb") as handle:
            good = json.loads(handle.read().splitlines()[-1])
        bad = [b'{"ts": 1, \xff}\n']
        for extra in ({"dev_packages": [{"path": ["a"], "head": 1, "dirty": [1]}]}, {"dev_packages": 5},
                      {"pins": {"a": 5}}):
            bad.append((json.dumps(dict(good, **extra)) + "\n").encode())
        with open(path, "ab") as handle:
            handle.writelines(bad)
        self.assertIn("4 malformed receipt record(s) were skipped", self.verify("report", digest))
        self.verify("disclose", digest)
        self.verify("status")

    # stress-test fixes: a plan never written has no saved bundle; another plan's bundle is not its legacy one
    def test_unwritten_plan_next_to_a_saved_one_has_no_legacy_gap(self):
        verify = gate.load_verify()
        folder = os.path.join(self.root, "analysis", "a", "provenance")
        self.write("analysis/a/provenance/plan-aaaaaaaa.md", "x\n")
        self.assertEqual(verify.saved_bundle_state(folder, "bbbbbbbb"), "none")
        self.assertEqual(verify.saved_bundle_state(folder, "aaaaaaaa"), "legacy")
        self.assertFalse(os.path.exists(os.path.join(folder, ".publish.lock")))  # a read creates no lock

    # stress-test fixes: a superscript digit is not a version number
    def test_run_version_rejects_unicode_digits(self):
        verify = gate.load_verify()
        self.write("analysis/a/results/run_20260101_a/RUN.txt", "run: run_20260101_a\nversion: \u00b2\nstatus: current\n")
        label = verify.label_run(os.path.join(self.root, "analysis", "a", "results", "run_20260101_a"))
        self.assertTrue(any("whole number" in str(p) for p in label["problems"]), label)
        self.assertEqual(verify.run_order(label)[0], 0)

    # stress-test fixes: a provenance recovery gap on write is a `verify:` error
    def test_write_recovery_gap_is_a_verify_error(self):
        digest = self.approve(test_verify.plan("run `{}`".format(test_verify.FIT)))
        self.run_cmd("python " + test_verify.FIT)
        self.verify("write", digest, "--analysis-dir", "analysis/a")
        folder = os.path.join(self.root, "analysis", "a", "provenance")
        lint = [n for n in os.listdir(folder) if n.startswith("lint-")][0]
        with open(os.path.join(folder, lint), "a") as handle:
            handle.write("edited\n")
        error = self.verify("write", digest, "--analysis-dir", "analysis/a", fails=True)
        self.assertIn("verify:", error)
        self.assertNotIn("Traceback", error)

    # stress-test fixes: `runs` falls back to outputs/ when the folder has no results/
    def test_runs_default_falls_back_to_outputs(self):
        self.approve(test_verify.plan("run `{}`".format(test_verify.FIT)))
        self.write("analysis/a/outputs/run_20260101_a/RUN.txt", "run: run_20260101_a\nversion: 1\nkind: model\nstatus: current\n")
        self.assertIn("run_20260101_a", self.verify("runs"))


    # 0.24.0: `runs` reads a run-layout folder through the shared resolver and flags a bad kind
    def test_runs_shows_kind_and_flags_a_bad_kind(self):
        for name, kind in (("run_20261104_baseline", "analysis"), ("run_20261105_odd", "model")):
            self.write("analysis/a/outputs/{0}/RUN.txt".format(name),
                       "run: {}\nversion: 1\nkind: {}\nstatus: current\n".format(name, kind))
            self.write("analysis/a/outputs/{}/figures/01_x.png".format(name), "x")
        out = self.verify("runs", "analysis/a/outputs")
        self.assertRegex(out, r"run_20261104_baseline \| 1 \| analysis \|")
        self.assertIn("gap `run_20261105_odd`: kind `model` is not one of", out)
        self.assertNotIn("gap `run_20261104_baseline`: kind", out)

    def test_runs_on_a_flat_outputs_folder_lists_none(self):
        self.write("analysis/a/outputs/01_fit.tsv", "x\n")
        self.assertIn("No `run_<YYYYMMDD>_<slug>` folders here.", self.verify("runs", "analysis/a/outputs"))

    # 0.25.0: a steps layout has no RUN.txt; `runs` lists the step folders and the last change
    def steps_folder(self):
        self.write("analysis/a/outputs/01_prepare/01_prepare.tsv", "x\n")
        self.write("analysis/a/outputs/03_show/figures/03_show.png", "x")
        self.write("analysis/a/outputs/03_show/source_data/03_show.tsv", "x\n")
        self.write("analysis/a/outputs/03_show/figures/03_extra.png", "x")
        self.write("analysis/a/outputs/04_report/04_report.html", "x")

    def test_runs_lists_step_folders_with_no_runtxt_gap(self):
        self.steps_folder()
        out = self.verify("runs", "analysis/a/outputs")
        for step in ("01_prepare", "03_show", "04_report"):
            self.assertRegex(out, r"\| {} \| \d{{4}}-\d\d-\d\d \d\d:\d\d \| [0-9a-f]{{8}} \|".format(step))
        self.assertNotIn("no label", out)
        self.assertNotIn("unlabelled", out)
        self.assertNotIn("No `run_<YYYYMMDD>_<slug>` folders here.", out)
        self.assertIn("Last change: none logged", out)
        self.assertIn("- gap `03_extra`: figure has no source data", out)
        self.assertNotIn("`03_show`:", out)  # that stem is paired

    def test_runs_skips_a_linked_step_folder(self):
        self.steps_folder()
        os.symlink(os.path.join(self.root, "analysis", "a", "outputs", "03_show"),
                   os.path.join(self.root, "analysis", "a", "outputs", "05_link"))
        data = json.loads(self.verify("runs", "analysis/a/outputs", "--json"))
        self.assertNotIn("05_link", [s["step"] for s in data["steps"]])

    def test_runs_lists_a_fresh_marked_scaffold_and_panels(self):
        self.write("analysis/a/outputs/.layout", "layout: steps\nversion: 1\n")
        data = json.loads(self.verify("runs", "analysis/a/outputs", "--json"))
        self.assertEqual((data["steps"], data["runs"], data["findings"]), ([], [], []))
        out = self.verify("runs", "analysis/a/outputs")
        self.assertIn("Step folders: none yet.", out)
        self.assertIn("Last change: none logged", out)
        self.assertNotIn("No `run_<YYYYMMDD>_<slug>` folders here.", out)
        self.write("analysis/a/outputs/panels/figures/plot_a.png", "x")
        data = json.loads(self.verify("runs", "analysis/a/outputs", "--json"))
        self.assertEqual([s["step"] for s in data["steps"]], ["panels"])

    def test_runs_quotes_the_newest_change_heading_and_keeps_legacy_runs(self):
        self.steps_folder()
        self.write("analysis/a/logs/CHANGES.md", "# Changes\n\n## 2026-11-12 09:00 abc1234 ok\n- a\n\n"
                   "## 2026-11-10 08:00 def5678 failed\n- b\n")
        self.label("analysis/a/outputs/run_20261001_old", "current")
        out = self.verify("runs", "analysis/a/outputs")
        self.assertIn("Last change: ## 2026-11-12 09:00 abc1234 ok", out)
        self.assertRegex(out, r"\| run_20261001_old \| 1 \| model \| current \|")  # legacy RUN.txt stays read
        self.assertNotIn("| 01_prepare | 1 |", out)
        data = json.loads(self.verify("runs", "analysis/a/outputs", "--json"))
        self.assertEqual([s["step"] for s in data["steps"]], ["01_prepare", "03_show", "04_report"])
        self.assertEqual([r["run"] for r in data["runs"]], ["run_20261001_old"])

    # 0.24.0: `write` indexes the verify record in the analysis doc's Outputs table, once per hash
    def written(self, doc_text):
        self.write("analysis/a/README.md", doc_text)
        digest = self.approve(test_verify.plan("run `{}`".format(test_verify.FIT)))
        self.run_cmd("python " + test_verify.FIT)
        return digest, self.verify("write", digest, "--analysis-dir", "analysis/a")

    def test_write_appends_one_outputs_row_and_replaces_it_on_rerun(self):
        doc = "# A\n\n## Outputs\n\n| File | Description |\n|---|---|\n| `outputs/x.tsv` | x |\n\n## Next\n\ntext\n"
        digest, out = self.written(doc)
        self.assertIn("indexed provenance/verify-{}.md".format(digest), out)
        self.verify("write", digest, "--analysis-dir", "analysis/a")
        with open(os.path.join(self.root, "analysis", "a", "README.md")) as handle:
            text = handle.read()
        self.assertEqual(text.count("| provenance/verify-{}.md |".format(digest)), 1, text)
        self.assertRegex(text, r"\| x \|\n\| provenance/verify-%s\.md \| verify \w+ \(\d{4}-\d\d-\d\d\) \|\n\n## Next" % digest)

    def test_write_without_an_outputs_table_adds_nothing_and_says_so(self):
        doc = "# A\n\n## Outputs\n\nSee outputs/.\n"
        digest, out = self.written(doc)
        self.assertIn("note: README.md has no `## Outputs` table", out)
        with open(os.path.join(self.root, "analysis", "a", "README.md")) as handle:
            self.assertEqual(handle.read(), doc)


    # 0.28: the sibling-plugin info lines reach a real report and never change its status
    def test_report_prints_wording_leftover_and_decision_lines_as_info(self):
        evidence = "\n**Evidence**\n- IL7R is associated with day 28 [agent-derived: `data/meta.tsv:1`]\n"
        decisions = "\n## Decisions to record\n\n- Pairing by donor, not by visit\n"
        digest = self.approve(test_verify.plan("run `{}`".format(test_verify.FIT)).replace(
            "\nOutputs:", evidence + decisions + "\nOutputs:"))
        self.run_cmd("python " + test_verify.FIT)
        self.write("analysis/a/A.md", "# a\n\n## Key Findings\n\n- Drug X drives IL7R [agent-derived: `outputs/de.tsv`]\n")
        self.write("analysis/a/outputs/numbers.json", json.dumps({"namespace": "a", "values": [
            {"key": "n_old", "value": 1, "computed_at": "scripts/gone.py:L3"}]}))
        self.write(".living/decisions.md", "# Decisions\n\n- something else\n")
        base = self.verify("report", digest)
        self.assertIn("Wording in `analysis/a/A.md` Key Findings: L5 uses `drives`", base)
        self.assertNotIn("Wording in the plan's Evidence", base)
        self.assertIn("numbers.json has 1 key(s) whose script no longer exists: n_old (scripts/gone.py)", base)
        self.assertIn("Decisions to record: 1 of 1 bullet(s)", base)
        for text in ("Wording in", "numbers.json has", "Decisions to record:"):
            self.assertNotRegex(base, r"\*\*(?:gap|block)\*\*: " + text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
