"""Approval-flow fixes from the function audit: run: python3 hooks/tests/test_approval_flow_fixes.py

X1 a baseline approval that is expired or from another session no longer gives the change-only card.
X2 an approval approved by an event with no session id no longer claims a run may follow.
X3 a prompt that starts like a gate command but does not parse says nothing changed, and odd spacing parses.
X4/X8 two session ids that sanitise to one name no longer share an explore grant or other state.
X6 a pinned input the time limit kept from being re-checked is not receipted as checked.
X7 a truncated launch record is reported unreadable and kept, not called older than 24 h.
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

import test_gate  # noqa: E402  (after the path is set)

GATE = test_gate.GATE
PLAN_WITH_INPUT = "Inputs: data/in.tsv\n\n" + test_gate.PLAN


class ApprovalFlowFixTest(test_gate.GateTest):
    def path(self, *parts):
        return os.path.join(self.root, ".mycelium-extra", *parts)

    def gate(self):
        sys.dont_write_bytecode = True
        sys.path.insert(0, os.path.dirname(GATE))
        import gate
        return gate

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write(text)

    def show(self, text, session="s1"):
        notice = self.hook("stop", {"last_assistant_message": text}, session=session)
        return notice["systemMessage"].split("approve plan ")[1][:8]

    def prompt(self, text, session="s1"):
        return self.hook("prompt", {"prompt": text}, session=session)["systemMessage"]

    def run_gated(self, command="python analysis/x.py", session="s1"):
        return self.hook("tool", {"tool_name": "Bash", "tool_input": {"command": command}}, session=session)

    def post(self, command="python analysis/x.py", session="s1"):
        return self.hook("post", {"tool_name": "Bash", "tool_input": {"command": command},
                                  "tool_response": {"stdout": ""}}, session=session)

    def receipts(self):
        if not os.path.isfile(self.path("receipts.jsonl")):
            return []
        with open(self.path("receipts.jsonl")) as handle:
            return [json.loads(line) for line in handle]

    def expire(self, digest):
        path = self.path("approvals", digest + ".json")
        with open(path) as handle:
            record = json.load(handle)
        record["approved_at"] -= 30 * 24 * 3600
        with open(path, "w") as handle:
            json.dump(record, handle)

    # X1: the change-only card claims the unchanged steps stay "as approved". That is only true while the
    # baseline approval is active in this session.

    def test_an_expired_baseline_gets_the_whole_card(self):
        self.write("analysis/a/04_plot.py", "print(1)\n")
        digest, _ = self.approve(self.CARD_PLAN)
        self.expire(digest)
        card = self.card(self.amended())
        self.assertNotIn("amendment to", card)
        self.assertIn("Choices", card, "the whole card names the choices, not only the delta")

    def test_another_sessions_baseline_gets_the_whole_card(self):
        self.write("analysis/a/04_plot.py", "print(1)\n")
        self.approve(self.CARD_PLAN)  # approved in s1
        card = self.hook("stop", {"last_assistant_message": self.amended()}, session="s2")["systemMessage"]
        self.assertNotIn("amendment to", card)
        self.assertIn("Choices", card)

    def test_a_fresh_baseline_in_this_session_still_gets_the_change_only_card(self):
        self.write("analysis/a/04_plot.py", "print(1)\n")
        self.approve(self.CARD_PLAN)
        self.assertIn("amendment to", self.card(self.amended()))

    # X2: a run is matched to its approval by session, so an approval recorded without one authorizes nothing.

    def test_an_approval_without_a_session_id_does_not_claim_a_run_may_follow(self):
        notice = self.hook("stop", {"last_assistant_message": test_gate.PLAN}, session=None)
        digest = notice["systemMessage"].split("approve plan ")[1][:8]
        message = self.prompt("approve plan " + digest, session=None)
        self.assertIn("no session id", message)
        self.assertNotIn("may run for", message)
        self.assertTrue(self.denied(self.run_gated(session="s1")))
        self.assertTrue(self.denied(self.run_gated(session=None)), "the approval cannot authorize its own session either")

    # X3: a near-miss command used to be ignored in silence.

    def test_a_near_miss_command_says_nothing_changed(self):
        for prompt in ("send packet 0123456789ab please", "allow explore 1234567", "card 1234", "hints maybe"):
            message = self.prompt(prompt)
            self.assertIn("did not parse as a command", message, prompt)
            self.assertIn("nothing changed", message, prompt)
        for prompt in ("focus on cluster 3", "approve the idea of using a mixed model first"):
            self.assertNotIn("did not parse", json.dumps(self.hook("prompt", {"prompt": prompt})), prompt)  # prose, not a command

    def test_command_spacing_is_tolerated(self):
        self.assertIn("no pending plan", self.prompt("approve plan  1234abcd"))
        self.assertIn("allowed", self.prompt("allow  explore"))

    # X4/X8: two ids that sanitise to one name shared one grant file.

    def test_session_names_do_not_collide(self):
        gate = self.gate()
        self.assertNotEqual(gate.safe_session("a.b"), gate.safe_session("a/b"))
        self.assertEqual(gate.safe_session("s1"), "s1", "an already safe id keeps its name")
        self.assertEqual(gate.safe_session(None), "unknown")

    def test_an_explore_grant_is_not_shared_with_an_id_that_sanitises_alike(self):
        command = "MYCELIUM_EXTRA_EXPLORE=1 python analysis/x.py"
        self.assertIn("allowed", self.prompt("allow explore", session="a.b"))
        self.assertIsNone(self.run_gated(command, session="a.b"))
        self.assertTrue(self.denied(self.run_gated(command, session="a/b")))

    # X6: pins_checked said true although the time limit kept the pin from being read again.

    def test_a_pin_the_time_limit_skipped_is_not_reported_as_checked(self):
        # a pinned folder past the hashing deadline is skipped, not compared
        self.write("data/in.tsv", "a\n")
        digest = self.show("Inputs: data/\n\n" + test_gate.PLAN)
        self.prompt("approve plan " + digest)
        self.config({"pin_seconds": 0})  # every hash is now past its deadline
        result = self.run_gated()
        self.assertIn("not re-checked", result["systemMessage"])
        self.post()
        receipt, = self.receipts()
        self.assertFalse(receipt["pins_checked"])
        self.assertEqual(receipt["pins_unchecked"], ["data"])
        self.assertTrue(receipt["pins"])

    def test_a_pin_read_in_time_is_still_reported_as_checked(self):
        self.write("data/in.tsv", "a\n")
        digest = self.show(PLAN_WITH_INPUT)
        self.prompt("approve plan " + digest)
        self.run_gated()
        self.post()
        receipt, = self.receipts()
        self.assertTrue(receipt["pins_checked"])
        self.assertEqual(receipt["pins_unchecked"], [])

    # X7: a crash-truncated launch record was called "older than 24 h" and its bytes were lost.

    def test_a_truncated_launch_record_is_reported_unreadable_and_kept(self):
        self.write("data/in.tsv", "a\n")
        digest = self.show(PLAN_WITH_INPUT)
        self.prompt("approve plan " + digest)
        self.assertIsNone(self.run_gated())
        folder = self.path("launches")
        names = [n for n in os.listdir(folder) if n.endswith(".json")]
        self.assertEqual(len(names), 1)
        with open(os.path.join(folder, names[0]), "w") as handle:
            handle.write('{"ts": ')  # a crash in the middle of the write
        self.post()
        receipt, = self.receipts()
        self.assertEqual(receipt["launch_match"], "unmatched")
        self.assertIn("unreadable", receipt["launch_note"])
        self.assertNotIn("older than", receipt["launch_note"])
        kept = os.listdir(os.path.join(folder, "abandoned"))
        self.assertTrue(any(name.startswith("unreadable-") for name in kept), kept)


# The harness class carries the whole gate suite; this file runs only its own tests.
for _name in dir(test_gate.GateTest):
    if _name.startswith("test_"):
        setattr(ApprovalFlowFixTest, _name, None)
del _name


if __name__ == "__main__":
    unittest.main(verbosity=2)
