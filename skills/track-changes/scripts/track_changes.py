#!/usr/bin/env python3
"""track-changes: a read-only view of how one analysis moved away from its approved intent.

    sh hooks/py.sh - --plugin-root <plugin> [--repo DIR] [--analysis analysis/X] [--original HASH] [--current HASH]
        [--transcript FILE] [--json] [--no-write] < track_changes.py

Reads approvals, approval instances, the re-pin journal, kept script snapshots, receipts, the focus records and
(optionally) a Claude Code transcript. Writes only `.mycelium-extra/track-changes/<analysis>/`: snapshot.json,
brief.md, report.html. Nothing here approves, freezes, runs, pins or re-grades anything; it never calls
`freeze_state`, `keep_snapshot`, `verify report`, or any helper that writes gate state. What it did not observe
is said so: no warning is not evidence of no drift.
"""

import argparse
import calendar
import hashlib
import importlib.util
import json
import os
import re
import sys
import time

SCHEMA = "mycelium-extra.track-changes.v1"
CAP_ITEMS, CAP_PLAN_ITEMS, CAP_RECEIPTS, CAP_TIMELINE = 80, 25, 40, 200
CAP_DIFF, CAP_DIFF_TOTAL = 40, 300
CAP_TRANSCRIPT_BYTES, CAP_TRANSCRIPT_LINES = 20 * 1024 * 1024, 300000
SECRET = re.compile(
    r"(?i)((?:api[_-]?key|secret|token|passw(?:or)?d|credential|auth)[\w-]*\s*[:=]\s*\S+"
    r"|\bAKIA[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9]{20,}\b|\bsk-[A-Za-z0-9_-]{20,}\b|\bxox[abp]-[A-Za-z0-9-]{10,}\b"
    r"|-----BEGIN[ A-Z]*PRIVATE KEY-----)")
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")


class Stop(Exception):
    """A refusal to produce a report; the message says what to pass instead."""


def load(plugin_root):
    hooks = os.path.join(plugin_root, "hooks")
    sys.dont_write_bytecode = True
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    import gate
    import focus
    return gate, focus, gate.load_verify()


def stamp(ts, fmt="%m-%d %H:%M"):
    return time.strftime(fmt, time.localtime(ts))


def iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def ident(prefix, *parts):
    return prefix + "-" + hashlib.sha256("\x1f".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:8]


def short(text, limit=90):
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text if len(text) <= limit else text[:limit - 1] + "…"


class Redactor:
    def __init__(self):
        self.count = 0

    def __call__(self, text):
        text, n = SECRET.subn("[redacted]", text)
        self.count += n
        return text


class Snapshot:
    def __init__(self):
        self.items, self.evidence, self.timeline, self.limitations = [], {}, [], []

    def evid(self, source, ref, detail="", ts=None):
        key = ident("E", source, ref)
        self.evidence.setdefault(key, {"id": key, "source": source, "ref": ref, "detail": detail, "ts": ts})
        return key

    def event(self, ts, kind, text, ref=None):
        if ts:
            self.timeline.append({"ts": ts, "when": stamp(ts), "kind": kind, "text": short(text, 160), "ref": ref})

    def item(self, kind, key, title, bucket, **fields):
        item = {"id": ident(kind[0].upper(), kind, key), "kind": kind, "title": short(title, 120), "bucket": bucket,
                "file": "", "difference": "observed", "focus_relation": "within_path",
                "semantic_relation": "unassessed", "authorization_relation": "not_applicable",
                "historical": "not_applicable", "consequence": "not_assessed", "attribution": "not_applicable",
                "currency": "not_checked", "summary": "", "observed": "", "potential": "", "unknown": "",
                "baseline": "", "current": "", "authorization": "", "context": "", "next": [], "evidence": [],
                "diff": [], "limitations": []}
        item.update(fields)
        self.items.append(item)
        return item


def read_json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def open_focuses(root, focus):
    """[(session_id, open episode)] over every session record that parses; a bad record is skipped."""
    folder = os.path.join(root, ".mycelium-extra", "focus")
    found = []
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        record = read_json(os.path.join(folder, name))
        session = record.get("session_id") if isinstance(record, dict) else None
        try:
            episode = focus.open_episode(focus.read(root, session)) if isinstance(session, str) else None
        except focus.FocusError:
            continue
        if episode:
            found.append((session, episode))
    return found


def first_instance(root, digest):
    """The earliest approval instance of a plan: what its first approval froze (None for a legacy approval)."""
    folder = os.path.join(root, ".mycelium-extra", "approval-instances", digest)
    found = [r for r in (read_json(os.path.join(folder, n)) for n in sorted(os.listdir(folder)) if n.endswith(".json"))
             if isinstance(r, dict)] if os.path.isdir(folder) else []
    return min(found, key=lambda r: r.get("approved_at", 0)) if found else None


