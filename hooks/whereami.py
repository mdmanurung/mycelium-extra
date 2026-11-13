"""where: a short "what is going on" card for one analysis, shaped for a reader with ADHD.

    where            the full card: aim, state, do next, approach checklist, later, watch out
    where short      the name, then five lines: aim, state, next, then, block
    where all        one line per analysis

Typed as a whole prompt it is answered by the gate hook (needs the gate on); `/mycelium-extra:where` runs it
from the skill. On Claude Code no model call runs; OpenCode passes the card to the model as the rewritten prompt. Every fact comes from files (`code/` or `scripts/`, `outputs/<step>/`, `logs/CHANGES.md`, `plans/TRACKER.md`, the
analysis doc, `provenance/`); nothing is written by a model. The one write is the full card to
`.mycelium-extra/now/<analysis path, "/" as "__">.md`, plugin state outside the analysis and outside git.

    python3 hooks/whereami.py [short|all] [--repo DIR] [--cwd DIR] [--session ID] [--no-write]

Stdlib-only; Python 3.9+.
"""

import glob
import json
import os
import re
import sys
import textwrap
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import analysis_paths as ap  # noqa: E402
import focus  # noqa: E402

CAP = 5  # items per list; the rest is "+N more"
WIDTH = 46
SCRIPT = re.compile(r"^(\d{2}[a-z]?_[^.]+)\.(?:marimo\.py|R|r|py|qmd|Rmd|rmd|ipynb|jl)$")
OPEN_STATUS = ("todo", "in progress", "blocked")
CLOSED_STATUS = ("done", "closed", "complete", "cancel", "drop", "reject", "wontfix", "wont", "won't", "resolved")
LOOSE_OK = ("numbers.json",)  # a file Mycelium's register_value writes directly in outputs/
VERB = re.compile(r"^\s*where(?:\s+am\s+i)?(?:\s+(short|all))?\s*[?.!]?\s*$", re.IGNORECASE)


# ---------------------------------------------------------------- where is the analysis

def locate(root, cwd, session_id=None):
    """Repository-relative path of the analysis: the open focus, else the nearest folder above `cwd` that has a
    `code/` (or Mycelium's `scripts/`) folder and a Snakefile, `plans/` or `outputs/`, or its own `<NAME>.md`
    doc; else None."""
    if session_id:
        try:
            episode = focus.open_episode(focus.read(root, session_id))
        except (focus.FocusError, OSError):
            episode = None
        if episode:
            return episode["analysis_path"]
    path = os.path.realpath(cwd)
    top = os.path.realpath(root)
    while ap.inside(path, top) and path != top:
        if ap.is_analysis(path) and (ap.source_dir(path) is None or ap.find_doc(path) is not None or any(
                os.path.exists(os.path.join(path, n)) for n in ("Snakefile", "plans", "outputs"))):
            return os.path.relpath(path, top)
        path = os.path.dirname(path)
    return None


# ---------------------------------------------------------------- facts

def step_id(step):
    return step["stem"].split("_")[0]


