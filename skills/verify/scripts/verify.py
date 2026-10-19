"""Check an approved grill plan against what ran, and write its provenance.

Stdlib-only; runs on Python 3.9+. Run it from stdin, inside the repository, so
Mycelium's hooks do not open the post-action cycle:

    sh <root>/hooks/py.sh - --plugin-root <root> list < verify.py
    sh <root>/hooks/py.sh - --plugin-root <root> report <hash> [--analysis-dir DIR] [--claims DOC] [--instance ID] [--require-reportable] [--resolve-citations [--contact EMAIL]] [--json] < verify.py
    sh <root>/hooks/py.sh - --plugin-root <root> disclose <hash> [--analysis-dir DIR] [--resolve-citations [--contact EMAIL]] < verify.py
    sh <root>/hooks/py.sh - --plugin-root <root> write <hash> --analysis-dir DIR [--claims DOC] [--require-reportable] < verify.py
    sh <root>/hooks/py.sh - --plugin-root <root> stale [--content] [--json] < verify.py
    sh <root>/hooks/py.sh - --plugin-root <root> status [--json] < verify.py
    sh <root>/hooks/py.sh - --plugin-root <root> explore [--session ID | --all] [--json] < verify.py
    sh <root>/hooks/py.sh - --plugin-root <root> runs [RESULTS_DIR] [--json] < verify.py
    sh <root>/hooks/py.sh - --plugin-root <root> diff <old-hash> <new-hash> < verify.py
    sh <root>/hooks/py.sh - --plugin-root <root> multiplicity <hash> [--json] < verify.py

It reuses the approval gate's own parsers (`<root>/hooks/gate.py`), so a plan
covers here exactly the scripts it let through. `report` only reads. `write`
copies the frozen plan, its run receipts, and the report into
DIR/provenance/, after the user confirms. Output never repeats the plan's
status line, so a reply quoting it is not offered for approval as a new plan.
"""

import argparse
import base64
import bisect
import collections
import csv
import datetime
import decimal
import glob
import hashlib
import io
import json
import math
import os
import pickletools
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

gate = None  # the approval gate module, loaded from --plugin-root
PLUGIN_ROOT = None

STEP_FOLDERS = {"code", "scripts", "src", "R", "py", "python", "workflow", "notebooks", "steps", "bin"}
SKIP_FOLDERS = {"provenance", "logs", "outputs", "results", "_archive", "archive", "__pycache__"}
EXIT_CONFLICT = "COMPLETED_NONZERO_EXIT"  # sacct's State says COMPLETED but its ExitCode is not 0:0
EXIT_UNREADABLE = "COMPLETED_UNREADABLE_EXIT"  # State COMPLETED, ExitCode present but not `N:M`
FAILED_JOB = {"FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL", "PREEMPTED", "BOOT_FAIL",
              "DEADLINE", EXIT_CONFLICT}
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
    "Claims are checked only where a document's `<!-- claims -->` block names the output cell; other "
    "numbers in the text are listed, not checked, and a verified claim matches its cell, not the truth.",
    "A resolved citation shows that the identifier exists and that its title and first author appear in "
    "the citation text; it does not show that the paper supports the sentence citing it.",
    "With `snakemake --use-conda`, a rule's env is read only from a literal `conda:` path in the Snakefile or "
    "its literal `include:` files, matched to a built env under `.snakemake/conda/` by the env file's bytes; "
    "any other rule env is a gap. The reader is checked on a synthetic folder, not against a real Snakemake run.",
    "Pip packages are read from the conda env's site-packages: one uninstalled after the run is not seen, "
    "and `pip install --user` packages under `~/.local` are not read.",
]


# ---------------------------------------------------------------- loading

def load_gate(plugin_root):
    global gate, PLUGIN_ROOT
    PLUGIN_ROOT = os.path.abspath(plugin_root)
    path = os.path.join(PLUGIN_ROOT, "hooks", "gate.py")
    if not os.path.isfile(path):
        sys.exit("verify: {} not found. verify reads the mycelium-extra approval gate's receipts"
                 "; pass --plugin-root <the plugin folder>.".format(path))
    sys.path.insert(0, os.path.dirname(path))
    sys.dont_write_bytecode = True  # leave no __pycache__ in the plugin folder
    import gate as module
    gate = module


def read_jsonl(path, invalid=None):
    records = []
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                try:
                    record = json.loads(line)
                    if not isinstance(record, dict) or not isinstance(record.get("ts"), (int, float)) \
                            or isinstance(record["ts"], bool) or not math.isfinite(record["ts"]) \
                            or not isinstance(record.get("command", ""), str):
                        raise ValueError("invalid receipt")
                    datetime.datetime.fromtimestamp(record["ts"])
                    for key in ("paths", "plans", "env_lines"):
                        if key in record and (not isinstance(record[key], list)
                                              or any(not isinstance(v, str) for v in record[key])):
                            raise ValueError("invalid receipt list")
                    for key in ("script", "engine", "pins", "command_env", "hook_env"):
                        if record.get(key) is not None and not isinstance(record[key], dict):
                            raise ValueError("invalid receipt mapping")
                    records.append(record)
                except (ValueError, OverflowError, OSError):
                    if invalid is not None:
                        invalid.append(line_no)
    return records


