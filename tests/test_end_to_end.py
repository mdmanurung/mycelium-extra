"""End-to-end chain on the fixture project (docs/design/c1-fixture-project.md, section 7).

Run: python3 tests/test_end_to_end.py
"""

import hashlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "e2e"))
import defects  # noqa: E402
import harness  # noqa: E402

A, SCRIPTS, OUTPUTS = harness.ANALYSIS, harness.SCRIPTS, harness.OUTPUTS
REFERENCES = os.path.join(harness.SKILLS, "grill", "references")
PROBE = "python3 -c \"print(open('data/processed/vaccine-cohort/counts.tsv').readline().split()[:3])\""


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


@unittest.skipUnless(harness.git_available(), "git is not installed")
class BaselineChain(unittest.TestCase):
    maxDiff = None

    def project(self, r=None):
        project = harness.Project.fresh(r=r)
        self.addCleanup(project.close)
        return project

    def check(self, condition, project, message):
        if not condition:
            self.fail("{}\nchain so far:\n  {}".format(message, "\n  ".join(project.log)))

    def run_chain(self, project):
        """Steps 1-11 of design section 7. Each assertion says which step failed."""
        p = project
        # 1. fresh project: init created the gate; a second init changes nothing
        self.check("created" in p.init_output and "gate.json" in p.init_output, p, "step 1: " + p.init_output)
        again = p.init()
        self.check("already gated:" in again, p, "step 1: second init said: " + again)
        self.check(p.git("status", "--porcelain") == "", p, "step 1: second init changed the tree")

        # 2. data contract, documented stdin form with process substitution, run with bash -c
        code, out, err = p.data_contract(harness.contract_text())
        self.check(code == 0, p, "step 2: data contract exited {}:\n{}{}".format(code, out, err))
        passes = [line for line in out.splitlines() if line.startswith("PASS")]
        self.check(len(passes) == 5 and "0 blocking alerts, 0 warnings" in out, p, "step 2: " + out)

        # 3. approval
        digest, notice, reply = p.approve(harness.plan_text())
        pins = ["data/processed/vaccine-cohort/sample_metadata.tsv", "data/processed/vaccine-cohort/counts.tsv"]
        listed = notice.split("Inputs pinned")[-1].split("Outputs")[0]
        self.check(all(pin in listed for pin in pins), p, "step 3: notice does not list both pinned inputs:\n" + notice)
        record = p.approval(digest)
        self.check(record is not None and "approved" in ((reply or {}).get("systemMessage") or ""), p,
                   "step 3: approval of {} not recorded: {}".format(digest, reply))
        self.check(sorted(record["pins"]) == sorted(pins), p, "step 3: pins {}".format(record["pins"]))

        # 4. the three planned runs; then an inline read-only probe (Mycelium sees it, the gate does not)
        results = []
        for script in SCRIPTS:
            result = p.run_step(script)
            self.check(not result.denied, p, "step 4: the gate denied `{}`: {}".format(result.command, result.reason))
            self.check(result.pre is None, p, "step 4: the gate spoke for `{}`: {}".format(result.command, result.pre))
            self.check(result.code == 0, p, "step 4: `{}` exited {}:\n{}".format(result.command, result.code,
                                                                                  result.stderr))
            self.check(len(result.receipts) == 1 and result.receipts[0]["plans"] == [digest], p,
                       "step 4: `{}` receipts {}".format(result.command, result.receipts))
            results.append(result)
        probe = p.agent_bash(PROBE)
        self.check(probe.pre is None and probe.code == 0 and probe.receipts == [], p,
                   "step 4: inline probe: pre {} exit {} receipts {}".format(probe.pre, probe.code, probe.receipts))
        baseline = harness.expected("baseline.json")["outputs"]
        for rel in OUTPUTS:
            name = os.path.basename(rel)
            self.check(sha256(p.path(rel)) == baseline[name]["sha256"], p,
                       "step 4: {} differs from expected/baseline.json".format(rel))
        p.space_outputs([(rel, result.receipts[0]) for rel, result in zip(OUTPUTS, results)])

        # 5. Mycelium's lineage manifest: three runs and one inline command
        p.lineage()
        with open(p.path(".living", "log", "data-lineage", p.session + ".json")) as handle:
            actions = json.load(handle)["actions"]
        self.check([a["script"] for a in actions] == [p.path(s) for s in SCRIPTS] + [None], p,
                   "step 5: lineage actions {}".format(actions))

        # 6. verify report
        code, report, err = p.verify("report", digest)
        self.check(code == 0, p, "step 6: verify report exited {}: {}".format(code, err))
        self.check(harness.status_line(report) == "Verify status: CONFORMS", p, "step 6: report:\n" + report)
        claims = harness.expected("claims.json")
        self.check("- `{}`: {} verified (0 via transform), 0 mismatch, 0 unverified, 0 explore-only; {} other "
                   "number(s) not claimed".format(claims["doc"], len(claims["verified"]), len(claims["not_claims"]))
                   in report, p, "step 6: claims: " + report)
        self.check("Fact tags in `{}` Key Findings: 5 agent-derived.".format(claims["doc"]) in report, p,
                   "step 6: fact tags: " + report)
        for script in SCRIPTS:
            # Claude Code's PostToolUse carries no exit code, so the row reads
            # `ran (exit status not recorded)` until E3; either form of `ran` is accepted here.
            row = [line for line in report.splitlines() if line.startswith("| `{}` |".format(script))]
            self.check(len(row) == 1 and row[0].split("|")[2].strip().startswith("ran"), p,
                       "step 6: script row for {}: {}".format(script, row))
        for rel, result in zip(OUTPUTS, results):
            row = [line for line in report.splitlines() if line.startswith("| `{}` |".format(rel))]
            self.check(len(row) == 1 and "`{}` at".format(result.command) in row[0], p,
                       "step 6: output {} not tied to its run: {}".format(rel, row))
        self.check("1 inline command(s)" in report, p, "step 6: no inline-command info:\n" + report)
        self.check("analysis folder `{}`".format(A) in report, p, "step 6: analysis folder:\n" + report)

        # 7. verify write, then commit the provenance (and F-001's ledger cell)
        p.fill_ledger(digest)
        code, out, err = p.verify("write", digest, "--analysis-dir", A)
        self.check(code == 0 and harness.status_line(out) == "Verify status: CONFORMS", p,
                   "step 7: verify write exited {}:\n{}{}".format(code, out, err))
        for name in ("PROVENANCE.md", "plan-{}.md".format(digest), "receipts-{}.jsonl".format(digest),
                     "outputs-{}.tsv".format(digest)):
            self.check(os.path.isfile(p.path(A, "provenance", name)), p, "step 7: no provenance/" + name)
        p.git("add", "-A")
        p.git("commit", "-q", "-m", "provenance for plan " + digest)

        # 8. verify status: one row
        code, out, err = p.verify("status", "--json")
        rows = json.loads(out) if code == 0 else []
        self.check(len(rows) == 1 and rows[0]["verified"] == "CONFORMS" and rows[0]["manifest"] == "listed: active"
                   and rows[0]["lint"] == "clean" and rows[0]["hash"] == digest, p, "step 8: status: " + out + err)

        # 9. verify stale
        code, out, err = p.verify("stale")
        self.check(code == 0 and out.strip().startswith("0 of 1 verified plans stale"), p, "step 9: " + out + err)

        # 10. decision-status --term normalisation: entries 1, 4, 5 in date order, raw status fields
        code, out, err = p.stdin_skill("decision-status", "decision_threads.py",
                                       "--living-dir .living --term normalisation --json")
        entries = json.loads(out) if code == 0 else []
        self.check([(e["date"], e["status"]) for e in entries]
                   == [("2026-03-02", "confirmed"), ("2026-05-10", "held"), ("2026-07-15", "confirmed")],
                   p, "step 10: " + out + err)

        # 11. new-analysis scaffold; a second run on the same dest refuses
        skill_dir = os.path.join(harness.SKILLS, "new-analysis")
        command = "python3 - --dest=analysis/followup --templates={} < {}".format(
            harness.sh_quote(os.path.join(skill_dir, "templates")),
            harness.sh_quote(os.path.join(skill_dir, "scripts", "new_analysis.py")))
        code, out, err = p.skill("new-analysis", command)
        self.check(code == 0 and "created analysis/followup/" in out and "### followup" in out, p,
                   "step 11: " + out + err)
        code, out, err = p.skill("new-analysis", command)
        self.check(code != 0 and "refused:" in out + err, p, "step 11: second run: " + out + err)
        return digest

    def test_baseline_chain(self):
        """With R if Rscript is on PATH (03 runs for real), else as test_baseline_chain_without_r."""
        self.run_chain(self.project())

    def test_baseline_chain_without_r(self):
        """R hidden from PATH: 03 is an effect that writes expected/summary.tsv; its receipt is real."""
        project = self.project(r=False)
        code, out, err = project.shell("command -v Rscript")
        self.assertNotEqual(code, 0, "Rscript still on PATH: " + out)
        self.run_chain(project)

    def test_stale_and_status_after_an_edit(self):
        """E4: editing a verified plan's script makes `stale` and `status` name it."""
        p = self.project(r=False)
        digest = self.run_chain(p)
        p.edit(SCRIPTS[1], lambda text: text + "\n# tweak\n")
        code, out, err = p.verify("stale")
        self.assertEqual(code, 0, err)
        self.assertIn("## Plan {} - `{}`".format(digest, A), out)
        self.assertIn("- script `{}` edited since it ran at".format(SCRIPTS[1]), out)
        self.assertTrue(out.strip().endswith("1 of 1 verified plans stale."), out)
        code, out, err = p.verify("status", "--json")
        self.assertEqual([r["stale"] for r in json.loads(out)], ["1 change(s)"], out + err)


