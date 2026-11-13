#!/usr/bin/env python3
"""Read-only status of an analysis map (plans/MAP.md and plans/map/NN-slug.md).

Run: <skill-dir>/../../hooks/mxpy - <analysis-dir | plans-dir | MAP.md> < <this file>
Prints the frontier, blocked, claimed and closed tickets and the fog count.
Exit 0 when the map is sound, 1 when it has problems, 2 on a usage error.
Writes nothing.
"""
import re
import sys
from pathlib import Path

TYPES = {"research", "prototype", "grilling", "task"}
STATUSES = {"open", "closed"}
NONE_WORDS = {"", "none", "-", "n/a"}


def find_map(arg):
    p = Path(arg)
    for cand in (p, p / "MAP.md", p / "plans" / "MAP.md"):
        if cand.is_file() and cand.name == "MAP.md":
            return cand
    return None


def header_fields(text):
    """Key: value lines before the first '## ' heading."""
    fields, title = {}, ""
    for line in text.splitlines():
        if line.startswith("## "):
            break
        if line.startswith("# ") and not title:
            title = line[2:].strip()
            continue
        m = re.match(r"^([A-Za-z][A-Za-z ]*?):\s*(.*)$", line)
        if m:
            fields.setdefault(m.group(1).strip().lower(), m.group(2).strip())
    return title, fields


def section(text, name):
    m = re.search(r"^##\s+" + re.escape(name) + r"\s*$", text, re.M | re.I)
    if not m:
        return None
    rest = text[m.end():]
    n = re.search(r"^##\s", rest, re.M)
    return rest[: n.start()] if n else rest


def bullets(body):
    body = re.sub(r"<!--.*?-->", "", body or "", flags=re.S)
    return [ln.strip()[2:].strip() for ln in body.splitlines() if re.match(r"^\s*[-*]\s+\S", ln)]


def items(body):
    """Count entries in a section: each bullet is one; a block of plain lines is one."""
    body = re.sub(r"<!--.*?-->", "", body or "", flags=re.S)
    found = []
    for block in re.split(r"\n\s*\n", body):
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        if any(re.match(r"^[-*]\s+\S", ln) for ln in lines):
            found += [ln[2:].strip() for ln in lines if re.match(r"^[-*]\s+\S", ln)]
        else:
            found.append(" ".join(lines))
    return found


def load(map_path):
    problems = []
    plans = map_path.parent
    tickets = {}
    for f in sorted((plans / "map").glob("[0-9]*-*.md")):
        title, fields = header_fields(f.read_text(encoding="utf-8"))
        blocked = fields.get("blocked by", "")
        claim = fields.get("claimed", "")
        resolution = section(f.read_text(encoding="utf-8"), "Resolution") or ""
        tickets[f.stem] = {
            "title": title or f.stem,
            "type": fields.get("type", "").lower(),
            "status": fields.get("status", "").lower(),
            "blocked": blocked,
            "claim": "" if claim.lower() in NONE_WORDS else claim,
            "resolution": re.sub(r"<!--.*?-->", "", resolution, flags=re.S).strip(),
        }
    return tickets, problems


def resolve(ref, tickets):
    """A blocker names a ticket by file stem, by its NN prefix, or by title.
    Returns (key or None, all matches), so an ambiguous prefix can be told from a missing ticket."""
    ref = ref.strip().strip("`").removesuffix(".md")
    if ref in tickets:
        return ref, [ref]
    hits = [k for k in tickets if k.split("-", 1)[0] == ref or tickets[k]["title"].lower() == ref.lower()]
    return (hits[0] if len(hits) == 1 else None), hits


def blockers(field, tickets):
    """Split 'Blocked by' on ';' first. A piece that is not one ticket is split again on ',', so a title
    with a comma still works when written alone or after a ';'."""
    refs = []
    for piece in field.split(";"):
        piece = piece.strip()
        if piece.lower() in NONE_WORDS:
            continue
        if resolve(piece, tickets)[1]:
            refs.append(piece)
        else:
            refs += [b.strip() for b in piece.split(",") if b.strip().lower() not in NONE_WORDS]
    return refs


