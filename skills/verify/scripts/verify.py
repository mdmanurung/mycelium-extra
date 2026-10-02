"""Check an approved grill plan against what ran, and write its provenance.

Stdlib-only; runs on Python 3.6+. Run it from stdin, inside the repository, so
Mycelium's hooks do not open the post-action cycle:

    python3 - --plugin-root <root> list < verify.py
    python3 - --plugin-root <root> report <hash> [--analysis-dir DIR] [--json] < verify.py
    python3 - --plugin-root <root> write <hash> --analysis-dir DIR < verify.py

It reuses the approval gate's own parsers (`<root>/hooks/gate.py`), so a plan
covers here exactly the scripts it let through. `report` only reads. `write`
copies the frozen plan, its run receipts, and the report into
DIR/provenance/, after the user confirms. Output never repeats the plan's
status line, so a reply quoting it is not offered for approval as a new plan.
"""

import argparse
import base64
import collections
import glob
import json
import os
import re
import subprocess
import sys
import time

gate = None  # the approval gate module, loaded from --plugin-root
PLUGIN_ROOT = None

OUTPUTS_LINE = re.compile(r"^[\s>*_`-]*outputs[\s*_`]*:(.*)$", re.IGNORECASE | re.MULTILINE)
OUTPUT_WORD = re.compile(r"[\w./~*?\[\]-]+")
STEP_FOLDERS = {"code", "scripts", "src", "R", "py", "python", "workflow", "notebooks", "steps", "bin"}
SKIP_FOLDERS = {"provenance", "logs", "outputs", "results", "_archive", "archive", "__pycache__"}
FAILED_JOB = {"FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL", "PREEMPTED", "BOOT_FAIL",
              "DEADLINE"}
LOOKUP = re.compile(r"^command\s+-[vV]\b")  # older receipts recorded these as runs
SNAKE_RULE = re.compile(r"^\s*rule\s+(\w+)\s*:", re.MULTILINE)
TOLERANCE = 5  # seconds of clock skew between the hook and the filesystem
MAX_FILES = 5000
SHOWN_OUTPUTS = 40
LIMITS = [
    "A receipt's time is when the gate's hook fired. A run Claude Code moved to the background "
    "writes its outputs after that, so such outputs show as not tied to a run.",
    "Mycelium's lineage covers finished Mycelium sessions only.",
    "Code run through MCP notebook tools (`nb_*_execute`) bypasses both the gate and the lineage.",
    "A run of a planned script proves it ran, not that it implements the plan's choices; "
    "that is what the review step checks.",
]


# ---------------------------------------------------------------- loading

def load_gate(plugin_root):
    global gate, PLUGIN_ROOT
    PLUGIN_ROOT = os.path.abspath(plugin_root)
    path = os.path.join(PLUGIN_ROOT, "hooks", "gate.py")
    if not os.path.isfile(path):
        sys.exit("verify: {} not found. verify reads the mycelium-extra approval gate's receipts "
                 "(Claude Code only); pass --plugin-root <the plugin folder>.".format(path))
    sys.path.insert(0, os.path.dirname(path))
    sys.dont_write_bytecode = True  # leave no __pycache__ in the plugin folder
    import gate as module
    gate = module


def read_jsonl(path):
    records = []
    if os.path.isfile(path):
        with open(path) as handle:
            for line in handle:
                try:
                    records.append(json.loads(line))
                except ValueError:
                    continue
    return records


