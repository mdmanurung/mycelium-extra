"""Recorded analysis history. Reads only; explicit save is the sole durable writer.

Source readers deliberately report malformed lines instead of using the gate's
permissive log readers, which skip them. Gate parsers still establish plan links.
"""
import copy
import glob
import json
import math
import os
import re
import time
import hashlib

from evidence import digest, identity, relative, SCHEMA as HANDOFF

SCHEMA = "mycelium-extra.analysis-journal.v1"
CHECKPOINT = "mycelium-extra.analysis-checkpoint.v1"


def utc(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        try:
            return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(value))
        except (ValueError, OverflowError, OSError):
            pass
    return None


def contained(root, rel):
    return relative(rel) and os.path.commonpath([os.path.realpath(root),
                                               os.path.realpath(os.path.join(root, rel))]) == os.path.realpath(root)


def note(root, reference):
    path, mark, anchor = reference.partition("#")
    if not contained(root, path) or not path.lower().endswith((".md", ".markdown")) or any(ord(c) < 32 for c in anchor):
        raise ValueError("note must be a contained repository-relative Markdown path with an optional anchor")
    target = os.path.join(root, path)
    try:
        with open(target, "rb") as handle:
            sha = hashlib.sha256(handle.read()).hexdigest()
        status = "available"
    except OSError:
        sha, status = None, "absent"
    return {"reference": path + (mark + anchor if mark else ""), "sha256": sha, "status": status}


def semantic_event(event):
    return {k: v for k, v in event.items() if k not in ("observed_at", "sources", "original_evidence")}


def payload(data):
    """No catalog, nested documents, scan clock, availability or save operation."""
    return {"schema": SCHEMA, "analysis_path": data["analysis_path"], "objective": data["objective"],
            "events": [semantic_event(e) for e in sorted(data["events"], key=lambda e: e["id"])],
            "notes": sorted(data["notes"], key=lambda n: n["reference"]),
            "note_observations": data["note_observations"],
            "limitations": data["limitations"],
            "source_coverage": {k: v for k, v in data["coverage"].items() if k != "checkpoints"}}


def findings_ok(projection):
    rows = projection.get("findings", []) if isinstance(projection, dict) else None
    return isinstance(rows, list) and all(isinstance(f, list) and len(f) >= 2 and all(isinstance(x, str) for x in f[:2]) for f in rows)


