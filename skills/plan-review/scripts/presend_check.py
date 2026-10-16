"""Flag likely secrets and identifiers in a plan-review packet before it leaves the machine (roadmap C3).

The packet goes to Codex (OpenAI) and Biomni (Phylo). This check reads it locally and reports what looks
like a secret, a contact detail, a home-directory path, or a participant identifier from the plan's own
input tables. It is conservative and pattern-based: a clean result is not evidence that nothing sensitive
remains. It reports, the user decides, and it never prints a matched value in full.

    python3 - --packet <(cat <<'EOF'
    <the packet>
    EOF
    ) [--repo <repository root>] < presend_check.py

Add `--json` for one structured result on stdout instead of the text (same exit status): the packet's
SHA-256 and size, each flag as line, kind and masked value, whether `redactions:` is valid, and each
unread or unsupported input as a masked name and a reason. It never carries a matched value in full. The
SHA-256 is of the exact bytes read, so `scripts/review_packet.py` can bind consent to them.

Exit 0: nothing flagged. 1: the packet cannot be read. 2: something flagged and the packet's
`redactions:` lists what was removed, so the user decides. 3: something flagged and `redactions:` is
empty or missing, so do not send. Plain text on stdout.

What is and is not caught is the PATTERNS table below. Not caught, by design: a secret with no recognisable
shape or keyword, a name or an identifier in free text, a value in a table the plan does not name under
`Inputs:`, anything in a language the patterns do not cover, and re-identification by combining facts.
"""

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys

NOTE = "This check is pattern-based. A clean result is not evidence that nothing sensitive remains."

# (kind, pattern, why it may be sensitive). Listed so a user can see what is and is not caught.
PATTERNS = [
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "a private key block"),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "an AWS access key ID"),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b"), "a GitHub token"),
    ("API key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"), "a key in the sk-... form"),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "a Slack token"),
    ("bearer token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}"), "an authorization header value"),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "a signed token"),
    ("credential in URL", re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@"), "a user and password in a URL"),
    ("secret assignment",
     re.compile(r"(?i)\b(?:api[_-]?key|secret|token|passw(?:or)?d|pwd|auth(?:orization)?)\b[\"']?\s*[:=]\s*[\"']?"
                r"(?![\"']?(?:none|null|true|false|required|redacted|\.\.\.|<|\[|\{|\$))[^\s\"']{8,}"),
     "a value assigned to a name like token or password"),
    ("email address", re.compile(r"\b[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b"), "a contact detail"),
    ("home path", re.compile(r"(?:/home/|/Users/|[A-Za-z]:\\Users\\)[^/\\\s\"'`]+"), "a path that names a person's account"),
    ("IPv4 address", re.compile(r"(?<![\w.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\w.])"),
     "a network address"),
]
# Columns of a table named under `Inputs:` whose values are read as participant or sample identifiers.
ID_COLUMN = re.compile(r"(?i)^(?:donor|subject|participant|patient|individual|person|case|specimen|mrn|"
                       r"sample|sample_?id|subject_?id|participant_?id|patient_?id|donor_?id)$")
MIN_ID = 1          # known short IDs still need exact token boundaries
MAX_ROWS = 100000   # rows read per input table
INPUT_EXT = (".tsv", ".csv", ".txt")
REDACTIONS = re.compile(r"^(?P<indent>[ \t]*)redactions[ \t]*:[ \t]*(?P<rest>[^\n]*?)[ \t]*$", re.MULTILINE)


def mask(value, keep=3):
    """Enough to find the place, not enough to reuse the value. An identifier keeps one character: a short
    one is its first three."""
    return "{}... ({} chars)".format(value[:keep] if len(value) > 2 * keep else "[masked]", len(value))


