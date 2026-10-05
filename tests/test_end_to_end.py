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


if __name__ == "__main__":
    unittest.main()
