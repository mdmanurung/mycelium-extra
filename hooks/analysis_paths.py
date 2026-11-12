"""One place that finds an analysis's files, so every skill reads the same layout.

Three layouts are read:
- "steps" (new): `outputs/<script stem>/` folders (`NN_name`, or `NNa_name`), one per script, each holding
  `figures/ source_data/ tables/`. A rerun overwrites its folder. `runs()` returns one "steps" entry (path =
  the outputs folder) first; `figures()`, `source_data()` and `tables()` gather across all step folders.
  Changes to code and outputs are logged in `<analysis>/logs/CHANGES.md` (`change_log()`, `last_change()`).
- "run": old `outputs/run_<YYYYMMDD>_<slug>[_vNN]/` folders with a `RUN.txt` and an `outputs/current` link.
  They are left in place and still read, after the "steps" entry.
- "flat": old analyses keep files directly in `outputs/`.
An `outputs/current` link, where it exists and resolves inside the repository, still wins in `current_run()`.

Stdlib-only; Python 3.9+. The gate does not import this module (hooks/gate.py keeps its own root finder).
"""

import hashlib
import os
import re
import subprocess

RUN_DIR = re.compile(r"^run_\d{8}_.+$")
STEP_DIR = re.compile(r"^\d{2}[a-z]?_.+$")
PANELS_DIR = "panels"  # manuscript panels (plot_<panel>.R|py) write outputs/panels/, a step folder without a number
STEP_SUBDIRS = ("logs", "figures", "source_data", "tables")  # a step folder that has run holds at least one of these (Snakemake writes logs/ for every step)
KINDS = ("analysis", "figures", "scratch")
FIGURE_EXT = (".png", ".pdf")


# ---------------------------------------------------------------- roots (three different meanings)

def git_toplevel(start):
    """The git toplevel of `start`, resolved, or None when `start` is not in a git repository."""
    start = os.path.abspath(start)
    while not os.path.isdir(start):
        start = os.path.dirname(start)
    try:
        out = subprocess.run(["git", "-C", start, "rev-parse", "--show-toplevel"], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, encoding="utf-8", errors="replace")
    except OSError:
        return None
    if out.returncode == 0 and out.stdout.strip():
        return os.path.realpath(out.stdout.strip())
    return None


def repo_root(start):
    """The git toplevel of `start`, else `start` itself (absolute)."""
    return git_toplevel(start) or os.path.abspath(start)


def living_root(start):
    """The nearest ancestor of `start` with `.living/` (Mycelium's repository marker), searching up to
    the git toplevel; else the toplevel; else None. This is new-analysis's root."""
    path = os.path.abspath(start)
    while not os.path.isdir(path):
        path = os.path.dirname(path)
    top = git_toplevel(path)
    while True:
        if os.path.isdir(os.path.join(path, ".living")):
            return path
        parent = os.path.dirname(path)
        if path == top or parent == path:
            return top
        path = parent


def gate_root(start):
    """The nearest ancestor of `start` (itself included) with `.mycelium-extra/gate.json`, else None.
    This is where the approval gate is on."""
    path = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(path, ".mycelium-extra", "gate.json")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def inside(path, root):
    """True when `path` is `root` or below it (both compared as given; resolve them first)."""
    root = root.rstrip(os.sep)
    return path == root or path.startswith(root + os.sep)


# ---------------------------------------------------------------- the analysis doc

def find_doc(folder):
    """Path of `<NAME>.md` (NAME = the folder's name in capitals, `-` as `_`) if it exists, else of
    `README.md` if it exists, else None."""
    folder = os.path.abspath(folder)
    name = os.path.basename(folder).upper().replace("-", "_") + ".md"
    for candidate in (name, "README.md"):
        path = os.path.join(folder, candidate)
        if os.path.isfile(path):
            return path
    return None


# ---------------------------------------------------------------- RUN.txt

def _strip_comment(value):
    """`value` up to the first ` #` that is not inside quotes, trailing space trimmed."""
    quote = None
    for i, ch in enumerate(value):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and i > 0 and value[i - 1] in " \t":
            return value[:i].rstrip()
    return value.rstrip()


