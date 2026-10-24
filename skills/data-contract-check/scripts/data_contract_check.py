"""Check a plan's data assumptions against a sample-level table, read-only.

Stdlib-only; runs on Python 3.9+. Run it from stdin so Mycelium's hooks do
not open the post-action cycle:

    sh <plugin>/hooks/py.sh - --contract /tmp/contract.json < data_contract_check.py

The contract states what the plan assumes; this script decides what blocks.
Every failed check of a coverage-list kind blocks, and the contract cannot
downgrade it. A table is CSV, TSV (.tsv, .tab, .txt), or the `obs` of an `.h5ad` file; h5ad
is read through h5py when it is importable, and is a gap (never a pass) when
it is not. Any other format, or bytes that are not UTF-8, is a gap; a row with
more fields than the header, or a quote that never closes, blocks. Exit codes: 0 clean or warnings only, 2 blocking, 3 a gap and nothing
blocking, 1 usage or input error. `--result-json PATH` also writes a machine-readable result
(contract and table identities, each check's status and message, the exit code, and whether each
check could run at all) so a later step can read what happened without parsing text.

`--profile-only --profile-spec SPEC` instead prints a descriptive profile of one table (rows read, group counts,\nmissing values) and checks nothing; see the skill's section 5. Exit 0 complete or partial, 3 unavailable, 1 usage error.
"""

import argparse
import csv
import io
import json
import hashlib
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict

SCHEMA = "mycelium-extra.data_contract.v1"
ALERT_SCHEMA = "mycelium-extra.contract_alert.v1"
RESULT_SCHEMA = "mycelium-extra.contract_result.v1"
MISSING = {"", "na", "nan", "null", "none", "<na>"}
MAX_EVIDENCE = 5


class ContractError(Exception):
    pass


class TableGap(Exception):
    """The table, or a column of it, cannot be read here; the checks on it are gaps."""


class ReaderMissing(TableGap):
    """An optional reader (h5py) is not installed; kept apart from a table that is unreadable."""


class ReferenceMissing(Exception):
    """A reference file the contract declares does not exist; blocks, like a missing table."""


def is_missing(value):
    return value is None or value.strip().lower() in MISSING


def alert(kind, message, blocking, expected=None, observed=None, evidence=None, gap=False, cause=None):
    record = {
        "schema": ALERT_SCHEMA,
        "severity": "error" if blocking else ("gap" if gap else "warning"),
        "kind": kind,
        "message": message,
        "blocking": blocking,
    }
    if cause:
        record["cause"] = cause  # why the check could not run at all; absent when it ran
    if expected is not None:
        record["expected"] = expected
    if observed is not None:
        record["observed"] = observed
    if evidence:
        record["evidence"] = [str(item) for item in evidence[:MAX_EVIDENCE]]
        if len(evidence) > MAX_EVIDENCE:
            record["evidence"].append("... {} more".format(len(evidence) - MAX_EVIDENCE))
    return record


TAB_SEPARATED = (".tsv", ".tab", ".txt")


class TableShapeError(Exception):
    """The table parses but its shape makes every check on it untrustworthy; blocks."""


def read_table(path, wanted=None):
    """Return (columns, rows, unreadable): rows are dicts of strings, unreadable maps column to reason.

    The CSV/TSV reader follows Mycelium's skills/core/scripts/data_contract_check.py
    (pinned 8f8b167; MIT, Copyright (c) 2024 Mycelium Contributors), which was
    itself adapted from this file; it is copied here, never imported.
    """
    lower = path.lower()
    if lower.endswith(".h5ad"):
        return read_h5ad_obs(path, wanted)
    if lower.endswith(".csv"):
        delimiter = ","
    elif lower.endswith(TAB_SEPARATED):
        delimiter = "\t"
    else:
        raise TableGap("unsupported table format '{}'; export it to CSV or TSV".format(
            os.path.splitext(path)[1] or path))
    # Decode strictly: replacing bad bytes would merge distinct identifiers
    # (p\xff and p\xfe both become p\ufffd) and could fake a passing check.
    # Parse strictly too: lenient csv reads everything after an unclosed quote
    # into one field, so later rows silently vanish.
    try:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.reader(handle, delimiter=delimiter, strict=True)
            try:
                records, starts, last = [], [], 0
                for record in reader:
                    records.append(record)
                    starts.append(last + 1)  # physical line where this record begins
                    last = reader.line_num
            except csv.Error as error:
                raise TableShapeError("line {} cannot be parsed ({}), so later rows may be missing or "
                                      "merged".format(reader.line_num, error))
    except UnicodeDecodeError as error:
        raise TableGap("the table is not valid UTF-8 (byte {} at offset {}); re-export it as UTF-8".format(
            error.object[error.start:error.start + 1], error.start))
    if not records:
        return [], [], {}
    columns = records[0]
    # Blank header fields (trailing delimiters) cannot be named by a contract.
    named = [c for c in columns if c.strip()]
    if len(set(named)) != len(named):
        raise TableGap("the table has duplicate column headers")
    rows = []
    for line_no, record in zip(starts[1:], records[1:]):
        if not record:
            continue  # a blank line, as csv.DictReader skips it
        # Any extra field is malformed, even an empty one: the extra field may be
        # a leading row name, which shifts every value one column to the right.
        extra = record[len(columns):]
        if extra:
            hint = "; an R write.table export with row names does this, so re-export with " \
                "row.names = FALSE" if len(extra) == 1 else ""
            raise TableShapeError("line {} has more fields than the header ({} > {}), so its values "
                                  "cannot be assigned to columns{}".format(
                                      line_no, len(record), len(columns), hint))
        if not any(field.strip() for field in record):
            continue  # a ',,,' line (Excel padding) is no sample, so it must not count toward rows
        # A short row's absent trailing fields are missing values, never None.
        record = record + [""] * (len(columns) - len(record))
        rows.append(dict(zip(columns, record)))
    return columns, rows, {}


# ---------------------------------------------------------------- h5ad obs

def decode(value):
    """UTF-8 bytes from an .h5ad, strictly; undecodable bytes make the column unreadable."""
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TableGap("a value is not valid UTF-8 ({!r})".format(value[:error.end]))


