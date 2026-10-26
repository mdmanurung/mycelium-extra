#!/usr/bin/env python3
"""Read-only manuscript artifact-contract checks (except optional result JSON).

No biological conclusion is validated. Exit: 0=pass, 1=usage error (nothing was
judged), 2=declared contract failed, 3=gap/malformed/unavailable. JSON follows
mycelium-extra.contract_result.v1. Python 3.9+, standard library only. This tool
does not execute notebooks or plots.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile

SCHEMA = "mycelium-extra.manuscript_checks.v1"
RESULT_SCHEMA = "mycelium-extra.contract_result.v1"
MAX_TABLE_BYTES = 16 * 1024 * 1024  # check only small, published plot/source tables
ALLOWED = {
    "contract": {"schema", "data_manifest", "figure_map", "figures", "tables"},
    "figure": {"id", "script", "source_data", "required_columns", "outputs"},
    "table": {"id", "file", "key_columns", "required_columns", "finite_numeric_columns",
              "nonnegative_integer_columns", "ratio_invariant"},
    "ratio_invariant": {"numerator", "denominator", "fraction", "tolerance"},
}


class UsageError(Exception):
    """Bad command line or destination; nothing was judged. Exit 1, never 2."""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, "{}: error: {}\n".format(self.prog, message))


def resolve_under(root, name):
    if not isinstance(name, str) or not name.strip():
        raise ValueError("path must be a non-empty string")
    candidate = Path(name)
    if candidate.is_absolute():
        raise ValueError("absolute project path is not permitted: " + name)
    path = (root / candidate).resolve()
    if path != root and root not in path.parents:
        raise ValueError("path outside project: " + name)
    return path


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as inp:
        for chunk in iter(lambda: inp.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_table(path):
    if path.stat().st_size > MAX_TABLE_BYTES:
        raise ValueError("table exceeds 16 MiB lightweight-check limit")
    delim = "\t" if path.suffix.lower() in (".tsv", ".tab", ".txt") else ","
    with path.open("r", encoding="utf-8-sig", newline="") as inp:
        reader = csv.reader(inp, delimiter=delim, strict=True)
        header = [h.strip() for h in next(reader, None) or []]
        if not header or not all(header) or len(set(header)) != len(header):
            raise ValueError("empty, blank or duplicated column headers")
        other = "," if delim == "\t" else "\t"
        if len(header) == 1 and other in header[0]:
            raise ValueError("one column only; file looks " + ("comma" if other == "," else "tab") + "-delimited")
        rows = []
        for row in reader:
            if not any(c.strip() for c in row):
                continue
            if len(row) != len(header):
                raise ValueError("row width differs from header")
            rows.append(dict(zip(header, row)))
    return header, rows


def compare_fraction(num, den, value, tol=1e-8):
    if den <= 0 or num < 0 or num > den or value < 0 or value > 1:
        return False
    return math.isclose(num / den, value, abs_tol=tol, rel_tol=tol)


def checked_num(value, column, integer=False):
    """Parse one cell; an error names the column, never the cell's value."""
    value = value.strip()
    if value == "":
        raise ValueError("column " + column + ": missing numeric value")
    if integer:
        if not re.fullmatch(r"[0-9]+", value):
            raise ValueError("column " + column + ": not a nonnegative integer count")
        return int(value)
    if not re.fullmatch(r"[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?", value, re.ASCII):
        raise ValueError("column " + column + ": not a number")
    n = float(value)
    if not math.isfinite(n):
        raise ValueError("column " + column + ": non-finite numeric value")
    return n


def unknown_keys(entry, kind):
    """Name the first undeclared key, so a misspelled check is a gap, not a silent skip."""
    extra = sorted(set(entry) - ALLOWED[kind])
    if extra:
        raise ValueError("unknown " + kind + " key: " + extra[0])


def column_list(value, what):
    """A declared column list must be a list of nonempty unique strings."""
    if not isinstance(value, list) or not value or \
            not all(isinstance(x, str) and x.strip() for x in value) or \
            len(set(value)) != len(value):
        raise ValueError("malformed declaration: " + what + " must be a nonempty list of unique column names")
    return value


