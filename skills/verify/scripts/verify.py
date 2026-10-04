"""Check an approved grill plan against what ran, and write its provenance.

Stdlib-only; runs on Python 3.6+. Run it from stdin, inside the repository, so
Mycelium's hooks do not open the post-action cycle:

    python3 - --plugin-root <root> list < verify.py
    python3 - --plugin-root <root> report <hash> [--analysis-dir DIR] [--json] < verify.py
    python3 - --plugin-root <root> write <hash> --analysis-dir DIR < verify.py
    python3 - --plugin-root <root> stale [--json] < verify.py
    python3 - --plugin-root <root> status [--json] < verify.py
    python3 - --plugin-root <root> explore [--session ID | --all] [--json] < verify.py

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
import datetime
import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
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
    "With `snakemake --use-conda`, rules run in their own envs under `.snakemake/conda/`; the conda env "
    "recorded is the one Snakemake ran in, not the rules' envs.",
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


LINT_LINE = re.compile(r"^(.+?):(\d+):(\d+): \[([\w-]+)\] (.*)$")
LINT_LANGUAGES = {".py": "Python", ".R": "R", ".r": "R"}
NOTEBOOK_EXT = (".ipynb", ".qmd", ".Rmd", ".rmd")
FENCE = re.compile(r"^\s*(`{3,})(.*)$")
CHUNK = re.compile(r"^\s*\{(r|python)\b", re.I)


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
    """{language: code} of a .qmd/.Rmd's r and python chunks, every other line blank so
    line numbers match the document. Python magic and shell lines become comments."""
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return {}
    code, fence, language, magic = {}, None, None, False
    for n, line in enumerate(lines):
        match = FENCE.match(line)
        if fence is None:
            if match:
                fence, chunk, magic = match.group(1), CHUNK.match(match.group(2)), None
                language = chunk and {"r": "R", "python": "Python"}[chunk.group(1).lower()]
            continue
        if match and len(match.group(1)) >= len(fence) and not match.group(2).strip():
            fence = None
        elif language:
            if magic is None:
                magic = language == "Python" and line.lstrip().startswith("%%")
            commented = language == "Python" and (magic or line.lstrip().startswith(("%", "!")))
            code.setdefault(language, [""] * len(lines))[n] = "# " + line if commented else line
    return {language: "\n".join(body) for language, body in code.items()}


def lint(root, files, report, scilintr, rscript, seconds):
    """Run scilintr on the code; remaining findings block, an unchecked language is a gap.
    The Python CLI skips R files and exits 0 on a missing path, so each language gets
    its own CLI and only existing files are passed. It also exits 0, silent, on code that
    does not parse, so Python code is parsed first and an unparseable file is a gap."""
    result = {"findings": [], "waivers": [], "output": [], "notebooks": []}
    by_language = collections.defaultdict(list)
    scratch = tempfile.mkdtemp(prefix="mycelium-extra-lint-")
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

    def extract(rel, language, code, starts=None):
        if language == "Python" and not parses(rel, code):
            return
        path = os.path.join(scratch, "{}_{}".format(len(cells), os.path.basename(rel))) + (
            ".py" if language == "Python" else ".R")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(code)
        cells[path] = (rel, starts)
        by_language[language].append(path)

    try:
        for rel in files:
            ext = os.path.splitext(rel)[1]
            extracted = notebook_code(os.path.join(root, rel)) if ext == ".ipynb" else None
            chunks = chunk_code(os.path.join(root, rel)) if ext.lower() in (".qmd", ".rmd") else None
            if ext in LINT_LANGUAGES:
                if LINT_LANGUAGES[ext] != "Python" or parses(rel):
                    by_language[LINT_LANGUAGES[ext]].append(rel)
            elif extracted:
                extract(rel, *extracted)
            elif chunks:
                for language, code in sorted(chunks.items()):
                    extract(rel, language, code)
            elif rel.endswith(NOTEBOOK_EXT):
                result["notebooks"].append(rel)
        lint_languages(root, by_language, cells, report, result, scilintr, rscript, seconds)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    for rel in files:
        if os.path.splitext(rel)[1] in LINT_LANGUAGES or rel.endswith(NOTEBOOK_EXT):
            try:
                with open(os.path.join(root, rel), errors="replace") as handle:
                    result["waivers"] += [(rel, n, line.strip()) for n, line in enumerate(handle, 1)
                                          if "ANALYSIS_OK[" in line]
            except OSError:
                continue
    if result["notebooks"]:
        report.add("info", "{} notebook(s) not linted: {}.".format(
            len(result["notebooks"]), gate.listing(result["notebooks"], 5)))
    return result


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


def lint_languages(root, by_language, cells, report, result, scilintr, rscript, seconds):
    for language, paths in sorted(by_language.items()):
        command = [scilintr] if language == "Python" else [rscript, "-e", "scilintr::main()"]
        try:
            proc = subprocess.run(command + paths, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  universal_newlines=True, timeout=seconds)
        except (OSError, subprocess.SubprocessError) as error:
            if isinstance(error, subprocess.TimeoutExpired):
                report.add("gap", "scilintr ({}) not checked: timed out after {:.0f} s.".format(language, seconds))
            else:
                report.add("gap", "scilintr ({}) not checked: `{}` not found. Install it (`{}`) and re-verify."
                           .format(language, command[0], "pip install scilintr" if language == "Python"
                                   else 'install.packages("scilintr")'))
            continue
        proc.stdout = "\n".join(cell_line(line, cells) for line in proc.stdout.splitlines())
        for path, (rel, _) in cells.items():
            proc.stdout = proc.stdout.replace(path, rel)
        found = [m.groups() for m in map(LINT_LINE.match, proc.stdout.splitlines()) if m]
        result["output"].append("$ {}\n{}".format(" ".join(command[:3] + ["<{} files>".format(len(paths))]),
                                                  proc.stdout.rstrip()))
        if proc.returncode == 1 and found:
            result["findings"] += found
            rules = collections.Counter(f[3] for f in found)
            report.add("block", "{} scilintr finding(s) remain in {} code ({}). Fix each or add an "
                       "`ANALYSIS_OK[...]` waiver, then re-verify.".format(
                           len(found), language, ", ".join("{} {}".format(n, r) for r, n in rules.most_common())))
        elif proc.returncode == 0 and not found:
            report.add("info", "scilintr: {} {} file(s) clean.".format(len(paths), language))
        else:
            report.add("gap", "scilintr ({}) not checked: exit {} with output it could not read: {}".format(
                language, proc.returncode, cell((proc.stdout.strip().splitlines() or [""])[-1])[:200]))


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


def conda_snapshots(root, runs, report):
    """`conda list --explicit` of each conda env the plan's runs used and no conda-lock.yml pins,
    read from the env's conda-meta records (conda itself need not be on PATH)."""
    envs = collections.OrderedDict()
    for r in runs:
        if any(os.path.basename(l.get("path", "")) == "conda-lock.yml" for l in r.get("lockfiles") or []):
            continue
        env = conda_env(root, r)
        if env:
            env = envs.setdefault(env["prefix"] or env["env"], env)
            env["last_run"] = max(env.get("last_run", 0), r.get("ts", 0))
    snapshots = []
    for env in envs.values():
        meta = os.path.join(env["prefix"] or "", "conda-meta")
        records = [gate.read_json(p, {}) for p in sorted(glob.glob(os.path.join(meta, "*.json")))]
        urls = sorted("{}#{}".format(m["url"], m["md5"]) if m.get("md5") else m["url"]
                      for m in records if m.get("url"))
        if not env["prefix"] or not urls:
            report.add("gap", "Conda env `{}` ({}) was not found, so its packages were not recorded.".format(
                env["env"], env["source"]))
            continue
        try:
            changed = os.stat(os.path.join(meta, "history")).st_mtime
        except OSError:
            changed = 0
        stale = changed > env["last_run"] + TOLERANCE
        if stale:
            report.add("gap", "Conda env `{}` changed {}, after its last run here ({}); the recorded package "
                              "list is the env as it is now.".format(env["env"], when(changed), when(env["last_run"])))
        else:
            report.add("info", "Conda env `{}` ({}): {} packages recorded.".format(env["env"], env["source"],
                                                                                 len(urls)))
        snapshots.append(dict(env, packages=urls, changed_after_run=stale))
    return snapshots


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


