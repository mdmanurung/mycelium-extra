"""List the Mycelium decision entries a task touches, oldest first.

Read-only and stdlib-only; runs on Python 3.6+. Run it from stdin so
Mycelium's hooks do not open the post-action cycle:

    python3 - --living-dir .living --tag cycombine --term cytovi < decision_threads.py

The script extracts; it does not judge. It never infers that an entry is
current or superseded. `status`, `supersedes`, `scope` and `revisit` are raw
field values; `hints` are status words found in the heading.
"""

import argparse
import json
import os
import re
import sys

HEADING = re.compile(r"^(#{2,3})\s+(.*\S)\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
DATE = re.compile(r"\[?(\d{4}-\d{2}-\d{2})\]?")
POSITIONAL_ID = re.compile(r"\b[DLT]-\d+\b")
# Both **Name**: and **Name:** occur in real logs.
FIELD = re.compile(r"^\*\*([A-Za-z][A-Za-z -]*?)(?:\*\*\s*:|:\*\*)\s*(.*)$")
KEPT_FIELDS = {
    "status": "status",
    "supersedes": "supersedes",
    "superseded by": "superseded_by",
    "scope": "scope",
    "revisit when": "revisit",
    "resolved-by": "resolved_by",
}
HINT_WORDS = re.compile(
    r"\b(confirmed|rejected|reject(?:ion)?|held|shelved|superseded|supersedes?|"
    r"reversed?|overturns?|revisit(?:ed)?|addendum|retired?|archived|"
    r"deprecated|withdrawn|replaced|reopen(?:ed|s)?|wrong)\b",
    re.IGNORECASE,
)
TEMPLATE_STATUS = re.compile(r"\w+\s*\|\s*\w+")


def split_heading(text):
    """Return (date, title, positional_ids) for one heading's text."""
    ids = POSITIONAL_ID.findall(text)
    match = DATE.search(text)
    if match is None:
        return None, text, ids
    title = text[match.end():].lstrip(" :—–-")
    prefix = text[:match.start()].strip(" :—–-")
    if prefix and not POSITIONAL_ID.fullmatch(prefix):
        title = prefix + " " + title
    return match.group(1), title or text, ids


def parse_entries(path):
    entries = []
    in_fence = False
    current = None
    with open(path, encoding="utf-8", errors="replace") as handle:
        for number, line in enumerate(handle, start=1):
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                if current is not None:
                    current["_body"].append(line)
                continue
            heading = HEADING.match(line)
            if heading:
                date, title, ids = split_heading(heading.group(2))
                current = {
                    "file": os.path.basename(path),
                    "line": number,
                    "level": len(heading.group(1)),
                    "date": date,
                    "title": title,
                    "positional_ids": ids,
                    "tags": [],
                    "hints": sorted({w.lower() for w in HINT_WORDS.findall(title)}),
                    "_body": [],
                }
                entries.append(current)
                continue
            if current is None:
                continue
            current["_body"].append(line)
            field = FIELD.match(line.strip())
            if not field:
                continue
            name, value = field.group(1).strip().lower(), field.group(2).strip()
            if name == "tags":
                current["tags"] = [t.strip().lower() for t in value.split(",") if t.strip()]
            elif name in KEPT_FIELDS:
                if name == "status" and TEMPLATE_STATUS.fullmatch(value):
                    continue
                current.setdefault(KEPT_FIELDS[name], value)
    return entries


def matches(entry, tags, terms):
    if tags and set(tags) & set(entry["tags"]):
        return True
    text = entry["title"] + "\n" + "".join(entry["_body"])
    return any(re.search(term, text, re.IGNORECASE) for term in terms)


def sort_key(entry):
    # Undated entries sort after dated ones; file position breaks ties.
    return (entry["date"] is None, entry["date"] or "", entry["file"], entry["line"])


def render(entry):
    parts = [
        "{}:{}".format(entry["file"], entry["line"]),
        entry["date"] or "undated",
        "#" * entry["level"] + " " + entry["title"],
    ]
    lines = ["  ".join(parts)]
    extras = []
    for key in ("status", "supersedes", "superseded_by", "scope", "revisit", "resolved_by"):
        if key in entry:
            extras.append("{}: {}".format(key, entry[key]))
    if entry["hints"]:
        extras.append("hints: " + ", ".join(entry["hints"]))
    if entry["positional_ids"]:
        extras.append("positional ids (do not resolve): " + ", ".join(entry["positional_ids"]))
    extras.append("tags: " + (", ".join(entry["tags"]) if entry["tags"] else "(none)"))
    lines.extend("    " + extra for extra in extras)
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--living-dir", default=".living")
    parser.add_argument("--tag", action="append", default=[],
                        help="exact tag, case-insensitive; repeatable")
    parser.add_argument("--term", action="append", default=[],
                        help="regex searched in heading and body; repeatable")
    parser.add_argument("--include-learnings", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    names = ["decisions.md"] + (["learnings.md"] if args.include_learnings else [])
    entries = []
    for name in names:
        path = os.path.join(args.living_dir, name)
        if os.path.isfile(path):
            entries.extend(parse_entries(path))
        else:
            print("missing: " + path, file=sys.stderr)
    if not entries:
        return 1

    tags = [t.lower() for t in args.tag]
    if tags or args.term:
        selected = [e for e in entries if matches(e, tags, args.term)]
    else:
        selected = entries
    selected.sort(key=sort_key)

    if args.json:
        for entry in selected:
            del entry["_body"]
        json.dump(selected, sys.stdout, indent=1)
        print()
        return 0

    print("{} of {} entries; oldest first. Raw fields only: no status is inferred.".format(
        len(selected), len(entries)))
    for entry in selected:
        print(render(entry))
    return 0


if __name__ == "__main__":
    sys.exit(main())
