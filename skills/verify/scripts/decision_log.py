"""Append one row to a run's decision log. Stdlib-only; run it from stdin, like the other verify scripts:

    <root>/hooks/mxpy - LOG PHASE DECISION WHY EVIDENCE RESULT PLAN_ROW SOURCE < decision_log.py

LOG is `<analysis>/logs/decisions.tsv`. The file starts with the header ts, phase, decision, why, evidence, result,
plan_row, source, and rows are only ever appended: a wrong row gets a later row that supersedes it. PLAN_ROW is the
approved plan's step number, and SOURCE is that row's Source cell (`user`, `inherited: <path>`, `repo: <path>`).
Evidence is a pointer (a path, `file:line` or a commit), never prose. PHASE `start` writes the marker row that opens
a run; it takes empty cells for the rest. Tabs and newlines in a cell become spaces. A negative number stays as it is.
"""
import datetime
import os
import sys

COLUMNS = ("ts", "phase", "decision", "why", "evidence", "result", "plan_row", "source")


def clean(text):
    return " ".join(str(text).replace("\t", " ").replace("\r", " ").replace("\n", " ").split())


def main(argv):
    if argv and argv[0] in ("-h", "--help"):
        print("usage: decision_log.py LOG PHASE DECISION WHY EVIDENCE RESULT PLAN_ROW SOURCE\n")
        print(__doc__.strip())
        return 0
    if len(argv) != 8:
        sys.exit("decision_log: need 8 arguments: LOG PHASE DECISION WHY EVIDENCE RESULT PLAN_ROW SOURCE "
                 "(use '' for a cell with nothing to say; a `start` row may leave most empty).")
    path, cells = argv[0], [clean(c) for c in argv[1:]]
    if cells[0] != "start" and (not cells[1] or not cells[5]):
        sys.exit("decision_log: a decision row needs a decision and a plan_row. A choice with no approved plan row "
                 "is an unplanned impactful choice: stop and ask the researcher instead of logging it.")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fresh = not os.path.isfile(path) or os.path.getsize(path) == 0
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(path, "a", encoding="utf-8") as handle:
        if fresh:
            handle.write("\t".join(COLUMNS) + "\n")
        handle.write("\t".join([stamp] + cells) + "\n")
    print("logged " + path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