def parse_iso(text):
    """Epoch seconds for 2026-09-30T08:39:36Z, +0200, +02:00, or naive (UTC)."""
    if not isinstance(text, str):
        return None
    m = re.match(r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(?:\.\d+)?(Z|[+-]\d{2}:?\d{2})?$",
                 (text or "").strip())
    if not m:
        return None
    import calendar
    try:
        seconds = calendar.timegm(time.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        return None
    zone = m.group(3)
    if zone and zone != "Z":
        digits = zone[1:].replace(":", "")
        if int(digits[:2]) > 23 or int(digits[2:]) > 59:
            return None
        offset = int(digits[:2]) * 3600 + int(digits[2:]) * 60
        seconds -= offset if zone[0] == "+" else -offset
    return seconds


def when(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else "?"


def read_approval(path):
    if not os.path.isfile(path):
        return None
    try:
        return gate.read_approval(path)
    except gate.InvalidApproval as error:
        sys.exit("verify: " + str(error))


def rel_or_abs(root, path):
    path = os.path.normpath(path if os.path.isabs(path) else os.path.join(root, path))
    rel = os.path.relpath(path, root)
    return path if rel.startswith("..") else rel.replace(os.sep, "/")


def under(path, folder):
    return path == folder or path.startswith(folder.rstrip("/") + "/")


# ---------------------------------------------------------------- outside records

def exit_conflict(state, code):
    """`state`, or EXIT_CONFLICT / EXIT_UNREADABLE when sacct says COMPLETED but the job's ExitCode (`N:M`: exit
    status, signal) is not `0:0` or cannot be read. A blank ExitCode (a sacct that gave none) leaves the state
    as it was; completion is the state and a clean exit, not the state alone."""
    if state != "COMPLETED" or not code.strip():
        return state
    match = re.match(r"^(\d+):(\d+)$", code.strip())
    if not match:
        return EXIT_UNREADABLE
    return state if match.group(1) == match.group(2) == "0" else EXIT_CONFLICT


def sacct_state(sacct, job_id, since):
    """The job's final state from sacct, or None when sacct cannot be run. `submit` is the job's
    sbatch line as Slurm expanded it (`$dir` resolved), read from `workdir`; a Slurm older than
    20.11 has no SubmitLine field, so the call is retried without it."""
    day = time.strftime("%Y-%m-%d", time.localtime(since))
    for fields in ("JobID,State,ExitCode,Start,End,WorkDir,SubmitLine", "JobID,State,ExitCode,Start,End"):
        try:
            proc = subprocess.Popen([sacct, "-j", str(job_id), "-n", "-P", "-X", "-S", day, "-o", fields],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8",
                                    errors="replace")
            out, _ = proc.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            return None
        except (OSError, ValueError):
            return None
        if proc.returncode == 0:
            break
    found = None
    for line in out.splitlines():
        parts = line.split("|", 6)  # SubmitLine is last, so a `|` inside it stays whole
        if len(parts) >= 5 and re.split(r"[._]", parts[0])[0] == str(job_id):  # `N_2`: an array task
            state = parts[1].split()[0] if parts[1] else "UNKNOWN"
            state = exit_conflict(state, parts[2])
            end = parts[4] if re.match(r"^\d{4}-", parts[4]) else None
            try:
                end = time.mktime(time.strptime(end, "%Y-%m-%dT%H:%M:%S")) if end else None
            except (ValueError, OverflowError, OSError):
                end = None
            if found is None:
                found = {"state": state, "exit": parts[2], "end": end,
                         "workdir": parts[5] if len(parts) > 6 else None,
                         "submit": re.sub(r"[;&|<>()]", " ", parts[6]) if len(parts) > 6 else None}
            else:  # an array: the worst task's state, and the last task's end
                rank = lambda s: 2 if s in FAILED_JOB else 0 if s == "COMPLETED" else 1
                if rank(state) > rank(found["state"]):
                    found.update(state=state, exit=parts[2])
                found["end"] = None if end is None or found["end"] is None else max(end, found["end"])
    return found or {"state": "NOT_FOUND", "exit": None, "end": None}


def decode_name(encoded):
    padded = encoded + "=" * (-len(encoded) % 4)
    for decode in (base64.urlsafe_b64decode, base64.b64decode):
        try:
            return decode(padded.encode("ascii")).decode("utf-8")
        except (ValueError, UnicodeError):
            continue
    return None


def pickle_strings(blob):
    """The string constants in a pickle, read with pickletools: nothing in it is executed."""
    found = []
    try:
        for _, arg, _ in pickletools.genops(blob):
            if isinstance(arg, str):
                found.append(arg)
            elif isinstance(arg, bytes) and arg[:1] == b"\x80":  # a nested code object's pickle
                found.extend(pickle_strings(arg))
    except (ValueError, RecursionError):  # co_code bytes, a truncated or crafted pickle: keep what was read
        pass
    return found


def code_text(code):
    """A Snakemake record's `code` as text that names the rule's script. Snakemake 9 stores
    the rule source (`script: "x.py"`) or nothing; before 9 it is base64 of a pickled code
    object, whose string constants hold the `script:`/`notebook:` path as written."""
    if not isinstance(code, str):
        return ""
    try:
        blob = base64.b64decode(code.encode("ascii"), validate=True)
    except (ValueError, UnicodeError):
        return code
    # ponytail: the path is relative to the Snakefile's folder, which the record does not
    # name, so it matches only when that is the workdir (new-analysis's run.sh `cd`s there).
    return "\n".join([code] + pickle_strings(blob)) if blob[:1] == b"\x80" else code


def snakemake_records(folders, since, invalid=None):
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
                    with open(full, encoding="utf-8") as handle:
                        data = json.load(handle)
                    if not isinstance(data, dict):
                        raise ValueError("invalid metadata")
                    start, end = float(data.get("starttime") or 0), float(data.get("endtime") or 0)
                    if not math.isfinite(start) or not math.isfinite(end) \
                            or not isinstance(data.get("shellcmd") or "", str):
                        raise ValueError("invalid metadata fields")
                except (OSError, ValueError, TypeError, OverflowError):
                    if invalid is not None:
                        invalid.append(full)
                    continue
                path = decode_name(os.path.relpath(full, meta).replace(os.sep, ""))
                if path is None:
                    continue
                records.append({
                    "path": os.path.normpath(path if os.path.isabs(path) else os.path.join(workdir, path)),
                    "rule": data.get("rule"),
                    "start": start,
                    "end": end,
                    "incomplete": data.get("incomplete") in (True, "True", "true"),
                    # Not `input`: an input is read, not run. A `{input.script}` step is in the expanded
                    # shellcmd; a `script:`/`notebook:` path is in `code`.
                    "command": "\n".join([data.get("shellcmd") or "", code_text(data.get("code"))]),
                    "workdir": workdir,
                })
    return records


STATIC_IO = ("static", "static+repository")  # upstream's io_detection values that name literal paths; "unresolved" names none
LINEAGE_SPLIT = re.compile(r"\s*(?:&&|\|\||[;|\n])\s*")


def lineage_actions(root, start, end):
    """Mycelium's lineage actions in the window, as upstream wrote them plus what verify keeps of each: `epoch`,
    `session` (Mycelium's own id, which is the host's only when Mycelium fell back to it), `files` (its outputs: root-relative
    path, sha256, `missing` when the path did not exist when the action was recorded), `exit`, `io` (io_detection),
    `warnings` (its own and the manifest's extraction warnings for it) and `manifest`. An unreadable manifest, a
    non-object action or a malformed field is skipped or read as absent, never an error."""
    actions = []
    for path in sorted(glob.glob(os.path.join(root, ".living", "log", "data-lineage", "*.json"))):
        try:
            with open(path, encoding="utf-8") as handle:
                manifest = json.load(handle)
        except (OSError, ValueError):
            continue
        if not isinstance(manifest, dict) or not isinstance(manifest.get("actions"), list):
            continue
        shared = manifest.get("extraction_warnings")
        shared = [w for w in shared if isinstance(w, str)] if isinstance(shared, list) else []
        for action in manifest["actions"]:
            if not isinstance(action, dict):
                continue
            ts = parse_iso(action.get("ts"))
            if ts is None or not start - TOLERANCE <= ts <= end + TOLERANCE:
                continue
            script = action.get("script") if isinstance(action.get("script"), str) and action.get("script") else None
            files = [{"path": rel_or_abs(root, rec["path"]), "sha256": rec["sha256"] if isinstance(rec.get("sha256"), str) else None,
                      "missing": bool(rec.get("_missing"))}
                     for rec in (action.get("outputs") if isinstance(action.get("outputs"), list) else [])
                     if isinstance(rec, dict) and isinstance(rec.get("path"), str) and rec["path"]]
            code = action.get("bash_exit")
            own = action.get("lineage_warnings")
            warnings = [w for w in own if isinstance(w, str)] if isinstance(own, list) else []
            command = action.get("bash_cmd") if isinstance(action.get("bash_cmd"), str) else None
            label = (script or command or "event at {}".format(action.get("ts"))) + ": "  # how upstream prefixes them
            warnings += [w[len(label):] for w in shared if w.startswith(label) and w[len(label):] not in warnings]
            actions.append(dict(action, script=script, epoch=ts, session=manifest.get("session_id"),
                                manifest=os.path.basename(path), files=files, warnings=warnings,
                                exit=None if isinstance(code, bool) or not isinstance(code, int) else code,
                                io=action.get("io_detection") if isinstance(action.get("io_detection"), str) else None))
    return actions


def lineage_join(root, action, receipts):
    """(receipt, how, why): the attempt a lineage action belongs to. `explicit` when the action carries the attempt id or
    call id of exactly one recorded attempt (upstream writes none at this revision). Otherwise `inferred`: a matched
    attempt with the same session id, the same command (a whole command, or one `&&`/`;`/`|` segment of it), the same
    script and a launch-to-report window around the action's time, and only when exactly one attempt fits. Anything
    less is (None, None, why not): no timestamp or output path ever joins an action to an attempt."""
    for key, field in (("attempt_id", "attempt_id"), ("call_id", "call_id"), ("tool_use_id", "call_id")):
        want = action.get(key)
        if isinstance(want, str) and want:
            found = [r for r in receipts if r.get(field) == want]
            if len(found) == 1:
                return found[0], "explicit", None
            return None, None, "its explicit {} `{}` names {} recorded attempts".format(key, want, len(found))
    if not action["script"]:
        return None, None, "it names no script (inline code), so no script identity joins it to an attempt"
    session, rel = action.get("session"), rel_or_abs(root, action["script"])
    commands = set(squash(part) for part in LINEAGE_SPLIT.split(action.get("bash_cmd") or "") if part.strip())
    pool = [r for r in receipts if launch_kind(r) == "matched" and r.get("attempt_id")]
    for name, ok in (("session", lambda r: bool(session) and r.get("session_id") == session),
                     ("command", lambda r: squash(r.get("command", "")) in commands),
                     ("script", lambda r: rel in ran_paths(root, r)),
                     ("time", lambda r: window(r)[0] - TOLERANCE <= action["epoch"] <= r["ts"] + TOLERANCE)):
        pool = [r for r in pool if ok(r)]
        if not pool:
            return None, None, "no matched attempt shares its {}{}".format(
                name, " (Mycelium's session id is its own date-counter unless it fell back to the host's)" if name == "session" else "")
    if len(pool) > 1:
        return None, None, "no unique attempt fits it: {} attempts share its session, command, script and time".format(len(pool))
    return pool[0], "inferred", None


def fits_attempt(r, mtime):
    """The file's time falls in the attempt (its report, and its start when recorded), within the clock tolerance."""
    return r["ts"] >= mtime - TOLERANCE and (started(r) is None or mtime >= started(r) - TOLERANCE)


def lineage_for(root, rel, mtime, sha, actions, receipts):
    """The lineage actions that list `rel` as an output, each judged: (entry, receipt) pairs. `entry.used` is true only
    for an action joined to one attempt and not contradicted. Static detection is not a write: an unresolved
    io_detection, a nonzero exit, a path that was missing when it was recorded, a hash that is not the file's now,
    a file time outside the joined attempt, or an attempt that watched the declared outputs and did not see this one change
    (upstream fills a missing hash from disk later, so a hash that matches proves nothing either) all leave it unused."""
    found = []
    for action in actions:
        listed = [f for f in action["files"] if f["path"] == rel]
        if not listed:
            continue
        receipt, how, why = lineage_join(root, action, receipts)
        notes = [] if receipt is not None else ["not joined: " + why]
        if action["io"] not in STATIC_IO:
            notes.append("its io_detection is `{}`, not a resolved static detection".format(action["io"]))
        if action["exit"] not in (None, 0):
            notes.append("lineage records exit {}".format(action["exit"]))
        if listed[0]["missing"]:
            notes.append("the path was missing when the action was recorded")
        if listed[0]["sha256"] and sha and listed[0]["sha256"] != sha:
            notes.append("its hash differs from the file now")
        if receipt is not None:
            seen = observed_paths(receipt)
            if not fits_attempt(receipt, mtime):
                notes.append("the file's time is outside the joined attempt")
            if seen is not None and rel not in seen and not any(under(rel, folder) for folder in seen):
                notes.append("the joined attempt observed the declared outputs and did not see it change")
        found.append(({"ts": action["ts"], "script": action["script"] and rel_or_abs(root, action["script"]),
                       "io_detection": action["io"], "exit": action["exit"], "manifest": action["manifest"],
                       "joined": receipt.get("attempt_id") if receipt is not None else None, "how": how,
                       "warnings": action["warnings"], "notes": notes, "used": not notes}, receipt))
    return found


def lineage_findings(report, rel, found):
    """One info line per output that lineage lists: what it says, how it was used or why not, and the upstream limits."""
    for entry, _ in found:
        report.add("info", "Mycelium's lineage lists `{}` as a static output of `{}` (io_detection {}{}): {}. A path found by static "
                           "scanning is not proof of a write, and a hash read from disk is not proof that this invocation wrote it.".format(
                               rel, entry["script"] or "inline code", entry["io_detection"],
                               "; warnings: " + "; ".join(entry["warnings"]) if entry["warnings"] else "",
                               "used as a candidate producer only (join: {})".format(entry["how"]) if entry["used"]
                               else "not used as producer evidence: " + "; ".join(entry["notes"])))


def apply_lineage(grade, found, digest, rel):
    """Fold the judged lineage into `grade`; adds `lineage` (the entries) and, for two producers, `conflict`. Lineage
    is only ever a candidate (`lineage-record`): it confirms an `attempt-observed` producer ("lineage agrees"), agrees
    with or supplies a candidate, or names a second producer, which leaves the output unresolved. It never makes
    an output `supported`."""
    grade["lineage"] = [entry for entry, _ in found]
    used = collections.OrderedDict((id(r), r) for entry, r in found if entry["used"])
    if not used:
        return grade
    hows = {e["how"] for e, _ in found if e["used"]}
    owner = grade["owner"]
    via = "Mycelium's lineage lists it as a static output of `{}` (io_detection {}); the join to the attempt is {}".format(
        next(e["script"] for e, _ in found if e["used"]), next(e["io_detection"] for e, _ in found if e["used"]),
        "explicit (its attempt id)" if hows == {"explicit"} else
        "inferred (same session, command and script, and exactly one matching attempt)")

    def conflict(others):
        names = [candidate_text(r, digest) for r in others]
        grade.update(owner=None, producer_attempt=None, strength="unresolved", conflict=True, candidates=names,
                     reason="two producers: " + "; ".join(names),
                     gap="Output `{}` has two producers: {}; neither is established, so the output stays unresolved."
                     .format(rel, " and ".join(names)))
        return grade

    named = list(used.values())
    if len(named) > 1:
        return conflict(named)
    receipt = named[0]
    if owner is not None and (owner is receipt or owner.get("attempt_id") == receipt.get("attempt_id")):
        if grade["evidence_method"] == "attempt-observed":
            grade["reason"] += "; lineage agrees ({})".format(via)
        else:
            grade.update(evidence_method="lineage-record", reason=via + "; the timing candidate is the same attempt")
        return grade
    if owner is not None:
        return conflict([owner, receipt])
    if grade["candidates"]:  # an ambiguity that lineage names one party of does not resolve it
        grade["reason"] += "; lineage names {}, which does not resolve it".format(candidate_text(receipt, digest))
        return grade
    grade.update(owner=receipt, evidence_method="lineage-record", strength="candidate",
                 candidates=[candidate_text(receipt, digest)],
                 reason=via + "; a detected path and a hash read from disk are not proof that this invocation wrote it")
    return grade


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


LINT_LINE = re.compile(r"^(.+?):(\d+):(\d+): \[([\w-]+)\] (.*)$")
LINT_LANGUAGES = {".py": "Python", ".R": "R", ".r": "R"}
CHOICE_NUMBER = re.compile(r"(?<![\w.])-?\d*\.?\d+(?:[eE][-+]?\d+)?(?![\w.])")
NOTEBOOK_EXT = (".ipynb", ".qmd", ".Rmd", ".rmd")
FENCE = re.compile(r"^\s*(`{3,})(.*)$")
CHUNK = re.compile(r"^\s*\{(r|python)\b", re.I)
ENGINE = re.compile(r"\bengine\s*=\s*[\"']?(\w+)", re.I)
CHILD = re.compile(r"\bchild\s*=\s*(?:([\"'])(?P<path>[^\"']+)\1)?")
QUARTO_CHILD = re.compile(r"^\s*#\|\s*child:\s*[\"']?(?P<path>[^\"'\s\[]+)?")
READ_CHUNK = re.compile(r"^[^#]*\bread_chunk\s*\(\s*(?:path\s*=\s*)?(?:([\"'])(?P<path>[^\"']+)\1)?")
# scilintr 0.1.1's `main()` lints only its first argument, as a folder, prints no column and
# always exits 0, so R code goes through `lint_project()` on a copy, in LINT_LINE's format.
# Each file is parsed first: lintr's parse-error finding is dropped by a nearby ANALYSIS_OK.
R_LINT = ('a <- commandArgs(TRUE); for (p in a[-1]) tryCatch(parse(p), error = function(e) cat("unparseable: ", p, '
          '": ", gsub("\\\\s+", " ", conditionMessage(e)), "\\n", sep = "")); f <- scilintr::lint_project(a[1]); '
          'for (x in f) cat(sprintf("%s:%d:1: [%s] %s\\n", x$file, x$line, x$rule, gsub("\\\\s+", " ", x$message))); '
          'quit(status = if (length(f)) 1 else 0)')


# The same run with waivers off: a finding a waiver suppresses is then reported, so verify can name it.
R_NO_WAIVERS = ('for (n in c("apply_waivers", "filter_waivers_cross_file")) '
                'assignInNamespace(n, function(f, ...) f, "scilintr"); ')
WAIVER = re.compile(r"ANALYSIS_OK\[([\w-]+)\]:\s*(.*?)\s*$")
R_WAIVER_LINES, PY_WAIVER_LINES = 8, 4  # how far from its line scilintr lets a waiver reach, each way / downward


def code_files(root, analysis_dir, planned):
    """The analysis folder's code (skipping outputs, provenance, logs), else the planned scripts."""
    if not analysis_dir or analysis_dir == ".":
        return [p for p in planned if os.path.isfile(os.path.join(root, p))]
    files = []
    for folder, dirs, names in os.walk(os.path.join(root, analysis_dir)):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in SKIP_FOLDERS)
        files += [rel_or_abs(root, os.path.join(folder, n)) for n in sorted(names)]
    return files[:MAX_FILES]


def notebook_code(path):
    """(language, code, first line of each code cell) of a Jupyter notebook, or None.
    Magic and shell lines become comments, so line numbers still map to cells."""
    try:
        with open(path, encoding="utf-8") as handle:
            nb = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(nb, dict):
        return None
    meta = nb.get("metadata") or {}
    language = ((meta.get("kernelspec") or {}).get("language")
                or (meta.get("language_info") or {}).get("name") or "python").lower()
    language = {"python": "Python", "r": "R"}.get(language)
    lines, starts = [], []
    for entry in nb.get("cells") or [] if language else []:
        if entry.get("cell_type") != "code":
            continue
        source = entry.get("source") or ""
        source = (source if isinstance(source, str) else "".join(source)).splitlines()
        magic = language == "Python" and bool(source) and source[0].lstrip().startswith("%%")
        starts.append(len(lines) + 1)
        lines += ["# " + line if language == "Python" and (magic or line.lstrip().startswith(("%", "!")))
                  else line for line in source] + [""]
    return (language, "\n".join(lines), starts) if starts else None


def chunk_code(path):
    """({language: code}, refs) of a .qmd/.Rmd's r and python chunks, every other line blank
    so line numbers match the document. Python magic and shell lines become comments. An
    `engine=` option picks the language; other engines are skipped like `{bash}`. refs are
    the (line, quoted path or None) of each `child=` and `read_chunk()`, whose code lives
    in another file."""
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return {}, []
    code, refs, fence, language, magic = {}, [], None, None, False
    for n, line in enumerate(lines):
        match = FENCE.match(line)
        if fence is None:
            if match:
                fence, chunk, magic = match.group(1), CHUNK.match(match.group(2)), None
                engine = chunk and (ENGINE.search(match.group(2)) or chunk).group(1).lower()
                language = chunk and {"r": "R", "python": "Python"}.get(engine)
                child = chunk and CHILD.search(match.group(2))
                if child:
                    refs.append((n + 1, child.group("path")))
            continue
        if match and len(match.group(1)) >= len(fence) and not match.group(2).strip():
            fence = None
        elif language:
            ref = language == "R" and (QUARTO_CHILD.match(line) or READ_CHUNK.match(line))
            if ref:
                refs.append((n + 1, ref.group("path")))
            if magic is None:
                magic = language == "Python" and line.lstrip().startswith("%%")
            commented = language == "Python" and (magic or line.lstrip().startswith(("%", "!")))
            code.setdefault(language, [""] * len(lines))[n] = "# " + line if commented else line
    return {language: "\n".join(body) for language, body in code.items()}, refs


def lint(root, files, report, scilintr, rscript, seconds, deadline=None, choices=()):
    """Run scilintr on the code; remaining findings block, an unchecked language is a gap.
    The Python CLI skips R files and exits 0 on a missing path, so each language gets
    its own CLI and only existing files are passed. It also exits 0, silent, on code that
    does not parse, so Python code is parsed first and an unparseable file is a gap. R code
    is copied to one folder, which `lint_project()` lints with its cross-file rules; a script
    keeps its repository path there, so a `source()` between copied scripts still resolves.
    `choices` is (row text, Choice cell) for each plan row; a threshold finding whose numbers a Choice
    of a row naming that script states is info."""
    result = {"findings": [], "waivers": [], "output": [], "notebooks": [], "approved": []}
    by_language = collections.defaultdict(list)
    scratch = os.path.realpath(tempfile.mkdtemp(prefix="mycelium-extra-lint-"))  # R prints real paths
    cells = {}  # extracted notebook code path -> (notebook, first line of each code cell)

    def parses(rel, code=None):
        try:
            if code is None:
                with open(os.path.join(root, rel), "rb") as handle:
                    code = handle.read()
            compile(code, rel, "exec")
            return True
        except (SyntaxError, ValueError, OSError) as error:
            report.add("gap", "scilintr (Python) not checked: `{}` does not parse under Python {} ({}).".format(
                rel, "{}.{}.{}".format(*sys.version_info[:3]), cell(str(error))[:120]))
            return False

    def extract(rel, language, code, starts=None, keep_path=False):
        if language == "Python" and not parses(rel, code):
            return
        if keep_path:
            path = os.path.join(scratch, "src", os.path.splitext(rel)[0] + ".R")
            os.makedirs(os.path.dirname(path), exist_ok=True)
        else:
            path = os.path.join(scratch, "{}_{}".format(len(cells), os.path.basename(rel))) + (
                ".py" if language == "Python" else ".R")
        with open(path, "w", encoding="utf-8", errors="surrogateescape") as handle:
            handle.write(code)
        cells[path] = (rel, starts)
        by_language[language].append(path)

    files, seen = list(files), set(files)
    try:
        for rel in files:  # grows as `child=` and `read_chunk()` paths are followed
            ext = os.path.splitext(rel)[1]
            extracted = notebook_code(os.path.join(root, rel)) if ext == ".ipynb" else None
            chunks, refs = chunk_code(os.path.join(root, rel)) if ext.lower() in (".qmd", ".rmd") else (None, [])
            for n, target in refs:
                path = target and rel_or_abs(root, os.path.join(os.path.dirname(os.path.join(root, rel)), target))
                if not target:
                    report.add("gap", "scilintr not checked: `{}:{}` pulls in code through a path that is not "
                                      "a quoted string.".format(rel, n))
                elif not os.path.isfile(os.path.join(root, path)):
                    report.add("gap", "scilintr not checked: `{}:{}` pulls in `{}`, which was not found next to "
                                      "the document.".format(rel, n, target))
                elif path not in seen:
                    files.append(path)
                    seen.add(path)
            if ext in LINT_LANGUAGES and LINT_LANGUAGES[ext] == "R":
                try:
                    with open(os.path.join(root, rel), encoding="utf-8", errors="surrogateescape") as handle:
                        extract(rel, "R", handle.read(), keep_path=not (os.path.isabs(rel) or rel.startswith("..")))
                except OSError as error:
                    report.add("gap", "scilintr (R) not checked: `{}` unreadable ({}).".format(rel, error.strerror))
            elif ext in LINT_LANGUAGES:
                if parses(rel):
                    by_language["Python"].append(rel)
            elif extracted:
                extract(rel, *extracted)
            elif chunks:
                for language, code in sorted(chunks.items()):
                    extract(rel, language, code)
            elif rel.endswith(NOTEBOOK_EXT) and not refs:
                result["notebooks"].append(rel)
        result["reasons"] = scan_waivers(root, files, result)
        def approved(rel):
            """The numbers a script's own plan rows approved; a script no row names keeps every Choice."""
            mine = [choice for text, choice in choices if rel in text] or [choice for _, choice in choices]
            return {float(n) for choice in mine for n in CHOICE_NUMBER.findall(choice)}

        lint_languages(root, by_language, cells, report, result, scilintr, [rscript, "-e", R_LINT, scratch],
                       seconds, deadline, approved)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    pair_waivers(result, report)
    if result["notebooks"]:
        report.add("info", "{} notebook(s) not linted: {}.".format(
            len(result["notebooks"]), gate.listing(result["notebooks"], 5)))
    return result


def scan_waivers(root, files, result):
    """Fill result["waivers"] with every `ANALYSIS_OK[` line of the code; return {(file, line): reason}. A reason
    may continue on the next comment line, as scilintr's R waiver (which needs none) is often written."""
    reasons = {}
    for rel in files:
        if os.path.splitext(rel)[1] in LINT_LANGUAGES or rel.endswith(NOTEBOOK_EXT):
            try:
                with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as handle:
                    lines = handle.read().splitlines()
            except OSError:
                continue
            for n, line in enumerate(lines, 1):
                if "ANALYSIS_OK[" not in line:
                    continue
                result["waivers"].append((rel, n, line.strip()))
                match = WAIVER.search(line)
                reason = match.group(2).rstrip('",') if match else ""
                follow = lines[n] if n < len(lines) else ""
                if match and not reason and re.match(r"^\s*#\s*\S", follow):
                    reason = follow.strip().lstrip("# ")
                reasons[(rel, n)] = reason
    return reasons


def pair_waivers(result, report):
    """result["waived"]: each finding scilintr suppressed (found only with waivers off) with the waiver that
    covers it and that waiver's reason. R accepts a waiver with no reason, which Python does not: block it."""
    result["waived"] = []
    blocked = set()
    for path, line, rule, message, language in result.get("unwaived", []):
        file_ = re.sub(r"\[code cell \d+\]$", "", path)
        reach = R_WAIVER_LINES if language == "R" else PY_WAIVER_LINES
        near = [w for w in result["waivers"] if w[0] == file_ and (
            file_.endswith(NOTEBOOK_EXT) or (language == "R" and abs(w[1] - line) <= reach)
            or (language != "R" and 0 <= line - w[1] <= reach))]
        waiver = min(near, key=lambda w: abs(w[1] - line), default=None)
        reason = result["reasons"].get((waiver[0], waiver[1]), "") if waiver else ""
        result["waived"].append((path, line, rule, message, waiver and waiver[0], waiver and waiver[1], reason))
        if waiver and language == "R" and not reason and (waiver[0], waiver[1]) not in blocked:
            blocked.add((waiver[0], waiver[1]))
            report.add("block", "`{}:{}` waives {} with no reason after `ANALYSIS_OK[...]:`. Python's scilintr "
                       "requires one; write what is done, why it is valid, and where it is checked.".format(
                           waiver[0], waiver[1], rule))


def cell_line(line, cells):
    """A scilintr line on extracted notebook code, cited as `<notebook>[code cell N]:<line>`."""
    match = LINT_LINE.match(line)
    if not match or match.group(1) not in cells:
        return line
    rel, starts = cells[match.group(1)]
    if not starts:  # .qmd/.Rmd code keeps the document's line numbers
        return line
    number = int(match.group(2))
    index = max(bisect.bisect_right(starts, number), 1)
    return "{}[code cell {}]:{}:{}: [{}] {}".format(rel, index, number - starts[index - 1] + 1, *match.groups()[2:])


def unwaived_pass(root, language, paths, cells, result, report, command, seconds, normal, deadline=None):
    """Lint again with waivers off; a finding that only this run reports was waived. Best effort: the first
    pass decides the status, so a failure here is only an info line."""
    if language == "Python":
        command = [command[0], "--no-waivers"]
    else:
        command = command[:2] + [R_NO_WAIVERS + command[2]] + command[3:]
    try:
        seconds = min(seconds, max(0.001, deadline - time.monotonic())) if deadline is not None else seconds
        proc = subprocess.run(command + paths, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              encoding="utf-8", errors="replace", timeout=seconds)
        out = "\n".join(cell_line(line, cells) for line in proc.stdout.splitlines())
        for path, (rel, _) in cells.items():
            out = out.replace(path, rel)
        every = [m.groups() for m in map(LINT_LINE.match, out.splitlines()) if m]
        if proc.returncode not in (0, 1) or (proc.returncode == 1) != bool(every):
            raise OSError("exit {}".format(proc.returncode))
    except (OSError, subprocess.SubprocessError):
        report.add("info", "Waived {} findings were not listed: the run with waivers off failed.".format(language))
        return
    result.setdefault("unwaived", []).extend((f[0], int(f[1]), f[3], f[4], language) for f in every
                                              if (f[0], f[1], f[2], f[3]) not in normal)


def approved_threshold(root, finding, approved, cells=()):
    """Whether a threshold finding's line holds only numbers that the plan rows' Choice cells approved.
    `finding` is as scilintr printed it: for a notebook that is the extracted code file, whose line is the
    one linted. `approved(rel)` gives the numbers for the script `rel`; a signed number must match its sign,
    and text after `#` is not read."""
    path, line, _, rule, message = finding
    if "threshold" not in (rule + " " + message).lower():
        return False
    numbers_ok = approved(cells[path][0] if path in cells else path)
    if not numbers_ok:
        return False
    try:
        with open(os.path.join(root, path), encoding="utf-8", errors="replace") as handle:
            text = handle.read().splitlines()[int(line) - 1]
    except (OSError, IndexError, ValueError):
        return False
    numbers = {float(n) for n in CHOICE_NUMBER.findall(text.split("#")[0])}
    return bool(numbers) and numbers <= numbers_ok


def lint_languages(root, by_language, cells, report, result, scilintr, r_lint, seconds, deadline=None,
                   approved=lambda rel: frozenset()):
    for language, paths in sorted(by_language.items()):
        command = [scilintr] if language == "Python" else r_lint
        try:
            timeout = min(seconds, max(0.001, deadline - time.monotonic())) if deadline is not None else seconds
            proc = subprocess.run(command + paths, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  encoding="utf-8", errors="replace", timeout=timeout)
        except (OSError, subprocess.SubprocessError) as error:
            if isinstance(error, subprocess.TimeoutExpired):
                report.add("gap", "scilintr ({}) not checked: timed out after {:.0f} s.".format(language, timeout))
            else:
                report.add("gap", "scilintr ({}) not checked: `{}` not found. Install it (`{}`) and re-verify, or "
                           "record its path with the init skill (`--tools {} PATH`).".format(
                               language, command[0], "pip install scilintr" if language == "Python"
                               else 'install.packages("scilintr")',
                               "--scilintr" if language == "Python" else "--rscript"))
            continue
        raw_lines, shown_lines = proc.stdout.splitlines(), []
        for line in raw_lines:
            line = cell_line(line, cells)
            for path, (rel, _) in cells.items():
                line = line.replace(path, rel)
            shown_lines.append(line)
        proc.stdout = "\n".join(shown_lines)
        broken = [line[len("unparseable: "):].partition(": ") for line in proc.stdout.splitlines()
                  if line.startswith("unparseable: ")]
        for rel, _, error in broken:
            report.add("gap", "scilintr (R) not checked: `{}` does not parse ({}).".format(
                rel, cell(re.sub(r"^.*?:\d+:\d+: ", "", error))[:120]))
        found = [m.groups() for m in map(LINT_LINE.match, proc.stdout.splitlines()) if m]
        raw = {}  # the finding as shown -> as printed, where the file and line can be read
        for printed, line in zip(raw_lines, shown_lines):
            if LINT_LINE.match(printed) and LINT_LINE.match(line):
                raw[LINT_LINE.match(line).groups()] = LINT_LINE.match(printed).groups()
        shown = command[:1] if language == "Python" else [command[0], "-e", "'scilintr::lint_project()'"]
        result["output"].append("$ {}\n{}".format(" ".join(shown + ["<{} files>".format(len(paths))]),
                                                  proc.stdout.rstrip()))
        if proc.returncode == 1 and found:
            result["findings"] += found
            planned = [f for f in found if approved_threshold(root, raw.get(f, f), approved, cells)]
            result.setdefault("approved", []).extend(planned)
            for f in planned:
                report.add("info", "`{}:{}` [{}]: its threshold is a Choice the plan approved, so it does not "
                                   "block.".format(f[0], f[1], f[3]))
            rules = collections.Counter(f[3] for f in found if f not in planned)
            if rules:
                report.add("block", "{} scilintr finding(s) remain in {} code ({}). Fix each or add an "
                           "`ANALYSIS_OK[...]` waiver, then re-verify.".format(
                               sum(rules.values()), language,
                               ", ".join("{} {}".format(n, r) for r, n in rules.most_common())))
        elif proc.returncode == 0 and not found:
            if len(paths) > len(broken):
                report.add("info", "scilintr: {} {} file(s) clean.".format(len(paths) - len(broken), language))
        else:
            report.add("gap", "scilintr ({}) not checked: exit {} with output it could not read: {}".format(
                language, proc.returncode, cell((proc.stdout.strip().splitlines() or [""])[-1])[:200]))
        if result["waivers"] and (proc.returncode, bool(found)) in ((1, True), (0, False)):
            unwaived_pass(root, language, paths, cells, result, report, command, seconds, {f[:4] for f in found},
                          deadline)


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
    found = gate.read_outputs(plan)[0]
    if found is None:
        return None
    words = []
    for word in found:
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


def is_script(root, path):
    """A planned path is a script by its extension, a Snakefile name, or a `#!` line; another
    existing file the plan names (a log to read, a README) is not, though a run may mention it."""
    if gate.SCRIPT_EXT.search(path) or is_snakefile(path):
        return True
    try:
        with open(os.path.join(root, path), "rb") as handle:
            return handle.read(2) == b"#!"
    except OSError:
        return False


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


def ran_paths(root, receipt):
    """The receipt's paths that ran as the program. A path handed to `-e`/`-c` code or to a
    program read from stdin (a lint call, a parse check, another tool's script) did not run."""
    paths = receipt.get("paths", [])
    words = receipt.get("command", "").split()
    head = next((i for i, w in enumerate(words) if gate.RUNNERS.match(os.path.basename(w))), None)
    for word in words[head + 1:] if head is not None else []:
        if word in ("-c", "-e", "--eval", "-", "<"):
            cwd = os.path.join(root, receipt.get("cwd") or ".")  # resolved the way the gate recorded paths
            stdin = {gate.repo_relative(root, cwd, words[k + 1]) for k in range(len(words) - 1) if words[k] == "<"}
            return [p for p in paths if p in stdin]
        if not word.startswith("-"):
            break
    return paths


def is_run(root, receipt, commands):
    """False for a `command -v` lookup and for a receipt whose paths were only handed to other code."""
    if LOOKUP.match(receipt.get("command", "")):
        return False
    return receipt.get("kind") in commands or bool(ran_paths(root, receipt))


def approval_runs(root, config, digest, approved_at, receipts):
    """The real, non-explore runs recorded under an approval since it was approved, oldest first. A
    re-approval restarts the count, since it rewrites `approved_at`. The gate's `max_runs_per_approval`
    counts with this, so it and `verify` agree."""
    return [r for r in receipts if digest in r.get("plans", []) and not r.get("explore")
            and r.get("ts", 0) >= approved_at and is_run(root, r, config["gated_commands"])]


def is_wrapper(receipt):
    """A run that starts other steps: a shell script, Snakemake, Nextflow, or a Slurm job."""
    return receipt.get("kind") in ("bash", "sh", "zsh", "snakemake", "nextflow", "sbatch") or any(
        p.endswith((".sh", "Snakefile", ".smk")) for p in receipt.get("paths", []))


def wrapper_candidates(receipts, record):
    """The recorded wrapper runs that fit a Snakemake job in time: the first that ended after the job
    finished, and any other that ended within the clock tolerance of it. The join is by time, so
    every one of them could be the run the job was in."""
    later = [r for r in receipts if r.get("ts", 0) >= record["end"] - TOLERANCE and is_wrapper(r)]
    if not later:
        return []
    earliest = min(r["ts"] for r in later)
    return [r for r in later if r["ts"] <= earliest + 2 * TOLERANCE]


def wrapper_receipt(receipts, record):
    """The wrapper run a Snakemake job was in, when exactly one fits; None when none or several do."""
    possible = wrapper_candidates(receipts, record)
    return possible[0] if len(possible) == 1 else None


def launch_kind(receipt):
    """matched, unmatched or ambiguous as the gate recorded it; `legacy` for a receipt written before launch matching."""
    kind = receipt.get("launch_match")
    return kind if kind in ("matched", "unmatched", "ambiguous") else "legacy"


def started(receipt):
    """The launch time the gate recorded in a receipt (`started`), or None for a receipt that has none."""
    start = receipt.get("started")
    if isinstance(start, bool) or not isinstance(start, (int, float)) or not math.isfinite(start) \
            or start > receipt["ts"]:
        return None
    return start


def window(receipt):
    """(start, end) of a receipt's attempt: its launch to its report. A receipt with no start is a point at its
    report, so a run that began before another ended and was reported after it is seen only when it records a start."""
    start = started(receipt)
    return (receipt["ts"] if start is None else start), receipt["ts"]


def observed_paths(receipt):
    """The declared output paths a matched attempt saw created or changed between its Pre and Post, or None
    when it observed nothing (a legacy, unmatched or ambiguous receipt, or an observation that was skipped)."""
    seen = receipt.get("outputs_changed")
    if launch_kind(receipt) != "matched" or not receipt.get("attempt_id") \
            or receipt.get("outputs_observation") != "observed" or not isinstance(seen, dict):
        return None
    return {p for key in ("created", "changed") for p in (seen.get(key) if isinstance(seen.get(key), list) else [])
            if isinstance(p, str)}


def candidate_text(receipt, digest):
    """A run in words for a candidate list; no backticks, since the By column's first backticked token reads as its producer."""
    return describe_run(receipt, digest).replace("`", "")


def not_observed(receipt, rel):
    """Why a receipt's attempt gives no attempt-observed evidence for `rel`."""
    kind = launch_kind(receipt)
    if kind == "legacy":
        return "launch link not recorded (the receipt predates launch matching)"
    if kind != "matched":
        return "its launch was {}{}".format(kind, " ({})".format(receipt["launch_note"]) if receipt.get("launch_note") else "")
    seen = observed_paths(receipt)
    if seen is None:
        return "its attempt observed no outputs ({})".format(receipt.get("outputs_observation") or "no observation recorded")
    if any(under(rel, folder) for folder in seen):
        return "its attempt saw the declared folder change, which names no file"
    return "its attempt observed the declared outputs and did not see this one change"


def abandoned_attempts(root):
    """The launches that never reported back (the gate moves them to launches/abandoned/), one dict per attempt:
    started, attempt_id, the plans and approval instances it launched under, its command."""
    folder = gate.state_path(root, "launches", "abandoned")
    found = []
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        record = gate.read_json(os.path.join(folder, name), None)
        if not isinstance(record, dict):
            continue
        for attempt in (record.get("attempts") if record.get("ambiguous") else [record]) or []:
            started = attempt.get("started", attempt.get("ts")) if isinstance(attempt, dict) else None
            if isinstance(started, bool) or not isinstance(started, (int, float)):
                continue
            runs = attempt.get("runs") if isinstance(attempt.get("runs"), dict) else {}
            entries = [e for group in runs.values() if isinstance(group, list) for e in group if isinstance(e, dict)]
            found.append({"started": started, "attempt_id": attempt.get("attempt_id"),
                          "plans": sorted({p for e in entries for p in e.get("plans") or [] if isinstance(p, str)}),
                          "instances": dict(i for e in entries for i in (e.get("instance_ids") or {}).items()),
                          "command": next(iter(runs), "")})
    return found


def grade_output(rel, mtime, file_level, since, mine, digest, jobs, abandoned, wrappers):
    """How well the evidence names the producer of output `rel` (written at `mtime`):
    attempt-observed: a matched attempt of this plan saw the declared output change, and no other attempt
      (any plan, explore included, or a job that was running) overlaps it and could have written it;
    workflow-record: Snakemake's record names the rule, joined to a wrapper run by time (`wrappers` lists those);
    timing-only: only the time of the file against the receipts, which is at most a candidate;
    none: no recorded run.
    Returns owner (the one run to name, or None), producer_attempt, evidence_method, strength
    (`supported` only for a clean attempt-observed; else `candidate` or `unresolved`), candidates, reason and gap
    (a finding for an ambiguity, or None)."""
    result = {"owner": None, "producer_attempt": None, "evidence_method": "none",
              "strength": "unresolved", "candidates": [], "reason": "no recorded run", "gap": None}
    mine_ids = {id(r) for r in mine}

    def fits(r):  # the file's time falls in the attempt that saw it change
        return fits_attempt(r, mtime)

    listed = [r for r in mine if rel in (observed_paths(r) or ()) and fits(r)]
    if listed:
        owner = min(listed, key=lambda r: r["ts"])
        # another attempt could have written it if it ran while the owner did; with no recorded start, from a
        # clock tolerance before the file's time (a run that began earlier and ended later goes unseen)
        low = started(owner) if started(owner) is not None else min(mtime, owner["ts"]) - TOLERANCE
        high = owner["ts"]
        rivals = []
        for r in since:
            if r is owner or r.get("attempt_id") == owner.get("attempt_id"):
                continue
            start, end = window(r)
            if r.get("job_id"):  # a job runs on after its submission is reported
                start, end = r["ts"], (jobs.get(r["job_id"]) or {}).get("end") or time.time()
            if start > high or end < low:
                continue
            seen = observed_paths(r)
            if file_level and seen is not None and id(r) in mine_ids and rel not in seen:
                continue  # an attempt of this plan that watched this very path and did not see it change
            rivals.append(r)
        open_attempts = [a for a in abandoned if low - gate.LAUNCH_SECONDS <= a["started"] <= high]
        result.update(evidence_method="attempt-observed")
        if not rivals and not open_attempts:
            result.update(owner=owner, producer_attempt=owner["attempt_id"], strength="supported", reason=
                          "a matched attempt saw this declared output change, and no overlapping attempt could have written it")
            return result
        names = [candidate_text(r, digest) for r in [owner] + rivals] + [
            "attempt started at {} with no completion record".format(when(a["started"])) for a in open_attempts]
        result.update(candidates=names, reason="an overlapping attempt could also have written it",
                      gap="Output `{}` was observed written by an attempt of this plan, but an overlapping attempt "
                          "could also have written it ({}); attribution is ambiguous.".format(rel, "; ".join(names[1:])))
        return result
    if wrappers is not None:  # Snakemake's record names the rule that wrote it
        result.update(evidence_method="workflow-record",
                      candidates=[candidate_text(r, digest) for r in wrappers])
        if len(wrappers) == 1:
            result.update(owner=wrappers[0], strength="candidate", reason=
                          "Snakemake's record names the rule; the wrapper run is joined to it by time only (" +
                          not_observed(wrappers[0], rel) + ")")
        elif wrappers:
            result.update(reason="{} wrapper runs fit Snakemake's record in time".format(len(wrappers)),
                          gap="Output `{}` was written in a Snakemake job that {} wrapper runs fit in time; "
                              "attribution is ambiguous.".format(rel, len(wrappers)))
        else:
            result.update(reason="Snakemake's record names the rule, but no wrapper run is recorded")
        return result
    later = [r for r in since if r.get("ts", 0) >= mtime - TOLERANCE and not r.get("job_id")]
    batch = [r for r in since if r.get("job_id") and r["ts"] <= mtime + TOLERANCE
             and ((jobs.get(r["job_id"]) or {}).get("end") or time.time()) >= mtime - TOLERANCE]
    earliest = min((r["ts"] for r in later), default=None)
    possible = ([r for r in later if r["ts"] <= earliest + 2 * TOLERANCE] if later else []) + batch
    if possible:
        result.update(evidence_method="timing-only", candidates=[candidate_text(r, digest) for r in possible])
    if len(possible) > 1:
        result.update(reason="competing timestamp-compatible writers",
                      gap="Output `{}` has competing timestamp-compatible writers; attribution is ambiguous.".format(rel))
    elif possible:
        owner = possible[0]
        result.update(owner=owner, strength="candidate", reason="only timing evidence: " + not_observed(owner, rel))
        if abs(owner["ts"] - mtime) > TOLERANCE:
            result.update(reason=result["reason"] + "; only distant timestamp evidence",
                          gap="Output `{}` has only distant timestamp evidence; its producer is unverified.".format(rel))
    return result


def describe_run(receipt, digest):
    if receipt is None:
        return "no recorded run"
    command = receipt.get("command", "")
    label = "`{}` at {}".format(command[:80], when(receipt.get("ts")))
    script = (receipt.get("script") or {}).get("path")
    if script and script not in command[:80]:  # a long interpreter path cuts the script off
        label += " (script `{}`)".format(script)
    if receipt.get("explore"):
        return label + " (explore, not reportable)"
    if digest in receipt.get("plans", []):
        return label
    if receipt.get("plans"):
        return label + " (under plan {})".format(receipt["plans"][-1])
    return label + " (no approved plan)"


CONDA_RUNNERS = ("conda", "mamba", "micromamba")
ACTIVATE = re.compile(r"\b(?:conda|mamba|micromamba)\s+activate\s+([^\s;&|]+)")


def conda_env(root, receipt):
    """{env, prefix, source} of the conda env a run used, from its receipt; None if it names none."""
    declared = receipt.get("command_env") or {}
    if declared.get("manager") == "pixi":
        return None  # pixi projects carry pixi.lock
    name, source = None, None
    if declared.get("manager") in CONDA_RUNNERS and declared.get("env"):
        name, source = declared["env"], "`{} run`".format(declared["manager"])
    for line in receipt.get("env_lines") or [] if not name else []:
        match = ACTIVATE.search(line)
        if match:
            name, source = match.group(1), "`activate` in the job script"
    if not name:
        try:
            words = shlex.split(receipt.get("command", ""))
        except ValueError:
            words = []
        for word in words:
            prefix = os.path.dirname(os.path.dirname(word))
            if os.path.isabs(word) and os.path.basename(os.path.dirname(word)) == "bin" \
                    and os.path.isdir(os.path.join(prefix, "conda-meta")):
                return {"env": os.path.basename(prefix), "prefix": prefix, "source": "interpreter path"}
    if not name:
        if declared or receipt.get("env_lines"):
            return None  # a job's own module, venv or container env, not the session's
        prefix = (receipt.get("hook_env") or {}).get("CONDA_PREFIX")
        return {"env": os.path.basename(prefix), "prefix": prefix, "source": "session `CONDA_PREFIX`"} \
            if prefix else None
    if "/" in name:
        base = os.path.join(root, receipt.get("cwd") or ".")
        return {"env": name, "prefix": os.path.normpath(os.path.join(base, os.path.expanduser(name))),
                "source": source}
    known = read_text(os.path.expanduser("~/.conda/environments.txt")).split()
    matches = sorted({p for p in known if os.path.basename(p.rstrip("/")) == name})
    return {"env": name, "prefix": matches[0] if len(matches) == 1 else None, "source": source}


def pep503(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def pip_packages(prefix, records):
    """The Python packages in a conda env's site-packages that conda did not install: not in any
    conda-meta record's files, or reinstalled since (INSTALLER is no longer conda). Returns
    (requirement lines, unreadable folder names, number also in conda-meta, newest folder mtime)."""
    owned = set()
    for m in records:
        for f in m.get("files") or []:
            head, sep, tail = f.partition("site-packages/")
            if sep:
                owned.add(tail.split("/")[0])
    conda = {pep503(m["name"]): m.get("version", "") for m in records if m.get("name")}
    lines, unreadable, both, newest = [], [], 0, 0
    for path in sorted(glob.glob(os.path.join(prefix, "lib", "python*", "site-packages", "*-info"))):
        base = os.path.basename(path)
        if not base.endswith((".dist-info", ".egg-info")):
            continue
        folder = os.path.isdir(path)  # an .egg-info can be a plain PKG-INFO file
        installer = read_text(os.path.join(path, "INSTALLER")).strip() if folder else ""
        if base in owned and installer in ("", "conda"):
            continue
        headers = {}
        meta = os.path.join(path, "METADATA" if base.endswith(".dist-info") else "PKG-INFO") if folder else path
        for line in read_text(meta).splitlines():
            if not line.strip():
                break
            key, sep, value = line.partition(":")
            if sep and key in ("Name", "Version"):
                headers.setdefault(key, value.strip())
        if not headers.get("Name") or not headers.get("Version"):
            unreadable.append(base)
            continue
        notes = []
        if pep503(headers["Name"]) in conda:
            both += 1
            notes.append("also in conda-meta as {}".format(conda[pep503(headers["Name"])]))
        if installer not in ("", "pip"):
            notes.append("installer: " + installer)
        url = gate.read_json(os.path.join(path, "direct_url.json"), {}) if folder else {}
        vcs = url.get("vcs_info") or {}
        line = "{}=={}".format(headers["Name"], headers["Version"])
        if url.get("url") and vcs.get("vcs") and vcs.get("commit_id"):
            line = "{} @ {}+{}@{}".format(headers["Name"], vcs["vcs"], url["url"], vcs["commit_id"])
        elif url.get("url"):  # a local path or archive: not on an index, so `pip install -r` must skip it
            notes.append("{}: {}".format("editable" if (url.get("dir_info") or {}).get("editable") else "from",
                                         url["url"]))
            line = "# " + line
        lines.append(line + ("  # " + "; ".join(notes) if notes else ""))
        try:
            newest = max(newest, os.stat(path).st_mtime)
        except OSError:
            pass
    return lines, unreadable, both, newest


def conda_snapshots(root, runs, report):
    """`conda list --explicit` of each conda env the plan's runs used and no conda-lock.yml pins,
    read from the env's conda-meta records (conda itself need not be on PATH), and the pip packages
    in each env, locked or not, read from its site-packages."""
    envs = collections.OrderedDict()
    for r in runs:
        env = conda_env(root, r)
        if env:
            locked = any(os.path.basename(l.get("path", "")) == "conda-lock.yml" for l in r.get("lockfiles") or [])
            env = envs.setdefault(env["prefix"] or env["env"], env)
            env["last_run"] = max(env.get("last_run", 0), r.get("ts", 0))
            env["locked"] = env.get("locked", True) and locked
    snapshots = []
    for env in envs.values():
        locked = env.pop("locked")
        meta = os.path.join(env["prefix"] or "", "conda-meta")
        records = [gate.read_json(p, {}) for p in sorted(glob.glob(os.path.join(meta, "*.json")))]
        urls = [] if locked else sorted("{}#{}".format(m["url"], m["md5"]) if m.get("md5") else m["url"]
                                        for m in records if m.get("url"))
        if not env["prefix"] or not records or not (urls or locked):
            report.add("gap", "Conda env `{}` ({}) was not found, so its {}packages were not recorded.".format(
                env["env"], env["source"], "pip " if locked else ""))
            continue
        pip, unreadable, both, pip_changed = pip_packages(env["prefix"], records)
        if unreadable:
            report.add("gap", "Conda env `{}`: {} pip package folder(s) have no readable name and version, so "
                              "they were not recorded: {}.".format(env["env"], len(unreadable),
                                                                   ", ".join("`{}`".format(u) for u in unreadable)))
        pip_stale = pip_changed > env["last_run"] + TOLERANCE
        if pip_stale:
            report.add("gap", "Pip packages in conda env `{}` changed {}, after its last run here ({}); the "
                              "recorded pip list is the env as it is now.".format(
                                  env["env"], when(pip_changed), when(env["last_run"])))
        if not urls and not pip:
            continue  # locked, and nothing pip-installed
        try:
            changed = 0 if locked else os.stat(os.path.join(meta, "history")).st_mtime
        except OSError:
            changed = 0
        stale = changed > env["last_run"] + TOLERANCE
        pip_note = "{} pip package{}{}".format(len(pip), "" if len(pip) == 1 else "s",
                                               " ({} also in conda-meta)".format(both) if both else "")
        if stale:
            report.add("gap", "Conda env `{}` changed {}, after its last run here ({}); the recorded package "
                              "list is the env as it is now.".format(env["env"], when(changed), when(env["last_run"])))
        elif locked:
            report.add("info", "Conda env `{}` ({}): conda packages pinned by `conda-lock.yml`; {} recorded.".format(
                env["env"], env["source"], pip_note))
        else:
            report.add("info", "Conda env `{}` ({}): {} packages recorded{}.".format(
                env["env"], env["source"], len(urls), "; " + pip_note if pip else ""))
        snapshots.append(dict(env, packages=urls, changed_after_run=stale, pip=pip, pip_changed_after_run=pip_stale))
    return snapshots


SNAKE_CONDA = re.compile(r"^[ \t]*conda:\s*[\"']([^\"'\n]+)[\"']", re.MULTILINE)
SNAKE_CONDA_ANY = re.compile(r"^[ \t]*conda:", re.MULTILINE)
SNAKE_INCLUDE = re.compile(r"^[ \t]*include:\s*[\"']([^\"'\n]+)[\"']", re.MULTILINE)
SNAKE_INCLUDE_ANY = re.compile(r"^[ \t]*include:", re.MULTILINE)
USE_CONDA = re.compile(r"--use-conda\b|--(?:software-deployment-method|sdm)[ =]conda\b")


def snake_conda_decls(root, rel, report, seen=None):
    """[(env file path relative to the repository, rule name)] for each literal `conda:` path in the
    Snakefile `rel` and its literal `include:` files. Paths resolve against the including file's folder,
    as Snakemake does. A `conda:` or `include:` that is not a string literal is a gap, not skipped."""
    seen = set() if seen is None else seen
    if rel in seen or len(seen) > 50:
        return []
    seen.add(rel)
    text = read_text(os.path.join(root, rel))
    if not text:
        report.add("gap", "Snakefile `{}` could not be read, so its rule envs were not recorded.".format(rel))
        return []
    here = os.path.dirname(rel)
    rules = [(m.start(), m.group(1)) for m in SNAKE_RULE.finditer(text)]
    found = []
    for m in SNAKE_CONDA.finditer(text):
        rule = next((name for start, name in reversed(rules) if start < m.start()), "")
        found.append((os.path.normpath(os.path.join(here, m.group(1))), rule))
    if len(SNAKE_CONDA_ANY.findall(text)) > len(found):
        report.add("gap", "`{}` has a `conda:` that is not a string literal, so that rule env was not "
                          "recorded.".format(rel))
    includes = SNAKE_INCLUDE.findall(text)
    if len(SNAKE_INCLUDE_ANY.findall(text)) > len(includes):
        report.add("gap", "`{}` has an `include:` that is not a string literal, so rule envs in it were not "
                          "recorded.".format(rel))
    for inc in includes:
        found += snake_conda_decls(root, os.path.normpath(os.path.join(here, inc)), report, seen)
    return found


def rule_envs(root, runs, report):
    """The per-rule conda envs of a `snakemake --use-conda` run: each literal `conda:` env file's sha256
    and, when exactly one built env under `.snakemake/conda/` is a byte-identical copy of that file, its
    conda-meta packages and its pip packages. Files are only read. Anything else (file missing or
    unreadable, no built env, several, no conda-meta records) is a gap, never `recorded`. The folder
    layout is not validated against a real Snakemake run: only synthetic folders were available."""
    out, done = [], set()
    for r in runs:
        if r.get("kind") != "snakemake":
            continue
        cwd = r.get("cwd") or "."
        snakefiles = [p for p in ran_paths(root, r) if is_snakefile(p)] or [os.path.join(cwd, "Snakefile")]
        decls = []
        for smk in snakefiles:
            if os.path.isfile(os.path.join(root, smk)):
                decls += snake_conda_decls(root, os.path.normpath(smk), report)
        flagged = bool(USE_CONDA.search(r.get("command", "")))
        for env_rel, rule in decls:
            if (cwd, env_rel, flagged) in done:
                continue
            done.add((cwd, env_rel, flagged))
            label = "Rule env `{}` (rule `{}`)".format(env_rel, rule or "?")
            if not flagged:
                report.add("gap", "{} is declared, but the run does not show `--use-conda` (a profile can set "
                                  "it), so it was not recorded.".format(label))
                continue
            try:
                with open(os.path.join(root, env_rel), "rb") as handle:
                    data = handle.read()
            except OSError:
                report.add("gap", "{} could not be read, so it was not recorded.".format(label))
                continue
            digest = hashlib.sha256(data).hexdigest()
            built = []
            for yaml in sorted(glob.glob(os.path.join(root, cwd, ".snakemake", "conda", "*.yaml"))):
                try:
                    with open(yaml, "rb") as handle:
                        same = handle.read() == data
                except OSError:
                    continue
                if same and os.path.isdir(yaml[:-len(".yaml")]):
                    built.append(yaml[:-len(".yaml")])
            if len(built) != 1:
                report.add("gap", "{}: env file sha256 {}, but {} built env(s) under `.snakemake/conda/` match "
                                  "it, so its packages were not recorded.".format(
                                      label, digest[:12], "no" if not built else len(built)))
                continue
            meta = os.path.join(built[0], "conda-meta")
            records = [gate.read_json(p, {}) for p in sorted(glob.glob(os.path.join(meta, "*.json")))]
            urls = sorted("{}#{}".format(m["url"], m["md5"]) if m.get("md5") else m["url"]
                          for m in records if m.get("url"))
            if not urls:
                report.add("gap", "{}: env file sha256 {}; the built env has no readable `conda-meta` records "
                                  "(format not recognised), so its packages were not recorded.".format(
                                      label, digest[:12]))
                continue
            pip, unreadable, both, _ = pip_packages(built[0], records)
            if unreadable:
                report.add("gap", "{}: {} pip package folder(s) have no readable name and version, so they "
                                  "were not recorded.".format(label, len(unreadable)))
            try:
                changed = os.stat(os.path.join(meta, "history")).st_mtime
            except OSError:
                changed = 0
            stale = changed > r.get("ts", 0) + TOLERANCE
            if stale:
                report.add("gap", "{} changed {}, after its run here ({}); the recorded list is the env as it "
                                  "is now.".format(label, when(changed), when(r.get("ts", 0))))
            report.add("info", "{}: file sha256 {}, {} packages recorded{}.".format(
                label, digest[:12], len(urls), "; {} pip".format(len(pip)) if pip else ""))
            out.append({"file": env_rel, "rule": rule, "sha256": digest, "prefix": built[0], "packages": urls,
                        "pip": pip, "changed_after_run": stale, "synthetic_format_only": True})
    return out


def prose_validation(plan, binding, report):
    """F06 residual, info: Validation cells that hold prose while no validation binding covers their row. The
    cell is not executed or reconciled, so this says so; it is not a gap (the plan did not ask for a check)."""
    rows = plan_rows(plan)[0]
    covered = set(str(c.get("plan_row")) for c in (binding or {}).get("checks") or [])
    prose = [key for key, row in rows.items() if key not in covered
             and row.get("validation", "").strip(" -\u2013\u2014*_").lower() not in ("", "none", "n/a", "na")]
    if prose:
        report.add("info", "{} Validation cell{} prose only; nothing checks {}.".format(
            len(prose), " is" if len(prose) == 1 else "s are", "it" if len(prose) == 1 else "them"))


def default_reasons(plan, report):
    """D9, advisory: each plan row whose `default:` gives no usable reason is an info finding, so the
    status does not change. The check lives in plan-review's scripts and is imported from the plugin
    root, as gate.py is; a checker that is missing or fails is a gap, like a missing scilintr."""
    folder = os.path.join(PLUGIN_ROOT, "skills", "plan-review", "scripts")
    try:
        if folder not in sys.path:
            sys.path.insert(0, folder)
        import default_reasons as module
        found, defaults, flags = module.check_plan(plan)
    except Exception as error:  # ImportError, SyntaxError, or a bug in the checker
        report.add("gap", "Default reasons not checked: `{}` could not run ({}: {}).".format(
            os.path.join(folder, "default_reasons.py"), type(error).__name__, cell(str(error))[:120]))
        return
    for flag in flags:
        report.add("info", "Default without a usable reason (advisory): " + cell(module.describe(flag)))


# ---------------------------------------------------------------- fact tags (D7)

FACT_TAG = re.compile(r"\[(human-stated|agent-derived|agent-asserted)(?::\s*([^\]]*))?\][\s.;,]*$")
BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def section_bullets(text, label):
    """[(line number, item text)] for the list under the first line that labels a section `label`
    (`## Evidence`, `**Evidence**`, `Evidence:`, `- **Evidence**:`), up to the first other line.
    ponytail: a prose paragraph between the label and its list ends the section early."""
    lines = HTML_COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), text).split("\n")
    head = re.compile(r"^\s*(?:#{1,6}\s+|[-*]\s+)?(?:\*\*)?" + re.escape(label) +
                      r"(?:\*\*)?(?:\s*$|\s*[:.])", re.I)
    start = next((i for i, line in enumerate(lines) if head.match(line)), None)
    items = []
    for i, line in enumerate(lines[start + 1:] if start is not None else [], start=(start or 0) + 2):
        match = BULLET.match(line)
        if match:
            items.append([i, match.group(1).strip()])
        elif items and line[:1] in (" ", "\t") and line.strip():
            items[-1][1] += " " + line.strip()
        elif line.strip():
            break
    return [tuple(item) for item in items]


