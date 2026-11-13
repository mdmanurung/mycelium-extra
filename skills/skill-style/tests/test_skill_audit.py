#!/usr/bin/env python3
"""Tests for skill_audit.py. Run: python3.11 skills/skill-style/tests/test_skill_audit.py"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "skill_audit.py"
SHARED = "Always cite the saved figure that supports each conclusion before you write it down."

GOOD = f"""---
name: good
disable-model-invocation: true
description: Rank the parked ideas so the user can pick one.
---

# Good

## 1. Collect

Read the registry. Done when every open row is listed.

## 2. Show

Print the table and wait until the user picks.

See [rubric](references/rubric.md).

{SHARED}
"""

BAD = f"""---
name: bad
description: "This skill helps with many things and it also does more things than any description should hold, so the first sentence runs on past the cap of one hundred and fifty characters. Second."
---

# Bad

1. Do the first thing.
2. Do the second thing.

Never do this. Do not do that. Don't do the other. You must not guess.

{SHARED}

```
Never inside a fence is ignored by the sentence scan.
```
""" + "\nfiller line\n" * 160


def make(tmp, files):
    for rel, text in files.items():
        path = Path(tmp) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def run(root, *extra):
    return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), *extra], capture_output=True, text=True)


class SkillAuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        make(self.tmp.name, {
            "skills/good/SKILL.md": GOOD,
            "skills/good/references/rubric.md": "Rubric text.\n",
            "skills/good/references/orphan.md": "Nobody points here.\n",
            "skills/bad/SKILL.md": BAD,
        })

    def report(self):
        result = run(self.tmp.name, "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        return {s["skill"]: s for s in data["skills"]}, data

    def test_description_and_invocation(self):
        skills, data = self.report()
        self.assertEqual(skills["good"]["invocation"], "user")
        self.assertEqual(skills["bad"]["invocation"], "model")
        self.assertFalse(skills["good"]["over_cap"])
        self.assertTrue(skills["bad"]["over_cap"])
        self.assertFalse(skills["bad"]["leading_word_ok"])
        self.assertTrue(skills["good"]["leading_word_ok"])
        self.assertEqual(data["totals"]["model_invoked_description_words"], skills["bad"]["desc_words"])

    def test_sprawl_and_negations(self):
        skills, _ = self.report()
        self.assertTrue(skills["bad"]["sprawl"])
        self.assertFalse(skills["good"]["sprawl"])
        self.assertEqual(skills["bad"]["negations"], 5)
        self.assertEqual(skills["good"]["negations"], 0)

    def test_steps_without_completion_cue(self):
        skills, _ = self.report()
        self.assertEqual(skills["good"]["steps_to_review"], [])
        self.assertEqual(len(skills["bad"]["steps_to_review"]), 2)

    def test_orphan_references(self):
        skills, _ = self.report()
        self.assertEqual(skills["good"]["orphan_references"], ["references/orphan.md"])

    def test_orphan_check_uses_whole_names(self):
        make(self.tmp.name, {
            "skills/a/SKILL.md": "---\nname: a\ndescription: Alpha.\n---\nSee references/run-plans.md.\n",
            "skills/a/references/plans.md": "x\n",
            "skills/a/references/run-plans.md": "y\n",
        })
        skills, _ = self.report()
        self.assertEqual(skills["a"]["orphan_references"], ["references/plans.md"])

    def test_other_skill_pointer_and_test_only_reference(self):
        make(self.tmp.name, {
            "skills/c/SKILL.md": "---\nname: c\ndescription: Cee.\n---\nRead ../d/references/shared.md.\n",
            "skills/d/SKILL.md": "---\nname: d\ndescription: Dee.\n---\nBody.\n",
            "skills/d/references/shared.md": "s\n",
            "skills/d/references/dev.md": "s\n",
            "skills/d/tests/test_d.py": "UNLINKED_OK = {'dev.md'}\n",
        })
        skills, _ = self.report()
        self.assertEqual(skills["d"]["orphan_references"], [])
        self.assertEqual(skills["d"]["developer_references"], ["references/dev.md"])

    def test_folded_description_counts_every_line(self):
        words = " ".join(["word"] * 70)
        make(self.tmp.name, {
            "skills/f/SKILL.md": f"---\nname: f\ndescription: Write things.\n  {words}\n---\nBody.\n",
        })
        skills, _ = self.report()
        self.assertGreater(skills["f"]["desc_words"], 60)
        self.assertTrue(skills["f"]["over_cap"])

    def test_section_level_done_when_covers_list_items(self):
        make(self.tmp.name, {
            "skills/s/SKILL.md": "---\nname: s\ndescription: Ess.\n---\n## Chart\n\nDone when the map exists.\n\n1. Do one.\n2. Do two.\n\n## Format\n\n1. Answer first.\n2. Then context.\n",
        })
        skills, _ = self.report()
        self.assertEqual(skills["s"]["steps_to_review"], [])

    def test_duplicate_sentences_across_skills(self):
        _, data = self.report()
        dups = data["duplicate_sentences"]
        self.assertEqual(len(dups), 1)
        self.assertEqual(sorted(dups[0]["files"]), ["bad/SKILL.md", "good/SKILL.md"])

    def test_table_output_and_read_only(self):
        before = sorted(p.as_posix() for p in Path(self.tmp.name).rglob("*"))
        result = run(self.tmp.name)
        self.assertEqual(result.returncode, 0)
        self.assertIn("SPRAWL", result.stdout)
        self.assertIn("JSON:", result.stdout)
        self.assertEqual(before, sorted(p.as_posix() for p in Path(self.tmp.name).rglob("*")))

    def test_unusable_input_exits_2(self):
        self.assertEqual(run(Path(self.tmp.name) / "missing").returncode, 2)
        empty = tempfile.TemporaryDirectory()
        self.addCleanup(empty.cleanup)
        self.assertEqual(run(empty.name).returncode, 2)
        self.assertEqual(run(self.tmp.name, "--format", "xml").returncode, 2)

    def test_runs_from_stdin_like_the_docs_say(self):
        with open(SCRIPT) as script:
            result = subprocess.run([sys.executable, "-", "--root", self.tmp.name, "--format", "json"],
                                    stdin=script, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