def choose_baselines(gate, focus, root, rel, episode, args, approvals, snap):
    candidates = [r for r in approvals or [] if focus.plan_touches(gate, root, r, rel)]  # newest first
    by_hash = {r["hash"]: r for r in approvals or []}
    names = [r["hash"] for r in candidates]
    wanted = args.original or (episode or {}).get("original_plan_hash")
    if wanted:
        if wanted not in by_hash:
            raise Stop("no approved plan {}. Pass --original with a plan that exists.".format(wanted))
        original, relation = by_hash[wanted], "explicit"
    elif len(candidates) == 1:
        original, relation = candidates[0], "single_candidate"
    elif not candidates:
        original, relation = None, "none"
    else:
        raise Stop("{} approved plans name paths inside {} ({}); which one states the original intent? Pass "
                   "--original <hash>. Nothing is guessed from dates.".format(len(candidates), rel, ", ".join(names)))
    if args.current:
        if args.current not in by_hash:
            raise Stop("no approved plan {}. Pass --current with a plan that exists.".format(args.current))
        current = by_hash[args.current]
    else:
        current = candidates[0] if candidates else None
    if relation == "none":
        snap.limitations.append("no approved plan names a path inside {}: there is no intent baseline".format(rel))
    return original, current, relation


def plan_items(gate, verify, snap, original, current, redact):
    if not original or not current or original["hash"] == current["hash"]:
        return
    ev = snap.evid("approval", original["hash"], "original plan approved " + stamp(original["approved_at"]), original["approved_at"])
    ev2 = snap.evid("approval", current["hash"], "current plan approved " + stamp(current["approved_at"]), current["approved_at"])
    old, new = original["plan"], current["plan"]
    ask = ["revise the plan with `/mycelium-extra:grill` if this was not intended, then approve the new hash"]
    changes = verify.plan_changes(old, new)
    for step, column, was, now in changes[:CAP_PLAN_ITEMS]:
        routine = any(word in column for word in ("source", "evidence", "note"))
        snap.item("plan", (original["hash"], current["hash"], step, column), "Plan step {} {}: {} → {}".format(
            step, column, short(redact(was), 40) or "(empty)", short(redact(now), 40) or "(empty)"),
            "authorized" if routine else "attention", file="plan " + current["hash"],
            authorization_relation="covered_current", historical="different_original", semantic_relation="unassessed",
            summary="Observed plan change between the original and the current approved plan.",
            observed="Row {}, {}: was `{}`, now `{}`.".format(step, column, short(redact(was), 200), short(redact(now), 200)),
            potential="" if routine else "Potential analytical implication: a changed Choice, Step or Validation can change what is estimated; whether it does is for the researcher to assess.",
            unknown="Why the plan changed is not recorded here.",
            baseline="Original plan {} (approved {}).".format(original["hash"], stamp(original["approved_at"])),
            current="Current plan {} (approved {}).".format(current["hash"], stamp(current["approved_at"])),
            authorization="The current plan was approved by the researcher, so this is a later authorized revision, not an unexplained deviation.",
            next=ask, evidence=[ev, ev2], consequence="potential" if not routine else "not_assessed")
    if len(changes) > CAP_PLAN_ITEMS:
        snap.limitations.append("{} more plan row changes not listed; `verify diff {} {}` shows all".format(
            len(changes) - CAP_PLAN_ITEMS, original["hash"], current["hash"]))
    before, after = verify.plan_objective(old), verify.plan_objective(new)
    if before != after:
        snap.item("plan", (original["hash"], current["hash"], "objective"), "Plan objective changed", "attention",
                  file="plan " + current["hash"], authorization_relation="covered_current", historical="different_original",
                  summary="Observed change of the declared objective.", observed="Was `{}`; now `{}`.".format(
                      short(redact(before), 200) or "(none)", short(redact(after), 200) or "(none)"),
                  potential="Potential analytical implication: the question being answered may have moved.",
                  unknown="Whether the analysis still answers the original question.", next=ask, evidence=[ev, ev2])
    snap.limitations.append("inputs, outputs and validation blocks of the two plans are not compared here; `verify diff` does")