def text(value):
    """One obs value as the string a CSV export would hold; missing values become ""."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return decode(value)
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, float) and value != value:
        return ""
    return str(value)


def attr(node, key, default=None):
    value = node.attrs.get(key, default)
    if isinstance(value, bytes):
        return decode(value)
    if hasattr(value, "tolist") and not isinstance(value, str):
        value = value.tolist()
    if isinstance(value, list):
        return [text(v) for v in value]
    return value


def obs_values(h5file, node, h5py):
    """A 1-D obs column as a list of strings, in AnnData's on-disk encodings.

    anndata >= 0.8 (dataframe 0.2.0): arrays and string arrays are datasets;
    categoricals are groups with `codes` and `categories`; nullable integer,
    boolean, and string arrays are groups with `values` and `mask`.
    anndata 0.7 (dataframe 0.1.0): a categorical is a dataset of codes whose
    `categories` attribute references `obs/__categories/<column>`.
    Anything else raises TableGap.
    """
    encoding = attr(node, "encoding-type", "")
    if isinstance(node, h5py.Group):
        if encoding == "categorical" and "codes" in node and "categories" in node:
            return decode_codes(node["codes"][()].tolist(), obs_values(h5file, node["categories"], h5py))
        if encoding in ("nullable-integer", "nullable-boolean", "nullable-string-array") \
                and "values" in node and "mask" in node:
            values = obs_values(h5file, node["values"], h5py)
            mask = node["mask"][()].tolist()
            if len(mask) != len(values):
                raise TableGap("its mask and values differ in length")
            return ["" if hidden else v for v, hidden in zip(values, mask)]
        raise TableGap("unrecognised encoding '{}'".format(encoding or "none"))
    if node.dtype.names or len(node.shape) != 1:
        raise TableGap("not a 1-D column (shape {}, encoding '{}')".format(node.shape, encoding or "none"))
    if "categories" in node.attrs and isinstance(node.attrs["categories"], h5py.Reference):
        categories = h5file[node.attrs["categories"]][()].tolist()
        return decode_codes(node[()].tolist(), [text(c) for c in categories])
    return [text(v) for v in node[()].tolist()]


def decode_codes(codes, categories):
    if (not isinstance(codes, list) or not isinstance(categories, list) or
            any(type(c) is not int or c < -1 or c >= len(categories) for c in codes)):
        raise TableGap("categorical codes must be integers naming a category, or -1 for missing")
    return ["" if c < 0 else categories[c] for c in codes]


def read_h5ad_obs(path, wanted=None):
    """Read obs from an .h5ad file through h5py; never reads X or layers."""
    try:
        import h5py
    except ImportError as error:
        raise ReaderMissing("h5py cannot be imported ({}), so the obs of an .h5ad file cannot be read; install "
                            "h5py or export obs to a TSV".format(error))
    try:
        h5file = h5py.File(path, "r")
    except (OSError, IOError) as error:
        raise TableGap("not readable as HDF5: {}".format(error))
    with h5file:
        obs = h5file.get("obs")
        if not isinstance(obs, h5py.Group) or attr(obs, "encoding-type") != "dataframe" \
                or not isinstance(attr(obs, "_index"), str) or attr(obs, "_index") not in obs:
            raise TableGap("obs is not in a recognised AnnData encoding (anndata 0.7 or later expected: "
                           "a dataframe group with an _index attribute)")
        index = attr(obs, "_index")
        order = attr(obs, "column-order", [])
        if not isinstance(order, list):
            order = [text(order)] if order else []
        columns = [index] + [c for c in order if c != index]
        missing = [c for c in columns if c not in obs]
        if missing:
            raise TableGap("obs lists columns it does not hold: " + ", ".join(missing))
        values, unreadable = {}, {}
        for column in columns:
            if wanted is not None and column not in wanted and column != index:
                continue  # read only what the contract names, plus the index for the row count
            try:
                values[column] = obs_values(h5file, obs[column], h5py)
            except TableGap as error:
                if column == index:
                    raise TableGap("its index '{}' is unreadable: {}".format(index, error))
                unreadable[column] = str(error)
        if len({len(v) for v in values.values()}) > 1:
            raise TableGap("obs columns differ in length")
    names = list(values)
    rows = [dict(zip(names, cells)) for cells in zip(*[values[c] for c in names])]
    return columns, rows, unreadable


def apply_filters(rows, filters, columns):
    for rule in filters:
        column = rule.get("column")
        if "equals" in rule:
            allowed = {str(rule["equals"])}
            rows = [r for r in rows if r[column] in allowed]
        elif "in" in rule:
            allowed = {str(v) for v in rule["in"]}
            rows = [r for r in rows if r[column] in allowed]
        elif "not_in" in rule:
            banned = {str(v) for v in rule["not_in"]}
            rows = [r for r in rows if r[column] not in banned]
        else:
            raise ContractError("filter needs equals, in, or not_in: {}".format(rule))
    return rows


def need(check, key):
    if key not in check:
        raise ContractError("{} check needs '{}'".format(check.get("kind"), key))
    return check[key]


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def drop_missing(rows, keys, kind):
    """Split rows into complete and a warning for rows missing any key column."""
    kept = [r for r in rows if not any(is_missing(r[k]) for k in keys)]
    dropped = len(rows) - len(kept)
    warnings = []
    if dropped:
        warnings.append(alert(
            kind, "{} rows have a missing value in {} and were left out of this check".format(
                dropped, ", ".join(keys)),
            blocking=not kept, observed="{} of {} rows".format(dropped, len(rows))))
    return kept, warnings


def check_schema(check, columns, rows, ctx=None):
    missing = [c for c in need(check, "columns") if c not in columns]
    if not missing:
        return []
    return [alert("schema", "required columns are absent", True,
                  expected=", ".join(check["columns"]), observed="missing: " + ", ".join(missing))]


def check_cohort(check, columns, rows, ctx=None):
    alerts = []
    column = check.get("column")
    if column is not None:
        present = Counter(r[column] for r in rows)
        absent = [lvl for lvl in as_list(check.get("levels")) if str(lvl) not in present]
        if absent:
            alerts.append(alert(
                "cohort", "required levels of '{}' are absent after filtering".format(column), True,
                expected=", ".join(str(l) for l in as_list(check["levels"])),
                observed="absent: " + ", ".join(str(l) for l in absent),
                evidence=["{}={}".format(k, v) for k, v in sorted(present.items())]))
    if "min_rows" in check and len(rows) < int(check["min_rows"]):
        alerts.append(alert("cohort", "fewer rows than the plan assumes", True,
                            expected=">= {}".format(check["min_rows"]), observed=str(len(rows))))
    if "rows" in check and len(rows) != int(check["rows"]):
        alerts.append(alert("cohort", "row count differs from the plan", True,
                            expected=str(check["rows"]), observed=str(len(rows))))
    for col in as_list(check.get("no_missing")):
        n = sum(1 for r in rows if is_missing(r[col]))
        if n:
            alerts.append(alert("cohort", "'{}' has missing values".format(col), True,
                                expected="0 missing", observed="{} of {} rows".format(n, len(rows))))
    return alerts


def check_unit(check, columns, rows, ctx=None):
    unit = need(check, "unit")
    group = need(check, "group")
    within = as_list(check.get("within"))
    rows, alerts = drop_missing(rows, [unit, group] + within, "unit_of_replication")
    if not rows:
        return alerts
    cells = Counter((r[group],) + tuple(r[w] for w in within) + (r[unit],) for r in rows)
    repeats = sorted(key for key, n in cells.items() if n > 1)
    if repeats:
        labels = [group] + within + [unit]
        alerts.append(alert(
            "unit_of_replication",
            "a unit appears more than once in the same {} cell; rows are not independent units".format(
                " x ".join([group] + within)),
            True, expected="1 row per {} per cell".format(unit),
            observed="{} repeated cells".format(len(repeats)),
            evidence=[", ".join("{}={}".format(l, v) for l, v in zip(labels, key)) +
                      " ({} rows)".format(cells[key]) for key in repeats]))
    units = defaultdict(set)
    for r in rows:
        units[r[group]].add(r[unit])
    minimum = int(check.get("min_units_per_group", 2))
    small = sorted((g, len(u)) for g, u in units.items() if len(u) < minimum)
    if small:
        alerts.append(alert(
            "unit_of_replication", "groups with fewer distinct {} than required".format(unit), True,
            expected=">= {} per {}".format(minimum, group),
            observed=", ".join("{}={}".format(g, n) for g, n in small)))
    shared = sorted(u for u in set.union(*units.values()) if sum(u in s for s in units.values()) > 1) \
        if len(units) > 1 else []
    if shared and not check.get("units_may_span_groups", False):
        alerts.append(alert(
            "unit_of_replication", "some {} appear in more than one {} level".format(unit, group), True,
            expected="each {} in one {}".format(unit, group),
            observed="{} shared units".format(len(shared)), evidence=shared))
    return alerts


def check_pairing(check, columns, rows, ctx=None):
    unit = need(check, "unit")
    within = need(check, "within")
    rows, alerts = drop_missing(rows, [unit, within], "pairing")
    if not rows:
        return alerts
    levels = [str(l) for l in as_list(check.get("levels"))] or sorted({r[within] for r in rows})
    seen = defaultdict(set)
    for r in rows:
        seen[r[unit]].add(r[within])
    incomplete = sorted((u, sorted(set(levels) - s)) for u, s in seen.items() if set(levels) - s)
    if incomplete:
        alerts.append(alert(
            "pairing", "units are missing a level of '{}'".format(within), True,
            expected="every {} at {}".format(unit, ", ".join(levels)),
            observed="{} of {} units incomplete".format(len(incomplete), len(seen)),
            evidence=["{} lacks {}".format(u, ", ".join(m)) for u, m in incomplete]))
    return alerts


def check_batch(check, columns, rows, ctx=None):
    batch = need(check, "batch")
    contrast = need(check, "contrast")
    rows, alerts = drop_missing(rows, [batch, contrast], "batch_confounding")
    if not rows:
        return alerts
    table = defaultdict(Counter)
    for r in rows:
        table[r[batch]][r[contrast]] += 1
    levels = sorted({r[contrast] for r in rows})
    evidence = ["{}: {}".format(b, ", ".join("{}={}".format(l, c[l]) for l in levels if c[l]))
                for b, c in sorted(table.items())]
    if len(levels) < 2:
        return alerts + [alert("batch_confounding", "the contrast has fewer than two levels", True,
                               observed=", ".join(levels) or "none")]
    single = sorted(b for b, c in table.items() if len(c) == 1)
    if len(single) == len(table):
        alerts.append(alert(
            "batch_confounding", "'{}' is fully nested in '{}': no batch holds two contrast levels".format(
                contrast, batch), True,
            expected="batches shared across {} levels".format(contrast),
            observed="{} of {} batches single-level".format(len(single), len(table)), evidence=evidence))
        return alerts
    if single:
        alerts.append(alert(
            "batch_confounding", "some batches hold only one '{}' level".format(contrast), False,
            observed="{} of {} batches single-level".format(len(single), len(table)),
            evidence=["{}: {}".format(b, next(iter(table[b]))) for b in single]))
    isolated = sorted(l for l in levels
                      if all(len(c) == 1 for c in table.values() if c[l]))
    if isolated:
        alerts.append(alert(
            "batch_confounding",
            "contrast levels that share no batch with another level; any contrast with them is confounded with batch",
            True, expected="every level shares a batch with another level",
            observed=", ".join(isolated),
            evidence=["{}: {}".format(l, ", ".join(sorted(b for b, c in table.items() if c[l])))
                      for l in isolated]))
    lone = sorted(l for l in levels if l not in isolated
                  and sum(1 for c in table.values() if c[l]) == 1)
    if lone:
        alerts.append(alert(
            "batch_confounding", "contrast levels measured in a single batch", False,
            observed=", ".join(lone)))
    share = check.get("max_share")
    if share is not None:
        totals = Counter(r[contrast] for r in rows)
        over = [(b, l) for b, c in sorted(table.items()) for l in levels
                if c[l] and c[l] / float(totals[l]) > share]
        if over:
            alerts.append(alert(
                "batch_confounding",
                "a batch holds more than {} of a '{}' level".format(percent(share), contrast), False,
                expected="each batch at most {} of each {} level".format(percent(share), contrast),
                observed="{} batch-level pairs over".format(len(over)),
                evidence=["{} holds {} of {} {} rows ({})".format(
                    b, table[b][l], totals[l], l, percent(table[b][l] / float(totals[l]))) for b, l in over]))
    return alerts


def percent(share):
    return "{:.0f}%".format(100 * share)


def cross_table(check, rows):
    """The batch-by-contrast row counts the check ran on, shown on every run."""
    batch, contrast = check["batch"], check["contrast"]
    rows = [r for r in rows if not is_missing(r[batch]) and not is_missing(r[contrast])]
    counts = defaultdict(Counter)
    for r in rows:
        counts[r[batch]][r[contrast]] += 1
    return {"batch": batch, "contrast": contrast, "levels": sorted({r[contrast] for r in rows}),
            "counts": dict((b, dict(c)) for b, c in sorted(counts.items()))}


def render_cross_table(table):
    """Counts with each cell's share of its contrast level, as plain aligned text."""
    levels = table["levels"]
    totals = Counter()
    for counts in table["counts"].values():
        totals.update(counts)
    header = ["{} \\ {}".format(table["batch"], table["contrast"])] + levels + ["total"]
    body = []
    for b, counts in sorted(table["counts"].items()):
        cells = ["{} ({})".format(counts.get(l, 0), percent(counts.get(l, 0) / float(totals[l])))
                 for l in levels]
        body.append([b] + cells + [str(sum(counts.values()))])
    body.append(["total"] + [str(totals[l]) for l in levels] + [str(sum(totals.values()))])
    widths = [max(len(row[i]) for row in [header] + body) for i in range(len(header))]
    return ["  ".join(cell.ljust(w) for cell, w in zip(row, widths)).rstrip() for row in [header] + body]