def redactions_listed(packet):
    """Require nonempty kind/field pairs; arbitrary scalars cannot satisfy disclosure."""
    matches = list(REDACTIONS.finditer(packet))
    if len(matches) != 1:
        return False
    match = matches[0]
    rest = re.sub(r"\s+#.*$", "", match.group("rest")).strip()
    if rest:
        try:
            entries = json.loads(rest)
        except ValueError:
            return False
    else:
        entries, current = [], None
        for line in packet[match.end():].splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            item = re.fullmatch(r"\s*-\s+kind:\s*(.+?)\s*", line)
            field = re.fullmatch(r"\s+(field|replaced_with):\s*(.+?)\s*", line)
            if item:
                current = {"kind": item.group(1).strip("\"'")}
                entries.append(current)
            elif field and current is not None and field.group(1) not in current:
                current[field.group(1)] = field.group(2).strip("\"'")
            elif line[:1].isspace():
                return False
            else:
                break
    return isinstance(entries, list) and bool(entries) and all(
        isinstance(entry, dict) and {"kind", "field"}.issubset(entry)
        and not set(entry) - {"kind", "field", "replaced_with"} and all(
            isinstance(value, str) and value.strip() and value.lower() not in ("null", "none", "~")
            for value in entry.values()) for entry in entries)


def packet_inputs(packet):
    """Paths named on the packet's or plan's `Inputs:` line."""
    found = []
    for match in re.finditer(r"(?im)^[ \t]*Inputs[ \t]*:[ \t]*([^\n]*)$", packet):
        for parts in re.findall(r"`([^`]+)`|\"([^\"]+)\"|'([^']+)'|([^,;\s]+)", match.group(1)):
            found.append(next(p for p in parts if p))
    return found


def known_identifiers(packet, repo):
    """{identifier: column} from the ID-like columns of the tables the plan names as inputs, under `repo`."""
    ids, unread = {}, []
    for rel in packet_inputs(packet):
        path = rel if os.path.isabs(rel) else os.path.join(repo, rel)
        if not rel.lower().endswith(INPUT_EXT):
            if rel.lower() not in ("none", "n/a"):
                unread.append(rel)
            continue
        if not os.path.isfile(path):
            unread.append(rel)
            continue
        try:
            with open(path, encoding="utf-8-sig", errors="strict", newline="") as handle:
                sample = handle.read(4096)
                handle.seek(0)
                delimiter = "," if sample.count(",") > sample.count("\t") else "\t"
                reader = csv.reader(handle, delimiter=delimiter, strict=True)
                header = next(reader, [])
                if not header or len(set(header)) != len(header):
                    unread.append(rel)
                columns = [i for i, name in enumerate(header) if ID_COLUMN.match(name.strip())]
                for n, row in enumerate(reader):
                    if n >= MAX_ROWS:
                        unread.append(rel)
                        break
                    if len(row) != len(header) and rel not in unread:
                        unread.append(rel)
                    for i in columns:
                        if i < len(row) and len(row[i].strip()) >= MIN_ID:
                            ids.setdefault(row[i].strip(), header[i].strip())
        except (OSError, csv.Error, UnicodeError):
            unread.append(rel)
    return ids, unread


def check(packet, repo=None):
    """(flags, unread inputs). A flag is (line, kind, masked value, why)."""
    flags = []
    lines = packet.splitlines()
    for number, line in enumerate(lines, 1):
        for kind, pattern, why in PATTERNS:
            for match in pattern.finditer(line):
                flags.append((number, kind, mask(match.group(0)), why))
    unread = []
    if repo:
        ids, unread = known_identifiers(packet, repo)
        if ids:
            token = re.compile(r"(?<![\w-])(?:{})(?![\w-])".format(
                "|".join(re.escape(v) for v in sorted(ids, key=len, reverse=True))))
            for number, line in enumerate(lines, 1):
                for match in token.finditer(line):
                    flags.append((number, "participant identifier", mask(match.group(0), keep=1),
                                  "a value in a known identifier column of an input table"))
    return sorted(set(flags)), unread