@unittest.skipUnless(harness.git_available(), "git is not installed")
class Defects(unittest.TestCase):
    """One case per planted defect (design section 8); the methods are added from defects.DEFECTS."""


def defect_case(d):
    def test(self):
        project = harness.Project.fresh()
        self.addCleanup(project.close)
        outcome = d.run(project)
        want = {k: v for k, v in d.expect.items() if k != "messages"}
        got = {k: outcome.get(k) for k in want}
        absent = [m for m in d.expect.get("messages", []) if m not in outcome.get("text", "")]
        if got != want or absent:
            self.fail("{}: expected {}, got {}; messages not found: {}\noutput:\n{}\nchain:\n  {}".format(
                d.id, want, got, absent, outcome.get("text", ""), "\n  ".join(project.log)))
    test.__doc__ = "{}: {}{}".format(d.id, "known miss" if d.known_miss else "caught by " + d.caught_by,
                                     ", xfail until " + d.xfail_task if d.xfail_task else "")
    return unittest.expectedFailure(test) if d.xfail_task else test


for _defect in defects.DEFECTS:
    setattr(Defects, "test_" + _defect.id.replace("-", "_"), defect_case(_defect))


def checklist():
    """{row name: Check cell} of llm-failure-modes.md, plus analysis-decisions.md rows mapped to None:
    that file has no Check column, so its rows make no claim that a tool catches them."""
    rows = {}
    for name in ("llm-failure-modes.md", "analysis-decisions.md"):
        with open(os.path.join(REFERENCES, name), encoding="utf-8") as handle:
            for line in handle:
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if line.startswith("| ") and cells[0] not in ("Failure mode", "Decision point", "---"):
                    rows[cells[0]] = cells[-1] if name.startswith("llm") else None
    return rows