def evaluate(root, config_rel):
    """Return a status report; do not write/modify any project data."""
    root = Path(root).resolve()
    contract = {"path": str(config_rel), "sha256": None}
    checks, inputs = [], []

    def add(check_id, status, msg, **kw):
        checks.append({"id": check_id, "status": status, "message": msg, **kw})

    def observe(path):
        try:
            path = resolve_under(root, path)
            exists = path.is_file()
            size = path.stat().st_size if exists else None
            hashed = exists and size <= MAX_TABLE_BYTES
            rel = str(path.relative_to(root))
            if not any(i["path"] == rel for i in inputs):
                inputs.append({"path": rel, "sha256": sha256(path) if hashed else None, "size": size,
                               "identity": "sha256" if hashed else "size_only" if exists else "absent"})
            return path if exists else None
        except (OSError, ValueError) as e:
            raise ValueError(str(e))

    try:
        path = resolve_under(root, config_rel)
        raw = path.read_bytes()
        contract["sha256"] = hashlib.sha256(raw).hexdigest()
        cfg = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicate_json_keys)
        if not isinstance(cfg, dict) or cfg.get("schema") != SCHEMA:
            raise ValueError("missing/unsupported schema")
        if not isinstance(cfg.get("figures", []), list) or not isinstance(cfg.get("tables", []), list):
            raise ValueError("figures and tables must be lists")
        if not cfg.get("figures") and not cfg.get("tables"):
            raise ValueError("at least one figure or table contract required")
        unknown_keys(cfg, "contract")
    except (OSError, UnicodeDecodeError, ValueError, TypeError) as e:
        add("config", "gap", "Unreadable or invalid contract: " + str(e))
        return make_result(contract, inputs, checks)

    if "data_manifest" in cfg:
        try:
            manifest_path = observe(cfg["data_manifest"])
            add("data-manifest", "pass" if manifest_path else "gap",
                "Declared data manifest exists" if manifest_path else "Declared data manifest unavailable")
        except ValueError as e:
            add("data-manifest", "gap", str(e))

    seen_ids = set()
    for fig in cfg.get("figures", []):
        if not isinstance(fig, dict) or not all(k in fig for k in ("id", "script", "source_data", "required_columns")):
            add("figure-declaration", "gap", "figure entry missing required fields")
            continue
        if not isinstance(fig["id"], str) or not fig["id"].strip():
            add("figure-declaration", "gap", "figure id must be a nonblank string")
            continue
        fid = fig["id"].strip()
        if fid in seen_ids:
            add("figure:" + fid, "block", "duplicate figure id")
            continue
        seen_ids.add(fid)
        base = "figure:" + fid
        try:
            unknown_keys(fig, "figure")
            required = column_list(fig["required_columns"], "required_columns")
        except ValueError as e:
            add(base, "gap", str(e))
            continue
        outputs = fig.get("outputs")
        if not isinstance(outputs, list) or not all(isinstance(x, str) and x.strip() for x in outputs):
            add(base, "gap", "outputs must be a list of project-relative paths; use [] for a source-only declaration")
            continue
        try:
            script = observe(fig["script"])
            src = observe(fig["source_data"])
            add(base + ":script", "pass" if script else "gap", "Figure script available" if script else "Figure script unavailable")
            if not src:
                add(base + ":source", "gap", "Declared source-data table unavailable")
            else:
                cols, rows = read_table(src)
                if not rows:
                    add(base + ":source", "block", "Source-data table has no data rows")
                    continue
                missing = sorted(set(required) - set(cols))
                add(base + ":source", "block" if missing else "pass", "Missing declared plotting columns: " + ", ".join(missing) if missing else "All declared plotting columns present (not proof all actual aesthetics declared)", n_rows=len(rows))
            if not outputs:
                add(base + ":output", "pass", "Source-only declaration: no rendered output declared or checked")
            for output in outputs:
                output_path = observe(output)
                full = bool(output_path) and output_path.stat().st_size > 0
                add(base + ":output:" + output, "pass" if full else "gap", "Figure output present" if full else "Figure output is empty" if output_path else "Figure output not observed")
        except (ValueError, OSError, csv.Error) as e:
            add(base, "gap", "Cannot inspect figure contract: " + str(e))

    if "figure_map" in cfg:
        check_figure_map(cfg, observe, add)

    seen_tables = set()
    for tbl in cfg.get("tables", []):
        if not isinstance(tbl, dict) or not all(x in tbl for x in ("id", "file", "key_columns")):
            add("table-declaration", "gap", "table contract requires id/file/key_columns")
            continue
        if not isinstance(tbl["id"], str) or not tbl["id"].strip():
            add("table-declaration", "gap", "table id must be a nonblank string")
            continue
        tid = tbl["id"].strip()
        if tid in seen_tables:
            add("table:" + tid, "block", "duplicate table id")
            continue
        seen_tables.add(tid)
        base = "table:" + tid
        try:
            unknown_keys(tbl, "table")
            keys = column_list(tbl["key_columns"], "key_columns")
            req_extra, numeric, counts = [column_list(tbl[k], k) if k in tbl else []
                                          for k in ("required_columns", "finite_numeric_columns", "nonnegative_integer_columns")]
        except ValueError as e:
            add(base, "gap", str(e))
            continue
        try:
            path = observe(tbl["file"])
            if not path:
                add(base, "gap", "Table unavailable")
                continue
            cols, rows = read_table(path)
            if not rows:
                add(base, "block", "Declared table has no data rows")
                continue
            required = set(req_extra) | set(keys) | set(numeric) | set(counts)
            ratio = tbl.get("ratio_invariant")
            tolerance = 1e-8
            if "ratio_invariant" in tbl:
                if not isinstance(ratio, dict) or not all(isinstance(ratio.get(k), str) and ratio.get(k) for k in ("numerator", "denominator", "fraction")):
                    add(base, "gap", "Malformed ratio_invariant declaration")
                    continue
                try:
                    unknown_keys(ratio, "ratio_invariant")
                except ValueError as e:
                    add(base, "gap", str(e))
                    continue
                tolerance = ratio.get("tolerance", 1e-8)
                if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
                    add(base, "gap", "ratio_invariant tolerance must be a JSON number")
                    continue
                if not math.isfinite(tolerance) or tolerance < 0:
                    add(base, "gap", "ratio_invariant tolerance must be finite and nonnegative")
                    continue
                required.update([ratio["numerator"], ratio["denominator"], ratio["fraction"]])
            missing = sorted(required - set(cols))
            if missing:
                add(base, "block", "Missing table columns: " + ", ".join(missing))
                continue
            ids = set()
            problem = None
            for n, row in enumerate(rows, 2):
                key = tuple(row[k].strip() for k in keys)
                if any(not v.strip() for v in key):
                    problem = "missing key at row " + str(n); break
                if key in ids:
                    problem = "duplicate key at row " + str(n) + " in " + ", ".join(keys); break
                ids.add(key)
                try:
                    for col in counts:
                        checked_num(row[col], col, integer=True)
                    for col in numeric:
                        checked_num(row[col], col)
                    if ratio:
                        parts = [checked_num(row[ratio[k]], ratio[k], integer=k != "fraction") for k in ("numerator", "denominator", "fraction")]
                        if not compare_fraction(*parts, tolerance):
                            raise ValueError("fraction inconsistent with declared numerator/denominator")
                except (ValueError, KeyError, TypeError) as err:
                    problem = "row " + str(n) + ": " + str(err); break
            ran = ["key uniqueness"] + ["declared integer counts"] * bool(counts) + ["declared numeric types"] * bool(numeric) + ["ratio invariant"] * bool(ratio)
            add(base, "block" if problem else "pass", problem or ", ".join(ran).capitalize() + " passed", n_rows=len(rows))
        except (ValueError, OSError, csv.Error, TypeError) as e:
            add(base, "gap", "Cannot inspect table: " + str(e))
    return make_result(contract, inputs, checks)