def ago(seconds):
    if seconds < 90:
        return "just now"
    if seconds < 3600:
        return "{} min ago".format(int(seconds // 60))
    if seconds < 48 * 3600:
        return "{} h ago".format(int(seconds // 3600))
    return "{} d ago".format(int(seconds // 86400))


class Budget:
    """A time and file cap for the folder walks of one card, so a huge outputs/ cannot stall the hook."""

    def __init__(self, seconds=1.5, files=5000):
        self.end = time.monotonic() + seconds
        self.cap = files
        self.count = 0
        self.truncated = False

    def exhausted(self):
        return self.count >= self.cap or time.monotonic() > self.end


def mtime_or_zero(path):
    """Modification time of the file or link itself (a broken link or a vanished file gives 0)."""
    try:
        return os.lstat(path).st_mtime
    except OSError:
        return 0.0


def newest(path, budget=None):
    """What a step folder holds, as a dict: `time` and `any` for files outside logs/ (the output), and
    `log_time`, `log_any` and `log_file` for files under the top-level logs/ (Snakemake writes it at job
    start, so it is no sign of output). Stops at the budget and sets `budget.truncated`."""
    budget = budget or Budget()
    found = {"time": 0.0, "any": False, "log_time": 0.0, "log_any": False, "log_file": None}
    if os.path.isfile(path) or os.path.islink(path):
        mtime = mtime_or_zero(path)
        budget.count += 1
        found.update(time=mtime, any=mtime > 0)
        return found
    logs = os.path.join(path, "logs")
    for here, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        in_logs = here == logs or here.startswith(logs + os.sep)
        for name in files:
            if name.startswith("."):
                continue
            if budget.exhausted():
                budget.truncated = True
                return found
            budget.count += 1
            full = os.path.join(here, name)
            mtime = mtime_or_zero(full)
            if mtime == 0.0:
                continue  # vanished while walking
            if in_logs:
                found["log_any"] = True
                if mtime >= found["log_time"]:
                    found["log_time"], found["log_file"] = mtime, full
            else:
                found["any"] = True
                found["time"] = max(found["time"], mtime)
    return found


def activity(root, rel):
    """A cheap sign of recent work for `where all`: the newest modification time of outputs/ and the folders
    two levels below it, and of logs/CHANGES.md. No file is listed."""
    folder = os.path.join(root, rel)
    best = mtime_or_zero(ap.change_log(folder) or "")
    top = os.path.join(folder, "outputs")
    best = max(best, mtime_or_zero(top))
    try:
        for step in os.listdir(top):
            path = os.path.join(top, step)
            best = max(best, mtime_or_zero(path))
            if os.path.isdir(path):
                for inner in os.listdir(path):
                    best = max(best, mtime_or_zero(os.path.join(path, inner)))
    except OSError:
        pass
    return best


def benchmark_seconds(folder, stem):
    """Seconds of the step's last run from its Snakemake benchmark, or None."""
    path = os.path.join(folder, "outputs", stem, "logs", stem + ".benchmark.tsv")
    try:
        with open(path, encoding="utf-8") as handle:
            rows = handle.read().splitlines()
        return float(rows[1].split("\t")[0])
    except (OSError, IndexError, ValueError):
        return None


def purpose_of(path):
    """First line under a `## Purpose` heading of the analysis doc, or None."""
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            lines = [handle.readline() for _ in range(120)]
    except (OSError, TypeError):
        return None
    for i, line in enumerate(lines):
        if re.match(r"^#+\s*purpose\b", line, re.IGNORECASE):
            for later in lines[i + 1:i + 8]:
                if later.strip() and not later.lstrip().startswith(("#", "<!--")):
                    return focus._one_line(later)
    return None


def tracker_open(folder):
    """[(id, item, status)] of open rows of plans/TRACKER.md."""
    path = os.path.join(folder, "plans", "TRACKER.md")
    if not os.path.isfile(path):
        return []
    rows = []
    for line in ap.read(path).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) >= 3 and cells[2].lower().startswith(OPEN_STATUS):
            rows.append((cells[0], re.sub(r"[`*]", "", cells[1]), cells[2].split()[0].lower()))
    return rows


def pending_entries(root):
    """The stored grill briefs that have no approval yet, as their text, read once."""
    found = []
    for path in glob.glob(os.path.join(root, ".mycelium-extra", "pending", "*.json")):
        try:
            with open(path, encoding="utf-8") as handle:
                entries = json.load(handle)
        except (OSError, ValueError):
            continue
        for entry in entries if isinstance(entries, list) else []:
            if (isinstance(entry, dict) and entry.get("hash") and "Plan status:" in entry.get("text", "")
                    and not os.path.isfile(os.path.join(root, ".mycelium-extra", "approvals",
                                                        entry["hash"] + ".json"))):
                found.append(entry["text"])
    return found


def pending_plan(rel, texts):
    """True when an unapproved brief names this analysis path (not a longer path that starts with it)."""
    pattern = re.compile(r"(?<![\w-])" + re.escape(rel) + r"(?![\w-])")
    return any(pattern.search(text) for text in texts)


def has_rule(snakefile, stem):
    """False when a Snakefile (its text, read once by the caller) exists but no rule names outputs/<stem>/:
    run.sh would never run that step."""
    return snakefile is None or "outputs/{}/".format(stem) in snakefile


def minute_start(seconds):
    """`seconds` (epoch) cut down to its minute, the resolution of every time stamp verify and run.sh write."""
    return seconds - seconds % 60


def verify_state(folder, now, budget=None, log=None):
    """How current the verify record is, as a dict with `state` ('verified', 'changed', 'interrupted',
    'nonconforming', 'never' or 'unreadable'), `line` (the card text) and `changed` ('code', 'outputs', 'log' or None).
    Reads `provenance/.transactions/pending.json` (existence only) and the last data row of
    `provenance/PROVENANCE.md` (verify replaces a re-verified hash's row and appends, so the last row is
    the newest). A root-level PROVENANCE.md is not the record. Changed means the newest of the last
    CHANGES.md heading, code/ and outputs/ is in a later minute than the Verified cell; the same minute
    counts as verified. A Status cell of DOES_NOT_CONFORM gives 'nonconforming'; CONFORMS_WITH_GAPS is shown on the line. When the shared `budget` ran out, the walks did not see every file, so a
    'verified' line says so. `log` is the newest CHANGES.md heading line, or None."""
    prov = os.path.join(folder, "provenance")
    if os.path.exists(os.path.join(prov, ".transactions", "pending.json")):
        return {"state": "interrupted", "line": "Verify was interrupted.", "changed": None}
    row = None
    try:
        with open(os.path.join(prov, "PROVENANCE.md"), encoding="utf-8", errors="replace") as handle:
            for line in handle:
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if line.startswith("|") and len(cells) >= 4 and cells[0] != "Plan" and not set(cells[0]) <= set("-: "):
                    row = cells
    except OSError:
        pass
    if row is None:
        return {"state": "never", "line": "Never verified.", "changed": None}
    try:
        verified = time.mktime(time.strptime(row[2], "%Y-%m-%d %H:%M"))
    except (ValueError, OverflowError):
        return {"state": "unreadable", "line": "Verify record unreadable.", "changed": None}
    budget = budget or Budget()
    seen = {}
    if log:
        try:
            seen["log"] = time.mktime(time.strptime(log[3:19], "%Y-%m-%d %H:%M"))
        except ValueError:
            pass
    for name in ("code", "scripts", "outputs"):
        seen[name] = newest(os.path.join(folder, name), budget)["time"] if os.path.isdir(os.path.join(folder, name)) else 0.0
    what, when = max(seen.items(), key=lambda kv: kv[1])
    if minute_start(when) > verified:
        return {"state": "changed", "line": "Changed since verify: {}, {}.".format(what, ago(now - when)),
                "changed": what}
    status = row[3].strip() if len(row) > 3 else ""
    line = "Verified {}".format(ago(now - verified))
    if status.upper() in ("DOES_NOT_CONFORM", "CONFORMS_WITH_GAPS"):
        line += ": " + status.upper()
    if budget.truncated:  # the walks stopped early: newer files may exist
        line += "; not every file was checked"
    state = "nonconforming" if "DOES_NOT_CONFORM" in status.upper() else "verified"
    return {"state": state, "line": line + ".", "changed": None}


def numbers_leftovers(folder, entry):
    """Keys of `outputs/numbers.json` whose recorded script file no longer exists. Mycelium's register_value
    writes `{"namespace": ..., "values": [{"key", "value", "provenance", "computed_at": "scripts/x.py:L42"}]}`
    and never deletes a key, so a renamed or removed script leaves its keys behind. The script path is read
    from `computed_at`, relative to the analysis folder. A file of another shape, or an entry without a
    `computed_at`, gives nothing. Report only."""
    path = ap.numbers(folder, entry)
    try:
        if not path or os.path.getsize(path) > 2_000_000:
            return []
        data = json.loads(ap.read(path))
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    values = data.get("values")
    items = values if isinstance(values, list) else [dict(v, key=k) for k, v in data.items() if isinstance(v, dict)]
    left = []
    for item in items:
        site = item.get("computed_at") if isinstance(item, dict) else None
        match = re.fullmatch(r"(.+?):L?\d+(?:-L?\d+)?", site) if isinstance(site, str) else None
        # A caller outside the analysis root (absolute path) or a notebook or stdin (`<stdin>`) has no file here.
        if match and not match.group(1).startswith(("<", "/")) and not os.path.exists(
                os.path.join(folder, match.group(1))):
            left.append(str(item.get("key")))
    return left


def loose_outputs(folder):
    """Names of files directly in `outputs/` when `outputs/.layout` marks the steps layout (`numbers.json` is
    Mycelium's own and is fine). Steps write `outputs/<stem>/`; Mycelium's habit is flat files here."""
    top = os.path.join(folder, "outputs")
    if not ap.layout_marker(top):
        return []
    try:
        names = sorted(os.listdir(top))
    except OSError:
        return []
    return [n for n in names if not n.startswith(".") and n not in LOOSE_OK and os.path.isfile(os.path.join(top, n))]


def where_mycelium(root):
    """True when `<root>/.mycelium-extra/gate.json` has `where_mycelium` true. Read as plain JSON, no gate
    import; anything unreadable is off."""
    try:
        with open(os.path.join(root, ".mycelium-extra", "gate.json"), encoding="utf-8") as handle:
            return json.load(handle).get("where_mycelium") is True
    except (OSError, ValueError, AttributeError):
        return False


def table_rows(path):
    """The data rows of the first markdown table in `path` as dicts keyed by the lower-cased header cells."""
    try:
        lines = ap.read(path).splitlines()
    except OSError:
        return []
    header, rows = None, []
    for line in lines:
        if not line.startswith("|"):
            if header and rows:
                break
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = [c.lower() for c in cells]
        elif not set("".join(cells)) <= set("-: "):
            rows.append(dict(zip(header, cells)))
    return rows


def plain(text):
    """A table cell without backticks, bold marks and link targets."""
    return focus._one_line(re.sub(r"[`*]", "", re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)))


def mycelium_later(root, rel):
    """LATER rows read from Mycelium's registries, only when `where_mycelium` is on: open rows of
    `todo/TODO_REGISTRY.md` that name this analysis path, and the F-IDs of `.living/findings/FINDINGS_REGISTRY.md`
    that the analysis doc cites or whose Topic is the analysis, with their status. Registry files only: no topic
    file, no decisions.md."""
    folder = os.path.join(root, rel)
    named = re.compile(r"(?<![\w-])" + re.escape(rel) + r"(?![\w-])")
    out = []
    for row in table_rows(os.path.join(root, "todo", "TODO_REGISTRY.md")):
        status = (row.get("status") or "").lower()
        if named.search(" ".join(row.values())) and not status.startswith(CLOSED_STATUS):
            out.append("{}: {}{}".format(row.get("id") or "todo", plain(row.get("item") or row.get("title") or ""),
                                         " ({})".format(status) if status else ""))
    doc = ap.find_doc(folder)
    cited = set(re.findall(r"\bF-\d+\b", ap.read(doc))) if doc else set()
    for row in table_rows(os.path.join(root, ".living", "findings", "FINDINGS_REGISTRY.md")):
        fid = plain(row.get("id") or "")
        if fid in cited or plain(row.get("topic") or "") == os.path.basename(rel) or named.search(" ".join(row.values())):
            claim = plain(row.get("claim") or "")
            out.append("{} ({}): {}".format(fid, plain(row.get("status") or "no status"),
                                            claim if len(claim) <= 70 else claim[:67] + "..."))
    return out


def facts(root, rel, budget=None, pending=None, verify=True, mycelium=None):
    """Everything the cards print, as a dict. `budget` caps the folder walks; `pending` is the list from
    `pending_entries`, read once by a caller that builds many cards; `verify` False skips the verify line
    (`where all` does not print it); `mycelium` False skips the opt-in Mycelium LATER rows, None reads the
    `where_mycelium` key of gate.json."""
    folder = os.path.join(root, rel)
    budget = budget or Budget()
    now = time.time()
    entry, _ = ap.current_run(folder)
    layout = entry["layout"] if entry else "none"
    aim, doc = focus.objective_of(root, rel)
    if aim is None or aim.startswith("["):  # a scaffold placeholder is no aim
        aim = purpose_of(os.path.join(root, doc) if doc else None)
    if aim is None or aim.startswith("["):
        aim = "not written: open {}".format(doc or "the analysis doc")
    log = ap.last_change(folder)
    failed = bool(log and log.rstrip().endswith("failed"))
    ran = None
    if log:
        try:
            ran = ago(now - time.mktime(time.strptime(log[3:19], "%Y-%m-%d %H:%M")))
        except ValueError:
            ran = "run time unreadable"

    snake_path = os.path.join(folder, "Snakefile")
    snakefile = ap.read(snake_path) if os.path.isfile(snake_path) else None  # read once, not once per step
    code = ap.source_dir(folder) or os.path.join(folder, "code")  # Mycelium analyses keep their scripts in scripts/
    scripts = sorted(n for n in (os.listdir(code) if os.path.isdir(code) else []) if SCRIPT.match(n))
    steps, marked = [], layout in ("steps", "none")
    since = 0.0  # newest script or upstream output so far: a step older than this is stale
    for name in scripts:
        stem = SCRIPT.match(name).group(1)
        out = os.path.join(folder, "outputs", stem)
        held = newest(out, budget)
        if not held["any"]:  # an older layout kept a rendered page in reports/<stem>*
            for old in glob.glob(os.path.join(folder, "reports", stem + "*")):
                older = newest(old, budget)
                if older["any"]:
                    held.update(any=True, time=max(held["time"], older["time"]))
        script_time = mtime_or_zero(os.path.join(code, name))
        since = max(since, script_time)
        if held["any"]:
            state = "stale" if held["time"] < since else "current"
        elif not held["log_any"] and not has_rule(snakefile, stem):
            state = "unmanaged"
        else:
            state = "todo"
        steps.append({"stem": stem, "script": name, "state": state, "script_time": script_time,
                      "out_time": held["time"], "log_file": held["log_file"],
                      "empty": os.path.isdir(out) and not held["any"] and not held["log_any"],
                      "log_only": held["log_any"] and not held["any"]})
        if held["any"]:
            since = max(since, held["time"])
    if marked and failed:  # a step with only logs was running when the run stopped; else the first unrun step
        stopped = [s for s in steps if s["log_only"]]
        for step in stopped[-1:] or [s for s in steps if s["state"] == "todo"][:1]:
            step["state"] = "failed"
    redo = [s for s in steps if s["state"] in ("todo", "stale", "failed")] if marked else []
    seconds = [benchmark_seconds(folder, s["stem"]) for s in redo]
    minutes = None
    if redo and all(v is not None for v in seconds):
        minutes = max(1, int(sum(seconds) / 60 + 0.99))

    figures = ap.figures(entry) if entry and layout == "steps" else []
    sources = {ap.stem(p) for p in ap.source_data(entry)} if entry and layout == "steps" else set()
    watch = ["figure {} has no source data".format(ap.stem(p)) for p in figures
             if p.lower().endswith(".png") and ap.stem(p) not in sources]
    watch += ["{} has an empty output folder".format(s["stem"]) for s in steps if s["empty"]]
    loose = loose_outputs(folder)
    if loose:
        watch.append("{} loose file{} in outputs/ ({}); steps write outputs/<stem>/".format(
            len(loose), "" if len(loose) == 1 else "s", ", ".join(loose[:3]) + (", ..." if len(loose) > 3 else "")))
    if os.path.isdir(os.path.join(folder, "scripts")) and os.path.isdir(os.path.join(folder, "code")):
        watch.append("scripts/ sits next to code/; steps belong in code/")
    left = numbers_leftovers(folder, entry)
    if left:
        watch.append("numbers.json keys with a missing script: {}{}".format(
            ", ".join(left[:CAP]), " +{} more".format(len(left) - CAP) if len(left) > CAP else ""))

    record = verify_state(folder, now, budget, log) if verify else None
    tracker = tracker_open(folder)
    finished = marked and bool(steps) and not redo and not failed
    if finished:  # scaffold rows such as "S01: code/01_prep.R" stay todo after the step has run
        done = [r for r in tracker if any(s["script"] in r[1] for s in steps if s["state"] == "current")]
        if done:
            tracker = [r for r in tracker if r not in done]
            watch.append("tracker rows {} say open but their steps are current".format(
                ", ".join(r[0] for r in done)))
    nxt = []
    if marked and failed:
        bad = next((s for s in steps if s["state"] == "failed"), None)
        if bad and bad["log_file"]:
            nxt.append("Read " + os.path.relpath(bad["log_file"], folder))
        elif bad:
            nxt.append("Read outputs/{0}/logs/{0}.log".format(bad["stem"]))
        else:
            nxt.append("Read logs/CHANGES.md")
        nxt.append("Fix the cause, then: bash run.sh")
    elif redo:
        nxt.append("bash run.sh")
        shown = [p for p in figures if p.lower().endswith(".png")]
        if shown:
            nxt.append("Open " + os.path.relpath(max(shown, key=mtime_or_zero), folder))
    elif pending_plan(rel, pending_entries(root) if pending is None else pending):
        nxt.append("Type: approve   (a plan for this folder is waiting)")
    elif tracker:
        nxt.append("{}: {}".format(tracker[0][0], tracker[0][1]))
    elif marked and steps and record and record["state"] in ("changed", "interrupted", "never", "nonconforming"):
        nxt.append("Run /mycelium-extra:verify")
    else:
        nxt.append("Nothing pending")
    later = ["{}: {}".format(i, item) + ("  (blocked)" if st == "blocked" else "") for i, item, st in tracker]
    if nxt and tracker and nxt[0].startswith(tracker[0][0] + ":"):
        later = later[1:]
    if mycelium is None:
        mycelium = where_mycelium(root)
    if mycelium:
        later += mycelium_later(root, rel)

    cause = None
    stale = [s for s in steps if s["state"] == "stale"]
    if stale:
        changed = [s for s in steps if s["state"] in ("stale", "current") and s["script_time"] > s["out_time"] > 0]
        if changed:
            cause = "{} changed {}. Stale: {}.".format(
                changed[0]["script"], ago(now - changed[0]["script_time"]), ", ".join(step_id(s) for s in stale))
        else:
            cause = "An earlier step was rerun. Stale: {}.".format(", ".join(step_id(s) for s in stale))
    managed = [s for s in steps if s["state"] != "unmanaged"]
    if not marked:
        state_word = (entry or {}).get("status") or "old layout"
    elif failed:
        state_word = "failed"
    elif stale:
        state_word = "stale"
    elif not managed:
        state_word = "no steps"
    elif all(s["state"] == "todo" for s in managed):
        state_word = "not run"
    elif redo:
        state_word = "partial"
    else:
        state_word = "current"
    if ran and ran != "run time unreadable":
        last_run = "Last run {}: {}.".format("failed" if failed else "ok", ran)
    elif ran:
        last_run = "Last run {}: run time unreadable.".format("failed" if failed else "ok")
    elif any(s["state"] in ("current", "stale") for s in steps):
        ran, last_run = "no run log", "No run log (logs/CHANGES.md)."
    else:
        last_run = None
    if record and record["state"] in ("changed", "interrupted", "unreadable", "nonconforming"):
        watch.append(record["line"])
    if budget.truncated:
        watch.insert(0, "stopped counting at {} files; state may be wrong".format(budget.count))
    return {"rel": rel, "name": os.path.basename(rel), "aim": aim, "layout": layout, "log": log, "ran": ran,
            "last_run": last_run, "failed": failed, "steps": steps, "marked": marked, "redo": redo,
            "minutes": minutes, "next": nxt, "later": later, "watch": watch, "cause": cause,
            "cause_note": "Assumes steps run in number order." if stale else None, "state": state_word,
            "truncated": budget.truncated, "verify": record["line"] if record else None,
            "run": (entry or {}).get("name") if layout == "run" else None,
            "run_status": (entry or {}).get("status") if layout == "run" else None}


# ---------------------------------------------------------------- cards

MARK = {"current": "[x]", "stale": "[~]", "todo": "[ ]", "failed": "[!]", "unmanaged": "   "}


def capped(items, indent="  - "):
    shown = ["{}{}".format(indent, i) for i in items[:CAP]]
    if len(items) > CAP:
        shown.append("{}+{} more".format(indent, len(items) - CAP))
    return shown


def wrapped(text, indent="  "):
    return textwrap.wrap(text, WIDTH, initial_indent=indent, subsequent_indent=indent) or [indent + "-"]


def step_line(facts_):
    steps = facts_["steps"]
    if not steps:
        return "No numbered scripts in code/ or scripts/ yet."
    if not facts_["marked"]:
        return "Old {} layout: no per-step state.".format("run-folder" if facts_["layout"] == "run" else "flat") + (
            " Latest run: {} ({}).".format(facts_["run"], facts_["run_status"] or "no status") if facts_["run"] else "")
    current = sum(1 for s in steps if s["state"] == "current")
    where = next((i + 1 for i, s in enumerate(steps) if s["state"] not in ("current", "unmanaged")), len(steps))
    head = "{} of {} steps current.".format(current, len(steps))
    if facts_["redo"]:
        head = "Step {} of {}. ".format(where, len(steps)) + head
    return head


def render_card(f):
    lines = ["WHERE YOU ARE: " + f["name"], "", "AIM"] + wrapped(f["aim"])
    lines += ["", "RIGHT NOW", "  " + step_line(f)]
    if f["cause"]:
        lines += ["  " + f["cause"], "  " + f["cause_note"]]
    elif f["last_run"]:
        lines.append("  " + f["last_run"])
    if f["verify"]:
        lines.append("  " + f["verify"])
    eta = "  (about {} min)".format(f["minutes"]) if f["minutes"] and f["redo"] else (
        "  (time unknown)" if f["redo"] else "")
    lines += ["", "DO NEXT" + eta] + (["  Nothing pending."] if f["next"] == ["Nothing pending"] else
                                                  ["  {}. {}".format(i + 1, t) for i, t in enumerate(f["next"][:CAP])])
    lines += ["", "APPROACH"]
    if f["steps"]:
        rows = ["  {} {}".format(MARK[s["state"]], s["stem"]) if f["marked"] else "  - " + s["stem"]
                for s in f["steps"]]
        lines += rows[:CAP] + (["  +{} more".format(len(rows) - CAP)] if len(rows) > CAP else [])
    else:
        lines.append("  none yet")
    if f["later"]:
        lines += ["", "LATER"] + capped(f["later"])
    if f["watch"]:
        lines += ["", "WATCH OUT"] + capped(f["watch"])
    return "\n".join(lines)


def render_short(f):
    state = step_line(f) if not f["cause"] else "{} {} {}".format(step_line(f), f["cause"], f["cause_note"])
    if f["verify"]:
        state += " " + f["verify"]
    then = f["next"][1] if len(f["next"]) > 1 else (f["later"][0] if f["later"] else "nothing")
    return "\n".join([f["name"], "AIM    " + f["aim"], "STATE  " + state, "NEXT   " + f["next"][0],
                      "THEN   " + then, "BLOCK  " + (f["watch"][0] if f["watch"] else "none")])


def with_code(root, rels):
    """The folders among `rels` (repository-relative) that are analyses: a code/ or scripts/ folder, or their
    own `<NAME>.md` doc (see analysis_paths.is_analysis)."""
    return [r for r in rels if ap.is_analysis(os.path.join(root, r))]


def subfolders(root, rel):
    """Repository-relative non-hidden folders directly under `rel`, sorted."""
    try:
        names = sorted(n for n in os.listdir(os.path.join(root, rel))
                       if not n.startswith(".") and os.path.isdir(os.path.join(root, rel, n)))
    except OSError:
        return []
    return [(rel + "/" if rel not in ("", ".") else "") + n for n in names]


def read_config(root):
    """`<root>/.mycelium-extra/gate.json` as a dict, or None. Plain JSON, no gate import; `where all` run from
    the command line has no config from the gate, so it reads the roots the gate would use."""
    try:
        with open(os.path.join(root, ".mycelium-extra", "gate.json"), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def manifest_roots(root, skip):
    """Top-level folders (not in `skip`) that hold an ANALYSIS_MANIFEST.md: where a Mycelium repository keeps
    its analyses when the gate names other roots or none."""
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return []
    return [n for n in names if n not in skip and not n.startswith(".")
            and os.path.isfile(os.path.join(root, n, ap.MANIFEST_NAME))]


def find_analyses(root, config=None, cwd=None):
    """(analysis folders, roots searched). The folders directly under each gated root; when there are none,
    one level further down and the folders next to the current directory, and the top-level folders that hold
    an ANALYSIS_MANIFEST.md. With no config, the gate.json of the repository names the roots."""
    config = config or read_config(root)
    roots = focus.roots_of(config) if config and config.get("gated_paths") else ["analysis", "nbs"]
    top = focus.analyses(root, roots)
    found = with_code(root, top)
    if found:
        return found, roots
    extra = manifest_roots(root, roots)
    if extra:
        top += focus.analyses(root, extra)
        found = with_code(root, top)
        if found:
            return found, roots + extra
    for rel in top:
        found += with_code(root, subfolders(root, rel))
    if cwd:
        parent = os.path.dirname(os.path.realpath(cwd))
        if ap.inside(parent, os.path.realpath(root)) and parent != os.path.realpath(root):
            found += with_code(root, subfolders(root, os.path.relpath(parent, os.path.realpath(root))))
    return sorted(set(found)), roots


def render_all(root, config=None, cwd=None, budget=None):
    found, roots = find_analyses(root, config, cwd)
    if not found:
        return ("No analysis folders under {} (nor one level below them, nor next to this folder). "
                "Make one with the new-analysis skill.").format(", ".join(r + "/" for r in roots))
    ranked = sorted(found, key=lambda r: -activity(root, r))
    budget = budget or Budget(3.0, 20000)  # one cap for the whole list
    pending = pending_entries(root)
    pad = max(len(os.path.basename(r)) for r in ranked[:8])
    lines = ["ANALYSES  (newest activity first)"]
    for rel in ranked[:8]:
        name = os.path.basename(rel).ljust(pad)
        if budget.exhausted():
            lines.append("  {}  not scanned".format(name))
            continue
        try:
            r = facts(root, rel, budget, pending, verify=False, mycelium=False)
        except OSError:
            lines.append("  {}  unreadable  -  next: where (in that folder) to see the error".format(name))
            continue
        listed = ap.manifest_status(os.path.join(root, rel), root)
        status = listed.partition(": ")[2]  # the manifest's status word, when the manifest lists one
        lines.append("  {}  {:8}  {}  next: {}{}{}".format(
            name, r["state"], r["ran"] or "never run", r["next"][0], "  [manifest: {}]".format(status) if status else "",
            "  (state may be wrong)" if r["truncated"] else ""))
    if len(ranked) > 8:
        lines.append("  +{} not scanned".format(len(ranked) - 8))
    return "\n".join(lines)


# ---------------------------------------------------------------- the one write

def save(root, rel, text):
    """Write the full card to .mycelium-extra/now/<rel with / as __>.md atomically; the path, or None on failure."""
    folder = os.path.join(root, ".mycelium-extra", "now")
    path = os.path.join(folder, rel.replace("/", "__") + ".md")
    body = "# Where you are: {}\n\nWritten: {}\n\n```text\n{}\n```\n".format(rel, time.strftime("%Y-%m-%d %H:%M"), text)
    try:
        os.makedirs(folder, exist_ok=True)
        tmp = path + ".tmp{}".format(os.getpid())
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.write(body)
        os.replace(tmp, path)
    except OSError:
        return None
    return os.path.relpath(path, root)


def answer(root, cwd, mode=None, session_id=None, config=None, write=True):
    """The text for one `where` request."""
    if mode == "all":
        return render_all(root, config, cwd)
    rel = locate(root, cwd, session_id)
    if rel is None:
        return ("No analysis found here. Type `focus <folder>`, or `where all` to list them.")
    f = facts(root, rel)
    card = render_card(f)
    out = render_short(f) if mode == "short" else card
    saved = save(root, rel, card) if write else None
    return out + ("\n\nSaved: " + saved if saved else "")


def main(argv):
    args = [a for a in argv[1:] if a != "-"]
    opts = {}
    for flag in ("--repo", "--cwd", "--session"):
        if flag in args:
            i = args.index(flag)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    write = "--no-write" not in args
    mode = next((a for a in args if a in ("short", "all")), None)
    cwd = opts.get("--cwd", os.getcwd())
    root = opts.get("--repo") or ap.repo_root(cwd)
    print(answer(root, cwd, mode, opts.get("--session"), None, write))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
