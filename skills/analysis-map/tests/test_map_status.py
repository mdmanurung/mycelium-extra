#!/usr/bin/env python3
"""Tests for map_status.py. Run: python3.11 skills/analysis-map/tests/test_map_status.py"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "map_status.py"

MAP = """# Cohort map

## Destination

An approved analysis plan for the donor-level comparison.

## Decisions so far

- [Pick the cohort](map/01-cohort.md): use cohort B.

## Not yet specified

<!-- comment -->
- Batch handling, waits on the cohort

## Out of scope

- Spatial data: not collected
"""


def ticket(title, typ="grilling", status="open", blocked="none", claimed="none", res=""):
    return (
        f"# {title}\n\nType: {typ}\nStatus: {status}\nBlocked by: {blocked}\n"
        f"Claimed: {claimed}\n\n## Question\n\nQ?\n\n## Resolution\n\n{res}\n"
    )


def build(tmp, map_text, tickets):
    plans = Path(tmp) / "plans"
    (plans / "map").mkdir(parents=True)
    (plans / "MAP.md").write_text(map_text, encoding="utf-8")
    for name, body in tickets.items():
        (plans / "map" / f"{name}.md").write_text(body, encoding="utf-8")
    return Path(tmp)


def run(path):
    p = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)
    return p.returncode, p.stdout


class MapStatus(unittest.TestCase):
    def test_sound_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(tmp, MAP, {
                "01-cohort": ticket("Pick the cohort", status="closed", res="Cohort B."),
                "02-batch": ticket("Choose batch handling", blocked="01-cohort"),
                "03-access": ticket("Request the raw files", typ="task", claimed="2026-11-13 s1"),
                "04-ref": ticket("Check the reference", blocked="02-batch"),
            })
            code, out = run(tmp)
            self.assertEqual(code, 0, out)
            self.assertIn("frontier 1  blocked 1  claimed 1  closed 1  fog 1  out-of-scope 1", out)
            self.assertIn("frontier: Choose batch handling", out)
            self.assertIn("blocked: Check the reference waits on Choose batch handling", out)
            self.assertIn("claimed: Request the raw files by 2026-11-13 s1", out)

    def test_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(tmp, MAP, {
                "01-cohort": ticket("Pick the cohort", status="closed", res="B."),
                "02-a": ticket("A", blocked="03-b"),
                "03-b": ticket("B", blocked="02-a"),
            })
            code, out = run(tmp)
            self.assertEqual(code, 1)
            self.assertIn("PROBLEM: cycle", out)

    def test_missing_blocker_and_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = MAP + "\n- [Ghost](map/09-ghost.md): gone\n"
            build(tmp, text, {
                "01-cohort": ticket("Pick the cohort", status="closed", res="B."),
                "02-a": ticket("A", blocked="07-nowhere"),
            })
            code, out = run(tmp)
            self.assertEqual(code, 1)
            self.assertIn("'07-nowhere', which is not a ticket", out)
            self.assertIn("map/09-ghost.md, which does not exist", out)

    def test_closed_without_resolution_or_decision_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(tmp, MAP, {
                "01-cohort": ticket("Pick the cohort", status="closed", res=""),
                "02-x": ticket("X", status="closed", res="done"),
            })
            code, out = run(tmp)
            self.assertEqual(code, 1)
            self.assertIn("01-cohort: closed with an empty Resolution", out)
            self.assertIn("02-x: closed but in neither Decisions so far nor Out of scope", out)

    def test_bad_type_and_route_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = MAP.replace("- Batch handling, waits on the cohort\n", "")
            build(tmp, text, {"01-cohort": ticket("Pick the cohort", status="closed", res="B.")})
            code, out = run(tmp)
            self.assertEqual(code, 0, out)
            self.assertIn("route clear", out)
            build_bad = tempfile.mkdtemp()
            build(build_bad, text, {"01-cohort": ticket("Pick the cohort", typ="vibes", status="closed", res="B.")})
            code, out = run(build_bad)
            self.assertEqual(code, 1)
            self.assertIn("type 'vibes'", out)

    def test_prose_fog_blocks_route_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = MAP.replace("- Batch handling, waits on the cohort\n", "Fog: which cohort to use.\n")
            build(tmp, text, {"01-cohort": ticket("Pick the cohort", status="closed", res="B.")})
            code, out = run(tmp)
            self.assertIn("fog 1", out)
            self.assertNotIn("route clear", out)

    def test_notes_file_ignored_and_comma_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(tmp, MAP, {
                "01-cohort": ticket("Pick the cohort", status="closed", res="B."),
                "02-c": ticket("C, with comma"),
                "03-d": ticket("D", blocked="C, with comma"),
                "README": "notes\n",
            })
            code, out = run(tmp)
            self.assertEqual(code, 0, out)
            self.assertIn("blocked: D waits on C, with comma", out)

    def test_closed_ticket_placement(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = MAP.replace("- [Pick the cohort](map/01-cohort.md): use cohort B.\n", "").replace(
                "- Spatial data: not collected", "- Spatial data: not collected\n- Dropped donors, see 02-b")
            build(tmp, text, {
                "01-cohort": ticket("Pick the cohort", status="closed", res="B."),
                "02-b": ticket("Dropped donors", status="closed", res="out"),
            })
            code, out = run(tmp)
            self.assertEqual(code, 1)
            self.assertIn("01-cohort: closed but in neither", out)
            self.assertNotIn("02-b:", out)
        with tempfile.TemporaryDirectory() as tmp:
            text = MAP.replace("map/01-cohort.md", "map/01-cohort-ab.md") + "\n"
            build(tmp, text, {"01-cohort": ticket("Pick the cohort", status="closed", res="B."),
                              "01-cohort-ab": ticket("Other", status="closed", res="x")})
            code, out = run(tmp)
            self.assertIn("01-cohort: closed but in neither", out)

    def test_ambiguous_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(tmp, MAP, {
                "01-cohort": ticket("Pick the cohort", status="closed", res="B."),
                "01-a2": ticket("A2"),
                "02-z": ticket("Z", blocked="01"),
            })
            code, out = run(tmp)
            self.assertIn("matches 2 tickets", out)
            self.assertNotIn("which is not a ticket", out)

    def test_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _ = run(tmp)
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