TOOLS = ("data-contract-check", "verify", "approval gate")
ROADMAP = os.path.join(harness.REPO, "docs", "roadmap")


def claimed_tool(check):
    """The tool a Check cell credits, fully or as `partial: <tool> (...)`; None if it credits none."""
    for part in (check or "").split(";"):
        part = part.strip()
        if part.startswith("partial:"):
            part = part[len("partial:"):].split("(")[0].strip()
        if part in TOOLS:
            return part
    return None


FAMILY = {"DC": {"data-contract-check", "none"}, "G": {"approval gate"}, "V": {"verify", "none"},
          "S": {"verify"}, "M": {"decision-status"}, "KB": {"approval gate", "verify"}}
NO_FULL_CLAIM = ("none", "partial:", "planned:", "cross-ref:")


class Catalog(unittest.TestCase):
    """Contract tests on defects.DEFECTS (design section 9); no project needed."""

    def test_covers_name_real_rows(self):
        rows = checklist()
        bad = [(d.id, c) for d in defects.DEFECTS for c in d.covers if c not in rows and not c.startswith("tool:")]
        self.assertEqual(bad, [])

    def test_known_misses_cover_an_unclaimed_row(self):
        rows = checklist()
        bad = [d.id for d in defects.DEFECTS if d.known_miss and not any(
            c in rows and (rows[c] is None or rows[c].startswith(NO_FULL_CLAIM)) for c in d.covers)]
        self.assertEqual(bad, [])

    def test_claimed_tools_catch_a_defect(self):
        caught = {(c, d.caught_by) for d in defects.DEFECTS if not d.known_miss for c in d.covers}
        missing = [(row, tool) for row, tool in ((r, claimed_tool(c)) for r, c in checklist().items())
                   if tool and (row, tool) not in caught]
        self.assertEqual(missing, [])

    def test_tasks_are_roadmap_headings(self):
        headings = set()
        for name in os.listdir(ROADMAP):
            with open(os.path.join(ROADMAP, name), encoding="utf-8") as handle:
                headings.update(line[4:].split(":")[0] for line in handle if line.startswith("### "))
        tasks = defects.LATER + [d.xfail_task for d in defects.DEFECTS if d.xfail_task]
        self.assertEqual([t for t in tasks if t not in headings], [])

    def test_ids_unique_and_families_match(self):
        ids = [d.id for d in defects.DEFECTS]
        self.assertEqual(sorted(set(i for i in ids if ids.count(i) > 1)), [])
        bad = [d.id for d in defects.DEFECTS if d.caught_by not in FAMILY[d.id.split("-")[0]]
               or d.known_miss != (d.caught_by == "none")]
        self.assertEqual(bad, [])


