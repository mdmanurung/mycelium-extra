"""Run: python3 skills/verify/tests/test_pstack_checks.py

The checks added in 0.31 from pstack: the decision log against the plan, reproduce-or-drop, and the `explain`
block. Each check has a fixture where it must fire (a planted break) and one where it must stay quiet.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
LOGGER = os.path.join(PLUGIN, "skills", "verify", "scripts", "decision_log.py")
sys.path.insert(0, os.path.join(PLUGIN, "hooks"))
sys.dont_write_bytecode = True
import gate  # noqa: E402

verify = gate.load_verify()
HEADER = "\t".join(verify.DECISION_COLUMNS)
PLAN = "\n".join(["| Step | Choice | Source | Validation |", "|---|---|---|---|",
                  "| 1 | filter genes below 10 counts | user | counts table |",
                  "| 2 | seed 7 | inherited: code/a.R | rerun |",
                  "| 3 | file layout | default: the repo's naming | listing |"])


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(text)


def levels(report):
    return [(level, text) for level, text in report.findings]


class Tmp(unittest.TestCase):
    def setUp(self):
        self.dir = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)

    def log(self, *rows, header=HEADER):
        write(os.path.join(self.dir, "an", "logs", "decisions.tsv"), "\n".join([header] + list(rows)) + "\n")


class DecisionLog(Tmp):
    def row(self, plan_row, phase="fit", decision="drop donor 4", source="user"):
        return "\t".join(["2026-11-16T10:00:00Z", phase, decision, "why", "outputs/x.tsv", "done", plan_row, source])

    def run_check(self, plan=PLAN):
        report = verify.Report()
        entries = verify.decision_log(self.dir, "an", plan, report)
        return report, entries

    def test_a_row_with_no_plan_row_blocks(self):  # planted break: an unplanned impactful choice
        self.log(self.row(""))
        report, _ = self.run_check()
        self.assertEqual(report.status(), "DOES_NOT_CONFORM")
        self.assertIn("no plan row", [t for l, t in report.findings if l == "block"][0])

    def test_a_row_naming_a_plan_row_that_does_not_exist_blocks(self):  # planted break
        self.log(self.row("9"))
        report, _ = self.run_check()
        self.assertEqual(report.status(), "DOES_NOT_CONFORM")
        self.assertIn("`9`", [t for l, t in report.findings if l == "block"][0])

    def test_rows_that_match_the_plan_are_quiet(self):  # control
        self.log(self.row("1"), self.row("2", source="inherited: code/a.R"))
        report, entries = self.run_check()
        self.assertEqual(len(entries), 2)
        self.assertEqual(report.status(), "CONFORMS")

    def test_a_row_linked_to_a_default_row_is_info_only(self):
        self.log(self.row("3", source="default: x"))
        report, _ = self.run_check()
        self.assertEqual(report.status(), "CONFORMS")
        self.assertTrue(any("`default:` row" in t for l, t in report.findings if l == "info"))

    def test_start_rows_mark_a_run_and_are_not_decisions(self):
        self.log(self.row("", phase="start", decision=""), self.row("1"))
        report, entries = self.run_check()
        self.assertEqual(len(entries), 1)
        self.assertEqual(report.status(), "CONFORMS")

    def test_a_missing_log_is_a_gap_when_the_plan_has_user_rows(self):  # planted break: no log at all
        report, entries = self.run_check()
        self.assertEqual(entries, [])
        self.assertEqual([l for l, _ in report.findings], ["gap"])
        self.assertIn("No decision log", report.findings[0][1])
        self.assertEqual(report.status(), "CONFORMS_WITH_GAPS")

    def test_with_no_analysis_folder_a_user_plan_gets_an_info_line_not_a_gap(self):
        report = verify.Report()
        self.assertEqual(verify.decision_log(self.dir, None, PLAN, report), [])
        self.assertEqual([l for l, _ in report.findings], ["info"])

    def test_a_header_only_log_has_no_gap(self):  # control: the log exists and holds no decisions
        self.log()
        report, entries = self.run_check()
        self.assertEqual(entries, [])
        self.assertEqual(report.status(), "CONFORMS")

    def test_user_rows_with_no_decision_row_get_one_info_line(self):  # F5 planted break: an empty log passed silently
        self.log(self.row("1"))
        report, _ = self.run_check()
        said = [t for l, t in report.findings if "no decision row" in t]
        self.assertEqual(len(said), 1)
        self.assertIn("2 (inherited)", said[0])
        self.assertNotIn("1 (user)", said[0])
        self.assertEqual(report.status(), "CONFORMS")

    def test_start_rows_only_still_lists_the_silent_plan_rows(self):
        self.log(self.row("", phase="start", decision=""))
        report, _ = self.run_check()
        self.assertTrue(any("1 (user), 2 (inherited)" in t for l, t in report.findings))

    def test_all_asked_rows_covered_is_quiet(self):  # F5 control
        self.log(self.row("1"), self.row("2", source="inherited: code/a.R"))
        report, _ = self.run_check()
        self.assertFalse(any("no decision row" in t for l, t in report.findings))

    def stamped(self, plan_row, stamp):
        return self.row(plan_row).replace("2026-11-16T10:00:00Z", stamp)

    def test_rows_before_the_approval_are_counted_not_judged(self):  # F2 planted break: old rows blocked a revised plan
        self.log(self.stamped("9", "2026-11-01T10:00:00Z"), self.stamped("1", "2026-11-16T10:00:00Z"))
        report = verify.Report()
        approved = verify.decision_time("2026-11-10T00:00:00Z")
        entries = verify.decision_log(self.dir, "an", PLAN, report, approved)
        self.assertEqual(len(entries), 1)
        self.assertNotIn("block", [l for l, _ in report.findings])
        self.assertTrue(any("1 row(s)" in t and "before this approval" in t for l, t in report.findings))

    def test_a_row_after_the_approval_with_an_unknown_row_still_blocks(self):  # F2 control
        self.log(self.stamped("9", "2026-11-16T10:00:00Z"))
        report = verify.Report()
        verify.decision_log(self.dir, "an", PLAN, report, verify.decision_time("2026-11-10T00:00:00Z"))
        self.assertEqual(report.status(), "DOES_NOT_CONFORM")

    def test_a_row_with_a_bad_ts_is_a_gap_and_not_judged(self):
        self.log(self.stamped("9", "yesterday"))
        report = verify.Report()
        self.assertEqual(verify.decision_log(self.dir, "an", PLAN, report, 0), [])
        self.assertEqual(report.status(), "CONFORMS_WITH_GAPS")

    def test_a_grill_shaped_plan_without_an_id_column_matches_by_position(self):  # F3 planted break
        grill = "\n".join(["| Step | Choice | Source | Validation |", "|---|---|---|---|",
                           "| code/01_prep.R | filter genes below 10 counts | user | counts table |",
                           "| code/02_fit.R | seed 7 | inherited: code/a.R | rerun |",
                           "| code/03_plot.R | file layout | default: the repo's naming | listing |"])
        self.log(self.row("1"), self.row("2", source="inherited: code/a.R"))
        report, entries = self.run_check(grill)
        self.assertEqual(len(entries), 2)
        self.assertEqual(report.status(), "CONFORMS")
        self.log(self.row("4"))  # control: a position past the table still blocks
        report, _ = self.run_check(grill)
        self.assertEqual(report.status(), "DOES_NOT_CONFORM")

    def test_a_plan_with_an_id_column_matches_by_id_not_position(self):  # F3 control
        withid = "\n".join(["| Step | # | Choice | Source |", "|---|---|---|---|",
                            "| a | 10 | x | user |", "| b | 20 | y | default: z |"])
        self.log(self.row("10"))
        report, _ = self.run_check(withid)
        self.assertEqual(report.status(), "CONFORMS")
        self.log(self.row("1"))
        report, _ = self.run_check(withid)
        self.assertEqual(report.status(), "DOES_NOT_CONFORM")

    def test_a_duplicate_id_is_a_gap_not_a_block(self):  # F3
        dup = "\n".join(["| # | Choice | Source |", "|---|---|---|", "| 1 | x | user |", "| 1 | y | user |"])
        self.log(self.row("1"))
        report, _ = self.run_check(dup)
        self.assertEqual(report.status(), "CONFORMS_WITH_GAPS")
        self.assertNotIn("block", [l for l, _ in report.findings])

    def test_a_missing_log_is_quiet_when_every_row_is_a_default(self):
        only = "\n".join(["| Step | Choice | Source | Validation |", "|---|---|---|---|", "| 1 | naming | default: repo | ls |"])
        report, _ = self.run_check(only)
        self.assertEqual(report.findings, [])

    def test_a_wrong_header_is_a_gap_and_nothing_is_read(self):
        self.log(self.row("1"), header="when\twhat")
        report, entries = self.run_check()
        self.assertEqual(entries, [])
        self.assertEqual(report.status(), "CONFORMS_WITH_GAPS")

    def test_a_short_row_is_skipped_with_a_gap(self):
        self.log("only\ttwo")
        report, entries = self.run_check()
        self.assertEqual(entries, [])
        self.assertEqual(report.status(), "CONFORMS_WITH_GAPS")


class Appender(Tmp):
    def append(self, *cells):
        path = os.path.join(self.dir, "an", "logs", "decisions.tsv")
        return subprocess.run([sys.executable, LOGGER, path] + list(cells), stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True), path

    def test_writes_the_header_once_and_appends_rows(self):
        first, path = self.append("fit", "filter at 10", "package default", "outputs/f.tsv", "ran", "1", "user")
        second, _ = self.append("fit", "seed 7", "inherited", "code/a.R:3", "ran", "2", "inherited: code/a.R")
        self.assertEqual((first.returncode, second.returncode), (0, 0), first.stderr + second.stderr)
        lines = open(path).read().splitlines()
        self.assertEqual(lines[0], HEADER)
        self.assertEqual(len(lines), 3)

    def test_a_negative_number_is_kept_and_tabs_are_flattened(self):
        _, path = self.append("fit", "cutoff\tlfc", "why", "x", "-1.3", "1", "user")
        row = open(path).read().splitlines()[1].split("\t")
        self.assertEqual(row[5], "-1.3")  # result: no formula-injection quote is added
        self.assertEqual(row[2], "cutoff lfc")

    def test_a_decision_with_no_plan_row_is_refused(self):  # planted break: the appender will not log an unplanned choice
        result, path = self.append("fit", "drop donor 4", "why", "x", "done", "", "user")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(os.path.exists(path))

    def test_a_start_row_needs_no_plan_row(self):
        result, path = self.append("start", "", "", "", "", "", "")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("\tstart\t", open(path).read())

    def test_the_wrong_number_of_arguments_is_refused(self):
        result, _ = self.append("fit")
        self.assertNotEqual(result.returncode, 0)


class Explain(Tmp):
    def doc(self, *lines):
        write(os.path.join(self.dir, "an", "AN.md"), "# AN\n<!-- explain\n" + "\n".join(lines) + "\n-->\n")

    def run_check(self):
        report = verify.Report()
        found = verify.explain_blocks(self.dir, "an", [], [], report)
        return report, found

    def test_a_cited_figure_that_exists_is_found(self):  # control
        write(os.path.join(self.dir, "an", "outputs", "03_by_donor.pdf"), "x")
        self.doc("log2FC 1.8 | one donor | outputs/03_by_donor.pdf")
        report, found = self.run_check()
        self.assertEqual(found[0]["verdict"], "figure found")
        self.assertEqual(report.findings, [])

    def test_a_missing_figure_is_a_gap(self):  # planted break
        self.doc("log2FC 1.8 | batch | outputs/03_by_batch.pdf")
        report, found = self.run_check()
        self.assertEqual(found[0]["verdict"], "figure missing")
        self.assertEqual(report.status(), "CONFORMS_WITH_GAPS")

    def test_unsupported_is_stated_and_is_info(self):
        self.doc("log2FC 1.8 | depth | unsupported: no inspected figure")
        report, found = self.run_check()
        self.assertEqual(found[0]["verdict"], "unsupported")
        self.assertEqual(report.status(), "CONFORMS")

    def test_a_malformed_line_is_a_gap(self):
        self.doc("log2FC 1.8 | batch")
        report, found = self.run_check()
        self.assertEqual(found, [])
        self.assertEqual(report.status(), "CONFORMS_WITH_GAPS")


class Reproduce(Tmp):
    def doc(self, *lines):
        write(os.path.join(self.dir, "an", "AN.md"), "# AN\n<!-- reproduce\n" + "\n".join(lines) + "\n-->\n")

    def run_all(self):
        return {r["finding"]: r for r in verify.reproduce(self.dir, ["an/AN.md"], 5)["results"]}

    def test_a_finding_that_prints_its_expected_output_twice_reproduces(self):
        write(os.path.join(self.dir, "an", "n.txt"), "8\n")
        self.doc("8 hits | cat an/n.txt | 8 | the hit count is 8")
        self.assertEqual(self.run_all()["8 hits"]["verdict"], "reproduced")

    def test_a_finding_whose_output_differs_is_dropped_as_unreproduced(self):  # planted break
        write(os.path.join(self.dir, "an", "n.txt"), "7\n")
        self.doc("8 hits | cat an/n.txt | 8 | the hit count is 8")
        entry = self.run_all()["8 hits"]
        self.assertEqual(entry["verdict"], "unreproduced")
        self.assertIn("printed `7`", entry["reason"])

    def test_a_command_that_could_write_is_inconclusive_and_never_runs(self):  # planted break: the guard holds
        target = os.path.join(self.dir, "an", "gone.txt")
        write(target, "x")
        self.doc("gone | rm an/gone.txt | x | the file is kept")
        entry = self.run_all()["gone"]
        self.assertEqual(entry["verdict"], "inconclusive")
        self.assertIn("not a read-only command", entry["reason"])
        self.assertTrue(os.path.exists(target))

    def test_a_redirect_is_inconclusive(self):
        self.doc("w | echo hi > an/out.txt | hi | writes")
        self.assertEqual(self.run_all()["w"]["verdict"], "inconclusive")
        self.assertFalse(os.path.exists(os.path.join(self.dir, "an", "out.txt")))

    def test_a_line_with_the_wrong_shape_is_listed_not_read(self):
        self.doc("only | three | parts")
        result = verify.reproduce(self.dir, ["an/AN.md"], 5)
        self.assertEqual(result["results"], [])
        self.assertEqual(len(result["unparsed"]), 1)

    def test_the_report_lists_the_dropped_finding_and_says_nothing_was_fixed(self):
        write(os.path.join(self.dir, "an", "n.txt"), "7\n")
        self.doc("8 hits | cat an/n.txt | 8 | count")
        text = verify.render_reproduce(verify.reproduce(self.dir, ["an/AN.md"], 5))
        self.assertIn("## Unreproduced (dropped)", text)
        self.assertIn("nothing was fixed", text)


if __name__ == "__main__":
    unittest.main()