def check(root, digest, analysis_dir=None, sacct="sacct", hash_mb=2000, seconds=120, scilintr="scilintr",
          rscript="Rscript"):
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
        if is_run(root, r, config["gated_commands"]):
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
        direct = [r for r in mine if path in ran_paths(root, r)]
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
            elif code in ("failed", "interrupted"):  # PostToolUseFailure with no exit code, or an abort
                row["status"] = "failed (no exit code)" if code == "failed" else "interrupted"
                report.add("block", "`{}` {} at {}{}.".format(
                    path, "failed without an exit code" if code == "failed" else "was interrupted",
                    when(last["ts"]), ": " + last["error_line"] if last.get("error_line") else ""))
            elif last.get("job_id"):
                state = (job or {}).get("state")
                row["status"] = "job {} {}".format(last["job_id"], state or "state unknown (no sacct)")
                if state in FAILED_JOB:
                    report.add("block", "`{}`: Slurm job {} ended {}.".format(path, last["job_id"], state))
                elif state != "COMPLETED":
                    report.add("gap", "`{}`: Slurm job {} is {}; check `sacct -j {}`.".format(
                        path, last["job_id"], state or "of unknown state", last["job_id"]))
            elif code == 0:
                row["status"] = "ran (exit 0 from hook event)" if last.get("exit_source") == "event" else "ran"
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
    for folder in folders:
        runs = [r for r in mine if any(under(p, folder) for p in ran_paths(root, r))]
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
            if r in mine or not any(under(p, analysis_dir) for p in ran_paths(root, r)):
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

    seen = {p for r in since for p in ran_paths(root, r)}
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

    default_reasons(plan, report)
    envs = conda_snapshots(root, mine, report)
    linted = lint(root, code_files(root, analysis_dir, planned), report, scilintr, rscript, seconds)

    return {"hash": digest, "approved_at": approved_at, "start": start, "session_id": approval.get("session_id"),
            "analysis_dir": analysis_dir, "git": gate.git_state(root), "runs": len(mine),
            "scripts": scripts, "folders": folders, "commands": commands, "inputs": inputs,
            "outputs": outputs, "outputs_named": words, "findings": report.findings, "lint": linted, "envs": envs,
            "status": report.status(), "plan": plan,
            # Kept for the record (a scaffolder call can explain a moved input), marked as not runs.
            "receipts": sorted(mine + [dict(r, not_a_run="only passed planned paths to other code")
                                       for r in handed], key=lambda r: r.get("ts", 0))}


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
    lines += ["", "## Lint", ""]
    lint_rows = result["lint"]["findings"]
    lines += ["- `{}:{}` [{}] {}".format(cell(f[0]), f[1], f[3], cell(f[4])) for f in lint_rows[:SHOWN_OUTPUTS]]
    if len(lint_rows) > SHOWN_OUTPUTS:
        lines.append("- {} more; `write` records them all.".format(len(lint_rows) - SHOWN_OUTPUTS))
    waivers = result["lint"]["waivers"]
    lines.append("{} `ANALYSIS_OK` waiver(s){}".format(len(waivers), ":" if waivers else "."))
    lines += ["- `{}:{}` {}".format(cell(w[0]), w[1], cell(w[2])) for w in waivers[:SHOWN_OUTPUTS]]
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
             "outputs": "outputs-{}.tsv".format(digest), "report": "verify-{}.md".format(digest),
             "lint": "lint-{}.txt".format(digest)}
    if result.get("envs"):
        paths["env"] = "env-{}.txt".format(digest)
        with open(os.path.join(folder, paths["env"]), "w") as handle:
            handle.write("# Conda envs of plan {}'s runs, read {} from each env's conda-meta (the format of "
                         "`conda list --explicit --md5`).\n# One block per env: copy a block from `@EXPLICIT` "
                         "into its own file for `conda create -n <name> --file <file>`.\n".format(digest, stamp))
            for env in result["envs"]:
                handle.write("\n# env: {}\n# prefix: {}\n# from: {}\n{}@EXPLICIT\n{}\n".format(
                    env["env"], env["prefix"], env["source"],
                    "# changed after the run: this is the env as it was when verify read it\n"
                    if env["changed_after_run"] else "", "\n".join(env["packages"])))
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
    with open(os.path.join(folder, paths["lint"]), "w") as handle:
        lint = result["lint"]
        handle.write("\n\n".join(lint["output"]) or "scilintr did not run.")
        handle.write("\n\n# ANALYSIS_OK waivers ({})\n".format(len(lint["waivers"])))
        handle.writelines("{}:{}: {}\n".format(*w) for w in lint["waivers"])
    with open(os.path.join(folder, paths["report"]), "w") as handle:
        handle.write("Written {} by mycelium-extra verify.\n\n".format(stamp))
        handle.write(render(result, all_outputs=True))
    index = os.path.join(folder, "PROVENANCE.md")
    row = "| {} | {} | {} | {} | [plan]({}) · [receipts]({}) · [outputs]({}) · [lint]({}) · [report]({}){} |".format(
        digest, when(result["approved_at"]), stamp, result["status"], paths["plan"], paths["receipts"],
        paths["outputs"], paths["lint"], paths["report"],
        " · [conda env]({})".format(paths["env"]) if "env" in paths else "")
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
        record = gate.read_json(os.path.join(folder, name), None)
        if not record:
            continue
        digest = record.get("hash", name[:8])
        table = gate.plan_table(record.get("plan", ""))
        scripts = [p for p in gate.plan_paths(table) if gate.gated_rel(root, root, p, config)]
        rows.append((record.get("approved_at", 0), digest, scripts, runs[digest]))
    return rows