# ------------------------------------------------- unique_key and the declared checks

def resolve(base_dir, path):
    return path if os.path.isabs(path) else os.path.join(base_dir, path)


def failed(kind, message, observed=None, evidence=None, expected=None):
    return alert(kind, message, True, expected=expected, observed=observed, evidence=evidence)


def read_lines(path):
    """One identifier per line, strict UTF-8; blank lines and lines starting with # are skipped."""
    try:
        with open(path, encoding="utf-8-sig") as handle:
            return [line.strip() for line in handle if line.strip() and not line.lstrip().startswith("#")]
    except UnicodeDecodeError as error:
        raise TableGap("the list is not valid UTF-8 (offset {}); re-export it as UTF-8".format(error.start))


def load_keys(spec, base_dir, extra=()):
    """Keys, and rows when a column names them, from an independent file the contract declares.

    spec: {"path"} and one of "column" (optional "filters"), "header" (optional "exclude"), "lines".
    Returns (keys in file order, rows). Raises ReferenceMissing, TableGap or TableShapeError.
    """
    path = resolve(base_dir, spec["path"])
    if not os.path.isfile(path):
        raise ReferenceMissing("not found: " + spec["path"])
    if spec.get("lines"):
        return read_lines(path), []
    named = [spec["column"]] + list(extra) + [f["column"] for f in spec.get("filters", [])] \
        if "column" in spec else []
    columns, rows, unreadable = read_table(path, set(named) if named else None)
    if spec.get("header"):
        return [c for c in columns if c not in as_list(spec.get("exclude"))], []
    absent = sorted(set(c for c in named if c not in columns))
    if absent:
        raise TableShapeError("the file lacks column(s) " + ", ".join(absent))
    bad = sorted(set(c for c in named if c in unreadable))
    if bad:
        raise TableGap("column(s) cannot be read: " + ", ".join(bad))
    rows = apply_filters(rows, spec.get("filters", []), columns)
    return [r[spec["column"]] for r in rows], rows


def gap_cause(error, default="table_unreadable"):
    return "optional_reader_missing" if isinstance(error, ReaderMissing) else default


def reference_failure(kind, error, what):
    """A declared file that cannot be used is never a pass: unreadable is a gap, missing or malformed blocks."""
    if isinstance(error, TableGap):
        return alert(kind, "the {} cannot be read, so this check did not run".format(what), False,
                     observed=str(error), gap=True, cause=gap_cause(error, "reference_unreadable"))
    return alert(kind, "the {} the contract declares cannot be used".format(what), True, observed=str(error),
                 cause="reference_unusable")


def repeated(values):
    return sorted(v for v, n in Counter(values).items() if n > 1)


def quoted(values):
    return ["'{}'".format(v) if v else "'' (empty)" for v in values]


def check_sample_alignment(check, columns, rows, ctx=None):
    kind, spec = "sample_alignment", check["reference"]
    extra = as_list(check.get("agree_on"))
    try:
        ref_keys, ref_rows = load_keys(spec, ctx["base_dir"], extra)
    except (ReferenceMissing, TableGap, TableShapeError) as error:
        return [reference_failure(kind, error, "independent key list")]
    if check.get("header_keys"):
        keys = [c for c in columns if c not in as_list(check.get("exclude"))]
    else:
        keys = [r[check["key"]] for r in rows]
    alerts = []
    for side, values in (("the table", keys), ("the independent list", ref_keys)):
        empty = sum(1 for v in values if is_missing(v))
        if empty:
            alerts.append(failed(kind, "{} has empty or missing keys".format(side),
                                 "{} of {}".format(empty, len(values))))
        again = repeated([v for v in values if not is_missing(v)])
        if again:
            alerts.append(failed(kind, "{} repeats keys".format(side), "{} repeated keys".format(len(again)),
                                 evidence=quoted(again)))
    have, want = set(keys), set(ref_keys)
    if len(have) != len(want):
        alerts.append(failed(kind, "the table and the independent list hold different numbers of keys",
                             "table {}, list {}".format(len(have), len(want)), expected="the same distinct keys"))
    for message, only in (("keys in the table but not in the independent list", sorted(have - want)),
                          ("keys in the independent list but not in the table", sorted(want - have))):
        if only:
            alerts.append(failed(kind, message, "{} keys".format(len(only)), evidence=quoted(only)))
    if extra:
        theirs = {}
        for r in ref_rows:
            theirs.setdefault(r[spec["column"]], r)
        wrong = ["{}: {} is {} in the table but {} in the list".format(r[check["key"]], col, r[col],
                                                                       theirs[r[check["key"]]][col])
                 for r in rows if r[check["key"]] in theirs for col in extra
                 if r[col] != theirs[r[check["key"]]][col]]
        if wrong:
            alerts.append(failed(kind, "values differ between the table and the independent list",
                                 "{} differing values".format(len(wrong)), evidence=wrong))
    return alerts


