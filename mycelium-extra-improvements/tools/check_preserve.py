#!/usr/bin/env python3
"""Check that a split README keeps every piece of the old README's content.

Usage: check_preserve.py OLD_README NEW_FILE [NEW_FILE ...]

Units taken from OLD_README:
  - every heading's text (bold run-in headings like "**Limits.**" count too)
  - every table cell
  - every non-empty line of every fenced code block
  - every sentence of every paragraph and list item
  - every inline `code` span (the token check: gate.json keys, schema names,
    status strings, defaults, commands, paths)
A unit with fewer than 4 letters/digits is trivial and skipped.

Matching: Markdown emphasis (**), heading/list markers and runs of whitespace are
normalised in both old and new text; a unit passes if it occurs as a substring of
the concatenated new files. Exit status 1 if any unit is missing.
"""
import re
import sys


def norm(s):
    s = s.replace("**", "")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


SENT_SPLIT = re.compile(r"(?<=[.!?:;])\s+(?=[A-Z`(\[\"/])")


def units(text):
    out = []  # (kind, unit)
    in_code = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            if line.strip():
                out.append(("code", line.strip()))
            continue
        s = line.strip()
        if not s:
            continue
        for tok in re.findall(r"`([^`]+)`", s):
            out.append(("token", "`" + tok + "`"))
        m = re.match(r"^#{1,6}\s+(.*)$", s)
        if m:
            out.append(("heading", m.group(1)))
            continue
        if s.startswith("|"):
            if re.match(r"^\|[-\s|:]+\|$", s):
                continue
            for cell in s.strip("|").split("|"):
                out.append(("cell", cell.strip()))
            continue
        s = re.sub(r"^([-*]|\d+\.)\s+", "", s)
        # bold run-in heading: "**Limits.** text"
        m = re.match(r"^\*\*([^*]+?)\.?\*\*\s*(.*)$", s)
        if m:
            out.append(("heading", m.group(1)))
            s = m.group(2)
            if not s:
                continue
        for sent in SENT_SPLIT.split(s):
            out.append(("sentence", sent))
    return out


def main(argv):
    old = open(argv[1], encoding="utf-8").read()
    new = " ".join(open(p, encoding="utf-8").read() for p in argv[2:])
    hay = norm(new)
    total = 0
    missing = []
    seen = set()
    for kind, u in units(old):
        n = norm(u).rstrip(".:")
        if len(re.findall(r"[A-Za-z0-9]", n)) < 4 or (kind, n) in seen:
            continue
        seen.add((kind, n))
        total += 1
        if n not in hay:
            missing.append((kind, n))
    by_kind = {}
    for kind, n in seen:
        by_kind[kind] = by_kind.get(kind, 0) + 1
    print("units checked: %d (%s)" % (total, ", ".join(
        "%s %d" % (k, by_kind[k]) for k in sorted(by_kind))))
    print("missing: %d" % len(missing))
    for kind, n in missing:
        print("  [%s] %s" % (kind, n))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