def code_items(gate, verify, snap, root, config, original, current, redact, budget_cache):
    if not current:
        return {}
    budget = gate.hash_budget(config)
    approved_at = current.get("approved_at", 0)
    orig_inst = first_instance(root, original["hash"]) if original else None
    orig_scripts = (orig_inst or {}).get("scripts") if orig_inst else (original or {}).get("scripts")
    cur_pins = dict(gate.read_script_pins(root, current["hash"]))
    cur_pins.update(current.get("scripts") or {})
    repins = [e for h in {current["hash"], (original or current)["hash"]} for e in gate.read_repins(root, h)]
    rels = set(cur_pins) | set(orig_scripts or {}) | set(e["rel"] for e in repins)
    last_change, diff_budget, used = 0, CAP_DIFF_TOTAL, 0
    if original and orig_inst is None:
        snap.limitations.append("original plan {} has no approval-instance record: its first script pins are not "
                                "recoverable, so original code baselines are unavailable".format(original["hash"]))
    for rel in sorted(rels)[:40]:
        path = os.path.join(root, rel)
        now = gate.fingerprint(path, budget)
        mine = sorted((e for e in repins if e["rel"] == rel), key=lambda e: e.get("ts", 0))
        since = [e for e in mine if e.get("ts", 0) >= approved_at and e["hash"] == current["hash"]]
        for e in mine:
            snap.event(e["ts"], "repin", "{} re-pinned (+{} -{})".format(rel, e.get("added") or 0, e.get("removed") or 0),
                       snap.evid("repin", rel + str(e["ts"]), "re-pin journal entry", e["ts"]))
        cur_pin, orig_pin = cur_pins.get(rel), (orig_scripts or {}).get(rel)
        if now.get("missing"):
            snap.item("code", rel, "{} was deleted".format(rel), "attention", file=rel, difference="observed",
                      summary="Observed: the file no longer exists.", authorization_relation="not_established",
                      unknown="Whether the deletion was intended.", evidence=[snap.evid("file", rel, "missing at snapshot")])
            continue
        unfrozen = bool(cur_pin) and not gate.unchanged(cur_pin, now)
        new_since_approval = not cur_pin
        vs_original = bool(orig_pin) and not gate.unchanged(orig_pin, now)
        if not (unfrozen or new_since_approval or vs_original or since):
            continue
        base_pin, baseline_name = (orig_pin, "original approval") if vs_original else (cur_pin, "current approval")
        diff = gate.script_diff(root, rel, base_pin) if base_pin and base_pin.get("sha256") and not now.get("missing") else None
        evid = [snap.evid("script", rel, "fingerprint now " + (now.get("sha256") or "size/mtime")[:12])]
        if base_pin:
            evid.append(snap.evid("pin", rel + str(base_pin.get("sha256")), baseline_name + " pin"))
        shown, numbers = [], ""
        if diff is not None:
            body = [l for l in diff if not l.startswith(("---", "+++"))]
            for line in body[:min(CAP_DIFF, max(diff_budget, 0))]:
                shown.append(["add" if line.startswith("+") else "del" if line.startswith("-") else "ctx", redact(line[:300])])
            diff_budget -= len(shown)
            if len(body) > len(shown):
                shown.append(["ctx", "… {} more diff lines not shown".format(len(body) - len(shown))])
            dropped, fresh, other = gate.diff_numbers(diff)
            known, _row = gate.plan_numbers(current["plan"], rel)
            outside = [n for n in fresh if float(n) not in known]
            numbers = "Numbers dropped: {}; new: {}{}; other changed lines: {}.".format(
                ", ".join(dropped) or "none", ", ".join(fresh) or "none",
                " ({} not in the plan)".format(", ".join(outside)) if outside else "", other)
        else:
            outside = []
            used += 1
        last_change = max([last_change, now.get("mtime", 0)] + [e["ts"] for e in since])
        attention = unfrozen or new_since_approval or bool(outside)
        title = ("{} edited since approval {}".format(rel, current["hash"]) if unfrozen else
                 "{} is new since the approval".format(rel) if new_since_approval else
                 "{} differs from the original approved code".format(rel))
        snap.item("code", rel, title, "attention" if attention else "authorized", file=rel,
                  difference="observed" if diff is not None else "unavailable",
                  authorization_relation="not_established" if unfrozen or new_since_approval else "covered_current",
                  historical="different_original" if vs_original else ("no_baseline" if original and not orig_pin else "not_applicable"),
                  consequence="potential" if outside else "not_assessed", attribution="unattributed",
                  summary="Observed code change{}.".format("; reportable use needs a freeze" if unfrozen or new_since_approval else ""),
                  observed=("The bytes differ from the {} pin. {}".format(baseline_name, numbers) if diff is not None else
                            "The bytes differ from the {} pin, but the pinned version was not kept, so no line diff exists.".format(baseline_name)),
                  potential=("Potential analytical implication: new numbers {} are not in the plan's rows; whether they change a "
                             "result is not assessed.".format(", ".join(outside)) if outside else ""),
                  unknown="Who edited it and why is not recorded here{}.".format(
                      "; re-pinned {}x since approval, last {}".format(len(since), stamp(since[-1]["ts"])) if since else ""),
                  baseline="Original code baseline: {}.".format("available (approval instance)" if orig_pin else
                                                                  "not available" + (" (script absent from the original approval)" if original else "")),
                  current="Current approval {} pinned {}.".format(current["hash"], "this script" if cur_pin else "no pin for this script"),
                  authorization="Edits after an approval re-pin as working code; freeze approves the reviewed bytes." if unfrozen
                  else "The current approval pins these bytes.",
                  next=(["review the diff, then type `freeze {}`".format(current["hash"])] if unfrozen or new_since_approval else []),
                  evidence=evid, diff=shown, limitations=([] if diff is not None else ["pinned version not kept (size limit, or only size and mtime pinned)"]))
    if used:
        snap.limitations.append("{} changed script(s) have no kept baseline snapshot: line diffs unavailable".format(used))
    return {"last_code_change": last_change}