class BashEvents(unittest.TestCase):
    """agent_bash sends Claude Code's event shapes, and the failure event only if hooks.json has it."""

    def setUp(self):
        self.sent = []
        self.project = harness.Project(tempfile.mkdtemp(prefix="mx-e2e-"))
        self.addCleanup(self.project.close)
        os.makedirs(self.project.root)
        self.project.hook = lambda entry, payload, cwd=None: self.sent.append((entry, payload))

    def test_success_has_no_exit_code(self):
        self.project.agent_bash("true")
        entry, payload = self.sent[-1]
        self.assertEqual((entry, payload["hook_event_name"]), ("post", "PostToolUse"))
        self.assertEqual(sorted(payload["tool_response"]), ["interrupted", "isImage", "stderr", "stdout"])

    def test_failure_needs_its_event_registered(self):
        self.project.events = {"PreToolUse": "tool", "PostToolUse": "post"}
        result = self.project.agent_bash("exit 3")
        self.assertEqual((result.code, result.event, len(self.sent)), (3, "PostToolUseFailure", 1))
        self.project.events["PostToolUseFailure"] = "post"
        self.project.agent_bash("echo no >&2; exit 3")
        entry, payload = self.sent[-1]
        self.assertEqual(payload["hook_event_name"], "PostToolUseFailure")
        self.assertEqual(payload["error"].splitlines(), ["Exit code 3", "no"])
        self.assertNotIn("tool_response", payload)

    def test_legacy_shape(self):
        self.project.agent_bash("exit 2", response="legacy")
        self.assertEqual(self.sent[-1][1]["tool_response"]["exit_code"], 2)

    def test_hooks_json_is_read(self):
        events = harness.registered_events()
        self.assertEqual([events.get(e) for e in ("PreToolUse", "PostToolUse", "Stop", "UserPromptSubmit")],
                         ["tool", "post", "stop", "prompt"])


