"""Compare two delimited tables by a key and report how they differ. Read-only, stdlib only.

Run: sh <skill-dir>/../../hooks/py.sh - OLD NEW --key donor,gene [--rtol 1e-6] [--atol 1e-8] [--max-rows 10] [--redact-keys] < <skill-dir>/scripts/diff_tables.py

Reads .csv, .tsv and either one gzipped (.gz). Any other name is sniffed from its first line.
Exit 0: identical. Exit 1: different. Exit 2: unusable input (missing file or key, empty key,
duplicate keys, duplicate column names, a row with more cells than the header).

How cells compare:
- Numbers (strict: 1, -2.5, 1e-3, inf, nan) compare with a symmetric tolerance. Integers compare exactly.
- An infinite value differs from any other value, and inf equals inf only with the same sign.
- NA, N/A and nan (any case) are the same missing value. An empty cell is its own value.
- Everything else is text and compares exactly, whitespace included. "007" is text, so "007" differs from "7".
- Columns are matched by name. A different order of shared columns is reported.
- Blank lines are skipped. Both tables are held in memory.

Key values can identify people. --redact-keys hides key values, text cell values and column
names: rows show as "row N (OLD)" or "row N (NEW)" and columns as "column N (OLD)" (position in the file).
"""

import argparse
import csv
import gzip
import itertools
import math
import re
import sys