def execution_items(gate, snap, root, original, current):
    hashes = [h for h in dict.fromkeys(r["hash"] for r in (original, current) if r)]
    receipts = [r for r in gate.read_receipts(root) if isinstance(r, dict) and not r.get("explore")
                and set(r.get("plans") or []) & set(hashes) and isinstance(r.get("ts"), (int, float))]
    if not receipts:
        if hashes:
            snap.limitations.append("no receipts for plan(s) {}: nothing shows these plans were run under the gate".format(", ".join(hashes)))
        return
    receipts.sort(key=lambda r: r["ts"])
    total = len(receipts)
    receipts = receipts[-CAP_RECEIPTS:]
    for r in receipts:
        snap.event(r["ts"], "run", "{} {} · exit {} · launch {}".format(
            r.get("kind") or "run", ",".join((r.get("paths") or [])[:2]) or "", r.get("exit_status"), r.get("launch_match")),
            snap.evid("receipt", "{}:{}".format(r.get("ts"), r.get("call_id") or r.get("command_sha") or ""), "receipt", r["ts"]))
    failed = [r for r in receipts if r.get("exit_status") not in (0, "unknown")]
    unknown = [r for r in receipts if r.get("exit_status") == "unknown"]
    unmatched = [r for r in receipts if r.get("launch_match") != "matched"]
    sbatch = [r for r in receipts if r.get("kind") == "sbatch"]
    other_instance = [r for r in receipts if current and current["hash"] in (r.get("plans") or []) and r.get("approval_instance")
                      and r.get("approval_instance") != current.get("instance_id")]
    gap = unknown or unmatched or sbatch
    bad = failed or gap or other_instance
    lines = []
    for i, r in enumerate(receipts):
        if r in failed:
            later = next((x for x in receipts[i + 1:] if x.get("exit_status") == 0 and x.get("paths") == r.get("paths")), None)
            lines.append("{} {} exited {}{}".format(stamp(r["ts"]), ",".join((r.get("paths") or [])[:2]) or "run", r.get("exit_status"),
                                                 "; a later run of the same path at {} exited 0 (both kept)".format(stamp(later["ts"])) if later else "; no later successful run of that path"))
    snap.item("execution", hashes, "Execution record: {} run(s), {} failed, {} unmatched".format(len(receipts), len(failed), len(unmatched)),
              "attention" if bad else "routine", file="receipts.jsonl", difference="observed", consequence="unknown",
              authorization_relation="covered_current" if current and not other_instance else "not_established",
              summary="{}{} run record(s) for {}.".format("Execution evidence gap: " if gap else "", total, ", ".join(hashes)),
              observed="; ".join(lines[:5]) or "No failed run recorded.",
              unknown="; ".join(filter(None, [
                  "run completion is unknown for {} run(s)".format(len(unknown)) if unknown else "",
                  "{} run(s) had no matched launch record".format(len(unmatched)) if unmatched else "",
                  "{} sbatch submission(s) show submission only, not that the job finished".format(len(sbatch)) if sbatch else ""]))
              or "Nothing recorded says whether the runs' outputs are the ones the plan declares.",
              authorization="{} run(s) of the current plan carry a different approval instance than the current one.".format(len(other_instance))
              if other_instance else "Runs of the current plan carry the current instance or none is recorded.",
              next=["`/mycelium-extra:verify report {}` grades what these runs establish".format((current or original)["hash"])],
              evidence=[snap.evid("receipt", "{}:{}".format(r.get("ts"), r.get("call_id") or ""), "receipt", r["ts"]) for r in receipts[:10]],
              limitations=(["only the last {} of {} receipts are summarized".format(CAP_RECEIPTS, total)] if total > CAP_RECEIPTS else []))


def output_items(gate, snap, root, current, last_change):
    words = gate.output_words(current["plan"]) if current else None
    if not words:
        return
    older, missing, fine = [], [], []
    for word in words[:30]:
        path = os.path.join(root, word)
        if os.path.isdir(path):
            continue
        if not os.path.isfile(path):
            missing.append(word)
        elif last_change and os.path.getmtime(path) < last_change:
            older.append(word)
        else:
            fine.append(word)
    if not (older or missing):
        if fine:
            snap.limitations.append("{} declared output(s) are not older than the latest code change; that does not show the code produced them".format(len(fine)))
        return
    snap.item("output", words, "{} declared output(s) older than the latest code change".format(len(older)) if older else
              "{} declared output(s) missing".format(len(missing)), "attention" if older else "routine", file=", ".join((older or missing)[:3]),
              currency="older_than_change" if older else "unknown", consequence="potential" if older else "unknown", attribution="not_applicable",
              summary="Declared outputs may not reflect the current code." if older else "Declared outputs not found.",
              observed="Older than the newest changed script: {}. Missing: {}.".format(", ".join(older) or "none", ", ".join(missing) or "none"),
              potential="Potential: results built from the earlier code may be out of date until the plan's steps are rerun." if older else "",
              unknown="Whether any output was produced by the earlier or the later code is not established by a modification time.",
              next=["rerun the affected steps after `freeze`, then `/mycelium-extra:verify report {}`".format(current["hash"])],
              evidence=[snap.evid("file", w, "output path") for w in (older or missing)[:5]])