def check_figure_map(cfg, observe, add):
    """Every figure contract has one map row, and every row's script and source data exist."""
    try:
        path = observe(cfg["figure_map"])
        if not path:
            add("figure-map", "gap", "Declared figure map unavailable")
            return
        cols, rows = read_table(path)
    except (ValueError, OSError, csv.Error) as e:
        add("figure-map", "gap", "Cannot read figure map: " + str(e))
        return
    missing_cols = sorted({"figure", "script", "source_data"} - set(cols))
    if missing_cols:
        add("figure-map", "gap", "Figure map lacks columns: " + ", ".join(missing_cols))
        return
    ids = [row["figure"].strip() for row in rows]
    blank = [str(n) for n, i in enumerate(ids, 2) if not i]
    if blank:
        add("figure-map", "gap", "Figure map has blank figure ids at rows: " + ", ".join(blank))
    repeated = sorted({i for i in ids if i and ids.count(i) > 1})
    if repeated:
        add("figure-map", "block", "Figure map repeats ids: " + ", ".join(repeated))
        return
    declared = [f["id"].strip() for f in cfg.get("figures", []) if isinstance(f, dict) and isinstance(f.get("id"), str) and f["id"].strip()]
    unmapped = [i for i in declared if i not in ids]
    if unmapped:
        add("figure-map", "gap", "Figure contracts without a map row: " + ", ".join(unmapped))
    unavailable = 0
    for n, row in enumerate(rows, 2):
        for col in ("script", "source_data"):
            try:
                found = observe(row[col])
            except ValueError as e:
                found, why = None, str(e)
            else:
                why = "file unavailable"
            if not found:
                unavailable += 1
                add("figure-map:" + ids[n - 2], "gap", "row " + str(n) + ", column " + col + ": " + why)
    if not (unmapped or unavailable or blank):
        add("figure-map", "pass", "{} mapped panels; {} have a figure contract. Map rows are not checked against plotted content.".format(len(ids), len(declared)), n_rows=len(rows))


