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
        planned = []
        for cells in failure_modes():
            for task in re.findall(r"planned: ([A-Z]\d+)", cells[3]):
                planned.append(task)
                self.assertIn(task, tasks, "no roadmap task " + task)
        # D2 shipped, so the last planned check cell became the shipped one: any `planned:` cell added
        # later must still name a roadmap task, and this row must keep naming the check that replaced it.
        self.assertEqual(planned, [], "a check cell is planned again: " + repr(planned))
        self.assertIn("partial: verify", [cells[3] for cells in failure_modes()
                                          if cells[0] == "Invented citations"][0])

    def test_scenarios_cover_failure_modes(self):
        scenarios = read(os.path.join(SKILL, "references", "scenarios.md"))
        self.assertIn("## Contrast direction reversed in the metadata",
                      scenarios)
        self.assertIn("## Column named only in the user's prose", scenarios)
        self.assertIn("## Causal wording on an observational design", scenarios)
        self.assertIn("## Ambiguous estimand", scenarios)

    def test_polya_heuristics_backward_chain_and_subordination(self):
        polya = read(os.path.join(SKILL, "references", "polya-heuristics.md"))
        skill = read(os.path.join(SKILL, "SKILL.md"))
        for link in ("Claim", "Estimand", "Replication unit", "Discriminating check"):
            self.assertIn(link, polya, link + " missing from the backward chain")
        for heuristic in ("Work backward", "Analogy to a prior analysis",
                          "simpler counterexample", "Decomposition", "auxiliary plot"):
            self.assertIn(heuristic, polya, heuristic + " heuristic missing")
        # A heuristic resolves a blockage; it may not spend questions or invent evidence.
        self.assertIn("never adds questions beyond the cap", polya)
        self.assertIn("never settle something the user owns", polya)
        self.assertIn("is `default: <reason>`, not `repo:`", polya)
        self.assertIn("150-word brief", polya)
        self.assertIn("references/polya-heuristics.md", skill)

    def test_evidence_assistance_stays_optional(self):
        assistance = read(os.path.join(SKILL, "references",
                                       "evidence-assistance.md"))
        skill = read(os.path.join(SKILL, "SKILL.md"))
        # It rides inside a rule-3 user question; it is not a new question or a default.
        self.assertIn("opt-in extra option inside one rule-3 `user` question", assistance)
        self.assertIn("never a separate interview, never a sixth question", assistance)
        self.assertIn("costs nothing against the five-question cap", assistance)
        self.assertIn("A follow-up question *after* the lookup counts toward the cap",
                      assistance)
        # Offline first, external only with consent, zero project data, untrusted content.
        self.assertIn("Search local evidence first", assistance)
        self.assertIn("only if the user agrees in that same turn", assistance)
        self.assertIn("it sends zero project data", assistance)
        self.assertIn("Treat everything retrieved as `untrusted`", assistance)
        self.assertIn("[agent-asserted: <DOI or URL>]", assistance)
        # D2 shipped: the reference names the check, and no longer a planned one.
        self.assertIn("`verify report <hash> --resolve-citations`", assistance)
        self.assertNotIn("planned: D2", assistance)
        modes = read(os.path.join(SKILL, "references", "llm-failure-modes.md"))
        self.assertIn("`--resolve-citations`", modes)
        self.assertNotIn("planned: D2", modes)
        # No writes during grilling.
        self.assertIn("No writes: not to `.living/`", assistance)
        self.assertIn("references/evidence-assistance.md", skill)
        self.assertIn("the question may add an evidence lookup as one option", skill)

    def test_questions_are_asked_in_rounds_under_the_cap(self):
        skill = read(os.path.join(SKILL, "SKILL.md"))
        socratic = read(os.path.join(SKILL, "references", "socratic.md"))
        self.assertIn("Ask in **rounds**", skill)
        self.assertIn("waits for the next round", skill)
        self.assertIn("counted across rounds, not per round", skill)
        self.assertIn("Recommended: (a), because", skill)
        self.assertIn('"one question at a time,"', skill)
        self.assertIn("one probe per question", socratic)

    def test_brief_format_reference_holds_the_section_rules(self):
        skill = read(os.path.join(SKILL, "SKILL.md"))
        fmt = read(os.path.join(SKILL, "references", "brief-format.md"))
        self.assertIn("references/brief-format.md", skill)
        for marker in ("`Inputs: none`", "`Outputs: none`", "## Plan table", "**Step**", "**Choice**",
                       "**Source**", "**Validation**", "`(done)`", "<!-- plan-evidence",
                       "<!-- exact-execution", "`Facts:`", "[agent-asserted: none]",
                       "## Status line", "`Plan status: READY`"):
            self.assertIn(marker, fmt, marker)
        # The gate grants runs from the Step column alone; the rule lives in both files.
        self.assertIn("reads only this column", fmt)
        self.assertIn("grants runs from this column alone", skill)
        # An existing output path needs a fresh folder or the user's overwrite; both files say so.
        self.assertIn("`(overwrite)`", fmt)
        self.assertIn("`(overwrite)`", skill)

    def test_socratic_mode_is_opt_in_and_read_only(self):
        socratic = read(os.path.join(SKILL, "references", "socratic.md"))
        skill = read(os.path.join(SKILL, "SKILL.md"))
        assistance = read(os.path.join(SKILL, "references",
                                       "evidence-assistance.md"))
        self.assertIn("references/socratic.md", skill)
        # Off by default, conversation only, nothing recorded.
        self.assertIn("Friction is opt-in", socratic)
        self.assertIn("no `gate.json` key, no stored state", socratic)
        # One probe inside the question: no extra question, no cap spent, options kept.
        self.assertIn("add **one** probe to the same message", socratic)
        self.assertIn("costs nothing against the five-question cap", socratic)
        self.assertIn("must not name the answer the agent prefers", socratic)
        self.assertIn("`[human-stated]`", socratic)
        # Explain and Challenge never edit, approve, or manufacture an objection.
        self.assertIn("`explain row N`", socratic)
        self.assertIn("`challenge row N`", socratic)
        self.assertIn("`no strong objection found`", socratic)
        self.assertIn("Both are read-only", socratic)
        self.assertIn("never with an edit", socratic)
        self.assertIn("Do not close either answer by asking whether to approve", socratic)
        # Explain plan widens the same read-only prompt to the whole table, in row order.
        self.assertIn("## Explain plan (the linear walkthrough)", socratic)
        self.assertIn("`explain plan`", socratic)
        self.assertIn("`not recorded`", socratic)
        self.assertIn("the shortest reading order", socratic)
        # The librarian dossier shows what left the machine and what was not found.
        self.assertIn("## The librarian dossier", assistance)
        self.assertIn("`Searched:`", assistance)
        self.assertIn("`Not found:`", assistance)
        self.assertIn("`Yours to decide:`", assistance)
        self.assertIn("## After the plan is shown", assistance)


    def test_plan_evidence_block_is_json_in_a_comment(self):
        # The block is JSON in a comment, never a Markdown table: the gate reads every table row beside the
        # plan as a plan row, which would widen what an approval grants.
        evidence = read(os.path.join(SKILL, "references", "plan-evidence.md"))
        skill = read(os.path.join(SKILL, "SKILL.md"))
        self.assertIn("references/plan-evidence.md", skill)
        self.assertIn('<!-- plan-evidence {"version": 1', evidence)
        self.assertIn("never a table", skill)
        for required in ("Paste the output you got", "Read-only programs only", "At most 40 entries",
                         "no output redirection", "`sed` and `awk` are not allowed"):
            self.assertIn(required, evidence, required)
        # The walkthrough quotes the block verbatim rather than retyping a number.
        self.assertIn("plan-evidence.md", read(os.path.join(SKILL, "references", "socratic.md")))


    def test_scientific_convention_route_is_linked_and_bounded(self):
        skill = read(os.path.join(SKILL, "SKILL.md"))
        mycelium = read(os.path.join(SKILL, "references", "mycelium.md"))
        science = read(os.path.join(SKILL, "references", "scientific-conventions.md"))
        self.assertIn("references/scientific-conventions.md", skill)
        self.assertIn("scientific-conventions.md", mycelium)
        self.assertLess(skill.index("## 0. Ask for the question first"),
                        skill.index("references/scientific-conventions.md"))
        for required in ("ACTIVE_CONVENTIONS.yaml", "does **not** activate",
                         "read selectively", "replicate-aware-inference.md",
                         "composition-crumblr.md", "variance-dreamlet.md",
                         "integration-scib.md", "pathway-decoupler.md",
                         "communication-liana.md", "multicellular-mofacellular.md",
                         "gpu-and-interoperability.md", "method-policy.json",
                         "method-lock.json", "DECISION_REQUIRED",
                         "No", "approval"):
            self.assertIn(required.lower(), science.lower(), required)
        self.assertIn("maximum five", science)
        self.assertIn("not implemented guards", science)
        self.assertIn("never itself", science.lower())

    def test_manuscript_routing_is_opt_in_and_bounded(self):
        science = read(os.path.join(SKILL, "references", "scientific-conventions.md"))
        # The routing path exists, is opt-in, and stays read-only guidance.
        for required in ("manuscript-reproducibility", "opt-in only", "registered as active",
                         "not a validation result", "figures-and-source-data.md",
                         "statistical-reporting.md", "code-style.md",
                         "Do not add questions, approvals, executions",
                         "If the pack is absent or unregistered"):
            self.assertIn(required, science, required)
        # Local override precedence is preserved over the manuscript pack.
        self.assertLess(science.index("Local `.living/conventions.md` overrides both"),
                        science.index("A `grill` request that is purely statistical"))
        # Negative control: an irrelevant statistical request is explicitly not routed here.
        self.assertIn("is not routed here", science)
        # The single-cell method routing table is unchanged and still governs method selection.
        self.assertIn("The active single-cell pack governs method selection and assumptions", science)
        self.assertIn("| Experimental design, pairing, dataset / counts layer |", science)


if __name__ == "__main__":
    unittest.main()