MONTH = "(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
DATE_LIKE = re.compile(
    r"^(?:\d{{1,2}}-{m}(?:-\d{{2,4}})?|{m}-\d{{1,2}}(?:-\d{{2,4}})?|\d{{4}}-\d{{1,2}}-\d{{1,2}}"
    r"|\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}})$".format(m=MONTH), re.IGNORECASE)


def check_identifiers(check, columns, rows, ctx=None):
    kind, column = "identifiers", check["column"]
    ids = [r[column] for r in rows]
    alerts = []
    empty = sum(1 for v in ids if is_missing(v))
    if empty:
        alerts.append(failed(kind, "'{}' has empty or missing identifiers".format(column),
                             "{} of {} rows".format(empty, len(ids))))
    again = repeated([v for v in ids if not is_missing(v)])
    if again:
        alerts.append(failed(kind, "'{}' repeats identifiers".format(column),
                             "{} repeated identifiers".format(len(again)), evidence=quoted(again)))
    if "namespace" in check:
        try:
            names, _ = load_keys(check["namespace"], ctx["base_dir"])
        except (ReferenceMissing, TableGap, TableShapeError) as error:
            return alerts + [reference_failure(kind, error, "identifier namespace")]
        known = set(n for n in names if not is_missing(n))
        if not known:
            return alerts + [alert(kind, "the declared namespace holds no identifiers, so it cannot be an "
                                         "authority", False, gap=True, cause="reference_unusable")]
        outside = sorted(set(v for v in ids if not is_missing(v) and v not in known))
        if outside:
            alerts.append(failed(
                kind, "identifiers that are not in the declared namespace", "{} identifiers".format(len(outside)),
                evidence=quoted(outside),
                expected="every identifier in the namespace (exact match; nothing is repaired or renamed)"))
        return alerts
    # No authority: whatever the strings look like, they cannot be certified.
    datelike = sorted(set(v for v in ids if DATE_LIKE.match(v.strip())))
    if datelike:
        alerts.append(alert(
            kind, "date-like identifiers: a spreadsheet may have rewritten symbols as dates, but legitimate or "
                  "corrupted cannot be told without a declared namespace", False,
            observed="{} date-like identifiers".format(len(datelike)), evidence=quoted(datelike)))
    alerts.append(alert(kind, "no identifier namespace is declared, so identifier validity is unverified; only "
                              "empties and repeats were checked", False, gap=True))
    return alerts


def check_unique_key(check, columns, rows, ctx=None):
    kind, names = "unique_key", as_list(check["columns"])
    alerts = []
    for col in names:
        empty = [i + 1 for i, r in enumerate(rows) if is_missing(r[col])]
        if empty:
            alerts.append(failed(kind, "'{}' has empty or missing values, so it cannot be a key".format(col),
                                 "{} of {} rows".format(len(empty), len(rows)),
                                 evidence=["row {} after filters".format(i) for i in empty]))
    if alerts:
        return alerts
    counts = Counter(tuple(r[c] for c in names) for r in rows)
    again = sorted((k, n) for k, n in counts.items() if n > 1)
    if again:
        alerts.append(failed(kind, "the key ({}) is not unique".format(", ".join(names)),
                             "{} repeated keys".format(len(again)), expected="1 row per key",
                             evidence=["{} ({} rows)".format(", ".join(k), n) for k, n in again]))
    return alerts


def sample_facts(array, properties):
    """Facts about a bounded sample of numeric values (numpy is present whenever h5py is)."""
    import numpy as np
    facts = {"violations": {}, "nonfinite": 0, "sampled": int(array.size)}
    if array.dtype.kind not in "iufb":
        facts["not_numeric"] = str(array.dtype)
        return facts
    values = array.astype("float64").ravel()
    finite = np.isfinite(values)
    facts["nonfinite"] = int(values.size - finite.sum())
    values = values[finite]
    if values.size == 0:
        return facts
    facts["min"], facts["max"] = float(values.min()), float(values.max())
    tests = {"non_negative": values < 0, "integer_valued": values != np.floor(values)}
    if "max_at_most" in properties:
        tests["max_at_most"] = values > properties["max_at_most"]
    for name, bad in tests.items():
        if properties.get(name) and bad.any():
            facts["violations"][name] = int(bad.sum())
    return facts


