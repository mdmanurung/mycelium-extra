"""Contract checks for the read-only plan-review skill.

Run: python3 skills/plan-review/tests/test_plan_review.py
"""

import os
import unittest


SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(relative):
    with open(os.path.join(SKILL, relative), encoding="utf-8") as handle:
        return handle.read()


class PlanReviewContractTest(unittest.TestCase):
    def test_skill_is_discoverable_and_references_exist(self):
        skill = read("SKILL.md")
        self.assertTrue(skill.startswith("---\nname: plan-review\n"))
        self.assertIn("description:", skill.split("---", 2)[1])
        for name in ("review-contract.md", "codex-review.md", "biomni-review.md",
                     "synthesis.md"):
            self.assertIn("references/" + name, skill)
            self.assertTrue(os.path.isfile(os.path.join(SKILL, "references", name)))

    def test_review_cannot_be_mistaken_for_execution_or_approval(self):
        skill = read("SKILL.md")
        codex = read("references/codex-review.md")
        biomni = read("references/biomni-review.md")
        self.assertIn("do not run project analysis", skill)
        self.assertIn("Do not rewrite the plan", skill)
        self.assertIn("A prior approval does not cover a changed plan", skill)
        self.assertIn("--sandbox read-only", codex)
        self.assertIn("unexpected changes", codex.lower())
        self.assertIn("--ignore-user-config", codex)
        self.assertIn("Do not call `upload_file`", biomni)
        self.assertIn("`auto_mode` false", biomni)
        self.assertIn("start only after the user agrees", biomni)
        self.assertIn("not a project result", biomni)
        self.assertIn("send only after the user agrees", skill)

    def test_missing_and_conflicting_reviews_stay_visible(self):
        skill = read("SKILL.md")
        contract = read("references/review-contract.md")
        synthesis = read("references/synthesis.md")
        self.assertIn("status: complete", contract)
        self.assertIn("unavailable | invalid", contract)
        self.assertIn("An empty `issues` list is meaningful only", contract)
        self.assertIn("do not label single-reviewer findings as agreement", synthesis)
        self.assertIn("Conflicts", synthesis)
        self.assertIn("User decision required", synthesis)
        self.assertIn("cannot impersonate an independent second Codex reviewer", skill)

    def test_redaction_rules_are_backed_by_a_check_and_are_specific(self):
        skill = read("SKILL.md")
        contract = read("references/review-contract.md")
        codex = read("references/codex-review.md")
        biomni = read("references/biomni-review.md")
        synthesis = read("references/synthesis.md")
        self.assertTrue(os.path.isfile(os.path.join(SKILL, "scripts", "presend_check.py")))
        self.assertIn("scripts/presend_check.py", skill)
        self.assertIn("Exit 3 means flags with an empty or malformed `redactions:`", skill)
        self.assertIn("Never write the removed value there", contract)
        self.assertIn("`[]` means nothing was removed, and is acceptable only after the check", contract)
        for item in ("home-directory paths", "contact details", "ID columns", "free-text clinical notes"):
            self.assertIn(item, contract)
        self.assertIn("a clean result is not evidence that nothing sensitive remains", contract.replace("Say the check is pattern-based and ", ""))
        self.assertIn("Codex reads the repository, not only the packet", codex)
        self.assertIn("data-free copy", codex)
        self.assertIn("An instruction is not enforcement", codex)
        self.assertIn("the pre-send check's output", biomni)
        self.assertIn("pre-send check's result", synthesis)
        self.assertIn("never report it as clean", skill)

    def test_packet_and_provenance_require_evidence(self):
        contract = read("references/review-contract.md")
        synthesis = read("references/synthesis.md")
        for field in ("estimand:", "biological_unit:", "proposed_plan:",
                      "known_decisions:", "unknowns:", "redactions:"):
            self.assertIn(field, contract)
        self.assertIn("identical factual fields", contract)
        self.assertIn("participant identifiers", contract)
        self.assertIn("user (accepted review: codex)", contract)
        self.assertIn("user (accepted review: biomni; PMID", contract)
        self.assertIn("Paste this format into the message", contract)
        self.assertIn("Source column is provenance, not permission", contract)
        self.assertIn("Do not edit the original plan", synthesis)

    def test_default_reasons_check_runs_on_the_draft_and_is_advisory(self):
        skill = read("SKILL.md")
        self.assertIn("< <skill-dir>/scripts/default_reasons.py", skill)
        self.assertTrue(os.path.isfile(os.path.join(SKILL, "scripts", "default_reasons.py")))
        self.assertIn("It is advisory: it never blocks", skill)
        self.assertIn("never report it as clean", skill)

    def test_byte_bound_send_sequence_is_documented_and_consent_comes_from_the_gate(self):
        skill = read("SKILL.md")
        contract = read("references/review-contract.md")
        script = read("scripts/review_packet.py")
        for step in ("review_packet.py prepare", "review_packet.py preview", "send packet <first 12",
                     "review_packet.py verify"):
            self.assertIn(step, skill)
        for text in (skill, contract):  # the gate's `send packet` prompt now writes the record
            self.assertNotIn("**Pending:**", text)
            self.assertIn("The approval gate records it as `.mycelium-extra/review-consent/<digest>.json`", text)
        self.assertIn("cooperative, not a sandbox", skill)
        self.assertIn("pending | unavailable | invalid", contract)
        self.assertIn("THIS SCRIPT NEVER WRITES ONE", script)


if __name__ == "__main__":
    unittest.main()
