"""List glossary terms and their _Avoid_ words where they appear in an analysis.

Read-only. Run from stdin so Mycelium's hooks stay closed:

    <skill-dir>/../../hooks/mxpy - --analysis analysis/NAME < <skill-dir>/scripts/check_terms.py

Exit 0: no _Avoid_ word found and nothing was skipped. Exit 1: at least one found
(drift), or an _Avoid_ word is also a defined term. Exit 2: the check could not run
or is incomplete (no GLOSSARY.md, no terms parsed, no analysis doc, unreadable file,
scan cut at the file limit, bad folder). A gap is never exit 0.

A term is a line `**Term**:` (definition on the next lines) or `**Term**: definition`.
Inline code spans (`like_this`) and path-like words (outputs/run_1/x.tsv) are not
searched for _Avoid_ words, because they are names, not prose. --include-code-spans
searches them too. Table header cells are always searched.

Scans the analysis doc (<NAME>.md or README.md), comments in code/, and the
first line (header) of *.tsv and *.csv under outputs/ and data/.
"""

import argparse
import json
import os
import re
import sys

CODE_EXT = {".r": "#", ".R": "#", ".py": "#", ".sh": "#", ".snakefile": "#", ".js": "//", ".cpp": "//"}
TABLE_EXT = (".tsv", ".csv")
MAX_FILES = 400
MAX_LINE = 20000


def parse_glossary(text):
    """Return [{'term', 'avoid': [..]}] from the Pocock-style format."""
    terms = []
    for line in text.splitlines():
        line = line.rstrip()
        m = re.match(r"^\*\*(.+?)\*\*\s*(?::.*)?$", line)
        if m:
            terms.append({"term": m.group(1).strip(), "avoid": []})
            continue
        m = re.match(r"^_Avoid_\s*:\s*(.*)$", line)
        if m and terms:
            for part in m.group(1).split(","):
                word = re.sub(r"\(.*?\)", "", part).strip().strip("`'\" ._")
                if word:
                    terms[-1]["avoid"].append(word)
    return terms


def pattern(word):
    # case-insensitive; `_`, `-` and spaces in the word match any of them; word edges are non-alphanumeric
    pieces = [re.escape(p) for p in re.split(r"[\s_\-]+", word.strip()) if p]
    if not pieces:
        return None
    return re.compile(r"(?<![A-Za-z0-9])" + r"[\s_\-]+".join(pieces) + r"(?![A-Za-z0-9])", re.I)


CODE_SPAN = re.compile(r"`[^`]*`")
PATH_WORD = re.compile(r"\S*/\S*[_.]\S*|\S*[_.]\S*/\S*|(?:^|(?<=\s))[~.]?/\S*")


def prose(text):
    """The text without inline code spans and path-like words."""
    return PATH_WORD.sub(" ", CODE_SPAN.sub(" ", text))


def find_doc(folder):
    name = os.path.basename(os.path.abspath(folder)).upper().replace("-", "_")
    for candidate in (name + ".md", "README.md"):
        path = os.path.join(folder, candidate)
        if os.path.isfile(path):
            return path
    return None