def parse_ts(text):
    try:
        return calendar.timegm(time.strptime(str(text)[:19], "%Y-%m-%dT%H:%M:%S"))
    except ValueError:
        return None


def transcript_scan(path, root, since):
    """(edits, shell mentions, info) from a Claude Code transcript: direct Edit/Write tool calls only, and a bare
    count of shell commands that mention an analysis folder. No prompt text or command text is kept."""
    info = {"status": "available", "note": ""}
    edits, mentions = [], {}
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as handle:
            if size > CAP_TRANSCRIPT_BYTES:
                handle.seek(size - CAP_TRANSCRIPT_BYTES)
                handle.readline()
                info.update(status="partial", note="only the last {} of the transcript was read".format(
                    "{} MB".format(CAP_TRANSCRIPT_BYTES >> 20) if CAP_TRANSCRIPT_BYTES >= 1 << 20 else "{} KB".format(CAP_TRANSCRIPT_BYTES >> 10)))
            for count, raw in enumerate(handle):
                if count >= CAP_TRANSCRIPT_LINES:
                    info.update(status="partial", note="stopped after {} lines".format(CAP_TRANSCRIPT_LINES))
                    break
                if b"tool_use" not in raw:
                    continue
                try:
                    record = json.loads(raw)
                except ValueError:
                    info["bad_lines"] = info.get("bad_lines", 0) + 1
                    continue
                ts = parse_ts(record.get("timestamp")) if isinstance(record, dict) else None
                content = ((record.get("message") or {}).get("content")) if isinstance(record, dict) else None
                if (since and (ts is None or ts < since)) or not isinstance(content, list):
                    continue
                for part in content:
                    if not isinstance(part, dict) or part.get("type") != "tool_use":
                        continue
                    data = part.get("input") if isinstance(part.get("input"), dict) else {}
                    if part.get("name") in EDIT_TOOLS:
                        target = data.get("file_path") or data.get("notebook_path")
                        if isinstance(target, str):
                            full = os.path.normpath(target if os.path.isabs(target) else os.path.join(root, target))
                            rel = os.path.relpath(full, root) if full == root or full.startswith(root + os.sep) else None
                            edits.append({"ts": ts, "rel": rel, "tool": part["name"], "sidechain": bool(record.get("isSidechain"))})
                    elif part.get("name") == "Bash" and isinstance(data.get("command"), str):
                        for name in set(re.findall(r"analysis/([A-Za-z0-9][A-Za-z0-9._-]*)", data["command"])):
                            mentions[name] = mentions.get(name, 0) + 1
    except OSError as error:
        return [], {}, {"status": "unavailable", "note": "could not read the transcript ({})".format(type(error).__name__)}
    if info.get("bad_lines"):
        info["note"] = (info["note"] + "; " if info["note"] else "") + "{} unparseable line(s) skipped".format(info["bad_lines"])
        info["status"] = "partial"
    return edits, mentions, info


def top(rel):
    parts = rel.split("/")
    return "/".join(parts[:2]) if parts[0] == "analysis" and len(parts) > 2 else None


