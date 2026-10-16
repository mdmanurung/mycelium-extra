"""Flag likely secrets and identifiers in a plan-review packet before it leaves the machine (roadmap C3).

The packet goes to Codex (OpenAI) and Biomni (Phylo). This check reads it locally and reports what looks
like a secret, a contact detail, a home-directory path, or a participant identifier from the plan's own
input tables. It is conservative and pattern-based: a clean result is not evidence that nothing sensitive
remains. It reports, the user decides, and it never prints a matched value in full.

    python3 - --packet <(cat <<'EOF'
    <the packet>
    EOF
    ) [--repo <repository root>] < presend_check.py

Exit 0: nothing flagged. 1: the packet cannot be read. 2: something flagged and the packet's
`redactions:` lists what was removed, so the user decides. 3: something flagged and `redactions:` is
empty or missing, so do not send. Plain text on stdout.

What is and is not caught is the PATTERNS table below. Not caught, by design: a secret with no recognisable
shape or keyword, a name or an identifier in free text, a value in a table the plan does not name under
`Inputs:`, anything in a language the patterns do not cover, and re-identification by combining facts.
"""

import argparse
import csv
import io
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
MIN_ID = 3          # shorter values are too common to mean anything
MAX_ROWS = 100000   # rows read per input table
INPUT_EXT = (".tsv", ".csv", ".txt")
REDACTIONS = re.compile(r"^(?P<indent>[ \t]*)redactions[ \t]*:[ \t]*(?P<rest>[^\n]*?)[ \t]*$", re.MULTILINE)


def mask(value, keep=3):
    """Enough to find the place, not enough to reuse the value. An identifier keeps one character: a short
    one is its first three."""
    return "{}... ({} chars)".format(value[:keep] if len(value) > 2 * keep else value[:1], len(value))


def redactions_listed(packet):
    """True when the packet's `redactions:` field names something; False when it is `[]`, empty or missing."""
    match = REDACTIONS.search(packet)
    if not match:
        return False
    rest = re.sub(r"\s*#.*$", "", match.group("rest")).strip()
    if rest:
        return rest not in ("[]", "~", "null")
    for line in packet[match.end():].splitlines():
        if line.strip():
            return bool(re.match(r"\s*-\s*[^\s#]", line))
    return False


def packet_inputs(packet):
    """Paths named on the packet's or plan's `Inputs:` line."""
    found = []
    for match in re.finditer(r"(?im)^\s*Inputs\s*:\s*(.+)$", packet):
        found += [p.strip("`,;\"'") for p in match.group(1).split() if p.strip("`,;\"'")]
    return found


def known_identifiers(packet, repo):
    """{identifier: column} from the ID-like columns of the tables the plan names as inputs, under `repo`."""
    ids, unread = {}, []
    for rel in packet_inputs(packet):
        path = rel if os.path.isabs(rel) else os.path.join(repo, rel)
        if not rel.lower().endswith(INPUT_EXT) or not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8", errors="replace", newline="") as handle:
                sample = handle.read(4096)
                handle.seek(0)
                delimiter = "," if sample.count(",") > sample.count("\t") else "\t"
                reader = csv.reader(handle, delimiter=delimiter)
                header = next(reader, [])
                columns = [i for i, name in enumerate(header) if ID_COLUMN.match(name.strip())]
                for n, row in enumerate(reader):
                    if n >= MAX_ROWS:
                        unread.append(rel)
                        break
                    for i in columns:
                        if i < len(row) and len(row[i].strip()) >= MIN_ID:
                            ids.setdefault(row[i].strip(), header[i].strip())
        except (OSError, csv.Error):
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
            token = re.compile(r"(?<![A-Za-z0-9])(?:{})(?![A-Za-z0-9])".format(
                "|".join(re.escape(v) for v in sorted(ids, key=len, reverse=True))))
            for number, line in enumerate(lines, 1):
                for match in token.finditer(line):
                    flags.append((number, "participant identifier", mask(match.group(0), keep=1),
                                  "a value in the `{}` column of an input table".format(ids[match.group(0)])))
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
            out.append("`redactions:` is empty, so do not send. Remove or replace each flagged value and list "
                       "what was removed (kind and field, never the value), or tell the user why it must stay.")
    else:
        out.append("Pre-send check: nothing flagged.")
    if unread:
        out.append("Not checked against identifiers: {} (unreadable or too long).".format(", ".join(unread)))
    out.append(NOTE)
    return "\n".join(out) + "\n"


def main(argv):
    parser = argparse.ArgumentParser(prog="presend_check")
    parser.add_argument("--packet", required=True, help="the packet text (a path; use process substitution)")
    parser.add_argument("--repo", default=None, help="repository root, to read the tables the plan names under Inputs:")
    args = parser.parse_args(argv)
    try:
        with open(args.packet, encoding="utf-8", errors="replace") as handle:
            packet = handle.read()
    except (OSError, IOError) as error:
        sys.stderr.write("presend_check: cannot read the packet: {}\n".format(error))
        return 1
    flags, unread = check(packet, os.path.abspath(args.repo) if args.repo else None)
    listed = redactions_listed(packet)
    sys.stdout.write(render(flags, unread, listed))
    return 0 if not flags else 2 if listed else 3


if __name__ == "__main__":
    if sys.stdout.encoding.lower().replace("-", "") != "utf8":  # an ASCII locale on Python 3.6
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, sys.stdout.encoding, "backslashreplace")
    sys.exit(main(sys.argv[1:]))