# A line scilintr's R016 flags (hardcoded sample IDs), planted in each R place verify lints.
R016 = 'keep <- meta[meta$sample_id %in% c("S01", "S02", "S03"), ]'
# Rscript-lint that flags each R016 line it is given, in the format verify parses, and exits 1.
FLAG_R016 = """#!/bin/sh
found=0
for a in "$@"; do
  [ -f "$a" ] || continue
  for n in $(grep -n 'sample_id %in% c(' "$a" | cut -d: -f1); do echo "$a:$n:1: [R016] hardcoded sample IDs"; found=1; done
done
exit $found
"""
# Rscript-lint as scilintr 0.1.1's `Rscript -e 'scilintr::main()' <args>` behaves (E4 probe,
# docs/design/e4-real-use.md section 6): only the first argument is read, as a project root; a
# file root lints nothing; findings print as `path:N [RULE/severity] message`; exit is always 0.
SCILINTR_0_1_1 = """#!/bin/sh
shift 2
root="$1"
if [ -d "$root" ]; then
  n=$(grep -rln 'sample_id %in% c(' "$root" | while read f; do echo "$f:1 [R016/warning] R016: hardcoded sample IDs"; done)
  [ -n "$n" ] && { echo "$n"; echo "scilintr: $(echo "$n" | wc -l | tr -d ' ') finding(s)" >&2; exit 0; }
fi
echo "scilintr: no findings" >&2
exit 0
"""