def render(flags, unread, listed):
    out = []
    if flags:
        out.append("Pre-send check: {} flag(s) in the packet.".format(len(flags)))
        out += ["- line {}: {} `{}` ({}).".format(*f) for f in flags[:30]]
        if len(flags) > 30:
            out.append("- ... {} more.".format(len(flags) - 30))
        if listed:
            out.append("`redactions:` lists what was removed. Show these flags to the user; they decide whether to send.")
        else:
            out.append("`redactions:` is empty or malformed, so do not send. Remove or replace each flagged value and list "
                       "what was removed (kind and field, never the value), or tell the user why it must stay.")
    else:
        out.append("Pre-send check: nothing flagged.")
    if unread:
        out.append("Not checked against identifiers: {} input(s) (missing, unsupported, malformed or truncated). Do not send before disclosing this coverage gap.".format(len(unread)))
    out.append(NOTE)
    return "\n".join(out) + "\n"


def unread_reasons(unread, repo):
    """Why each unread input was not checked: the name masked, never the path in full."""
    out = []
    for rel in sorted(set(unread)):
        path = rel if os.path.isabs(rel) else os.path.join(repo, rel)
        reason = ("unsupported type" if not rel.lower().endswith(INPUT_EXT) else
                  "missing" if not os.path.isfile(path) else "unreadable, malformed or truncated")
        out.append({"input": mask(rel), "reason": reason})
    return out


def analyse(raw, repo=None):
    """Scan the packet bytes `raw`. Returns the structured result; its `exit` is the exit status."""
    packet = raw.decode("utf-8", errors="replace").replace("\r\n", "\n")  # as text mode read it
    flags, unread = check(packet, repo)
    listed = redactions_listed(packet)
    matches = list(REDACTIONS.finditer(packet))
    valid = len(matches) == 1 and (re.sub(r"\s+#.*$", "", matches[0].group("rest")).strip() == "[]" or listed)
    return {"schema": "mycelium-extra.presend-check.v1", "packet_sha256": hashlib.sha256(raw).hexdigest(),
            "packet_bytes": len(raw), "flags": flags, "unread": unread, "redactions_listed": listed,
            "redactions_valid": valid, "inputs_unread": unread_reasons(unread, repo) if repo else [],
            "exit": 3 if unread or not valid else 0 if not flags else 2 if listed else 3, "note": NOTE}


def as_json(result):
    keys = ("schema", "packet_sha256", "packet_bytes", "exit", "redactions_listed", "redactions_valid",
            "inputs_unread", "note")
    out = {k: result[k] for k in keys}
    out["flags"] = [{"line": n, "kind": k, "masked": m, "why": w} for n, k, m, w in result["flags"]]
    return json.dumps(out, indent=2, sort_keys=True) + "\n"


def main(argv):
    parser = argparse.ArgumentParser(prog="presend_check")
    parser.add_argument("--packet", required=True, help="the packet text (a path; use process substitution)")
    parser.add_argument("--repo", default=None, help="repository root, to read the tables the plan names under Inputs:")
    parser.add_argument("--json", action="store_true", help="print one structured result instead of text")
    args = parser.parse_args(argv)
    try:
        with open(args.packet, "rb") as handle:
            raw = handle.read()
    except (OSError, IOError) as error:
        sys.stderr.write("presend_check: cannot read the packet: {}\n".format(error))
        return 1
    result = analyse(raw, os.path.abspath(args.repo) if args.repo else None)
    if args.json:
        sys.stdout.write(as_json(result))
        return result["exit"]
    sys.stdout.write("Packet sha256: {} ({} bytes). Consent applies to these exact bytes only.\n".format(
        result["packet_sha256"], result["packet_bytes"]))
    sys.stdout.write(render(result["flags"], result["unread"], result["redactions_listed"]))
    if not result["redactions_valid"]:
        sys.stdout.write("Redaction entries are missing or malformed; do not send. Use [] or objects with kind/field strings.\n")
    return result["exit"]


if __name__ == "__main__":
    if sys.stdout.encoding.lower().replace("-", "") != "utf8":  # an ASCII locale on Python 3.6
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, sys.stdout.encoding, "backslashreplace")
    sys.exit(main(sys.argv[1:]))
