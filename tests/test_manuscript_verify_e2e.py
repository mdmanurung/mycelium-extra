"""Simulated-host oracle for the manuscript-audit `verify` scenarios
(docs/design/2026-10-26-manuscript-native-verify.md).

Run: python3 tests/test_manuscript_verify_e2e.py
     python3 tests/test_manuscript_verify_e2e.py --record OUT.json   (writes the observed outcomes)

SIMULATED HOST, not native: the real hooks/gate_run.py receives the event shapes Claude Code sends
(tests/e2e/harness.py), the producer and the checker really run as subprocesses between their
PreToolUse and PostToolUse/PostToolUseFailure, and the real verify reads the result. No model and no
Claude Code process take part; the native run is the runbook in the design note.
"""

import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "e2e"))
import harness  # noqa: E402
import manuscript_scenario as ms  # noqa: E402

TOLERANCE = 5.0  # verify's clock-skew allowance (skills/verify/scripts/verify.py, TOLERANCE)


class ManuscriptProject(harness.Project):
    """A gated scratch project from tests/e2e/manuscript_scenario.py instead of the vaccine fixture."""

    scenario = "S1"

    @classmethod
    def for_scenario(cls, scenario):
        cls_ = type("ManuscriptProject" + scenario, (cls,), {"scenario": scenario})
        return cls_.fresh(r=False)

    def _setup(self):
        os.makedirs(self.root)
        os.makedirs(self.bin)
        os.makedirs(self.home)
        self.write_fakes()
        ms.write_project(self.root, self.scenario)
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "manuscript scenario " + self.scenario)
        self.init_output = self.init()
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "mycelium-extra init")


def rewrite_evidence(project):
    """The evidence file is rewritten outside any attempt (an agent `tidying` or forging the result)."""
    path = project.path(ms.EVIDENCE)
    with open(path, encoding="utf-8") as handle:
        result = json.load(handle)
    result.update(status="pass", exit_code=0)
    for check in result.get("checks") or []:
        check["status"] = "pass"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(result, indent=1))
    project.log.append("rewrote " + ms.EVIDENCE + " outside any attempt")


def run_scenario(name):
    """Drive one scenario; returns what was observed. S5b: the check fails, then a pass is forged at once."""
    base = "S2" if name == "S5b" else name
    p = ManuscriptProject.for_scenario(base)
    try:
        digest, notice, _ = p.approve(ms.plan_text())
        steps = [p.agent_bash(ms.PRODUCER_CMD)]
        if name == "S4":  # the researcher-approved contract is edited after approval, before the check
            p.edit(ms.CONTRACT, lambda t: t.replace('"fraction"\n      ]', '"fraction_pct"\n      ]', 1))
        if name != "S3":
            steps.append(p.agent_bash(ms.CHECK_CMD))
        if name == "S5":
            time.sleep(TOLERANCE + 1.5)  # beyond verify's clock-skew allowance, in real time
            rewrite_evidence(p)
        if name == "S5b":
            rewrite_evidence(p)
        code, text, err = p.verify("report", digest)
        jcode, jtext, jerr = p.verify("report", digest, "--json")
        if code or jcode:
            raise harness.HarnessError("verify exited {}/{}: {}{}".format(code, jcode, err, jerr))
        report = json.loads(jtext)
        validation = dict((v["id"], v) for v in report.get("validation") or [])
        findings = [line[2:] for line in text.splitlines() if line.startswith("- **block**") or line.startswith("- **gap**")]
        return {
            "scenario": name, "host": "simulated (Claude Code event shapes; real gate, checker and verify)",
            "digest": digest, "card_has_binding": ms.BINDING_ID in notice,
            "steps": [{"command": s.command, "denied": s.denied, "exit": s.code, "post_event": s.event,
                       "deny_reason": ((s.pre or {}).get("hookSpecificOutput") or {}).get("permissionDecisionReason")}
                      for s in steps],
            "outcome": (validation.get(ms.BINDING_ID) or {}).get("outcome"),
            "reason": (validation.get(ms.BINDING_ID) or {}).get("reason"),
            "status": text.rstrip().rsplit("Verify status: ", 1)[-1].strip(),
            "json_status": report.get("status"),
            "findings": findings, "log": list(p.log),
        }
    finally:
        p.close()


@unittest.skipUnless(harness.git_available(), "git is not installed")
class ManuscriptVerifyOracle(unittest.TestCase):
    maxDiff = None

    def scenario(self, name):
        observed = run_scenario(name)
        self.assertTrue(observed["card_has_binding"], observed)
        self.assertEqual(observed["status"], observed["json_status"], observed)
        return observed

    def test_s1_a_matched_passing_check_conforms(self):
        o = self.scenario("S1")
        self.assertEqual([(s["denied"], s["exit"], s["post_event"]) for s in o["steps"]],
                         [(False, 0, "PostToolUse"), (False, 0, "PostToolUse")], o)
        self.assertEqual(o["outcome"], "passed", o)
        self.assertEqual(o["status"], "CONFORMS", o)

    def test_s2_a_missing_plotting_column_fails_and_names_it(self):
        o = self.scenario("S2")
        self.assertEqual((o["steps"][1]["exit"], o["steps"][1]["post_event"]), (2, "PostToolUseFailure"), o)
        self.assertEqual(o["outcome"], "failed", o)
        self.assertIn("Missing declared plotting columns: fraction", o["reason"], o)
        self.assertEqual(o["status"], "DOES_NOT_CONFORM", o)

    def test_s3_a_check_that_never_ran_is_not_established(self):
        o = self.scenario("S3")
        self.assertEqual(len(o["steps"]), 1, o)
        self.assertEqual(o["outcome"], "not run", o)
        self.assertIn("no matched run", o["reason"], o)
        self.assertNotEqual(o["status"], "CONFORMS", o)
        self.assertTrue(any("not established" in f for f in o["findings"]), o)

    def test_s4_a_contract_edited_after_approval_is_denied_and_changed(self):
        o = self.scenario("S4")
        check = o["steps"][1]
        self.assertTrue(check["denied"], o)
        self.assertIn("manuscript_checks.json changed", check["deny_reason"], o)
        self.assertEqual(o["outcome"], "changed", o)
        self.assertNotEqual(o["status"], "CONFORMS", o)

    def test_s5_evidence_rewritten_after_the_attempt_is_unattributable(self):
        o = self.scenario("S5")
        self.assertEqual(o["outcome"], "unattributable", o)
        self.assertIn("modified after the attempt", o["reason"], o)
        self.assertNotEqual(o["status"], "CONFORMS", o)

    def test_s5b_a_forged_pass_over_a_failed_check_still_fails(self):  # the recorded exit code decides
        o = self.scenario("S5b")
        self.assertEqual(o["steps"][1]["exit"], 2, o)
        self.assertEqual(o["outcome"], "failed", o)
        self.assertEqual(o["status"], "DOES_NOT_CONFORM", o)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--record":
        observed = [run_scenario(name) for name in ("S1", "S2", "S3", "S4", "S5", "S5b")]
        with open(sys.argv[2], "w", encoding="utf-8") as handle:
            json.dump(observed, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print("\n".join("{scenario}: {outcome} / {status}".format(**o) for o in observed))
    else:
        unittest.main()