def focus_items(snap, root, rel, edits, mentions, transcript, started):
    mine = top(rel + "/x")
    groups, shared = {}, []
    for e in edits:
        r = e["rel"]
        if r is None or r.startswith("."):
            continue
        group = top(r + "/x") if r.startswith("analysis/") else None
        if group is None:
            shared.append(e)
        elif group != mine and os.path.isdir(os.path.join(root, group)):
            groups.setdefault(group, []).append(e)
    for group, found in sorted(groups.items()):
        files = sorted(set(e["rel"] for e in found))
        times = [e["ts"] for e in found if e["ts"]]
        side = any(e["sidechain"] for e in found)
        snap.item("focus", group, "Observed work under {} while {} was in focus".format(group, mine), "attention", file=files[0],
                  difference="observed", focus_relation="outside_path", semantic_relation="unassessed", attribution="contextual" if side else "direct_tool",
                  authorization_relation="not_applicable", consequence="unknown",
                  summary="Relationship to current focus not established: {} edit(s) to {} file(s) in another analysis.".format(len(found), len(files)),
                  observed="Direct editor tool calls: {}.{}".format(", ".join(files[:5]) + (" …" if len(files) > 5 else ""),
                                                                    " Some came from a subagent." if side else ""),
                  unknown="This may be a supporting dependency or a different analysis; no semantic judgement is made. Shell commands are not attributed.",
                  context="First {} last {} (transcript timestamps).".format(stamp(min(times)) if times else "?", stamp(max(times)) if times else "?"),
                  next=["if this is a new analysis, type `focus switch {}`; if it supports {}, note why in the plan or analysis doc".format(group, mine)],
                  evidence=[snap.evid("transcript_edit", f, "direct {} tool call".format(found[0]["tool"])) for f in files[:5]],
                  limitations=["out-of-directory work may be supporting analysis"])
        for e in found:
            snap.event(e["ts"], "edit", "edit {}".format(e["rel"]), snap.evid("transcript_edit", e["rel"], "direct tool call"))
    if shared:
        files = sorted(set(e["rel"] for e in shared if e["rel"]))
        snap.item("focus", "shared", "{} edit(s) outside analysis/ during the focus".format(len(shared)), "routine", file=files[0] if files else "",
                  focus_relation="unknown", attribution="direct_tool", consequence="unknown",
                  summary="Relationship to current focus not established: shared or project code was edited.",
                  observed="Direct editor tool calls: {}.".format(", ".join(files[:5]) + (" …" if len(files) > 5 else "")),
                  unknown="Helpers outside the analysis folder are often supporting code; this is not called unrelated.",
                  evidence=[snap.evid("transcript_edit", f, "direct tool call") for f in files[:5]],
                  limitations=["an out-of-directory edit is not out of scope"])
    if mentions:
        others = {k: v for k, v in mentions.items() if "analysis/" + k != mine}
        if others:
            snap.limitations.append("shell commands mention other analyses ({}); shell effects are not attributed".format(
                ", ".join("analysis/{} x{}".format(k, v) for k, v in sorted(others.items())[:5])))


def collect(args, gate, focus, verify):
    now = time.time()
    snap, redact = Snapshot(), Redactor()
    root = gate.find_root(args.repo) or os.path.abspath(args.repo)
    gated = os.path.isfile(os.path.join(root, ".mycelium-extra", "gate.json"))
    config = gate.load_config(root) if gated else dict(gate.DEFAULTS)
    focuses = open_focuses(root, focus)
    session_focus = None
    if args.analysis:
        rel = focus.resolve_target(root, args.analysis)
        match = [f for f in focuses if f[1]["analysis_path"] == rel]
        session_focus = match[0] if len(match) == 1 else None
    elif len(focuses) == 1:
        session_focus = focuses[0]
        rel = session_focus[1]["analysis_path"]
    elif focuses:
        raise Stop("several sessions have an open focus ({}); pass --analysis analysis/<folder>.".format(
            ", ".join(sorted(set(f[1]["analysis_path"] for f in focuses)))))
    else:
        found = focus.analyses(root)
        if len(found) == 1:
            rel = found[0]
        else:
            raise Stop("no focus is open and {}; pass --analysis analysis/<folder>{}.".format(
                "there is no folder under analysis/" if not found else "there are {} analyses".format(len(found)),
                " ({})".format(", ".join(found[:6])) if found else ""))
    episode = session_focus[1] if session_focus else None
    approvals = gate.all_approvals(root) if gated else []
    if approvals is None:
        approvals = []
        snap.limitations.append("reading approvals ran out of time: plan baselines unavailable")
    if not gated:
        snap.limitations.append("no .mycelium-extra/gate.json: there are no approvals, instances or receipts to read")
    original, current, relation = choose_baselines(gate, focus, root, rel, episode, args, approvals, snap)
    objective, doc = focus.objective_of(root, rel)
    if original:
        snap.event(original["approved_at"], "approval", "plan {} approved (original)".format(original["hash"]))
    if current and current is not original:
        snap.event(current["approved_at"], "approval", "plan {} approved (current)".format(current["hash"]))
    if episode:
        snap.event(episode["started_at"], "focus", "focus started on {}".format(rel))
    plan_items(gate, verify, snap, original, current, redact)
    extra = code_items(gate, verify, snap, root, config, original, current, redact, {}) or {}
    execution_items(gate, snap, root, original, current)
    output_items(gate, snap, root, current, extra.get("last_code_change", 0))
    transcript = {"status": "not_requested", "note": ""}
    path = args.transcript or (episode or {}).get("transcript_path")
    if path and os.path.isfile(path):
        edits, mentions, transcript = transcript_scan(path, root, (episode or {}).get("started_at"))
        focus_items(snap, root, rel, edits, mentions, transcript, episode)
        if not episode:
            transcript["note"] = (transcript["note"] + "; " if transcript["note"] else "") + "no focus window: the whole transcript was read"
    elif path:
        transcript = {"status": "unavailable", "note": "the recorded transcript file is not readable"}
    if transcript["status"] in ("not_requested", "unavailable"):
        snap.limitations.append("cross-analysis edits not observed: no transcript was read{}".format(
            "" if args.transcript or episode else " (pass --transcript, or focus first)"))
    if redact.count:
        snap.limitations.append("{} secret-like string(s) replaced with [redacted] in diffs and plan text".format(redact.count))
    if len(snap.items) > CAP_ITEMS:
        snap.limitations.append("{} items beyond the first {} were left out".format(len(snap.items) - CAP_ITEMS, CAP_ITEMS))
        snap.items = snap.items[:CAP_ITEMS]
    order = {"attention": 0, "authorized": 1, "routine": 2}
    rank = {"plan": 0, "code": 1, "execution": 2, "focus": 3, "output": 4}
    snap.items.sort(key=lambda i: (order[i["bucket"]], rank[i["kind"]], i["id"]))
    snap.timeline.sort(key=lambda e: e["ts"])
    snap.timeline = snap.timeline[-CAP_TIMELINE:]
    for e in snap.items:
        e["evidence"] = [x for x in dict.fromkeys(e["evidence"]) if x in snap.evidence]
    manifest = os.path.isdir(os.path.join(root, ".living"))
    return {
        "schema": SCHEMA, "generated_at": iso(now), "root": os.path.basename(root), "analysis_path": rel,
        "objective": {"text": objective, "source": doc},
        "focus": {"active_at_snapshot": bool(episode), "focus_id": (episode or {}).get("focus_id"),
                  "started_at": (episode or {}).get("started_at")} if episode else {"active_at_snapshot": False},
        "baselines": {"original_plan": (original or {}).get("hash"), "current_plan": (current or {}).get("hash"),
                      "current_instance": (current or {}).get("instance_id"), "relation": relation,
                      "original_approved": (original or {}).get("approved_at"), "current_approved": (current or {}).get("approved_at")},
        "coverage": {"focus_events": "available" if episode else "not_requested", "approvals": "available" if gated and approvals else "not_available",
                     "snapshots": "partial" if any("snapshot" in l or "baseline" in l for l in snap.limitations) else "available",
                     "receipts": "available" if any(i["kind"] == "execution" for i in snap.items) else "not_available",
                     "claude_transcript": transcript["status"], "transcript_note": transcript["note"], "mycelium": "present" if manifest else "absent",
                     "limitations": snap.limitations,
                     "not_observed": ["shell-made edits", "file reads"] + (
                         ["subagent work not marked in the transcript"] if transcript["status"] in ("available", "partial")
                         else ["edits to other analyses (no transcript read)"])},
        "counts": {b: sum(1 for i in snap.items if i["bucket"] == b) for b in order},
        "items": snap.items, "evidence": sorted(snap.evidence.values(), key=lambda e: e["id"]), "timeline": snap.timeline,
    }