def list_plans(root):
    lines = ["| Plan | Approved | Scripts in table | Runs |", "|---|---|---|---|"]
    for approved, digest, scripts, count in sorted(approved_plans(root), reverse=True):
        lines.append("| {} | {} | {} | {} |".format(digest, when(approved), len(scripts), count))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- stale sweep

def provenance_receipts(root):
    """Every provenance/receipts-<hash>.jsonl git tracks or would track; a walk outside git."""
    listed = gate.git(root, "ls-files", "-co", "--exclude-standard", "--", "*provenance/receipts-*.jsonl")
    if listed is not None:
        return sorted(line for line in listed.splitlines() if line)
    found = []
    for folder, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        if os.path.basename(folder) == "provenance":
            found += [os.path.relpath(os.path.join(folder, f), root) for f in files
                      if re.match(r"^receipts-[0-9a-f]{8}\.jsonl$", f)]
    return sorted(found)


def stale_plan(root, rel, budget):
    """What no longer matches one plan's provenance: scripts, pinned inputs, outputs."""
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
    rows = []
    if os.path.isfile(table):
        with open(table) as handle:
            rows = [line.rstrip("\n").split("\t") for line in handle][1:]
    for row in rows:
        if len(row) < 3:
            continue
        path, written, size = row[0], row[1], row[2]
        try:
            info = os.stat(os.path.join(root, path))
        except OSError:
            changes.append("output `{}` deleted since verify recorded it".format(path))
            continue
        try:
            then = datetime.datetime.strptime(written, "%Y-%m-%dT%H:%M:%S%z").timestamp()
        except ValueError:
            then = None
        if (size and str(info.st_size) != size) or (then is not None and abs(info.st_mtime - then) > 2):
            changes.append("output `{}` rewritten {} (provenance out of date)".format(path, when(info.st_mtime)))
    sessions = sorted({r["session_id"] for r in runs if r.get("session_id")})
    return {"hash": digest, "analysis_dir": os.path.dirname(folder) or ".", "changes": changes,
            "sessions": sessions}


