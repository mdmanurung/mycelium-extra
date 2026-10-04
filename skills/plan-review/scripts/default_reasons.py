"""Flag plan rows whose `default:` source gives no usable reason (roadmap D9).

grill labels a technical choice it made itself `default: <reason>` in the plan
table's Source column. This check flags a `default:` with no reason, a reason
under MIN_WORDS words, or a reason that is only one of EMPTY_PHRASES. It is
advisory: it reports, it never blocks, and it does not judge whether a reason
is correct.

    python3 - --plan <(cat <<'EOF'
    <the plan>
    EOF
    ) < default_reasons.py

Prints plain text. Exit 0 when the plan was checked (flags or not), 1 when the
plan cannot be read, 3 when the text holds no plan table (nothing was checked).
verify imports check_plan() from this file.
"""

import argparse
import io
import re
import sys

# Reasons that give a reviewer nothing to push back on. Matched case-insensitively
# as whole words (a trailing "s" is allowed). Extend this list as needed.
EMPTY_PHRASES = [
    "standard",
    "common practice",
    "best practice",
    "typical",
]

# A reason needs at least this many words, not counting FILLER. A reason that
# contains an empty phrase needs this many words besides the phrase.
MIN_WORDS = 3
FILLER = {"a", "an", "the", "is", "it", "its", "it's", "this", "that", "just", "and", "or"}

TABLE_ROW = re.compile(r"^\s*\|(.*)\|\s*$")
TABLE_RULE = re.compile(r"^\s*\|[\s:|-]*-[\s:|-]*\|\s*$")
DEFAULT = re.compile(r"(?<![\w-])default\s*:", re.IGNORECASE)
NEXT_SOURCE = re.compile(r"(?<![\w-])(?:default|repo)\s*:", re.IGNORECASE)
WORD = re.compile(r"[^\W_](?:[\w'.+/-]*[^\W_])?", re.UNICODE)


def split_row(line):
    match = TABLE_ROW.match(line)
    if not match:
        return None
    return [c.replace("\0", "|").strip() for c in match.group(1).replace("\\|", "\0").split("|")]


def tables(plan):
    """Yield (header, [(line number, cells)]) for each Markdown table in the text."""
    lines = plan.splitlines()
    header, rows = None, []
    for i, line in enumerate(lines):
        cells = split_row(line)
        if cells is None:
            if header is not None:
                yield header, rows
            header, rows = None, []
            continue
        if TABLE_RULE.match(line):
            continue
        following = lines[i + 1] if i + 1 < len(lines) else ""
        if TABLE_RULE.match(following):
            if header is not None:
                yield header, rows
            header, rows = [c.lower() for c in cells], []
        elif header is not None:
            rows.append((i + 1, cells))
    if header is not None:
        yield header, rows


def problem(reason):
    """None when the reason is usable, else a short description of what is wrong."""
    text = reason.lower()
    words = [w for w in WORD.findall(text) if w not in FILLER]
    if not words:
        return "no reason"
    stripped = text
    for phrase in EMPTY_PHRASES:
        pattern = r"(?<!\w)" + r"\s+".join(re.escape(part) for part in phrase.lower().split()) + r"s?(?!\w)"
        stripped = re.sub(pattern, " ", stripped)
    left = [w for w in WORD.findall(stripped) if w not in FILLER]
    if stripped != text and len(left) < MIN_WORDS:
        return "an empty phrase, not a reason"
    if len(words) < MIN_WORDS:
        return "a reason under {} words".format(MIN_WORDS)
    return None


def check_plan(plan):
    """(tables found, defaults found, flags). Each flag is a dict with row, step, column, line, text,
    problem. Only the Source column is read when the table has one; otherwise every cell is."""
    found, defaults, flags = 0, 0, []
    for header, rows in tables(plan):
        found += 1
        columns = [i for i, name in enumerate(header) if name == "source"] or list(range(len(header)))
        step = header.index("step") if "step" in header else None
        for line, cells in rows:
            for i in columns:
                if i >= len(cells):
                    continue
                for match in DEFAULT.finditer(cells[i]):
                    defaults += 1
                    rest = cells[i][match.end():]
                    later = NEXT_SOURCE.search(rest)
                    issue = problem((rest[:later.start()] if later else rest).strip())
                    if issue:
                        flags.append({"row": cells[0] or "at line {}".format(line),
                                      "step": cells[step] if step is not None and step < len(cells) else "",
                                      "column": header[i] if i < len(header) else "", "line": line,
                                      "text": cells[i], "problem": issue})
    return found, defaults, flags


def describe(flag):
    step = flag["step"]
    if len(step) > 60:
        step = step[:57] + "..."
    return "row {}{}: \"{}\" is {}.".format(flag["row"], " ({})".format(step) if step else "",
                                          flag["text"], flag["problem"])


def render(found, defaults, flags):
    if not found:
        return "Default reasons not checked: no plan table found.\n"
    if not flags:
        return "Default reasons: {} default(s), each with a reason.\n".format(defaults)
    lines = ["Default reasons (advisory): {} of {} default(s) need a reason.".format(len(flags), defaults)]
    lines += ["- " + describe(flag) for flag in flags]
    lines.append("Give each one a reason a reviewer can check against this data, or source it as user or repo: <path>.")
    return "\n".join(lines) + "\n"


def main(argv):
    parser = argparse.ArgumentParser(prog="default_reasons")
    parser.add_argument("--plan", required=True, help="the plan text (a path; use process substitution)")
    args = parser.parse_args(argv)
    try:
        with open(args.plan, encoding="utf-8", errors="replace") as handle:
            plan = handle.read()
    except (OSError, IOError) as error:
        sys.stderr.write("default_reasons: cannot read the plan: {}\n".format(error))
        return 1
    found, defaults, flags = check_plan(plan)
    sys.stdout.write(render(found, defaults, flags))
    return 0 if found else 3


if __name__ == "__main__":
    if sys.stdout.encoding.lower().replace("-", "") != "utf8":  # an ASCII locale on Python 3.6
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, sys.stdout.encoding, "backslashreplace")
    sys.exit(main(sys.argv[1:]))
