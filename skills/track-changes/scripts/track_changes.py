#!/usr/bin/env python3
"""track-changes: a read-only view of how one analysis moved away from its approved intent.

    sh hooks/py.sh - --plugin-root <plugin> [--repo DIR] [--analysis <folder>] [--original HASH] [--current HASH]
        [--transcript FILE] [--json] [--no-write] < track_changes.py

Reads approvals, approval instances, the re-pin journal, kept script snapshots, receipts, the focus records and
(optionally) a Claude Code transcript. Writes only `.mycelium-extra/track-changes/<analysis>/`: snapshot.json,
brief.md, report.html. Nothing here approves, freezes, runs, pins or re-grades anything; it never calls
`freeze_state`, `keep_snapshot`, `verify report`, or any helper that writes gate state. What it did not observe
is said so: no warning is not evidence of no drift.
"""

import argparse
import calendar
import glob
import hashlib
import importlib.util
import json
import os
import posixpath
import re
import sys
import time

SCHEMA = "mycelium-extra.track-changes.v1"
CAP_ITEMS, CAP_PLAN_ITEMS, CAP_RECEIPTS, CAP_TIMELINE = 80, 25, 40, 200
CAP_DIFF, CAP_DIFF_TOTAL = 40, 300
CAP_EXPLAIN = 400
CAP_TRANSCRIPT_BYTES, CAP_TRANSCRIPT_LINES = 20 * 1024 * 1024, 300000
SECRET = re.compile(
    r"(?i)((?:api[_-]?key|secret|token|passw(?:or)?d|credential|auth)[\w-]*[\"']?\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[\"']?(?:(?:Bearer|Basic|Token)\s+)?\S+)"
    r"|\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"
    r"|\b[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@\S*"  # a password in a URL
    r"|\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}"  # a JWT
    r"|\bAKIA[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9]{20,}\b|\bsk-[A-Za-z0-9_-]{20,}\b|\bxox[abp]-[A-Za-z0-9-]{10,}\b"
    r"|-----BEGIN[ A-Z]*PRIVATE KEY-----[\s\S]*?-----END[ A-Z]*PRIVATE KEY-----)")
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


def session_episode(root, focus, session_id):
    """This session's open focus episode, or None. Another session's focus is never used: a focus left open by a
    session that ended is not this session's (it is inactive once another session starts)."""
    if not session_id:
        return None
    try:
        return focus.open_episode(focus.read(root, session_id))
    except focus.FocusError:
        return None


def first_instance(root, digest):
    """The earliest approval instance of a plan: what its first approval froze (None for a legacy approval)."""
    folder = os.path.join(root, ".mycelium-extra", "approval-instances", digest)
    found = [r for r in (read_json(os.path.join(folder, n)) for n in sorted(os.listdir(folder)) if n.endswith(".json"))
             if isinstance(r, dict)] if os.path.isdir(folder) else []
    return min(found, key=lambda r: r.get("approved_at", 0)) if found else None


def choose_baselines(gate, focus, verify, root, rel, episode, args, approvals, snap):
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
        shown = ["{} (approved {}; {})".format(r["hash"], stamp(r["approved_at"]), short(verify.plan_objective(r["plan"]), 50) or "no objective line")
                 for r in candidates[:8]]
        raise Stop("{} approved plans name paths inside {}; which one states the original intent? Pass --original <hash>. "
                   "Nothing is guessed from dates. Newest first: {}{}".format(
                       len(candidates), rel, "; ".join(shown), " \u2026 and {} more (`verify list` shows them all)".format(len(candidates) - 8)
                       if len(candidates) > 8 else ""))
    if args.current:
        if args.current not in by_hash:
            raise Stop("no approved plan {}. Pass --current with a plan that exists.".format(args.current))
        current = by_hash[args.current]
    else:
        current = candidates[0] if candidates else None
    if relation == "none":
        snap.limitations.append("no approved plan names a path inside {}: there is no intent baseline".format(rel))
    return original, current, relation