@unittest.skipUnless(harness.git_available(), "git is not installed")
class RealUse(unittest.TestCase):
    """E4: features with no record of real use, on the fixture (docs/design/e4-real-use.md)."""
    maxDiff = None

    def project(self):
        project = harness.Project.fresh(r=False)
        self.addCleanup(project.close)
        return project

    def prompt(self, p, text):
        return ((p.hook("prompt", {"prompt": text}) or {}).get("systemMessage") or "")

    def stop(self, p):
        return ((p.hook("stop", {"last_assistant_message": "done", "stop_hook_active": False}) or {})
                .get("systemMessage") or "")

    def test_hints(self):
        p = self.project()
        ask = "re-run the differential analysis"
        self.assertEqual(self.prompt(p, ask), "", "hints must be off by default")
        self.assertIn("command hints on for this repository", self.prompt(p, "hints on"))
        self.assertEqual(self.prompt(p, ask), "mycelium-extra hint: this fits /mycelium-extra:grill")
        self.assertEqual(self.prompt(p, "review the code"), "mycelium-extra hint: this fits /mycelium:review")
        self.assertEqual(self.prompt(p, "run mycelium analyze on this"), "")
        self.assertEqual(self.prompt(p, "/mycelium:analyze differential"), "")
        digest = p.approve(harness.plan_text())[0]
        self.assertEqual(self.prompt(p, ask), "", "no grill hint while a plan is approved")
        p.run_step(SCRIPTS[0])
        self.assertEqual(self.stop(p), "mycelium-extra hint: next, `/mycelium-extra:verify {}`".format(digest))
        self.assertEqual(self.stop(p), "", "the verify hint is shown once per session")
        self.assertIn("command hints off", self.prompt(p, "hints off"))
        self.assertEqual(self.prompt(p, ask), "")

    def test_verify_explore(self):
        p = self.project()
        self.assertIn("exploratory runs allowed", self.prompt(p, "allow explore"))
        for _ in range(2):
            run = p.run_step(SCRIPTS[0], prefix="MYCELIUM_EXTRA_EXPLORE=1 ")
            self.assertEqual([r.get("explore") for r in run.receipts], [True])
        self.assertIn("2 exploratory run(s) this session are not reportable", self.stop(p))
        p.edit(SCRIPTS[0], lambda text: text + "\n# edited\n")
        code, out, err = p.verify("explore", "--session", p.session)
        self.assertEqual(code, 0, err)
        self.assertIn("1. `python3 {}`\n   - ran: `{}`".format(SCRIPTS[0], SCRIPTS[0]), out)
        self.assertIn("(2 runs), exit 0", out)
        self.assertIn("script `{}` edited since this run".format(SCRIPTS[0]), out)
        self.assertNotIn("MYCELIUM_EXTRA_EXPLORE=1 python3", out)

    def plant_r016(self, p):
        """R016 in 03_summary.R, in a report.Rmd chunk, and in an R notebook inside the analysis folder."""
        os.makedirs(p.path(A, "notebooks"))
        with open(p.path("nbs", "r_explore.ipynb"), encoding="utf-8") as handle:
            nb = json.load(handle)
        nb["cells"][1]["source"].append("\n" + R016)
        with open(p.path(A, "notebooks", "r_explore.ipynb"), "w", encoding="utf-8") as handle:
            json.dump(nb, handle)
        p.edit(SCRIPTS[2], lambda text: text + "\n" + R016 + "\n")
        p.edit(A + "/reports/report.Rmd", lambda text: text.replace("```{r", "```{r}\n" + R016 + "\n```\n\n```{r", 1))
        p.commit("plant R016")
        with open(p.path(A, "reports", "report.Rmd"), encoding="utf-8") as handle:
            return [n for n, line in enumerate(handle, 1) if line.strip() == R016][0]

    def lint_report(self, p, fake=None):
        if fake:
            with open(os.path.join(p.bin, "Rscript-lint"), "w", encoding="utf-8") as handle:
                handle.write(fake)
        digest = p.run_plan()[0]
        code, out, err = p.verify("report", digest)
        self.assertEqual(code, 0, err)
        return out

    def test_r_code_reaches_r_lint(self):
        """.Rmd chunks keep the document's line numbers; notebook findings cite the code cell."""
        p = self.project()
        rmd_line = self.plant_r016(p)
        out = self.lint_report(p, FLAG_R016)
        self.assertEqual(harness.status_line(out), "Verify status: DOES_NOT_CONFORM", out)
        self.assertIn("3 scilintr finding(s) remain in R code (3 R016)", out)
        self.assertIn("- `{}/reports/report.Rmd:{}` [R016]".format(A, rmd_line), out)
        self.assertIn("- `{}/notebooks/r_explore.ipynb[code cell 1]:3` [R016]".format(A), out)
        self.assertIn("- `{}:18` [R016]".format(SCRIPTS[2]), out)

    @unittest.expectedFailure  # until E6: scilintr 0.1.1's R CLI lints nothing it is given as files
    def test_r_findings_block_with_scilintr_0_1_1(self):
        p = self.project()
        self.plant_r016(p)
        out = self.lint_report(p, SCILINTR_0_1_1)
        self.assertNotIn("R file(s) clean", out)
        self.assertEqual(harness.status_line(out), "Verify status: DOES_NOT_CONFORM", out)

    @unittest.skipUnless(harness.real_rscript(), "real tools off (MX_E2E_REAL_TOOLS=1, MX_E2E_RSCRIPT)")
    @unittest.expectedFailure  # until E6
    def test_r_findings_block_with_real_scilintr(self):
        p = self.project()
        p.write_fakes(rscript=harness.real_rscript())
        self.plant_r016(p)
        out = self.lint_report(p)
        self.assertNotIn("R file(s) clean", out)
        self.assertEqual(harness.status_line(out), "Verify status: DOES_NOT_CONFORM", out)


if __name__ == "__main__":
    unittest.main()
