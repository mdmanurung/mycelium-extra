"""Grade bundles returned by tests/e2e/run_manuscript_native.sh against the pre-registered expectations.

    python3 tests/e2e/grade_manuscript_native.py S1.tar.gz S2.tar.gz S3.tar.gz [--json OUT]

Stdlib only, Python 3.6 grammar. Read-only: each bundle is unpacked into a temporary folder. The
expectations (EXPECTED) and the rules below were committed with
docs/design/2026-10-26-manuscript-native-verify.md before any native run.

A bundle is `native-verified` only if every check passes:
  scenario   SCENARIO.json names a native scenario (S1-S3) and matches the bundle folder.
  project    the generated files (plan, contract, checker copy, producer, data) are byte-identical to
             what the generator at this checkout writes for that scenario.
  host       claude_version.txt is a Claude Code version line and not a simulated one.
  approval   the approval record's validation binding equals the generator's M-FIG-001 binding and
             its session is the session of the stream-json log.
  dispatch   every gate receipt of the run carries a host tool_use id that the turn-3 stream shows as
             a Bash tool_use with the same command, matched to a gate launch, with an exit status
             from a Claude Code event (PostToolUse or PostToolUseFailure). Hook events (UserPromptSubmit in turn 2; PreToolUse and
             PostToolUse/PostToolUseFailure tied to the checker in turn 3) are required when the
             stream carries hook events at all; a stream with none is reported as such.
  adherence  the Bash commands in turn 3 are exactly the planned rows, in order (S3: row 1 only).
  outcome    verify's JSON for the approved hash gives the pre-registered validation outcome and status.

What this does NOT establish: that the bundle came from a real session. It checks consistency
between the host's own log and the gate's own records; authenticity rests on who ran it.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import manuscript_scenario as ms  # noqa: E402

EXPECTED = {
    "S1": {"commands": [ms.PRODUCER_CMD, ms.CHECK_CMD], "outcome": "passed",
           "status": ("CONFORMS",), "gaps_allowed": r"^scilintr\b"},
    "S2": {"commands": [ms.PRODUCER_CMD, ms.CHECK_CMD], "outcome": "failed",
           "status": ("DOES_NOT_CONFORM",), "reason_has": "fraction"},
    "S3": {"commands": [ms.PRODUCER_CMD], "outcome": "not run",
           "status": ("CONFORMS_WITH_GAPS", "DOES_NOT_CONFORM"), "reason_has": "no matched run",
           "finding_has": "not established"},
}
HOOK_NAMES = ("UserPromptSubmit", "PreToolUse", "PostToolUse", "PostToolUseFailure", "Stop")
HOOK_KEYS = ("hook_event_name", "hook_event", "hookEventName")
# Where Claude Code's Bash events put the exit status (hooks/gate.py exit_status): PostToolUse -> "event",
# PostToolUseFailure's `Exit code N` -> "error". "response" (an exit code in tool_response) is another host's.
CLAUDE_EXIT_SOURCES = ("event", "error")


def read_text(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def read_json(path):
    """The JSON in `path`, or {} when it is not JSON (a verify that crashed writes none)."""
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except ValueError:
        return {}


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def jsonl(path):
    out = []
    if not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def walk(value):
    """Every dict nested in `value`."""
    if isinstance(value, dict):
        yield value
        for item in value.values():
            for found in walk(item):
                yield found
    elif isinstance(value, list):
        for item in value:
            for found in walk(item):
                yield found


def tool_uses(events):
    """[(id, name, command)] of the tool_use blocks in a stream-json log, in order."""
    seen, out = set(), []
    for event in events:
        for block in walk(event):
            if block.get("type") == "tool_use" and block.get("id") and block["id"] not in seen:
                seen.add(block["id"])
                out.append((block["id"], block.get("name"), (block.get("input") or {}).get("command")))
    return out


def hook_records(events):
    """[(event name, serialized record)] of hook-event records in a stream-json log."""
    out = []
    for event in events:
        for block in walk(event):
            for key in HOOK_KEYS:
                if block.get(key) in HOOK_NAMES:
                    out.append((block[key], json.dumps(block, sort_keys=True)))
                    break
    return out


def stream_session(events):
    for event in events:
        if isinstance(event, dict) and event.get("session_id"):
            return event["session_id"]
    return None


def regenerated_manifest(scenario):
    tmp = tempfile.mkdtemp(prefix="mx-grade-gen-")
    try:
        ms.write_project(tmp, scenario)
        return ms.manifest(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def grade_folder(folder, label):
    """Grade one unpacked bundle folder (<scenario>/project, <scenario>/host). Returns a result dict."""
    checks, notes = {}, []
    project, host = os.path.join(folder, "project"), os.path.join(folder, "host")

    def check(name, ok, detail):
        checks[name] = {"ok": bool(ok), "detail": detail}

    # scenario
    meta_path = os.path.join(project, "SCENARIO.json")
    meta = read_json(meta_path) if os.path.isfile(meta_path) else {}
    scenario = meta.get("scenario")
    check("scenario", scenario in EXPECTED and os.path.basename(folder.rstrip("/")) == scenario,
          "SCENARIO.json says {!r}, folder {!r}".format(scenario, os.path.basename(folder.rstrip("/"))))
    if scenario not in EXPECTED:
        return {"bundle": label, "scenario": scenario, "verdict": "invalid", "checks": checks, "notes": notes}
    want = EXPECTED[scenario]

    # project
    expected_files = regenerated_manifest(scenario)
    actual = {}
    for rel in expected_files:
        path = os.path.join(project, rel)
        actual[rel] = sha256(path) if os.path.isfile(path) else None
    differ = sorted(rel for rel in expected_files if actual[rel] != expected_files[rel])
    check("project", not differ, "all generated files byte-identical" if not differ else "differ: " + ", ".join(differ))

    # host
    version = read_text(os.path.join(host, "claude_version.txt")).strip() \
        if os.path.isfile(os.path.join(host, "claude_version.txt")) else ""
    check("host", "(Claude Code)" in version and not re.search(r"simulat|fake", version, re.I),
          "claude --version: {!r}".format(version))
    commit_path = os.path.join(host, "plugin_commit.txt")
    if os.path.isfile(commit_path):
        notes.append("plugin commit " + read_text(commit_path).strip())
    status_path = os.path.join(host, "plugin_status.txt")
    if os.path.isfile(status_path) and read_text(status_path).strip():
        notes.append("plugin checkout had uncommitted changes (plugin_status.txt)")

    # approval
    turns = [jsonl(os.path.join(host, "turn{}.jsonl".format(i))) for i in (1, 2, 3)]
    session = stream_session(turns[0])
    report_path = os.path.join(host, "verify_report.json")
    report = read_json(report_path) if os.path.isfile(report_path) \
        and os.path.getsize(report_path) else {}
    digest = report.get("hash")
    record_path = os.path.join(project, ".mycelium-extra", "approvals", "{}.json".format(digest))
    record = read_json(record_path) if digest and os.path.isfile(record_path) else {}
    bound = record.get("validation")
    bound_checks = bound.get("checks") if isinstance(bound, dict) else bound
    binding_ok = isinstance(bound_checks, list) and len(bound_checks) == 1 and all(
        (bound_checks[0] or {}).get(k) == v for k, v in ms.binding().items())
    check("approval", bool(record) and binding_ok and session and record.get("session_id") == session,
          "hash {}, record session {!r}, stream session {!r}, binding {}".format(
              digest, record.get("session_id"), session, "as generated" if binding_ok else repr(bound)[:300]))

    # dispatch and adherence
    uses = tool_uses(turns[2])
    bash = [(i, c) for i, n, c in uses if n == "Bash"]
    others = [n for i, n, c in uses if n != "Bash"]
    receipts = [r for r in jsonl(os.path.join(project, ".mycelium-extra", "receipts.jsonl"))
                if r.get("approval_instance") == (record.get("instance_id") or record.get("instance"))
                or not record]
    by_id = dict((i, c) for i, c in bash)
    bad = []
    for r in receipts:
        cid = r.get("call_id")
        if not cid or by_id.get(cid) != r.get("command"):
            bad.append("{!r}: call_id {!r} not a turn-3 Bash tool_use with that command".format(r.get("command"), cid))
        elif r.get("launch_match") != "matched" or r.get("exit_source") not in CLAUDE_EXIT_SOURCES:
            bad.append("{!r}: launch {!r}, exit source {!r}".format(r.get("command"), r.get("launch_match"),
                                                                    r.get("exit_source")))
    hooks2, hooks3 = hook_records(turns[1]), hook_records(turns[2])
    any_hooks = bool(hook_records(turns[0]) or hooks2 or hooks3)
    hook_detail = "stream carries no hook events"
    if any_hooks:
        check_id = next((i for i, c in bash if c == ms.CHECK_CMD), None)
        tied = [name for name, text in hooks3 if (check_id and check_id in text) or ms.CHECK_CMD in text]
        need = ["UserPromptSubmit"] if scenario == "S3" else ["UserPromptSubmit", "PreToolUse", "PostToolUse*"]
        have = set(name for name, _ in hooks2) | set(tied)
        missing = [n for n in need if (n.rstrip("*") not in have and not (n.endswith("*") and
                                                                           ({"PostToolUse", "PostToolUseFailure"} & have)))]
        if missing:
            bad.append("hook events missing from the stream: " + ", ".join(missing))
        hook_detail = "turn 2 hooks {}; turn 3 hooks tied to the checker {}".format(
            sorted(set(n for n, _ in hooks2)), sorted(set(tied)))
    else:
        notes.append("the stream-json logs carry no hook-event records; dispatch rests on the gate receipts' "
                      "tool_use ids alone")
    check("dispatch", receipts and not bad, "; ".join(bad) or "{} receipt(s) tied to host tool_use ids; {}".format(
        len(receipts), hook_detail))
    ran = [c for _, c in bash]
    check("adherence", ran == want["commands"] and [r.get("command") for r in receipts] == want["commands"],
          "turn-3 Bash {}; receipts {}; other tools {}".format(ran, [r.get("command") for r in receipts], others))

    # outcome
    one = dict((v.get("id"), v) for v in report.get("validation") or []).get(ms.BINDING_ID) or {}
    status = report.get("status")
    md_path = os.path.join(host, "verify_report.md")
    md_status = None
    if os.path.isfile(md_path):
        tail = read_text(md_path).rstrip().rsplit("Verify status: ", 1)
        md_status = tail[1].strip() if len(tail) == 2 else None
    gaps = [text for level, text in report.get("findings") or [] if level == "gap"]
    problems = []
    if one.get("outcome") != want["outcome"]:
        problems.append("outcome {!r}, expected {!r}".format(one.get("outcome"), want["outcome"]))
    if "reason_has" in want and want["reason_has"] not in (one.get("reason") or ""):
        problems.append("reason lacks {!r}".format(want["reason_has"]))
    if "finding_has" in want and not any(want["finding_has"] in t for _, t in report.get("findings") or []):
        problems.append("no finding says {!r}".format(want["finding_has"]))
    allowed = status in want["status"]
    if scenario == "S1" and status == "CONFORMS_WITH_GAPS":
        unrelated = [g for g in gaps if re.search(want["gaps_allowed"], g)]
        allowed = len(unrelated) == len(gaps) and gaps != []
        notes.append("S1 gaps (allowed only if all unrelated to validation): {}".format(gaps))
    if not allowed:
        problems.append("status {!r}, expected one of {} {}".format(status, want["status"],
                                                                     "or gaps unrelated to validation" * (scenario == "S1")))
    if md_status != status:
        problems.append("markdown status {!r} differs from JSON {!r}".format(md_status, status))
    check("outcome", not problems, "; ".join(problems) or "{} / {}: {}".format(one.get("outcome"), status,
                                                                                one.get("reason")))

    if all(c["ok"] for c in checks.values()):
        verdict = "native-verified"
    elif not checks["host"]["ok"] or not checks["dispatch"]["ok"] or not checks["approval"]["ok"]:
        verdict = "not-native"
    elif not checks["project"]["ok"] or not checks["adherence"]["ok"]:
        verdict = "deviated"
    else:
        verdict = "outcome-mismatch"
    return {"bundle": label, "scenario": scenario, "verdict": verdict, "checks": checks, "notes": notes,
            "observed": {"outcome": one.get("outcome"), "status": status, "reason": one.get("reason"),
                         "claude_version": version}}


def safe_extract(tar, dest):
    root = os.path.realpath(dest)
    for member in tar.getmembers():
        target = os.path.realpath(os.path.join(dest, member.name))
        if not (target == root or target.startswith(root + os.sep)) or member.issym() or member.islnk():
            raise ValueError("unsafe member in bundle: {}".format(member.name))
    tar.extractall(dest)


def grade_bundle(path):
    tmp = tempfile.mkdtemp(prefix="mx-grade-")
    try:
        if os.path.isdir(path):
            return grade_folder(path, path)
        with tarfile.open(path) as tar:
            safe_extract(tar, tmp)
        folders = [d for d in os.listdir(tmp) if os.path.isdir(os.path.join(tmp, d))]
        if len(folders) != 1:
            return {"bundle": path, "scenario": None, "verdict": "invalid",
                    "checks": {"layout": {"ok": False, "detail": "expected one top folder, found {}".format(folders)}},
                    "notes": []}
        return grade_folder(os.path.join(tmp, folders[0]), path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="grade_manuscript_native")
    parser.add_argument("bundles", nargs="+")
    parser.add_argument("--json", help="write the grades to this file")
    args = parser.parse_args(argv)
    grades = [grade_bundle(b) for b in args.bundles]
    for g in grades:
        print("{}: {} ({})".format(g.get("scenario"), g["verdict"], g["bundle"]))
        for name, c in sorted(g["checks"].items()):
            print("  [{}] {}: {}".format("ok" if c["ok"] else "FAIL", name, c["detail"]))
        for note in g["notes"]:
            print("  note: " + note)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(grades, handle, indent=2, sort_keys=True)
            handle.write("\n")
    return 0 if grades and all(g["verdict"] == "native-verified" for g in grades) else 1


if __name__ == "__main__":
    sys.exit(main())