def find_cycle(edges):
    state, stack = {}, []

    def visit(n):
        state[n] = 1
        stack.append(n)
        for m in edges.get(n, []):
            if state.get(m) == 1:
                return stack[stack.index(m):] + [m]
            if m not in state:
                found = visit(m)
                if found:
                    return found
        state[n] = 2
        stack.pop()
        return None

    for n in edges:
        if n not in state:
            found = visit(n)
            if found:
                return found
    return None


def main(argv):
    if len(argv) != 1:
        print("usage: map_status.py <analysis-dir | plans-dir | MAP.md>", file=sys.stderr)
        return 2
    map_path = find_map(argv[0])
    if not map_path:
        print(f"no MAP.md under {argv[0]}", file=sys.stderr)
        return 2
    raw = map_path.read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    tickets, problems = load(map_path)

    for key, t in tickets.items():
        if t["type"] not in TYPES:
            problems.append(f"{key}: type '{t['type']}' is not one of {sorted(TYPES)}")
        if t["status"] not in STATUSES:
            problems.append(f"{key}: status '{t['status']}' is not open or closed")
        if t["status"] == "closed" and not t["resolution"]:
            problems.append(f"{key}: closed with an empty Resolution")
        if t["status"] == "closed" and t["claim"]:
            problems.append(f"{key}: closed but still claimed")

    edges = {}
    for key, t in tickets.items():
        edges[key] = []
        for ref in blockers(t["blocked"], tickets):
            hit, hits = resolve(ref, tickets)
            if len(hits) > 1:
                problems.append(f"{key}: blocked by '{ref}', which matches {len(hits)} tickets ({', '.join(hits)}); use the full file name")
            elif hit is None:
                problems.append(f"{key}: blocked by '{ref}', which is not a ticket")
            elif hit == key:
                problems.append(f"{key}: blocks itself")
            else:
                edges[key].append(hit)
    cycle = find_cycle(edges)
    if cycle:
        problems.append("cycle: " + " -> ".join(cycle))

    for target in re.findall(r"\]\(\s*(?:\./)?map/([^)\s#]+?)(?:\.md)?\s*(?:#[^)]*)?\)", text):
        if target not in tickets:
            problems.append(f"MAP.md links map/{target}.md, which does not exist")
    for key, t in tickets.items():
        if t["status"] == "closed":
            link = re.compile(r"map/" + re.escape(key) + r"(?![\w-])")
            in_decisions = link.search(section(text, "Decisions so far") or "")
            scoped_out = section(text, "Out of scope") or ""
            in_out = link.search(scoped_out) or t["title"].lower() in scoped_out.lower() or re.search(
                r"(?<![\w-])" + re.escape(key) + r"(?![\w-])", scoped_out)
            if not in_decisions and not in_out:
                problems.append(f"{key}: closed but in neither Decisions so far nor Out of scope")
    for name in ("Destination", "Decisions so far", "Not yet specified", "Out of scope"):
        if section(text, name) is None:
            problems.append(f"MAP.md has no '## {name}' section")

    def open_blockers(key):
        return [b for b in edges[key] if tickets[b]["status"] != "closed"]

    openk = [k for k, t in tickets.items() if t["status"] == "open"]
    claimed = [k for k in openk if tickets[k]["claim"]]
    frontier = [k for k in openk if not tickets[k]["claim"] and not open_blockers(k)]
    blocked = [k for k in openk if open_blockers(k)]
    closed = [k for k, t in tickets.items() if t["status"] == "closed"]
    fog = items(section(text, "Not yet specified"))
    out = items(section(text, "Out of scope"))

    print(f"map: {map_path}")
    print(f"frontier {len(frontier)}  blocked {len(blocked)}  claimed {len(claimed)}  closed {len(closed)}  fog {len(fog)}  out-of-scope {len(out)}")
    for k in frontier:
        print(f"  frontier: {tickets[k]['title']} [{tickets[k]['type']}] ({k})")
    for k in blocked:
        names = ", ".join(tickets[b]["title"] for b in open_blockers(k))
        print(f"  blocked: {tickets[k]['title']} waits on {names}")
    for k in claimed:
        print(f"  claimed: {tickets[k]['title']} by {tickets[k]['claim']}")
    if not openk and tickets and not fog:
        print("route clear: no open tickets and no fog; hand the decisions to grill")
    elif not openk and fog:
        print("no open tickets but fog remains: graduate it into tickets or close it out")
    for p in problems:
        print(f"PROBLEM: {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