def parse_run_txt(path):
    """The `key: value` lines of a RUN.txt as a dict. Blank lines and lines starting with `#` are skipped;
    a value is everything after the first `:` up to an unquoted ` #`; an empty value is "". Unknown keys
    are kept. A `kind` outside analysis | figures | scratch adds `kind_error`. A missing or unreadable
    file gives {}."""
    fields = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return fields
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        key, colon, value = line.partition(":")
        if colon and re.match(r"^[a-z_]+$", key.strip()):
            fields[key.strip()] = _strip_comment(value.strip())
    if "kind" in fields and fields["kind"] not in KINDS:
        fields["kind_error"] = "kind `{}` is not one of {}".format(fields["kind"], " | ".join(KINDS))
    return fields


# ---------------------------------------------------------------- runs

def _base(folder, results_dir=None):
    if results_dir:
        return os.path.join(folder, results_dir)
    results = os.path.join(folder, "results")
    return results if os.path.isdir(results) else os.path.join(folder, "outputs")


def base(folder, results_dir=None):
    """The folder that holds an analysis's runs: `results_dir`, else `results/` if it exists, else `outputs/`."""
    return _base(folder, results_dir)


def _newest(path):
    """Newest file mtime inside `path` (RUN.txt excluded: labelling a run does not make it newer), or 0."""
    newest = 0
    for here, dirs, names in os.walk(path):
        for name in names:
            if name == "RUN.txt" and here == path:
                continue
            try:
                newest = max(newest, os.lstat(os.path.join(here, name)).st_mtime)
            except OSError:
                continue
    return newest


def _entry(path):
    meta = parse_run_txt(os.path.join(path, "RUN.txt")) if os.path.isfile(os.path.join(path, "RUN.txt")) else None
    return {"path": path, "name": os.path.basename(path), "run_txt": meta,
            "kind": meta.get("kind") if meta else None, "status": meta.get("status") if meta else None,
            "layout": "run"}


def _flat(base):
    return {"path": base, "name": os.path.basename(base), "run_txt": None, "kind": None, "status": None,
            "layout": "flat"}


def _steps(base):
    return {"path": base, "name": os.path.basename(base), "run_txt": None, "kind": "analysis", "status": None,
            "layout": "steps"}


def runs(folder, results_dir=None):
    """Run folders of an analysis, oldest name first. `results_dir` if given, else `<folder>/results/`
    if it exists, else `<folder>/outputs/`. A run is a real directory named `run_<YYYYMMDD>_<slug>`; dotfiles such as `.gitkeep` are ignored.
    When there are none but files (or other folders) sit in the outputs folder, one entry with
    layout "flat" and the outputs folder as its path is returned, so old analyses keep working.
    When a step folder (`NN_name`, see STEP_DIR, holding a figures, source_data or tables folder) exists, the first entry has layout "steps" and the
    outputs folder as its path; old run folders follow it."""
    base = _base(folder, results_dir)
    if not os.path.isdir(base):
        return []
    found, other, has_steps, bare = [], False, False, False
    for name in sorted(os.listdir(base)):
        path = os.path.join(base, name)
        if name == "current" or name.startswith(".") or os.path.islink(path):
            continue
        if os.path.isdir(path) and RUN_DIR.match(name):
            found.append(_entry(path))
        elif os.path.isdir(path) and (STEP_DIR.match(name) or name == PANELS_DIR):
            # a data folder such as `10x_counts` has the name but no output subfolder: it is no step
            if any(os.path.isdir(os.path.join(path, sub)) for sub in STEP_SUBDIRS):
                has_steps = True
            else:
                bare = True
        else:
            other = True
    if has_steps:
        return [_steps(base)] + found
    other = other or bare
    if not found and other:
        return [_flat(base)]
    return found


