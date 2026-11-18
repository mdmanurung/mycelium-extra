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
# Parentheses stay in a DOI (`10.1016/S0140-6736(20)30183-5`); `clean_doi` drops an unbalanced `)`. A table bar, a
# brace and a dash end the match.
DOI = re.compile(r"\b10\.\d{4,9}/[^\s,;>\]\"'`*<|{}\u2013\u2014]+")
TRAILING = ".,;:!?-"
# `PMID 1`, `PubMed ID: 1`, `PMID 1, PMID 2`, and a list `PMID 1, 2`, `PMIDs 1 2`, `PMIDs 1/2`, `PMIDs 1, 2, and 3`.
# `pmids_in` keeps a bare number after the first only when it has 7 to 9 digits and is not a date (8 digits that
# start 19 or 20), so a year, a page or a count (`PMID 31178118, 2019`, `, 12 co-authors`) ends the list.
PMID_LABEL = r"(?:PMIDs?|PubMed\s+IDs?)"
PMID_SEP = r"(?:\s*[,;&/]\s*(?:and\s+)?|\s+and\s+|\s+|\s*[-\u2022]\s+)"
PMID = re.compile(r"\b" + PMID_LABEL + r"[\s:=#\[(]*\d+(?:" + PMID_SEP + r"(?:" + PMID_LABEL + r"[\s:=#\[(]*)?\d+)*", re.I)
PMID_LABELLED = re.compile(r"\b" + PMID_LABEL + r"[\s:=#\[(]*\d+", re.I)
PMID_URL = re.compile(r"\bpubmed\.ncbi\.nlm\.nih\.gov/(\d+)|\bncbi\.nlm\.nih\.gov/pubmed/(\d+)", re.I)
ARXIV_ID = r"(\d{4}\.\d{4,5}|[a-z-]+(?:\.[a-z]{2})?/\d{7})(?:v\d+)?"
ARXIV = re.compile(r"\barXiv\s*[:=]?\s*" + ARXIV_ID + r"|\barxiv\.org/(?:abs|pdf|html)/" + ARXIV_ID, re.I)
LOG_SECTION = "Retrieval log"
# A version, release, year or date. A bare number, a DOI, a PMID or an arXiv id does not count.
VERSION = re.compile(r"\b(?:19|20)\d{2}\b|\b\d+\.\d+|\b(?:v|release|build|rel\.?)\s*\d+\b|\b[A-Z]{2,}\d{4,}\b", re.I)
# The suffixes a publisher URL adds after a DOI (lit-policy.md): a file extension, a view segment, a figure or
# supplement segment, and the publisher's own article number (6 digits or more). Nothing else matches a logged DOI.
URL_SUFFIX = re.compile(r"(?:\.(?:full|pdf|abstract|html|xml|epub|full-text|supplementary-material))+|(?:/(?:full|"
                        r"abstract|epdf|pdf|pdfdirect|references|citedby|figures?(?:/\d+)?|suppl?(?:info)?(?:-\d+)?|"
                        r"\d{6,}))+")


def normalise(text):
    """One cleaning step for a reference line and a log line, before any id is read: Markdown emphasis, code and
    strike markers (`*`, `_`, backtick, `~`, and a backslash before `_`), curly and straight quotes, and braces.
    A `*`, `_` or `~` between two letters or digits stays, so a DOI such as `10.1002/a_b` keeps its underscore."""
    text = re.sub(r"\\(?=_)", "", text)
    text = re.sub("[`{}\"'\u2018\u2019\u201c\u201d]", "", text)
    return re.sub(r"(?<![A-Za-z0-9])[*_~]+|[*_~]+(?![A-Za-z0-9])", "", text)


def has_version(text):
    """True when the text names a version, release, year or date outside its identifiers."""
    text = normalise(text)
    for pattern in (DOI, PMID_URL, PMID_LABELLED, ARXIV):
        text = pattern.sub(" ", text)
    return bool(VERSION.search(text))


def clean_doi(raw, in_url=False, preprint=False):  # `in_url`: any URL, so a `&` starts the next query part
    """A matched DOI without what surrounds it: a query or fragment (and `&...` inside a URL), a trailing `.,;:!?-`
    or `/`, a bioRxiv or medRxiv version suffix (`v1`, `v2.full`) when the DOI came from one of their URLs, and a
    closing `)` that no opening one balances."""
    out = re.split(r"[?#&]" if in_url else r"[?#]", raw, 1)[0].rstrip(TRAILING + "/")
    while out.endswith(")") and out.count(")") > out.count("("):
        out = out[:-1].rstrip(TRAILING + "/")
    if preprint:  # after the `)` is dropped, so `...123456v1)` from a Markdown link loses its version too
        out = re.sub(r"(?<=\d)v\d+(?:[./+].*)?$", "", out)
    return out


def pmids_in(region):
    """The PMIDs of one matched list: the first number, each `PMID`-labelled number, and each bare 7 to 9 digit
    number that is not a date, up to the first number that is none of these."""
    found = []
    for label, number in re.findall(r"(" + PMID_LABEL + r")?[\s:=#\[(]*(\d+)", region, re.I):
        if found and not label and (not re.fullmatch(r"\d{7,9}", number) or re.fullmatch(r"(?:19|20)\d{6}", number)):
            break
        found.append(number)
    return found


def find_ids(text):
    """[(kind, value, in_url)] for each DOI, PMID and arXiv id in the text, read after `normalise`. `in_url` marks a
    DOI inside a publisher URL (not doi.org), where the match may run on into a path suffix."""
    text = normalise(text)
    found = []
    for m in DOI.finditer(text):
        token = text[max(text.rfind(" ", 0, m.start()), text.rfind("\n", 0, m.start())) + 1:m.start()]
        in_url = "://" in token and "doi.org" not in token
        preprint = in_url and re.search(r"(?:bio|med)rxiv\.org", token, re.I) is not None
        found.append(("doi", clean_doi(m.group(), "://" in token, preprint), in_url))
    for m in PMID.finditer(text):
        found += [("pmid", d, False) for d in pmids_in(m.group())]
    for m in PMID_URL.finditer(text):
        found.append(("pmid", m.group(1) or m.group(2), False))
    for m in ARXIV.finditer(text):
        found.append(("arxiv", (m.group(1) or m.group(2)).lower(), False))
    return found


def logged(kind, value, in_url, pool):
    """The logged id that matches, or None. A DOI matches the exact logged DOI. One taken from a publisher URL also
    matches a logged DOI followed by a suffix in `URL_SUFFIX` (`.full`, `/full`, `/figures/1`, `/6012345`)."""
    if (kind, value) in pool:
        return value
    if kind == "doi" and in_url:
        for k, v in sorted(pool, key=lambda pair: -len(pair[1])):
            if k == "doi" and value.startswith(v) and URL_SUFFIX.fullmatch(value[len(v):]):
                return v
    return None


def normal_id(kind, value):
    """Lower-case form of an id, so a log line and a reference line compare equal."""
    return value.strip().rstrip(TRAILING + "/").lower()


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
    for index, (ident, kind, value, in_url) in enumerate(ids):
        match = logged(kind, normal_id(kind, value), in_url, pool)
        if match:
            if match != normal_id(kind, value):
                ids[index] = (ident, kind, match, in_url)  # the DOI itself, not the publisher's path after it
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