def fact_tags(where, items, report):
    """D7, advisory: count each fact's provenance tag and flag an untagged fact, an `agent-derived`
    one without its artifact, and an `agent-asserted` one without a source. Info only."""
    if not items:
        return
    counts, flags = collections.Counter(), []
    for line, item in items:
        match = FACT_TAG.search(item)
        tag, source = (match.group(1), (match.group(2) or "").strip()) if match else (None, "")
        counts[tag or "untagged"] += 1
        if not tag:
            flags.append("L{} untagged `{}`".format(line, cell(item)[:40].replace("`", "")))
        elif tag == "agent-derived" and not source:
            flags.append("L{} agent-derived without its artifact".format(line))
        elif tag == "agent-asserted" and source.lower() in ("", "none"):
            flags.append("L{} agent-asserted without a source".format(line))
    if counts["untagged"] == len(items):
        report.add("info", "Fact tags: {} fact(s) in {}, none tagged (written before D7, or untagged).".format(
            len(items), where))
        return
    shown = ", ".join("{} {}".format(counts[t], t) for t in ("agent-derived", "human-stated", "agent-asserted",
                                                            "untagged") if counts[t])
    report.add("info", "Fact tags in {}: {}{}.".format(where, shown, "; flagged: " + "; ".join(flags)
                                                       if flags else ""))


# ---------------------------------------------------------------- claims (D1)

CLAIMS_BLOCK = re.compile(r"<!--\s*claims\b(.*?)-->", re.S)
NUMBER = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][+-]?\d+)?"
CLAIM_LINE = re.compile(r"^\s*(?:[-*]\s+)?(<=|>=|<|>|=)?\s*(" + NUMBER + r")(%?)\s*\|\s*([^|]+?)\s*(?:\|.*)?$")
PROSE_NUMBER = re.compile(r"(?<![\w.])" + NUMBER + r"(?!\w)")
SECTION_HEADING = re.compile(r"^#{1,6}\s", re.M)
SKIPPED_PROSE = re.compile(r"<!--.*?-->|`[^`\n]*`|\]\([^)]*\)", re.S)


def number(text):
    try:
        value = decimal.Decimal(text.replace(",", ""))
        return value if value.is_finite() else None
    except (decimal.InvalidOperation, AttributeError):
        return None


def agrees(claim, qualifier, cell_value):
    """The claim is the cell rounded (half-up or half-even) or truncated to the claim's last digit;
    an inequality is compared raw."""
    if qualifier in ("<", ">", "<=", ">="):
        return {"<": cell_value < claim, ">": cell_value > claim, "<=": cell_value <= claim,
                ">=": cell_value >= claim}[qualifier]
    try:
        step = decimal.Decimal(1).scaleb(claim.as_tuple().exponent)
        return any(cell_value.quantize(step, rounding=r) == claim
                   for r in (decimal.ROUND_HALF_UP, decimal.ROUND_HALF_EVEN, decimal.ROUND_DOWN))
    except decimal.InvalidOperation:
        return False


def claim_cell(path, column, row, max_bytes):
    """(the cell's text, None) or (None, why it cannot be read). A table needs a row label
    (first-column value) unless it has one data row: the guard against a common value such
    as 0.05 matching some row of a large column."""
    try:
        if os.path.getsize(path) > max_bytes:
            return None, "the file is over the size budget (--hash-mb), so it was not read"
        with open(path, encoding="utf-8", errors="replace", newline="") as handle:
            if path.endswith(".json"):
                value = json.load(handle)
                for key in column.split("."):
                    value = value[int(key)] if isinstance(value, list) else value[key]
                return (None, "`{}` is not a number".format(column)) if isinstance(value, (dict, list)) \
                    else (str(value), None)
            text = handle.read()
    except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
        return None, "`{}` could not be read ({})".format(column, type(error).__name__)
    first = text.split("\n", 1)[0]
    rows = [r for r in csv.reader(io.StringIO(text), delimiter="\t" if "\t" in first else ",") if r]
    if not rows:
        return None, "the file is empty"
    if column == "rows":
        return str(len(rows) - 1), None
    if column not in rows[0]:
        return None, "no column `{}`".format(column)
    if rows[0].count(column) > 1:
        return None, "{} columns are named `{}`; the cell is ambiguous".format(rows[0].count(column), column)
    index = rows[0].index(column)
    hits = [r for r in rows[1:] if r[0] == row] if row else rows[1:]
    if row and not hits:
        return None, "no row `{}`".format(row)
    if not hits:
        return None, "the table has no data rows"
    if len(hits) > 1:
        return None, "{} rows {}; name one by its first-column label".format(
            len(hits), "are labelled `{}`".format(row) if row else "match")
    return (hits[0][index] if index < len(hits[0]) else ""), None


def check_claims(root, analysis_dir, outputs, extra, report, max_bytes):
    """Check each `<!-- claims -->` line of the analysis doc, the Markdown outputs, and the --claims
    documents against the output cell it names. Numbers in the block's own section that the block
    does not cover are listed as info: the block, not the prose, is the checked record."""
    by_path = {row["path"]: row for row in outputs}
    docs = document_set(root, analysis_dir, outputs, extra)
    checked = []
    for doc in sorted(set(docs), key=docs.index):
        asked = doc in [rel_or_abs(root, os.path.abspath(p)) for p in extra]
        text = read_text(os.path.join(root, doc)) if os.path.isfile(os.path.join(root, doc)) else None
        blocks = list(CLAIMS_BLOCK.finditer(text or ""))
        if not blocks:
            if asked:
                report.add("gap", "Claims not checked in `{}`: {}.".format(
                    doc, "it does not exist" if text is None else "it has no `<!-- claims -->` block"))
            continue
        claims, values, unparsed = [], [], 0
        for block in blocks:
            line_no = text.count("\n", 0, block.start(1)) + 1
            for offset, line in enumerate(block.group(1).split("\n")):
                if not line.strip():
                    continue
                where = "`{}:{}`".format(doc, line_no + offset)
                match = CLAIM_LINE.match(line)
                words = match.group(4).split(None, 2) if match else []
                if len(words) < 2:
                    unparsed += 1
                    report.add("gap", "{}: claims line does not parse (want `value | file column [row]`): "
                                      "`{}`.".format(where, cell(line.strip())[:80]))
                    continue
                qualifier, raw, percent = match.group(1), match.group(2), match.group(3)
                claim = number(raw)
                values.append(claim)
                path = os.path.normpath(os.path.join(analysis_dir or "", words[0]))
                if path not in by_path and os.path.normpath(words[0]) in by_path:
                    path = os.path.normpath(words[0])
                entry = {"doc": doc, "line": line_no + offset, "claim": (qualifier or "") + raw + percent,
                         "file": path, "column": words[1], "row": words[2] if len(words) > 2 else None,
                         "observed": None, "registered": os.path.basename(path) == "numbers.json"}
                claims.append(entry)
                coordinate = "`{}` {}{}".format(path, words[1], " row " + entry["row"] if entry["row"] else "")
                if claim is None:
                    entry.update(verdict="unverified", reason="the claim is outside the supported numeric range")
                elif path not in by_path:
                    why = "it does not exist" if not os.path.exists(os.path.join(root, path)) \
                        else "it is not an output this plan's runs wrote"
                    entry.update(verdict="unverified", reason="cites `{}`, but {}".format(path, why))
                else:
                    found, why = claim_cell(os.path.join(root, path), words[1], entry["row"], max_bytes)
                    observed = number(found) if found is not None else None
                    entry["observed"] = found
                    if found is not None and observed is None:
                        why = "{} holds `{}`, not a finite number".format(coordinate, cell(found)[:40])
                    if observed is None:
                        entry.update(verdict="unverified", reason=why)
                    elif agrees(claim, qualifier, observed):
                        entry["verdict"] = "verified"
                    else:
                        entry["verdict"] = "mismatch"
                        if percent:
                            try:
                                if agrees(claim, qualifier, observed * 100):
                                    entry["verdict"] = "verified-transform"
                            except decimal.DecimalException:
                                entry.update(verdict="unverified", reason="the percentage transform is outside "
                                             "the supported numeric range")
                    if entry["verdict"].startswith("verified") and by_path[path].get("explore"):
                        entry["verdict"] = "explore-only"
                if entry["verdict"] == "mismatch":
                    report.add("block", "{} claims {}, but {} holds {}.".format(
                        where, entry["claim"], coordinate, found))
                elif entry["verdict"] == "explore-only":
                    report.add("block", "{} claims {} from {}, which an explore run wrote; explore outputs "
                                        "are not reportable.".format(where, entry["claim"], coordinate))
                elif entry["verdict"] == "unverified":
                    report.add("gap", "{} claim {} is unverified: {}.".format(where, entry["claim"],
                                                                             entry["reason"]))
        # Prose numbers in each block's section (heading to heading) that no claim covers.
        loose = []
        for block in blocks:
            starts = [m.start() for m in SECTION_HEADING.finditer(text)]
            begin = max([s for s in starts if s < block.start()] or [0])
            end = min([s for s in starts if s > block.end()] or [len(text)])
            section = SKIPPED_PROSE.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), text[begin:end])
            for m in PROSE_NUMBER.finditer(section):
                value = number(m.group())
                if value is not None and value not in values and (begin + m.start(), m.group()) not in loose:
                    loose.append((begin + m.start(), m.group()))
        if loose:
            shown = ["L{} `{}`".format(text.count("\n", 0, at) + 1, raw) for at, raw in loose]
            report.add("info", "{} number(s) in `{}` near its claims block are not claims, so not checked: "
                               "{}{}.".format(len(loose), doc, ", ".join(shown[:12]),
                                              " and {} more".format(len(shown) - 12) if len(shown) > 12 else ""))
        counts = collections.Counter(c["verdict"] for c in claims)
        matched = counts["verified"] + counts["verified-transform"]
        compared = matched + counts["mismatch"] + counts["explore-only"]  # a cell was read and compared
        coverage = {"blocks": len(blocks), "claim_lines": len(claims) + unparsed, "unparsed_lines": unparsed,
                    "cells_checked": compared, "matched": matched, "mismatched": counts["mismatch"],
                    "unverified": counts["unverified"], "registered": sum(1 for c in claims if c["registered"]),
                    "prose_numbers_listed": len(loose)}
        checked.append({"doc": doc, "claims": claims, "counts": dict(counts), "not_claims": len(loose),
                        "coverage": coverage})
    registered = sum(c["coverage"]["registered"] for c in checked)
    if registered:
        report.add("info", "{} claim(s) cite a registered `numbers.json` value: Mycelium's `register_value` upserts, so a "
                           "matching value shows the file's current content, not which run wrote it. Run attribution needs "
                           "the output's producer (artifact and run identity) above, not the number.".format(registered))
    return checked


# ---------------------------------------------------------------- citation resolution (D2)

DOI = re.compile(r"(?<![\w/])10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")
PMID = re.compile(r"\bPMID:?\s*(\d{4,9})\b", re.I)
ARXIV = re.compile(r"\barXiv:\s*(\d{4}\.\d{4,5})(?:v\d+)?\b", re.I)
REFERENCE_HEADING = re.compile(r"^#{1,6}\s*(?:references|bibliography|literature cited|works cited)\s*$",
                               re.I | re.M)
REFERENCE_LINE = re.compile(r"^\s*(?:[-*]\s+|\d+[.)]\s+)?\S.*\(\d{4}[a-z]?\)")
CITATION_DELAY = 1.0  # seconds between requests: Crossref, NCBI and arXiv each ask for about one
MAX_LOOKUP_BYTES = 200000
CITATIONS_SHOWN = 40


def document_set(root, analysis_dir, outputs, extra):
    """The researcher's own documents, in the order they are checked: the analysis doc, the Markdown
    outputs of the plan's runs, then the `--claims` documents."""
    by_path = {row["path"]: row for row in outputs}
    docs = [p for p in by_path if p.endswith(".md")]
    if analysis_dir:
        name = os.path.basename(analysis_dir).upper().replace("-", "_") + ".md"
        docs.insert(0, os.path.join(analysis_dir, name))
    docs += [rel_or_abs(root, os.path.abspath(p)) for p in extra]
    return sorted(set(docs), key=docs.index)


def trim_identifier(raw):
    """A matched DOI without the punctuation of the sentence it sat in: trailing `.`, `,`, `;` and `:`
    always, and a trailing `)` or `]` only when no opening one balances it (DOIs may contain
    parentheses, as in `10.1002/(SICI)1099-0`)."""
    out = raw.rstrip(".,;:")
    pairs = {")": "(", "]": "["}
    while out and out[-1] in pairs and out.count(out[-1]) > out.count(pairs[out[-1]]):
        out = out[:-1]
    return out


def citations_in_text(text, doc):
    """One entry per citation: `{"doc", "line", "text", "kind", "id"}`. `kind` is `doi`, `pmid` or
    `arxiv` when the line carries an identifier, and `none` for a reference-shaped line under a
    reference heading that carries none (those cannot be resolved, only listed)."""
    starts = [m.start() for m in SECTION_HEADING.finditer(text)]
    sections = [(m.start(), min([s for s in starts if s > m.start()] or [len(text)]))
                for m in REFERENCE_HEADING.finditer(text)]
    entries, offset = [], 0
    for lineno, line in enumerate(text.split("\n"), 1):
        here, offset = offset, offset + len(line) + 1
        found = [("doi", trim_identifier(m.group())) for m in DOI.finditer(line)]
        found += [("pmid", m.group(1)) for m in PMID.finditer(line)]
        found += [("arxiv", m.group(1)) for m in ARXIV.finditer(line)]
        for kind, ident in found:
            entries.append({"doc": doc, "line": lineno, "text": line.strip(), "kind": kind, "id": ident})
        if not found and REFERENCE_LINE.match(line) and any(a <= here < b for a, b in sections):
            entries.append({"doc": doc, "line": lineno, "text": line.strip(), "kind": "none", "id": None})
    return entries


