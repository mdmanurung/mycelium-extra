"""Check a research note against the format in references/note-format.md.

Run: <skill-dir>/../../hooks/mxpy - <note.md> [--ids] < <skill-dir>/scripts/check_note.py
Exit 0 when the note fits the format, 1 when it does not or cannot be read. Stdlib only.
`--ids` also prints each DOI, PMID and arXiv id in the References section.
A note with no `## Retrieval log` section gets a WARN line for each cited DOI, PMID or arXiv id, and still
exits 0 (the 0.32.1 behaviour). When the section exists (references/lit-policy.md), it needs a `Window:` line,
come after References, and list every cited id; a miss is a FAIL.
"""

import re
import sys

SECTIONS = ["Question", "Answer", "Evidence", "Not established", "Next step", "References"]
COLUMNS = ["claim", "source", "quote or value", "confidence"]
EMPTY = {"", "-", "--", "?", "tbd", "todo", "n/a", "na", "none yet"}
UNSUPPORTED = "unsupported: no source"
REF_LINE = re.compile(r"^\s*(?:[-*]\s*)?\[?(S\d+)\]?[:.)\s]\s*(.*)$")
SOURCE_ID = re.compile(r"\bS\d+\b")
# Parentheses stay in a DOI (`10.1016/S0140-6736(20)30183-5`); `clean_doi` drops an unbalanced `)`.
DOI = re.compile(r"\b10\.\d{4,9}/[^\s,;>\]\"'`*<]+")
# `PMID 1`, `PMID: 1`, `PMID=1`, `PMID 1, 2` and `PMIDs 1 2`.
PMID = re.compile(r"\bPMID(s?)\s*[:=]?\s*(\d+(?:(?:\s*[,;&]\s*|\s+and\s+|\s+)(?:PMID\s*[:=]?\s*)?\d+)*)", re.I)
ARXIV_ID = r"(\d{4}\.\d{4,5}|[a-z-]+(?:\.[a-z]{2})?/\d{7})(?:v\d+)?"
ARXIV = re.compile(r"\barXiv\s*[:=]?\s*" + ARXIV_ID + r"|\barxiv\.org/(?:abs|pdf)/" + ARXIV_ID, re.I)
LOG_SECTION = "Retrieval log"
# A version, release, year or date. A bare number, a DOI, a PMID or an arXiv id does not count.
VERSION = re.compile(r"\b(?:19|20)\d{2}\b|\b\d+\.\d+|\b(?:v|release|build|rel\.?)\s*\d+\b|\b[A-Z]{2,}\d{4,}\b", re.I)


def has_version(text):
    """True when the text names a version, release, year or date outside its identifiers."""
    for pattern in (DOI, PMID, ARXIV):
        text = pattern.sub(" ", text)
    return bool(VERSION.search(text))


def clean_doi(raw):
    """A matched DOI without the punctuation around it: a query or fragment, a trailing `.,;:`, and a
    closing `)` that no opening one balances."""
    out = re.split(r"[?#]", raw, 1)[0].rstrip(".,;:")
    while out.endswith(")") and out.count(")") > out.count("("):
        out = out[:-1].rstrip(".,;:")
    return out


def find_ids(text):
    """[(kind, value, in_url)] for each DOI, PMID and arXiv id in the text. `in_url` marks a DOI inside a
    publisher URL (not doi.org), where the match may run on into a version or path suffix."""
    found = []
    for m in DOI.finditer(text):
        token = text[max(text.rfind(" ", 0, m.start()), text.rfind("\n", 0, m.start())) + 1:m.start()]
        in_url = "://" in token and "doi.org" not in token
        value = clean_doi(m.group())
        if in_url and value.startswith("10.1101/"):  # bioRxiv and medRxiv URLs end in `v1` or `v1.full`
            value = re.sub(r"v\d+(?:\.[a-z-]+)*$", "", value)
        found.append(("doi", value, in_url))
    for m in PMID.finditer(text):
        digits = re.findall(r"\d+", m.group(2))
        if not m.group(1) and not re.search(r"[,;&]|\band\b", m.group(2)):
            digits = digits[:1]  # `PMID 31178118 2019`: the second number is not a PMID
        found += [("pmid", d, False) for d in digits]
    for m in ARXIV.finditer(text):
        found.append(("arxiv", (m.group(1) or m.group(2)).lower(), False))
    return found


def logged(kind, value, in_url, pool):
    """True when the log pool holds the id. A DOI taken from a publisher URL also matches a logged DOI that is
    a prefix of it followed by a version, path or extension (`...123456v1.full`, `.../gkaa1100/6012345`)."""
    if (kind, value) in pool:
        return True
    if kind == "doi" and in_url:
        return any(k == "doi" and value.startswith(v)
                   and (not value[len(v):][:1].isalnum() or re.match(r"v\d+", value[len(v):]))
                   for k, v in pool)
    return False


def normal_id(kind, value):
    """Lower-case form of an id, so a log line and a reference line compare equal."""
    value = value.strip().rstrip(".,;:").lower()
    return value


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
    """Return (problems, ids, warnings): problems and warnings are lists of strings, ids a list of
    (S-id, kind, value, in_url)."""
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

    defined, refs = {}, []
    for number, line in body("References"):
        match = REF_LINE.match(line)
        if match:
            ident, rest = match.groups()
            if ident in defined:
                problems.append("line {}: reference {} is already defined on line {}".format(number, ident, defined[ident]))
            else:
                defined[ident] = number
            refs.append([number, ident, rest])
        elif refs:  # a wrapped reference: the next line belongs to it
            refs[-1][2] += "\n" + line
    for number, ident, rest in refs:
        if not has_version(rest):
            problems.append("line {}: reference {} has no version, year, date or release".format(number, ident))
        ids += [(ident, kind, value, in_url) for kind, value, in_url in find_ids(rest)]
    log_problems, warnings = check_log(sections, ids)
    problems += log_problems
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
    return problems, ids, warnings


def check_log(sections, ids):
    """(problems, warnings) for the retrieval log. No log is a warning; a log that misses a cited id or the Window
    line is a problem."""
    problems = []
    if LOG_SECTION not in sections:
        if ids:
            return [], ["no `## {}` section: add one that lists each cited DOI, PMID and arXiv id ({})".format(
                LOG_SECTION, ", ".join(sorted({i[2] for i in ids})))]
        return [], []
    start, rows = sections[LOG_SECTION]
    if "References" in sections and start < sections["References"][0]:
        problems.append("section `## {}` must come after `## References`".format(LOG_SECTION))
    text = "\n".join(line for _, line in rows)
    if not re.search(r"^\s*Window:[ \t]*\S", text, re.M | re.I):
        problems.append("`## {}` has no `Window:` line (write `Window: none` when no window was set)".format(LOG_SECTION))
    pool = {(kind, normal_id(kind, value)) for kind, value, _ in find_ids(text)}
    for ident, kind, value, in_url in ids:
        if logged(kind, normal_id(kind, value), in_url, pool):
            continue
        problems.append("reference {} cites {} {}, which is not in the `## {}`".format(
            ident, kind.upper() if kind != "arxiv" else "arXiv", value, LOG_SECTION))
    return problems, []


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
    problems, ids, warnings = check(text)
    for warning in warnings:
        print("WARN " + warning)
    for problem in problems:
        print("FAIL " + problem)
    if "--ids" in argv:
        for ident, kind, value, _ in ids:
            print("ID {} {} {}".format(ident, kind, value))
    print("{}: {}".format(args[0], "{} problem(s)".format(len(problems)) if problems else "fits the format"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