def current_run(folder, results_dir=None):
    """(entry or None, reason). Reason is "current link" (the target of `current`, which must resolve
    inside the repository), "outside repository" (it does not: a gap, entry None), "steps layout"
    (the steps entry, when step folders exist), "newest run" (by newest file mtime, skipping kind
    `scratch`), "flat layout" or "none"."""
    base = _base(folder, results_dir)
    link = os.path.join(base, "current")
    if os.path.islink(link):
        target = os.path.realpath(link)
        if not inside(target, os.path.realpath(repo_root(folder))):
            return None, "outside repository"
        if os.path.isdir(target):
            return _entry(target), "current link"
    found = runs(folder, results_dir)
    if found and found[0]["layout"] == "steps":
        return found[0], "steps layout"
    if found and found[0]["layout"] == "flat":
        return found[0], "flat layout"
    live = [r for r in found if r["kind"] != "scratch"]
    if live:
        return max(live, key=lambda r: (_newest(r["path"]), r["name"])), "newest run"
    return None, "none"


def _run_path(run):
    return run["path"] if isinstance(run, dict) else run


def numbers(folder, run=None):
    """`<run>/numbers.json` if it exists, else `<folder>/outputs/numbers.json` if it exists, else None."""
    for path in ((os.path.join(_run_path(run), "numbers.json"),) if run else ()) + (
            os.path.join(folder, "outputs", "numbers.json"),):
        if os.path.isfile(path):
            return path
    return None


def _files(path, only=None):
    if not os.path.isdir(path):
        return []
    return sorted(os.path.join(path, n) for n in os.listdir(path)
                  if not n.startswith(".") and os.path.isfile(os.path.join(path, n))
                  and (only is None or n.lower().endswith(only)))


def _gather(run, sub):
    """Files in `<run>/<sub>/`; for a "steps" run, in `<outputs>/<step>/<sub>/` over all step folders."""
    path = _run_path(run)
    if isinstance(run, dict) and run.get("layout") == "steps":
        out = []
        for name in sorted(os.listdir(path)):
            if (STEP_DIR.match(name) or name == PANELS_DIR) and os.path.isdir(os.path.join(path, name)):
                out += _files(os.path.join(path, name, sub))
        return sorted(out)
    return _files(os.path.join(path, sub))


def figures(run):
    """Sorted figure files of a run: those in `<run>/figures/`, plus PNG/PDF files directly in a flat run.
    A "steps" run gathers `outputs/*/figures/` over all step folders."""
    out = _gather(run, "figures")
    if isinstance(run, dict) and run.get("layout") == "flat":
        out += _files(_run_path(run), FIGURE_EXT)
    return sorted(out)


def source_data(run):
    """Sorted files in `<run>/source_data/` (over all step folders for a "steps" run)."""
    return _gather(run, "source_data")


def tables(run):
    """Sorted files in `<run>/tables/` (over all step folders for a "steps" run)."""
    return _gather(run, "tables")


# ---------------------------------------------------------------- the change log

def change_log(folder):
    """Path of `<folder>/logs/CHANGES.md` if it exists, else None."""
    path = os.path.join(folder, "logs", "CHANGES.md")
    return path if os.path.isfile(path) else None


def last_change(folder):
    """The heading line of the newest entry in the change log, else None. Entries are level-2 headings
    `## <YYYY-MM-DD HH:MM> <git short hash>[ dirty] <ok|failed>`. Newest is by the time stamp, so entry
    order does not matter; a tie goes to the later line."""
    path = change_log(folder)
    if not path:
        return None
    heads = [line.rstrip() for line in read(path).splitlines() if line.startswith("## ")]
    return max(enumerate(heads), key=lambda p: (p[1][3:19], p[0]))[1] if heads else None


def stem(path):
    """The `NN_name` stem that pairs a figure with its source-data table: the file name without its
    extension (and without `.gz`)."""
    name = os.path.splitext(os.path.basename(path))[0]
    if os.path.basename(path).lower().endswith(".gz"):
        name = os.path.splitext(name)[0]
    return name


# ---------------------------------------------------------------- small shared helpers

def read(path, errors="replace"):
    """The text of `path`; pass errors="strict" to raise on a bad byte."""
    with open(path, encoding="utf-8", errors=errors) as handle:
        return handle.read()


def fill(text, mapping):
    """Replace each `@@KEY@@` with its value."""
    for key, value in mapping.items():
        text = text.replace("@@" + key + "@@", value)
    return text


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
