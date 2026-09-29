"""Check a plan's data assumptions against a sample-level table, read-only.

Stdlib-only; runs on Python 3.6+. Run it from stdin so Mycelium's hooks do
not open the post-action cycle:

    python3 - --contract /tmp/contract.json < data_contract_check.py

The contract states what the plan assumes; this script decides what blocks.
Every failed check of a coverage-list kind blocks, and the contract cannot
downgrade it. Exit codes: 0 clean or warnings only, 2 blocking, 1 usage or
input error.
"""

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict

SCHEMA = "mycelium-extra.data_contract.v1"
ALERT_SCHEMA = "mycelium-extra.contract_alert.v1"
MISSING = {"", "na", "nan", "null", "none", "<na>"}
MAX_EVIDENCE = 5


class ContractError(Exception):
    pass


def is_missing(value):
    return value is None or value.strip().lower() in MISSING


def alert(kind, message, blocking, expected=None, observed=None, evidence=None):
    record = {
        "schema": ALERT_SCHEMA,
        "severity": "error" if blocking else "warning",
        "kind": kind,
        "message": message,
        "blocking": blocking,
    }
    if expected is not None:
        record["expected"] = expected
    if observed is not None:
        record["observed"] = observed
    if evidence:
        record["evidence"] = [str(item) for item in evidence[:MAX_EVIDENCE]]
        if len(evidence) > MAX_EVIDENCE:
            record["evidence"].append("... {} more".format(len(evidence) - MAX_EVIDENCE))
    return record


def read_table(path):
    delimiter = "," if path.lower().endswith(".csv") else "\t"
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


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


def check_schema(check, columns, rows):
    missing = [c for c in need(check, "columns") if c not in columns]
    if not missing:
        return []
    return [alert("schema", "required columns are absent", True,
                  expected=", ".join(check["columns"]), observed="missing: " + ", ".join(missing))]


def check_cohort(check, columns, rows):
    alerts = []
    column = check.get("column")
    if column is not None:
        present = Counter(r[column] for r in rows)
        absent = [lvl for lvl in as_list(check.get("levels")) if str(lvl) not in present]
        if absent:
            alerts.append(alert(
                "cohort", "required levels of '{}' are absent after filtering".format(column), True,
                expected=", ".join(str(l) for l in check["levels"]),
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


def check_unit(check, columns, rows):
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


def check_pairing(check, columns, rows):
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


def check_batch(check, columns, rows):
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
    return alerts


CHECKS = {
    "schema": check_schema,
    "cohort": check_cohort,
    "unit_of_replication": check_unit,
    "pairing": check_pairing,
    "batch_confounding": check_batch,
}


def referenced_columns(check):
    keys = ["column", "unit", "group", "batch", "contrast"]
    cols = [check[k] for k in keys if k in check]
    cols += as_list(check.get("within")) + as_list(check.get("no_missing"))
    return cols


def filter_columns(filters):
    return [rule.get("column") for rule in filters]


RELAXATIONS = ("units_may_span_groups",)


def run_contract(contract, base_dir):
    """Return (per-check summaries, alerts)."""
    if contract.get("schema") != SCHEMA:
        raise ContractError("contract schema must be " + SCHEMA)
    summaries, alerts = [], []
    cache = {}
    for index, check in enumerate(need(contract, "checks")):
        kind = check.get("kind")
        if kind not in CHECKS:
            raise ContractError("unknown check kind at checks[{}]: {}".format(index, kind))
        table = check.get("table", contract.get("table"))
        if not table:
            raise ContractError("checks[{}] has no table".format(index))
        label = "checks[{}] {}".format(index, check.get("label", kind))
        filters = contract.get("filters", []) + check.get("filters", [])
        path = table if os.path.isabs(table) else os.path.join(base_dir, table)
        found = []
        if not os.path.isfile(path):
            found.append(alert("schema", "the table the plan names does not exist", True,
                               observed="not found: " + table))
            columns, rows = [], []
        else:
            if path not in cache:
                cache[path] = read_table(path)
            columns, rows = cache[path]
            named = filter_columns(filters) + ([] if kind == "schema" else referenced_columns(check))
            absent = sorted({c for c in named if c not in columns})
            if absent:
                found.append(alert("schema", "columns this check or its filters name are absent", True,
                                   observed="missing: " + ", ".join(absent)))
        rows_checked = 0
        if not found:
            rows = apply_filters(rows, filters, columns)
            rows_checked = len(rows)
            if not rows:
                found.append(alert(kind, "no rows left after filters; the check would pass vacuously", True,
                                   expected=">= 1 row",
                                   observed="0 of {} rows".format(len(cache[path][1])),
                                   evidence=[json.dumps(f, sort_keys=True) for f in filters]))
            else:
                found.extend(CHECKS[kind](check, columns, rows))
        for record in found:
            record["check"] = label
            record["table"] = table
            record["rows_checked"] = rows_checked
        status = "block" if any(a["blocking"] for a in found) else ("warn" if found else "pass")
        summaries.append({"check": label, "kind": kind, "table": table, "rows_checked": rows_checked,
                          "status": status, "relaxations": [k for k in RELAXATIONS if check.get(k)]})
        alerts.extend(found)
    return summaries, alerts


def render(summaries, alerts):
    blocking = sum(a["blocking"] for a in alerts)
    lines = ["{} checks; {} blocking alerts, {} warnings.".format(
        len(summaries), blocking, len(alerts) - blocking)]
    for summary in summaries:
        line = "{:5} {} ({} rows)".format(summary["status"].upper(), summary["check"], summary["rows_checked"])
        if summary["relaxations"]:
            line += "  relaxed: " + ", ".join(summary["relaxations"])
        lines.append(line)
        for a in (a for a in alerts if a["check"] == summary["check"]):
            lines.append("    {} {}".format("BLOCK" if a["blocking"] else "warn:", a["message"]))
            for key in ("expected", "observed"):
                if key in a:
                    lines.append("      {}: {}".format(key, a[key]))
            for item in a.get("evidence", []):
                lines.append("      - " + item)
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--contract", required=True, help="path to the contract JSON")
    parser.add_argument("--root", default=".", help="directory relative table paths resolve from")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        with open(args.contract) as handle:
            contract = json.load(handle)
        summaries, alerts = run_contract(contract, args.root)
    except (ContractError, ValueError, OSError) as error:
        print("contract error: {}".format(error), file=sys.stderr)
        return 1
    if args.json:
        json.dump({"checks": summaries, "alerts": alerts}, sys.stdout, indent=1)
        print()
    else:
        print(render(summaries, alerts))
    return 2 if any(a["blocking"] for a in alerts) else 0


if __name__ == "__main__":
    sys.exit(main())
