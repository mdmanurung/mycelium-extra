"""Check a research note against the format in references/note-format.md.

Run: <skill-dir>/../../hooks/mxpy - <note.md> [--ids] < <skill-dir>/scripts/check_note.py
Exit 0 when the note fits the format, 1 when it does not or cannot be read. Stdlib only.
`--ids` also prints each DOI, PMID and arXiv id in the References section.
"""

import re
import sys

SECTIONS = ["Question", "Answer", "Evidence", "Not established", "Next step", "References"]
COLUMNS = ["claim", "source", "quote or value", "confidence"]
EMPTY = {"", "-", "--", "?", "tbd", "todo", "n/a", "na", "none yet"}
UNSUPPORTED = "unsupported: no source"
REF_LINE = re.compile(r"^\s*(?:[-*]\s*)?\[?(S\d+)\]?[:.)\s]\s*(.*)$")
SOURCE_ID = re.compile(r"\bS\d+\b")
DOI = re.compile(r"\b10\.\d{4,9}/[^\s,;)>\]]+")
PMID = re.compile(r"\bPMID:?\s*(\d+)", re.I)
ARXIV = re.compile(r"\barXiv:?\s*(\d{4}\.\d{4,5})", re.I)
# A version, release, year or date. A bare number, a DOI, a PMID or an arXiv id does not count.
VERSION = re.compile(r"\b(?:19|20)\d{2}\b|\b\d+\.\d+|\b(?:v|release|build|rel\.?)\s*\d+\b|\b[A-Z]{2,}\d{4,}\b", re.I)


def has_version(text):
    """True when the text names a version, release, year or date outside its identifiers."""
    for pattern in (DOI, PMID, ARXIV):
        text = pattern.sub(" ", text)
    return bool(VERSION.search(text))


def split_sections(lines):
    """Map each `## ` heading to (start line number, body lines)."""
    found, name = {}, None
    for number, line in enumerate(lines, 1):
        match = re.match(r"^##\s+(.*?)\s*$", line)
        if match:
            name = match.group(1)
            found[name] = (number, [])
        elif name is not None:
            found[name][1].append((number, line))
    return found


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_rule(line):
    return bool(re.match(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$", line))


def check(text):
    """Return (problems, ids): problems is a list of strings, ids a list of (S-id, kind, value)."""
    problems, ids = [], []
    lines = text.split("\n")
    sections = split_sections(lines)
    for name in SECTIONS:
        if name not in sections:
            problems.append("missing section `## {}`".format(name))
    if not re.search(r"^#\s+\S", text, re.M):
        problems.append("missing title line `# <title>`")
    last = 0
    for name in SECTIONS:
        if name in sections:
            if sections[name][0] < last:
                problems.append("section `## {}` is out of order; the order is {}".format(
                    name, ", ".join(SECTIONS)))
            last = max(last, sections[name][0])
    pinned = re.search(r"^Pinned:[ \t]*(.*)$", text, re.M)
    if not pinned or not pinned.group(1).strip():
        problems.append("missing `Pinned:` line (versions and releases the answer holds for)")
    elif not has_version(pinned.group(1)) and not re.match(r"none:\s*\S", pinned.group(1).strip(), re.I):
        problems.append("`Pinned:` has no version, date or release; write `none: <reason>` if the "
                        "question needs none")

    def body(name):
        return [(n, l) for n, l in sections.get(name, (0, []))[1] if l.strip()]

    for name in ("Question", "Not established", "Next step"):
        if name in sections and not body(name):
            problems.append("`## {}` is empty".format(name))
    if "Answer" in sections:
        answer = body("Answer")
        if not answer:
            problems.append("`## Answer` is empty")
        elif len(answer) > 2:
            problems.append("`## Answer` has {} lines; the format allows two".format(len(answer)))

    defined = {}
    for number, line in body("References"):
        match = REF_LINE.match(line)
        if not match:
            continue
        ident, rest = match.groups()
        if ident in defined:
            problems.append("line {}: reference {} is already defined on line {}".format(number, ident, defined[ident]))
        else:
            defined[ident] = number
        if not has_version(rest):
            problems.append("line {}: reference {} has no version, year, date or release".format(number, ident))
        ids += [(ident, "doi", m.group().rstrip(".")) for m in DOI.finditer(rest)]
        ids += [(ident, "pmid", m.group(1)) for m in PMID.finditer(rest)]
        ids += [(ident, "arxiv", m.group(1)) for m in ARXIV.finditer(rest)]
    if "References" in sections and not defined:
        problems.append("`## References` defines no source (write lines that start `S1`, `S2`, ...)")

    rows = [(n, l) for n, l in body("Evidence") if l.lstrip().startswith("|")]
    if "Evidence" in sections:
        if len(rows) < 3:
            problems.append("`## Evidence` has no table with a header and at least one row")
        else:
            header = [c.lower() for c in cells(rows[0][1])]
            if header != COLUMNS:
                problems.append("line {}: Evidence columns must be {}; found {}".format(
                    rows[0][0], " | ".join(COLUMNS), " | ".join(header)))
            for number, line in rows[1:]:
                if is_rule(line):
                    continue
                row = cells(line)
                if len(row) != len(COLUMNS):
                    problems.append("line {}: row has {} cells, expected {}".format(number, len(row), len(COLUMNS)))
                    continue
                for col, cell in zip(COLUMNS, row):
                    if cell.lower() in EMPTY:
                        problems.append("line {}: empty `{}` cell".format(number, col))
                claim, source, quote, conf = row
                if conf.lower() not in ("high", "medium", "low") and conf.lower() not in EMPTY:
                    problems.append("line {}: confidence `{}` is not high, medium or low".format(number, conf))
                if source.lower() in EMPTY:
                    continue
                if source.lower().startswith(UNSUPPORTED):
                    if conf.lower() != "low":
                        problems.append("line {}: an unsupported claim must have confidence low".format(number))
                    continue
                refs = SOURCE_ID.findall(source)
                if not refs:
                    problems.append("line {}: source `{}` names no reference id (S1, S2, ...) and is not "
                                    "`{}`".format(number, source, UNSUPPORTED))
                for ref in refs:
                    if ref not in defined:
                        problems.append("line {}: source {} is not defined in References".format(number, ref))
    return problems, ids


def main(argv):
    if argv in (["-h"], ["--help"]):
        print("usage: check_note.py <note.md> [--ids]")
        return 0
    args = [a for a in argv if a != "--ids"]
    if len(args) != 1:
        print("usage: check_note.py <note.md> [--ids]")
        return 1
    try:
        with open(args[0], encoding="utf-8") as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError) as error:
        print("cannot read {}: {}".format(args[0], error))
        return 1
    problems, ids = check(text)
    for problem in problems:
        print("FAIL " + problem)
    if "--ids" in argv:
        for ident, kind, value in ids:
            print("ID {} {} {}".format(ident, kind, value))
    print("{}: {}".format(args[0], "{} problem(s)".format(len(problems)) if problems else "fits the format"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