def reject_duplicate_json_keys(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError("duplicate JSON key: " + k)
        out[k] = v
    return out


def make_result(contract, inputs, checks):
    statuses = [x["status"] for x in checks]
    state = "block" if "block" in statuses else "gap" if "gap" in statuses else "pass"
    return {"schema": RESULT_SCHEMA, "status": state, "exit_code": 2 if state == "block" else 3 if state == "gap" else 0,
            "contract": contract, "inputs": inputs, "checks": checks,
            "message": "Declared file-presence, column-presence, key, count and ratio checks only. Does NOT inspect every actual plotting aesthetic, validate statistical inference, or authenticate producer execution."}


def write_result(result, root, config_rel, dest):
    """Save the result atomically inside the project, refusing to overwrite the contract or any declared input.

    The destination is project-relative, like --config; absolute or escaping paths are refused."""
    dest = resolve_under(root, dest)
    protected = [resolve_under(root, config_rel)]
    protected += [root / item["path"] for item in result["inputs"]]
    try:  # an earlier gap may have skipped observe(), so protect every path the contract names
        stack = [json.loads(protected[0].read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_json_keys)]
    except (OSError, ValueError):
        if dest.exists():
            raise UsageError("--result-json destination exists and the contract cannot be parsed: " + str(dest))
        stack = []
    while stack:
        v = stack.pop()
        if isinstance(v, (dict, list)):
            stack.extend(v.values() if isinstance(v, dict) else v)
        elif isinstance(v, str):
            try:
                protected.append(resolve_under(root, v))
            except ValueError:
                pass
    if dest in [p.resolve() for p in protected]:
        raise UsageError("--result-json destination would overwrite the contract or a declared input: " + str(dest))
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(dest.parent), delete=False) as out:
            temporary = Path(out.name)
            json.dump(result, out, indent=2, sort_keys=True)
            out.write("\n")
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(str(temporary), 0o666 & ~umask)
        os.replace(str(temporary), str(dest))
        temporary = None
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main(argv=None):
    parser = Parser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--config", required=True, help="Project-relative JSON check declaration")
    parser.add_argument("--result-json", help="Save observed result atomically, relative to --root; optional")
    args = parser.parse_args(argv)
    try:
        resolve_under(Path(args.root).resolve(), args.config).open("rb").close()
    except (OSError, ValueError) as e:
        print("usage error: --root/--config not usable: " + str(e), file=sys.stderr)
        return 1
    result = evaluate(args.root, args.config)
    if args.result_json is not None:
        try:
            write_result(result, Path(args.root).resolve(), args.config, args.result_json)
        except (UsageError, ValueError, OSError) as e:
            print("refusing to write result: " + str(e), file=sys.stderr)
            return 1
    print(json.dumps(result, sort_keys=True))
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
