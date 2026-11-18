#!/usr/bin/env python3
"""usage: check_summary.py [--kind auto|rcheck|pytest|ruff] [--notes] [--exit-code] [LOG ...]

Turn package check output into one readout line for `tree.py run --readout-value`.

Reads stdin, or the files named as arguments. It understands:
  - R CMD check and devtools::check()  -> "rcheck: 0 ERROR, 1 WARNING, 2 NOTE"
  - the pytest summary line            -> "pytest: 2 failed, 10 passed in 1.23s"
  - the ruff check summary             -> "ruff: 3 errors" or "ruff: clean"
When the input holds more than one, the parts join with "; ".

Options:
  --kind auto|rcheck|pytest|ruff   read one kind only (default auto)
  --notes                          after the line, list each NOTE section heading
  --exit-code                      exit 1 when there is an ERROR, a failed or errored test, or a ruff finding
                                   (a WARNING or NOTE never sets it: which of those fail is the user's plan row)
Exit 0: parsed. Exit 2: no summary found. Exit 1: only with --exit-code.
Stdlib only, Python 3.6+.
"""

import re
import sys

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
STATUS = re.compile(r"^Status:\s*(.*)$")
DEVTOOLS = re.compile(r"^(\d+) errors?\s*\S*\s*\|\s*(\d+) warnings?\s*\S*\s*\|\s*(\d+) notes?\b")
CHECK_LINE = re.compile(r"^\S?\s*\*?\s*checking\b.*\.\.\.(?:\s*\[[^\]]*\])?\s+(ERROR|WARNING|NOTE)\s*$")
PYTEST_COUNTS = re.compile(r"(\d+) (failed|passed|skipped|deselected|xfailed|xpassed|errors?|warnings?|rerun)\b")
PYTEST_END = re.compile(r"^=*\s*(.*?)\s+in\s+([\d.]+)s?(?:\s+\([^)]*\))?\s*=*$")
RUFF_FOUND = re.compile(r"^Found (\d+) errors?\.?$")


def clean(text):
    return [ANSI.sub("", line).rstrip() for line in text.splitlines()]


def parse_rcheck(lines):
    """Return (errors, warnings, notes, note_headings) or None."""
    counts = None
    for line in lines:
        m = STATUS.match(line)
        if m:
            body = m.group(1)
            if body.startswith("OK"):
                counts = (0, 0, 0)
            else:
                found = {k.upper(): int(n) for n, k in re.findall(r"(\d+) (ERROR|WARNING|NOTE)S?", body)}
                if found:
                    counts = (found.get("ERROR", 0), found.get("WARNING", 0), found.get("NOTE", 0))
        m = DEVTOOLS.match(line)
        if m and counts is None:
            counts = tuple(int(x) for x in m.groups())
    tallies = {"ERROR": 0, "WARNING": 0, "NOTE": 0}
    headings = []
    for line in lines:
        m = CHECK_LINE.match(line)
        if m:
            tallies[m.group(1)] += 1
            if m.group(1) == "NOTE":
                headings.append(re.sub(r"^\S?\s*\*?\s*", "", line).rsplit("...", 1)[0].strip())
    if counts is None:
        if not any(tallies.values()) and not any("checking" in l and "... OK" in l for l in lines):
            return None
        counts = (tallies["ERROR"], tallies["WARNING"], tallies["NOTE"])
    return counts + (headings,)


def parse_pytest(lines):
    """Return a dict of counts and the duration of the last summary line, or None."""
    for line in reversed(lines):
        if re.match(r"^=*\s*no tests ran\b", line):
            return {"no tests ran": 0}, None
        m = PYTEST_END.match(line)
        if m and PYTEST_COUNTS.search(m.group(1)) and not re.search(r"[^\d\w, ]", m.group(1)):
            counts = {}
            for n, word in PYTEST_COUNTS.findall(m.group(1)):
                key = "errors" if word.startswith("error") else word
                counts[key] = counts.get(key, 0) + int(n)
            return counts, m.group(2)
    return None


def parse_ruff(lines):
    for line in reversed(lines):
        if line.strip() == "All checks passed!":
            return 0
        m = RUFF_FOUND.match(line.strip())
        if m:
            return int(m.group(1))
    return None


def summarize(text, kind="auto", want_notes=False):
    """Return (line, notes, bad) where bad is True for an ERROR, a failed test or a ruff finding."""
    lines = clean(text)
    parts, notes, bad = [], [], False
    if kind in ("auto", "rcheck"):
        r = parse_rcheck(lines)
        if r:
            e, w, n, notes = r
            parts.append("rcheck: {} ERROR, {} WARNING, {} NOTE".format(e, w, n))
            bad = bad or e > 0
    if kind in ("auto", "pytest"):
        p = parse_pytest(lines)
        if p:
            counts, secs = p
            order = ("failed", "errors", "passed", "skipped", "xfailed", "xpassed", "deselected", "rerun", "warnings")
            shown = ["{} {}".format(counts[k], k) for k in order if k in counts]
            if "no tests ran" in counts:
                shown = ["no tests ran"]
            parts.append("pytest: " + ", ".join(shown) + (" in {}s".format(secs) if secs else ""))
            bad = bad or counts.get("failed", 0) > 0 or counts.get("errors", 0) > 0 or "no tests ran" in counts
    if kind in ("auto", "ruff"):
        k = parse_ruff(lines)
        if k is not None:
            parts.append("ruff: clean" if k == 0 else "ruff: {} errors".format(k))
            bad = bad or k > 0
    return "; ".join(parts), (notes if want_notes else []), bad


def main(argv):
    kind, want_notes, exit_code, files = "auto", False, False, []
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == "--kind" and args:
            kind = args.pop(0)
        elif a == "--notes":
            want_notes = True
        elif a == "--exit-code":
            exit_code = True
        elif a in ("-h", "--help"):
            print(__doc__)
            return 0
        else:
            files.append(a)
    if kind not in ("auto", "rcheck", "pytest", "ruff"):
        print("check_summary: --kind is auto, rcheck, pytest or ruff", file=sys.stderr)
        return 2
    if files:
        text = ""
        for path in files:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text += fh.read() + "\n"
    else:
        text = sys.stdin.read()
    line, notes, bad = summarize(text, kind, want_notes)
    if not line:
        print("check_summary: no R CMD check, pytest or ruff summary found", file=sys.stderr)
        return 2
    print(line)
    for note in notes:
        print("NOTE: " + note)
    return 1 if (exit_code and bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
