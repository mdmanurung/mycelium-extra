#!/usr/bin/env python3
"""Reference checks for docs/validation-recipes.md recipes 4 to 9. Copy one into a project and bind it.

Each subcommand reads TSV/CSV tables, writes {"status", "message"} to --out when given, and exits 0 for
passed or unsupported, 2 for failed. A missing file, missing column or unreadable table is `unsupported`,
never a pass. Every check states one claim; none of them says the analysis is right.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys

MISSING = {"", "NA", "NaN", "nan", "NULL"}


class Gap(Exception):
    """The check could not run: reported as unsupported, not as a failure of the analysis."""


def table(path, *need):
    try:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle, delimiter="," if path.endswith(".csv") else "\t", strict=True))
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        raise Gap("cannot read {}: {}".format(path, error))
    if not rows:
        raise Gap("{} has no data rows".format(path))
    cols = list(rows[0])
    for column in need:
        if column not in cols:
            raise Gap("{} has no column '{}'".format(path, column))
    if any(None in row or None in row.values() for row in rows):
        raise Gap("{} has a ragged row".format(path))
    return rows


def number(text):
    try:
        return float(text)
    except ValueError:
        return None


def count(text):
    value = number(text)
    return value is not None and math.isfinite(value) and value >= 0 and value == int(value)


def bad(text):
    """Missing or not a finite number: what a failed conversion leaves behind."""
    value = number(text)
    return text in MISSING or value is None or not math.isfinite(value)


def sample(items):
    return ", ".join(sorted(map(str, items))[:5]) + (" ..." if len(items) > 5 else "")


def missingness(a):
    before, after = table(a.before, a.key, *a.columns), table(a.after, a.key, *a.columns)
    index = {r[a.key]: r for r in after}
    lost = sorted(r[a.key] for r in before if r[a.key] not in index)
    if lost:
        return "failed", "{} key(s) in --before are absent after: {}".format(len(lost), sample(lost))
    new_bad, filled = [], []
    for row in before:
        for column in a.columns:
            was, now = row[column], index[row[a.key]][column]
            if was not in MISSING and bad(now):
                new_bad.append("{}:{}".format(row[a.key], column))
            if was in MISSING and now not in MISSING and not a.allow_fill:
                filled.append("{}:{}".format(row[a.key], column))
    if new_bad:
        return "failed", "{} value(s) became missing or non-finite: {}".format(len(new_bad), sample(new_bad))
    if filled:
        return "failed", "{} missing value(s) were filled without --allow-fill: {}".format(len(filled), sample(filled))
    return "passed", "no value became missing, non-finite or filled in {} row(s)".format(len(before))


def join(a):
    left, right = table(a.left, a.key), table(a.right, a.key)
    counts = {}
    for row in right:
        counts[row[a.key]] = counts.get(row[a.key], 0) + 1
    problems = []
    if a.relation in ("many_to_one", "one_to_one"):
        dup = [k for k, n in counts.items() if n > 1]
        if dup:
            problems.append("{} right key(s) repeat, so rows multiply: {}".format(len(dup), sample(dup)))
    if a.relation in ("one_to_one", "one_to_many"):
        seen = {}
        for row in left:
            seen[row[a.key]] = seen.get(row[a.key], 0) + 1
        dup = [k for k, n in seen.items() if n > 1] if a.relation == "one_to_one" else []
        if dup:
            problems.append("{} left key(s) repeat: {}".format(len(dup), sample(dup)))
    if a.require_all_left:
        unmatched = sorted({r[a.key] for r in left} - set(counts))
        if unmatched:
            problems.append("{} left key(s) have no match: {}".format(len(unmatched), sample(unmatched)))
    if problems:
        return "failed", "; ".join(problems)
    return "passed", "right keys fit the declared {} relation".format(a.relation)


def denominator(a):
    universe = {r[a.key] for r in table(a.universe, a.key)}
    present = {r[a.key] for r in table(a.table, a.key)}
    missing = sorted(universe - present)
    if missing:
        return "failed", "{} of {} declared unit(s) are absent from the table: {}".format(
            len(missing), len(universe), sample(missing))
    return "passed", "all {} declared unit(s) appear in the table".format(len(universe))


def collide(a):
    groups = {}
    for row in table(a.map, a.raw, a.norm):
        groups.setdefault(row[a.norm], set()).add(row[a.raw])
    allowed = {}
    if a.crosswalk:
        for row in table(a.crosswalk, a.raw, "canonical"):
            allowed[row[a.raw]] = row["canonical"]
    clashes = [n for n, raws in groups.items()
               if len(raws) > 1 and any(allowed.get(r) != n for r in raws)]
    if clashes:
        return "failed", "{} normalized key(s) merge distinct raw keys that no crosswalk justifies: {}".format(
            len(clashes), sample(clashes))
    return "passed", "no unjustified merge in {} normalized key(s)".format(len(groups))


def invariants(a):
    rows = table(a.table, a.key, *a.unit, *a.integer, *a.accounting)
    problems = []
    keys = [r[a.key] for r in rows]
    if len(set(keys)) != len(keys):
        problems.append("duplicate {} values".format(a.key))
    units = [tuple(r[c] for c in a.unit) for r in rows] if a.unit else []
    dup = sorted({"/".join(u) for u in units if units.count(u) > 1})
    if dup:
        problems.append("{} repeated observational unit(s): {}".format(len(dup), sample(dup)))
    if a.meta:
        meta = {r[a.key] for r in table(a.meta, a.key)}
        off = sorted(set(keys) ^ meta)
        if off:
            problems.append("{} key(s) are on one side only: {}".format(len(off), sample(off)))
    for column in a.integer:
        odd = [r[a.key] for r in rows if not count(r[column])]
        if odd:
            problems.append("column {} is not non-negative integer counts in {} row(s)".format(column, len(odd)))
    if a.accounting:
        start, kept, removed = a.accounting
        odd = [r[a.key] for r in rows if not all(count(r[c]) for c in a.accounting)
               or number(r[start]) != number(r[kept]) + number(r[removed])]
        if odd:
            problems.append("{} != {} + {} with non-negative counts in {} row(s): {}".format(
                start, kept, removed, len(odd), sample(odd)))
    if problems:
        return "failed", "; ".join(problems)
    return "passed", "declared invariants hold for {} row(s)".format(len(rows))


def same(a):
    """Recipe 9: every table the baseline run lists has the same bytes in the new run."""
    try:
        with open(a.baseline, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise Gap("cannot read {}: {}".format(a.baseline, error))
    expected = {}
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)  # the format `sha256sum` writes
        if not match:
            raise Gap("{} line {} is not `<sha256>  <file>`".format(a.baseline, n))
        name = match.group(2)
        if os.path.isabs(name) or ".." in name.split("/") or name in expected:
            raise Gap("{} line {}: {} is absolute, leaves the run folder or repeats".format(a.baseline, n, name))
        expected[name] = match.group(1)
    if not expected:
        raise Gap("{} lists no tables, so nothing would be compared".format(a.baseline))
    if not os.path.isdir(a.run_dir):
        raise Gap("run folder {} not found".format(a.run_dir))
    missing, differ = [], []
    for name, digest in expected.items():
        path = os.path.join(a.run_dir, name)
        if not os.path.isfile(path):
            missing.append(name)
            continue
        with open(path, "rb") as handle:
            if hashlib.sha256(handle.read()).hexdigest() != digest:
                differ.append(name)
    problems = (["{} table(s) differ from the baseline: {}".format(len(differ), sample(differ))] if differ else []) + \
        (["{} table(s) missing from the run: {}".format(len(missing), sample(missing))] if missing else [])
    if problems:
        return "failed", "; ".join(problems)
    return "passed", "{} table(s) byte-identical to the baseline".format(len(expected))


def accounting(text):
    names = text.split(",")
    if len(names) != 3 or not all(names):
        raise argparse.ArgumentTypeError("name three columns: START,RETAINED,REMOVED")
    return names


def parser():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", help="write the {status, message} result here")
    sub = p.add_subparsers(dest="check")
    sub.required = True  # the required= keyword needs Python 3.7
    s = sub.add_parser("missingness", help="recipe 4")
    s.add_argument("--before", required=True)
    s.add_argument("--after", required=True)
    s.add_argument("--key", required=True)
    s.add_argument("--columns", required=True, type=lambda t: t.split(","))
    s.add_argument("--allow-fill", action="store_true", help="the plan declares that missing values are filled")
    s.set_defaults(run=missingness)
    s = sub.add_parser("join", help="recipe 5, join cardinality")
    s.add_argument("--left", required=True)
    s.add_argument("--right", required=True)
    s.add_argument("--key", required=True)
    s.add_argument("--relation", required=True, choices=["many_to_one", "one_to_one", "one_to_many"])
    s.add_argument("--require-all-left", action="store_true")
    s.set_defaults(run=join)
    s = sub.add_parser("denominator", help="recipe 5, denominator")
    s.add_argument("--universe", required=True, help="table of every unit the question is about")
    s.add_argument("--table", required=True, help="the table the analysis counts from")
    s.add_argument("--key", required=True)
    s.set_defaults(run=denominator)
    s = sub.add_parser("collide", help="recipe 6")
    s.add_argument("--map", required=True, help="table with the raw key and its normalized key per row")
    s.add_argument("--raw", required=True)
    s.add_argument("--norm", required=True)
    s.add_argument("--crosswalk", help="table with --raw and canonical: aliases the plan says are one entity")
    s.set_defaults(run=collide)
    s = sub.add_parser("invariants", help="recipe 7")
    s.add_argument("--table", required=True)
    s.add_argument("--key", required=True)
    s.add_argument("--unit", type=lambda t: t.split(","), default=[], help="columns that name one observational unit")
    s.add_argument("--meta", help="metadata table; its key set must equal the table's (order is ignored)")
    s.add_argument("--integer", type=lambda t: t.split(","), default=[], help="columns that must hold counts")
    s.add_argument("--accounting", type=accounting, default=[], metavar="START,RETAINED,REMOVED",
                   help="per row, START = RETAINED + REMOVED, all non-negative counts")
    s.set_defaults(run=invariants)
    s = sub.add_parser("same", help="recipe 9, same results after a refactor")
    s.add_argument("--baseline", required=True, help="`sha256sum` output, made inside the baseline run folder")
    s.add_argument("--run", dest="run_dir", required=True, help="the new run folder")
    s.set_defaults(run=same)
    return p


def main(argv=None):
    a = parser().parse_args(argv)
    try:
        status, message = a.run(a)
    except Gap as gap:
        status, message = "unsupported", str(gap)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w") as handle:
            json.dump({"status": status, "message": message}, handle)
    print("{}: {}".format(status, message))
    return 2 if status == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