def normalise(text):
    """Lowercase, punctuation to spaces, whitespace collapsed: for comparing a title or a name with
    text a researcher wrote."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]+", " ", (text or "").lower())).strip()


def citation_gist(entry):
    """How a citation is named in a finding: its identifier, or the start of its text."""
    if entry["kind"] == "none":
        return "citation \"{}\"".format(cell(entry["text"])[:70])
    return "{} {}".format(entry["kind"].upper() if entry["kind"] != "arxiv" else "arXiv", entry["id"])


def citation_request(kind, ident, contact):
    """(url, headers) for one identifier. A contact address is sent only when the user configured
    one: Crossref asks for one in the URL, NCBI for `tool` and `email`."""
    agent = "mycelium-extra-verify" + (" (mailto:{})".format(contact) if contact else "")
    if kind == "doi":
        url = "https://api.crossref.org/works/" + urllib.parse.quote(ident)
        if contact:
            url += "?mailto=" + urllib.parse.quote(contact)
        return url, {"User-Agent": agent}
    if kind == "pmid":
        url = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&retmode=json&id="
               + urllib.parse.quote(ident) + "&tool=mycelium-extra")
        if contact:
            url += "&email=" + urllib.parse.quote(contact)
        return url, {"User-Agent": agent}
    return "http://export.arxiv.org/api/query?id_list=" + urllib.parse.quote(ident), {"User-Agent": agent}


def parse_lookup(kind, ident, body):
    """(title, first author's surname) from a service's reply, or (None, None) when it has no record."""
    text = body.decode("utf-8", "replace")
    if kind == "doi":
        message = (json.loads(text).get("message") or {})
        titles = message.get("title") or []
        authors = message.get("author") or []
        return (titles[0] if titles else None), (authors[0].get("family") if authors else None)
    if kind == "pmid":
        record = (json.loads(text).get("result") or {}).get(ident) or {}
        authors = record.get("authors") or []
        name = authors[0].get("name", "") if authors else ""
        return record.get("title"), (name.split()[0] if name.split() else None)
    found = re.search(r"<entry>.*?<title>(.*?)</title>", text, re.S)
    if not found:
        return None, None
    title = re.sub(r"\s+", " ", found.group(1)).strip()
    author = re.search(r"<entry>.*?<name>(.*?)</name>", text, re.S)
    parts = author.group(1).split() if author else []
    return title, (parts[-1] if parts else None)


def lookup_citation(kind, ident, contact, timeout=20):
    """(title, surname, verdict, note) for one identifier over the network.

    `resolved` means the service has a record; `unresolved` that it says it has none (the identifier
    does not exist); `not checked (request failed)` that the request could not be made at all — no
    network, a refused connection, a timeout — which is a gap, never a pass."""
    url, headers = citation_request(kind, ident, contact)
    try:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=timeout) as reply:  # noqa: S310 - https, fixed hosts
            body = reply.read(MAX_LOOKUP_BYTES)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None, None, "unresolved", "the service has no record of it (HTTP 404)"
        return None, None, "not checked (request failed)", "the service answered HTTP {}".format(error.code)
    except (urllib.error.URLError, OSError, ValueError) as error:
        return None, None, "not checked (request failed)", "the request failed: {}".format(
            cell(str(getattr(error, "reason", error)))[:120])
    try:
        title, surname = parse_lookup(kind, ident, body)
    except (ValueError, AttributeError, TypeError, KeyError):
        return None, None, "not checked (request failed)", "the service's reply did not parse"
    if not title:
        return None, None, "unresolved", "the service has no record of it"
    return title, surname, "resolved", ""


def citation_match(line, title, surname):
    """(whether the title appears in the citation text, whether the first author does).

    A title matches when most of its significant words are in the line, so an abbreviated citation
    is not called a mismatch; a surname matches on the whole word."""
    words = normalise(line)
    significant = [w for w in normalise(title).split() if len(w) > 3]
    found = sum(1 for w in significant if w in words.split() or w in words)
    title_ok = bool(significant) and found >= max(1, math.ceil(0.7 * len(significant)))
    author_ok = bool(surname) and normalise(surname) in words.split()
    return title_ok, author_ok


def check_citations(root, analysis_dir, outputs, extra, report, resolve=False, contact=None):
    """Resolve every DOI, PMID and arXiv ID in the checked documents.

    Offline (the default) each identifier is `not checked (offline)`, which is a gap: verify will not
    report a citation it did not check as resolved. With `resolve`, each identifier is queried once,
    rate-limited, and classified `resolved`, `mismatch`, `unresolved` (no such record) or
    `not checked (request failed)`. A reference with no identifier is listed, never resolved."""
    docs = document_set(root, analysis_dir, outputs, extra)
    entries = []
    for doc in docs:
        path = os.path.join(root, doc)
        if os.path.isfile(path):
            entries += citations_in_text(read_text(path), doc)
    looked = []
    for index, entry in enumerate(entries):
        where = "`{}:{}`".format(entry["doc"], entry["line"])
        on_screen = index < CITATIONS_SHOWN
        if entry["kind"] == "none":
            entry["verdict"] = "no identifier"
            if on_screen:
                report.add("info", "{}: {} carries no DOI, PMID or arXiv ID, so nothing was "
                                   "resolved.".format(where, citation_gist(entry)))
        elif not resolve:
            entry["verdict"] = "not checked (offline)"
            if on_screen:
                report.add("gap", "{}: {} not checked: resolving citations needs `--resolve-citations` "
                                  "and network access; offline this is a gap, not a pass.".format(
                                      where, citation_gist(entry)))
        else:
            title, surname, verdict, note = lookup_citation(entry["kind"], entry["id"], contact)
            if verdict == "resolved":
                title_ok, author_ok = citation_match(entry["text"], title, surname)
                if not (title_ok and author_ok):
                    verdict = "mismatch"
                    wrong = ([] if title_ok else ["the title"]) + ([] if author_ok else ["the first author"])
                    note = "the record is \"{}\" by {}, and the citation text does not name {}".format(
                        cell(title)[:90], surname or "an unnamed author", " or ".join(wrong))
            entry.update(verdict=verdict, title=title, author=surname, note=note)
            if on_screen:
                if verdict == "resolved":
                    report.add("info", "{}: {} resolved to \"{}\" by {}.".format(
                        where, citation_gist(entry), cell(title)[:90], surname or "an unnamed author"))
                elif verdict == "mismatch":
                    report.add("block", "{}: {} does not match the record: {}.".format(
                        where, citation_gist(entry), note))
                elif verdict == "unresolved":
                    report.add("block", "{}: {} is unresolved: {}.".format(where, citation_gist(entry), note))
                else:
                    report.add("gap", "{}: {} was {}. Network access is opt-in, so an unchecked "
                                      "citation stays a gap.".format(where, citation_gist(entry), verdict))
        looked.append(entry)
        if resolve and entry["kind"] != "none" and index + 1 < len(entries):
            time.sleep(CITATION_DELAY)  # one request per identifier, spaced as each service asks
    if len(entries) > CITATIONS_SHOWN:
        report.add("info", "{} more citation(s) were checked; `--json` or `write` lists them all.".format(
            len(entries) - CITATIONS_SHOWN))
    if not entries and docs:
        report.add("info", "No DOI, PMID or arXiv ID in the checked document(s).")
    return looked


def plan_runs(receipts, digest, approved_at, instance=None):
    """(the plan's runs, oldest first; when its window opens). Re-approving the same plan text
    rewrites approved_at, so the runs are every non-explore receipt naming it, and the window
    opens at the earliest of them. With an approval `instance`, only the runs that were launched
    under that instance count: a receipt of another instance, or one that records none (written before
    instances), is history and cannot establish this freeze."""
    mine = sorted((r for r in receipts if digest in r.get("plans", []) and not r.get("explore")
                   and (instance is None or r.get("approval_instance") == instance)),
                  key=lambda r: r["ts"])
    return mine, min([approved_at] + [r["ts"] for r in mine])


def load_instance(root, digest, instance_id):
    """The approval instance record `approval-instances/<digest>/<instance_id>.json` if it is there and well formed, else None."""
    path = gate.state_path(root, "approval-instances", digest, instance_id + ".json")
    record = gate.read_json(path, None) if os.path.isfile(path) else None
    approved = record.get("approved_at") if isinstance(record, dict) else None
    if not isinstance(record, dict) or record.get("hash") != digest or record.get("instance_id") != instance_id \
            or isinstance(approved, bool) or not isinstance(approved, (int, float)) \
            or any(record.get(key) is not None and not gate.valid_pins(record[key]) for key in ("pins", "scripts")):
        return None
    return record


def pick_instance(root, digest, plan, wanted):
    """(instance id, record) for `--instance`: an exact id or a unique prefix of this plan's instances.
    The record must hold this plan's text (by its sha256), pins that parse, and the id it is filed under."""
    folder = gate.state_path(root, "approval-instances", digest)
    names = [n[:-5] for n in sorted(os.listdir(folder)) if n.endswith(".json")] if os.path.isdir(folder) else []
    found = [n for n in names if n == wanted] or [n for n in names if wanted and n.startswith(wanted)]
    if len(found) != 1:
        sys.exit("verify: {} for plan {}. Known instances: {}.".format(
            "no approval instance " + wanted if not found else "approval instance prefix {} is ambiguous".format(wanted),
            digest, ", ".join(names) or "none"))
    record = load_instance(root, digest, found[0])
    if record is None or record.get("plan_sha256") != hashlib.sha256(plan.encode("utf-8")).hexdigest():
        sys.exit("verify: approval instance {} of plan {} is invalid or does not hold this plan's text; "
                 "restore it from the record before verifying.".format(found[0], digest))
    return found[0], record


def edit_evidence(root, path, budget, receipts):
    """One sentence on whether an approval covers the script's current version: a plan that pinned
    it, a run of it under a plan approved after the file was last modified (by file time), a run
    under a plan approved before that, or no plan at all. "" when the file cannot be hashed."""
    sha = gate.fingerprint(os.path.join(root, path), budget).get("sha256")  # not given the pin: it skips the hash when the size changed
    if not sha:
        return ""
    for folder in ("script-pins", "approvals"):
        names = sorted(os.listdir(gate.state_path(root, folder))) if os.path.isdir(gate.state_path(root, folder)) else []
        for name in names:
            record = gate.read_json(gate.state_path(root, folder, name), {})
            pin = (record if folder == "script-pins" else record.get("scripts") or {}).get(path) or {}
            if pin.get("sha256") == sha:
                return "Plan {} pinned this version, so an approval covers it; check that plan instead.".format(name[:8])
    folder = gate.state_path(root, "repins")
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:  # the gate re-pinned this version at a run
        if any(e["rel"] == path and e["pin"].get("sha256") == sha for e in gate.read_repins(root, name.split(".")[0])):
            return "Plan {} re-pinned this version at a run (a working scope, not a freeze); `freeze {}` approves it.".format(
                name[:8], name[:8])
    ran = [(r, (r.get("script") or {})) for r in receipts
           if r.get("plans") and not r.get("explore") and (r.get("script") or {}).get("path") == path
           and (r.get("script") or {}).get("sha256") == sha]
    older = None
    for r, recorded in reversed(ran):
        for plan_hash in r["plans"]:
            approved = gate.read_json(gate.state_path(root, "approvals", plan_hash + ".json"), {}).get("approved_at", 0)
            if approved >= recorded.get("mtime", 0):
                return ("This version ran under plan {} (approved {}), after the file was last modified, "
                        "so an approval covers it by file time; check that plan instead.".format(plan_hash, when(approved)))
            older = older or plan_hash
    if older:
        return ("This version ran under plan {}, but that plan was approved before the file was last "
                "modified, so no approval covers it.".format(older))
    return "This version has not run under any plan, so no approval covers it."


def gate_error_gaps(root, report, approved_at, sessions):
    """Gaps for the gate's own errors (`gate-errors.jsonl`) inside the plan's window, approval to now.
    A gate that failed open did not check or record what it saw, so observation is incomplete there.
    An error counts when its session is one of `sessions` (the plan's approval and credited
    receipts) or is not recorded; one before the approval, or from another session, is not this
    plan's. The record gives a time and an event, never an action: this is a bounded gap."""
    path = gate.state_path(root, "gate-errors.jsonl")
    if not os.path.exists(path):
        return 0
    invalid = []
    try:
        errors = read_jsonl(path, invalid)
    except (OSError, ValueError):
        errors = []
        invalid = ["file"]
    if invalid:
        report.add("gap", "The gate's error journal `{}` is unreadable or has {} malformed record(s) (lines {}); "
                   "observation history unavailable, so errors in this plan's window may be missing.".format(
                       os.path.relpath(path, root), len(invalid), ", ".join(map(str, invalid[:12]))))
    counted = 0
    for error in errors:
        session = error.get("session_id")
        if int(approved_at) <= error["ts"] <= time.time() + TOLERANCE \
                and (not isinstance(session, str) or not session or session in sessions):
            counted += 1
            event, decision = error.get("event"), error.get("decision")
            report.add("gap", "Gate error at {} (event `{}`{}{}); observation is incomplete there: the gate did "
                       "not check or record what it saw, so a run in that period may be missing from the "
                       "receipts. This is not a record that any specific action went unobserved.".format(
                           when(error["ts"]), str(event)[:40] if event else "unknown",
                           ", decision {}".format(str(decision)[:20]) if decision else "",
                           ", session {}".format(session) if isinstance(session, str) and session else ""))
    return counted


def instance_findings(report, digest, chosen, current, frozen, history, mine, approved_at, explicit, failed=()):
    """What the approval instance means for this check. Runs under another instance, or under none recorded,
    are history: they do not establish the freeze being verified, so none under it is a gap."""
    if chosen is None:
        report.add("info", "Approval {} predates approval instances (no instance id): it is read as one freeze, "
                           "and any earlier approval of the same text is not distinguished.".format(digest))
        return
    if frozen is None:
        report.add("gap", "Approval instance {} has no readable record under `approval-instances/{}/`, so the pins "
                          "and preparation it froze cannot be read from it.".format(chosen, digest))
    if frozen and frozen.get("prepared") not in (None, "complete"):
        report.add("gap", "Approval instance {} was prepared before readiness was recorded ({}): that its pins and card "
                          "were complete when approved is not established. Show the plan again and approve it.".format(
                              chosen, frozen.get("prepared")))
    for limit in (frozen or {}).get("limitations") or []:
        if isinstance(limit, str) and not limit.startswith("prepared before readiness"):
            report.add("info", "Approval instance {}: {}.".format(chosen, limit[:200]))
    if explicit and chosen != current:
        report.add("info", "This check is of approval instance {}, an earlier freeze; the current one is {}. "
                           "Pins, approval time and runs are those of that instance.".format(chosen, current))
    if history:
        report.add("info", "{} run(s) of this plan ran under other approval instance(s) ({}); they are history "
                           "and do not establish instance {}.".format(
                               sum(history.values()), ", ".join("{}: {}".format(k, v) for k, v in sorted(history.items())),
                               chosen) + (" Of these, {} failed: {}.".format(len(failed), "; ".join(
                                   "`{}` {} at {} (instance {})".format(r.get("command", "")[:60], text, when(r["ts"]),
                                                                       r.get("approval_instance") or "not recorded")
                                   for r, text in failed[:5])) if failed else ""))
        if not mine:
            report.add("gap", "No run is recorded under approval instance {} (approved {}); runs under an earlier "
                              "instance do not establish this freeze.".format(chosen, when(approved_at)))


def launch_findings(report, mine, abandoned, digest, chosen, approved_at):
    """Gaps for runs credited to the plan that no checked launch backs, and for attempts that never reported
    back; one info line for receipts written before launch matching, which are read as before."""
    for kind, what in (("unmatched", "no checked launch: Post without matching Pre"),
                       ("ambiguous", "an ambiguous launch (identical launches without a call id)")):
        groups = collections.OrderedDict()
        for r in mine:
            if launch_kind(r) == kind:
                groups.setdefault(r.get("launch_note") or "", []).append(r)
        for note, runs in groups.items():
            report.add("gap", "{} run(s) credited to this plan have {}{}: {}. The gate did not check the launch, so the "
                              "run is not established as started under the approval.".format(
                                  len(runs), what, " [{}]".format(note) if note else "",
                                  "; ".join("`{}` at {}".format(r.get("command", "")[:60], when(r.get("ts")))
                                            for r in runs[:3]) + (" and {} more".format(len(runs) - 3) if len(runs) > 3 else "")))
    legacy = sum(1 for r in mine if launch_kind(r) == "legacy")
    if legacy:
        report.add("info", "{} receipt(s) predate launch matching (launch link not recorded); they are read as before "
                           "and never as matched launches.".format(legacy))
    open_attempts = 0
    for attempt in abandoned:
        if digest not in attempt["plans"]:
            continue
        instance = attempt["instances"].get(digest)
        if (instance != chosen) if instance and chosen else attempt["started"] < approved_at - TOLERANCE:
            continue  # another freeze of this plan, or (no instance recorded) an attempt before the approval
        open_attempts += 1
        report.add("gap", "Attempt started at {} (`{}`) has no completion record: the call never reported back, so "
                          "what it ran or wrote is not known.".format(when(attempt["started"]), attempt["command"][:60]))
    return open_attempts


def check_receipt(report, r, judge_job=None):
    """A finding for a command receipt no script row judged, in the wording of a script's row. A
    submission that exited 0 and recorded a job is judged by `judge_job(what, r)`, the job's state;
    a compound command's own failure is already a block, so only its attribution gap is added here."""
    what, at, code = "`{}`".format(r.get("command", "")[:80]), when(r.get("ts")), r.get("exit_status")
    if isinstance(code, int) and code != 0:
        report.add("block", "{} failed (exit {}) at {}.".format(what, code, at))
    elif code in ("failed", "interrupted"):
        report.add("block", "{} {} at {}{}.".format(
            what, "failed without an exit code" if code == "failed" else "was interrupted", at,
            ": " + r["error_line"] if r.get("error_line") else ""))
    elif r.get("job_id") and judge_job:
        judge_job(what, r)
    elif code == 0:
        return
    elif "command_exit_status" in r:
        failed = r["command_exit_status"]
        if not (isinstance(failed, int) and failed != 0 or failed in ("failed", "interrupted")):
            report.add("gap", "{} was named in a compound command at {}, but its execution and exit "
                              "status cannot be attributed to this step.".format(what, at))
    elif r.get("background"):
        report.add("gap", "{} was started in the background at {}, so its exit status is not known and "
                          "the run is not counted as a success; check its output or log.".format(what, at))
    else:
        report.add("gap", "{} ran at {}, but the tool response carried no exit status, so the run is not "
                          "counted as a success.".format(what, at))


def step_key(root, r):
    """What a command receipt ran, for superseding an earlier try: its kind, cwd and the script,
    Snakefile or job script it named (a path, or an existing file among its arguments). A Snakemake
    run with none is the Snakefile in its cwd; any other command falls back to its command line."""
    kind, cwd, command = r.get("kind"), r.get("cwd") or ".", r.get("command", "")
    targets = set(ran_paths(root, r))
    if not targets:
        try:
            words = shlex.split(command)
        except ValueError:
            words = command.split()
        for word in words:
            rel = os.path.normpath(os.path.join(cwd, word))
            if not word.startswith("-") and os.path.basename(word) != kind \
                    and os.path.isfile(os.path.join(root, rel)):
                targets.add(rel)
    if targets:
        return (kind, cwd, tuple(sorted(targets)))
    return (kind, cwd) if kind == "snakemake" else (kind, command)


# ---------------------------------------------------------------- approved validation checks (C06)

CONTRACT_RESULT = "mycelium-extra.contract_result.v1"
PHRASE = {"failed": "failed", "not run": "was not run", "unsupported": "has unsupported evidence",
          "changed": "changed since approval", "unattributable": "has unattributable evidence",
          "stale": "is stale (outputs changed after it ran)"}


def contract_text(check):
    """`id`: message (expected X, observed Y) for one check of a data-contract result."""
    alerts = [a for a in check.get("alerts") or [] if isinstance(a, dict)]
    first = alerts[0] if alerts else {}
    detail = ", ".join("{} {}".format(key, first[key]) for key in ("expected", "observed") if first.get(key) is not None)
    return "`{}`: {}{}".format(check.get("id"), str(first.get("message") or check.get("message") or check.get("status"))[:120],
                               " ({})".format(detail) if detail else "")


def read_result(path, check):
    """(outcome, reason, warnings) from an evidence file's content: a JSON object whose `status` is passed or
    failed, or a data-contract result (`mycelium-extra.contract_result.v1`), which passes only with exit 0 and
    no block; its warnings are kept. Anything else is unsupported."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return "unsupported", "the file is not readable JSON", []
    if not isinstance(data, dict):
        return "unsupported", "the result is not a JSON object", []
    if data.get("schema") != CONTRACT_RESULT:
        status, note = data.get("status"), data.get("message")
        if status not in ("passed", "failed"):
            return "unsupported", "the result has no `status` of passed or failed", []
        return status, "the result says {}{}".format(status, " ({})".format(note.strip()[:200])
                                                     if isinstance(note, str) and note.strip() else ""), []
    status, code = data.get("status"), data.get("exit_code")
    if not isinstance(data.get("checks") or [], list) or not isinstance(data.get("contract") or {}, dict):
        return "unsupported", "the data-contract result's `checks` or `contract` is malformed", []
    checks = [c for c in data.get("checks") or [] if isinstance(c, dict)]
    pinned = (data.get("contract") or {}).get("sha256")
    if pinned and check["files"] and pinned not in check["files"].values():
        return "changed", "the result was produced from a contract that is not the pinned one", []
    label = "the data-contract result is {} (exit {})".format(status, code)
    if code == 0 and status in ("pass", "warn") and not any(c.get("status") == "block" for c in checks):
        return "passed", label, [contract_text(c) for c in checks if c.get("status") == "warn"]
    if code == 2 or status == "block":
        bad = [contract_text(c) for c in checks if c.get("status") == "block"]
        return "failed", label + ("; " + "; ".join(bad[:3]) if bad else ""), []
    if code in (1, 3) or status in ("gap", "error"):  # a table could not be read, or the contract was unusable: nothing was judged
        return "not run", label + "; the contract's checks could not run", []
    return "unsupported", label, []


def attribution_problem(root, run, path):
    """Why the evidence file at `path` is not tied to the matched attempt `run`, or None: the gate saw the attempt
    create or change it and nothing touched it afterwards."""
    if run.get("outputs_observation") != "observed":
        return "the gate did not observe outputs during the attempt ({})".format(run.get("outputs_observation") or "not recorded")
    seen = run.get("outputs_changed") or {}
    if path not in list(seen.get("created") or []) + list(seen.get("changed") or []):
        return "the matched attempt did not create or change `{}`".format(path)
    try:
        mtime = os.stat(os.path.join(root, path)).st_mtime
    except OSError:
        return "`{}` is missing now".format(path)
    if mtime > run["ts"] + TOLERANCE:
        return "`{}` was modified after the attempt ({})".format(path, when(mtime))
    return None


def changed_after(run, mine):
    """Why a passed check no longer speaks for the outputs, or None: a later attempt under the instance (other than a
    check's) changed a declared output, or ran without its outputs being observed, after the check's attempt."""
    for r in sorted(mine, key=lambda r: r.get("ts", 0)):
        if r.get("ts", 0) <= run.get("ts", 0) or r.get("validation_check"):
            continue
        seen = r.get("outputs_changed") or {}
        paths = sorted(set(p for k in ("created", "changed", "deleted") for p in seen.get(k) or []))
        if paths:
            return "`{}` changed in a later attempt (`{}` at {}); run the check again".format(
                paths[0], r.get("command", "")[:60], when(r["ts"]))
        if r.get("outputs_observation") != "observed":
            return "a later attempt (`{}` at {}) ran without its outputs observed, so they may have changed; run the " \
                   "check again".format(r.get("command", "")[:60], when(r["ts"]))
    return None


def judge_check(root, check, runs, edited, elsewhere):
    """One approved check against the matched runs of its invocation (oldest first): a dict with `outcome`
    (passed, failed, not run, unsupported, changed or unattributable), `reason`, and the identities kept in the bundle."""
    module = gate.blocks_module()
    found = dict((k, check[k]) for k in ("id", "plan_row", "required", "defined_by", "invocation", "evidence_path",
                                         "definition_sha256", "files"))
    found.update(outcome=None, reason=None, attempt_id=None, evidence_sha256=None, warnings=[])
    digest = module.file_sha256(os.path.join(root, check["evidence_path"]))
    found["evidence_sha256"] = None if digest.startswith("!") else digest
    if edited:
        found.update(outcome="changed", reason="; ".join("pinned `{}` is no longer the approved file ({})".format(
            path, "missing" if state == "missing" else "its content differs") for path, state in edited))
        return found
    if not runs:
        found.update(outcome="not run", reason="no matched run of `{}` under this approval instance{}".format(
            " ".join(check["invocation"]), "; it ran under another approval instance only" if elsewhere else ""))
        return found
    run = runs[-1]
    found["attempt_id"] = run.get("attempt_id")
    code = run.get("exit_status")
    problem = attribution_problem(root, run, check["evidence_path"])
    if (isinstance(code, int) and code != 0) or code in ("failed", "interrupted"):
        found.update(outcome="failed", reason="the check command {} at {}".format(
            "exited {}".format(code) if isinstance(code, int) else "was interrupted" if code == "interrupted"
            else "failed without an exit code", when(run["ts"])))
        if problem is None:  # a result the attempt wrote says more than the exit code: "could not run" or "other contract" is not "failed"
            outcome, reason, _ = read_result(os.path.join(root, check["evidence_path"]), check)
            if outcome in ("failed", "not run", "changed"):
                found.update(outcome=outcome, reason=(found["reason"] + "; " + reason) if outcome == "failed"
                             else reason + "; " + found["reason"])
    elif code != 0:
        found.update(outcome="unsupported", reason="the check command's exit status was not recorded, so it is not "
                                                   "counted as having completed")
    elif problem:
        found.update(outcome="unattributable", reason=problem)
    else:
        found["outcome"], found["reason"], found["warnings"] = read_result(
            os.path.join(root, check["evidence_path"]), check)
    return found


def check_validations(root, report, validation, mine, elsewhere):
    """Reconcile each check of the instance's validation binding with its matched run and result. `elsewhere`:
    ids of checks that were run under another approval instance. A required check that failed blocks; one not
    run, unsupported, changed or unattributable is a gap (not established), never a pass; an optional one is only
    information. `defined_by` is shown as declared and is not verified."""
    edited = {}
    for cid, path, state in gate.blocks_module().changes(root, validation):
        edited.setdefault(cid, []).append((path, state))
    results = []
    for check in validation["checks"]:
        runs = [r for r in mine if r.get("validation_check") == check["id"] and r.get("launch_match") == "matched"]
        one = judge_check(root, check, runs, edited.get(check["id"]), check["id"] in elsewhere)
        later = changed_after(runs[-1], mine) if one["outcome"] == "passed" else None
        if later:
            one.update(outcome="stale", reason="it passed, but " + later)
        results.append(one)
        who = "Validation `{}` (plan row {}, {}; declared {}, not verified)".format(
            one["id"], one["plan_row"], "required" if one["required"] else "optional", one["defined_by"])
        if one["outcome"] == "passed":
            if one["warnings"]:
                report.add("info", "{} passed with {} warning(s): {}".format(who, len(one["warnings"]), "; ".join(one["warnings"][:5])))
        elif not one["required"]:
            report.add("info", "{} {}: {}".format(who, PHRASE[one["outcome"]], one["reason"]))
        elif one["outcome"] == "failed":
            report.add("block", "{} failed: {}".format(who, one["reason"]))
        else:
            report.add("gap", "{} {}: {}; not established, so the plan's acceptance expectation is not counted as "
                              "met.".format(who, PHRASE[one["outcome"]], one["reason"]))
    return results


# ---------------------------------------------------------------- recovery history and exact execution (C07)

def attempt_state(r, jobs):
    """(kind, text) of one attempt: ok, failed or unknown, with the outcome in words."""
    code = r.get("exit_status")
    if isinstance(code, int) and not isinstance(code, bool):
        if code != 0:
            return "failed", "failed (exit {})".format(code)
        state = (jobs.get(r.get("job_id")) or {}).get("state") if r.get("job_id") else None
        if state in FAILED_JOB:
            return "failed", "job {} ended {}".format(r["job_id"], state)
        return "ok", "submitted job {} (exit 0)".format(r["job_id"]) if r.get("job_id") else "succeeded (exit 0)"
    if code in ("failed", "interrupted"):
        return "failed", "failed without an exit code" if code == "failed" else "interrupted"
    failed = r.get("command_exit_status")
    if isinstance(failed, int) and failed != 0 or failed in ("failed", "interrupted"):
        return "failed", "compound command failed (exit {})".format(failed)
    return "unknown", "exit status not recorded"


def run_argv(root, config, r):
    """(argv from the program on, inline VAR=value words) of one receipt's command."""
    command = r.get("command", "")
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    argv, inline = gate.launch_argv(tokens, root, os.path.join(root, r.get("cwd") or "."), config)
    return (argv, inline) if argv else (tokens, {})


def attempt_changes(root, config, a, b, operational):
    """(what changed from attempt `a` to the later `b`, whether the argument words differ in more than the
    operational flags, whether the code, inputs or folder differ). Only what the receipts carry is compared."""
    argv_a, env_a = run_argv(root, config, a)
    argv_b, env_b = run_argv(root, config, b)
    notes, argv_changed, code_changed = [], False, False
    if argv_a != argv_b or env_a != env_b:
        gone, new = collections.Counter(argv_a) - collections.Counter(argv_b), collections.Counter(argv_b) - collections.Counter(argv_a)
        parts = (["removed " + ", ".join("`{}`".format(t) for t in argv_a if t in gone)] if gone else []) + \
                (["added " + ", ".join("`{}`".format(t) for t in argv_b if t in new)] if new else []) + \
                ["inline variables {} -> {}".format(env_a, env_b)] * (env_a != env_b)
        ok, _ = gate.blocks_module().argv_matches(argv_a, argv_b, a.get("cwd") or ".", a.get("cwd") or ".", operational,
                                                  env_a, env_b)
        argv_changed = not ok or env_a != env_b
        notes.append(", ".join(parts) + ("" if argv_changed else " (operational flags only)"))
    if (a.get("cwd") or ".") != (b.get("cwd") or "."):
        notes.append("folder {} -> {}".format(a.get("cwd") or ".", b.get("cwd") or "."))
        code_changed = True
    sa, sb = a.get("script") or {}, b.get("script") or {}
    if sa.get("sha256") and sb.get("sha256") and (sa.get("path"), sa["sha256"]) != (sb.get("path"), sb["sha256"]):
        notes.append("script `{}` content changed".format(sb.get("path")))
        code_changed = True
    files = lambda r: dict((f.get("path"), f.get("sha256")) for f in (r.get("engine") or {}).get("files") or []
                           if isinstance(f, dict))
    notes += ["`{}` (engine file) changed".format(p) for p in sorted(files(a)) if p in files(b) and files(a)[p] != files(b)[p]]
    code_changed = code_changed or any("engine file" in n for n in notes)
    return notes, argv_changed, code_changed


def recovery_history(root, config, report, mine, jobs, execution):
    """One entry per step (as `step_key` groups the runs) that more than one attempt of this instance ran: every
    attempt in order, with what changed from the one before. The step's outcome stays that of its latest attempt
    (the findings above); here an earlier failure that a later success follows is named, as an equivalent retry
    (same command, or only the flags the exact-execution step lists as operational, same code and inputs: no
    finding but information) or, when anything else changed, as a recovery whose equivalence is not established (a gap)."""
    groups = collections.OrderedDict()
    for r in mine:
        groups.setdefault(step_key(root, r), []).append(r)
    entries = []
    for key, runs in groups.items():
        if len(runs) < 2:
            continue
        label = " ".join(key[2]) if len(key) == 3 else "snakemake" if key[0] == "snakemake" else key[1]
        rows = set(r.get("exact_step") for r in runs if r.get("exact_step"))
        operational = sorted(set(f for step in (execution or {}).get("steps") or [] if step["row"] in rows
                                 for f in step["operational"]))
        attempts = []
        for i, r in enumerate(runs):
            kind, text = attempt_state(r, jobs)
            notes = attempt_changes(root, config, runs[i - 1], r, operational)[0] if i else []
            attempts.append({"ts": r.get("ts"), "command": r.get("command", ""), "attempt_id": r.get("attempt_id"),
                             "outcome": kind, "text": text, "changes": notes})
        verdict, final = None, attempts[-1]
        failed = [(a, r) for a, r in zip(attempts[:-1], runs[:-1]) if a["outcome"] == "failed"]
        if final["outcome"] == "ok" and failed:
            diffs = [attempt_changes(root, config, r, runs[-1], operational) for _, r in failed]
            verdict = "changed command" if any(d[1] for d in diffs) else \
                "changed code" if any(d[2] for d in diffs) else "equivalent"
            earlier = ", ".join("`{}` failed at {}".format(a["command"][:60], when(a["ts"])) for a, _ in failed[:3])
            if verdict == "equivalent":
                report.add("info", "Step `{}` recovered: equivalent retry (an earlier attempt: {}; the later success ran the same "
                                   "command, differing at most in operational flags the plan lists).".format(label, earlier))
            else:
                report.add("gap", "Step `{}` recovered {}: equivalence not established (an earlier attempt: {}; the later success "
                                  "ran `{}`, changes: {}). The earlier failure stays in the history above; the success is "
                                  "not the approved computation's recovery unless the researcher says it is.".format(
                                      label, "with a changed command" if verdict == "changed command"
                                      else "after changed code or inputs", earlier, final["command"][:60],
                                      "; ".join(n for d in diffs for n in d[0]) or "none recorded"))
        entries.append({"step": label, "attempts": attempts, "operational": operational, "verdict": verdict})
    return entries


def exact_findings(report, mine, execution):
    """A gap for each run of an instance that declares exact execution but was not matched to a declared step
    (a validation check's own run is matched by its invocation instead)."""
    if not execution:
        return 0
    off = [r for r in mine if r.get("exact_match") is not True and not r.get("validation_check")]
    if off:
        report.add("gap", "{} run(s) are outside the exact reportable contract the plan declares (`exact-execution`): no declared step "
                          "was matched to them, so their command is not frozen: {}.".format(
                              len(off), "; ".join("`{}` at {}".format(r.get("command", "")[:60], when(r.get("ts"))) for r in off[:3])
                              + (" and {} more".format(len(off) - 3) if len(off) > 3 else "")))
    return len(off)


def check(root, digest, analysis_dir=None, sacct="sacct", hash_mb=2000, seconds=120, scilintr="scilintr",
          rscript="Rscript", claims=(), instance=None, resolve_citations=False, contact=None):
    config = gate.load_config(root)
    approval = read_approval(gate.state_path(root, "approvals", digest + ".json"))
    if approval is None:
        sys.exit("verify: no approved plan {}. Run `list` to see approved plans.".format(digest))
    plan, approved_at = approval.get("plan", ""), approval.get("approved_at", 0)
    # The approval instance this check is about: the one in approvals/<hash>.json (the newest), or the one
    # picked with `instance`. An approval with no instance id is legacy: one implicit freeze, history unknown.
    current = approval.get("instance_id") if isinstance(approval.get("instance_id"), str) else None
    chosen, frozen, pins, session = current, None, approval.get("pins"), approval.get("session_id")
    if instance:
        chosen, frozen = pick_instance(root, digest, plan, instance)
        if chosen != current:  # an earlier freeze: its own approval time, pins and session
            approved_at, pins, session = frozen["approved_at"], frozen.get("pins"), frozen.get("session_id")
    elif current:
        frozen = load_instance(root, digest, current)
    table = gate.plan_table(plan, every_cell=True)
    named = sorted(p for p in gate.plan_paths_in(root, table) if gate.gated_rel(root, root, p, config))
    planned = [p for p in named if is_script(root, p)]
    folders = [p for p in named if p not in planned and not os.path.isfile(os.path.join(root, p))]
    commands = [c for c in config["gated_commands"] if gate.names_command(c, table)]
    analysis_dir = rel_or_abs(root, analysis_dir) if analysis_dir else guess_analysis_dir(planned)
    budget = {"bytes": float(hash_mb) * 1024 * 1024, "deadline": time.time() + seconds}

    receipts, handed, invalid_receipts = [], [], []
    for r in read_jsonl(gate.state_path(root, "receipts.jsonl"), invalid_receipts):
        if is_run(root, r, config["gated_commands"]):
            receipts.append(r)
        elif not LOOKUP.match(r.get("command", "")):
            handed.append(r)
    handed = [r for r in handed if digest in r.get("plans", []) and not r.get("explore")]
    mine, start = plan_runs(receipts, digest, approved_at, chosen)
    history = collections.Counter(
        r.get("approval_instance") or "not recorded" for r in receipts
        if chosen and digest in r.get("plans", []) and not r.get("explore") and r.get("approval_instance") != chosen)
    since = sorted((r for r in receipts if r.get("ts", 0) >= start - TOLERANCE), key=lambda r: r["ts"])
    jobs = {}
    for r in mine:
        if r.get("job_id"):
            jobs[r["job_id"]] = sacct_state(sacct, r["job_id"], r["ts"])
    # A job ID on receipts of different commands came from one shared tool output, so its state
    # belongs to one of them only (an older gate gave every sbatch in one call the first ID).
    shared = {j for j in jobs if len({r["command"] for r in mine if r.get("job_id") == j}) > 1}

    def submitted(r, path):
        """Whether the receipt's Slurm job ran `path`, by the sbatch line Slurm recorded."""
        job = jobs.get(r.get("job_id")) or {}
        return bool(job.get("submit")) and mentions(job["submit"], root, path, job.get("workdir") or root)

    meta = {os.path.join(root, ".snakemake", "metadata")}
    for folder in ([analysis_dir] if analysis_dir else []) + folders + [os.path.dirname(p) for p in planned]:
        meta.add(os.path.join(root, folder, ".snakemake", "metadata"))  # a wrapper may `cd` there first
    for r in mine:
        record = (r.get("engine") or {}).get("record")
        if record:
            meta.add(os.path.normpath(os.path.join(root, r.get("cwd") or ".", record)))
    invalid_metadata = []
    smk = snakemake_records(sorted(m for m in meta if os.path.isdir(m)), start, invalid_metadata)

    report = Report()
    if analysis_dir:
        import provenance
        folder = os.path.join(root, analysis_dir, "provenance")
        if os.path.isdir(folder):
            with provenance.locked(os.path.join(folder, ".publish.lock")):
                saved_state = provenance.bundle_state(folder, digest)
            if saved_state != "complete":
                report.add("gap", "Saved provenance bundle is {}; no checksummed completion established.".format(saved_state))
    if invalid_receipts:
        report.add("gap", "{} malformed receipt record(s) were skipped (lines {}); the run history "
                   "is incomplete.".format(len(invalid_receipts), ", ".join(map(str, invalid_receipts[:12]))))
    gate_errors = gate_error_gaps(root, report, approved_at, {session} | {r.get("session_id") for r in mine})
    failed_before = [(r, attempt_state(r, {})[1]) for r in receipts
                     if chosen and digest in r.get("plans", []) and not r.get("explore")
                     and r.get("approval_instance") != chosen and attempt_state(r, {})[0] == "failed"]
    instance_findings(report, digest, chosen, current, frozen, history, mine, approved_at, bool(instance), failed_before)
    repin_findings(root, report, digest, approved_at)
    abandoned = abandoned_attempts(root)
    open_attempts = launch_findings(report, mine, abandoned, digest, chosen, approved_at)
    frozen_blocks = frozen if frozen is not None else approval  # the plan's validation and exact-execution blocks, as approved
    execution, binding = frozen_blocks.get("execution"), frozen_blocks.get("validation")
    off_contract = exact_findings(report, mine, execution)
    if invalid_metadata:
        report.add("gap", "{} unreadable or malformed Snakemake record(s) were skipped; workflow "
                   "evidence is incomplete.".format(len(invalid_metadata)))
    failed_commands = set()
    for receipt in mine:
        code = receipt.get("command_exit_status")
        key = (receipt.get("ts"), receipt.get("command"))
        if ((isinstance(code, int) and code != 0) or code in ("failed", "interrupted")) \
                and key not in failed_commands:
            report.add("block", "Compound command containing `{}` failed or was interrupted "
                       "(command exit {}) at {}; individual step outcomes are unknown.".format(
                           receipt.get("command", ""), code, when(receipt.get("ts"))))
            failed_commands.add(key)
    scripts, shown = [], set()  # shown: the Slurm jobs a planned script's row reports
    judged = set()  # ids of the receipts a planned script's row already judged

    def judge_job(what, last):
        """Report the state of `last`'s Slurm job under `what`; returns the row's status text."""
        job_id = last["job_id"]
        shown.add(job_id)
        if job_id in shared:
            report.add("gap", "{}: Slurm job {} is recorded for {} different sbatch commands, so its "
                              "state is not attributable; check `sacct -j {}`.".format(
                                  what, job_id, len({r["command"] for r in mine if r.get("job_id") == job_id}),
                                  job_id))
            return "job {} (state not attributable)".format(job_id)
        job = jobs.get(job_id) or {}
        state = job.get("state")
        if state == EXIT_CONFLICT:  # sacct's State and ExitCode disagree: the exit code is not ignored
            report.add("block", "{}: Slurm job {} reports COMPLETED but its ExitCode is {}; a completion needs "
                                "a clean exit, so it is treated as failed.".format(what, job_id, job.get("exit")))
        elif state == EXIT_UNREADABLE:
            report.add("gap", "{}: Slurm job {} reports COMPLETED but its ExitCode `{}` is not readable; check "
                              "`sacct -j {}`.".format(what, job_id, job.get("exit"), job_id))
        elif state in FAILED_JOB:
            report.add("block", "{}: Slurm job {} ended {}.".format(what, job_id, state))
        elif state != "COMPLETED":
            report.add("gap", "{}: Slurm job {} is {}; check `sacct -j {}`.".format(
                what, job_id, state or "of unknown state", job_id))
        return "job {} {}".format(job_id, state or "state unknown (no sacct)")

    for path in planned:
        row = {"path": path, "status": "no receipt", "last_run": None, "notes": [], "complete": False, "identity": None}
        direct = [r for r in mine if path in ran_paths(root, r) or submitted(r, path)]
        judged.update(id(r) for r in direct)
        inside = [m for m in smk if mentions(m["command"], root, path, m["workdir"])]
        if not inside and is_snakefile(path):
            rules = set(SNAKE_RULE.findall(read_text(os.path.join(root, path))))
            folder = os.path.normpath(os.path.join(root, os.path.dirname(path)))
            inside = [m for m in smk if m["rule"] in rules and os.path.normpath(m["workdir"]) == folder]
        if direct:
            last = direct[-1]
            row["complete"] = completed(last, jobs, shared)[0]
            shown.add(last.get("job_id"))
            row["last_run"] = last["ts"]
            code = last.get("exit_status")
            if isinstance(code, int) and code != 0:
                row["status"] = "failed (exit {})".format(code)
                report.add("block", "`{}` failed (exit {}) at {}.".format(path, code, when(last["ts"])))
            elif code in ("failed", "interrupted"):  # PostToolUseFailure with no exit code, or an abort
                row["status"] = "failed (no exit code)" if code == "failed" else "interrupted"
                report.add("block", "`{}` {} at {}{}.".format(
                    path, "failed without an exit code" if code == "failed" else "was interrupted",
                    when(last["ts"]), ": " + last["error_line"] if last.get("error_line") else ""))
            elif last.get("job_id"):
                row["status"] = judge_job("`{}`".format(path), last)
                if path not in ran_paths(root, last) and last["job_id"] not in shared:
                    row["notes"].append("matched by its sacct submit line")
            elif code == 0:
                row["status"] = "ran (exit 0 from hook event)" if last.get("exit_source") == "event" else "ran"
            elif "command_exit_status" in last:
                row["status"] = "execution not attributable (compound command)"
                report.add("gap", "`{}` was named in a compound command at {}, but its execution and "
                                  "exit status cannot be attributed to this step.".format(path, when(last["ts"])))
            elif last.get("background"):
                row["status"] = "started in the background (exit status unknown)"
                report.add("gap", "`{}` was started in the background at {}, so its exit status is not "
                                  "known and the run is not counted as a success; check its output or "
                                  "log.".format(path, when(last["ts"])))
            else:  # "unknown", or None in receipts from older gates: never read as success
                row["status"] = "ran (exit status unknown)"
                report.add("gap", "`{}` ran at {}, but the tool response carried no exit status, so the "
                                  "run is not counted as a success.".format(path, when(last["ts"])))
            recorded = last.get("script") or {}
            if recorded.get("path") == path and not recorded.get("missing"):
                now = gate.fingerprint(os.path.join(root, path), budget, pin=recorded)
                row["identity"] = script_identity(recorded, now)
                if now.get("missing"):
                    row["notes"].append("deleted since it ran")
                    report.add("block", "`{}` was deleted after its run at {}, so its outputs cannot be "
                                        "checked against the code.".format(path, when(last["ts"])))
                elif not gate.unchanged(recorded, now):
                    row["notes"].append("edited since it ran")
                    covered = edit_evidence(root, path, budget, receipts)
                    report.add("block", "`{}` was edited after its run at {}, so its outputs may not "
                                        "match the code.{}".format(path, when(last["ts"]),
                                                                   " " + covered if covered else ""))
                if not recorded.get("sha256") or not now.get("sha256"):
                    report.add("gap", "Script `{}` has a metadata-only fingerprint; its executed content is unverified.".format(path))
                approved = approved_script_pin(root, digest, frozen or approval, path)
                if approved.get("sha256") and recorded.get("sha256") and approved["sha256"] != recorded["sha256"]:
                    row["unfrozen"] = True  # the gate re-pinned an edit; no approval froze these bytes
                    row["notes"].append("ran code no approval froze")
                    report.add("gap", "`{}` ran at {} as edited since approval (approved {}, ran {}); no approval froze "
                                      "that version. `freeze {}` shows the diff and approves it; then run the plan "
                                      "again.".format(path, when(last["ts"]), approved["sha256"][:12],
                                                      recorded["sha256"][:12], digest))
                if recorded.get("git") in ("modified", "untracked"):
                    row["notes"].append("{} when it ran".format(recorded["git"]))
                    report.add("gap", "`{}` was {} when it ran, so no commit holds the code that ran."
                               .format(path, recorded["git"]))
        elif inside:
            last = max(inside, key=lambda m: m["end"])
            owner = wrapper_receipt(since, last)
            row["identity"] = "metadata only"  # only the file's time is compared with the rule's start
            row["complete"] = not last["incomplete"] and bool(owner) and not owner.get("explore") \
                and digest in owner.get("plans", [])
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
                    row["identity"] = "edited"
                    row["notes"].append("edited since it ran")
                    report.add("block", "`{}` was edited after its Snakemake run at {}.".format(
                        path, when(last["end"])))
            except OSError:
                row["identity"] = "deleted"
                row["notes"].append("deleted since it ran")
                report.add("block", "`{}` was deleted after its Snakemake run at {}, so its outputs cannot "
                                    "be checked against the code.".format(path, when(last["end"])))
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
    granted = set(gate.plan_grants(root, plan, config)[0])  # the Step column alone grants runs
    for folder in folders:
        runs = [r for r in mine if any(under(p, folder) for p in ran_paths(root, r))
                or under(r.get("cwd") or ".", folder)]  # `cd folder && snakemake` names no path
        report.add("info", "Folder `{}/` is planned as a whole; {} run(s) in it.".format(folder, len(runs)))
        if not runs and folder in granted and any(
                gate.SCRIPT_EXT.search(n) or is_snakefile(n)
                for _, _, names in os.walk(os.path.join(root, folder)) for n in names):
            report.add("gap", "The plan grants running the scripts in `{}/`, but no run in it under this "
                              "plan was recorded (looked for a run of a script in it, or a command "
                              "run from it).".format(folder))
    for command in commands:
        runs = [r for r in mine if r.get("kind") == command]
        if not runs:
            report.add("gap", "The plan names `{}`, but no `{}` run under it was recorded.".format(
                command, command))
    # Command and folder runs name no planned script, so no row above judged them: the latest run
    # of each step is, once, like a script row (an earlier failed try is superseded).
    latest = {}
    for r in mine:
        if id(r) not in judged:
            latest[step_key(root, r)] = r
    for r in sorted(latest.values(), key=lambda r: r["ts"]):
        check_receipt(report, r, judge_job)
    recovery = recovery_history(root, config, report, mine, jobs, execution)
    for job_id in sorted(set(jobs) - shown):  # jobs whose sbatch line names no planned script
        state = (jobs[job_id] or {}).get("state")
        if state == "COMPLETED" and job_id not in shared:
            continue
        run = next(r for r in mine if r.get("job_id") == job_id)
        report.add("gap", "Slurm job {} ({}) {}, and it names no planned script; check `sacct -j {}`."
                   .format(job_id, describe_run(run, digest), "is recorded for several sbatch commands, so its state is "
                           "not attributable" if job_id in shared else "is " + (
                               "COMPLETED with an ExitCode of {}".format((jobs[job_id] or {}).get("exit"))
                               if state in (EXIT_CONFLICT, EXIT_UNREADABLE) else state or "of unknown state"),
                           job_id))

    # Runs in the analysis folder that this plan does not cover, and scripts it does not name.
    unplanned_files = []
    if analysis_dir:
        for r in since:
            if r in mine or not any(under(p, analysis_dir) for p in ran_paths(root, r)) \
                    or (digest in r.get("plans", []) and not r.get("explore")):  # history of this plan's other instances
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
               if any(rel in ran_paths(root, r) and not r.get("explore") for r in since)
               or any(mentions(m["command"], root, rel, m["workdir"]) for m in smk)]
        for rel in ran:
            report.add("gap", "`{}` ran since the approval but is not in the plan table.".format(rel))
        idle = len(unplanned_files) - len(ran)
        if idle:
            report.add("info", "{} other script(s) in the analysis folder are not in the plan, and no "
                               "run of them since the approval was recorded.".format(idle))

    inputs = []
    for rel, pin in sorted((pins or {}).items()):
        now = gate.fingerprint(os.path.join(root, rel), budget, pin=pin)
        changed = not gate.unchanged(pin, now)
        inputs.append({"path": rel, "pinned": gate.describe(pin), "now": gate.describe(now),
                       "changed": changed,
                       "evidence": "not re-checked" if now.get("skipped") else
                       "content" if pin.get("sha256") and now.get("sha256") else "metadata only"})
        if changed:
            report.add("block", "Input `{}` changed since the approval (was {}, now {}).".format(
                rel, gate.describe(pin), gate.describe(now)))
        elif now.get("skipped"):
            report.add("gap", "Input `{}` could not be re-checked (time limit).".format(rel))
        elif not pin.get("sha256") or not now.get("sha256"):
            report.add("gap", "Input `{}` has a metadata-only fingerprint; unchanged content is unverified.".format(rel))

    outputs = []
    lineage = lineage_actions(root, start, time.time())
    attributed = {}  # (candidate run, folder, evidence method) -> (run, [(output, written)]): one finding per group
    words = plan_outputs(plan)
    if words is None:
        report.add("gap", "The plan has no `Outputs:` line, so its results cannot be tied to its runs.")
    else:
        for word in gate.read_outputs(plan)[1]:
            report.add("gap", "Output `{}` is shorthand that names no path; name the full path on the "
                              "`Outputs:` line.".format(word))
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
                grade = grade_output(rel, mtime, exact or bool(re.search(r"[*?\[]", word)), since, mine, digest, jobs,
                                     abandoned, wrapper_candidates(since, record) if record else None)
                owner, via = grade["owner"], "Snakemake rule `{}`".format(record["rule"]) if record else None
                fingerprint = output_fingerprint(full, budget)
                found = lineage_for(root, rel, mtime, fingerprint.get("sha256"), lineage, since)
                apply_lineage(grade, found, digest, rel)
                lineage_findings(report, rel, found)
                if grade["gap"]:
                    report.add("gap", grade["gap"])
                supported = grade["strength"] == "supported"
                origin = [] if supported else explore_origin(receipts, mine, rel, mtime)
                if origin:
                    report.add("gap", "Output `{}` was written inside the window of explore attempt(s) {} and was not "
                                      "re-observed under a matched approved attempt: not re-run under approval. Promotion "
                                      "needs an approved rerun with fresh output identity; an explore output is never "
                                      "relabelled as a result.".format(rel, ", ".join(
                                          "{} (code {})".format(a["attempt_id"] or "with no attempt id",
                                                                (a["script_sha256"] or "no content hash")[:12])
                                          for a in map(explore_attempt, origin))))
                outputs.append({"path": rel, "written": mtime,
                                "by": describe_run(owner, digest) if supported else "unresolved", "rule": via,
                                "producer_attempt": grade["producer_attempt"], "evidence_method": grade["evidence_method"],
                                "strength": grade["strength"], "candidates": grade["candidates"], "reason": grade["reason"],
                                "fingerprint": gate.describe(fingerprint), "record": fingerprint,
                                "lineage": grade["lineage"], "explore": bool(owner and owner.get("explore"))})
                if origin:
                    outputs[-1].update(promotion="not re-run under approval",
                                       explore_attempts=[explore_attempt(r) for r in origin])
                if mtime < start - TOLERANCE:
                    report.add("block", "Output `{}` was written {}, before the plan was approved.".format(
                        rel, when(mtime)))
                elif not supported and grade["evidence_method"] != "attempt-observed" and not grade.get("conflict"):
                    key = (None if owner is None else (owner.get("ts"), owner.get("command")),
                           os.path.dirname(rel), grade["evidence_method"])
                    attributed.setdefault(key, (owner, []))[1].append((rel, mtime))
            if older:
                report.add("info", "{} file(s) under `{}` predate this plan, so they are earlier runs' "
                                   "outputs and were not checked.".format(older, word))
    for (_, folder, method), (owner, files) in attributed.items():
        how = {"timing-only": "timing evidence only",
               "lineage-record": "Mycelium's lineage record, joined to the attempt by inference"}.get(
                   method, "joined to Snakemake's record by time only")
        if len(files) == 1:
            rel, mtime = files[0]
            if owner is None:
                report.add("gap", "Output `{}` (written {}) is not tied to any recorded run: a run "
                                  "moved to the background, or computation the gate did not see."
                           .format(rel, when(mtime)))
            else:
                report.add("gap", "Output `{}` was likely written by {} ({}: a candidate, not an established "
                                  "producer).".format(rel, describe_run(owner, digest), how))
            continue
        where = "{} files in `{}`".format(len(files), folder + "/" if folder else ".")
        if owner is None:
            report.add("gap", "{} (written {}) are not tied to any recorded run: a run moved to the "
                              "background, or computation the gate did not see."
                       .format(where, when(max(m for _, m in files))))
        else:
            names = ["`{}`".format(os.path.basename(rel)) for rel, _ in files[:3]]
            more = " and {} more".format(len(files) - 3) if len(files) > 3 else ""
            report.add("gap", "{} were likely written by {}: {}{} ({}: candidates, not established producers)."
                       .format(where, describe_run(owner, digest), ", ".join(names), more, how))

    seen = {p for r in since for p in ran_paths(root, r)}
    plugins = [os.path.realpath(p) for p in (PLUGIN_ROOT, os.path.expanduser("~/.claude/plugins"),
                                              os.path.expanduser("~/.codex/plugins"))]
    inline = 0
    for action in lineage:
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

    default_reasons(plan, report)
    fact_tags("the plan's Evidence", section_bullets(plan, "Evidence"), report)
    if analysis_dir:
        doc = os.path.join(analysis_dir, os.path.basename(analysis_dir).upper().replace("-", "_") + ".md")
        fact_tags("`{}` Key Findings".format(doc), section_bullets(read_text(os.path.join(root, doc)),
                                                                   "Key Findings"), report)
    envs = conda_snapshots(root, mine, report)
    rule_env_list = rule_envs(root, mine, report)
    linted = lint(root, code_files(root, analysis_dir, planned), report, scilintr, rscript, seconds,
                  choices=[(" ".join(row.values()), row.get("choice", "")) for row in plan_rows(plan)[0].values()])
    claimed = check_claims(root, analysis_dir, outputs, claims, report, budget["bytes"])
    cited = check_citations(root, analysis_dir, outputs, claims, report, resolve_citations, contact)
    elsewhere = set(r.get("validation_check") for r in receipts if digest in r.get("plans", []) and not r.get("explore")
                    and chosen and r.get("approval_instance") != chosen)
    validated = check_validations(root, report, binding, mine, elsewhere) if binding else []
    prose_validation(plan, binding, report)

    launches = collections.Counter(launch_kind(r) for r in mine)
    strengths = collections.Counter(row["strength"] for row in outputs)
    scope = {"runs": len(mine), "launch": {k: launches.get(k, 0) for k in ("matched", "unmatched", "ambiguous", "legacy")},
             "outputs": len(outputs), "supported": strengths.get("supported", 0),
             "candidate": strengths.get("candidate", 0), "unresolved": strengths.get("unresolved", 0)}
    scope["observation"] = {"gate_errors": gate_errors, "open_attempts": open_attempts, "off_contract": off_contract,
                            "steps": completion_steps(root, scripts, latest, commands, folders, granted, mine, jobs, shared)}
    return {"hash": digest, "approved_at": approved_at, "start": start, "session_id": session,
            "instance": {"selected": chosen, "current": current, "history": dict(history),
                         "prepared": (frozen or {}).get("prepared")}, "scope": scope,
            "analysis_dir": analysis_dir, "git": gate.git_state(root), "runs": len(mine),
            "scripts": scripts, "folders": folders, "commands": commands, "inputs": inputs,
            "outputs": outputs, "outputs_named": words, "findings": report.findings, "lint": linted, "envs": envs, "rule_envs": rule_env_list,
            "claims": claimed, "citations": cited, "recovery": recovery, "validation": validated,
            "validation_binding": binding,
            "status": report.status(), "plan": plan,
            # Kept for the record (a scaffolder call can explain a moved input), marked as not runs.
            "receipts": sorted(mine + [dict(r, not_a_run="only passed planned paths to other code")
                                       for r in handed], key=lambda r: r.get("ts", 0))}


# ---------------------------------------------------------------- reportable qualification (C10)

def completed(r, jobs, shared):
    """(whether this attempt completed, why not). A completion needs an integer exit 0; a background start, a compound
    command whose step is not attributable, or a Slurm submission (exit 0 of `sbatch`) is not one until sacct says the
    job COMPLETED, and a job id shared by several sbatch commands says nothing about this one."""
    code = r.get("exit_status")
    if isinstance(code, bool) or not isinstance(code, int):
        why = "started in the background (exit status unknown)" if r.get("background") else \
            "compound command, step outcome not attributable" if "command_exit_status" in r else \
            "failed without an exit code" if code == "failed" else "interrupted" if code == "interrupted" else \
            "exit status not recorded"
        return False, why
    if code != 0:
        return False, "failed (exit {})".format(code)
    job = r.get("job_id")
    if job:
        state = (jobs.get(job) or {}).get("state")
        if job in shared:
            return False, "submitted as job {}; its state is not attributable".format(job)
        if state != "COMPLETED":
            return False, "submitted to Slurm as job {}; its state is {}".format(job, state or "unknown")
    return True, "exit 0"


def approved_script_pin(root, digest, record, path):
    """The pin of `path` that approving the plan froze: the approval instance's, else the first-run ledger's; {}
    when the plan pinned none (no baseline to compare with)."""
    pin = (record.get("scripts") or {}).get(path)
    if not pin:
        try:
            pin = gate.read_script_pins(root, digest).get(path)
        except gate.InvalidApproval:
            pin = None
    return pin or {}


def repin_findings(root, report, digest, approved_at):
    """One info line when the gate re-pinned edited scripts since this approval: which, how often, when last."""
    found = {}
    for entry in gate.read_repins(root, digest):
        if entry.get("ts", 0) >= approved_at:
            found.setdefault(entry["rel"], []).append(entry["ts"])
    if found:
        report.add("info", "Edited since approval and re-pinned by the gate (a working scope, not a freeze): {}. "
                           "`freeze {}` shows the diffs and approves them.".format(
                               "; ".join("`{}` x{} (last {})".format(rel, len(times), when(max(times)))
                                         for rel, times in sorted(found.items())), digest))


def script_identity(recorded, now):
    """How the script's current bytes compare with the ones that ran: deleted, edited, metadata only (a size and time
    comparison, no content hash on one side), or unchanged (content hashes agree)."""
    if now.get("missing"):
        return "deleted"
    if not gate.unchanged(recorded, now):
        return "edited"
    return "unchanged" if recorded.get("sha256") and now.get("sha256") else "metadata only"


def completion_steps(root, scripts, latest, commands, folders, granted, mine, jobs, shared):
    """Every planned step with its latest attempt's completion: script rows, the latest unjudged command or folder
    run of each step, a named command with no run, and a granted folder with no run in it."""
    steps = [{"step": "`{}`".format(r["path"]), "complete": r["complete"], "why": r["status"]} for r in scripts]
    for r in sorted(latest.values(), key=lambda r: r.get("ts", 0)):
        done, why = completed(r, jobs, shared)
        steps.append({"step": "`{}`".format(r.get("command", "")[:60]), "complete": done, "why": why})
    for command in commands:
        if not any(r.get("kind") == command for r in mine):
            steps.append({"step": "`{}`".format(command), "complete": False, "why": "no run recorded"})
    for folder in folders:
        if folder in granted and not any(any(under(p, folder) for p in ran_paths(root, r))
                                         or under(r.get("cwd") or ".", folder) for r in mine):
            steps.append({"step": "`{}/`".format(folder), "complete": False, "why": "no run recorded"})
    return steps


def missing_outputs(root, words, analysis_dir):
    """The `Outputs:` words that name no existing file, found as the check finds them (a bare name may be read
    inside the analysis folder; code in a named folder is not an output)."""
    missing = []
    for word, (files, exact) in expand_outputs(root, words).items():
        local = os.path.join(analysis_dir, word) if analysis_dir else None
        if not files and local and expand_outputs(root, [local])[local][0]:
            files, exact = expand_outputs(root, [local])[local]
        if not exact:
            files = [f for f in files if not (gate.SCRIPT_EXT.search(f) or is_snakefile(f))]
        if not files:
            missing.append(word)
    return missing


ACTIONS = {
    "authorization": "run the planned steps again under this approval so the gate records matched launches, or approve "
                     "a plan for what actually ran",
    "completion": "let each planned step finish with exit 0 (a submitted batch job must reach COMPLETED), then report again",
    "code and input identity": "restore or re-approve the changed code or input (`freeze <hash>` for code changed since "
                               "approval, then run the plan again), or pin it with a content hash",
    "lineage": "re-run so the gate sees each declared output change during a matched attempt, or correct the "
               "`Outputs:` line",
    "required validation": "run each required check as a matched attempt that writes its result",
    "claim linkage": "correct the claim, or re-run so each cited output has a supported producer",
    "no blocking finding": "resolve each block finding below; a run that fails verification is never reportable",
    "no open gap": "close or resolve each gap finding below; a gap is evidence that could not be established, so the "
                   "run is not reportable while one is open",
}


def qualify(root, result):
    """Whether this approval instance's evidence is complete enough to report from, one answer per dimension:
    established, not established (with the reason) or not applicable. It is computed from the check's structured
    records, is separate from the legacy aggregate status, and is not a scientific judgement or a score: the run is
    `qualified` only when every applicable dimension is established."""
    scope, found = result["scope"], result["scope"].get("observation") or {}
    dims = []

    def add(name, problems, ok, applicable=True):
        dims.append({"dimension": name, "state": "not applicable" if not applicable else
                     "not established" if problems else "established",
                     "reason": "; ".join(problems) if problems else ok})

    def cap(items, n=3):
        return ", ".join(items[:n]) + (" and {} more".format(len(items) - n) if len(items) > n else "")

    launch, runs = scope["launch"], scope["runs"]
    problems = ["no run is recorded under this approval instance"] if not runs else \
        ["{} run(s) {}".format(launch[k], what) for k, what in (
            ("unmatched", "unmatched (a Post with no checked launch)"), ("ambiguous", "ambiguous (identical launches)"),
            ("legacy", "legacy (launch link not recorded)")) if launch[k]]
    if not (result["instance"] or {}).get("selected"):
        problems.append("the approval predates approval instances")
    if (result["instance"] or {}).get("prepared") not in (None, "complete"):
        problems.append("the approval instance was prepared before readiness was recorded")
    for key, what in (("gate_errors", "gate error(s) in the observation window"),
                      ("open_attempts", "attempt(s) with no completion record"),
                      ("off_contract", "run(s) outside the declared exact execution")):
        if found.get(key):
            problems.append("{} {}".format(found[key], what))
    add("authorization", problems, "{} of {} run(s) are matched launches under approval instance {}".format(
        launch["matched"], runs, result["instance"]["selected"]))

    steps = found.get("steps") or []
    undone = ["{} ({})".format(s["step"], s["why"]) for s in steps if not s["complete"]]
    add("completion", undone or ([] if steps else ["no planned step is named in the plan table"]),
        "all {} planned step(s): the latest attempt of each completed".format(len(steps)))

    problems, strong = [], 0
    for row in result["scripts"]:
        if row["last_run"] is None:
            continue
        state = row["identity"] or "not recorded"
        if row.get("unfrozen"):
            problems.append("script `{}` ran as edited since approval; no approval froze that version".format(row["path"]))
        elif state == "unchanged":
            strong += 1
        else:
            problems.append("script `{}` {}".format(row["path"], {
                "edited": "was edited after it ran", "deleted": "was deleted after it ran",
                "metadata only": "was compared by metadata only", "not recorded": "has no fingerprint in its receipt"}[state]))
    for row in result["inputs"]:
        if row["changed"]:
            problems.append("input `{}` changed".format(row["path"]))
        elif row["evidence"] == "content":
            strong += 1
        else:
            problems.append("input `{}` is {}".format(row["path"], "metadata only (no content hash)"
                                                      if row["evidence"] == "metadata only" else "not re-checked"))
    if not strong and not problems:
        problems.append("no script or input fingerprint is recorded")
    add("code and input identity", problems, "{} script(s) and input(s) unchanged, compared by content hash".format(strong))

    words = result["outputs_named"]
    if words is not None and not words:
        add("lineage", [], "", applicable=False)
        dims[-1]["reason"] = "the plan declares no output (`Outputs: none`)"
    else:
        rows = result["outputs"]
        problems = ["the plan has no `Outputs:` line"] if words is None else \
            ["declared output `{}` does not exist".format(w) for w in missing_outputs(root, words, result["analysis_dir"])]
        problems += ["`{}` has {} producer ({})".format(r["path"], r["strength"], r["evidence_method"]) if not r["explore"]
                     else "`{}` was written by an explore run".format(r["path"])
                     for r in rows if r["strength"] != "supported" or r["explore"]]
        if words and not rows and not problems:
            problems.append("no file under the declared output(s) was written under this approval")
        add("lineage", problems, "{} of {} declared output(s) have a supported producer (a matched attempt saw each "
                                 "change)".format(len(rows), len(rows)))

    binding = [v for v in result.get("validation") or [] if v["required"]]
    if not binding:
        add("required validation", [], "", applicable=False)
        dims[-1]["reason"] = ("no check is marked required" if result.get("validation") else
                              "the plan binds no check (its Validation cells are prose)")
    else:
        add("required validation", ["`{}` {}".format(v["id"], v["outcome"]) for v in binding if v["outcome"] != "passed"],
            "{} required check(s) passed".format(len(binding)))

    strength = dict((r["path"], r["strength"]) for r in result["outputs"])
    claims = [(d["doc"], c) for d in result.get("claims") or [] for c in d["claims"]]
    if not claims:
        add("claim linkage", [], "", applicable=False)
        dims[-1]["reason"] = "no checked claim"
    else:
        not_matched = ["`{}:{}` {}".format(doc, c["line"], c["verdict"]) for doc, c in claims
                       if not c["verdict"].startswith("verified")]
        unlinked = sorted(set("`{}` ({})".format(c["file"], strength[c["file"]]) for _, c in claims
                              if c["verdict"].startswith("verified") and strength.get(c["file"]) != "supported"
                              and c["file"] in strength))
        count = sum(1 for _, c in claims if c["verdict"].startswith("verified") and strength.get(c["file"]) != "supported")
        problems = (["{} claim(s) not matched: {}".format(len(not_matched), cap(not_matched))] if not_matched else []) + \
            (["{} claim cell(s) matched but their output's producer is not supported: {}".format(count, cap(unlinked))]
             if count else [])
        add("claim linkage", problems, "{} claim cell(s) matched and their outputs have supported producers{}".format(
            len(claims), "; a registered `numbers.json` value is attributed to the file's producer, not to the key's run"
            if any(c.get("registered") for _, c in claims) else ""))

    blocks = [text for level, text in result["findings"] if level == "block"]
    add("no blocking finding", ["{} block finding(s): {}".format(len(blocks), cap([b.split(". ")[0] for b in blocks], 2))]
        if blocks else [], "no finding blocks this plan")

    gaps = [text for level, text in result["findings"] if level == "gap"]
    add("no open gap", ["{} gap finding(s) open, listed under Findings".format(len(gaps))] if gaps else [],
        "no finding is an open gap")

    failing = [d for d in dims if d["state"] == "not established"]
    if failing:
        limit = "{} not established: {}.{}{}".format(
            failing[0]["dimension"], ACTIONS[failing[0]["dimension"]],
            " {} of {} dimensions are not established.".format(len(failing), len(dims)) if len(failing) > 1 else "",
            " {} gap finding(s) open.".format(len(gaps)) if gaps else "")
    else:
        limit = "qualification covers evidence linkage, not whether the analysis is scientifically right."
    return {"overall": "not qualified" if failing else "qualified", "dimensions": dims, "limitation": limit}


def reportable_error(result):
    """The message for `--require-reportable`, or None when the run is qualified."""
    q = result["qualification"]
    if q["overall"] == "qualified":
        return None
    return "verify: --require-reportable: not qualified. " + " ".join(
        "{}: {}.".format(d["dimension"], d["reason"]) for d in q["dimensions"] if d["state"] == "not established")


def rerun_evidence(root, result):
    """For each entry point the plan names (a `run.sh` or a Snakefile), three separate facts and never a launch: the
    entry point is `declared`; a `rerun attempted` is a matched run of it that began after verify saved its outputs
    table; it `reproduced specified artifacts` only when that rerun exited 0, saw each saved output rewritten, and the
    file's content hash now equals the saved one. A comparison needs hashes saved before the attempt."""
    entries = [row["path"] for row in result["scripts"]
               if os.path.basename(row["path"]) == "run.sh" or is_snakefile(row["path"])]
    table = os.path.join(root, result["analysis_dir"] or ".", "provenance", "outputs-{}.tsv".format(result["hash"]))
    saved, saved_at = {}, None
    if entries and os.path.isfile(table):
        saved_at = os.stat(table).st_mtime
        with open(table, encoding="utf-8") as handle:
            for line in list(handle)[1:]:
                row = line.rstrip("\n").split("\t")
                if len(row) > 3 and row[3]:
                    saved[row[0]] = row[3]
    budget = {"bytes": 2000.0 * 1024 * 1024, "deadline": time.time() + 120}
    found = []
    for path in entries:
        entry = {"path": path, "state": "declared", "reason": ""}
        found.append(entry)
        if saved_at is None:
            entry["reason"] = "no saved provenance outputs table, so a rerun has nothing earlier to be compared with"
            continue
        reruns = sorted((r for r in result["receipts"] if not r.get("not_a_run") and launch_kind(r) == "matched"
                         and path in ran_paths(root, r) and (started(r) or r["ts"]) > saved_at), key=lambda r: r["ts"])
        if not reruns:
            entry["reason"] = "no matched run of it since provenance was saved ({})".format(when(saved_at))
            continue
        last, bad = reruns[-1], []
        entry["state"] = "rerun attempted"
        changed = list((last.get("outputs_changed") or {}).get("created") or []) + \
            list((last.get("outputs_changed") or {}).get("changed") or [])
        if last.get("exit_status") != 0 or isinstance(last.get("exit_status"), bool):
            bad.append("the rerun did not exit 0")
        elif last.get("outputs_observation") != "observed":
            bad.append("outputs were not observed during the rerun ({})".format(last.get("outputs_observation") or "not recorded"))
        elif not saved:
            bad.append("the saved table holds no SHA256")
        else:
            for out, sha in sorted(saved.items()):
                now = output_fingerprint(os.path.join(root, out), budget).get("sha256")
                if out not in changed:
                    bad.append("`{}` was not rewritten by the rerun".format(out))
                elif now != sha:
                    bad.append("`{}` content differs from the saved SHA256".format(out) if now else
                               "`{}` could not be hashed".format(out))
        if bad:
            entry["reason"] = "reproduction not established: " + "; ".join(bad[:3])
        else:
            entry.update(state="rerun reproduced specified artifacts", reason="{} output(s) rewritten by the rerun have "
                         "the SHA256 saved before it".format(len(saved)))
    return found


QUALIFICATION_LINE = re.compile(r"^- Qualification: \*\*(not qualified|qualified)\*\*", re.M)


def recorded_qualification(folder, digest):
    """`qualified` or `not qualified` from the saved report, `not recorded` for a bundle written before it."""
    found = QUALIFICATION_LINE.search(read_text(os.path.join(folder, "verify-{}.md".format(digest))))
    return found.group(1) if found else "not recorded"


# ---------------------------------------------------------------- output

def cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def waiver_note(w):
    """`file:line`: reason, for a waived finding (path, line, rule, message, waiver file, waiver line, reason)."""
    where = "`{}:{}`".format(cell(w[4]), w[5]) if w[5] else "a waiver in `{}`".format(cell(w[4])) if w[4] else "a waiver"
    return "{}: {}".format(where, cell(w[6]) if w[6] else "no reason given")


def render_scope(result):
    """The lines that say, before the tables, what the check covered and what it could not establish."""
    scope, instance = result.get("scope"), result.get("instance") or {}
    if not scope:
        return []
    launch = scope["launch"]
    chosen = instance.get("selected")
    which = "a legacy approval (no instance id)" if not chosen else "approval instance {}{}".format(
        chosen, " (an earlier freeze; the current one is {})".format(instance["current"])
        if chosen != instance.get("current") else "")
    lines = ["## Scope", "",
             "- Checked against {}: {} run(s) under it - launch evidence {} matched, {} unmatched, {} ambiguous, "
             "{} legacy (launch link not recorded).".format(
                 which, scope["runs"], launch["matched"], launch["unmatched"], launch["ambiguous"], launch["legacy"])]
    if instance.get("history"):
        lines.append("- {} run(s) of this plan under other approval instance(s) are history, not evidence for it.".format(
            sum(instance["history"].values())))
    if scope["outputs"]:
        lines.append("- Producers: {} of {} output(s) have a supported producer; {} candidate, {} unresolved "
                     "(only a supported producer is named).".format(
                         scope["supported"], scope["outputs"], scope["candidate"], scope["unresolved"]))
    q = result.get("qualification")
    if q:
        lines += ["- Qualification: **{}**{}; separate from the verify status below, and not a scientific judgement."
                  .format(q["overall"], " (not established: {})".format(", ".join(
                      d["dimension"] for d in q["dimensions"] if d["state"] == "not established"))
                      if q["overall"] != "qualified" else ""),
                  "", "| Evidence | State | Basis |", "|---|---|---|"]
        lines += ["| {} | {} | {} |".format(d["dimension"], d["state"], cell(d["reason"])) for d in q["dimensions"]]
        lines += ["", "- Limitation: " + cell(q["limitation"])]
    return lines + [""]


def cut(text, limit=120):
    text = squash(text)
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "\u2026"


def render_summary(result, saved=False):
    """The five rows that open the report, each derived from what the check already computed: whether the plan
    ran, whether the claimed numbers match, what the code checks found, what nobody checked, and the next step.
    A row never says `yes` while a problem is open; `n/a` means the plan gave the check nothing to judge."""
    scope = result.get("scope") or {}
    q = dict((d["dimension"], d) for d in (result.get("qualification") or {}).get("dimensions", []))
    problem = lambda name: q[name]["reason"] if name in q and q[name]["state"] == "not established" else ""
    steps = (scope.get("observation") or {}).get("steps") or []
    undone = ["{} ({})".format(s["step"].strip("`"), s["why"]) for s in steps if not s["complete"]]
    runs = result["runs"]
    if not runs:
        ran = "no: no run is recorded under this approval"
    elif undone:
        ran = "no: {} of {} steps ran to completion; not completed: {}{}".format(
            len(steps) - len(undone), len(steps), "; ".join(undone[:2]), " and {} more".format(len(undone) - 2)
            if len(undone) > 2 else "")
    elif not steps:
        ran = "n/a: the plan table names no script, command or folder step"
    elif problem("authorization"):
        ran = "partly: all {} steps completed, but {}".format(len(steps), problem("authorization"))
    else:
        ran = "yes: {0} of {0} steps ran, {1} run(s), all completed".format(len(steps), runs)
    history = sum(((result.get("instance") or {}).get("history") or {}).values())
    if history and runs:
        ran += "; {} run(s) under an earlier approval are history".format(history)

    claims = [c for d in result.get("claims") or [] for c in d["claims"]]
    matched = sum(1 for c in claims if c["verdict"].startswith("verified"))
    if not claims:
        numbers = "n/a: no `<!-- claims -->` block names an output cell"
    elif matched < len(claims):
        wrong = collections.Counter(c["verdict"] for c in claims if not c["verdict"].startswith("verified"))
        numbers = "no: {} of {} claimed cells match; {}".format(matched, len(claims), ", ".join(
            "{} {}".format(n, v) for v, n in sorted(wrong.items())))
    elif problem("claim linkage"):
        numbers = "partly: {0} of {0} claimed cells match, but {1}".format(len(claims), problem("claim linkage"))
    else:
        numbers = "yes: {0} of {0} claimed cells match".format(len(claims))

    lint, texts = result["lint"], [text for _, text in result["findings"]]
    approved = len(lint.get("approved", []))
    open_ = collections.Counter(f[3] for f in lint["findings"] if f not in lint.get("approved", []))
    skipped = sorted(set(re.findall(r"scilintr \((\w+)\) not checked", " ".join(texts))))
    parts = ["lint " + ("{} open ({})".format(sum(open_.values()), ", ".join(
        "{} {}".format(r, n) if n > 1 else r for r, n in open_.most_common(3))) if open_ else "clean")]
    if approved:
        parts.append("{} threshold finding(s) {} you approved".format(
            approved, "is a Choice" if approved == 1 else "are Choices"))
    if lint.get("waived"):
        parts.append("{} waived".format(len(lint["waived"])))
    if skipped:
        parts.append("not checked: " + ", ".join(skipped))
    if not lint["output"] and not skipped:
        parts = ["n/a: no code was linted"]
    if problem("code and input identity"):
        parts.append(problem("code and input identity").split("; ")[0])
    code = "; ".join(parts)

    unchecked = []
    prose = [re.match(r"(\d+) Validation cell", t_) for t_ in texts]
    prose = [m for m in prose if m]
    if prose:
        unchecked.append("{} Validation cell(s) are prose".format(prose[0].group(1)))
    gaps = [t_ for level, t_ in result["findings"] if level == "gap"]
    if gaps:
        unchecked.append("{} open gap(s), first: {}".format(len(gaps), cut(gaps[0], 60)))
    unchecked.append("whether the code implements the choices (that is review)")

    blocks = [t_ for level, t_ in result["findings"] if level == "block"]
    if result["status"] == "DOES_NOT_CONFORM":
        nxt = "fix the first blocker: " + (cut(blocks[0].split(". ")[0], 100) if blocks else "see Findings")
    elif result["status"] == "CONFORMS_WITH_GAPS":
        nxt = "close the first gap: " + (cut(gaps[0], 100) if gaps else "see Findings")
    elif saved:
        nxt = "provenance is saved beside this report; commit it with the analysis"
    elif result["analysis_dir"]:
        nxt = "confirm saving provenance to {}/provenance/".format(result["analysis_dir"].rstrip("/"))
    else:
        nxt = "to save provenance, rerun as `write {} --analysis-dir DIR` once you confirm DIR".format(result["hash"])
    rows = (("Ran as planned", ran), ("Numbers match", numbers), ("Code checks", code),
            ("Not checked", "; ".join(unchecked)), ("Next", nxt))
    return ["{:<16}{}  ".format(label, cut(value)) for label, value in rows]


def render(result, all_outputs=False, saved=False):
    git = result["git"]
    head = "HEAD {} ({})".format(git["head"][:12], "uncommitted changes" if git.get("dirty") else "clean") \
        if git else "not a git repository"
    lines = [
        "# Verify plan {}: {}".format(result["hash"], result["status"]),
        "",
    ] + render_summary(result, saved) + [
        "",
        "Approved {}{} - analysis folder `{}` - {} run(s) under this plan - {}".format(
            when(result["approved_at"]),
            " (re-approved; first run {})".format(when(result["start"]))
            if result["start"] < result["approved_at"] - TOLERANCE else "",
            result["analysis_dir"] or "?", result["runs"], head),
        "",
    ] + render_scope(result) + [
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
        lines += ["| Output | Written | By | Evidence | Fingerprint |", "|---|---|---|---|---|"]
        for row in shown:
            by = row["by"] + (" via " + row["rule"] if row["rule"] else "")
            evidence = "{}, {}".format(row["evidence_method"], row["strength"]) + (
                "; candidates: " + "; ".join(row["candidates"][:3]) if row["strength"] != "supported" and row["candidates"]
                else "")
            lines.append("| `{}` | {} | {} | {} | {} |".format(cell(row["path"]), when(row["written"]), cell(by),
                                                                cell(evidence), row["fingerprint"]))
        if len(shown) < len(result["outputs"]):
            lines.append("")
            lines.append("{} more output file(s); `write` records them all.".format(
                len(result["outputs"]) - len(shown)))
    if result.get("recovery"):
        lines += ["", "## Recovery", "", "Steps with more than one attempt under this approval, every attempt in order. The step's "
                  "outcome above is its latest attempt's; an earlier failure is not erased by a later success.", ""]
        for entry in result["recovery"]:
            lines.append("Step `{}`{}".format(cell(entry["step"]), " (operational flags the plan lists: {})".format(
                ", ".join(entry["operational"])) if entry["operational"] else ""))
            for a in entry["attempts"]:
                lines.append("- {} `{}`: {}{}".format(when(a["ts"]), cell(a["command"][:120]), a["text"],
                                                     "; changed from the previous attempt: " + cell("; ".join(a["changes"]))
                                                     if a["changes"] else ""))
            lines.append("  Verdict: " + {"equivalent": "recovered: equivalent retry",
                                          "changed command": "recovered with a changed command: equivalence not established",
                                          "changed code": "recovered after changed code or inputs: equivalence not established",
                                          None: "no failed attempt was followed by a success"}[entry["verdict"]])
    if result.get("validation"):
        lines += ["", "## Validation", "", "Approved acceptance checks (`<!-- validation-bindings -->`), each against its matched "
                  "run's result; `declared` is the plan's own claim and is not verified."]
        for one in result["validation"]:
            lines.append("- `{}` (plan row {}, {}; declared {}, not verified): {}".format(
                one["id"], one["plan_row"], "required" if one["required"] else "optional", one["defined_by"],
                "passed with {} warning(s): {}".format(len(one["warnings"]), cell("; ".join(one["warnings"][:5])))
                if one["outcome"] == "passed" and one["warnings"] else
                "passed ({})".format(cell(one["reason"])) if one["outcome"] == "passed" else
                "{} - {}".format(one["outcome"], cell(one["reason"]))))
    if result.get("rerun"):
        lines += ["", "## Rerun evidence", "", "Entry points the plan names, never launched by verify: `declared`, `rerun attempted` "
                  "(a matched run after the outputs were saved) and `rerun reproduced specified artifacts` (equal content hashes) "
                  "are different facts."]
        for entry in result["rerun"]:
            lines.append("- `{}`: {}{}".format(cell(entry["path"]), "entry point declared" if entry["state"] == "declared"
                                               else entry["state"], "; " + cell(entry["reason"]) if entry["reason"] else ""))
    lines += ["", "## Lint", ""]
    lint_rows = result["lint"]["findings"]
    lines += ["- `{}:{}` [{}] {}".format(cell(f[0]), f[1], f[3], cell(f[4])) for f in lint_rows[:SHOWN_OUTPUTS]]
    if len(lint_rows) > SHOWN_OUTPUTS:
        lines.append("- {} more; `write` records them all.".format(len(lint_rows) - SHOWN_OUTPUTS))
    waivers = result["lint"]["waivers"]
    lines.append("{} `ANALYSIS_OK` waiver(s){}".format(len(waivers), ":" if waivers else "."))
    lines += ["- `{}:{}` {}".format(cell(w[0]), w[1], cell(w[2])) for w in waivers[:SHOWN_OUTPUTS]]
    waived = result["lint"].get("waived", [])
    if waived:
        lines.append("{} finding(s) waived:".format(len(waived)))
        lines += ["- `{}:{}` [{}] by {}".format(cell(w[0]), w[1], w[2], waiver_note(w)) for w in waived[:SHOWN_OUTPUTS]]
        if len(waived) > SHOWN_OUTPUTS:
            lines.append("- {} more; `write` records them all.".format(len(waived) - SHOWN_OUTPUTS))
    lines += ["", "## Claims", ""]
    for doc in result.get("claims", []):
        counts = doc["counts"]
        lines.append("- `{}`: {} verified ({} via transform), {} mismatch, {} unverified, {} explore-only; "
                     "{} other number(s) not claimed".format(
                         cell(doc["doc"]), counts.get("verified", 0) + counts.get("verified-transform", 0),
                         counts.get("verified-transform", 0), counts.get("mismatch", 0),
                         counts.get("unverified", 0), counts.get("explore-only", 0), doc["not_claims"]))
        cov = doc.get("coverage")
        if cov:
            lines.append("  - Coverage: {} block(s), {} claim line(s){}; {} cell(s) checked, {} matched, {} mismatched, "
                         "{} unverified; {} prose number(s) listed, not checked.".format(
                             cov["blocks"], cov["claim_lines"], " ({} unparsed)".format(cov["unparsed_lines"])
                             if cov["unparsed_lines"] else "", cov["cells_checked"], cov["matched"], cov["mismatched"],
                             cov["unverified"], cov["prose_numbers_listed"]))
            if cov["registered"]:
                lines.append("  - {} claim(s) cite a registered `numbers.json` value: it shows the file's current content, "
                             "not which run wrote it.".format(cov["registered"]))
    if not result.get("claims"):
        lines.append("No document with a `<!-- claims -->` block.")
    lines += ["", "## Citations", ""]
    citations = result.get("citations") or []
    if citations:
        counts = collections.Counter(c["verdict"] for c in citations)
        lines.append("- {} citation(s): {} resolved, {} mismatch, {} unresolved, {} without an identifier, "
                     "{} offline, {} where the request failed.".format(
                         len(citations), counts.get("resolved", 0), counts.get("mismatch", 0),
                         counts.get("unresolved", 0), counts.get("no identifier", 0),
                         counts.get("not checked (offline)", 0), counts.get("not checked (request failed)", 0)))
        for entry in citations:
            where = "`{}:{}`".format(entry["doc"], entry["line"])
            what = "{} {}".format(entry["kind"], entry["id"]) if entry["kind"] != "none" else "no identifier"
            note = " - " + entry["note"] if entry.get("note") else ""
            lines.append("- {}: {}: {}{}".format(where, what, entry["verdict"], note))
    else:
        lines.append("- none found (a citation needs a DOI, a `PMID:` number or an `arXiv:` number to be checked).")
    lines += ["", "## Findings", ""]
    order = {"block": 0, "gap": 1, "info": 2}
    for level, text in sorted(result["findings"], key=lambda f: order[f[0]]):
        lines.append("- **{}**: {}".format(level, text))
    if not result["findings"]:
        lines.append("- none")
    lines += ["", "## Not visible to verify", ""] + ["- " + text for text in LIMITS]
    lines += ["", "Verify status: " + result["status"]]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- disclosure (D3)

def plugin_manifest(root):
    """(name, version, rel path) from the plugin's own manifest, or (None, None, the path looked for)."""
    for rel in (os.path.join(".claude-plugin", "plugin.json"), os.path.join(".codex-plugin", "plugin.json")):
        path = os.path.join(root, rel)
        try:
            with open(path, encoding="utf-8") as handle:
                manifest = json.load(handle)
        except (OSError, ValueError):
            continue
        if isinstance(manifest, dict) and manifest.get("version"):
            return manifest.get("name") or "mycelium-extra", str(manifest["version"]), rel
    return None, None, os.path.join(".claude-plugin", "plugin.json")


def source(path, detail=None):
    """A record citation for one disclosure sentence."""
    return "[source: {}{}]".format(path, " " + detail if detail else "")


def stamp(value, with_time=False):
    """`value`, a POSIX timestamp, as a date, or None when it is not one."""
    try:
        when = time.localtime(float(value))
    except (TypeError, ValueError):
        return None
    return time.strftime("%Y-%m-%d %H:%M" if with_time else "%Y-%m-%d", when)


def render_disclosure(root, result):
    """A draft AI-use methods paragraph for one analysis folder: one sentence per line, each ending with
    the record it came from, or `[BLANK: ...]` where no record exists. Read-only: it prints, nothing is
    written, and the researcher edits what they keep into their own manuscript."""
    digest = result["hash"]
    approval = os.path.join(".mycelium-extra", "approvals", digest + ".json")
    instances = os.path.join(".mycelium-extra", "approval-instances", digest)
    receipts = os.path.join(".mycelium-extra", "receipts.jsonl")
    repins = os.path.join(".mycelium-extra", "repins", digest + ".jsonl")
    checked = "verify report for plan {} run on {}".format(digest, time.strftime("%Y-%m-%d %H:%M"))
    lines = ["# AI-use disclosure draft for plan " + digest, "",
             "## Each line below is one sentence and ends with the record it came from; fill in every "
             "`[BLANK: ...]` from what you know, and delete whatever you do not want to send", ""]

    name, version, rel = plugin_manifest(PLUGIN_ROOT or root)
    if version:
        lines.append("The agent planned, ran and checked the steps below under {0} {1}, a plugin for an AI coding "
                     "assistant, which is what wrote every record cited here. {2}".format(
                         name, version, source(rel)))
    else:
        lines.append("[BLANK: no readable plugin manifest with a version at {0}]".format(rel))

    steps = [cell(row.get("step") or "") for row in plan_rows(result.get("plan") or "")[0].values()]
    if steps:
        lines.append("The approved plan set out {0} step(s): {1}. {2}".format(
            len(steps), "; ".join(steps[:8]) + (" and {} more".format(len(steps) - 8) if len(steps) > 8 else ""),
            source(approval, "frozen plan text")))
    else:
        lines.append("[BLANK: the approval record at {0} names no plan step]".format(approval))

    approved = stamp(result.get("approved_at"), with_time=True)
    if approved:
        lines.append("You reviewed and approved that plan on {0}, and the record pins the version of each script "
                     "it covers. {1}".format(approved, source(approval)))
    else:
        lines.append("[BLANK: no approval timestamp was readable at {0}]".format(approval))

    folder_instances = os.path.join(root, instances)
    if os.path.isdir(folder_instances):
        freezes = len([n for n in os.listdir(folder_instances) if n.endswith(".json")])
        lines.append("This plan text was frozen {0} time(s); a later freeze starts a new timeline, and only the "
                     "current one is evidence for the runs counted below. {1}".format(
                         freezes, source(instances)))
    else:
        lines.append("[BLANK: no approval-instance record at {0}, so earlier freezes of this plan text cannot be "
                     "ruled out]".format(instances))

    scope = result.get("scope") or {}
    launch = scope.get("launch") or {}
    if result["runs"]:
        lines.append("The gate recorded {0} run(s) of the plan's steps under this approval: {1} with a matched "
                     "launch, {2} unmatched, {3} ambiguous, {4} from before launch matching was recorded. {5}"
                     .format(result["runs"], launch.get("matched", 0), launch.get("unmatched", 0),
                             launch.get("ambiguous", 0), launch.get("legacy", 0), source(receipts)))
    else:
        lines.append("[BLANK: no run receipt in {0} names this plan, so the records do not establish what ran]"
                     .format(receipts))

    repinned = gate.read_repins(root, digest) if gate else []
    if repinned:
        lines.append("The gate re-pinned {0} file(s) at run time under a working scope, each recorded with the run "
                     "that used it; a re-pin is not a new approval. {1}".format(len(repinned), source(repins)))
    else:
        lines.append("[BLANK: no re-pin record at {0}; the gate writes one whenever a run changes a pinned file, so "
                     "absence means none was recorded]".format(repins))

    if result.get("envs"):
        lines.append("{0} conda environment(s) used by these runs were recorded with their package versions. {1}"
                     .format(len(result["envs"]), source(receipts)))
    else:
        lines.append("[BLANK: no conda environment was recorded for these runs, so tool versions other than the "
                     "plugin's are not in the records]")

    lines.append("The checking stage reports {0} for this plan. {1}".format(result["status"], source(checked)))
    overall = (result.get("qualification") or {}).get("overall")
    if overall:
        lines.append("Reportable qualification at the time of this check: {0}; that covers evidence linkage, not "
                     "whether the analysis is scientifically right. {1}".format(overall, source(checked)))

    claims = result.get("claims") or []
    counts = collections.Counter(c["verdict"] for doc in claims for c in doc["claims"])
    if claims:
        lines.append("{0} claimed value(s) in {1} document(s) were checked against the output cells they name: {2} "
                     "verified, {3} mismatch, {4} unverified, {5} from an explore run only. {6}".format(
                         sum(counts.values()), len(claims),
                         counts.get("verified", 0) + counts.get("verified-transform", 0),
                         counts.get("mismatch", 0), counts.get("unverified", 0), counts.get("explore-only", 0),
                         source(claims[0]["doc"], "claims block")))
    else:
        lines.append("[BLANK: no document with a `<!-- claims -->` block, so the numbers written in the text were "
                     "not checked against their outputs]")

    citations = result.get("citations") or []
    if citations:
        cited = collections.Counter(c["verdict"] for c in citations)
        lines.append("{0} citation identifier(s) were found: {1} resolved, {2} mismatch, {3} unresolved, {4} carrying "
                     "no identifier. {5}".format(
                         len(citations), cited.get("resolved", 0), cited.get("mismatch", 0),
                         cited.get("unresolved", 0), cited.get("no identifier", 0),
                         source(claims[0]["doc"]) if claims else source(approval)))
        unchecked = cited.get("not checked (offline)", 0) + cited.get("not checked (request failed)", 0)
        if unchecked:
            lines.append("[BLANK: {0} citation(s) were not checked, because resolution needs network access; re-run "
                         "verify with `--resolve-citations` to check them]".format(unchecked))
    else:
        lines.append("[BLANK: no DOI, PMID or arXiv ID was found in the checked documents, so no citation was "
                     "resolved; references without an identifier cannot be checked]")

    lint = result.get("lint") or {}
    findings, waived = lint.get("findings") or [], lint.get("waived") or []
    if findings or waived:
        lines.append("{0} lint finding(s) were open on the code this plan covers, {1} of them waived with a stated "
                     "reason in the code. {2}".format(
                         len(findings) + len(waived), len(waived), source(checked, "scilintr findings")))
    else:
        lines.append("No lint finding was open on the code this plan covers at the time of this check. {0}".format(
            source(checked, "scilintr findings")))

    git = result.get("git")
    if git and git.get("head"):
        lines.append("The repository was at commit {0}{1} when this check ran. {2}".format(
            git["head"][:12], ", with uncommitted changes to tracked files" if git.get("dirty") else ", clean",
            source("git rev-parse HEAD, at check time")))
    else:
        lines.append("[BLANK: the repository's commit at the time of this check was not readable]")
    return "\n".join(lines) + "\n"


def _write_bundle(root, result, folder):
    if not os.path.isdir(os.path.join(root, result["analysis_dir"])):
        sys.exit("verify: analysis folder {} does not exist.".format(result["analysis_dir"]))
    os.makedirs(folder, exist_ok=True)
    digest = result["hash"]
    stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime())
    paths = {"plan": "plan-{}.md".format(digest), "receipts": "receipts-{}.jsonl".format(digest),
             "outputs": "outputs-{}.tsv".format(digest), "report": "verify-{}.md".format(digest),
             "lint": "lint-{}.txt".format(digest)}
    if result.get("validation_binding"):  # the frozen binding, each check's outcome and the raw evidence's identity
        paths["validation"] = "validation-{}.json".format(digest)
        with open(os.path.join(folder, paths["validation"]), "w", encoding="utf-8") as handle:
            json.dump({"schema": "mycelium-extra.validation-record.v1", "hash": digest,
                       "instance": (result.get("instance") or {}).get("selected"),
                       "binding": result["validation_binding"], "results": result["validation"]},
                      handle, indent=1, sort_keys=True)
            handle.write("\n")
    if any(env["packages"] for env in result.get("envs") or []):
        paths["env"] = "env-{}.txt".format(digest)
        with open(os.path.join(folder, paths["env"]), "w", encoding="utf-8", errors="surrogateescape") as handle:
            handle.write("# Conda envs of plan {}'s runs, read {} from each env's conda-meta (the format of "
                         "`conda list --explicit --md5`).\n# One block per env: copy a block from `@EXPLICIT` "
                         "into its own file for `conda create -n <name> --file <file>`.\n".format(digest, stamp))
            for env in (e for e in result["envs"] if e["packages"]):
                handle.write("\n# env: {}\n# prefix: {}\n# from: {}\n{}@EXPLICIT\n{}\n".format(
                    env["env"], env["prefix"], env["source"],
                    "# changed after the run: this is the env as it was when verify read it\n"
                    if env["changed_after_run"] else "", "\n".join(env["packages"])))
    if any(env.get("pip") for env in result.get("envs") or []):
        paths["pip"] = "pip-{}.txt".format(digest)
        with open(os.path.join(folder, paths["pip"]), "w", encoding="utf-8", errors="surrogateescape") as handle:
            handle.write("# Pip packages of plan {}'s runs, read {} from each conda env's site-packages: the "
                         "Python packages conda did not install.\n# Usable as: pip install -r {}. A commented-out package came "
                         "from a local path or archive: install it from there.\n".format(
                             digest, stamp, paths["pip"]))
            for env in (e for e in result["envs"] if e.get("pip")):
                handle.write("\n# env: {}\n# prefix: {}\n# from: {}\n{}{}\n".format(
                    env["env"], env["prefix"], env["source"],
                    "# changed after the run: this is the env as it was when verify read it\n"
                    if env["pip_changed_after_run"] else "", "\n".join(env["pip"])))
    if result.get("rule_envs"):
        paths["rule_envs"] = "rule-envs-{}.json".format(digest)
        with open(os.path.join(folder, paths["rule_envs"]), "w", encoding="utf-8") as handle:
            json.dump({"schema": "mycelium-extra.rule-envs.v1", "hash": digest,
                       "note": "Read from `.snakemake/conda/`; the layout was checked on a synthetic folder, "
                               "not a real Snakemake run.", "envs": result["rule_envs"]},
                      handle, indent=1, sort_keys=True)
            handle.write("\n")
    with open(os.path.join(folder, paths["plan"]), "w", encoding="utf-8", errors="surrogateescape") as handle:
        handle.write("# Approved plan {}\n\nApproved {} in session {}. Frozen copy of the plan "
                     "the mycelium-extra gate approved; do not edit it. Revise the analysis's own plan "
                     "instead.\n\n---\n\n{}\n".format(digest, when(result["approved_at"]),
                                                      result["session_id"], result["plan"].rstrip()))
    with open(os.path.join(folder, paths["receipts"]), "w", encoding="utf-8", errors="surrogateescape") as handle:
        for receipt in result["receipts"]:
            handle.write(json.dumps(receipt, sort_keys=True) + "\n")
    with open(os.path.join(folder, paths["outputs"]), "w", encoding="utf-8", errors="surrogateescape") as handle:
        # The first six columns are the older format (stale reads only the first three); a table without
        # the last four is a legacy bundle: its producers were chosen by timing, with no grade.
        handle.write("path\twritten\tsize\tsha256\tfingerprint\twritten_by\tproducer_attempt\tevidence_method"
                     "\tstrength\tapproval_instance\n")
        for row in result["outputs"]:
            record = row["record"]
            handle.write("\t".join(str(v) for v in [
                row["path"], time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(row["written"])),
                record.get("size", ""), record.get("sha256", ""), gate.method(record),
                row["by"] + (" via " + row["rule"] if row["rule"] else ""),
                row["producer_attempt"] or "", row["evidence_method"], row["strength"],
                (result.get("instance") or {}).get("selected") or "legacy"]) + "\n")
    with open(os.path.join(folder, paths["lint"]), "w", encoding="utf-8", errors="surrogateescape") as handle:
        lint = result["lint"]
        handle.write("\n\n".join(lint["output"]) or "scilintr did not run.")
        handle.write("\n\n# ANALYSIS_OK waivers ({})\n".format(len(lint["waivers"])))
        handle.writelines("{}:{}: {}\n".format(*w) for w in lint["waivers"])
        handle.write("\n# Waived findings ({})\n".format(len(lint.get("waived", []))))
        handle.writelines("{}:{} [{}] <- {}\n".format(w[0], w[1], w[2], waiver_note(w).replace("`", ""))
                          for w in lint.get("waived", []))
        handle.write("\n# Approved thresholds ({})\n".format(len(lint.get("approved", []))))
        handle.writelines("{}:{} [{}]\n".format(f[0], f[1], f[3]) for f in lint.get("approved", []))
    with open(os.path.join(folder, paths["report"]), "w", encoding="utf-8", errors="surrogateescape") as handle:
        handle.write("Written {} by mycelium-extra verify.\n\n".format(stamp))
        handle.write(render(result, all_outputs=True, saved=True))
    index = os.path.join(folder, "PROVENANCE.md")
    row = "| {} | {} | {} | {} | [plan]({}) - [receipts]({}) - [outputs]({}) - [lint]({}) - [report]({}){} |".format(
        digest, when(result["approved_at"]), stamp, result["status"], paths["plan"], paths["receipts"],
        paths["outputs"], paths["lint"], paths["report"],
        (" - [validation]({})".format(paths["validation"]) if "validation" in paths else "") +
        (" - [conda env]({})".format(paths["env"]) if "env" in paths else "") +
        (" - [pip]({})".format(paths["pip"]) if "pip" in paths else "") +
        (" - [rule envs]({})".format(paths["rule_envs"]) if "rule_envs" in paths else ""))
    if os.path.isfile(index):
        with open(index, encoding="utf-8") as handle:
            lines = [line.rstrip("\n") for line in handle if not line.startswith("| {} |".format(digest))]
    else:
        lines = ["# Provenance", "",
                 "One row per approved plan checked for this analysis by mycelium-extra verify. Each plan's "
                 "frozen text, its run receipts, and the check sit beside this file.", "",
                 "| Plan | Approved | Verified | Status | Files |", "|---|---|---|---|---|"]
    lines.append(row)
    with open(index, "w", encoding="utf-8", errors="surrogateescape") as handle:
        handle.write("\n".join(lines) + "\n")
    return ["PROVENANCE.md"] + list(paths.values())


def write(root, result):
    if not os.path.isdir(os.path.join(root, result["analysis_dir"])):
        sys.exit("verify: analysis folder {} does not exist.".format(result["analysis_dir"]))
    import provenance
    folder = os.path.join(root, result["analysis_dir"], "provenance")
    names = provenance.publish(folder, result["hash"], lambda stage: _write_bundle(root, result, stage))
    return [os.path.join(os.path.relpath(folder, root), name) for name in names]


def approved_plans(root):
    """(approved_at, hash, planned scripts, run count) for each approval the gate holds."""
    receipts = read_jsonl(gate.state_path(root, "receipts.jsonl"))
    folder = gate.state_path(root, "approvals")
    config = gate.load_config(root)
    runs = collections.Counter(digest for r in receipts
                               if not r.get("explore") and is_run(root, r, config["gated_commands"])
                               for digest in set(r.get("plans", [])))
    rows = []
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not name.endswith(".json"):
            continue
        record = read_approval(os.path.join(folder, name))
        if not record:
            continue
        digest = record.get("hash", name[:8])
        table = gate.plan_table(record.get("plan", ""), every_cell=True)
        scripts = [p for p in gate.plan_paths_in(root, table) if gate.gated_rel(root, root, p, config)]
        rows.append((record.get("approved_at", 0), digest, scripts, runs[digest]))
    return rows


def limit_marks(root, rows):
    """{hash: "limit N reached (M since approval)"} for approvals at or over `max_runs_per_approval`, from the
    receipts and `approved_at`. Empty when the setting is unset or invalid: the gate ignores those too. The
    approval record is never written; this is derived each time."""
    config = gate.load_config(root)
    limit = config.get("max_runs_per_approval")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        return {}
    receipts = read_jsonl(gate.state_path(root, "receipts.jsonl"))
    marks = {}
    for approved, digest, _, _ in rows:
        used = len(approval_runs(root, config, digest, approved, receipts))
        if used >= limit:
            marks[digest] = "limit {} reached ({} since approval)".format(limit, used)
    return marks


def list_plans(root):
    lines = ["| Plan | Approved | Scripts in table | Runs |", "|---|---|---|---|"]
    plans = approved_plans(root)
    marks = limit_marks(root, plans)
    for approved, digest, scripts, count in sorted(plans, reverse=True):
        lines.append("| {} | {} | {} | {}{} |".format(digest, when(approved), len(scripts), count,
                                                     " ({})".format(marks[digest]) if digest in marks else ""))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- stale sweep

def provenance_receipts(root):
    """Include interrupted first saves, using Git's inventory without scanning data trees."""
    listed = gate.git(root, "ls-files", "-co", "--exclude-standard", "--",
                      "*provenance/receipts-*.jsonl", "*provenance/complete-*.json",
                      "*provenance/.transactions/pending.json")
    if listed is not None:
        paths = set(line for line in listed.splitlines() if line)
    else:
        paths = set()
        for folder, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            if os.path.basename(folder) == "provenance":
                paths.update(os.path.relpath(os.path.join(folder, f), root) for f in files)
                if os.path.isfile(os.path.join(folder, ".transactions", "pending.json")):
                    paths.add(os.path.relpath(os.path.join(folder, ".transactions", "pending.json"), root))
    found = set()
    for rel in paths:
        name, folder = os.path.basename(rel), os.path.dirname(rel)
        if re.fullmatch(r"receipts-[0-9a-f]{8}\.jsonl", name):
            found.add(rel)
        elif re.fullmatch(r"complete-[0-9a-f]{8}\.json", name):
            found.add(os.path.join(folder, "receipts-" + name[9:-5] + ".jsonl"))
        elif name == "pending.json" and os.path.basename(folder) == ".transactions":
            pending = gate.read_json(os.path.join(root, rel), {})
            if isinstance(pending, dict) and isinstance(pending.get("members"), dict):
                found.update(os.path.join(os.path.dirname(folder), f) for f in pending["members"]
                             if re.fullmatch(r"receipts-[0-9a-f]{8}\.jsonl", f))
    return sorted(found)


# ---------------------------------------------------------------- refs lookup

def refs(root, path, sha=None):
    """Which saved bundles pinned `path` as a check's test or expectation file. Read-only, over `provenance/`.
    `definite`: a pinned file has this SHA256 (the path may have moved); `possible`: the same path pinned with another
    SHA256 or none given, or the path is named in the bundle's plan text. A bundle without a validation record cannot
    be searched for pins; it is counted, and still `possible` when its plan text names the path."""
    path = os.path.normpath(os.path.relpath(path, root) if os.path.isabs(path) else path)
    sha = (sha or "").lower() or None
    found, unsearched = [], 0
    for receipts in provenance_receipts(root):
        folder, digest = os.path.dirname(receipts), os.path.basename(receipts)[len("receipts-"):-len(".jsonl")]
        record = gate.read_json(os.path.join(root, folder, "validation-{}.json".format(digest)), None)
        hits = []
        checks = ((record or {}).get("binding") or {}).get("checks") if isinstance(record, dict) else None
        for check in checks if isinstance(checks, list) else []:
            for name, have in sorted((check.get("files") or {}).items()):
                if sha and isinstance(have, str) and have.startswith(sha):
                    hits.append(("definite", check.get("id"), name, "SHA256 matches"))
                elif os.path.normpath(name) == path:
                    hits.append(("possible", check.get("id"), name, "same path, SHA256 {}".format(
                        "differs ({})".format(have[:12]) if sha else "not compared; give --sha")))
        if not isinstance(checks, list):
            unsearched += 1
        try:
            with open(os.path.join(root, folder, "plan-{}.md".format(digest)), encoding="utf-8", errors="replace") as handle:
                named = path in handle.read()
        except OSError:
            named = False
        if named and not hits:
            hits.append(("possible", None, path, "named in the plan text; no pin recorded"))
        if hits:
            found.append({"hash": digest, "folder": folder, "hits": hits})
    return {"path": path, "sha": sha, "bundles": found, "unsearched": unsearched}


def render_refs(result):
    lines = ["Looking for `{}`{}".format(result["path"], " with SHA256 " + result["sha"] if result["sha"] else
                                         " (no --sha: a path match is only possible)"), ""]
    for level in ("definite", "possible"):
        for bundle in result["bundles"]:
            for kind, check, name, why in bundle["hits"]:
                if kind == level:
                    lines.append("- {}: plan {} in `{}`{}: {} ({})".format(
                        level, bundle["hash"], bundle["folder"], " check `{}`".format(check) if check else "",
                        name, why))
    if not result["bundles"]:
        lines.append("No bundle records a reference.")
    lines += ["", "No recorded reference is not proof the file was unused.",
              "{} bundle(s) have no validation record, so their pins cannot be searched.".format(result["unsearched"]),
              "Nothing was written; old receipts and findings are unchanged."]
    return "\n".join(lines) + "\n"


def output_fingerprint(path, budget):
    """An output is identified by its bytes. The gate reads a notebook as its code cells (right for the code that
    ran, wrong for results: executing it rewrites its outputs and its recorded size is the code's length), so an
    `.ipynb` output is hashed raw here."""
    try:
        info = os.stat(path)
    except OSError:
        return {"missing": True}
    if not path.endswith(".ipynb") or os.path.isdir(path):
        return gate.fingerprint(path, budget)
    record = {"size": info.st_size, "mtime": int(info.st_mtime)}
    if info.st_size <= budget["bytes"] and time.time() < budget["deadline"]:
        digest = gate.sha256_file(path, budget["deadline"])
        if digest:
            record["sha256"] = digest
            budget["bytes"] -= info.st_size
    return record


def stale_plan(root, rel, budget, content=False):
    import provenance
    folder = os.path.join(root, os.path.dirname(rel))
    with provenance.locked(os.path.join(folder, ".publish.lock")):
        digest = os.path.basename(rel)[len("receipts-"):-len(".jsonl")]
        state = provenance.bundle_state(folder, digest)
        result = ({"hash": digest, "analysis_dir": os.path.dirname(os.path.dirname(rel)) or ".",
                   "changes": [], "sessions": [], "content_checked": 0, "content_unchecked": 0}
                  if state == "interrupted" else _stale_plan(root, rel, budget, content))
        result["bundle"] = state
        result["recorded_approved"], result["recorded_verified"] = recorded_verify(folder, digest)
        result["recorded_lint"] = recorded_lint(folder, digest) if state != "interrupted" else "unchecked"
        if state != "complete":
            result["changes"].append("provenance bundle {}: no checksummed completion established".format(state))
        return result


def _stale_plan(root, rel, budget, content=False):
    """What no longer matches one plan's provenance: scripts, pinned inputs, outputs. Outputs are checked by size and
    time, or with `content` by the SHA256 verify saved; a file that cannot be hashed (no saved SHA256, or the byte or
    time budget is spent) keeps the metadata check and is counted as `content_unchecked`."""
    folder = os.path.dirname(rel)
    digest = os.path.basename(rel)[len("receipts-"):-len(".jsonl")]
    runs = [r for r in read_jsonl(os.path.join(root, rel)) if not r.get("explore") and not r.get("not_a_run")]
    changes, scripts = [], {}
    for r in runs:
        script = r.get("script") or {}
        if script.get("in_repo") and not script.get("missing"):
            scripts[script["path"]] = (r, script)  # receipts are in time order, so the last run wins
    for path, (r, recorded) in sorted(scripts.items()):
        now = gate.fingerprint(os.path.join(root, path), budget, pin=recorded)
        if now.get("missing"):
            changes.append("script `{}` deleted since it ran at {}".format(path, when(r.get("ts"))))
        elif not gate.unchanged(recorded, now):
            changes.append("script `{}` edited since it ran at {}".format(path, when(r.get("ts"))))
    pins = (runs[-1].get("pins") or {}) if runs else {}
    for path, pin in sorted(pins.items()):
        now = gate.fingerprint(os.path.join(root, path), budget, pin=pin)
        if not gate.unchanged(pin, now):
            changes.append("input `{}` changed (was {}, now {})".format(path, gate.describe(pin), gate.describe(now)))
    table = os.path.join(root, folder, "outputs-{}.tsv".format(digest))
    rows, producers = [], None
    if os.path.isfile(table):
        with open(table, encoding="utf-8") as handle:
            lines = [line.rstrip("\n").split("\t") for line in handle]
        rows = lines[1:]
        # a table without the evidence columns is from a verify that chose the producer by time alone
        producers = "graded" if lines and "evidence_method" in lines[0] else "legacy"
    hashed = unchecked = 0
    for row in rows:
        if len(row) < 3:
            continue
        path, written, size = row[0], row[1], row[2]
        try:
            info = os.stat(os.path.join(root, path))
        except OSError:
            changes.append("output `{}` deleted since verify recorded it".format(path))
            continue
        if content:
            saved = row[3] if len(row) > 3 else ""
            now = output_fingerprint(os.path.join(root, path), budget) if saved else {}
            if now.get("sha256"):
                hashed += 1
                if now["sha256"] != saved:
                    changes.append("output `{}` content differs from the SHA256 verify saved (rewritten {})".format(
                        path, when(info.st_mtime)))
                continue  # the content decides; a touched file with the same bytes is not a change
            unchecked += 1
        try:
            then = datetime.datetime.strptime(written, "%Y-%m-%dT%H:%M:%S%z").timestamp()
        except ValueError:
            then = None
        if (size and str(info.st_size) != size) or (then is not None and abs(info.st_mtime - then) > 2):
            changes.append("output `{}` rewritten {} (provenance out of date)".format(path, when(info.st_mtime)))
    sessions = sorted({r["session_id"] for r in runs if r.get("session_id")})
    return {"hash": digest, "analysis_dir": os.path.dirname(folder) or ".", "changes": changes,
            "sessions": sessions, "producers": producers, "content_checked": hashed, "content_unchecked": unchecked}


def stale(root, hash_mb, seconds, content=False):
    budget = {"bytes": float(hash_mb) * 1024 * 1024, "deadline": time.time() + seconds}
    plans = [stale_plan(root, rel, budget, content) for rel in provenance_receipts(root)]
    return {"plans": len(plans), "mode": "content" if content else "metadata",
            "content_checked": sum(p["content_checked"] for p in plans),
            "content_unchecked": sum(p["content_unchecked"] for p in plans),
            "stale": [p for p in plans if p["changes"]]}


def stale_note(result):
    """How the outputs were checked: by size and time (metadata checked), or by saved SHA256 with what was not."""
    if result.get("mode") != "content":
        return "Outputs: metadata checked (size and modification time), not content; `stale --content` compares the saved SHA256."
    return "Outputs: {} file(s) content checked against the saved SHA256{}.".format(
        result["content_checked"], "; content not checked for {} (no saved SHA256, or the --hash-mb/--seconds budget "
                                   "ran out), which keep the size and time check".format(result["content_unchecked"])
        if result["content_unchecked"] else "")


def render_stale(result):
    lines = []
    for plan in result["stale"]:
        lines += ["## Plan {} - `{}`".format(plan["hash"], plan["analysis_dir"]), ""]
        lines += ["- " + change for change in plan["changes"]]
        lines += ["- sessions: " + (", ".join(plan["sessions"]) or "none recorded"),
                  "- findings: `rg -n '{}' .living/findings/`".format(
                      "|".join(plan["sessions"] + ["plan " + plan["hash"]])), ""]
    summary = ("{} of {} verified plans stale.".format(len(result["stale"]), result["plans"])
               if result["plans"] else "No verified plans: no provenance/receipts-<hash>.jsonl found.")
    if not result["plans"]:
        return summary + "\n"
    # the summary leads a clean result and ends a stale one; the label goes at the other end
    lines = lines + [summary] if result["stale"] else [summary, stale_note(result)]
    if result["stale"]:
        lines.insert(0, stale_note(result) + "\n")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- status

MANIFEST_STATUS = re.compile(r"^[\s#>*-]*status[\s*]*:(.*)$", re.IGNORECASE)
HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")


def first_word(text):
    match = re.search(r"[A-Za-z][\w-]*", text)
    return match.group(0).lower() if match else ""


def manifest_status(root, folder):
    """`listed: <first status word>`, `listed`, or `not listed` in an ANALYSIS_MANIFEST.md.
    An entry is a table row or a heading's section naming the folder's path, or a heading
    that is the folder's name; Mycelium's YAML `status:`, `**Status**:` lines and a table's
    Status cell are read."""
    listed = gate.git(root, "ls-files", "-co", "--exclude-standard", "--", "*ANALYSIS_MANIFEST.md")
    files = listed.split() if listed is not None else [
        f for f in ["analysis/ANALYSIS_MANIFEST.md"] if os.path.isfile(os.path.join(root, f))]
    path = re.compile(r"(?<![\w./-])" + re.escape(folder.rstrip("/")) + r"(?![\w.-])")
    found = False
    for rel in files:
        lines = read_text(os.path.join(root, rel)).splitlines()
        header, section, matched, fenced = None, [], False, False
        for i, line in enumerate(lines + ["# end"]):
            if line.lstrip().startswith("```"):
                fenced = not fenced
            heading = not fenced and HEADING.match(line)
            if heading:
                if matched:
                    for text in section:
                        status = MANIFEST_STATUS.match(text)
                        if status and first_word(status.group(1)):
                            return "listed: " + first_word(status.group(1))
                    found = True
                section, matched = [], heading.group(1).strip("`* ") == os.path.basename(folder)
                continue
            row = gate.TABLE_ROW.match(line)
            if row and not gate.TABLE_RULE.match(line):
                cells = [c.strip().lower() for c in row.group(1).split("|")]
                following = lines[i + 1] if i + 1 < len(lines) else ""
                if gate.TABLE_RULE.match(following):
                    header = cells
                elif path.search(line):
                    found = True
                    if header and "status" in header and header.index("status") < len(cells):
                        word = first_word(cells[header.index("status")])
                        if word:
                            return "listed: " + word
                continue
            header = None if not row else header
            section.append(line)
            matched = matched or bool(path.search(line))
    return "listed" if found else "not listed"


def recorded_lint(folder, digest):
    text = read_text(os.path.join(folder, "lint-{}.txt".format(digest)))
    if not text:
        return "not recorded"
    approved = re.search(r"^# Approved thresholds \((\d+)\)$", text, re.M)
    approved = int(approved.group(1)) if approved else 0
    text = text.split("# ANALYSIS_OK waivers")[0]
    found = max(sum(1 for line in text.splitlines() if LINT_LINE.match(line)) - approved, 0)
    # A missing, timed-out or unreadable linter leaves no finding in the lint file; the report names it.
    gaps = sorted(set(re.findall(r"scilintr \((\w+)\) not checked",
                                 read_text(os.path.join(folder, "verify-{}.md".format(digest))))))
    states = (["{} finding(s)".format(found)] if found else []) + (
        ["{} approved threshold(s)".format(approved)] if approved else []) + (
        ["gap: {} not checked".format(", ".join(gaps))] if gaps else [])
    if states:
        return "; ".join(states)
    return "clean" if text.startswith("$ ") else "not run"


def recorded_verify(folder, digest):
    """(approved, verify status) from the analysis's PROVENANCE.md row for the plan."""
    for line in read_text(os.path.join(folder, "PROVENANCE.md")).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[0] == digest:
            return cells[1], cells[3]
    return "?", "verified"


def status(root, hash_mb, seconds):
    """One row per approved or verified plan: folder, runs, verify status, staleness, lint, manifest."""
    budget = {"bytes": float(hash_mb) * 1024 * 1024, "deadline": time.time() + seconds}
    rows = {}
    if gate.find_root(root):
        plans = approved_plans(root)
        marks = limit_marks(root, plans)
        for approved, digest, scripts, count in plans:
            rows[digest] = {"hash": digest, "approved": when(approved), "epoch": approved, "runs": count,
                            "analysis_dir": guess_analysis_dir(scripts) or "?", "verified": "not verified",
                            "stale": "-", "lint": "-", "reportable": "-"}
            if digest in marks:
                rows[digest]["expired"] = marks[digest]
    for rel in provenance_receipts(root):
        plan = stale_plan(root, rel, budget)
        folder = os.path.join(root, os.path.dirname(rel))
        approved, verified = plan["recorded_approved"], plan["recorded_verified"]
        runs = sum(1 for r in read_jsonl(os.path.join(root, rel)) if not r.get("explore") and not r.get("not_a_run"))
        row = rows.setdefault(plan["hash"], {"hash": plan["hash"], "approved": approved, "epoch": 0, "runs": runs})
        row.update(analysis_dir=plan["analysis_dir"], lint=plan["recorded_lint"],
                   reportable=recorded_qualification(folder, plan["hash"]),
                   verified=verified + " (" + plan["bundle"] + (", legacy producers" if plan.get("producers") == "legacy" else "") + ")",
                   stale="{} change(s)".format(len(plan["changes"])) if plan["changes"] else "no",
                   changes=plan["changes"])
    for row in rows.values():
        row["manifest"] = manifest_status(root, row["analysis_dir"]) if row["analysis_dir"] != "?" else "-"
    return sorted(rows.values(), key=lambda r: (r["epoch"], r["approved"], r["hash"]), reverse=True)


def render_status(rows):
    if not rows:
        return "No plans: nothing approved here and no provenance/receipts-<hash>.jsonl found.\n"
    lines = ["| Plan | Analysis | Approved | Runs | Verified | Stale | Lint | Manifest | Reportable |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append("| {hash} | `{analysis_dir}` | {approved} | {runs}{expired} | {verified} | {stale} | {lint} | "
                     "{manifest} | {reportable} |".format(**dict(r, expired=" ({})".format(r["expired"]) if r.get("expired") else "")))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- explore runs

EXPLORE_DAYS = 7


def explore_attempt(r):
    """One explore receipt as an attempt: when, its attempt id, the scope it ran under (the approval instance of
    `allow explore <hash>`; None for the session-wide grant), its exit status, and the code version: the script it
    ran and that script's sha256 as the gate fingerprinted it at launch (None when only metadata was recorded)."""
    script = r.get("script") if isinstance(r.get("script"), dict) else {}
    pins = r.get("explore_script_pins") if isinstance(r.get("explore_script_pins"), dict) else {}
    path, sha = script.get("path"), script.get("sha256")
    for name, pin in sorted(pins.items()) if not sha else ():
        if isinstance(pin, dict) and pin.get("sha256"):
            path, sha = name, pin["sha256"]
            break
    return {"ts": r.get("ts"), "attempt_id": r.get("attempt_id"), "scope": r.get("explore_scope"),
            "exit_status": r.get("exit_status"), "script": path, "script_sha256": sha}


def explore_origin(receipts, mine, rel, mtime):
    """The explore receipts whose attempt window holds the write time of output `rel`, when no matched attempt of
    the plan saw it change: such an output is the exploration's, not re-run under approval. Neither the gate nor a
    receipt records an explore run's output hash, so "the same content" is judged by the file's write time falling
    inside the explore attempt (the file is unchanged since); an approved rerun that rewrote the bytes moved the time."""
    if any(rel in (observed_paths(r) or ()) and fits_attempt(r, mtime) for r in mine):
        return []
    return [r for r in receipts if r.get("explore") and window(r)[0] - TOLERANCE <= mtime <= r["ts"] + TOLERANCE]


def explore_runs(root, session, hash_mb, seconds):
    """Explore runs of gated code, newest command last, one entry per distinct command:
    the material for a grill plan that re-runs them reportably."""
    config = gate.load_config(root)
    budget = {"bytes": float(hash_mb) * 1024 * 1024, "deadline": time.time() + seconds}
    since = time.time() - EXPLORE_DAYS * 86400
    prefix = re.compile(r"(^|\s){}=1\s+".format(gate.EXPLORE_VAR))
    merged = collections.OrderedDict()
    for r in read_jsonl(gate.state_path(root, "receipts.jsonl")):
        if not r.get("explore") or not is_run(root, r, config["gated_commands"]):
            continue
        if (r.get("session_id") != session) if session else r.get("ts", 0) < since:
            continue
        command = prefix.sub(r"\1", r.get("command", "")).strip()
        key = (r.get("cwd") or ".", command)
        entry = merged.pop(key, {"command": command, "cwd": key[0], "runs": 0, "first": r.get("ts"), "attempts": []})
        env = conda_env(root, r) or {}
        entry["attempts"].append(explore_attempt(r))  # every try stays, a failed one with the code it ran
        entry.update(runs=entry["runs"] + 1, last=r.get("ts"), session=r.get("session_id"),
                     paths=ran_paths(root, r), exit_status=r.get("exit_status"), env=env.get("env"))
        script = r.get("script") or {}
        entry["changed"] = None
        if script.get("in_repo") and script.get("missing"):
            entry["changed"] = "script `{}` not found when this ran".format(script["path"])
        elif script.get("in_repo"):
            now = gate.fingerprint(os.path.join(root, script["path"]), budget, pin=script)
            if now.get("missing"):
                entry["changed"] = "script `{}` deleted since this run".format(script["path"])
            elif not gate.unchanged(script, now):
                entry["changed"] = "script `{}` edited since this run".format(script["path"])
        merged[key] = entry  # re-inserted, so the order follows each command's last run
    return list(merged.values())


def render_explore(runs, scope):
    lines = ["# Explore runs ({})".format(scope), ""]
    if not runs:
        lines.append("None recorded.")
    for i, run in enumerate(runs, 1):
        lines.append("{}. `{}`".format(i, run["command"]))
        if run["cwd"] != ".":
            lines.append("   - from `{}`".format(run["cwd"]))
        if run["paths"]:
            lines.append("   - ran: " + ", ".join("`{}`".format(p) for p in run["paths"]))
        lines.append("   - last run {}{}, exit {}".format(
            when(run["last"]), " ({} runs)".format(run["runs"]) if run["runs"] > 1 else "",
            "not recorded" if run["exit_status"] is None else run["exit_status"]))
        if run["env"]:
            lines.append("   - conda env `{}`".format(run["env"]))
        for n, a in enumerate(run["attempts"], 1):
            code = a["exit_status"]
            lines.append("   - attempt {}: {}, exit {}{}, code {}, {}".format(
                n, when(a["ts"]), "not recorded" if code is None else code,
                " (failed)" if code not in (None, 0, "unknown") else "",
                "`{}` sha256 {}".format(a["script"], a["script_sha256"][:12]) if a["script_sha256"]
                else "not recorded (no content hash)",
                "scope " + a["scope"] if a["scope"] else "session-wide grant (not tied to a plan)"))
        if run["changed"]:
            lines.append("   - " + run["changed"])
    lines += ["", "Explore outputs are not results, and an explore run never validates a check or owns an output. "
                  "Promotion needs an approved rerun with fresh output identity: a plan that re-runs these commands "
                  "without the `{}=1` prefix, approved, and a run the gate sees write its outputs. `verify report` "
                  "marks an output written inside an explore attempt and not re-observed under a matched approved "
                  "attempt `not re-run under approval`; it is never relabelled. Explore runs of inline code "
                  "(`python -c`) are not recorded here.".format(gate.EXPLORE_VAR)]
    return "\n".join(lines) + "\n"


ID_HEADERS = ("#", "id", "no", "no.")


def squash(text):
    """Whitespace collapsed to single spaces: what two plans are compared by, never shortened."""
    return " ".join(str(text).split())


def plan_rows(plan):
    """(rows, unusable, columns) of the plan's tables. rows: the rows keyed by their ID cell (the
    column headed `#`, `id`, `no` or `no.`, else the first), each a {lowercased header: cell} dict
    with whitespace collapsed. unusable: {key: reason} for an ID used twice or a row with none (such
    rows are not in `rows`: they cannot be matched, so they are never compared). columns: the headers."""
    rows, unusable, columns, header, key_at = collections.OrderedDict(), collections.OrderedDict(), [], None, 0
    lines = plan.splitlines()
    for i, line in enumerate(lines):
        match = gate.TABLE_ROW.match(line)
        if not match:
            header = None
            continue
        if gate.TABLE_RULE.match(line):
            continue
        cells = [squash(cell.replace("\0", "|")) for cell in match.group(1).replace("\\|", "\0").split("|")]
        following = lines[i + 1] if i + 1 < len(lines) else ""
        if gate.TABLE_ROW.match(following) and gate.TABLE_RULE.match(following):
            header = [cell.lower() for cell in cells]
            key_at = next((j for j, name in enumerate(header) if name in ID_HEADERS), 0)
            columns += [name for name in header if name not in columns]
        elif header:
            key = cells[key_at] if key_at < len(cells) else ""
            if not key:
                unusable["(no ID)"] = "a row has no ID"
            elif key in rows or key in unusable:
                rows.pop(key, None)
                unusable[key] = "duplicate ID"
            else:
                rows[key] = dict(zip(header, cells))
    return rows, unusable, columns


def shown_plan(root, digest):
    """The text of a plan the gate showed but nobody approved yet (pending/<session>.json), or None."""
    folder = gate.state_path(root, "pending")
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not name.endswith(".json") or name.endswith(".hints.json"):
            continue
        entries = gate.read_json(os.path.join(folder, name), [])
        for entry in entries if isinstance(entries, list) else []:
            if isinstance(entry, dict) and entry.get("hash") == digest:
                return entry.get("text", "")
    return None


def plan_changes(old_text, new_text):
    """(step, column, was, now) for each difference between two plans' tables. column is "removed" or
    "added" for a whole row (its cells joined by " / "), "cannot compare" for an ID that is used
    twice or missing, "column removed" for a dropped header, "order changed" for the same IDs in a
    different order, else the header of a changed cell. Cells are compared whole, whitespace aside."""
    (before, bad_before, columns_before), (after, bad_after, columns_after) = plan_rows(old_text), plan_rows(new_text)
    changes = []
    for key in list(bad_before) + [k for k in bad_after if k not in bad_before]:
        sides = " and ".join(name for name, bad in (("old", bad_before), ("new", bad_after)) if key in bad)
        reason = (bad_before.get(key) or bad_after[key]).replace("a row has no ID", "row without an ID")
        changes.append((key, "cannot compare", "{} in the {} plan".format(reason, sides), ""))
    for key in list(before) + [k for k in after if k not in before]:
        if key in bad_before or key in bad_after:
            continue
        if key not in after:
            changes.append((key, "removed", " / ".join(before[key].values()), ""))
        elif key not in before:
            changes.append((key, "added", "", " / ".join(after[key].values())))
        else:
            changes += [(key, column, before[key].get(column, ""), now)
                        for column, now in after[key].items() if before[key].get(column, "") != now]
    changes += [("", "column removed", name, "") for name in columns_before if name not in columns_after]
    kept_before, kept_after = [k for k in before if k in after], [k for k in after if k in before]
    if kept_before != kept_after:
        changes.append(("", "order changed", " ".join(kept_before), " ".join(kept_after)))
    return changes


def plan_objective(text):
    """The plan's objective, whole and whitespace-collapsed ("" if none): the text after an
    `Objective` marker or under an `## Objective` heading, up to a blank line or the next structure."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        found = gate.OBJECTIVE_LINE.match(line)
        if found:
            heading = re.match(r"^\s*#+\s*objective\s*$", line, re.IGNORECASE)
            text = "" if heading else found.group(1)
            for more in lines[i + 1:]:
                if not more.strip():
                    if text.strip():
                        break
                    continue
                if gate.TABLE_ROW.match(more) or gate.INPUTS_LINE.match(more) or gate.OUTPUTS_LINE.match(more) \
                        or re.match(r"^\s*#", more):
                    break
                text += " " + more
            return squash(text)
    return ""


def plan_blocks(text, name):
    """The raw text of each `<!-- name ... -->` comment block, in order. Not parsed: only compared."""
    return [m.strip() for m in re.findall(r"<!--\s*" + name + r"\b(.*?)-->", text, re.DOTALL)]


def diff_plans(root, old, new):
    """What changed between two approved plans: the objective, table rows by step (added, removed,
    changed, reordered, and dropped columns), the `Inputs:` and `Outputs:` lines, the raw
    `validation-bindings` and `exact-execution` blocks, and the runs the plan table allows. Plans are
    compared whole, with whitespace collapsed. This is exact equality of what the plans say, not a
    judgement that the science is the same."""
    plans = []
    for digest in (old, new):
        record = read_approval(gate.state_path(root, "approvals", digest + ".json"))
        text = record.get("plan") if record else shown_plan(root, digest)
        if text is None:
            sys.exit("verify: no approved or shown plan {} (see `list`).".format(digest))
        plans.append(text)
    lines = ["# Plan diff {} -> {}".format(old, new), ""]
    was, now = [plan_objective(text) for text in plans]
    if was != now:
        lines.append("- Objective changed: `{}` -> `{}`. **Possible scientific change.**".format(was or "none", now or "none"))
    for key, column, was, now in plan_changes(plans[0], plans[1]):
        if column == "removed":
            lines.append("- Step {}: removed (was: {}).".format(key, was))
        elif column == "added":
            lines.append("- Step {}: added: {}.".format(key, now))
        elif column == "cannot compare":
            lines.append("- Step {}: cannot compare ({}); its rows are not matched.".format(key, was))
        elif column == "column removed":
            lines.append("- Column `{}` removed.".format(was))
        elif column == "order changed":
            lines.append("- Step order changed: {} -> {}.".format(was, now))
        else:
            flag = " **Possible scientific change.**" if column == "choice" else ""
            lines.append("- Step {}, {}: `{}` -> `{}`.{}".format(key, column, was, now, flag))
    for label, words, pattern in (("Inputs", gate.plan_inputs, gate.INPUTS_LINE),
                                  ("Outputs", gate.output_words, gate.OUTPUTS_LINE)):
        was, now = [words(text) or [] for text in plans]
        lines += ["- {}: + {}".format(label, word) for word in now if word not in was]
        lines += ["- {}: - {}".format(label, word) for word in was if word not in now]
        raw = [[squash(line) for line in pattern.findall(text)] for text in plans]
        if raw[0] != raw[1] and was == now:  # the words parse alike (a quoted path, say) but the line differs
            lines.append("- {}: line text changed: `{}` -> `{}`.".format(label, " ".join(raw[0]), " ".join(raw[1])))
    for label, name in (("Validation bindings", "validation-bindings"), ("Exact execution", "exact-execution")):
        was, now = [plan_blocks(text, name) for text in plans]
        if was != now:
            lines.append("- {}: {} (raw block text compared, not interpreted).".format(
                label, "added" if not was else "removed" if not now else "changed"))
    config = gate.load_config(root)
    was, now = [sum(gate.plan_grants(root, text, config), []) for text in plans]
    lines += ["- Scope: + {}".format(word) for word in now if word not in was]
    lines += ["- Scope: - {}".format(word) for word in was if word not in now]
    if len(lines) == 2:
        lines.append("No plan-table row, objective, `Inputs:`, `Outputs:`, binding block or scope changed.")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- multiplicity

def multiplicity(root, digest):
    """Everything tried before plan `digest` was settled: earlier approved plans that name one of
    its scripts or outputs, and every run of those scripts or in its analysis folder, up to the
    plan's last run. Counts and records only, from receipts and approvals; no sacct."""
    config = gate.load_config(root)
    folder = gate.state_path(root, "approvals")
    approvals = {}
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not name.endswith(".json"):
            continue
        record = read_approval(os.path.join(folder, name))
        if record:
            approvals[record.get("hash", name[:8])] = record
    if digest not in approvals:
        sys.exit("verify: no approved plan {}. Run `list` to see approved plans.".format(digest))

    def scripts(record):
        table = gate.plan_table(record.get("plan", ""), every_cell=True)
        return {p for p in gate.plan_paths_in(root, table) if gate.gated_rel(root, root, p, config)}

    def outputs(record):
        return {w.rstrip("/") for w in plan_outputs(record.get("plan", "")) or []}

    selected = approvals[digest]
    receipts = [r for r in read_jsonl(gate.state_path(root, "receipts.jsonl"))
                if is_run(root, r, config["gated_commands"])]
    mine, start = plan_runs(receipts, digest, selected.get("approved_at", 0))
    named, made = scripts(selected), outputs(selected)
    revisions = sorted((r for h, r in approvals.items() if h != digest and r.get("approved_at", 0) < start
                        and (scripts(r) & named or outputs(r) & made)), key=lambda r: r.get("approved_at", 0))
    analysis_dir = guess_analysis_dir(sorted(named))
    end = mine[-1]["ts"] if mine else start
    runs = [r for r in receipts if r.get("ts", 0) <= end and any(
        p in named or (analysis_dir and under(p, analysis_dir)) for p in ran_paths(root, r))]
    code = {}  # the code version of each script as this plan last ran it
    for r in mine:
        script = r.get("script") or {}
        if script.get("sha256"):
            code[script.get("path")] = script["sha256"]

    rows, counts = [], collections.Counter()
    previous = None
    for record in revisions + [selected]:
        changes = plan_changes(previous, record.get("plan", "")) if previous is not None else None
        choice = [c for c in changes or [] if c[1] == "choice"]
        detail = ["step {} choice: `{}` -> `{}`".format(k, was, now) for k, _, was, now in choice]
        if changes and len(changes) > len(choice):
            detail.append("{} other cell(s) changed".format(len(changes) - len(choice)))
        if changes is None:
            detail = ["first plan"]
        elif not changes:
            detail = ["no plan-table change"]
        if record is selected:
            detail.insert(0, "approved (selected)")
        counts["choice changed"] += bool(choice)
        rows.append({"ts": start if record is selected else record.get("approved_at", 0),
                     "what": "plan " + record.get("hash", "?"),
                     "detail": "; ".join(detail), "exit": ""})
        previous = record.get("plan", "")
    for r in runs:
        plans = r.get("plans") or []
        if r.get("explore"):
            what = "explore run"
            counts["explore before" if r["ts"] < start else "explore after"] += 1
        elif digest in plans:
            what = "run"
            counts["mine"] += 1
        elif r.get("approvals_unread"):
            what = "run (plans not read)"
            counts["unread"] += 1
        elif plans and plans[-1] not in approvals:  # moved out of approvals/, as the gate's timeout advice says
            what = "run (plan {}, approval not on file)".format(plans[-1])
            counts["unfiled"] += 1
        elif plans:
            what = "run (plan {})".format(plans[-1])
            counts["other plans"] += 1
        else:
            what = "run (no plan)"
            counts["no plan"] += 1
        script = r.get("script") or {}
        marker = ""
        if script.get("path") in code:
            if not script.get("sha256"):
                marker = " (code version unknown)"
            elif script["sha256"] != code[script["path"]]:
                marker = " (other code version)"
        status = r.get("exit_status")
        shown = ("job " + str(r["job_id"]) if r.get("job_id") else str(status)
                 if isinstance(status, int) or status in ("failed", "interrupted") else "not recorded")
        rows.append({"ts": r["ts"], "what": what, "detail": "`{}`{}".format(r.get("command", ""), marker),
                     "exit": shown})
    rows.sort(key=lambda row: row["ts"])
    return {"plan": digest, "analysis_dir": analysis_dir, "revisions": len(revisions),
            "counts": dict(counts), "rows": rows}


def render_multiplicity(result):
    c = result["counts"]
    line = ("{} earlier plan revision(s), {} explore run(s) before the approval, {} run(s) under earlier "
            "plans, {} run(s) under this plan.".format(result["revisions"], c.get("explore before", 0),
                                                       c.get("other plans", 0), c.get("mine", 0)))
    extra = [(c.get("explore after"), "explore run(s) after the approval"),
             (c.get("no plan"), "run(s) with no approved plan"),
             (c.get("unread"), "run(s) whose approvals were not read (time limit), so their plan is a gap"),
             (c.get("unfiled"), "run(s) under a plan whose approval is not on file (gap)")]
    line += "".join(" {} {}.".format(n, text) for n, text in extra if n)
    if result["revisions"]:
        line += " {} of {} plan change(s) edited a Choice cell.".format(c.get("choice changed", 0),
                                                                       result["revisions"])
    lines = ["# Multiplicity: plan {}".format(result["plan"]), "", line, "",
             "| When | What | Detail | Exit |", "|---|---|---|---|"]
    lines += ["| {} | {} | {} | {} |".format(when(r["ts"]), r["what"], cell(r["detail"]), r["exit"])
              for r in result["rows"]]
    lines += ["", "Earlier plans count as revisions when they name one of this plan's scripts or outputs. "
                  "Runs are matched by the scripts they ran{}; receipts do not record which files a run "
                  "wrote. A value changed inside a script shows only as another code version. Explore runs "
                  "of inline code (`python -c`) are not recorded.".format(
                      " (this plan's, or any in `{}/`)".format(result["analysis_dir"])
                      if result["analysis_dir"] else "")]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- runs

RUN_NAME = re.compile(r"^run_(\d{8})_(.+)$")
STATE_WORDS = re.compile(r"final|complete|smoke|latest|current|review", re.IGNORECASE)
RUN_STATUS = ("current", "side", "superseded", "scratch", "failed")
RUN_KIND = ("model", "data", "seed", "code-fix", "rerun", "sensitivity", "figures-only", "smoke")


def parse_label(text):
    """({key: value}, {key: line}, [(line or None, problem)]) from a run label. The header ends at the first
    blank line after a key; what follows is free text and is never read. Unknown keys are kept, not flagged."""
    fields, lines, problems, seen = {}, {}, [], False
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("#"):
            continue
        if not line.strip():
            if seen:
                break
            continue
        seen = True
        key, colon, value = line.partition(":")
        if not colon or not re.match(r"^[a-z_]+$", key.strip()):
            problems.append((number, "not a `key: value` line"))
            continue
        fields[key.strip()] = value.strip()
        lines[key.strip()] = number
    for key, allowed in (("status", RUN_STATUS), ("kind", RUN_KIND)):
        if key in fields and fields[key] not in allowed and fields[key] != "-":
            problems.append((lines[key], "`{}: {}` is not one of {}".format(key, fields[key], " | ".join(allowed))))
    if "version" in fields and fields["version"] != "-" and not fields["version"].isdigit():
        problems.append((lines["version"], "`version` is not a whole number"))
    if "status" not in fields:
        problems.append((None, "no `status:` line"))
    return fields, lines, problems


def scan_run(path):
    """(newest file mtime or 0, 8-hex id) of a run folder. RUN.txt is left out of both, because labelling a run
    must not change when it was updated or which run it is; the folder's own mtime is never used."""
    entries, newest = [], 0
    for folder, dirs, names in os.walk(path):
        for name in names + [d for d in dirs if os.path.islink(os.path.join(folder, d))]:
            full = os.path.join(folder, name)
            rel = os.path.relpath(full, path).replace(os.sep, "/")
            try:
                info = os.lstat(full)
            except OSError:
                continue
            if rel != "RUN.txt":
                entries.append((rel, info.st_size))
                newest = max(newest, info.st_mtime)
    text = "\n".join("{}\t{}".format(rel, size) for rel, size in sorted(entries))
    return newest, hashlib.sha256(text.encode("utf-8", "surrogateescape")).hexdigest()[:8]


def label_run(path):
    """One run folder as a dict: its label (inside RUN.txt, else the sibling `<run>.RUN.txt`), newest mtime, id."""
    name = os.path.basename(path)
    inside, sibling = os.path.join(path, "RUN.txt"), path + ".RUN.txt"
    source = "inside" if os.path.isfile(inside) else "sibling" if os.path.isfile(sibling) else None
    fields, lines, problems = parse_label(read_text(inside if source == "inside" else sibling)) if source \
        else ({}, {}, [])
    if fields.get("run") and fields["run"] != name:
        problems.append((lines["run"], "the label names `{}`, not this folder".format(fields["run"])))
    newest, digest = scan_run(path)
    return {"run": name, "path": path, "label": source, "fields": fields, "problems": problems, "epoch": newest,
            "updated": when(newest) if newest else "-", "id": digest,
            "status": fields.get("status") or ("-" if source else "unlabelled")}


def run_order(run):
    """Version, `_vNN` suffix, date: how the user's convention orders two runs of one slug."""
    version = run["fields"].get("version", "")
    suffix = re.search(r"_v(\d+)$", run["run"])
    return (int(version) if version.isdigit() else 0, int(suffix.group(1)) if suffix else 0,
            RUN_NAME.match(run["run"]).group(1), run["run"])


def run_findings(base, results, runs, pointers):
    found = []

    def add(severity, run, text):
        found.append({"severity": severity, "run": run, "text": text})

    for run in runs:
        name, fields = run["run"], run["fields"]
        if not run["label"]:
            add("gap", name, "no label: neither `{0}/RUN.txt` nor `{0}.RUN.txt` exists.".format(name))
        elif run["label"] == "sibling":
            add("info", name, "labelled by the sibling file `{}.RUN.txt` (a frozen run).".format(name))
        for number, problem in run["problems"]:
            add("gap", name, "malformed label{}: {}.".format(" (line {})".format(number) if number else "", problem))
        if STATE_WORDS.search(name):
            add("info", name, "the name has a state word ({}); state belongs in the label, not the name.".format(
                ", ".join(sorted(set(w.lower() for w in STATE_WORDS.findall(name))))))
        target = fields.get("superseded_by", "-")
        if target != "-" and not os.path.isdir(os.path.join(results if "/" not in target else base, target)):
            add("gap", name, "superseded_by `{}` does not exist.".format(target))
        for entry in [e.strip() for e in fields.get("reads", "-").split(",") if e.strip() not in ("", "-")]:
            if not any(os.path.isdir(os.path.join(root, entry)) for root in (base, results)):  # labels write both
                add("gap", name, "reads `{}`, which does not exist.".format(entry))
    for name, target in pointers:
        if not os.path.exists(os.path.join(results, name)):
            add("gap", name, "points to `{}`, which does not exist.".format(target))
    groups = collections.defaultdict(list)
    for run in runs:
        if run["status"] == "current":
            groups[(re.sub(r"_v\d+$", "", RUN_NAME.match(run["run"]).group(2)), run["fields"].get("kind", "-"))].append(run)
    for (stem, kind), group in sorted(groups.items()):
        if len(group) > 1:
            group.sort(key=run_order)
            add("suggestion", group[-1]["run"], "{} all say `current` for slug `{}`, kind `{}`; `{}` is the latest, so "
                "the older ones may be superseded. Only you set a status.".format(
                    ", ".join("`{}`".format(r["run"]) for r in group), stem, kind, group[-1]["run"]))
    return found


def run_citations(base, analysis, since):
    """Symlinks under the analysis's data/ and code/ that resolve into a `run_*` folder of another analysis,
    each with that run's label; a dangling link is a gap. `since` is the newest approval's time, or None."""
    here, found = os.path.realpath(analysis), []

    def add(severity, link, text, run=None):
        found.append({"severity": severity, "link": link, "run": run and rel_or_abs(base, run["path"]),
                      "status": run and run["status"], "id": run and run["id"], "text": text})

    for sub in ("data", "code"):
        for folder, dirs, names in os.walk(os.path.join(analysis, sub)):
            dirs.sort()
            for name in sorted(dirs + names):
                path = os.path.join(folder, name)
                if not os.path.islink(path):
                    continue
                link = os.path.relpath(path, analysis).replace(os.sep, "/")
                if not os.path.exists(path):
                    add("gap", link, "dangling: points to `{}`, which does not exist.".format(os.readlink(path)))
                    continue
                parts = os.path.realpath(path).split(os.sep)
                at = [i for i, part in enumerate(parts) if RUN_NAME.match(part)]
                if not at or under(os.sep.join(parts[:at[0] + 1]), here):
                    continue
                run = label_run(os.sep.join(parts[:at[0] + 1]))
                fields, status = run["fields"], run["status"]
                if not run["label"]:
                    add("gap", link, "the cited run has no label.", run)
                elif status not in RUN_STATUS:
                    add("gap", link, "the cited run's label has no usable status.", run)
                elif status == "superseded":
                    add("gap", link, "the cited run is superseded (by {}).".format(fields.get("superseded_by", "-")), run)
                elif status in ("failed", "scratch"):
                    add("gap", link, "the cited run is {}.".format(status), run)
                else:
                    add("info", link, "the cited run is {}.".format(status), run)
                if since and run["epoch"] > since:
                    add("info", link, "the cited run changed {}, after the newest approval ({}).".format(
                        run["updated"], when(since)), run)
    return found


def list_runs(base, gated, path):
    """The runs in a results folder and the cross-folder citations of its analysis. Read-only."""
    plans = approved_plans(base) if gated else []
    if path is None:
        if not plans:
            sys.exit("verify: no approval names an analysis folder here; pass the results folder: verify runs PATH")
        newest = max(plans, key=lambda p: p[0])
        rel = guess_analysis_dir(newest[2])
        if not rel:
            sys.exit("verify: the newest approval ({}) names no analysis folder; pass the results folder: "
                     "verify runs PATH".format(newest[1]))
        results = os.path.join(base, rel, "results")
    else:
        results = os.path.abspath(path)
        if not gated:  # labels name other runs from the project root: the repository the results folder is in
            top = gate.git(results if os.path.isdir(results) else os.path.dirname(results), "rev-parse", "--show-toplevel")
            base = top.strip() if top else base
    if not os.path.isdir(results):
        sys.exit("verify: {} is not a folder; pass the analysis's results folder: verify runs PATH".format(
            rel_or_abs(base, results)))
    analysis = os.path.dirname(results)
    mine = [p[0] for p in plans if guess_analysis_dir(p[2]) == os.path.relpath(analysis, base)]
    names = sorted(os.listdir(results))
    pointers = [(n, os.readlink(os.path.join(results, n))) for n in names if os.path.islink(os.path.join(results, n))]
    found = [label_run(os.path.join(results, n)) for n in names
             if RUN_NAME.match(n) and not os.path.islink(os.path.join(results, n))
             and os.path.isdir(os.path.join(results, n))]
    return {"results": rel_or_abs(base, results), "runs": found, "pointers": pointers,
            "findings": run_findings(base, results, found, pointers),
            "citations": run_citations(base, analysis, max(mine) if mine else None)}


def render_runs(result):
    lines = ["# Runs in `{}`".format(result["results"]), ""]
    if result["runs"]:
        lines += ["| Run | Version | Kind | Status | Updated | Id | Why |", "|---|---|---|---|---|---|---|"]
        for r in result["runs"]:
            f, why = r["fields"], r["fields"].get("why", "-")
            lines.append("| {} | {} | {} | {} | {} | {} | {} |".format(
                r["run"], f.get("version", "-"), f.get("kind", "-"), r["status"],
                r["updated"], r["id"], cell(why if len(why) <= 60 else why[:57] + "...")))
    else:
        lines.append("No `run_<YYYYMMDD>_<slug>` folders here.")
    if result["pointers"]:
        lines += [""] + ["`{}` -> `{}` (a pointer, not a run)".format(n, t) for n, t in result["pointers"]]
    lines += ["", "## Findings", ""]
    lines += ["- {} `{}`: {}".format(f["severity"], f["run"], f["text"]) for f in result["findings"]] or ["None."]
    lines += ["", "## Citations", ""]
    lines += ["- {} `{}`{}: {}".format(c["severity"], c["link"], " -> `{}` ({}, id {})".format(
        c["run"], c["status"], c["id"]) if c["run"] else "", c["text"]) for c in result["citations"]] \
        or ["No symlink in `data/` or `code/` points into another analysis's run."]
    lines += ["", "Status is only ever set by you in the label; a suggestion is not a status. Nothing was written."]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- decision trace (DT-1)

TRACE_LIMITS = [
    "Interpretation: declared, observed and check-result evidence shown; scientific correctness not determined "
    "(that is review).",
    "Not traced: modules and helpers the scripts import (only named scripts are pinned); findings stay in "
    "`report`, not attached to rows."]


def trace_hits(root, r, rows, declared, validation):
    """The indexes of the plan rows one receipt names, from the strongest source that names any: the exact-execution
    step it matched, the row of the validation check it ran, then the Step cells that declare a script or folder it
    ran (a command only when it ran no path). Never a filename likeness, a time, or a Slurm submit line."""
    if r.get("exact_match") is True and r.get("exact_step") is not None:
        hits = [i for i, row in enumerate(rows) if row["num"] == str(r["exact_step"])]
        if hits:
            return hits
    if r.get("validation_check"):
        wanted = [str(v["plan_row"]) for v in validation if v["id"] == r["validation_check"]]
        hits = [i for i, row in enumerate(rows) if row["num"] in wanted]
        if hits:
            return hits
    ran = set(ran_paths(root, r))
    if not ran:
        return [i for i, d in enumerate(declared) if r.get("kind") in d["commands"]]
    return [i for i, d in enumerate(declared)
            if ran & d["scripts"] or any(under(p, f) for p in ran for f in d["folders"])]


def trace_attempt(r, jobs=None):
    """One attempt in words: its id, time, launch label (observed only for a matched launch) and outcome, including
    the state sacct reports for a Slurm job, so a failed job reads failed here as it does in `report`."""
    kind = launch_kind(r)
    label = "observed: matched launch" if kind == "matched" else "unresolved: launch link not recorded (legacy)" \
        if kind == "legacy" else "unresolved: {} launch".format(kind)
    return "attempt {} at {} [{}]; {}{}".format(
        r.get("attempt_id") or "with no attempt id", when(r.get("ts")), label, attempt_state(r, jobs or {})[1],
        "; ran check `{}`".format(r["validation_check"]) if r.get("validation_check") else "")


def trace_jobs(result, sacct):
    """The Slurm states the trace needs: one `sacct` call per job the plan's own receipts submitted. Read-only,
    and only reached by `--trace`, so `report` and `--json` keep their output and their call pattern."""
    jobs = {}
    for r in result["receipts"]:
        if r.get("job_id") and r["job_id"] not in jobs:
            jobs[r["job_id"]] = sacct_state(sacct, r["job_id"], r.get("ts") or time.time())
    return jobs


def render_trace(root, result, wanted=None, sacct="sacct"):
    """The decision trace: each plan row with what is declared for it, the attempts that ran it, its bound checks'
    results and its supported outputs, every edge labelled with its source. Read-only: it reads `result`, saves
    nothing, and a link it cannot establish stays `unlinked` or `cannot map`. It never says a choice was implemented."""
    digest, chosen = result["hash"], result["instance"]["selected"]
    jobs = trace_jobs(result, sacct)
    head = "# Decision trace: plan {}, {}{}".format(
        digest, "approval instance " + chosen if chosen else "a legacy approval (no instance id)",
        "; {} run(s) under other approval instances are not shown".format(sum(result["instance"]["history"].values()))
        if result["instance"].get("history") else "")
    rows = gate.plan_rows(result["plan"])
    if rows is None:
        return "\n".join([head, "", "No step table (a Step column with a Choice or Validation column): nothing to "
                          "trace by row.", ""] + TRACE_LIMITS) + "\n"
    record = (load_instance(root, digest, chosen) if chosen else None) or read_approval(
        gate.state_path(root, "approvals", digest + ".json")) or {}
    steps = (record.get("execution") or {}).get("steps") or []
    counts = collections.Counter(r["num"] for r in rows)
    problem = ["row ID {} repeats".format(r["num"]) if counts[r["num"]] > 1 else "row has no ID" if r["id"] == "" else None
               for r in rows]
    names = {s["path"] for s in result["scripts"]}
    declared = []
    for r in rows:
        named = gate.plan_paths_in(root, r["step"])
        declared.append({"scripts": named & names, "folders": [f for f in result["folders"] if f in named],
                         "commands": [c for c in result["commands"] if gate.names_command(c, r["step"])],
                         "mentioned": (gate.plan_paths_in(root, r["choice"] + " " + r["check"]) & names) - named})
    attempts, unlinked = collections.defaultdict(list), []
    for r in (x for x in result["receipts"] if not x.get("not_a_run")):
        hits = trace_hits(root, r, rows, declared, result["validation"])
        bad = [problem[i] for i in hits if problem[i]]
        if len(hits) == 1 and not bad:
            attempts[hits[0]].append(r)
        else:
            unlinked.append((r, "cannot map: " + bad[0] if bad else
                             "matches rows " + ", ".join(rows[i]["num"] for i in hits) if hits
                             else "no row's Step cell names what it ran"))
    ids = [{r["attempt_id"] for r in attempts[i] if r.get("attempt_id")} for i in range(len(rows))]
    owned, loose = collections.defaultdict(list), []
    for o in result["outputs"]:
        owner = [i for i in range(len(rows)) if o.get("producer_attempt") and o["producer_attempt"] in ids[i]]
        if o["strength"] == "supported" and len(owner) == 1:
            owned[owner[0]].append(o)
        else:
            loose.append("`{}` [{}]: {}".format(o["path"], o["strength"], "producer attempt not linked to one row"
                                                if o["strength"] == "supported" else cut(o["reason"] or "no reason recorded")))

    # Each of these returns [(full text, short text)] for one row: the detail view shows the first, the table the second.
    def implementation(i):
        d, found = declared[i], []
        for path in sorted(d["scripts"]):
            pin = approved_script_pin(root, digest, record, path)
            how = "pinned sha256 " + pin["sha256"][:12] if pin.get("sha256") else "not pinned" + (
                " ({})".format(gate.method(pin)) if pin else "")
            frozen = not next(s for s in result["scripts"] if s["path"] == path).get("unfrozen")
            found.append(("`{}` [declared; {}{}]".format(path, how, "" if frozen else "; ran code no approval froze"),
                          "`{}`".format(path)))
        return found + [("folder `{}/` [declared]".format(f), "`{}/`".format(f)) for f in d["folders"]] + [
            ("command `{}` [declared]".format(c), "`{}`".format(c)) for c in d["commands"]]

    def validation(i):
        checks = [v for v in result["validation"] if str(v["plan_row"]) == rows[i]["num"]]
        if checks:
            return [("`{}` [declared binding, {}, defined_by {} (not verified); check result: {}{}]{}".format(
                v["id"], "required" if v["required"] else "optional", v["defined_by"], v["outcome"],
                ", attempt " + v["attempt_id"] if v.get("attempt_id") else "",
                "; a pass is the check's own claim, not proof the choice is right" if v["outcome"] == "passed"
                else ": " + cut(v["reason"] or "")), "`{}` check result: {}".format(v["id"], v["outcome"]))
                for v in checks]
        if gate.prose_check(rows[i]["check"]):
            return [("no executable check bound (the cell is prose); the choice is not established by a check",
                     "no executable check bound")]
        return [("not checked (the row names no check)", "not checked")]

    def output(i):
        if owned[i]:
            return [("`{}` [observed: producer supported, attempt {}]".format(o["path"], o["producer_attempt"]),
                     "`{}`".format(o["path"])) for o in owned[i]]
        text = "not applicable (Outputs: none)" if result["outputs_named"] == [] else \
            "not declared (no Outputs: line)" if result["outputs_named"] is None else "none linked to this row"
        return [(text, text.split(" (")[0])]

    lines = [head, ""]
    if wanted is None:
        lines += ["| Row | Choice | Declared | Check | Attempts | Output |", "|---|---|---|---|---|---|"]
        for i, r in enumerate(rows):
            if problem[i]:
                lines.append("| {} | {} | cannot map: {} | - | - | - |".format(
                    cell(r["num"]), cell(cut(r["choice"], 50)), problem[i]))
                continue
            made = attempts[i]
            lines.append("| {} | {} | {} | {} | {} | {} |".format(
                cell(r["num"]), cell(cut(r["choice"], 50)),
                cell(cut(", ".join(short for _, short in implementation(i)) or "none named", 60)),
                cell(cut("; ".join(short for _, short in validation(i)), 60)),
                "{} ({} matched launch{})".format(
                    len(made), sum(launch_kind(x) == "matched" for x in made),
                    "".join("; {} {}".format(n, k) for k, n in sorted(collections.Counter(
                        attempt_state(x, jobs)[0] for x in made if attempt_state(x, jobs)[0] != "ok").items())))
                if made else "none", cell(cut(", ".join(short for _, short in output(i)), 50))))
        lines.append("")
        shown = len(lines)
        if unlinked:
            lines += ["Attempts not linked to a row: {}".format(len(unlinked))] + [
                "- {}: {}".format(trace_attempt(r), why) for r, why in unlinked[:3]] + (
                ["- and {} more".format(len(unlinked) - 3)] if len(unlinked) > 3 else [])
        if loose:
            lines += ["Outputs not linked to a row:"] + ["- " + x for x in loose[:SHOWN_OUTPUTS]] + (
                ["- ... and {} more".format(len(loose) - SHOWN_OUTPUTS)] if len(loose) > SHOWN_OUTPUTS else [])
        orphans = sorted(names - set().union(*[d["scripts"] for d in declared]))
        if orphans:
            lines.append("Scripts named in no Step cell (mentioned, not declared): "
                         + ", ".join("`{}`".format(p) for p in orphans))
        lines += [""] * (len(lines) > shown) + ["Detail: report {} --trace <row>{}".format(
            digest, " --instance " + chosen if chosen else ""), ""]
    else:
        picked = [i for i, r in enumerate(rows) if r["num"] == wanted]
        if not picked:
            sys.exit("verify: plan {} has no row {} (rows: {}).".format(
                digest, wanted, ", ".join(r["num"] for r in rows)))
        for i in picked:
            r = rows[i]
            lines.append("Row {}: {}".format(r["num"], cut(r["choice"], 200) or "(no Choice cell)"))
            if problem[i]:
                lines += ["  cannot map: {}; nothing is linked to this row.".format(problem[i]), ""]
                continue
            exact = ["`{}` in {} [declared; operational flags: {}]".format(
                " ".join(s["argv"]), s["cwd"], ", ".join(s["operational"]) or "none")
                for s in steps if str(s["row"]) == r["num"]] or ["none declared (broad grant)"]
            recovered = ["{} attempts listed; no failure followed by a success".format(len(e["attempts"]))
                         if e["verdict"] is None else "equivalent retry" if e["verdict"] == "equivalent"
                         else "equivalence not established ({})".format(e["verdict"])
                         for e in result["recovery"]
                         if ids[i] & {a["attempt_id"] for a in e["attempts"] if a.get("attempt_id")}]
            fields = [("Approved choice", ["{} [declared; source: {}]".format(cut(r["choice"], 200), cut(r["source"], 60) or "none")]),
                      ("Declared implementation", [full for full, _ in implementation(i)]
                       or ["none named in this row's Step cell"]),
                      ("Mentioned only", ["`{}` [mentioned in Choice or Validation, not a declared step]".format(p)
                                          for p in sorted(declared[i]["mentioned"])]),
                      ("Exact command", exact), ("Validation", [full for full, _ in validation(i)]),
                      ("Observed launch", [trace_attempt(x, jobs) for x in attempts[i]]
                       or ["not observed (no run of this row under " + ("instance " + chosen if chosen else "this approval") + ")"]),
                      ("Recovery", recovered), ("Output", [full for full, _ in output(i)])]
            for label, items in fields:
                for n, item in enumerate(items):
                    lines.append("  {}: {}".format(label if n == 0 else " " * len(label), item))
            lines.append("")
        if unlinked or loose:
            lines += ["{} attempt(s) and {} output(s) of the plan are linked to no row: `report {} --trace`.".format(
                len(unlinked), len(loose), digest), ""]
    qualified = (result.get("qualification") or {}).get("overall")
    lines.append("Whole-plan verify status: {}{}. A row here is evidence, not a status; failures and open gaps: "
                 "`report {}`.".format(result["status"], "; qualification: " + qualified if qualified else "", digest))
    return "\n".join(lines + [""] + TRACE_LIMITS) + "\n"


def main(argv):
    parser = argparse.ArgumentParser(prog="verify")
    parser.add_argument("--plugin-root", required=True)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--sacct", default="sacct")
    parser.add_argument("--scilintr", help="default: the path in tools.json, else `scilintr` on PATH")
    parser.add_argument("--rscript", help="default: the path in tools.json, else `Rscript` on PATH")
    parser.add_argument("--hash-mb", type=float, default=2000)
    parser.add_argument("--seconds", type=float, default=120)
    parser.add_argument("action", choices=["list", "report", "write", "stale", "status", "diff", "explore",
                                           "multiplicity", "runs", "refs", "disclose"])
    parser.add_argument("hash", nargs="?")
    parser.add_argument("new_hash", nargs="?")
    parser.add_argument("--sha", help="refs: the SHA256 (or at least 8 hex) of the file that was wrong")
    parser.add_argument("--analysis-dir")
    parser.add_argument("--instance", help="report/write: check this approval instance (16 hex, or a unique prefix) "
                        "instead of the newest one in approvals/<hash>.json; see `report` for the instances of its runs")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--claims", action="append", default=[],
                        help="report/write: also check this document's claims block (repeatable)")
    parser.add_argument("--session", help="explore: this session's runs (default: $CLAUDE_CODE_SESSION_ID)")
    parser.add_argument("--all", action="store_true", help="explore: every session's runs, last 7 days")
    parser.add_argument("--content", action="store_true",
                        help="stale: compare each output's content with the SHA256 verify saved (default: size and time)")
    parser.add_argument("--require-reportable", action="store_true",
                        help="report/write: exit 3 and name the dimension unless the run is qualified for reporting")
    parser.add_argument("--resolve-citations", action="store_true",
                        help="report/write/disclose: resolve each DOI, PMID and arXiv ID over the network "
                             "(Crossref, NCBI, arXiv). Offline is the default, and is a gap, not a pass")
    parser.add_argument("--contact", help="--resolve-citations: an email address to send to Crossref and NCBI, "
                        "as both ask for one; omitted unless you configure it")
    parser.add_argument("--trace", nargs="?", const="", metavar="ROW",
                        help="report: the decision trace, one line per plan row, or one row's evidence links with ROW "
                        "(put the hash first: `report <hash> --trace [ROW]`). A text view; nothing is written")
    args = parser.parse_args(argv)
    if args.trace is not None and (args.action != "report" or args.json):
        sys.exit("verify: --trace is a text view of report only (not --json, write or the other actions); nothing was written.")
    if args.json and args.action == "disclose":
        sys.exit("verify: `disclose` prints a plain-text draft to edit; it has no --json form.")
    load_gate(args.plugin_root)
    root = gate.find_root(os.path.abspath(args.repo))
    if args.action in ("stale", "status"):  # committed provenance suffices, so no gate needed
        top = gate.git(os.path.abspath(args.repo), "rev-parse", "--show-toplevel")
        base = root or (top.strip() if top else os.path.abspath(args.repo))
        if args.action == "stale":
            result = stale(base, args.hash_mb, args.seconds, args.content)
            sys.stdout.write(json.dumps(result, indent=1) + "\n" if args.json else render_stale(result))
        else:
            rows = status(base, args.hash_mb, args.seconds)
            sys.stdout.write(json.dumps(rows, indent=1) + "\n" if args.json else render_status(rows))
        return 0
    if args.action == "refs":  # the positional after the action is the file's path; read-only, no gate needed
        if not args.hash or (args.sha and not re.fullmatch(r"[0-9a-fA-F]{8,64}", args.sha)):
            sys.exit("verify: `refs` needs the path of the file, and --sha (8 to 64 hex digits) when you have it.")
        top = gate.git(os.path.abspath(args.repo), "rev-parse", "--show-toplevel")
        result = refs(root or (top.strip() if top else os.path.abspath(args.repo)), args.hash, args.sha)
        sys.stdout.write(json.dumps(result, indent=1) + "\n" if args.json else render_refs(result))
        return 0
    if args.action == "runs":  # RESULTS_DIR is the positional after the action; no gate needed when it is given
        top = gate.git(os.path.abspath(args.repo), "rev-parse", "--show-toplevel")
        result = list_runs(root or (top.strip() if top else os.path.abspath(args.repo)), bool(root), args.hash)
        sys.stdout.write(json.dumps(result, indent=1) + "\n" if args.json else render_runs(result))
        return 0
    if root is None:
        sys.exit("verify: the approval gate is not on in this repository (no gate.json found).")
    if args.action == "explore":
        session = None if args.all else args.session or os.environ.get("CLAUDE_CODE_SESSION_ID")
        scope = "session {}".format(session) if session else "all sessions, last {} days{}".format(
            EXPLORE_DAYS, "" if args.all else "; no session ID found, so every session is shown")
        runs = explore_runs(root, session, args.hash_mb, args.seconds)
        sys.stdout.write(json.dumps(runs, indent=1) + "\n" if args.json else render_explore(runs, scope))
        return 0
    if args.action == "list":
        sys.stdout.write(list_plans(root))
        return 0
    if not args.hash or not re.match(r"^[0-9a-f]{8}$", args.hash):
        sys.exit("verify: give the plan's 8-character hash (see `list`).")
    if args.action == "diff":
        if not args.new_hash or not re.match(r"^[0-9a-f]{8}$", args.new_hash):
            sys.exit("verify: `diff` needs the old and the new plan's 8-character hashes (see `list`).")
        sys.stdout.write(diff_plans(root, args.hash, args.new_hash))
        return 0
    if args.action == "multiplicity":
        result = multiplicity(root, args.hash)
        sys.stdout.write(json.dumps(result, indent=1) + "\n" if args.json else render_multiplicity(result))
        return 0
    if args.action == "write" and not args.analysis_dir:
        sys.exit("verify: `write` needs --analysis-dir, confirmed by the user.")
    recorded = gate.lint_tools(root)
    result = check(root, args.hash, args.analysis_dir, args.sacct, args.hash_mb, args.seconds,
                   args.scilintr or recorded[0], args.rscript or recorded[1], args.claims, args.instance,
                   args.resolve_citations, args.contact)
    result["qualification"] = qualify(root, result)
    result["rerun"] = rerun_evidence(root, result)
    if args.action == "disclose":  # read-only: a draft for the researcher to edit, never written
        sys.stdout.write(render_disclosure(root, result))
        return 0
    refusal = reportable_error(result) if args.require_reportable else None
    if args.action == "write":
        if result["instance"]["selected"] != result["instance"]["current"]:
            sys.exit("verify: `write` records the current approval instance ({}); a bundle is keyed by the plan hash, "
                     "so writing an earlier instance would replace it. Use `report --instance` to read an earlier "
                     "freeze.".format(result["instance"]["current"]))
        written = write(root, result)
        for path in written:
            print("wrote " + path)
        if gate.git(root, "check-ignore", "-q", written[0]) is not None:
            print("warning: git ignores {}, so these files will not be committed with the analysis."
                  .format(os.path.dirname(written[0])))
        print("Verify status: " + result["status"])
        print("Qualification: " + result["qualification"]["overall"])
        if refusal:  # the record is saved either way: it says what was and was not established
            sys.stderr.write(refusal + "\n")
            return 3
        return 0
    if args.trace is not None:
        sys.stdout.write(render_trace(root, result, args.trace or None, args.sacct))
    elif args.json:
        shown = dict(result, plan=None, receipts=len(result["receipts"]))
        sys.stdout.write(json.dumps(shown, indent=1, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render(result))
    if refusal:
        sys.stderr.write(refusal + "\n")
        return 3
    return 0


if __name__ == "__main__":
    if sys.stdout.encoding.lower().replace("-", "") != "utf8":  # an ASCII locale on Python 3.6
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, sys.stdout.encoding, "backslashreplace")
    sys.exit(main(sys.argv[1:]))