def next_line(data):
    cur = data["baselines"]["current_plan"]
    by_kind = {}
    for i in data["items"]:
        if i["bucket"] == "attention":
            by_kind.setdefault(i["kind"], i)
    if "code" in by_kind and cur and by_kind["code"]["authorization_relation"] == "not_established":
        return "▶ review the diffs, then `freeze {}`   (or `/mycelium-extra:grill` to amend the plan)".format(cur)
    if "plan" in by_kind:
        return "▶ decide whether the plan change is intended; `/mycelium-extra:grill` revises it"
    if "focus" in by_kind:
        return "▶ `focus switch {}` if that is the new work, else note why it supports this analysis".format(
            by_kind["focus"]["title"].split()[4] if len(by_kind["focus"]["title"].split()) > 4 else "analysis/<folder>")
    if cur:
        return "▶ `/mycelium-extra:verify report {}` once the plan's steps have run".format(cur)
    return "▶ `/mycelium-extra:grill` to plan this analysis; there is no approved plan to compare"


def card(data):
    b, counts = data["baselines"], data["counts"]
    lines = ["mycelium-extra · track-changes {} · snapshot {}".format(data["analysis_path"], stamp(calendar.timegm(time.strptime(data["generated_at"], "%Y-%m-%dT%H:%M:%SZ"))))]
    lines.append("Baseline   original {} · current {}{}".format(
        b["original_plan"] or "none", b["current_plan"] or "none",
        " (instance {})".format(b["current_instance"][:8]) if b.get("current_instance") else ""))
    lines.append("Attention  {}".format(counts["attention"]))
    for i in [i for i in data["items"] if i["bucket"] == "attention"][:6]:
        lines.append("  ⚠ " + i["title"])
    more = counts["attention"] - 6
    if more > 0:
        lines.append("  … and {} more in the brief".format(more))
    lines.append("Also       {} authorized change(s) · {} routine".format(counts["authorized"], counts["routine"]))
    cov = data["coverage"]
    lines.append("Unknown    " + "; ".join(cov["not_observed"]) + (
        " \u00b7 {} coverage limit(s) in the brief".format(len(cov["limitations"])) if cov["limitations"] else ""))
    lines.append(next_line(data))
    return "\n".join(lines)