def validate_checkpoint(value, rel):
    if (not isinstance(value, dict) or value.get("schema") != CHECKPOINT
            or not isinstance(value.get("payload"), dict) or value["payload"].get("analysis_path") != rel
            or value.get("digest") != digest(value["payload"]) or not isinstance(value.get("saved_at"), str)):
        raise ValueError("invalid checkpoint schema, context or semantic digest")
    body = value["payload"]
    if body.get("schema") != SCHEMA or not isinstance(body.get("events"), list):
        raise ValueError("invalid checkpoint payload")
    if not isinstance(body.get("notes"), list) or not isinstance(body.get("objective"), dict):
        raise ValueError("invalid checkpoint notes or objective")
    for n in body["notes"]:
        if (not isinstance(n, dict) or not isinstance(n.get("reference"), str)
                or not relative(n["reference"].partition("#")[0])):
            raise ValueError("invalid checkpoint note reference")
    if not isinstance(value.get("observation_times", {}), dict) or not isinstance(value.get("source_references", {}), dict):
        raise ValueError("invalid observation metadata")
    if any(not isinstance(paths, list) or not all(isinstance(p, str) and relative(p) for p in paths)
           for paths in value.get("source_references", {}).values()):
        raise ValueError("invalid original source references")
    dates = [value["saved_at"]] + list((value.get("observation_times") or {}).values())
    if not all(d is None or isinstance(d, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", d) for d in dates):
        raise ValueError("invalid observation timestamp")
    for event in body["events"]:
        if (not isinstance(event, dict) or not isinstance(event.get("references"), dict)
                or not isinstance(event.get("detail"), dict) or not isinstance(event.get("summary"), str)
                or not isinstance(event.get("limitations"), list)
                or not all(isinstance(x, str) for x in event["limitations"])
                or not all(isinstance(event.get(k), str) for k in ("kind", "source_identity", "source_digest"))
                or event.get("id") != event_id(rel, event)):
            raise ValueError("invalid checkpoint event identity")
        if event["kind"] == "verification" and not findings_ok(event["detail"].get("projection")):
            raise ValueError("invalid checkpoint verification findings")
    return value


def event_id(rel, event):
    return "journal:" + event["kind"] + ":" + digest([rel, event["source_identity"], event["source_digest"]])


def save(root, data, fault=lambda stage: None):
    """Complete-file create-if-absent under the existing short lock. Never replaces."""
    import stateio
    body = payload(data)
    sha = digest(body)
    rel = data["analysis_path"] + "/journal/checkpoints"
    if not contained(root, rel):
        raise ValueError("checkpoint directory escapes repository")
    folder = os.path.join(root, rel)
    # Reject symlinked descendants even if they resolve inside the repository.
    cursor = root
    for part in rel.split("/"):
        cursor = os.path.join(cursor, part)
        if os.path.islink(cursor):
            raise ValueError("symlinked checkpoint directory")
    with stateio.locked(os.path.join(folder, ".save.lock")):
        path = os.path.join(folder, sha + ".json")
        if os.path.lexists(path):
            if os.path.islink(path):
                raise ValueError("symlinked checkpoint")
            with open(path, encoding="utf-8") as handle:
                return validate_checkpoint(json.load(handle), data["analysis_path"])
        value = {"schema": CHECKPOINT, "digest": sha, "saved_at": utc(time.time()), "payload": body,
                 "source_references": {e["id"]: [p for p in e.get("sources", []) if "/journal/checkpoints/" not in p]
                                       for e in data["events"]},
                 "observation_times": {e["id"]: e.get("observed_at") or data["refreshed_at"] for e in data["events"]}}
        fault("before_publish")
        stateio.write(path, value)
        return value


def collect(root, rel, gate, focus, notes=()):
    now = utc(time.time())
    events, coverage, checkpoints = {}, {}, []
    local = ".mycelium-extra/"
    relations = {}
    verify = gate.load_verify()
    config = gate.load_config(root) if os.path.isfile(os.path.join(root, ".mycelium-extra", "gate.json")) else dict(gate.DEFAULTS)
    limits = ["Only available recorded history is inspected; absence is not evidence of no activity.",
              "Order and equal timestamps establish no causality. File mtime is not an occurrence time.",
              "Checkpoints are observations, not tamper-proof attestations or complete-history certificates.",
              "No scheduler, verifier, analysis script, transcript or network service is queried."]

    def read(path, source, lines=False):
        if not contained(root, path):
            coverage[source] = "malformed"
            return []
        try:
            with open(os.path.join(root, path), encoding="utf-8") as handle:
                chunks = handle.readlines() if lines else [handle.read()]
        except FileNotFoundError:
            coverage.setdefault(source, "absent")
            return []
        except (OSError, UnicodeError):
            coverage[source] = "partial"
            return []
        result, bad = [], False
        for chunk in chunks:
            if not chunk.strip():
                continue
            try:
                value = json.loads(chunk, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("non-finite JSON")))
                if not isinstance(value, dict):
                    raise ValueError("object required")
                result.append(value)
            except (ValueError, TypeError):
                bad = True
        previous = coverage.get(source)
        coverage[source] = "partial" if bad else previous if previous not in (None, "absent", "available") else "available"
        return result

    def paths(pattern, source):
        found = sorted(os.path.relpath(p, root) for p in glob.glob(os.path.join(root, pattern)))
        if not found:
            coverage.setdefault(source, "absent")
        return found

    def add(kind, raw, native, path, summary, ts=None, refs=None, detail=None, limitations=None, attribution="recorded"):
        source_identity = kind + ":" + (native if isinstance(native, str) else digest(native)) if native else kind + ":" + digest(raw)
        e = {"kind": kind, "source_identity": source_identity, "source_digest": identity(raw) if kind == "verification" else digest(raw),
             "summary": summary, "occurred_at": utc(ts), "observed_at": None,
             "timestamp_basis": ({
                 "approval": "approval record approved_at",
                 "instance": "immutable instance approved_at",
                 "attempt": "receipt hook ts; not an attested computation or output-production time",
                 "repin": "re-pin record ts; detection is not the edit time",
                 "focus": "recorded focus episode started_at",
                 "launch": "pre-hook started timestamp; execution and completion not established",
             }.get(kind, "recorded timestamp") if utc(ts) else
                 "saved handoff generation is observation only; assessment time not recorded" if kind == "verification" else
                 "occurrence time not recorded"),
             "references": refs or {}, "detail": detail or {}, "limitations": limitations or [],
             "attribution": attribution, "difference": "recorded", "authorization_relation": "not_reassessed",
             "unknown": "Unrecorded activity and scientific implications are not assessed.",
             "sources": [path], "original_evidence": "available"}
        e["id"] = event_id(rel, e)
        if e["id"] in events:
            events[e["id"]]["original_evidence"] = "available"
            events[e["id"]]["sources"] = sorted(set(events[e["id"]]["sources"] + [path]))
        else:
            events[e["id"]] = e
        return e

    # Approvals retain plan links; instances inherit them only from a known plan.
    for path in paths(local + "approvals/*.json", "approvals"):
        for record in read(path, "approvals"):
            try:
                record = gate.read_approval(os.path.join(root, path))
                if not isinstance(record.get("plan"), str) or not re.fullmatch(r"[0-9a-f]{8}", record.get("hash", "")):
                    raise ValueError("invalid approval")
                if not focus.plan_touches(gate, root, record, rel):
                    continue
                h = record["hash"]
                named = gate.plan_paths_in(root, gate.plan_table(record["plan"], every_cell=True))
                outside = [p for p in named if p.startswith(("analysis/", "nbs/")) and not p.startswith(rel + "/")]
                relations[h] = "multi-analysis" if outside else "plan names analysis"
                add("approval", record, [h, record.get("instance_id")], path, "Plan approved", record.get("approved_at"),
                    {"plan": h, "instance": record.get("instance_id"), "session": record.get("session_id")},
                    {"objective": verify.plan_objective(record["plan"])}, attribution=relations[h])
            except (ValueError, TypeError, KeyError):
                coverage["approvals"] = "partial"

    # Import checkpoints first to recover plan membership and earlier projections in fresh clones.
    for path in paths(rel + "/journal/checkpoints/*.json", "checkpoints"):
        for value in read(path, "checkpoints"):
            try:
                validate_checkpoint(value, rel)
                if os.path.basename(path) != value["digest"] + ".json":
                    raise ValueError("checkpoint filename mismatch")
                checkpoints.append({"digest": value["digest"], "saved_at": value["saved_at"], "path": path,
                                    "event_ids": [e["id"] for e in value["payload"]["events"]],
                                    "source_coverage": value["payload"].get("source_coverage", {})})
                for old in value["payload"]["events"]:
                    e = copy.deepcopy(old)
                    e.update(sources=sorted(set((value.get("source_references") or {}).get(e["id"], []) + [path])), original_evidence="not inspected",
                             observed_at=(value.get("observation_times") or {}).get(e["id"]))
                    if e["references"].get("plan"):
                        relations.setdefault(e["references"]["plan"], e["attribution"])
                    if e["id"] in events:
                        current = events[e["id"]]
                        current["sources"].append(path)
                        dates = [d for d in (current.get("observed_at"), e.get("observed_at")) if d]
                        current["observed_at"] = min(dates) if dates else None
                    else:
                        events[e["id"]] = e
            except (ValueError, KeyError, TypeError):
                coverage["checkpoints"] = "partial"

    # Frozen plans are source documents, including legacy bundles without a handoff.
    for path in paths(rel + "/provenance/plan-*.md", "saved_plans"):
        try:
            h = os.path.basename(path)[5:-3]
            if not re.fullmatch(r"[0-9a-f]{8}", h) or not contained(root, path):
                raise ValueError("invalid saved plan path")
            with open(os.path.join(root, path), encoding="utf-8") as handle:
                text = handle.read()
            relations.setdefault(h, "saved analysis context; ownership not otherwise established")
            add("saved_plan", {"hash": h, "text": text}, h, path, "Frozen plan document saved",
                refs={"plan": h}, detail={"objective": verify.plan_objective(text)},
                limitations=["No approval or production time is inferred from document metadata."],
                attribution=relations[h])
            coverage["saved_plans"] = "available" if coverage.get("saved_plans") != "partial" else "partial"
        except (OSError, UnicodeError, ValueError):
            coverage["saved_plans"] = "partial"

    # Coherent committed handoffs are authoritative saved observations, never recovered here.
    import provenance
    folder = os.path.join(root, rel, "provenance")
    for path in paths(rel + "/provenance/evidence-*.json", "handoffs"):
        for value in read(path, "handoffs"):
            h = value.get("plan_hash")
            try:
                if value.get("schema") != HANDOFF:
                    coverage["handoffs"] = "unsupported"
                    continue
                if (value.get("analysis_path") != rel or value.get("snapshot_digest") != identity(value)
                        or not re.fullmatch(r"[0-9a-f]{8}", h or "")):
                    raise ValueError("invalid handoff")
                if not findings_ok(value):
                    raise ValueError("invalid handoff findings")
                # A reader must not create publication locks or run recovery.
                state = provenance.bundle_state(folder, h)
                if state != "complete":
                    coverage["handoffs"] = "interrupted" if state == "interrupted" else "partial"
                    continue
                relations.setdefault(h, "saved analysis context")
                marker_path = os.path.join(folder, "complete-" + h + ".json")
                with open(marker_path, "rb") as handle:
                    marker_before = handle.read()
                marker = json.loads(marker_before)
                with open(os.path.join(root, path), "rb") as handle:
                    member_bytes = handle.read()
                    member_digest = hashlib.sha256(member_bytes).hexdigest()
                if json.loads(member_bytes) != value:
                    raise ValueError("handoff changed during collection")
                if marker.get("sha256", {}).get(os.path.basename(path)) != member_digest:
                    raise ValueError("handoff not committed by completion")
                if os.path.exists(os.path.join(folder, ".transactions", "pending.json")):
                    coverage["handoffs"] = "interrupted"
                    continue
                with open(marker_path, "rb") as handle:
                    if marker_before != handle.read():
                        raise ValueError("publication changed during collection")
                event = add("verification", value, value["snapshot_digest"], path, "Verification saved",
                    refs={"plan": h, "instance": value.get("approval_instance")},
                    detail={"projection": {k: v for k, v in value.items() if k not in ("generated_at", "producer")}},
                    limitations=value.get("limitations"))
                dates = [d for d in (event.get("observed_at"), value.get("generated_at")) if isinstance(d, str)]
                event["observed_at"] = min(dates) if dates else None
            except (OSError, ValueError, TypeError, KeyError):
                coverage["handoffs"] = "partial"
    if os.path.exists(os.path.join(folder, ".transactions", "pending.json")):
        coverage["handoffs"] = "interrupted"
    if glob.glob(os.path.join(folder, "verify-*.md")) and coverage.get("handoffs") == "absent":
        coverage["handoffs"] = "partial"  # legacy prose is not parsed into a new verdict

    for path in paths(local + "approval-instances/*/*.json", "instances"):
        for record in read(path, "instances"):
            h = record.get("hash")
            if h not in relations:
                continue
            if (not record.get("instance_id") or record.get("schema") != "mycelium-extra.approval-instance.v1"
                    or os.path.basename(path) != str(record["instance_id"]) + ".json"
                    or not verify.load_instance(root, h, record["instance_id"])):
                coverage["instances"] = "partial"
                continue
            add("instance", record, [h, record["instance_id"]], path, "Approval instance recorded", record.get("approved_at"),
                {"plan": h, "instance": record["instance_id"], "session": record.get("session_id")},
                {"prepared": record.get("prepared")}, record.get("limitations"), relations[h])

    receipt_paths = [local + "receipts.jsonl"] + paths(rel + "/provenance/receipts-*.jsonl", "saved_receipts")
    for path in receipt_paths:
        source = "receipts" if path.startswith(local) else "saved_receipts"
        for record in read(path, source, lines=True):
            if (record.get("schema") not in (None, "mycelium-extra.receipt.v1")
                    or not isinstance(record.get("command", ""), str)
                    or not isinstance(record.get("paths", []), list)
                    or not all(isinstance(p, str) for p in record.get("paths", []))):
                coverage[source] = "partial"
                continue
            plans = record.get("plans")
            if not isinstance(plans, list) or not all(isinstance(h, str) for h in plans):
                coverage[source] = "partial"
                continue
            matched = sorted(set(plans) & set(relations))
            focused = record.get("focus_folder") == rel
            if not matched and not focused:
                continue  # shared script alone is not ownership
            if not matched:
                attribution = "focus only; plan attribution unknown"
            elif any(relations[h] == "multi-analysis" for h in matched):
                attribution = "multi-analysis"
            elif len(plans) > 1:
                attribution = "multiple plan attribution; analysis context recorded"
            else:
                attribution = relations[matched[0]]
            # not_a_run is an annotation added on export, not a conflicting native receipt.
            raw = {k: v for k, v in record.items() if k != "not_a_run"}
            run = verify.is_run(root, record, config["gated_commands"])
            status = record.get("exit_status")
            submission = record.get("kind") == "sbatch"
            outcome = "Path passed to other code; not a run" if not run else "submission recorded; job completion not recorded in receipt" if submission else (
                "exit 0 recorded" if status == 0 and type(status) is int else
                "failed attempt" if type(status) is int and status != 0 else "completion unknown")
            add("attempt", raw, record.get("attempt_id"), path, outcome, record.get("ts"),
                {"plan": matched[0] if len(matched) == 1 else None, "plans": plans,
                 "instance": record.get("approval_instance"), "attempt": record.get("attempt_id"),
                 "session": record.get("session_id")},
                {"exit_status": status, "kind": record.get("kind"), "launch_match": record.get("launch_match"),
                 "started_at": utc(record.get("started")), "submission": submission,
                 "not_a_run": not run},
                ["Submission is not job completion; inspect any saved verification for a later assessment."] if submission else [], attribution)

    for path in paths(local + "repins/*.jsonl", "repins"):
        h = os.path.basename(path)[:-6]
        if h not in relations:
            continue
        for r in read(path, "repins", lines=True):
            if not isinstance(r.get("rel"), str) or not gate.valid_fingerprint(r.get("pin")):
                coverage["repins"] = "partial"
                continue
            add("repin", r, None, path, "Script re-pinned", r.get("ts"), {"plan": h},
                {"path": r["rel"] if relative(r["rel"]) else None, "fingerprint": r["pin"]},
                ["Re-pinning is not scientific validation."], relations[h])

    for path in paths(local + "focus/*.json", "focus"):
        records = read(path, "focus")
        for record in records:
            try:
                checked = focus.read(root, record.get("session_id"))
                for e in checked["episodes"]:
                    if e["analysis_path"] == rel:
                        add("focus", e, e["focus_id"], path, "Session focus recorded", e["started_at"],
                            {"session": record["session_id"], "plan": e.get("original_plan_hash")},
                            {"ended_at": utc(e.get("ended_at"))})
            except (ValueError, TypeError, KeyError, focus.FocusError):
                coverage["focus"] = "partial"

    # Outstanding launches are separate observations, not completed receipts.
    for pattern in (local + "launches/*.json", local + "launches/abandoned/*.json"):
        for path in paths(pattern, "launches"):
            for r in read(path, "launches"):
                candidates = r.get("attempts") if r.get("ambiguous") else [r]
                for a in candidates or []:
                    if not isinstance(a, dict):
                        coverage["launches"] = "partial"
                        continue
                    runs = a.get("runs") or {}
                    if not isinstance(runs, dict) or not all(isinstance(rows, list) for rows in runs.values()):
                        coverage["launches"] = "partial"
                        continue
                    entries = [r for rows in runs.values() for r in rows if isinstance(r, dict)]
                    text_plans = {h for run in entries for h in (run.get("plans") if isinstance(run.get("plans"), list) else []) if isinstance(h, str)}
                    if a.get("focus_folder") != rel and not text_plans.intersection(relations):
                        continue
                    matched = sorted(text_plans.intersection(relations))
                    add("launch", a, a.get("attempt_id"), path, "Launch without a completion record", a.get("started"),
                        {"attempt": a.get("attempt_id"), "plans": sorted(text_plans),
                         "plan": matched[0] if len(matched) == 1 else None},
                        limitations=["No completion receipt available in this source observation."],
                        attribution="plan names analysis" if matched else "focus only; plan attribution unknown")

    # Resolve embedded-original availability by current source digest, never by a path's mere existence.
    for e in events.values():
        if e["original_evidence"] == "not inspected":
            e["original_evidence"] = "full original evidence unavailable in inspected sources; checkpoint projection retained"
    groups = {}
    for e in events.values():
        groups.setdefault(e["source_identity"], []).append(e)
    for group in groups.values():
        if len(group) > 1:
            for e in group:
                e["limitations"] = sorted(set(e["limitations"] + ["Conflicting or changed variants of this logical source record are retained; supersession is not inferred."]))

    objective, doc = focus.objective_of(root, rel)
    if not objective:
        for cp in sorted(checkpoints, key=lambda c: c["saved_at"], reverse=True):
            # Compact objective comes from an imported checkpoint, not inferred plan prose.
            values = read(cp["path"], "checkpoints")
            if values and values[0]["payload"].get("objective", {}).get("text"):
                objective = values[0]["payload"]["objective"]["text"]
                break
    attached = {n["reference"]: n for n in (note(root, n) for n in notes)}
    for cp in checkpoints:
        for value in read(cp["path"], "checkpoints"):
            for n in value["payload"].get("notes", []):
                attached.setdefault(n["reference"], n)
    notes_now = []
    for n in attached.values():
        current = note(root, n["reference"])
        notes_now.append(dict(n, current_status=current["status"], current_sha256=current["sha256"],
                              changed=current["sha256"] != n["sha256"]))
    coverage.update(transcripts="not inspected", scheduler="not inspected", gate_errors="not inspected")
    data = {"schema": SCHEMA, "analysis_path": rel, "refreshed_at": now,
            "objective": {"text": objective, "source": doc},
            "events": sorted(events.values(), key=lambda e: (e["occurred_at"] or "", e["id"])),
            "coverage": coverage, "checkpoints": sorted(checkpoints, key=lambda c: (c["saved_at"], c["digest"])),
            "notes": sorted(attached.values(), key=lambda n: n["reference"]), "note_observations": notes_now,
            "limitations": limits, "collection": {"loaded": len(events), "omitted": 0, "limit": None}}
    data["snapshot_digest"] = digest(payload(data))
    return data