def read_lines(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return [line[:MAX_LINE] for line in handle.read().splitlines()]


def doc_units(path):
    fenced = False
    for number, line in enumerate(read_lines(path), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            yield number, line


def code_units(path):
    ext = os.path.splitext(path)[1]
    mark = CODE_EXT.get(ext) if ext in CODE_EXT else CODE_EXT.get(ext.lower())
    if os.path.basename(path) == "Snakefile":
        mark = "#"
    if not mark:
        return
    for number, line in enumerate(read_lines(path), 1):
        if mark in line:
            comment = line[line.index(mark) + len(mark):]
            if comment.strip():
                yield number, comment


def header_units(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        first = handle.readline(MAX_LINE)
    if first.strip():
        yield 1, first.rstrip("\n")


def walk(root, suffixes=None, names=None):
    found = []
    for base, dirs, files in os.walk(root, followlinks=True):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(files):
            if (suffixes and name.endswith(suffixes)) or (names and name in names):
                found.append(os.path.join(base, name))
    return found


def sources(folder):
    """Yield (kind, relative path, units) for every place that is scanned; collect gaps."""
    items, gaps = [], []
    doc = find_doc(folder)
    if doc:
        items.append(("doc", doc, doc_units))
    else:
        gaps.append("no analysis doc (<NAME>.md or README.md)")
    code = os.path.join(folder, "code")
    if os.path.isdir(code):
        for path in walk(code, suffixes=tuple(CODE_EXT), names=("Snakefile",)):
            items.append(("code", path, code_units))
    for sub in ("outputs", "data"):
        root = os.path.join(folder, sub)
        if os.path.isdir(root):
            for path in walk(root, suffixes=TABLE_EXT):
                items.append(("header", path, header_units))
    if len(items) > MAX_FILES:
        gaps.append("scanned the first %d of %d files" % (MAX_FILES, len(items)))
        items = items[:MAX_FILES]
    return items, gaps


def check(folder, glossary_path, max_hits=5, include_code_spans=False):
    gaps = []
    try:
        with open(glossary_path, encoding="utf-8") as handle:
            terms = parse_glossary(handle.read())
    except OSError as err:
        return {"status": 2, "error": "cannot read glossary: %s" % err}
    if not terms:
        gap = "glossary has no terms (a term is a line like `**Donor**:`); nothing was checked"
        return {"status": 2, "terms": [], "clashes": [], "gaps": [gap]}
    for t in terms:
        t["term_re"] = pattern(t["term"])
        t["avoid_re"] = [(w, pattern(w)) for w in t["avoid"] if pattern(w)]
        t["uses"] = 0
        t["hits"] = {}
        t["counts"] = {}
    defined = {re.sub(r"[\s_\-]+", " ", t["term"].lower()): t["term"] for t in terms}
    clashes = []
    for t in terms:
        for w in t["avoid"]:
            key = re.sub(r"[\s_\-]+", " ", w.lower())
            if key in defined and defined[key] != t["term"]:
                clashes.append("%s: _Avoid_ word '%s' is also the term '%s'" % (t["term"], w, defined[key]))
    items, more = sources(folder)
    gaps += more
    for kind, path, units in items:
        rel = os.path.relpath(path, folder)
        try:
            for number, text in units(path):
                searched = text if include_code_spans or kind == "header" else prose(text)
                for t in terms:
                    if t["term_re"] and t["term_re"].search(text):
                        t["uses"] += 1
                    for word, rx in t["avoid_re"]:
                        if rx.search(searched):
                            t["counts"][word] = t["counts"].get(word, 0) + 1
                            hits = t["hits"].setdefault(word, [])
                            if len(hits) < max_hits:
                                hits.append("%s:%d (%s)" % (rel, number, kind))
        except OSError as err:
            gaps.append("cannot read %s: %s" % (rel, err))
    drift = any(t["counts"] for t in terms)
    if any(g.startswith("cannot read") for g in gaps):
        status = 2
    elif drift or clashes:
        status = 1
    else:
        status = 2 if gaps else 0
    out = []
    for t in terms:
        out.append({"term": t["term"], "uses": t["uses"], "avoid": [{"word": w, "count": t["counts"].get(w, 0), "first": t["hits"].get(w, [])} for w in t["avoid"]]})
    return {"status": status, "terms": out, "clashes": clashes, "gaps": gaps}


def render(result):
    lines = []
    if result.get("error"):
        return result["error"]
    for t in result["terms"]:
        lines.append("%s: used %d time(s)" % (t["term"], t["uses"]))
        for a in t["avoid"]:
            if a["count"]:
                lines.append("  avoid '%s': %d hit(s), first %s" % (a["word"], a["count"], "; ".join(a["first"])))
        if not any(a["count"] for a in t["avoid"]) and t["avoid"]:
            lines.append("  no avoid word found")
        if not t["uses"]:
            lines.append("  note: the term itself is not used anywhere scanned")
    for c in result["clashes"]:
        lines.append("clash: " + c)
    for g in result["gaps"]:
        lines.append("gap: " + g)
    verdict = {0: "result: no drift found", 1: "result: drift found", 2: "result: check incomplete (a gap is not a pass)"}
    lines.append(verdict[result["status"]] + (" (and the check has gaps)" if result["status"] == 1 and result["gaps"] else ""))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--analysis", default=".", help="analysis folder (default: current)")
    ap.add_argument("--glossary", help="default: <analysis>/GLOSSARY.md")
    ap.add_argument("--max-hits", type=int, default=5)
    ap.add_argument("--include-code-spans", action="store_true", help="also search inline code and path-like words")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    folder = args.analysis
    if not os.path.isdir(folder):
        print("not a folder: %s" % folder)
        return 2
    glossary = args.glossary or os.path.join(folder, "GLOSSARY.md")
    if not os.path.isfile(glossary):
        print("no GLOSSARY.md at %s (nothing checked)" % glossary)
        return 2
    result = check(folder, glossary, args.max_hits, args.include_code_spans)
    print(json.dumps(result, indent=2) if args.json else render(result))
    return result["status"]


if __name__ == "__main__":
    sys.exit(main())
