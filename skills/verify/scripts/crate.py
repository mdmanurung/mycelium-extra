"""Process Run RO-Crate export for one verified plan (stdlib only).

`build` turns the saved provenance bundle of a plan into the JSON-LD of an RO-Crate that follows the
Process Run Crate profile. `write` saves it as <analysis>/provenance/crate-<hash>/ro-crate-metadata.json.
Nothing here re-runs, re-hashes or re-grades anything: every hash and every producer comes from the bundle
(`verify write`) and from the plan's frozen approval instance. The output is deterministic: the same bundle
gives the same bytes.

Pinned from the published specifications (read 2026-11-13, see references/crate.md):
RO-Crate 1.3 and Process Run Crate 0.6.
"""

import csv
import datetime
import json
import os
import re
import urllib.parse

CRATE_SPEC = "https://w3id.org/ro/crate/1.3"
CRATE_CONTEXT = "https://w3id.org/ro/crate/1.3/context"
WFRUN_CONTEXT = "https://w3id.org/ro/terms/workflow-run/context"
PROCESS_PROFILE = "https://w3id.org/ro/wfrun/process/0.6"
MX = "urn:mycelium-extra:terms:"  # local terms; the context maps `mx:` to it
SCHEMA = "mycelium-extra.run-crate.v1"


class CrateError(Exception):
    pass


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def _types(entity):
    kind = entity.get("@type")
    return kind if isinstance(kind, list) else [kind]


