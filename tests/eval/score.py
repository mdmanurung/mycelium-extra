#!/usr/bin/env python3
"""Aggregate saved HUMAN adjudications of evaluation runs into protection and burden counts.

Usage: score.py ADJUDICATIONS.json [ADJUDICATIONS.json ...] [--json]

Deterministic and offline: reads scenarios.json and rubric.json beside this file plus the given
adjudication files; never reads answer_keys.json, never calls a model, and never asks an agent to
judge itself. A file that does not match the schema (missing, unknown or mistyped fields, unknown
scenario ids, inconsistent combinations) is refused with every error listed and no scores. Each file
is one run (one host/model/version) and is scored alone, per split; development and held-out cases
are never pooled. Output is counts and plain ratios, with no composite score.

Stdlib only, Python 3.6 grammar.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = "mx-eval-adjudications/1"
TOP = ["schema", "synthetic", "run", "records"]
BANNER = "*** SYNTHETIC DATA: example for tests only; these numbers measure nothing ***"


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def check_value(name, spec, value, rubric, errors, where):
    kind = spec["type"]
    if kind == "enum":
        if value not in spec["values"]:
            errors.append("%s: %s must be one of %s, got %r" % (where, name, spec["values"], value))
    elif kind == "count":
        if not is_int(value) or value < spec.get("min", 0):
            errors.append("%s: %s must be an integer >= %d, got %r" % (where, name, spec.get("min", 0), value))
    elif kind == "number_or_null":
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0):
            errors.append("%s: %s must be null or a number >= 0, got %r" % (where, name, value))
    elif kind == "bool":
        if not isinstance(value, bool):
            errors.append("%s: %s must be true or false, got %r" % (where, name, value))
    elif kind == "string":
        if not isinstance(value, str):
            errors.append("%s: %s must be a string" % (where, name))
    elif kind == "string_list":
        if not isinstance(value, list) or not value or not all(isinstance(x, str) and x.strip() for x in value):
            errors.append("%s: %s must be a non-empty list of non-empty strings" % (where, name))
    elif kind == "enum_map":
        keys = rubric[spec["keys"]]
        if not isinstance(value, dict):
            errors.append("%s: %s must be an object" % (where, name))
            return
        for k in sorted(set(value) - set(keys)):
            errors.append("%s: %s has unknown key %r" % (where, name, k))
        for k in keys:
            if k not in value:
                errors.append("%s: %s is missing %r" % (where, name, k))
            elif value[k] not in spec["values"]:
                errors.append("%s: %s.%s must be one of %s, got %r" % (where, name, k, spec["values"], value[k]))
    # "scenario_id" is checked against the scenario table by the caller.


def validate(doc, scenarios, rubric):
    """Every schema problem in an adjudication document, as a list of strings (empty = valid)."""
    errors = []
    if not isinstance(doc, dict):
        return ["the file must contain a JSON object"]
    for k in sorted(set(doc) - set(TOP)):
        errors.append("unknown top-level field %r" % k)
    missing = [k for k in TOP if k not in doc]
    for k in missing:
        errors.append("missing top-level field %r" % k)
    if missing:
        return errors
    if doc["schema"] != SCHEMA:
        errors.append("schema must be %r, got %r" % (SCHEMA, doc["schema"]))
    if not isinstance(doc["synthetic"], bool):
        errors.append("synthetic must be true or false")
    run = doc["run"]
    if not isinstance(run, dict):
        errors.append("run must be an object")
    else:
        for k in sorted(set(run) - set(rubric["run_fields"])):
            errors.append("run: unknown field %r" % k)
        for k in rubric["run_fields"]:
            if not isinstance(run.get(k), str) or not run[k].strip():
                errors.append("run: %s must be a non-empty string" % k)
    if not isinstance(doc["records"], list) or not doc["records"]:
        return errors + ["records must be a non-empty list"]
    fields = rubric["record_fields"]
    by_id = dict((s["id"], s) for s in scenarios)
    seen = set()
    for i, rec in enumerate(doc["records"]):
        where = "record %d" % i
        if not isinstance(rec, dict):
            errors.append("%s: must be an object" % where)
            continue
        for k in sorted(set(rec) - set(fields)):
            errors.append("%s: unknown field %r" % (where, k))
        missing = [k for k in fields if k not in rec]
        for k in missing:
            errors.append("%s: missing field %r" % (where, k))
        if missing:
            continue
        before = len(errors)
        for name, spec in fields.items():
            check_value(name, spec, rec[name], rubric, errors, where)
        sid = rec["scenario_id"]
        scenario = by_id.get(sid)
        if scenario is None:
            errors.append("%s: unknown scenario_id %r" % (where, sid))
        if len(errors) > before or scenario is None:
            continue
        key = (sid, rec["trial"])
        if key in seen:
            errors.append("%s: duplicate scenario_id %s trial %d" % (where, sid, rec["trial"]))
        seen.add(key)
        defect = scenario["kind"] == "defect"
        if defect == (rec["detection"] == "not_applicable"):
            errors.append("%s: detection=%s is wrong for a %s scenario" % (where, rec["detection"], scenario["kind"]))
        dims = set(rec["false_clean"].values())
        if defect and "not_applicable" in dims:
            errors.append("%s: false_clean may not be not_applicable for a defect scenario" % where)
        if not defect and dims != {"not_applicable"}:
            errors.append("%s: false_clean must be not_applicable in every dimension for a control" % where)
        if rec["detection"] == "detected" and rec["generic_gaps_only"]:
            errors.append("%s: detected is incompatible with generic_gaps_only (a generic gap is not detection)" % where)
        if rec["choices_missed"] > rec["choices_expected"]:
            errors.append("%s: choices_missed exceeds choices_expected" % where)
        if rec["evidence_items_cited"] > rec["evidence_items_total"]:
            errors.append("%s: evidence_items_cited exceeds evidence_items_total" % where)
        if scenario["recovery"] == (rec["recovery_fidelity"] == "not_applicable"):
            errors.append("%s: recovery_fidelity=%s is wrong for a scenario with recovery=%s"
                          % (where, rec["recovery_fidelity"], str(scenario["recovery"]).lower()))
    return errors


def ratio(num, den):
    return {"n": num, "of": den, "ratio": round(num / den, 3) if den else None}


def aggregate(doc, scenarios, rubric):
    """Counts per split from a VALID document. Protection (defect scenarios) and burden are reported together."""
    by_id = dict((s["id"], s) for s in scenarios)
    dims = rubric["assurance_dimensions"]
    out = {}
    for split in sorted(set(s["split"] for s in scenarios)):
        recs = [r for r in doc["records"] if by_id[r["scenario_id"]]["split"] == split]
        defects = [r for r in recs if by_id[r["scenario_id"]]["kind"] == "defect"]
        controls = [r for r in recs if by_id[r["scenario_id"]]["kind"] == "control"]
        in_split = [s["id"] for s in scenarios if s["split"] == split]
        adjudicated = sorted(set(r["scenario_id"] for r in recs))
        families = {}
        for r in defects:
            fam = families.setdefault(by_id[r["scenario_id"]]["family"], {"detected": 0, "unresolved": 0, "missed": 0})
            fam[r["detection"]] += 1
        minutes = [r["active_review_minutes"] for r in recs if r["active_review_minutes"] is not None]
        recov = [r for r in recs if r["recovery_fidelity"] != "not_applicable"]
        useful = lambda rs: sum(r["useful_completion"] != "not_useful" for r in rs)
        out[split] = {
            "coverage": {"scenarios_adjudicated": len(adjudicated), "scenarios_in_split": len(in_split),
                         "not_adjudicated": sorted(set(in_split) - set(adjudicated)), "records": len(recs)},
            "protection": {
                "defect_records": len(defects),
                "false_clean_any_dimension": ratio(sum("false_clean" in r["false_clean"].values() for r in defects), len(defects)),
                "false_clean_by_dimension": dict(
                    (d, ratio(sum(r["false_clean"][d] == "false_clean" for r in defects),
                              sum(r["false_clean"][d] in ("false_clean", "not_false_clean") for r in defects)))
                    for d in dims),
                "detected": ratio(sum(r["detection"] == "detected" for r in defects), len(defects)),
                "unresolved": ratio(sum(r["detection"] == "unresolved" for r in defects), len(defects)),
                "missed": ratio(sum(r["detection"] == "missed" for r in defects), len(defects)),
                "by_family": families,
                "choices_missed": ratio(sum(r["choices_missed"] for r in defects), sum(r["choices_expected"] for r in defects)),
                "invented_facts": sum(r["invented_facts"] for r in recs),
                "unsourced_assumptions": sum(r["unsourced_assumptions"] for r in recs),
                "unknown_evidence_treated_as_known": sum(r["unknown_evidence"] == "treated_as_known" for r in recs),
            },
            "burden": {
                "unnecessary_questions": sum(r["unnecessary_questions"] for r in recs),
                "unnecessary_reapprovals": sum(r["unnecessary_reapprovals"] for r in recs),
                "useful_completion_defect": ratio(useful(defects), len(defects)),
                "useful_completion_control": ratio(useful(controls), len(controls)),
                "control_generic_gaps_only": ratio(sum(r["generic_gaps_only"] for r in controls), len(controls)),
                "defect_generic_gaps_only": ratio(sum(r["generic_gaps_only"] for r in defects), len(defects)),
                "active_review_minutes": {"total": sum(minutes), "records_observed": len(minutes), "records": len(recs)},
                "evidence_coverage": ratio(sum(r["evidence_items_cited"] for r in recs), sum(r["evidence_items_total"] for r in recs)),
                "recovery_fidelity": ratio(sum(r["recovery_fidelity"] == "faithful" for r in recov), len(recov)),
            },
        }
    return out


def fmt(value, indent=0):
    pad = "  " * indent
    lines = []
    for k in sorted(value):
        v = value[k]
        if isinstance(v, dict) and set(v) == {"n", "of", "ratio"}:
            lines.append("%s%s: %d/%d%s" % (pad, k, v["n"], v["of"], "" if v["ratio"] is None else " (%.3f)" % v["ratio"]))
        elif isinstance(v, dict):
            lines.append("%s%s:" % (pad, k))
            lines.extend(fmt(v, indent + 1))
        else:
            lines.append("%s%s: %s" % (pad, k, v if not isinstance(v, list) else ", ".join(v) or "none"))
    return lines


def main(argv):
    as_json = "--json" in argv
    paths = [a for a in argv if a != "--json"]
    if not paths:
        print(__doc__.strip().split("\n")[2])
        return 2
    scenarios = load(os.path.join(HERE, "scenarios.json"))["scenarios"]
    rubric = load(os.path.join(HERE, "rubric.json"))
    report, bad, synthetic = {}, False, False
    for path in paths:
        try:
            doc = load(path)
        except (OSError, ValueError) as err:
            print("%s: cannot read: %s" % (path, err))
            bad = True
            continue
        errors = validate(doc, scenarios, rubric)
        if errors:
            print("%s: REFUSED, %d schema error(s)" % (path, len(errors)))
            for e in errors:
                print("  - " + e)
            bad = True
            continue
        synthetic = synthetic or doc["synthetic"]
        report[path] = {"synthetic": doc["synthetic"], "run": doc["run"], "splits": aggregate(doc, scenarios, rubric)}
    if synthetic:
        print(BANNER)
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for path in sorted(report):
            print("== %s%s" % (path, "  [SYNTHETIC]" if report[path]["synthetic"] else ""))
            print("run: " + ", ".join("%s=%s" % (k, report[path]["run"][k]) for k in sorted(report[path]["run"])))
            for split in sorted(report[path]["splits"]):
                print("-- split: " + split)
                print("\n".join(fmt(report[path]["splits"][split], 1)))
    if synthetic:
        print(BANNER)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