def inspect_h5ad_path(path, h5_path, properties, cap):
    """Does `h5_path` (X, layers/<name>, obsm/<name>) exist, and what do up to `cap` of its values look like?

    Never loads the matrix whole: a dense array is read by leading rows, a CSR/CSC matrix by its first
    stored values (implicit zeros are not counted). Raises ReaderMissing or TableGap.
    """
    try:
        import h5py
        import numpy as np
    except ImportError as error:
        raise ReaderMissing("h5py cannot be imported ({}), so the layer cannot be inspected; install h5py in "
                            "the environment the check runs in".format(error))
    try:
        h5file = h5py.File(path, "r")
    except (OSError, IOError) as error:
        raise TableGap("not readable as HDF5: {}".format(error))
    with h5file:
        node = h5file.get(h5_path)
        if node is None:
            return {"exists": False}
        facts = {"exists": True}
        if not properties:
            return facts
        if isinstance(node, h5py.Dataset):
            shape = node.shape
            facts["total"] = int(np.prod(shape)) if shape else 1
            if node.dtype.kind not in "iufb":
                facts["not_numeric"] = str(node.dtype)
                return facts
            width = max(1, int(np.prod(shape[1:]))) if shape else 1
            sample = np.asarray(node[:max(1, cap // width)] if shape else node[()]).ravel()[:cap]
        elif isinstance(node, h5py.Group) and attr(node, "encoding-type") in ("csr_matrix", "csc_matrix") \
                and isinstance(node.get("data"), h5py.Dataset):
            facts["total"] = int(node["data"].shape[0])
            sample = np.asarray(node["data"][:cap])
        else:
            facts["unsupported"] = "not a dense array or a CSR/CSC matrix (encoding '{}')".format(
                attr(node, "encoding-type", "") or "none")
            return facts
        facts.update(sample_facts(sample, properties))
        return facts


def check_h5ad_layer(check, columns, rows, ctx=None):
    kind, h5_path, properties = "h5ad_layer", check["h5_path"], check.get("properties", {})
    try:
        facts = inspect_h5ad_path(ctx["path"], h5_path, properties, check.get("sample_values", 100000))
    except TableGap as error:
        return [alert(kind, "the layer cannot be inspected, so this check did not run", False,
                      observed=str(error), gap=True, cause=gap_cause(error))]
    if not facts["exists"]:
        return [failed(kind, "the required path is absent from the file", "no '{}'".format(h5_path),
                       expected="'{}' present".format(h5_path))]
    if not properties:
        return []
    if "unsupported" in facts or "not_numeric" in facts:
        return [alert(kind, "the declared properties cannot be judged for '{}'".format(h5_path), False, gap=True,
                      cause="values_not_judgeable",
                      observed=facts.get("unsupported") or "values are not numeric ({})".format(facts["not_numeric"]))]
    alerts = []
    for name, count in sorted(facts["violations"].items()):
        alerts.append(failed(
            kind, "'{}' violates a declared property: {}".format(h5_path, name),
            "{} of {} sampled values; observed min {}, max {}".format(count, facts["sampled"], facts["min"],
                                                                      facts["max"]),
            expected=name if properties[name] is True else "{} {}".format(name, properties[name])))
    if facts["sampled"] == 0:
        alerts.append(alert(kind, "'{}' has no values to inspect".format(h5_path), False, gap=True,
                            cause="values_not_judgeable"))
    elif facts["nonfinite"]:
        alerts.append(alert(kind, "'{}' holds NaN or infinite values, which these properties cannot judge".format(
            h5_path), False, gap=True, cause="values_not_judgeable",
            observed="{} of {} sampled values".format(facts["nonfinite"], facts["sampled"])))
    elif not alerts and facts["sampled"] < facts["total"]:
        alerts.append(alert(kind, "the declared properties held in the first {} of {} stored values only; the "
                                  "rest was not read".format(facts["sampled"], facts["total"]), False))
    return alerts


# A limit each declared check always prints, because passing it proves less than it sounds like.
NOTES = {
    "sample_alignment": "keys are compared as sets: order is not compared (it is no failure for keyed data), and "
                        "equal key sets do not show the analysis uses them correctly (a positional use of the "
                        "inputs needs a project shuffle-invariance test)",
    "identifiers": "strings are compared exactly with an independent namespace; without one the check is a gap, "
                   "and no identifier is repaired or renamed",
    "h5ad_layer": "checks the path and the declared properties of a bounded sample; this cannot tell which "
                  "normalization algorithm produced the values",
}


def validate(check, index):
    """Contract syntax the checks rely on; a bad value is a usage error, never a pass."""
    kind = check["kind"]
    required = {"schema": ["columns"], "unit_of_replication": ["unit", "group"],
                "pairing": ["unit", "within"], "batch_confounding": ["batch", "contrast"]}
    for key in required.get(kind, []):
        need(check, key)
    for key in ("column", "unit", "group", "batch", "contrast"):
        if key in check and (not isinstance(check[key], str) or not check[key]):
            raise ContractError("checks[{}] {} must be a nonempty column name".format(index, key))
    for key in ("columns", "within", "no_missing"):
        if key not in check:
            continue
        value = check[key]
        if key == "within" and kind == "pairing":
            valid = isinstance(value, str) and bool(value)
        else:
            valid = (isinstance(value, (list, str)) and (bool(value) or key != "columns")
                     and (key != "columns" or isinstance(value, list))
                     and all(isinstance(c, str) and bool(c) for c in as_list(value)))
        if not valid:
            raise ContractError("checks[{}] {} has invalid column names".format(index, key))
    if kind == "cohort" and "levels" in check and "column" not in check:
        raise ContractError("cohort levels need a column")
    if kind == "cohort" and not any(k in check for k in ("column", "rows", "min_rows")) \
            and not check.get("no_missing"):
        raise ContractError("cohort check needs a column, row count, or no_missing columns")
    if "levels" in check and any(not isinstance(v, (str, int, float, bool))
                                  for v in as_list(check["levels"])):
        raise ContractError("checks[{}] levels must contain scalar values".format(index))
    for key in ("rows", "min_rows", "min_units_per_group"):
        if key in check:
            value = check[key]
            minimum = 1 if key == "min_units_per_group" else 0
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise ContractError("checks[{}] {} must be an integer >= {}".format(index, key, minimum))
    if "units_may_span_groups" in check and not isinstance(check["units_may_span_groups"], bool):
        raise ContractError("units_may_span_groups must be a boolean")
    if "id" in check and (not isinstance(check["id"], str) or not check["id"]):
        raise ContractError("checks[{}] id must be a nonempty string".format(index))
    if kind in DECLARED:
        validate_declared(check, index)
    elif set(check) - CLASSIC[kind] - {"kind", "id", "label", "table", "filters"}:
        # a typo would drop the assumption and pass, so it is a usage error, as for the declared kinds
        raise ContractError("checks[{}] {} does not accept: {}".format(
            index, kind, ", ".join(sorted(set(check) - CLASSIC[kind] - {"kind", "id", "label", "table", "filters"}))))
    if check.get("kind") == "batch_confounding" and "max_share" in check:
        share = check["max_share"]
        if isinstance(share, bool) or not isinstance(share, (int, float)) or not 0 < share <= 1:
            raise ContractError("checks[{}] max_share must be a number above 0 and at most 1, as a "
                                "share (0.7 for 70%): {}".format(index, json.dumps(share)))


CLASSIC = {  # kind: the keys its check reads besides kind, id, label, table and filters
    "schema": {"columns"},
    "cohort": {"column", "levels", "min_rows", "rows", "no_missing"},
    "unit_of_replication": {"unit", "group", "within", "min_units_per_group", "units_may_span_groups"},
    "pairing": {"unit", "within", "levels"},
    "batch_confounding": {"batch", "contrast", "max_share"},
}
DECLARED = {  # kind: the keys it accepts besides kind, id, label, table and filters; nothing else is read,
    # so a contract cannot carry a severity or a waiver that softens one of these checks
    "unique_key": {"columns"},
    "sample_alignment": {"key", "header_keys", "exclude", "reference", "agree_on"},
    "identifiers": {"column", "namespace"},
    "h5ad_layer": {"h5_path", "properties", "sample_values"},
}
PROPERTIES = {"non_negative": bool, "integer_valued": bool, "max_at_most": (int, float)}


def names_list(value, what, index):
    if not isinstance(value, list) or not value or any(not isinstance(v, str) or not v for v in value):
        raise ContractError("checks[{}] {} must be a nonempty list of names".format(index, what))


def validate_source(spec, what, index):
    """An independent file the contract declares: a table column, a table header, or a list of lines."""
    allowed = {"path", "column", "header", "lines", "exclude", "filters"}
    if not isinstance(spec, dict) or set(spec) - allowed:
        raise ContractError("checks[{}] {} must be an object with only {}".format(
            index, what, ", ".join(sorted(allowed))))
    if not isinstance(spec.get("path"), str) or not spec["path"]:
        raise ContractError("checks[{}] {} needs a file path".format(index, what))
    forms = [k for k in ("column", "header", "lines") if k in spec]
    if len(forms) != 1:
        raise ContractError("checks[{}] {} needs exactly one of column, header, or lines".format(index, what))
    if forms[0] == "column" and (not isinstance(spec["column"], str) or not spec["column"]):
        raise ContractError("checks[{}] {} column must be a nonempty name".format(index, what))
    if forms[0] != "column" and spec[forms[0]] is not True:
        raise ContractError("checks[{}] {} {} must be true".format(index, what, forms[0]))
    if "exclude" in spec:
        if forms[0] != "header":
            raise ContractError("checks[{}] {} exclude goes with header".format(index, what))
        names_list(spec["exclude"], what + " exclude", index)
    if "filters" in spec:
        if forms[0] != "column":
            raise ContractError("checks[{}] {} filters go with column".format(index, what))
        filter_columns(spec["filters"])


def validate_declared(check, index):
    kind = check["kind"]
    common = {"kind", "id", "label", "table"} | (set() if kind == "h5ad_layer" else {"filters"})
    extra = set(check) - common - DECLARED[kind]
    if extra:
        raise ContractError("checks[{}] {} does not accept: {}".format(index, kind, ", ".join(sorted(extra))))
    if kind == "unique_key":
        names_list(need(check, "columns"), "columns", index)
    elif kind == "sample_alignment":
        validate_source(need(check, "reference"), "reference", index)
        if ("key" in check) == bool(check.get("header_keys")):
            raise ContractError("checks[{}] sample_alignment needs a key column or header_keys: true, not both"
                                .format(index))
        if "key" in check and (not isinstance(check["key"], str) or not check["key"]):
            raise ContractError("checks[{}] key must be a nonempty column name".format(index))
        if "header_keys" in check and check["header_keys"] is not True:
            raise ContractError("checks[{}] header_keys must be true".format(index))
        if "exclude" in check:
            if not check.get("header_keys"):
                raise ContractError("checks[{}] exclude goes with header_keys".format(index))
            names_list(check["exclude"], "exclude", index)
        if "agree_on" in check:
            if "key" not in check or "column" not in check["reference"]:
                raise ContractError("checks[{}] agree_on needs a key column and a reference column".format(index))
            names_list(check["agree_on"], "agree_on", index)
    elif kind == "identifiers":
        need(check, "column")
        if "namespace" in check:
            validate_source(check["namespace"], "namespace", index)
    else:
        if not isinstance(need(check, "h5_path"), str) or not check["h5_path"].strip("/"):
            raise ContractError("checks[{}] h5_path must name a path in the file, such as X or "
                                "layers/counts".format(index))
        props = check.get("properties", {})
        if not isinstance(props, dict) or set(props) - set(PROPERTIES):
            raise ContractError("checks[{}] properties accepts only {}".format(index, ", ".join(sorted(PROPERTIES))))
        for name, value in props.items():
            if isinstance(value, bool) != (PROPERTIES[name] is bool) or not isinstance(value, PROPERTIES[name]):
                raise ContractError("checks[{}] property {} has an invalid value".format(index, name))
        if "sample_values" in check and (isinstance(check["sample_values"], bool)
                                         or not isinstance(check["sample_values"], int)
                                         or check["sample_values"] < 1):
            raise ContractError("checks[{}] sample_values must be a positive integer".format(index))


CHECKS = {
    "schema": check_schema,
    "cohort": check_cohort,
    "unit_of_replication": check_unit,
    "pairing": check_pairing,
    "batch_confounding": check_batch,
    "unique_key": check_unique_key,
    "sample_alignment": check_sample_alignment,
    "identifiers": check_identifiers,
    "h5ad_layer": check_h5ad_layer,
}
NO_ROWS = ("h5ad_layer",)  # reads its own file, not the table's rows


def referenced_columns(check):
    keys = ["column", "unit", "group", "batch", "contrast", "key"]
    cols = [check[k] for k in keys if k in check]
    cols += as_list(check.get("within")) + as_list(check.get("no_missing")) + as_list(check.get("agree_on"))
    if check.get("kind") == "unique_key":
        cols += as_list(check["columns"])
    return cols


def filter_columns(filters):
    if not isinstance(filters, list):
        raise ContractError("filters must be a list")
    for rule in filters:
        if not isinstance(rule, dict) or not isinstance(rule.get("column"), str) or not rule["column"]:
            raise ContractError("each filter needs a nonempty column name")
        operations = [key for key in ("equals", "in", "not_in") if key in rule]
        if len(operations) != 1:
            raise ContractError("each filter needs exactly one of equals, in, or not_in")
        operation = operations[0]
        values = rule[operation]
        if operation != "equals" and not isinstance(values, list):
            raise ContractError("filter {} must be a list".format(operation))
        if any(not isinstance(v, (str, int, float, bool)) for v in
               ([values] if operation == "equals" else values)):
            raise ContractError("filter values must be scalars")
    return [rule["column"] for rule in filters]


RELAXATIONS = ("units_may_span_groups",)


def table_inputs(check, table, path, base_dir):
    found = [{"role": "table", "path": table, "resolved": path}]
    for role in ("reference", "namespace"):
        if role in check:
            found.append({"role": role, "path": check[role]["path"],
                          "resolved": resolve(base_dir, check[role]["path"])})
    return found


def run_contract(contract, base_dir, inputs=None):
    """Return (per-check summaries, alerts); `inputs`, when a list, receives every file the checks name."""
    if not isinstance(contract, dict) or contract.get("schema") != SCHEMA:
        raise ContractError("contract schema must be " + SCHEMA)
    checks = need(contract, "checks")
    if not isinstance(checks, list) or not checks:
        raise ContractError("checks must be a nonempty list")
    global_filters = contract.get("filters", [])
    filter_columns(global_filters)
    summaries, alerts = [], []
    cache = {}
    plan = []
    ids = set()
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            raise ContractError("checks[{}] must be an object".format(index))
        kind = check.get("kind")
        if not isinstance(kind, str) or kind not in CHECKS:
            raise ContractError("unknown check kind at checks[{}]: {}".format(index, kind))
        validate(check, index)
        ident = check.get("id", "checks[{}]".format(index))
        if ident in ids:
            raise ContractError("check id '{}' is used twice".format(ident))
        ids.add(ident)
        table = check.get("table", contract.get("table"))
        if not isinstance(table, str) or not table:
            raise ContractError("checks[{}] has no table".format(index))
        if kind == "h5ad_layer" and not table.lower().endswith(".h5ad"):
            raise ContractError("checks[{}] h5ad_layer needs an .h5ad table".format(index))
        if kind == "sample_alignment" and check.get("header_keys") and table.lower().endswith(".h5ad"):
            raise ContractError("checks[{}] header_keys needs a CSV or TSV table".format(index))
        if kind == "sample_alignment" and check["reference"].get("path") and \
                os.path.realpath(resolve(base_dir, check["reference"]["path"])) == \
                os.path.realpath(resolve(base_dir, table)) and \
                check["reference"].get("column") == check.get("key") and \
                bool(check["reference"].get("header")) == bool(check.get("header_keys")):
            raise ContractError("checks[{}] sample_alignment compares the table with itself; the reference "
                                "must be an independent file".format(index))
        # h5ad_layer reads no rows, so neither the contract's filters nor columns apply to it
        local_filters = [] if kind in NO_ROWS else check.get("filters", [])
        filter_columns(local_filters)
        filters = [] if kind in NO_ROWS else global_filters + local_filters
        path = table if os.path.isabs(table) else os.path.join(base_dir, table)
        named = filter_columns(filters) + ([] if kind in ("schema",) + NO_ROWS else referenced_columns(check))
        plan.append((index, check, kind, table, filters, path, named))
    wanted = defaultdict(set)  # an .h5ad's obs is read only for the columns the contract names
    for _, _, _, _, _, path, named in plan:
        wanted[path].update(named)
    for index, check, kind, table, filters, path, named in plan:
        label = "checks[{}] {}".format(index, check.get("label", kind))
        found = []
        rows_checked = 0
        ctx = {"base_dir": base_dir, "path": path, "table": table}
        if inputs is not None:
            inputs.extend(table_inputs(check, table, path, base_dir))
        if not os.path.isfile(path):
            found.append(alert("schema", "the table the plan names does not exist", True,
                               observed="not found: " + table, cause="table_missing"))
        elif kind in NO_ROWS:
            found.extend(CHECKS[kind](check, [], [], ctx))
        else:
            if path not in cache:
                try:
                    cache[path] = read_table(path, wanted[path])
                except (TableGap, TableShapeError) as error:
                    cache[path] = error
            if isinstance(cache[path], TableGap):
                found.append(alert(kind, "the table cannot be read, so this check did not run", False,
                                   observed=str(cache[path]), gap=True, cause=gap_cause(cache[path])))
                columns, rows, unreadable = [], [], {}
            elif isinstance(cache[path], TableShapeError):
                found.append(alert("schema", "the table is malformed, so no check on it can be trusted", True,
                                   observed=str(cache[path]), cause="table_malformed"))
                columns, rows, unreadable = [], [], {}
            else:
                columns, rows, unreadable = cache[path]
            absent = sorted({c for c in named if c not in columns}) if columns else []
            if absent:
                found.append(alert("schema", "columns this check or its filters name are absent", True,
                                   observed="missing: " + ", ".join(absent), cause="columns_absent"))
            gaps = sorted({c for c in named if c in unreadable})
            if gaps:
                found.append(alert(kind, "columns this check or its filters name cannot be read, so "
                                         "this check did not run", False, gap=True, cause="columns_unreadable",
                                   evidence=["{}: {}".format(c, unreadable[c]) for c in gaps]))
            if not found:
                rows = apply_filters(rows, filters, columns)
                rows_checked = len(rows)
                if not rows:
                    found.append(alert(kind, "no rows left after filters; the check would pass vacuously", True,
                                       expected=">= 1 row", cause="no_rows",
                                       observed="0 of {} rows".format(len(cache[path][1])),
                                       evidence=[json.dumps(f, sort_keys=True) for f in filters]))
                else:
                    found.extend(CHECKS[kind](check, columns, rows, ctx))
        for record in found:
            record["check"] = label
            record["table"] = table
            record["rows_checked"] = rows_checked
        status = "block" if any(a["blocking"] for a in found) else \
            "gap" if any(a["severity"] == "gap" for a in found) else ("warn" if found else "pass")
        summary = {"check": label, "kind": kind, "table": table, "rows_checked": rows_checked,
                   "status": status, "relaxations": [k for k in RELAXATIONS if check.get(k)],
                   "id": check.get("id", "checks[{}]".format(index)),
                   "runnable": next((a["cause"] for a in found if a.get("cause")), "ran"),
                   "message": "; ".join(a["message"] for a in found) or "passed on {} rows".format(rows_checked)}
        if kind in NOTES:
            summary["note"] = NOTES[kind]
        if kind == "batch_confounding" and rows_checked:
            summary["cross_table"] = cross_table(check, rows)
        summaries.append(summary)
        alerts.extend(found)
    return summaries, alerts


def render(summaries, alerts):
    blocking = sum(a["blocking"] for a in alerts)
    gaps = sum(a["severity"] == "gap" for a in alerts)
    lines = ["{} checks; {} blocking alerts, {} warnings{}.".format(
        len(summaries), blocking, len(alerts) - blocking - gaps, ", {} gaps".format(gaps) if gaps else "")]
    for summary in summaries:
        line = "{:5} {} ({} rows)".format(summary["status"].upper(), summary["check"], summary["rows_checked"])
        if summary["relaxations"]:
            line += "  relaxed: " + ", ".join(summary["relaxations"])
        lines.append(line)
        if "note" in summary:
            lines.append("    note: " + summary["note"])
        if "cross_table" in summary:
            lines.append("    rows by batch and contrast level (share of the level):")
            lines.extend("      " + row for row in render_cross_table(summary["cross_table"]))
        for a in (a for a in alerts if a["check"] == summary["check"]):
            label = "BLOCK" if a["blocking"] else ("GAP  " if a["severity"] == "gap" else "warn:")
            lines.append("    {} {}".format(label, a["message"]))
            for key in ("expected", "observed"):
                if key in a:
                    lines.append("      {}: {}".format(key, a[key]))
            for item in a.get("evidence", []):
                lines.append("      - " + item)
    return "\n".join(lines)


HASH_LIMIT = 1 << 30


def file_identity(path):
    """sha256 of the bytes, or a stated weaker identity; read after the checks, so a file changed during the run
    is described as it ended (ponytail: hash before and after if a concurrent writer ever matters)."""
    try:
        if not os.path.isfile(path):
            return {"sha256": None, "identity": "absent"}
        info = os.stat(path)
        if info.st_size > HASH_LIMIT:
            return {"sha256": None, "identity": "size+mtime_ns", "size": info.st_size,
                    "mtime_ns": info.st_mtime_ns}
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
        return {"sha256": digest.hexdigest(), "identity": "sha256", "size": info.st_size}
    except OSError as error:
        return {"sha256": None, "identity": "unavailable: {}".format(error)}


def exit_code(alerts):
    if any(a["blocking"] for a in alerts):
        return 2
    return 3 if any(a["severity"] == "gap" for a in alerts) else 0


def build_result(contract_path, root, contract_bytes, summaries, alerts, inputs, code, error=None):
    """The machine-readable result: identities, each check's own status and message, and whether it could run."""
    seen, tables = set(), []
    for item in inputs:
        if (item["role"], item["resolved"]) not in seen:
            seen.add((item["role"], item["resolved"]))
            tables.append(dict(item, resolved=os.path.abspath(item["resolved"]), **file_identity(item["resolved"])))
    checks = []
    for summary in summaries:
        record = dict((k, summary[k]) for k in ("id", "check", "kind", "status", "runnable", "message", "table",
                                                "rows_checked", "relaxations", "note") if k in summary)
        record["alerts"] = [a for a in alerts if a["check"] == summary["check"]]
        checks.append(record)
    not_run = [c["id"] for c in checks if c["runnable"] != "ran"]
    worst = "error" if error else ("block" if code == 2 else "gap" if code == 3 else
                                   "warn" if alerts else "pass")
    return {
        "schema": RESULT_SCHEMA,
        "contract": {"path": os.path.abspath(contract_path),
                     "sha256": hashlib.sha256(contract_bytes).hexdigest() if contract_bytes is not None else None},
        "root": os.path.abspath(root),
        "tables": tables,
        "checks": checks,
        "exit_code": code,
        "status": worst,
        # "ran" means the check's own logic executed; a table or reader that was missing is not a pass
        "runnable": "contract_error" if error else ("incomplete" if not_run else "all_ran"),
        "not_run": not_run,
        "error": error,
    }


def write_result(path, result):
    tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=os.path.dirname(os.path.abspath(path)),
                                         delete=False) as handle:
            tmp = handle.name
            json.dump(result, handle, indent=1, sort_keys=True)
            handle.write("\n")
        os.replace(tmp, path)
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


# ---------------------------------------------------------------- descriptive profile

PROFILE_REQUEST = "mycelium-extra.data-profile-request.v1"
PROFILE_RESULT = "mycelium-extra.data-profile.v1"
PROFILE_KEYS = {"schema", "table", "unit_key", "row_key", "group_by", "missingness_columns",
                "max_rows_inspected", "max_groups", "small_cell_suppression"}
# name: (smallest, largest, default). Resource and privacy limits, not scientific thresholds.
PROFILE_LIMITS = {"max_rows_inspected": (1, 5000000, 250000), "max_groups": (1, 1000, 24),
                  "small_cell_suppression": (1, 1000, 5)}
PROFILE_NOT_ESTABLISHED = ["eligibility or correctness of the identifiers", "biological plausibility",
                           "that any expectation the plan makes holds", "statistical inference"]


def read_profile_spec(path):
    """The request as a dict with every limit filled in; anything else is a usage error."""
    try:
        with open(path, encoding="utf-8") as handle:
            spec = json.load(handle)
    except (OSError, ValueError) as error:
        raise ContractError("cannot read the profile spec: {}".format(error))
    if not isinstance(spec, dict) or spec.get("schema") != PROFILE_REQUEST:
        raise ContractError("the profile spec must be an object with schema '{}'".format(PROFILE_REQUEST))
    unknown = sorted(set(spec) - PROFILE_KEYS)
    if unknown:
        raise ContractError("unknown profile spec key(s): {}".format(", ".join(unknown)))
    if not isinstance(spec.get("table"), str) or not spec["table"]:
        raise ContractError("the profile spec needs a 'table' path")
    for name in ("unit_key", "row_key"):
        if spec.get(name) is not None and (not isinstance(spec[name], str) or not spec[name]):
            raise ContractError("'{}' must be a column name".format(name))
    for name in ("group_by", "missingness_columns"):
        value = spec.get(name, [])
        if not isinstance(value, list) or not all(isinstance(c, str) and c for c in value) or len(set(value)) != len(value):
            raise ContractError("'{}' must be a list of distinct column names".format(name))
        if name == "group_by" and len(value) > 4:
            raise ContractError("'group_by' takes at most 4 columns")
        if name == "group_by" and {spec.get("unit_key"), spec.get("row_key")} & set(value):
            raise ContractError("'group_by' cannot name the unit or row key: its values identify individuals")
        spec[name] = value
    for name, (low, high, default) in PROFILE_LIMITS.items():
        value = spec.get(name, default)
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ContractError("'{}' must be an integer from {} to {}".format(name, low, high))
        spec[name] = value
    return spec


def profile_table(path, spec):
    """Stream a CSV/TSV once, with the strict settings of read_table, and keep only bounded aggregates."""
    lower = path.lower()
    if lower.endswith(".h5ad"):
        raise TableGap("an .h5ad obs table cannot be read within a row budget here; export obs to CSV or TSV")
    if lower.endswith(".csv"):
        delimiter = ","
    elif lower.endswith(TAB_SEPARATED):
        delimiter = "\t"
    else:
        raise TableGap("unsupported table format '{}'; export it to CSV or TSV".format(
            os.path.splitext(path)[1] or path))
    group_by, miss = spec["group_by"], spec["missingness_columns"]
    unit_key, row_key = spec.get("unit_key"), spec.get("row_key")
    wanted = group_by + miss + [c for c in (unit_key, row_key) if c]
    rows, partial = 0, False
    groups, overflow = Counter(), False
    group_missing = {c: Counter() for c in miss}
    missing = Counter()
    units, row_keys = set(), set()
    try:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.reader(handle, delimiter=delimiter, strict=True)
            columns = next(reader, None)
            if columns is None:
                raise TableGap("the table is empty")
            named = [c for c in columns if c.strip()]
            if len(set(named)) != len(named):
                raise TableGap("the table has duplicate column headers")
            absent = [c for c in wanted if c not in columns]
            if absent:
                raise TableGap("column(s) absent from the table: {}".format(", ".join(absent)))
            at = {c: columns.index(c) for c in wanted}
            for record in reader:
                if len(record) > len(columns):
                    raise TableShapeError("line {} has more fields than the header, so its values cannot be "
                                          "assigned to columns".format(reader.line_num))
                if not any(field.strip() for field in record):
                    continue
                if rows >= spec["max_rows_inspected"]:
                    partial = True
                    break
                rows += 1
                record = record + [""] * (len(columns) - len(record))
                group = tuple(record[at[c]] for c in group_by)
                if group_by and not overflow:
                    groups[group] += 1
                    if len(groups) > spec["max_groups"]:
                        groups, overflow = Counter(), True
                for column in miss:
                    if is_missing(record[at[column]]):
                        missing[column] += 1
                        if group_by and not overflow:
                            group_missing[column][group] += 1
                if unit_key:
                    units.add(record[at[unit_key]])
                if row_key:
                    row_keys.add(record[at[row_key]])
    except UnicodeDecodeError as error:
        raise TableGap("the table is not valid UTF-8 (byte {} at offset {})".format(
            error.object[error.start:error.start + 1], error.start))
    except csv.Error as error:
        raise TableShapeError("line {} cannot be parsed ({}), so later rows may be missing or merged".format(
            reader.line_num, error))
    return {"rows": rows, "partial": partial, "groups": groups, "overflow": overflow, "missing": missing,
            "group_missing": group_missing, "units": len(units) if unit_key else None,
            "row_keys": len(row_keys) if row_key else None}


def profile_result(spec, stats, error=None):
    """The mycelium-extra.data-profile.v1 record. Counts below the suppression limit are never named."""
    limit = spec["small_cell_suppression"]
    result = {"schema": PROFILE_RESULT, "table": spec["table"], "not_established": PROFILE_NOT_ESTABLISHED}
    if error:
        result.update(inspection="unavailable", reason=error)
        return result
    partial = stats["partial"]
    result["inspection"] = "partial" if partial else "complete"
    result["coverage"] = {"rows_inspected": stats["rows"], "rows_total": None if partial else stats["rows"],
                          "rows_total_basis": "row budget reached" if partial else "fully_read",
                          "max_rows_inspected": spec["max_rows_inspected"]}
    descriptive = {"distinct_units_inspected": stats["units"], "distinct_row_keys_inspected": stats["row_keys"]}
    privacy = {"small_cell_suppression": limit, "applied": False, "identifiable_rows_exported": False}
    groups = stats["groups"]
    if spec["group_by"]:
        if stats["overflow"]:
            descriptive["group_counts"] = None
            descriptive["group_counts_omitted"] = "more than {} groups".format(spec["max_groups"])
        elif stats["units"] and stats["units"] > 1 and len(groups) == stats["units"]:
            descriptive["group_counts"] = None  # one group per unit: the labels are identifiers in disguise
            descriptive["group_counts_omitted"] = "there is one group per unit"
            privacy["applied"] = True
        elif any(n < limit for n in groups.values()):
            # One hidden cell is recoverable from the total and a shown cell, so hide the whole breakdown.
            descriptive["group_counts"] = None
            descriptive["group_counts_omitted"] = "a group is smaller than {}".format(limit)
            privacy["applied"] = True
        else:
            descriptive["group_counts"] = [dict(zip(spec["group_by"], key), count=n) for key, n in sorted(groups.items())]
    descriptive["missingness"] = []
    for column in spec["missingness_columns"]:
        entry = {"column": column, "inspected": stats["rows"], "missing": stats["missing"][column]}
        by_group = stats["group_missing"][column]
        if spec["group_by"] and descriptive.get("group_counts") is not None:
            if any(0 < n < limit for n in by_group.values()):
                entry["by_group"] = None
                entry["by_group_omitted"] = "a count is smaller than {}".format(limit)
                privacy["applied"] = True
            else:
                entry["by_group"] = [dict(zip(spec["group_by"], key), missing=by_group[key]) for key in sorted(groups)]
        descriptive["missingness"].append(entry)
    result["descriptive"], result["privacy"] = descriptive, privacy
    return result


def render_profile(result):
    """About ten lines of text; never a pass or fail word."""
    unit = "descriptive, not a validation result"
    if result["inspection"] == "unavailable":
        return "DATA REALITY \u00b7 {}\nTable    {}\nCoverage unavailable: {}\nNot established: {}".format(
            unit, result["table"], result["reason"], "everything about this table")
    cov, desc = result["coverage"], result["descriptive"]
    lines = ["DATA REALITY \u00b7 {}{}".format(unit, "; PARTIAL" if result["inspection"] == "partial" else ""),
             "Table    {}".format(result["table"])]
    if result["inspection"] == "complete":
        lines.append("Coverage complete: {0} of {0} rows read".format(cov["rows_inspected"]))
    else:
        lines.append("Coverage {} rows inspected; row budget reached; total rows not established".format(cov["rows_inspected"]))
    if desc["distinct_units_inspected"] is not None:
        lines.append("Units    {} distinct unit key values (among inspected rows)".format(desc["distinct_units_inspected"]))
    if "group_counts" in desc:
        if desc["group_counts"] is None:
            lines.append("Groups   omitted: {}".format(desc["group_counts_omitted"]))
        else:
            lines.append("Groups   " + "; ".join("{} {}".format(" / ".join(str(v) for k, v in g.items() if k != "count"), g["count"])
                                                for g in desc["group_counts"]) + (" (inspected rows only)" if result["inspection"] == "partial" else ""))
    for entry in desc["missingness"]:
        line = "Missing  {}: {} / {}".format(entry["column"], entry["missing"], entry["inspected"])
        if entry.get("by_group"):
            line += "; " + ", ".join("{} {}".format(" / ".join(str(v) for k, v in g.items() if k != "missing"), g["missing"])
                                     for g in entry["by_group"])
        elif "by_group_omitted" in entry:
            line += "; by-group breakdown omitted ({})".format(entry["by_group_omitted"])
        lines.append(line)
    lines.append("Not established: " + ", ".join(result["not_established"]))
    return "\n".join(lines)


def profile_main(argv):
    parser = argparse.ArgumentParser(prog="data_contract_check.py --profile-only",
                                     description="Describe a table's size, groups and missing values, read-only. Not a check.")
    parser.add_argument("--profile-only", action="store_true", required=True)
    parser.add_argument("--profile-spec", required=True, help="path to the profile request JSON")
    parser.add_argument("--root", default=".", help="directory a relative table path resolves from")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        spec = read_profile_spec(args.profile_spec)
    except ContractError as caught:
        print("profile error: {}".format(caught), file=sys.stderr)
        return 1
    try:
        result = profile_result(spec, profile_table(resolve(args.root, spec["table"]), spec))
    except (TableGap, TableShapeError, OSError) as caught:
        result = profile_result(spec, None, error=str(caught))
    if args.json:
        json.dump(result, sys.stdout, indent=1)
        print()
    else:
        print(render_profile(result))
    return 3 if result["inspection"] == "unavailable" else 0


def main(argv=None):
    if "--profile-only" in (sys.argv[1:] if argv is None else argv):
        return profile_main(sys.argv[1:] if argv is None else argv)  # a separate parser: ordinary usage text is untouched
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--contract", required=True, help="path to the contract JSON")
    parser.add_argument("--root", default=".", help="directory relative table paths resolve from")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--result-json", metavar="PATH",
                        help="also write a machine-readable result (identities, per-check status, exit code) here")
    args = parser.parse_args(argv)
    contract, contract_bytes, summaries, alerts, inputs, error = None, None, [], [], [], None
    try:
        with open(args.contract, "rb") as handle:
            contract_bytes = handle.read()
        contract = json.loads(contract_bytes.decode("utf-8"))
        summaries, alerts = run_contract(contract, args.root, inputs)
    except (ContractError, ValueError, OSError) as caught:
        error = str(caught)
    code = 1 if error else exit_code(alerts)
    if args.result_json:
        # Protect declared inputs even when validation stopped before recording their identities.
        paths = [args.contract]
        if isinstance(contract, dict):
            checks = contract.get("checks")
            for check in [contract] + (checks if isinstance(checks, list) else []):
                if not isinstance(check, dict):
                    continue
                if isinstance(check.get("table"), str):
                    paths.append(resolve(args.root, check["table"]))
                for role in ("reference", "namespace"):
                    spec = check.get(role)
                    if isinstance(spec, dict) and isinstance(spec.get("path"), str):
                        paths.append(resolve(args.root, spec["path"]))
        if os.path.realpath(args.result_json) in {os.path.realpath(p) for p in paths}:
            print("result path must differ from the contract and all input paths", file=sys.stderr)
            return 1
        try:
            write_result(args.result_json, build_result(args.contract, args.root, contract_bytes, summaries,
                                                        alerts, inputs, code, error))
        except OSError as caught:
            print("cannot write the result file: {}".format(caught), file=sys.stderr)
            return 1
    if error:
        print("contract error: {}".format(error), file=sys.stderr)
        return 1
    if args.json:
        json.dump({"checks": summaries, "alerts": alerts}, sys.stdout, indent=1)
        print()
    else:
        print(render(summaries, alerts))
    return code


if __name__ == "__main__":
    if sys.stdout.encoding.lower().replace("-", "") != "utf8":  # an ASCII locale on Python 3.6
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, sys.stdout.encoding, "backslashreplace")
    sys.exit(main())