def brief(data):
    b, cov = data["baselines"], data["coverage"]
    out = ["# Review brief: {}".format(data["analysis_path"]), "",
           "Snapshot {} · original plan {} · current plan {} · {}".format(
               data["generated_at"], b["original_plan"] or "none", b["current_plan"] or "none",
               "focus open" if data["focus"]["active_at_snapshot"] else "no focus open"), "",
           "Read-only evidence summary. It approves nothing and does not judge scientific validity.", ""]
    for bucket, head in (("attention", "Needs attention"), ("authorized", "Changed, now authorized"), ("routine", "Routine")):
        found = [i for i in data["items"] if i["bucket"] == bucket]
        if not found:
            continue
        out += ["## {} ({})".format(head, len(found)), ""]
        for i in found:
            out += ["### {}".format(i["title"]), "", i["summary"], ""]
            for label, key in (("Observed", "observed"), ("Potential", "potential"), ("Unknown", "unknown"), ("Baseline", "baseline"),
                               ("Current", "current"), ("Authorization", "authorization"), ("Context", "context")):
                if i[key]:
                    out.append("- **{}:** {}".format(label, i[key]))
            out.append("- **Axes:** difference {}, focus {}, authorization {}, consequence {}, attribution {}, currency {}".format(
                i["difference"], i["focus_relation"], i["authorization_relation"], i["consequence"], i["attribution"], i["currency"]))
            out += ["- **Evidence:** " + (", ".join(i["evidence"]) or "none")] + ["- Next: " + n for n in i["next"]] + [""]
    out += ["## Coverage", ""] + ["- {}: {}".format(k, v) for k, v in cov.items() if isinstance(v, str)]
    out += ["- Not observed: " + ", ".join(cov["not_observed"])] + ["- {}".format(l) for l in cov["limitations"]]
    return "\n".join(out) + "\n"


def write_outputs(args, gate, root, data, html):
    import stateio
    base = os.path.join(root, ".mycelium-extra", "track-changes")
    expected = os.path.join(os.path.realpath(root), ".mycelium-extra", "track-changes")
    if os.path.lexists(base) and os.path.realpath(base) != expected:  # a symlink here would send the report elsewhere
        raise Stop("refusing to write: .mycelium-extra/track-changes is a link or resolves outside the project")
    folder = os.path.join(base, re.sub(r"[^A-Za-z0-9_-]+", "-", data["analysis_path"]).strip("-"))
    os.makedirs(folder, mode=0o700, exist_ok=True)
    if not os.path.realpath(folder).startswith(expected + os.sep):
        raise Stop("refusing to write: {} resolves outside .mycelium-extra/track-changes/".format(folder))
    paths = {}
    for name, text in (("snapshot.json", json.dumps(data, indent=1) + "\n"), ("brief.md", brief(data)), ("report.html", html)):
        target = os.path.join(folder, name)
        stateio.atomic(target, text)
        os.chmod(target, 0o600)
        paths[name] = os.path.relpath(target, root)
    return paths


def load_render(plugin_root):
    path = os.path.join(plugin_root, "skills", "track-changes", "scripts", "render.py")
    spec = importlib.util.spec_from_file_location("mycelium_extra_track_render", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ASSETS = os.path.join(plugin_root, "skills", "track-changes", "assets")
    return module


def main(argv):
    parser = argparse.ArgumentParser(prog="track_changes")
    parser.add_argument("--plugin-root", required=True)
    parser.add_argument("--repo", default=os.getcwd())
    parser.add_argument("--analysis")
    parser.add_argument("--original")
    parser.add_argument("--current")
    parser.add_argument("--transcript")
    parser.add_argument("--json", action="store_true", help="print the snapshot instead of the card")
    parser.add_argument("--no-write", action="store_true", help="print only; write no files")
    args = parser.parse_args(argv)
    gate, focus, verify = load(args.plugin_root)
    try:
        data = collect(args, gate, focus, verify)
        root = gate.find_root(args.repo) or os.path.abspath(args.repo)
        paths = {}
        if not args.no_write:
            paths = write_outputs(args, gate, root, data, load_render(args.plugin_root).render(data, brief(data)))
    except (Stop, focus.FocusError) as error:
        print("track-changes: {}".format(error), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(data, indent=1))
    else:
        print(card(data))
        if paths:
            print("Files      {} (brief.md, report.html: open the HTML in a browser)".format(os.path.dirname(paths["brief.md"])))
        git = gate.git(root, "rev-parse", "--is-inside-work-tree")
        if paths and git and gate.git(root, "check-ignore", "-q", ".mycelium-extra/") is None:
            print("Warning    .mycelium-extra/ is not in .gitignore; the report holds code diffs. Add it before committing.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