NA_WORDS = {"na", "n/a", "nan"}
INT_RE = re.compile(r"[+-]?(?:0|[1-9][0-9]*)")
NUM_RE = re.compile(r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
INF_RE = re.compile(r"[+-]?inf(?:inity)?", re.IGNORECASE)


def read_table(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", newline="", encoding="utf-8-sig") as handle:
        first = handle.readline()
        if not first.strip():
            raise ValueError(f"{path}: empty file")
        name = path[:-3] if path.endswith(".gz") else path
        if name.endswith(".tsv"):
            delimiter = "\t"
        elif name.endswith(".csv"):
            delimiter = ","
        else:
            delimiter = "\t" if first.count("\t") >= first.count(",") and "\t" in first else ","
        reader = csv.reader(itertools.chain([first], handle), delimiter=delimiter)
        header = next(reader)
        rows = [(number, row) for number, row in enumerate(reader, start=1) if row]
    return header, rows


def parse(value):
    """Return (kind, payload). kind is empty, na, int, num or text."""
    if value == "":
        return "empty", None
    stripped = value.strip()
    if stripped.lower() in NA_WORDS:
        return "na", None
    if INT_RE.fullmatch(stripped):
        return "int", int(stripped)
    if NUM_RE.fullmatch(stripped):
        try:
            return "num", float(stripped)
        except OverflowError:
            return "num", math.inf
    if INF_RE.fullmatch(stripped):
        return "num", -math.inf if stripped.startswith("-") else math.inf
    return "text", value


def column_kind(values):
    kinds = set()
    for value in values:
        kind = parse(value)[0]
        if kind in ("empty", "na"):
            continue
        kinds.add("number" if kind == "num" else "integer" if kind == "int" else "text")
    if not kinds:
        return "empty"
    if len(kinds) == 1:
        return kinds.pop()
    return "number" if kinds == {"integer", "number"} else "mixed"


def index_rows(header, rows, key, label, path):
    duplicated = sorted({name for name in header if header.count(name) > 1})
    if duplicated:
        raise ValueError(f"{path}: duplicate column name(s) in {label}: {', '.join(duplicated)}")
    missing = [name for name in key if name not in header]
    if missing:
        raise ValueError(f"{path}: key column not found: {', '.join(missing)}")
    positions = [header.index(name) for name in key]
    indexed = {}
    duplicates = 0
    for number, row in rows:
        if len(row) > len(header):
            raise ValueError(
                f"{path}: data row {number} has {len(row)} cells but the header has {len(header)}"
            )
        row = row + [""] * (len(header) - len(row))
        keyed = tuple(row[position] for position in positions)
        if keyed in indexed:
            duplicates += 1
        indexed[keyed] = (number, row)
    if duplicates:
        raise ValueError(
            f"{path}: {duplicates} duplicate key value(s) in {label}; a key must name one row "
            "(add a column to --key, or fix the many-to-many source)"
        )
    return indexed


def values_differ(old, new, rtol, atol):
    old_kind, old_value = parse(old)
    new_kind, new_value = parse(new)
    if old_kind in ("int", "num") and new_kind in ("int", "num"):
        if old_kind == new_kind == "int":
            return old_value != new_value
        try:
            a, b = float(old_value), float(new_value)
        except OverflowError:
            return old_value != new_value
        if a == b:
            return False
        if math.isinf(a) or math.isinf(b):
            return True
        return abs(a - b) > atol + rtol * max(abs(a), abs(b))
    if old_kind != new_kind:
        return True
    if old_kind == "text":
        return old != new
    return False


def compare(old_path, new_path, key, rtol, atol, max_rows, redact):
    old_header, old_rows = read_table(old_path)
    new_header, new_rows = read_table(new_path)
    old = index_rows(old_header, old_rows, key, "OLD", old_path)
    new = index_rows(new_header, new_rows, key, "NEW", new_path)
    lines = []
    different = False

    def show(keyed, number, side):
        if redact:
            return f"row {number} ({side})"
        return ",".join(f"{k}={v}" for k, v in zip(key, keyed))

    def col(name, header, side):
        return f"column {header.index(name) + 1} ({side})" if redact else name

    def cell(value):
        kind = parse(value)[0]
        if redact and kind == "text":
            return "<text>"
        return "<empty>" if kind == "empty" else value

    only_old = [k for k in old if k not in new]
    only_new = [k for k in new if k not in old]
    if only_old or only_new:
        different = True
        lines.append(f"rows only in OLD: {len(only_old)}; only in NEW: {len(only_new)}")
        for keyed in only_old[:max_rows]:
            lines.append(f"  only in OLD: {show(keyed, old[keyed][0], 'OLD')}")
        for keyed in only_new[:max_rows]:
            lines.append(f"  only in NEW: {show(keyed, new[keyed][0], 'NEW')}")

    cols_old = [c for c in old_header if c not in key]
    cols_new = [c for c in new_header if c not in key]
    gone = [col(c, old_header, "OLD") for c in cols_old if c not in cols_new]
    added = [col(c, new_header, "NEW") for c in cols_new if c not in cols_old]
    if gone or added:
        different = True
        lines.append(f"columns only in OLD: {gone or 'none'}; only in NEW: {added or 'none'}")

    shared = [c for c in cols_old if c in cols_new]
    if shared != [c for c in cols_new if c in cols_old]:
        different = True
        lines.append("column order differs between OLD and NEW (columns are matched by name)")
    both = [k for k in old if k in new]
    changed_kinds = []
    for name in shared:
        old_index, new_index = old_header.index(name), new_header.index(name)
        kind_old = column_kind([old[k][1][old_index] for k in old])
        kind_new = column_kind([new[k][1][new_index] for k in new])
        if kind_old != kind_new:
            changed_kinds.append(f"{col(name, old_header, 'OLD')}: {kind_old} -> {kind_new}")
    if changed_kinds:
        different = True
        lines.append("type-like changes: " + "; ".join(changed_kinds))

    offenders = []
    per_column = {}
    for keyed in both:
        for name in shared:
            before = old[keyed][1][old_header.index(name)]
            after = new[keyed][1][new_header.index(name)]
            if values_differ(before, after, rtol, atol):
                per_column[name] = per_column.get(name, 0) + 1
                offenders.append((keyed, name, before, after))
    if offenders:
        different = True
        cells = ", ".join(f"{col(n, old_header, 'OLD')} ({c})" for n, c in per_column.items())
        lines.append(f"{len(offenders)} cell(s) differ beyond rtol={rtol:g}, atol={atol:g} in: {cells}")
        for keyed, name, before, after in offenders[:max_rows]:
            where = show(keyed, old[keyed][0], "OLD")
            lines.append(f"  {where} {col(name, old_header, 'OLD')}: {cell(before)} -> {cell(after)}")

    summary = (
        f"{'DIFFERENT' if different else 'IDENTICAL'}: OLD {len(old)} rows, NEW {len(new)} rows, "
        f"{len(only_old)} removed, {len(only_new)} added, {len(offenders)} cells changed"
    )
    return different, lines + [summary]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare two tables by key columns (read-only).")
    parser.add_argument("old")
    parser.add_argument("new")
    parser.add_argument("--key", required=True, help="comma-separated key column(s)")
    parser.add_argument("--rtol", type=float, default=1e-6)
    parser.add_argument("--atol", type=float, default=1e-8)
    parser.add_argument("--max-rows", type=int, default=10, help="offending rows to list per kind")
    parser.add_argument(
        "--redact-keys",
        action="store_true",
        help="hide key values, text cell values and column names (rows and columns by position)",
    )
    args = parser.parse_args(argv)
    key = [name.strip() for name in args.key.split(",") if name.strip()]
    if not key:
        print("UNUSABLE: --key names no column")
        return 2
    try:
        different, lines = compare(
            args.old, args.new, key, args.rtol, args.atol, args.max_rows, args.redact_keys
        )
    except (OSError, ValueError, csv.Error, UnicodeDecodeError, EOFError) as error:
        print(f"UNUSABLE: {error}")
        return 2
    print("\n".join(lines))
    return 1 if different else 0


if __name__ == "__main__":
    sys.exit(main())
