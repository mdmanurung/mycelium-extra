"""Regenerate large-history and fresh-clone demos using the regression fixture.

python3.12 tests/e2e/make_journal_example.py [--output-dir DIR] [--receipts 147]
Hook invocations record simulated tool outcomes; no analysis or scheduler runs.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills/track-changes/tests"))
from test_journal import JournalTest, history, journal


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(ROOT / "docs/examples"))
    parser.add_argument("--receipts", type=int, default=147)
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    case = JournalTest()
    case.setUp()
    try:
        first, _, third = history(case, args.receipts)
        case.saved_verification(first)
        checkpoint = journal.save(case.root, case.collect_journal(["notes/interpretation.md#research"]))
        case.saved_verification(third)
        records = case.gate.read_receipts(case.root)
        legacy = dict(records[-2], attempt_id=None, exit_status="unknown")
        conflict = dict(records[0], exit_status=99)
        with open(os.path.join(case.root, ".mycelium-extra/receipts.jsonl"), "a") as handle:
            handle.write(json.dumps(legacy) + "\n" + json.dumps(conflict) + "\n{malformed synthetic line\n")
        case.cli("--journal", "--analysis", "analysis/a", "--original", first)
        report = Path(case.root) / ".mycelium-extra/track-changes/analysis__a/report.html"
        shutil.copyfile(report, out / "analysis-journal.html")
        journal.save(case.root, case.collect_journal())
        demo = out / "journal-demo"
        if demo.exists():
            shutil.rmtree(demo)  # only this generated synthetic directory
        shutil.copytree(Path(case.root) / "analysis", demo / "analysis",
                        ignore=shutil.ignore_patterns(".save.lock", ".publish.lock", ".transactions"))
        shutil.copytree(Path(case.root) / "notes", demo / "notes")
        (demo / ".gitignore").write_text(".mycelium-extra/\n")
        result = case.cli("--journal", "--analysis", "analysis/a", repo=str(demo))
        shutil.copyfile(demo / ".mycelium-extra/track-changes/analysis__a/report.html", out / "analysis-journal-missing.html")
        shutil.rmtree(demo / ".mycelium-extra")
        print("Generated", out / "analysis-journal.html")
        print("Fresh-clone report:", result.strip())
        print("First checkpoint", checkpoint["digest"], "saved", checkpoint["saved_at"])
    finally:
        case.doCleanups()


if __name__ == "__main__": main()