def _iso(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _link(root, crate_dir, repo_path):
    """The id of a file the crate describes: its path from the crate folder, percent-encoded."""
    rel = os.path.relpath(os.path.join(root, repo_path), crate_dir).replace(os.sep, "/")
    return urllib.parse.quote(rel, safe="/-._~")


def _pins(root, digest, instance):
    """(inputs, scripts, source): the pins of the freeze the bundle was written for, else the approval's own."""
    state = os.path.join(root, ".mycelium-extra")
    record = None
    if instance and re.fullmatch(r"[0-9a-f]{16}", instance):
        record = _read_json(os.path.join(state, "approval-instances", digest, instance + ".json"))
    source = "approval instance " + instance if record else None
    if not isinstance(record, dict):
        record = _read_json(os.path.join(state, "approvals", digest + ".json"))
        source = "approvals/{}.json".format(digest) if isinstance(record, dict) else None
    if not isinstance(record, dict):
        return {}, {}, None
    return record.get("pins") or {}, record.get("scripts") or {}, source


def _published(folder, digest):
    """The date `verify write` saved the bundle, from the index row in its completion marker."""
    marker = _read_json(os.path.join(folder, "complete-{}.json".format(digest)))
    row = (marker or {}).get("index_row", "")
    found = re.findall(r"\|\s*(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}\s*(?=\|)", row)
    if len(found) < 2:
        raise CrateError("the completion marker of plan {} has no write date".format(digest))
    return found[1]  # the row reads: plan | approved | verified | ...


def _fingerprint(entity, pin):
    """Add what a pin or output record says about a file's identity; say plainly when it says little."""
    if not isinstance(pin, dict):
        entity["mx:fingerprint"] = "not recorded"
    elif pin.get("sha256"):
        entity["sha256"] = pin["sha256"]
        entity["mx:fingerprint"] = "sha256"
    elif pin.get("missing"):
        entity["mx:fingerprint"] = "missing when recorded"
    elif pin.get("folder"):
        entity["mx:fingerprint"] = "folder listing"
        entity["mx:listingSha256"] = pin.get("listing_sha256")
        entity["mx:files"] = pin.get("files")
    elif pin.get("skipped"):
        entity["mx:fingerprint"] = "not pinned: " + str(pin["skipped"])
    else:
        entity["mx:fingerprint"] = "size and time only"
    if isinstance(pin, dict) and isinstance(pin.get("size"), int) and not pin.get("folder"):
        entity["contentSize"] = str(pin["size"])
    return entity


def _read_outputs(folder, digest):
    with open(os.path.join(folder, "outputs-{}.tsv".format(digest)), encoding="utf-8", errors="replace",
              newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _read_receipts(folder, digest):
    found = []
    with open(os.path.join(folder, "receipts-{}.jsonl".format(digest)), encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict):
                found.append(value)
    return found


def build(root, folder, digest, version="unknown", crate_dir=None):
    """The crate (a dict) for the bundle at `folder` (an analysis folder's provenance/). Paths in the crate
    are relative to `crate_dir`, which defaults to folder/crate-<digest>."""
    crate_dir = crate_dir or os.path.join(folder, "crate-" + digest)
    outputs = _read_outputs(folder, digest)
    receipts = _read_receipts(folder, digest)
    instance = next((r.get("approval_instance") for r in outputs if r.get("approval_instance")
                     not in (None, "", "legacy")), None)
    input_pins, script_pins, pin_source = _pins(root, digest, instance)
    gaps = []
    if pin_source is None:
        gaps.append("No approval record was found, so no script or input hash is recorded.")

    entities = {}

    def add(entity):
        entities[entity["@id"]] = entity
        return {"@id": entity["@id"]}

    # scripts and inputs, from the frozen pins
    script_ref = {}
    for path in sorted(script_pins):
        entity = {"@id": _link(root, crate_dir, path), "@type": ["File", "SoftwareSourceCode"],
                  "name": os.path.basename(path), "mx:repositoryPath": path}
        script_ref[path] = add(_fingerprint(entity, script_pins[path]))
    input_ref = {}
    for path in sorted(input_pins):
        pin = input_pins[path]
        kind = "Dataset" if isinstance(pin, dict) and pin.get("folder") else "File"
        entity = {"@id": _link(root, crate_dir, path) + ("/" if kind == "Dataset" else ""),
                  "@type": kind, "name": os.path.basename(path.rstrip("/")), "mx:repositoryPath": path}
        input_ref[path] = add(_fingerprint(entity, pin))

    # one action per script per matched run of this plan
    runs = []
    for receipt in receipts:
        if (digest not in (receipt.get("plans") or []) or receipt.get("launch_match") != "matched"
                or receipt.get("not_a_run") or receipt.get("explore")):
            continue
        for path in receipt.get("paths") or []:
            if path in script_ref:
                runs.append((receipt.get("started") or receipt.get("ts") or 0, str(receipt.get("attempt_id")), path,
                             receipt))
    runs.sort(key=lambda r: (r[0], r[1], r[2]))
    actions, by_attempt = [], {}
    for number, (start, attempt, path, receipt) in enumerate(runs, 1):
        action = {"@id": "#run-{:03d}-{}".format(number, re.sub(r"[^0-9A-Za-z]+", "", attempt)[:12] or "x"),
                  "@type": "CreateAction", "name": "Run of {}".format(os.path.basename(path)),
                  "instrument": script_ref[path], "startTime": _iso(start),
                  "mx:attemptId": receipt.get("attempt_id"), "result": []}  # no command: it can carry secrets
        if receipt.get("ts"):
            action["endTime"] = _iso(receipt["ts"])
        if receipt.get("exit_status") == 0:
            action["actionStatus"] = "http://schema.org/CompletedActionStatus"
        elif receipt.get("exit_status") is not None:
            action["actionStatus"] = "http://schema.org/FailedActionStatus"
            action["mx:exitStatus"] = receipt["exit_status"]
        action["object"] = [input_ref[p] for p in sorted(input_ref)]
        actions.append(action)
        by_attempt.setdefault(str(receipt.get("attempt_id")), []).append((path, action))

    # outputs: linked to the producing action when the record names one, else an explicit gap
    unresolved = 0
    for row in outputs:
        path = row["path"]
        entity = {"@id": _link(root, crate_dir, path), "@type": "File", "name": os.path.basename(path),
                  "mx:repositoryPath": path, "dateCreated": row.get("written") or None,
                  "mx:evidenceMethod": row.get("evidence_method"), "mx:strength": row.get("strength")}
        entity = {k: v for k, v in entity.items() if v not in (None, "")}
        pin = {}
        if row.get("size", "") != "":
            pin["size"] = int(row["size"])
        if row.get("sha256"):
            pin["sha256"] = row["sha256"]
        _fingerprint(entity, pin)
        if not pin.get("sha256"):  # say how weak the identity is, as the bundle's own column does
            entity["mx:fingerprint"] = row.get("fingerprint") or "not recorded"
        owners = by_attempt.get(row.get("producer_attempt") or "", [])
        if row.get("strength") == "supported" and owners:
            owner = next((a for p, a in owners if p in (row.get("written_by") or "")), owners[0][1])
            owner["result"].append({"@id": entity["@id"]})
        else:
            unresolved += 1
            entity["mx:producerAttribution"] = ("candidate" if row.get("strength") == "candidate"
                                                else "unresolved")
            entity["mx:producerGap"] = ("No run is named as the producer of this file; the evidence is {} "
                                        "({}).".format(row.get("evidence_method") or "none",
                                                       row.get("strength") or "unresolved"))
        add(entity)
    if unresolved:
        gaps.append("{} output file(s) have no established producer; each is marked mx:producerAttribution."
                    .format(unresolved))
    if not actions:
        gaps.append("No matched run of this plan names a pinned script, so the crate has no run action.")
    for action in actions:
        action["result"] = sorted(action["result"], key=lambda r: r["@id"])
        if not action["result"]:
            del action["result"]
        add(action)

    # the bundle's own records, so the crate points at the evidence it came from
    members = []
    for name in ("plan-{}.md", "receipts-{}.jsonl", "outputs-{}.tsv", "evidence-{}.json"):
        name = name.format(digest)
        full = os.path.join(folder, name)
        if os.path.isfile(full):
            record = {"@id": _link(root, crate_dir, os.path.relpath(full, root)), "@type": "File", "name": name}
            marker = _read_json(os.path.join(folder, "complete-{}.json".format(digest))) or {}
            sha = (marker.get("sha256") or {}).get(name)
            if sha:
                record["sha256"] = sha
            members.append(add(record))

    for ref, name, version_text in ((CRATE_SPEC, "RO-Crate", "1.3"), (PROCESS_PROFILE, "Process Run Crate", "0.6")):
        add({"@id": ref, "@type": "CreativeWork", "name": name, "version": version_text})
    tool = add({"@id": "#mycelium-extra", "@type": "SoftwareApplication", "name": "mycelium-extra",
                "softwareVersion": version})

    graph_ids = sorted(entities)
    parts = [{"@id": i} for i in graph_ids if "CreateAction" not in _types(entities[i])
             and "SoftwareApplication" not in _types(entities[i]) and "CreativeWork" not in _types(entities[i])]
    root_entity = {"@id": "./", "@type": "Dataset",
                   "name": "Run record of plan {}".format(digest),
                   "description": "Process Run Crate written by mycelium-extra from the saved verify bundle of plan "
                                  "{}. It records what the approval gate saw, with the recorded hashes; it does not "
                                  "judge whether the analysis is right. File ids are paths from this folder; the "
                                  "crate describes files beside it and does not copy them.".format(digest),
                   "datePublished": _published(folder, digest), "identifier": digest,
                   "conformsTo": {"@id": PROCESS_PROFILE}, "hasPart": parts,
                   "mentions": [{"@id": a["@id"]} for a in sorted(actions, key=lambda a: a["@id"])],
                   "mx:generatedBy": tool, "mx:schema": SCHEMA}
    if gaps:
        root_entity["mx:gaps"] = gaps
    descriptor = {"@id": "ro-crate-metadata.json", "@type": "CreativeWork", "about": {"@id": "./"},
                  "conformsTo": {"@id": CRATE_SPEC}}
    others = [entities[i] for i in graph_ids]
    return {"@context": [CRATE_CONTEXT, WFRUN_CONTEXT, {"mx": MX}],
            "@graph": [descriptor, root_entity] + others}


def render(crate):
    return json.dumps(crate, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write(root, analysis_dir, digest, version="unknown"):
    """Save the crate and return its path relative to `root`. Needs a complete bundle."""
    import provenance
    folder = os.path.join(root, analysis_dir, "provenance")
    state = provenance.bundle_state(folder, digest)
    if state != "complete":
        raise CrateError("the bundle for plan {} in {} is {}; run `verify write {}` first".format(
            digest, os.path.relpath(folder, root), state, digest))
    import stateio
    target = os.path.join(folder, "crate-" + digest, "ro-crate-metadata.json")
    stateio.atomic(target, render(build(root, folder, digest, version)))
    return os.path.relpath(target, root)
