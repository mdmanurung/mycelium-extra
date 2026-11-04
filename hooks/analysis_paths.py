"""One place that finds an analysis's files, so every skill reads the same layout.

The layout is docs/concepts/analysis-layout.md: `outputs/run_<YYYYMMDD>_<slug>[_vNN]/` folders with a
`RUN.txt`, an `outputs/current` link, and `figures/ source_data/ tables/ numbers.json` inside a run. Old
analyses keep files directly in `outputs/`; that is the "flat" layout and is still read.

Stdlib-only; Python 3.9+. The gate does not import this module (hooks/gate.py keeps its own root finder).
"""

import hashlib
import os
import re
import subprocess

RUN_DIR = re.compile(r"^run_\d{8}_.+$")
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


def runs(folder, results_dir=None):
    """Run folders of an analysis, oldest name first. `results_dir` if given, else `<folder>/results/`
    if it exists, else `<folder>/outputs/`. A run is a real directory named `run_<YYYYMMDD>_<slug>`.
    When there are none but files (or other folders) sit in the outputs folder, one entry with
    layout "flat" and the outputs folder as its path is returned, so old analyses keep working."""
    base = _base(folder, results_dir)
    if not os.path.isdir(base):
        return []
    found, other = [], False
    for name in sorted(os.listdir(base)):
        path = os.path.join(base, name)
        if name == "current" or os.path.islink(path):
            continue
        if os.path.isdir(path) and RUN_DIR.match(name):
            found.append(_entry(path))
        else:
            other = True
    if not found and other:
        return [_flat(base)]
    return found


def current_run(folder, results_dir=None):
    """(entry or None, reason). Reason is "current link" (the target of `current`, which must resolve
    inside the repository), "outside repository" (it does not: a gap, entry None), "newest run" (by
    newest file mtime, skipping kind `scratch`), "flat layout" or "none"."""
    base = _base(folder, results_dir)
    link = os.path.join(base, "current")
    if os.path.islink(link):
        target = os.path.realpath(link)
        if not inside(target, os.path.realpath(repo_root(folder))):
            return None, "outside repository"
        if os.path.isdir(target):
            return _entry(target), "current link"
    found = runs(folder, results_dir)
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


def figures(run):
    """Sorted figure files of a run: those in `<run>/figures/`, plus PNG/PDF files directly in a flat run."""
    path = _run_path(run)
    out = _files(os.path.join(path, "figures"))
    if isinstance(run, dict) and run.get("layout") == "flat":
        out += _files(path, FIGURE_EXT)
    return sorted(out)


def source_data(run):
    """Sorted files in `<run>/source_data/`."""
    return _files(os.path.join(_run_path(run), "source_data"))


def tables(run):
    """Sorted files in `<run>/tables/`."""
    return _files(os.path.join(_run_path(run), "tables"))


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
