"""Contract checks for grill's reference files.

Run: python3 skills/grill/tests/test_grill_references.py
"""

import os
import re
import unittest


SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(SKILL))
ROADMAP = os.path.join(REPO, "docs", "roadmap")

# Developer behaviour checks, not read by the agent at run time.
UNLINKED_OK = {"scenarios.md"}

CELL_SPLIT = re.compile(r"(?<!\\)\|")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def table_rows(text):
    """Yield the cells of every body row of every Markdown table."""
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or re.match(r"^\|\s*-{3}", line):
            continue
        cells = [c.strip() for c in CELL_SPLIT.split(line)[1:-1]]
        if cells and cells[0] in ("Failure mode", "Decision point"):
            continue
        yield cells


def failure_modes():
    return list(table_rows(read(os.path.join(SKILL, "references",
                                             "llm-failure-modes.md"))))


class GrillReferenceContractTest(unittest.TestCase):
    def test_skill_links_every_runtime_reference(self):
        skill = read(os.path.join(SKILL, "SKILL.md"))
        for name in sorted(os.listdir(os.path.join(SKILL, "references"))):
            if name.endswith(".md") and name not in UNLINKED_OK:
                self.assertIn("references/" + name, skill,
                              name + " is not linked from SKILL.md")

    def test_skill_walks_failure_modes_after_decisions(self):
        skill = read(os.path.join(SKILL, "SKILL.md"))
        decisions = skill.index("references/analysis-decisions.md")
        modes = skill.index("references/llm-failure-modes.md")
        self.assertLess(decisions, modes)
        self.assertIn("names a guard", skill)
        self.assertIn("never claims a `planned:` check already runs", skill)

    def test_skill_asks_for_the_question_before_retrieving(self):
        skill = read(os.path.join(SKILL, "SKILL.md"))
        self.assertLess(skill.index("## 0. Ask for the question first"),
                        skill.index("## 1. Retrieve before asking"))
        self.assertIn("reminder of what the task is", skill)
        self.assertIn("> Question (user's words):", skill)
        self.assertIn("> Hoped-for claim:", skill)
        self.assertIn("> Question: not stated (the user declined).", skill)

    def test_brief_evidence_carries_provenance_tags(self):
        skill = read(os.path.join(SKILL, "SKILL.md"))
        evidence = skill[skill.index("- **Evidence**"):skill.index("- **Inputs**")]
        for tag in ("[human-stated]", "[agent-derived: ", "[agent-asserted: ",
                    "[agent-asserted: none]", "Facts: "):
            self.assertIn(tag, evidence)

    def test_every_failure_mode_has_four_cells_and_a_guard(self):
        rows = failure_modes()
        self.assertGreaterEqual(len(rows), 25)
        for cells in rows:
            self.assertEqual(len(cells), 4, "malformed row: %r" % (cells,))
            mode, shows, guard, check = cells
            self.assertTrue(mode and shows and guard and check,
                            "empty cell in row %r" % (mode,))

    def test_failure_mode_names_are_unique(self):
        names = [cells[0] for cells in failure_modes()]
        self.assertEqual(len(names), len(set(names)))

    def test_cross_refs_name_existing_decision_points(self):
        decisions = read(os.path.join(SKILL, "references",
                                      "analysis-decisions.md"))
        points = {cells[0] for cells in table_rows(decisions)}
        refs = 0
        for cells in failure_modes():
            for ref in re.findall(r"cross-ref: ([^;]+)", cells[3]):
                refs += 1
                self.assertIn(ref.strip(), points,
                              "unknown decision point: " + ref)
        self.assertGreater(refs, 0)

    def test_check_cells_use_the_legend(self):
        tools = r"(data-contract-check|verify|approval gate)"
        part = re.compile(r"^(none|" + tools + r"|partial: " + tools + r" \([^();]+\)"
                          r"|cross-ref: .+|planned: [A-Z]\d+)$")
        for cells in failure_modes():
            for piece in cells[3].split("; "):
                self.assertRegex(piece, part, "check cell of %r" % (cells[0],))

    def test_planned_checks_name_roadmap_tasks(self):
        if not os.path.isdir(ROADMAP):
            self.skipTest("docs/roadmap/ not present")
        roadmap = "\n".join(read(os.path.join(ROADMAP, name))
                            for name in os.listdir(ROADMAP)
                            if name.endswith(".md"))
        tasks = set(re.findall(r"^#{2,3} ([A-Z]\d+)\b", roadmap, re.M))
        planned = 0
        for cells in failure_modes():
            for task in re.findall(r"planned: ([A-Z]\d+)", cells[3]):
                planned += 1
                self.assertIn(task, tasks, "no roadmap task " + task)
        self.assertGreater(planned, 0)

    def test_scenarios_cover_failure_modes(self):
        scenarios = read(os.path.join(SKILL, "references", "scenarios.md"))
        self.assertIn("## Contrast direction reversed in the metadata",
                      scenarios)
        self.assertIn("## Column named only in the user's prose", scenarios)


if __name__ == "__main__":
    unittest.main()