def parse_iso(text):
    """Epoch seconds for 2026-09-30T08:39:36Z, +0200, +02:00, or naive (UTC)."""
    m = re.match(r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(?:\.\d+)?(Z|[+-]\d{2}:?\d{2})?$",
                 (text or "").strip())
    if not m:
        return None
    import calendar
    seconds = calendar.timegm(time.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M:%S"))
    zone = m.group(3)
    if zone and zone != "Z":
        digits = zone[1:].replace(":", "")
        offset = int(digits[:2]) * 3600 + int(digits[2:]) * 60
        seconds -= offset if zone[0] == "+" else -offset
    return seconds


def when(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else "?"


def rel_or_abs(root, path):
    path = os.path.normpath(path if os.path.isabs(path) else os.path.join(root, path))
    rel = os.path.relpath(path, root)
    return path if rel.startswith("..") else rel.replace(os.sep, "/")


def under(path, folder):
    return path == folder or path.startswith(folder.rstrip("/") + "/")


# ---------------------------------------------------------------- outside records

def sacct_state(sacct, job_id, since):
    """The job's final state from sacct, or None when sacct cannot be run."""
    day = time.strftime("%Y-%m-%d", time.localtime(since))
    try:
        proc = subprocess.Popen([sacct, "-j", str(job_id), "-n", "-P", "-X", "-S", day,
                                 "-o", "JobID,State,ExitCode,Start,End"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        out, _ = proc.communicate(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        return None
    except (OSError, ValueError):
        return None
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) >= 5 and parts[0].split(".")[0] == str(job_id):
            end = parts[4] if re.match(r"^\d{4}-", parts[4]) else None
            return {"state": parts[1].split()[0] if parts[1] else "UNKNOWN", "exit": parts[2],
                    "end": time.mktime(time.strptime(end, "%Y-%m-%dT%H:%M:%S")) if end else None}
    return {"state": "NOT_FOUND", "exit": None, "end": None}


def decode_name(encoded):
    padded = encoded + "=" * (-len(encoded) % 4)
    for decode in (base64.urlsafe_b64decode, base64.b64decode):
        try:
            return decode(padded.encode("ascii")).decode("utf-8")
        except (ValueError, UnicodeError):
            continue
    return None


def snakemake_records(folders, since):
    """Snakemake's per-output records (rule, start, end, command) written since `since`."""
    records = []
    for meta in folders:
        workdir = os.path.dirname(os.path.dirname(meta))
        for folder, _, files in os.walk(meta):
            for name in files:
                full = os.path.join(folder, name)
                try:
                    if os.stat(full).st_mtime < since - TOLERANCE:
                        continue
                    with open(full) as handle:
                        data = json.load(handle)
                except (OSError, ValueError):
                    continue
                path = decode_name(os.path.relpath(full, meta).replace(os.sep, ""))
                if path is None:
                    continue
                inputs = data.get("input") or []
                records.append({
                    "path": os.path.normpath(path if os.path.isabs(path) else os.path.join(workdir, path)),
                    "rule": data.get("rule"),
                    "start": float(data.get("starttime") or 0),
                    "end": float(data.get("endtime") or 0),
                    "incomplete": data.get("incomplete") in (True, "True", "true"),
                    # The step script is an input (`{input.script}`) and appears in the expanded command.
                    "command": "\n".join([data.get("shellcmd") or "", data.get("code") or ""]
                                         + [str(i) for i in (inputs if isinstance(inputs, list) else [inputs])]),
                    "workdir": workdir,
                })
    return records


def lineage_actions(root, start, end):
    actions = []
    for path in sorted(glob.glob(os.path.join(root, ".living", "log", "data-lineage", "*.json"))):
        try:
            with open(path) as handle:
                manifest = json.load(handle)
        except (OSError, ValueError):
            continue
        for action in manifest.get("actions") or []:
            ts = parse_iso(action.get("ts"))
            if ts is not None and start - TOLERANCE <= ts <= end + TOLERANCE:
                actions.append(dict(action, epoch=ts, session=manifest.get("session_id")))
    return actions


# ---------------------------------------------------------------- the check

class Report(object):
    def __init__(self):
        self.findings = []

    def add(self, level, text):
        self.findings.append((level, text))

    def status(self):
        levels = {level for level, _ in self.findings}
        return "DOES_NOT_CONFORM" if "block" in levels else "CONFORMS_WITH_GAPS" if "gap" in levels \
            else "CONFORMS"


def guess_analysis_dir(files):
    if not files:
        return None
    common = os.path.dirname(files[0]) if len(files) == 1 else os.path.commonpath(files)
    if common in files:
        common = os.path.dirname(common)
    while os.path.basename(common) in STEP_FOLDERS and common.count("/") >= 2:
        common = os.path.dirname(common)
    return common if common.count("/") >= 1 else None


def plan_outputs(plan):
    """Words on the plan's `Outputs:` lines; None without the line, [] for `none`."""
    lines = OUTPUTS_LINE.findall(plan)
    if not lines:
        return None
    words = []
    for line in lines:
        for word in OUTPUT_WORD.findall(line):
            word = word.rstrip(".,;:")
            if word.startswith("./"):
                word = word[2:]
            if word and word.lower() != "none" and word not in words and ("/" in word or "." in word):
                words.append(word)
    return words


def expand_outputs(root, words):
    """Map each named output to (its files, whether it names one file exactly).

    Folders and globs are expanded; provenance/ and hidden folders are skipped,
    so naming the analysis folder does not list verify's own files."""
    expanded = {}
    for word in words:
        pattern = os.path.join(root, word)
        matches = sorted(glob.glob(pattern)) if re.search(r"[*?\[]", word) else \
            ([pattern] if os.path.exists(pattern) else [])
        files = []
        for match in matches:
            if os.path.isdir(match):
                for folder, dirs, names in os.walk(match):
                    dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "provenance")
                    files += [os.path.join(folder, n) for n in sorted(names) if not n.startswith(".")]
            else:
                files.append(match)
        exact = not re.search(r"[*?\[]", word) and os.path.isfile(pattern)
        expanded[word] = ([rel_or_abs(root, f) for f in files[:MAX_FILES]], exact)
    return expanded


def mentions(command, root, rel, workdir):
    """Whether a Snakemake command line runs the repository file `rel`."""
    full = os.path.join(root, rel)
    names = {full, rel, os.path.relpath(full, workdir)}
    return any(re.search(r"(^|[\s'\"=])" + re.escape(name) + r"($|[\s'\"])", command) for name in names)


def is_snakefile(path):
    return os.path.basename(path).startswith("Snakefile") or path.endswith(".smk")


def read_text(path):
    try:
        with open(path, errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


def ran_paths(receipt):
    """The receipt's paths that ran as the program. A path handed to `-e`/`-c` code or to a
    program read from stdin (a lint call, a parse check, another tool's script) did not run."""
    paths = receipt.get("paths", [])
    words = receipt.get("command", "").split()
    head = next((i for i, w in enumerate(words) if gate.RUNNERS.match(os.path.basename(w))), None)
    for word in words[head + 1:] if head is not None else []:
        if word in ("-c", "-e", "--eval", "-", "<"):
            cwd = receipt.get("cwd") or "."
            stdin = {os.path.normpath(os.path.join(cwd, words[k + 1]))
                     for k in range(len(words) - 1) if words[k] == "<"}
            return [p for p in paths if p in stdin]
        if not word.startswith("-"):
            break
    return paths


def is_run(receipt, commands):
    """False for a `command -v` lookup and for a receipt whose paths were only handed to other code."""
    if LOOKUP.match(receipt.get("command", "")):
        return False
    return receipt.get("kind") in commands or bool(ran_paths(receipt))


def is_wrapper(receipt):
    """A run that starts other steps: a shell script, Snakemake, Nextflow, or a Slurm job."""
    return receipt.get("kind") in ("bash", "sh", "zsh", "snakemake", "nextflow", "sbatch") or any(
        p.endswith((".sh", "Snakefile", ".smk")) for p in receipt.get("paths", []))


def wrapper_receipt(receipts, record):
    """The first recorded wrapper run that ended after a Snakemake job finished: the run it was in."""
    later = [r for r in receipts if r.get("ts", 0) >= record["end"] - TOLERANCE and is_wrapper(r)]
    return min(later, key=lambda r: r["ts"]) if later else None


def describe_run(receipt, digest):
    if receipt is None:
        return "no recorded run"
    label = "`{}` at {}".format(receipt.get("command", "")[:80], when(receipt.get("ts")))
    if receipt.get("explore"):
        return label + " (explore, not reportable)"
    if digest in receipt.get("plans", []):
        return label
    if receipt.get("plans"):
        return label + " (under plan {})".format(receipt["plans"][-1])
    return label + " (no approved plan)"


def check(root, digest, analysis_dir=None, sacct="sacct", hash_mb=2000, seconds=120):
    config = gate.load_config(root)
    approval = gate.read_json(gate.state_path(root, "approvals", digest + ".json"), None)
    if approval is None:
        sys.exit("verify: no approved plan {}. Run `list` to see approved plans.".format(digest))
    plan, approved_at = approval.get("plan", ""), approval.get("approved_at", 0)
    table = gate.plan_table(plan)
    named = sorted(p for p in gate.plan_paths(table) if gate.gated_rel(root, root, p, config))
    planned = [p for p in named if os.path.isfile(os.path.join(root, p)) or gate.SCRIPT_EXT.search(p)]
    folders = [p for p in named if p not in planned]
    commands = [c for c in config["gated_commands"] if gate.names_command(c, table)]
    analysis_dir = rel_or_abs(root, analysis_dir) if analysis_dir else guess_analysis_dir(planned)
    budget = {"bytes": float(hash_mb) * 1024 * 1024, "deadline": time.time() + seconds}

    receipts, handed = [], []
    for r in read_jsonl(gate.state_path(root, "receipts.jsonl")):
        if is_run(r, config["gated_commands"]):
            receipts.append(r)
        elif not LOOKUP.match(r.get("command", "")):
            handed.append(r)
    handed = [r for r in handed if digest in r.get("plans", []) and not r.get("explore")]
    # Re-approving the same plan text rewrites approved_at, so the plan's runs are every
    # non-explore receipt naming it, and its window opens at the earliest of them.
    mine = sorted((r for r in receipts if digest in r.get("plans", []) and not r.get("explore")),
                  key=lambda r: r["ts"])
    start = min([approved_at] + [r["ts"] for r in mine])
    since = sorted((r for r in receipts if r.get("ts", 0) >= start - TOLERANCE), key=lambda r: r["ts"])
    jobs = {}
    for r in mine:
        if r.get("job_id"):
            jobs[r["job_id"]] = sacct_state(sacct, r["job_id"], r["ts"])

    meta = {os.path.join(root, ".snakemake", "metadata")}
    for folder in ([analysis_dir] if analysis_dir else []) + folders + [os.path.dirname(p) for p in planned]:
        meta.add(os.path.join(root, folder, ".snakemake", "metadata"))  # a wrapper may `cd` there first
    for r in mine:
        record = (r.get("engine") or {}).get("record")
        if record:
            meta.add(os.path.normpath(os.path.join(root, r.get("cwd") or ".", record)))
    smk = snakemake_records(sorted(m for m in meta if os.path.isdir(m)), start)

    report = Report()
    scripts = []
    for path in planned:
        row = {"path": path, "status": "no receipt", "last_run": None, "notes": []}
        direct = [r for r in mine if path in ran_paths(r)]
        inside = [m for m in smk if mentions(m["command"], root, path, m["workdir"])]
        if not inside and is_snakefile(path):
            rules = set(SNAKE_RULE.findall(read_text(os.path.join(root, path))))
            folder = os.path.normpath(os.path.join(root, os.path.dirname(path)))
            inside = [m for m in smk if m["rule"] in rules and os.path.normpath(m["workdir"]) == folder]
        if direct:
            last = direct[-1]
            row["last_run"] = last["ts"]
            job = jobs.get(last.get("job_id")) if last.get("job_id") else None
            code = last.get("exit_status")
            if isinstance(code, int) and code != 0:
                row["status"] = "failed (exit {})".format(code)
                report.add("block", "`{}` failed (exit {}) at {}.".format(path, code, when(last["ts"])))
            elif last.get("job_id"):
                state = (job or {}).get("state")
                row["status"] = "job {} {}".format(last["job_id"], state or "state unknown (no sacct)")
                if state in FAILED_JOB:
                    report.add("block", "`{}`: Slurm job {} ended {}.".format(path, last["job_id"], state))
                elif state != "COMPLETED":
                    report.add("gap", "`{}`: Slurm job {} is {}; check `sacct -j {}`.".format(
                        path, last["job_id"], state or "of unknown state", last["job_id"]))
            else:
                row["status"] = "ran" if code == 0 else "ran (exit status not recorded)"
            recorded = last.get("script") or {}
            if recorded.get("path") == path and not recorded.get("missing"):
                now = gate.fingerprint(os.path.join(root, path), budget, pin=recorded)
                if now.get("missing"):
                    row["notes"].append("deleted since it ran")
                    report.add("block", "`{}` was deleted after its run at {}, so its outputs cannot be "
                                        "checked against the code.".format(path, when(last["ts"])))
                elif not gate.unchanged(recorded, now):
                    row["notes"].append("edited since it ran")
                    report.add("block", "`{}` was edited after its run at {}, so its outputs may not "
                                        "match the code.".format(path, when(last["ts"])))
                if recorded.get("git") in ("modified", "untracked"):
                    row["notes"].append("{} when it ran".format(recorded["git"]))
                    report.add("gap", "`{}` was {} when it ran, so no commit holds the code that ran."
                               .format(path, recorded["git"]))
        elif inside:
            last = max(inside, key=lambda m: m["end"])
            owner = wrapper_receipt(since, last)
            row["last_run"] = last["end"]
            row["status"] = "ran in Snakemake rule `{}`".format(last["rule"])
            row["notes"].append("inside " + describe_run(owner, digest))
            if last["incomplete"]:
                report.add("block", "`{}`: Snakemake marks rule `{}` incomplete.".format(path, last["rule"]))
            if owner is None or owner.get("explore") or digest not in owner.get("plans", []):
                report.add("gap", "`{}` ran in Snakemake rule `{}` inside {}.".format(
                    path, last["rule"], describe_run(owner, digest)))
            try:
                if os.stat(os.path.join(root, path)).st_mtime > last["start"] + TOLERANCE:
                    row["notes"].append("edited since it ran")
                    report.add("block", "`{}` was edited after its Snakemake run at {}.".format(
                        path, when(last["end"])))
            except OSError:
                pass
        elif any(path in r.get("paths", []) for r in handed):
            last = [r for r in handed if path in r.get("paths", [])][-1]
            row["status"] = "not run: only passed to other code"
            report.add("gap", "`{}` was only passed to other code (last: `{}` at {}), never run itself; "
                              "lint and parse calls look like this.".format(
                                  path, last.get("command", "")[:80], when(last["ts"])))
        else:
            report.add("gap", "`{}`: no run under this plan was recorded.".format(path))
        if direct and is_wrapper(direct[-1]):
            steps = [m for m in smk if m["start"] >= start - TOLERANCE]
            if steps:
                row["notes"].append("wrapper: {} Snakemake job(s) ran inside".format(len(steps)))
            else:
                row["notes"].append("wrapper")
                report.add("gap", "`{}` is a wrapper, and no Snakemake records show which steps ran "
                                  "inside it.".format(path))
        scripts.append(row)

    if handed:
        report.add("info", "{} receipt(s) under this plan only passed planned paths to other code "
                           "(`-e`/`-c` code or a program read from stdin) and are not counted as runs."
                   .format(len(handed)))
    for folder in folders:
        runs = [r for r in mine if any(under(p, folder) for p in ran_paths(r))]
        report.add("info", "Folder `{}/` is planned as a whole; {} run(s) in it.".format(folder, len(runs)))
    for command in commands:
        runs = [r for r in mine if r.get("kind") == command]
        if not runs:
            report.add("gap", "The plan names `{}`, but no `{}` run under it was recorded.".format(
                command, command))

    # Runs in the analysis folder that this plan does not cover, and scripts it does not name.
    unplanned_files = []
    if analysis_dir:
        for r in since:
            if r in mine or not any(under(p, analysis_dir) for p in ran_paths(r)):
                continue
            if r.get("explore"):
                report.add("gap", "Explore run in the analysis folder: {}.".format(describe_run(r, digest)))
            elif r.get("plans"):
                report.add("info", "Run under another plan: {}.".format(describe_run(r, digest)))
            else:
                report.add("gap", "Run with no approved plan: {}.".format(describe_run(r, digest)))
        top = os.path.join(root, analysis_dir)
        for folder, dirs, names in os.walk(top):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in SKIP_FOLDERS)
            for name in sorted(names):
                rel = rel_or_abs(root, os.path.join(folder, name))
                if gate.SCRIPT_EXT.search(rel) and rel not in planned \
                        and not any(under(rel, f) for f in folders):
                    unplanned_files.append(rel)
        ran = [rel for rel in unplanned_files  # explore runs are reported above
               if any(rel in ran_paths(r) and not r.get("explore") for r in since)
               or any(mentions(m["command"], root, rel, m["workdir"]) for m in smk)]
        for rel in ran:
            report.add("gap", "`{}` ran since the approval but is not in the plan table.".format(rel))
        idle = len(unplanned_files) - len(ran)
        if idle:
            report.add("info", "{} other script(s) in the analysis folder are not in the plan, and no "
                               "run of them since the approval was recorded.".format(idle))

    inputs = []
    for rel, pin in sorted((approval.get("pins") or {}).items()):
        now = gate.fingerprint(os.path.join(root, rel), budget, pin=pin)
        changed = not gate.unchanged(pin, now)
        inputs.append({"path": rel, "pinned": gate.describe(pin), "now": gate.describe(now),
                       "changed": changed})
        if changed:
            report.add("block", "Input `{}` changed since the approval (was {}, now {}).".format(
                rel, gate.describe(pin), gate.describe(now)))
        elif now.get("skipped"):
            report.add("gap", "Input `{}` could not be re-checked (time limit).".format(rel))

    outputs = []
    words = plan_outputs(plan)
    if words is None:
        report.add("gap", "The plan has no `Outputs:` line, so its results cannot be tied to its runs.")
    else:
        listed = set()
        for word, (files, exact) in expand_outputs(root, words).items():
            local = os.path.join(analysis_dir, word) if analysis_dir else None
            if not files and local and expand_outputs(root, [local])[local][0]:
                files, exact = expand_outputs(root, [local])[local]
                report.add("info", "Output `{}` read as `{}`; Outputs lines take repository paths.".format(
                    word, local))
            if not exact:  # code in a named folder is tracked as scripts, not outputs
                files = [f for f in files if not (gate.SCRIPT_EXT.search(f) or is_snakefile(f))]
            if not files:
                report.add("gap", "Output `{}` does not exist.".format(word))
            older = 0
            for rel in files:
                full = os.path.join(root, rel)
                try:
                    mtime = os.stat(full).st_mtime
                except OSError:
                    continue
                if rel in listed:
                    continue
                if mtime < start - TOLERANCE and not exact:
                    older += 1  # earlier runs' files in a named folder or glob
                    continue
                listed.add(rel)
                record = next((m for m in smk if m["path"] == os.path.normpath(full)), None)
                if record:
                    owner = wrapper_receipt(since, record)
                    via = "Snakemake rule `{}`".format(record["rule"])
                else:
                    later = [r for r in since if r.get("ts", 0) >= mtime - TOLERANCE and not r.get("job_id")]
                    batch = [r for r in since if r.get("job_id") and r["ts"] <= mtime + TOLERANCE
                             and ((jobs.get(r["job_id"]) or {}).get("end") or time.time()) >= mtime - TOLERANCE]
                    owner = min(later, key=lambda r: r["ts"]) if later else (batch[-1] if batch else None)
                    via = None
                fingerprint = gate.fingerprint(full, budget)
                outputs.append({"path": rel, "written": mtime, "by": describe_run(owner, digest), "rule": via,
                                "fingerprint": gate.describe(fingerprint), "record": fingerprint})
                if mtime < start - TOLERANCE:
                    report.add("block", "Output `{}` was written {}, before the plan was approved.".format(
                        rel, when(mtime)))
                elif owner is None:
                    report.add("gap", "Output `{}` (written {}) is not tied to any recorded run: a run "
                                      "moved to the background, or computation the gate did not see."
                               .format(rel, when(mtime)))
                elif owner.get("explore") or digest not in owner.get("plans", []):
                    report.add("gap", "Output `{}` was likely written by {}.".format(
                        rel, describe_run(owner, digest)))
            if older:
                report.add("info", "{} file(s) under `{}` predate this plan, so they are earlier runs' "
                                   "outputs and were not checked.".format(older, word))

    seen = {p for r in since for p in ran_paths(r)}
    plugins = [os.path.realpath(p) for p in (PLUGIN_ROOT, os.path.expanduser("~/.claude/plugins"),
                                              os.path.expanduser("~/.codex/plugins"))]
    inline = 0
    for action in lineage_actions(root, start, time.time()):
        script = action.get("script")
        if not script:
            inline += 1
            continue
        rel = rel_or_abs(root, script)
        if any(under(os.path.realpath(script), p) for p in plugins):
            continue  # Mycelium's and this plugin's own scripts
        if rel not in seen and rel not in planned:
            report.add("gap", "Mycelium's lineage saw `{}` run at {}, which the gate did not record."
                       .format(rel, when(action["epoch"])))
    if inline:
        report.add("info", "{} inline command(s) ran in the window (Mycelium lineage); read-only "
                           "probes are typical, and they are not checked.".format(inline))

    return {"hash": digest, "approved_at": approved_at, "start": start, "session_id": approval.get("session_id"),
            "analysis_dir": analysis_dir, "git": gate.git_state(root), "runs": len(mine),
            "scripts": scripts, "folders": folders, "commands": commands, "inputs": inputs,
            "outputs": outputs, "outputs_named": words, "findings": report.findings,
            "status": report.status(), "receipts": mine, "plan": plan}


# ---------------------------------------------------------------- output

def cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def render(result, all_outputs=False):
    git = result["git"]
    head = "HEAD {} ({})".format(git["head"][:12], "uncommitted changes" if git.get("dirty") else "clean") \
        if git else "not a git repository"
    lines = [
        "# Verify plan {}".format(result["hash"]),
        "",
        "Approved {}{} · analysis folder `{}` · {} run(s) under this plan · {}".format(
            when(result["approved_at"]),
            " (re-approved; first run {})".format(when(result["start"]))
            if result["start"] < result["approved_at"] - TOLERANCE else "",
            result["analysis_dir"] or "?", result["runs"], head),
        "",
        "## Planned scripts",
        "",
        "| Script | Status | Last run | Notes |",
        "|---|---|---|---|",
    ]
    for row in result["scripts"]:
        lines.append("| `{}` | {} | {} | {} |".format(cell(row["path"]), cell(row["status"]),
                                                     when(row["last_run"]), cell("; ".join(row["notes"]))))
    if not result["scripts"]:
        lines.append("| (none named in the plan table) | | | |")
    if result["inputs"]:
        lines += ["", "## Pinned inputs", "", "| Input | Pinned | Now |", "|---|---|---|"]
        for row in result["inputs"]:
            lines.append("| `{}` | {} | {}{} |".format(cell(row["path"]), row["pinned"], row["now"],
                                                      " (changed)" if row["changed"] else ""))
    lines += ["", "## Outputs", ""]
    if result["outputs_named"] is None:
        lines.append("The plan has no `Outputs:` line.")
    elif not result["outputs"]:
        lines.append("No output files found for: {}.".format(", ".join(result["outputs_named"]) or "none"))
    else:
        shown = result["outputs"] if all_outputs else result["outputs"][:SHOWN_OUTPUTS]
        lines += ["| Output | Written | By | Fingerprint |", "|---|---|---|---|"]
        for row in shown:
            by = row["by"] + (" via " + row["rule"] if row["rule"] else "")
            lines.append("| `{}` | {} | {} | {} |".format(cell(row["path"]), when(row["written"]), cell(by),
                                                          row["fingerprint"]))
        if len(shown) < len(result["outputs"]):
            lines.append("")
            lines.append("{} more output file(s); `write` records them all.".format(
                len(result["outputs"]) - len(shown)))
    lines += ["", "## Findings", ""]
    order = {"block": 0, "gap": 1, "info": 2}
    for level, text in sorted(result["findings"], key=lambda f: order[f[0]]):
        lines.append("- **{}**: {}".format(level, text))
    if not result["findings"]:
        lines.append("- none")
    lines += ["", "## Not visible to verify", ""] + ["- " + text for text in LIMITS]
    lines += ["", "Verify status: " + result["status"]]
    return "\n".join(lines) + "\n"


def write(root, result):
    folder = os.path.join(root, result["analysis_dir"], "provenance")
    if not os.path.isdir(os.path.join(root, result["analysis_dir"])):
        sys.exit("verify: analysis folder {} does not exist.".format(result["analysis_dir"]))
    os.makedirs(folder, exist_ok=True)
    digest = result["hash"]
    stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime())
    paths = {"plan": "plan-{}.md".format(digest), "receipts": "receipts-{}.jsonl".format(digest),
             "outputs": "outputs-{}.tsv".format(digest), "report": "verify-{}.md".format(digest)}
    with open(os.path.join(folder, paths["plan"]), "w") as handle:
        handle.write("# Approved plan {}\n\nApproved {} in Claude Code session {}. Frozen copy of the plan "
                     "the mycelium-extra gate approved; do not edit it. Revise the analysis's own plan "
                     "instead.\n\n---\n\n{}\n".format(digest, when(result["approved_at"]),
                                                      result["session_id"], result["plan"].rstrip()))
    with open(os.path.join(folder, paths["receipts"]), "w") as handle:
        for receipt in result["receipts"]:
            handle.write(json.dumps(receipt, sort_keys=True) + "\n")
    with open(os.path.join(folder, paths["outputs"]), "w") as handle:
        handle.write("path\twritten\tsize\tsha256\tfingerprint\twritten_by\n")
        for row in result["outputs"]:
            record = row["record"]
            handle.write("\t".join(str(v) for v in [
                row["path"], time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(row["written"])),
                record.get("size", ""), record.get("sha256", ""), gate.method(record),
                row["by"] + (" via " + row["rule"] if row["rule"] else "")]) + "\n")
    with open(os.path.join(folder, paths["report"]), "w") as handle:
        handle.write("Written {} by mycelium-extra verify.\n\n".format(stamp))
        handle.write(render(result, all_outputs=True))
    index = os.path.join(folder, "PROVENANCE.md")
    row = "| {} | {} | {} | {} | [plan]({}) · [receipts]({}) · [outputs]({}) · [report]({}) |".format(
        digest, when(result["approved_at"]), stamp, result["status"], paths["plan"], paths["receipts"],
        paths["outputs"], paths["report"])
    if os.path.isfile(index):
        with open(index) as handle:
            lines = [line.rstrip("\n") for line in handle if not line.startswith("| {} |".format(digest))]
    else:
        lines = ["# Provenance", "",
                 "One row per approved plan checked for this analysis by mycelium-extra verify. Each plan's "
                 "frozen text, its run receipts, and the check sit beside this file.", "",
                 "| Plan | Approved | Verified | Status | Files |", "|---|---|---|---|---|"]
    lines.append(row)
    with open(index, "w") as handle:
        handle.write("\n".join(lines) + "\n")
    rel = os.path.relpath(folder, root)
    return [os.path.join(rel, name) for name in ["PROVENANCE.md"] + list(paths.values())]


def list_plans(root):
    receipts = read_jsonl(gate.state_path(root, "receipts.jsonl"))
    folder = gate.state_path(root, "approvals")
    config = gate.load_config(root)
    runs = collections.Counter(digest for r in receipts if not r.get("explore")
                               for digest in set(r.get("plans", [])))
    rows = []
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        record = gate.read_json(os.path.join(folder, name), None)
        if not record:
            continue
        digest = record.get("hash", name[:8])
        table = gate.plan_table(record.get("plan", ""))
        scripts = [p for p in gate.plan_paths(table) if gate.gated_rel(root, root, p, config)]
        rows.append((record.get("approved_at", 0), digest, len(scripts), runs[digest]))
    lines = ["| Plan | Approved | Scripts in table | Runs |", "|---|---|---|---|"]
    for approved, digest, scripts, count in sorted(rows, reverse=True):
        lines.append("| {} | {} | {} | {} |".format(digest, when(approved), scripts, count))
    return "\n".join(lines) + "\n"


def main(argv):
    parser = argparse.ArgumentParser(prog="verify")
    parser.add_argument("--plugin-root", required=True)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--sacct", default="sacct")
    parser.add_argument("--hash-mb", type=float, default=2000)
    parser.add_argument("--seconds", type=float, default=120)
    parser.add_argument("action", choices=["list", "report", "write"])
    parser.add_argument("hash", nargs="?")
    parser.add_argument("--analysis-dir")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    load_gate(args.plugin_root)
    root = gate.find_root(os.path.abspath(args.repo))
    if root is None:
        sys.exit("verify: the approval gate is not on in this repository (no gate.json found).")
    if args.action == "list":
        sys.stdout.write(list_plans(root))
        return 0
    if not args.hash or not re.match(r"^[0-9a-f]{8}$", args.hash):
        sys.exit("verify: give the plan's 8-character hash (see `list`).")
    if args.action == "write" and not args.analysis_dir:
        sys.exit("verify: `write` needs --analysis-dir, confirmed by the user.")
    result = check(root, args.hash, args.analysis_dir, args.sacct, args.hash_mb, args.seconds)
    if args.action == "write":
        written = write(root, result)
        for path in written:
            print("wrote " + path)
        if gate.git(root, "check-ignore", "-q", written[0]) is not None:
            print("warning: git ignores {}, so these files will not be committed with the analysis."
                  .format(os.path.dirname(written[0])))
        print("Verify status: " + result["status"])
        return 0
    if args.json:
        shown = dict(result, plan=None, receipts=len(result["receipts"]))
        sys.stdout.write(json.dumps(shown, indent=1, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