def binding_checks(gate, text):
    """({id: required, definition}, None) from a plan's validation-bindings block, ({}, None) without one,
    (None, reason) when the block cannot be read. The strict reader of hooks/validation.py decides what is readable."""
    data, errors = gate.blocks_module().read_block(text, "validation-bindings", "checks")
    if errors:
        return None, errors[0]
    found = {}
    for item in (data or {}).get("checks", []):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or item["id"] in found:
            return None, "a check has no usable, unique id"
        definition = {key: item.get(key) for key in ("plan_row", "test_paths", "invocation", "evidence_path")}
        found[item["id"]] = (item.get("required", True), json.dumps(definition, sort_keys=True))
    return found, None


def lost_coverage(gate, snap, original, current, ev, ev2, ask):
    """One attention item when an approved revision drops or redefines a validation binding or a declared output.
    An unreadable block is a limitation, never "no losses". Equivalence of checks is never judged."""
    old, new = original["plan"], current["plan"]
    before, why_old = binding_checks(gate, old)
    after, why_new = binding_checks(gate, new)
    for side, why in (("original", why_old), ("current", why_new)):
        if why:
            snap.limitations.append("validation bindings of the {} plan could not be compared: {}".format(side, why))
    removed = changed = added = []
    if before is not None and after is not None:
        removed = sorted(i for i, (required, _) in before.items() if required and i not in after)
        changed = sorted(i for i in before if i in after and before[i][1] != after[i][1])
        added = sorted(i for i in after if i not in before)
    was, now = [gate.output_words(text) or [] for text in (old, new)]
    dropped = [w for w in was if w not in now]
    if not (removed or changed or dropped):
        return
    parts, potential = [], []
    if removed:
        parts.append("required validation binding{} {} no longer in the plan".format("s" if len(removed) > 1 else "", ", ".join(removed)))
        potential.append("what the removed check tested may no longer be tested")
    if changed:
        parts.append("binding{} {}: definition changed (rows, test files, command or evidence path)".format(
            "s" if len(changed) > 1 else "", ", ".join(changed)))
        potential.append("a redefined check may test something else")
    if dropped:
        parts.append("output{} no longer declared: {}".format("s" if len(dropped) > 1 else "", ", ".join(dropped[:5]) + (" \u2026" if len(dropped) > 5 else "")))
        potential.append("a declared output the plan no longer names may no longer be produced or checked")
    if added and (removed or changed):
        parts.append("new binding{} present: {}; whether {} replaces anything is not assessed".format(
            "s" if len(added) > 1 else "", ", ".join(added), "it" if len(added) == 1 else "they"))
    snap.item("plan", (original["hash"], current["hash"], "lost-coverage"),
              "Possible lost plan coverage between plans {} and {}".format(original["hash"], current["hash"]), "attention",
              file="plan " + current["hash"], authorization_relation="covered_current", historical="different_original",
              semantic_relation="unassessed", summary="Observed: the approved revision drops or redefines validation coverage.",
              observed="; ".join(parts) + ".", potential="Potential: " + "; ".join(potential) + ".",
              unknown="Whether an equivalent check or output exists elsewhere, or the change was intended, is not recorded here.",
              authorization="The current plan was approved by the researcher, so this is a later authorized revision, not an unexplained deviation.",
              next=ask + ["`verify diff {} {}` lists every difference".format(original["hash"], current["hash"])],
              evidence=[ev, ev2], consequence="potential")


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
    lost_coverage(gate, snap, original, current, ev, ev2, ask)
    snap.limitations.append("inputs and exact-execution blocks of the two plans are not compared here, and bindings and outputs only for removal or redefinition; `verify diff` shows everything")


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
                                "recoverable; baselines come from the approval record, which a later approval of the same plan may have "
                                "re-baselined".format(original["hash"]))
    if len(rels) > 40:
        snap.limitations.append("only the first 40 of {} pinned scripts were compared".format(len(rels)))
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
                shown.append(["add" if line.startswith("+") else "del" if line.startswith("-") else "ctx", redact(line)[:300]])
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
                  baseline="Original code baseline: {}.".format("available (the original approval's pin)" if orig_pin else
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
    failed = [r for r in receipts if r.get("exit_status") not in (0, "unknown", None)]
    unknown = [r for r in receipts if r.get("exit_status") in ("unknown", None)]  # a legacy receipt has no status: unknown, not failed
    unmatched = [r for r in receipts if r.get("launch_match") != "matched"]
    sbatch = [r for r in receipts if r.get("kind") == "sbatch"]
    # a receipt's instance is that of its last plan, so only a receipt of this plan alone says anything about this instance
    other_instance = [r for r in receipts if current and (r.get("plans") or []) == [current["hash"]] and r.get("approval_instance")
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
    older, missing, fine, patterns = [], [], [], []

    def classify(path, label):
        if os.path.isdir(path):
            return
        if not os.path.isfile(path):
            missing.append(label)
        elif last_change and os.path.getmtime(path) < last_change:
            older.append(label)
        else:
            fine.append(label)

    for word in words[:30]:
        if any(c in word for c in "*?["):  # `<name>` and `{a,b}` in an Outputs line become patterns
            hits = sorted(glob.glob(os.path.join(root, word)))[:50]
            for hit in hits:
                classify(hit, os.path.relpath(hit, root))
            if not hits:
                patterns.append(word)
        else:
            classify(os.path.join(root, word), word)
    if len(words) > 30:
        snap.limitations.append("only the first 30 of {} declared output paths were checked".format(len(words)))
    if patterns:
        snap.limitations.append("declared output pattern(s) matched no file, so they were not checked: {}".format(", ".join(patterns[:3])))
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


def transcript_scan(path, root, since, container):
    """(edits, shell mentions, info) from a Claude Code transcript: direct Edit/Write tool calls only, and a bare
    count of shell commands that mention an analysis folder. No prompt text or command text is kept."""
    info = {"status": "available", "note": ""}
    edits, mentions = [], {}
    real_root = os.path.realpath(root)
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
                            rel = None
                            for base in (root, real_root):
                                if full == base or full.startswith(base + os.sep):
                                    rel = os.path.relpath(full, base)
                                    break
                            if rel is None:
                                real = os.path.realpath(full)
                                if real.startswith(real_root + os.sep):
                                    rel = os.path.relpath(real, real_root)
                            if rel is None:
                                info["outside_root"] = info.get("outside_root", 0) + 1
                            edits.append({"ts": ts, "rel": rel, "tool": part["name"], "sidechain": bool(record.get("isSidechain"))})
                    elif part.get("name") == "Bash" and isinstance(data.get("command"), str):
                        for name in set(re.findall(re.escape(container) + r"/([A-Za-z0-9_][A-Za-z0-9._-]*)", data["command"])):
                            mentions[name] = mentions.get(name, 0) + 1
    except OSError as error:
        return [], {}, {"status": "unavailable", "note": "could not read the transcript ({})".format(type(error).__name__)}
    if info.get("bad_lines"):
        info["note"] = (info["note"] + "; " if info["note"] else "") + "{} unparseable line(s) skipped".format(info["bad_lines"])
        info["status"] = "partial"
    return edits, mentions, info


def unit_of(path, container):
    """The sibling folder of the focus that `path` lies in (`container/<unit>`), or None when it is not inside
    the focus's container or is a bare file there."""
    prefix = container + "/"
    if path.startswith(prefix):
        rest = path[len(prefix):].split("/")
        return prefix + rest[0] if len(rest) > 1 else None
    return None


def focus_items(snap, root, rel, edits, mentions, transcript, started):
    mine = rel  # the focused folder; its siblings under the same parent are the other analyses
    container = posixpath.dirname(rel)
    groups, shared = {}, []
    for e in edits:
        r = e["rel"]
        if r is None or r.startswith("."):
            continue
        if r == mine or r.startswith(mine + "/"):
            continue  # inside the focus: not drift
        group = unit_of(r, container) if container else None
        if group is None or not os.path.isdir(os.path.join(root, group)):
            shared.append(e)
        else:
            groups.setdefault(group, []).append(e)
    for group, found in sorted(groups.items()):
        files = sorted(set(e["rel"] for e in found))
        times = [e["ts"] for e in found if e["ts"]]
        side = any(e["sidechain"] for e in found)
        snap.item("focus", group, "Observed work under {} while {} was in focus".format(group, mine), "attention", file=files[0], target=group,
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
        snap.item("focus", "shared", "{} edit(s) outside {}/ during the focus".format(len(shared), container), "routine", file=files[0] if files else "",
                  focus_relation="unknown", attribution="direct_tool", consequence="unknown",
                  summary="Relationship to current focus not established: shared or project code was edited.",
                  observed="Direct editor tool calls: {}.".format(", ".join(files[:5]) + (" …" if len(files) > 5 else "")),
                  unknown="Helpers outside the analysis folder are often supporting code; this is not called unrelated.",
                  evidence=[snap.evid("transcript_edit", f, "direct tool call") for f in files[:5]],
                  limitations=["an out-of-directory edit is not out of scope"])
    if mentions:
        others = {k: v for k, v in mentions.items() if container + "/" + k != mine}
        if others:
            snap.limitations.append("shell commands mention other analyses ({}); shell effects are not attributed".format(
                ", ".join("{}/{} x{}".format(container, k, v) for k, v in sorted(others.items())[:5])))


def prioritize(snap):
    """Order items by bucket then kind, and only then keep the first CAP_ITEMS: the cap must never drop an
    attention item that was collected late while a routine one collected early stays. Says what it left out."""
    order = {"attention": 0, "authorized": 1, "routine": 2}
    rank = {"plan": 0, "code": 1, "execution": 2, "focus": 3, "output": 4}
    snap.items.sort(key=lambda i: (order[i["bucket"]], rank[i["kind"]], i["id"]))
    if len(snap.items) > CAP_ITEMS:
        snap.limitations.append("{} items beyond the first {} were left out".format(len(snap.items) - CAP_ITEMS, CAP_ITEMS))
        snap.items = snap.items[:CAP_ITEMS]


def walkthrough(gate, verify, plan, source, redact):
    """The plan's `<!-- plan-evidence -->` block joined to its table rows: each step, the rows it consumes,
    and the command and output the plan recorded. Nothing here runs: the page shows the text the approval
    pinned, and `verify report` is what re-runs the commands."""
    blocks = verify.EVIDENCE_BLOCK.findall(plan or "")
    note, entries = "", {}
    if len(blocks) > 1:
        note = "the plan has {} plan-evidence blocks; only the first is shown".format(len(blocks))
    if blocks:
        try:
            payload = json.loads(blocks[0])
            rows = payload["rows"]
            if payload.get("version") != 1 or not isinstance(rows, list):
                raise ValueError("not version 1")
            for row in rows:
                if isinstance(row, dict) and str(row.get("row") or ""):
                    entries.setdefault(str(row["row"]), row)
        except (ValueError, KeyError, TypeError):
            note = "the plan-evidence block did not parse, so no command or output is shown"

    def text(value, limit=200):
        return short(redact(str(value if value is not None else "")), limit)

    def read(entry):
        """Each recorded command, its claim, and its output, capped for the page."""
        found = []
        for item in entry.get("evidence") or []:
            if not isinstance(item, dict):
                continue
            lines = redact(str(item.get("out") if item.get("out") is not None else "")).splitlines()
            found.append({"claim": text(item.get("claim")), "cmd": text(item.get("cmd"), 300),
                          "out": "\n".join(lines[:verify.EVIDENCE_MAX_LINES]),
                          "more": max(0, len(lines) - verify.EVIDENCE_MAX_LINES)})
        return found

    out, matched = [], set()
    for position, row in enumerate(gate.plan_rows(plan or "") or [], 1):
        key = str(row.get("id") or row.get("num") or position)
        matched.add(key)
        entry = entries.get(key) or {}
        out.append({"row": key, "step": text(row.get("step")), "choice": text(row.get("choice")),
                    "depends_on": [str(d) for d in entry.get("depends_on") or []], "evidence": read(entry)})
    for key in sorted(set(entries) - matched):  # recorded evidence for a row the table no longer has
        out.append({"row": key, "step": "not in the plan table", "choice": "",
                    "depends_on": [str(d) for d in entries[key].get("depends_on") or []],
                    "evidence": read(entries[key])})
    return {"plan": source, "note": note, "rows": out}


def collect(args, gate, focus, verify):
    now = time.time()
    snap, redact = Snapshot(), Redactor()
    root = gate.find_root(args.repo) or os.path.abspath(args.repo)
    gated = os.path.isfile(os.path.join(root, ".mycelium-extra", "gate.json"))
    config = gate.load_config(root) if gated else dict(gate.DEFAULTS)
    session_id = args.session or os.environ.get("CLAUDE_CODE_SESSION_ID")
    episode = session_episode(root, focus, session_id)
    if args.analysis:
        rel = focus.resolve_target(root, args.analysis, focus.roots_of(config))
        if episode and episode["analysis_path"] != rel:
            episode = None  # this session is focused elsewhere: no focus window for this analysis
    elif episode:
        rel = episode["analysis_path"]
    else:
        found = focus.analyses(root, focus.roots_of(config))
        raise Stop("this session has no open focus{}; pass --analysis <folder>{}.".format(
            "" if session_id else " (no session id: set $CLAUDE_CODE_SESSION_ID or pass --session)",
            " ({})".format(", ".join(found[:6])) if found else ""))
    approvals = gate.all_approvals(root) if gated else []
    explicit_current = bool(args.current)
    if approvals is None:
        approvals = []
        snap.limitations.append("reading approvals ran out of time: plan baselines unavailable")
    if not gated:
        snap.limitations.append("no .mycelium-extra/gate.json: there are no approvals, instances or receipts to read")
    original, current, relation = choose_baselines(gate, focus, verify, root, rel, episode, args, approvals, snap)
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
        edits, mentions, transcript = transcript_scan(path, root, (episode or {}).get("started_at"), posixpath.dirname(rel))
        focus_items(snap, root, rel, edits, mentions, transcript, episode)
        if transcript.get("outside_root"):
            snap.limitations.append("{} transcript edit(s) lay outside the project path and were not classified".format(transcript["outside_root"]))
        if not episode:
            transcript["note"] = (transcript["note"] + "; " if transcript["note"] else "") + "no focus window: the whole transcript was read"
    elif path:
        transcript = {"status": "unavailable", "note": "the recorded transcript file is not readable"}
    if transcript["status"] in ("not_requested", "unavailable"):
        snap.limitations.append("cross-analysis edits not observed: no transcript was read{}".format(
            "" if args.transcript or episode else " (pass --transcript, or focus first)"))
    if redact.count:
        snap.limitations.append("{} secret-like string(s) replaced with [redacted] in diffs and plan text".format(redact.count))
    prioritize(snap)
    snap.timeline.sort(key=lambda e: e["ts"])
    snap.timeline = snap.timeline[-CAP_TIMELINE:]
    for e in snap.items:
        e["evidence"] = [x for x in dict.fromkeys(e["evidence"]) if x in snap.evidence]
    manifest = os.path.isdir(os.path.join(root, ".living"))
    base = current or original
    source = ("current approved plan " + current["hash"] if current else
              "original approved plan " + original["hash"] if original else "no approved plan")
    walk = walkthrough(gate, verify, (base or {}).get("plan"), source, redact)
    return {
        "schema": SCHEMA, "generated_at": iso(now), "root": os.path.basename(root), "analysis_path": rel,
        "objective": {"text": redact(objective) if objective else objective, "source": doc},
        "focus": {"active_at_snapshot": bool(episode), "focus_id": (episode or {}).get("focus_id"),
                  "started_at": (episode or {}).get("started_at")} if episode else {"active_at_snapshot": False},
        "baselines": {"original_plan": (original or {}).get("hash"), "current_plan": (current or {}).get("hash"),
                      "current_instance": (current or {}).get("instance_id"), "relation": relation,
                      "current_selection": "explicit" if explicit_current else "newest_naming_folder",
                      "original_approved": (original or {}).get("approved_at"), "current_approved": (current or {}).get("approved_at")},
        "coverage": {"focus_events": "available" if episode else "not_requested", "approvals": "available" if gated and approvals else "not_available",
                     "snapshots": "partial" if any("snapshot" in l or "baseline" in l for l in snap.limitations) else "available",
                     "receipts": "available" if any(i["kind"] == "execution" for i in snap.items) else "not_available",
                     "claude_transcript": transcript["status"], "transcript_note": transcript["note"], "mycelium": "present" if manifest else "absent",
                     "limitations": snap.limitations,
                     "not_observed": ["shell-made edits", "file reads", "scripts no approval pinned and no run touched"] + (
                         ["subagent work not marked in the transcript"] if transcript["status"] in ("available", "partial")
                         else ["edits to other analyses (no transcript read)"])},
        "counts": {b: sum(1 for i in snap.items if i["bucket"] == b) for b in ("attention", "authorized", "routine")},
        "items": snap.items, "evidence": sorted(snap.evidence.values(), key=lambda e: e["id"]), "timeline": snap.timeline,
        "walkthrough": walk,
    }


def explain(data, wanted):
    """The bounded evidence block for one item: five headings, no verdict. A unique id prefix is enough."""
    found = [i for i in data["items"] if i["id"] == wanted] or [i for i in data["items"] if i["id"].startswith(wanted)]
    if len(found) != 1:
        ids = ", ".join(i["id"] for i in data["items"][:8]) or "none"
        raise Stop("{} item matches '{}'; ids in this snapshot: {}".format("no" if not found else "more than one", wanted, ids))
    i = found[0]
    by_id = {e["id"]: e for e in data["evidence"]}
    lines = ["mycelium-extra · track-changes explain {} · {}".format(i["id"], i["title"]), ""]
    lines += ["Observed", "  " + short(i["observed"] or i["summary"] or "nothing recorded", CAP_EXPLAIN), ""]
    lines += ["Potential", "  " + short(i["potential"] or "no analytical implication was assessed", CAP_EXPLAIN), ""]
    lines += ["Unknown", "  " + short(i["unknown"] or "not stated for this item", CAP_EXPLAIN),
              "  not observed anywhere in this report: " + "; ".join(data["coverage"]["not_observed"]), ""]
    lines += ["Authorization",
              "  {}; focus relation {}; difference {}".format(
                  short(i["authorization"] or i["authorization_relation"], CAP_EXPLAIN), i["focus_relation"], i["difference"]), ""]
    lines += ["Evidence"]
    for key in i["evidence"][:5]:
        e = by_id[key]
        lines.append("  {} {} {}".format(e["id"], e["source"], short(" ".join(x for x in (e["ref"], e["detail"]) if x), 100)))
    if not i["evidence"]:
        lines.append("  none recorded")
    if len(i["evidence"]) > 5:
        lines.append("  … and {} more in snapshot.json".format(len(i["evidence"]) - 5))
    lines.append("This block approves, freezes and validates nothing; it does not say whether the change matters.")
    return "\n".join(lines)


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
            by_kind["focus"].get("target") or "<folder>")
    if cur:
        return "▶ `/mycelium-extra:verify report {}` once the plan's steps have run".format(cur)
    return "▶ `/mycelium-extra:grill` to plan this analysis; there is no approved plan to compare"


def card(data):
    b, counts = data["baselines"], data["counts"]
    lines = ["mycelium-extra · track-changes {} · snapshot {}".format(data["analysis_path"], stamp(calendar.timegm(time.strptime(data["generated_at"], "%Y-%m-%dT%H:%M:%SZ"))))]
    lines.append("Baseline   original {} · current {}{}{}".format(
        b["original_plan"] or "none", b["current_plan"] or "none",
        " (instance {})".format(b["current_instance"][:8]) if b.get("current_instance") else "",
        " (newest approved plan naming this folder; --current to choose)" if b["current_plan"] and b.get("current_selection") != "explicit" else ""))
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


def output_folder(base, analysis_path):
    """The report folder for one analysis. Two analyses can spell one folder name (`a/b` and a folder
    literally named `a__b`); when the snapshot already there belongs to another analysis, keep both by
    adding a hash of the exact path."""
    folder = os.path.join(base, analysis_path.replace("/", "__"))
    snapshot = os.path.join(folder, "snapshot.json")
    if os.path.isfile(snapshot):
        try:
            with open(snapshot, encoding="utf-8") as handle:
                prior = json.load(handle).get("analysis_path")
        except (OSError, ValueError, AttributeError):
            prior = None
        if prior is not None and prior != analysis_path:
            folder = "{}-{}".format(folder, hashlib.sha256(analysis_path.encode("utf-8")).hexdigest()[:8])
    return folder


def write_outputs(args, gate, root, data, html):
    import stateio
    base = os.path.join(root, ".mycelium-extra", "track-changes")
    expected = os.path.join(os.path.realpath(root), ".mycelium-extra", "track-changes")
    if os.path.lexists(base) and os.path.realpath(base) != expected:  # a symlink here would send the report elsewhere
        raise Stop("refusing to write: .mycelium-extra/track-changes is a link or resolves outside the project")
    folder = output_folder(base, data["analysis_path"])
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
    parser.add_argument("--session", help="the session whose focus to use (default: $CLAUDE_CODE_SESSION_ID)")
    parser.add_argument("--original")
    parser.add_argument("--current")
    parser.add_argument("--transcript")
    parser.add_argument("--json", action="store_true", help="print the snapshot instead of the card")
    parser.add_argument("--no-write", action="store_true", help="print only; write no files")
    parser.add_argument("--journal", action="store_true", help="collect historical Analysis Journal")
    parser.add_argument("--save-checkpoint", action="store_true", help="explicitly save an immutable journal checkpoint")
    parser.add_argument("--note", action="append", default=[], metavar="RELATIVE_PATH[#ANCHOR]")
    parser.add_argument("--explain", metavar="ITEM_ID", help="print the bounded evidence block for one item (read-only; writes no files)")
    args = parser.parse_args(argv)
    if (args.save_checkpoint or args.note) and not args.journal:
        parser.error("--save-checkpoint and --note require --journal")
    if args.save_checkpoint and (args.no_write or args.explain):
        parser.error("--save-checkpoint conflicts with --no-write and --explain")
    if args.journal and args.explain:
        parser.error("--explain selects ordinary report items; use the Journal's evidence controls")
    gate, focus, verify = load(args.plugin_root)
    try:
        if args.journal:
            scripts = os.path.join(args.plugin_root, "skills", "track-changes", "scripts")
            if scripts not in sys.path:
                sys.path.insert(0, scripts)
            import journal
            root = gate.find_root(args.repo) or os.path.abspath(args.repo)
            episode = session_episode(root, focus, args.session or os.environ.get("CLAUDE_CODE_SESSION_ID"))
            target = args.analysis or (episode or {}).get("analysis_path")
            if not target:
                raise Stop("Journal needs --analysis or this session's open focus")
            config = gate.load_config(root) if os.path.isfile(os.path.join(root, ".mycelium-extra", "gate.json")) else dict(gate.DEFAULTS)
            rel = focus.resolve_target(root, target, focus.roots_of(config))
            history = journal.collect(root, rel, gate, focus, args.note)
            # The Journal has an explicit historical scope; ordinary Review retains its endpoint selection.
            ordinary_args = argparse.Namespace(**vars(args))
            approvals = [e for e in history["events"] if e["kind"] == "approval"]
            journal_baseline = not ordinary_args.original and bool(approvals)
            if journal_baseline:
                ordinary_args.original = approvals[0]["references"]["plan"]
            try:
                data = collect(ordinary_args, gate, focus, verify)
                if journal_baseline:
                    data["baselines"]["relation"] = "journal_history_display"
                    data["baselines"]["original_selection"] = "earliest_available_for_display"
                    data["coverage"]["limitations"].append(
                        "Journal Review starts at the earliest available approval for display; this does not "
                        "establish original intent. Pass --original to choose the comparison baseline.")
            except (Stop, ValueError, OSError, KeyError, TypeError) as error:
                data = {"schema": SCHEMA, "generated_at": history["refreshed_at"], "analysis_path": rel,
                        "objective": history["objective"], "focus": {"active_at_snapshot": False},
                        "baselines": {"original_plan": None, "current_plan": None},
                        "coverage": {"limitations": [str(error)], "not_observed": ["ordinary comparison unavailable"]},
                        "counts": {"attention": 0, "authorized": 0, "routine": 0},
                        "items": [], "evidence": [], "timeline": []}
            data["journal"] = history
            if args.save_checkpoint:
                saved = journal.save(root, history)
                data["journal"]["saved_checkpoint"] = {"digest": saved["digest"], "saved_at": saved["saved_at"]}
        else:
            data = collect(args, gate, focus, verify)
    except (Stop, focus.FocusError, ValueError, OSError) as error:  # a malformed approval record is a ValueError
        print("track-changes: {}".format(error), file=sys.stderr)
        return 2
    if args.explain:
        try:
            print(explain(data, args.explain))
        except Stop as error:
            print("track-changes: {}".format(error), file=sys.stderr)
            return 2
        return 0
    root = gate.find_root(args.repo) or os.path.abspath(args.repo)
    paths, write_error = {}, None
    if not args.no_write:
        try:
            paths = write_outputs(args, gate, root, data, load_render(args.plugin_root).render(data, brief(data)))
        except Stop as error:
            print("track-changes: {}".format(error), file=sys.stderr)
            return 2
        except (ValueError, OSError) as error:  # still show what was found
            write_error = error
    if args.json:
        print(json.dumps(data["journal"] if args.journal else data, indent=1))
    else:
        if args.journal:
            j = data["journal"]
            print("Analysis Journal · {} · {} recorded events · refreshed {}".format(
                j["analysis_path"], len(j["events"]), j["refreshed_at"]))
            print("Coverage: " + "; ".join("{}: {}".format(k, v) for k, v in sorted(j["coverage"].items())))
            if j.get("saved_checkpoint"):
                print("Checkpoint: {}/journal/checkpoints/{}.json (first saved {})".format(
                    j["analysis_path"], j["saved_checkpoint"]["digest"], j["saved_checkpoint"]["saved_at"]))
        else:
            print(card(data))
        if write_error:
            print("Files      none written: {}".format(write_error))
        if paths:
            print("Files      {} (brief.md, report.html: open the HTML in a browser)".format(os.path.dirname(paths["brief.md"])))
        git = gate.git(root, "rev-parse", "--is-inside-work-tree")
        if paths and git and gate.git(root, "check-ignore", "-q", ".mycelium-extra/") is None:
            print("Warning    .mycelium-extra/ is not in .gitignore; the report holds code diffs. Add it before committing.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
