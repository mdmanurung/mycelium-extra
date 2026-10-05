#!/usr/bin/env python3
"""Check that every relative link and #anchor in the given Markdown files resolves.

Usage: check_links.py FILE.md [FILE.md ...]

- Links: inline [text](target) and reference definitions "[id]: target".
  http(s):, mailto: and other scheme links are skipped, and so are template
  placeholders such as @@DOC@@. Links inside fenced code blocks and inline code
  spans are ignored.
- A path is resolved relative to the linking file and must exist (file or folder).
- An anchor (#frag, or path.md#frag) must match a heading in the target file using
  GitHub's rules: lowercase; drop every character that is not a letter, digit,
  space, hyphen or underscore; spaces become hyphens; a repeated slug gets -1, -2...
  Explicit <a name="..."> / id="..." anchors are accepted too.
Exit status 1 if any link fails, 2 if no file is given.
"""
import os
import re
import sys

LINK = re.compile(r"(?<!\!)\[(?:[^\]\[]|\[[^\]]*\])*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
IMG = re.compile(r"\!\[[^\]]*\]\(([^)\s]+)\)")
REFDEF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s+(\S+)")


def strip_code(text):
    out = []
    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```") or line.strip().startswith("~~~"):
            in_code = not in_code
            out.append("")
            continue
        out.append("" if in_code else re.sub(r"`[^`]*`", "``", line))
    return out


def slug(heading):
    h = heading.strip().lower()
    h = re.sub(r"[^\w\- ]", "", h, flags=re.UNICODE)
    return h.replace(" ", "-")


def anchors(path):
    text = open(path, encoding="utf-8").read()
    found = set()
    counts = {}
    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
        if m:
            # GitHub drops formatting markers but keeps the inner text
            raw = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", m.group(1))
            s = slug(raw)
            n = counts.get(s, 0)
            found.add(s if n == 0 else "%s-%d" % (s, n))
            counts[s] = n + 1
    for m in re.finditer(r"<a\s+(?:name|id)=\"([^\"]+)\"", text):
        found.add(m.group(1))
    return found


def main(files):
    bad = 0
    checked = 0
    for f in files:
        lines = strip_code(open(f, encoding="utf-8").read())
        for i, line in enumerate(lines, 1):
            targets = [m.group(1) for m in LINK.finditer(line)]
            targets += [m.group(1) for m in IMG.finditer(line)]
            m = REFDEF.match(line)
            if m:
                targets.append(m.group(1))
            for t in targets:
                t = t.strip("<>")
                if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", t) or re.match(r"^@@\w+@@$", t):
                    continue
                checked += 1
                path, _, frag = t.partition("#")
                target = os.path.normpath(os.path.join(os.path.dirname(f), path)) if path else f
                if not os.path.exists(target):
                    print("%s:%d: missing file %s" % (f, i, t))
                    bad += 1
                    continue
                if frag:
                    if os.path.isdir(target) or not target.endswith(".md"):
                        print("%s:%d: anchor on non-Markdown target %s" % (f, i, t))
                        bad += 1
                    elif frag not in anchors(target):
                        print("%s:%d: missing anchor %s" % (f, i, t))
                        bad += 1
    print("links checked: %d, broken: %d" % (checked, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