def stale(root, hash_mb, seconds):
    budget = {"bytes": float(hash_mb) * 1024 * 1024, "deadline": time.time() + seconds}
    plans = [stale_plan(root, rel, budget) for rel in provenance_receipts(root)]
    return {"plans": len(plans), "stale": [p for p in plans if p["changes"]]}


def render_stale(result):
    lines = []
    for plan in result["stale"]:
        lines += ["## Plan {} · `{}`".format(plan["hash"], plan["analysis_dir"]), ""]
        lines += ["- " + change for change in plan["changes"]]
        lines += ["- sessions: " + (", ".join(plan["sessions"]) or "none recorded"),
                  "- findings: `rg -n '{}' .living/findings/`".format(
                      "|".join(plan["sessions"] + ["plan " + plan["hash"]])), ""]
    lines.append("{} of {} verified plans stale.".format(len(result["stale"]), result["plans"])
                 if result["plans"] else "No verified plans: no provenance/receipts-<hash>.jsonl found.")
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
    text = text.split("# ANALYSIS_OK waivers")[0]
    found = sum(1 for line in text.splitlines() if LINT_LINE.match(line))
    # A missing, timed-out or unreadable linter leaves no finding in the lint file; the report names it.
    gaps = sorted(set(re.findall(r"scilintr \((\w+)\) not checked",
                                 read_text(os.path.join(folder, "verify-{}.md".format(digest))))))
    states = (["{} finding(s)".format(found)] if found else []) + (
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
        for approved, digest, scripts, count in approved_plans(root):
            rows[digest] = {"hash": digest, "approved": when(approved), "epoch": approved, "runs": count,
                            "analysis_dir": guess_analysis_dir(scripts) or "?", "verified": "not verified",
                            "stale": "-", "lint": "-"}
    for rel in provenance_receipts(root):
        plan = stale_plan(root, rel, budget)
        folder = os.path.join(root, os.path.dirname(rel))
        approved, verified = recorded_verify(folder, plan["hash"])
        runs = sum(1 for r in read_jsonl(os.path.join(root, rel)) if not r.get("explore") and not r.get("not_a_run"))
        row = rows.setdefault(plan["hash"], {"hash": plan["hash"], "approved": approved, "epoch": 0, "runs": runs})
        row.update(analysis_dir=plan["analysis_dir"], verified=verified, lint=recorded_lint(folder, plan["hash"]),
                   stale="{} change(s)".format(len(plan["changes"])) if plan["changes"] else "no",
                   changes=plan["changes"])
    for row in rows.values():
        row["manifest"] = manifest_status(root, row["analysis_dir"]) if row["analysis_dir"] != "?" else "-"
    return sorted(rows.values(), key=lambda r: (r["epoch"], r["approved"], r["hash"]), reverse=True)


def render_status(rows):
    if not rows:
        return "No plans: nothing approved here and no provenance/receipts-<hash>.jsonl found.\n"
    lines = ["| Plan | Analysis | Approved | Runs | Verified | Stale | Lint | Manifest |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append("| {hash} | `{analysis_dir}` | {approved} | {runs} | {verified} | {stale} | {lint} | "
                     "{manifest} |".format(**r))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- explore runs

EXPLORE_DAYS = 7


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
        entry = merged.pop(key, {"command": command, "cwd": key[0], "runs": 0, "first": r.get("ts")})
        env = conda_env(root, r) or {}
        entry.update(runs=entry["runs"] + 1, last=r.get("ts"), session=r.get("session_id"),
                     paths=ran_paths(root, r), exit_status=r.get("exit_status"), env=env.get("env"))
        script = r.get("script") or {}
        entry["changed"] = None
        if script.get("in_repo"):
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
        if run["changed"]:
            lines.append("   - " + run["changed"])
    lines += ["", "Explore outputs are not results: a plan that re-runs these commands without the "
                  "`{}=1` prefix makes them reportable. Explore runs of inline code (`python -c`) are "
                  "not recorded here.".format(gate.EXPLORE_VAR)]
    return "\n".join(lines) + "\n"


def plan_rows(plan):
    """The plan table's rows keyed by their first cell, each a {lowercased header: cell} dict."""
    rows, header = collections.OrderedDict(), None
    lines = plan.splitlines()
    for i, line in enumerate(lines):
        match = gate.TABLE_ROW.match(line)
        if not match:
            header = None
            continue
        if gate.TABLE_RULE.match(line):
            continue
        cells = [cell.replace("\0", "|").strip() for cell in match.group(1).replace("\\|", "\0").split("|")]
        following = lines[i + 1] if i + 1 < len(lines) else ""
        if gate.TABLE_ROW.match(following) and gate.TABLE_RULE.match(following):
            header = [cell.lower() for cell in cells]
        elif header and cells[0]:
            rows[cells[0]] = dict(zip(header, cells))
    return rows


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


def diff_plans(root, old, new):
    """What changed between two approved plans: table rows by step, and the `Inputs:` line."""
    plans = []
    for digest in (old, new):
        record = gate.read_json(gate.state_path(root, "approvals", digest + ".json"), None)
        text = record.get("plan") if record else shown_plan(root, digest)
        if text is None:
            sys.exit("verify: no approved or shown plan {} (see `list`).".format(digest))
        plans.append(text)
    before, after = plan_rows(plans[0]), plan_rows(plans[1])
    lines = ["# Plan diff {} -> {}".format(old, new), ""]
    for key in list(before) + [k for k in after if k not in before]:
        if key not in after:
            lines.append("- Step {}: removed (was: {}).".format(key, " / ".join(before[key].values())))
        elif key not in before:
            lines.append("- Step {}: added: {}.".format(key, " / ".join(after[key].values())))
        else:
            for column in after[key]:
                was, now = before[key].get(column, ""), after[key][column]
                if was != now:
                    flag = " **Possible scientific change.**" if column == "choice" else ""
                    lines.append("- Step {}, {}: `{}` -> `{}`.{}".format(key, column, was, now, flag))
    was, now = [gate.plan_inputs(text) or [] for text in plans]
    lines += ["- Inputs: + {}".format(word) for word in now if word not in was]
    lines += ["- Inputs: - {}".format(word) for word in was if word not in now]
    if len(lines) == 2:
        lines.append("No plan-table row or `Inputs:` entry changed.")
    return "\n".join(lines) + "\n"


def main(argv):
    parser = argparse.ArgumentParser(prog="verify")
    parser.add_argument("--plugin-root", required=True)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--sacct", default="sacct")
    parser.add_argument("--scilintr", default="scilintr")
    parser.add_argument("--rscript", default="Rscript")
    parser.add_argument("--hash-mb", type=float, default=2000)
    parser.add_argument("--seconds", type=float, default=120)
    parser.add_argument("action", choices=["list", "report", "write", "stale", "status", "diff", "explore"])
    parser.add_argument("hash", nargs="?")
    parser.add_argument("new_hash", nargs="?")
    parser.add_argument("--analysis-dir")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--session", help="explore: this session's runs (default: $CLAUDE_CODE_SESSION_ID)")
    parser.add_argument("--all", action="store_true", help="explore: every session's runs, last 7 days")
    args = parser.parse_args(argv)
    load_gate(args.plugin_root)
    root = gate.find_root(os.path.abspath(args.repo))
    if args.action in ("stale", "status"):  # committed provenance suffices, so no gate needed
        top = gate.git(os.path.abspath(args.repo), "rev-parse", "--show-toplevel")
        base = root or (top.strip() if top else os.path.abspath(args.repo))
        if args.action == "stale":
            result = stale(base, args.hash_mb, args.seconds)
            sys.stdout.write(json.dumps(result, indent=1) + "\n" if args.json else render_stale(result))
        else:
            rows = status(base, args.hash_mb, args.seconds)
            sys.stdout.write(json.dumps(rows, indent=1) + "\n" if args.json else render_status(rows))
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
    if args.action == "write" and not args.analysis_dir:
        sys.exit("verify: `write` needs --analysis-dir, confirmed by the user.")
    result = check(root, args.hash, args.analysis_dir, args.sacct, args.hash_mb, args.seconds, args.scilintr,
                   args.rscript)
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
