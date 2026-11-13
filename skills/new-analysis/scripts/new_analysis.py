"""Scaffold a new analysis folder that plugs into Mycelium.

Run from stdin so Mycelium's hooks stay closed, with every option in --flag=value form
(the approval gate reads a bare analysis/... argument as a script to run):
    <plugin>/hooks/mxpy - --dest=analysis/<name> [--steps=01_a.R,02_b.py,03_c.ipynb,04_d.qmd,05_e.marimo.py]
              [--format=R|py|ipynb|qmd|marimo] [--lang=r|python]
              [--data=PATH ...] [--code=PATH ...] [--doc-template=PATH] [--panels=Fig1a.R,Fig1b.py]
              [--wrapper=NN_name:skill-name ...]
              --templates=<skill-dir>/templates [--dry-run] < new_analysis.py

Creates <dest>/ with numbered step stubs in code/, a Snakefile that runs them in
order, run.sh, run.sbatch, the analysis doc (Mycelium's analysis-readme template: <NAME>.md in a
Mycelium repository, README.md elsewhere), and data/ code/ plans/ outputs/ logs/ reports/
(plans/ holds PLAN.md and TRACKER.md; reports/ holds <name>.qmd, a Quarto report skeleton with a
mermaid chain of the steps and one Methods and Results tab per step, for analysis-report to fill). data/ holds symlinks, and code/ holds the steps plus any
linked shared code. Refuses a non-empty <dest>, never
overwrites, and writes nothing outside <dest> except an empty lock file, .<name>.scaffold.lock, that it
leaves in the parent folder. Stdlib-only; runs on Python 3.9+.

--wrapper=NN_name:skill-name adds code/NN_name.sh, a stub that runs a pipeline skill's script from inside the
repository (the gate ignores scripts outside it), with a plan row and a tracker row; it is not in the Snakefile.
The theme files take a theme_set(...) call from an active lucid-coder fig.theme rule when there is one.

--panels adds a manuscript layer: one code/plot_<panel> stub per panel, config/figure_map.tsv and
config/manuscript_checks.json for manuscript-audit, with repository-relative paths. On a non-empty
<dest> it adds only the manuscript files that are missing and never overwrites one that exists.

--migrate moves a run-folder analysis (a Snakefile with RUN/OUT/BASE and outputs/run_*/ folders) to the
step-folder layout. It writes Snakefile.new, run.sh.new, run.sbatch.new, _quarto.yml.new and MIGRATE.md next to the
originals and prints the Snakefile diff; --apply renames the originals to *.pre-0.27 and installs the new files;
--seed step=run copies a step's declared outputs out of a run folder. It never edits code/ or deletes a run folder.
"""

import argparse
import contextlib
import datetime
import difflib
import fcntl
import json
import os
import re
import subprocess
import shutil
import tempfile
import sys

ap = None  # hooks/analysis_paths.py, loaded by load_paths from --templates


def load_paths(templates):
    """Import the shared resolver. This script runs from stdin, so it finds hooks/ from --templates
    (<plugin>/skills/new-analysis/templates)."""
    global ap
    hooks = os.path.join(os.path.abspath(templates), "..", "..", "..", "hooks")
    sys.dont_write_bytecode = True
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    import analysis_paths
    ap = analysis_paths


PANEL = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*)\.(R|py)$")
STEP = re.compile(r"^(\d{2})_([A-Za-z0-9][A-Za-z0-9_-]*)(?:\.(R|py|ipynb|qmd|marimo\.py))?$")
FORMATS = ("R", "py", "ipynb", "qmd", "marimo")
EXT = {"marimo": "marimo.py"}  # the file suffix of a format, where it differs from its name
DEFAULT_STEPS = "01_prepare.R,02_fit.R,03_show.R"
DEFAULT_NAMES = ("01_prepare", "02_fit", "03_show")  # --format gives these one extension
STATE_DIR = ".mycelium-extra"  # holds gate.json, whose "step_format" is the repository default
LANGS = {"r": "R", "python": "py"}  # --lang for a qmd step: knitr (R) or jupyter (Python)
DIRS = ["data", "code", "plans", "outputs", "logs", "reports"]
UNTRACKED_OK = {"outputs/", "logs/"}  # often ignored on purpose (large or regenerable files)
OUTPUT_EXT = {"R": ".rds", "py": ".parquet"}
MYCELIUM_TEMPLATE = os.path.join("skills", "core", "templates", "analysis-readme.md")
SHOW = re.compile(r"_show$")  # a script step named NN_show is the figure step: it writes figures/ and source_data/
THEMES = ("report.scss", "report-dark.scss")  # Quarto theme from DESIGN.md, copied under reports/
MYCELIUM_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
CODE_THEMES = ("theme.R", "theme.py")  # the shared plot style, written to code/
FINDINGS_HINT = ("<!-- One bullet per result: the claim, its .living/findings ID once crystallized, "
                 "and a link to its saved, inspected plot and panel. Plots are the primary interpretive outputs; "
                 "use a table only as an explicit fallback with a reason a plot cannot convey the evidence. "
                 "End with a tag naming the outputs/ file behind it: [agent-derived: `outputs/<file>`]. -->")


class Refusal(Exception):
    pass


def git(cwd, *args):
    try:
        return subprocess.run(["git", "-C", cwd] + list(args), stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, encoding="utf-8", errors="replace")
    except OSError:
        return None


def canonical(path):
    """Absolute path with symlinked parents resolved, keeping the last component as named."""
    path = os.path.abspath(path)
    return os.path.join(os.path.realpath(os.path.dirname(path)), os.path.basename(path))


def inside(path, root):
    return root is not None and (path == root or path.startswith(root.rstrip(os.sep) + os.sep))


def display(path, root):
    return os.path.relpath(path, root) if inside(path, root) else path


def parse_steps(text, fmt, lang):
    steps, previous = [], -1
    for name in [part.strip() for part in text.split(",") if part.strip()]:
        match = STEP.match(name)
        kind = match and ("marimo" if match.group(3) == "marimo.py" else match.group(3) or fmt)
        if not kind:
            raise Refusal("step {!r} must look like NN_name.R, NN_name.py, NN_name.ipynb, NN_name.qmd or NN_name.marimo.py "
                          "(or NN_name with --format)".format(name))
        name = "{}.{}".format(match.group(0), EXT.get(kind, kind)) if not match.group(3) else name
        number = int(match.group(1))
        if number <= previous:
            raise Refusal("step numbers must increase: {} comes after {:02d}".format(name, previous))
        previous = number
        stem = "{}_{}".format(match.group(1), match.group(2))
        step_lang = lang if kind == "qmd" else "r" if kind == "R" else "python"
        show = kind in ("R", "py") and bool(SHOW.search(stem))
        steps.append({"file": name, "path": "code/" + name, "num": match.group(1), "stem": stem, "kind": kind,
                      "lang": step_lang, "rule": "step" + re.sub(r"\W", "_", stem), "show": show,
                      "dir": "outputs/" + stem,  # the step's own folder; a rerun overwrites it
                      "html": "outputs/{0}/{0}.html".format(stem) if kind == "qmd" else None,
                      "executed": name if kind == "ipynb" else None,
                      "stub": "stub_{}.qmd".format(step_lang) if kind == "qmd" else
                      "stub_marimo.py" if kind == "marimo" else "stub_show." + kind if show else "stub." + kind})
    if not steps:
        raise Refusal("--steps is empty")
    for step, after in zip(steps, steps[1:] + [None]):  # a table both languages read when the next step differs
        ext = ".tsv" if after and after["lang"] != step["lang"] else OUTPUT_EXT[LANGS[step["lang"]]]
        if step["show"]:  # figures and their plotted table share the step's stem (layout contract, rule 3)
            step["outs"] = ["figures/{}.png".format(step["stem"]), "figures/{}.pdf".format(step["stem"]),
                            "source_data/{}.tsv".format(step["stem"])]
            step["rel_out"] = step["outs"][-1]
        else:
            step["rel_out"] = step["stem"] + ext
            step["outs"] = [step["rel_out"]]
        step["output"] = "{}/{}".format(step["dir"], step["rel_out"])  # outputs/<stem>/..., for docs and stubs
    for before, step in zip([None] + steps, steps):
        step["rel_in"] = before["rel_out"] if before else None
        step["input"] = before["output"] if before else None
        step["in_stem"] = before["stem"] if before else None
    return steps


ENV_FILE = "lucid-coder.yaml"  # lucid-coder's env pointer: env.r and env.python, or env.prefix, name the interpreters
# ponytail: line match on lucid-coder's flat env block, no YAML parser; parse properly if the file grows nested r:/python: keys
ENV_LINE = re.compile(r"^\s+(manager|name|prefix|r|python):\s*[\"']?([^\"'#\s]+)")
ENV_HEAD = re.compile(r"^env:\s*(#.*)?$")


def interpreters(root):
    """Rscript, python and jupyter from lucid-coder.yaml at the root, each kept only when the file exists;
    bare names otherwise. env.r and env.python win; without them (the pixi form /lucid-coder:align writes:
    manager, name, prefix) the interpreters are <prefix>/bin/Rscript and <prefix>/bin/python.
    Returns (paths, used, note)."""
    found = {"rscript": "Rscript", "python": "python", "jupyter": "jupyter"}
    path = os.path.join(root, ENV_FILE) if root else None
    if not path or not os.path.isfile(path):
        return found, [], "environment: none recorded; run /lucid-coder:align to write lucid-coder.yaml"
    try:
        lines = ap.read(path, "strict").splitlines()
    except (OSError, ValueError):  # unreadable or not UTF-8
        return found, [], "environment: WARNING: {} could not be read; kept the bare names on PATH".format(ENV_FILE)
    values, in_env = {}, False
    for line in lines:  # only the top-level env: block counts
        if line.strip() and not line.startswith((" ", "\t", "#")):
            in_env = bool(ENV_HEAD.match(line))
        match = in_env and ENV_LINE.match(line)
        if match:
            values.setdefault(match.group(1), match.group(2))
    named = {tool: os.path.abspath(os.path.join(root, os.path.expanduser(values[key])))
             for key, tool in (("r", "rscript"), ("python", "python")) if key in values}
    prefix = values.get("prefix") or (".pixi/envs/" + values["name"]
                                      if values.get("manager") == "pixi" and values.get("name") else None)
    derived = {}  # from the prefix: kept only when the file exists, so a python-only env raises no warning
    if prefix:
        bindir = os.path.abspath(os.path.join(root, os.path.expanduser(prefix), "bin"))
        derived = {tool: os.path.join(bindir, exe) for tool, exe in (("rscript", "Rscript"), ("python", "python"))
                   if tool not in named}
    chosen = dict(derived, **named)
    if "python" in chosen:
        chosen["jupyter"] = os.path.join(os.path.dirname(chosen["python"]), "jupyter")
    used = sorted(k for k, v in chosen.items() if os.path.isfile(v))
    missing = sorted(k for k in named if k not in used)
    found.update({k: chosen[k] for k in used})
    note = "environment: {} from {}".format(", ".join(used) or "nothing", ENV_FILE)
    if any(k in derived for k in used):
        note += " (from the prefix: " + ", ".join(sorted(k for k in used if k in derived)) + ")"
    if missing:
        note += "; WARNING: {} in {} is not a file, kept the bare name".format(", ".join(missing), ENV_FILE)
    unresolved = [exe for tool, exe in (("rscript", "Rscript"), ("python", "python")) if tool not in used]
    if unresolved and values.get("manager") == "pixi" and values.get("name"):
        note += "; no {} found for the pixi env, so run the Snakefile as `pixi run -e {} bash run.sh`".format(
            " or ".join("bin/" + exe for exe in unresolved), values["name"])
    return found, used, note


RULES_SECONDS = 5  # a slow or hung rules.js must never hold up a scaffold
CALL_CHARS = re.compile(r"^[A-Za-z0-9_.:,=()\"' +*/<>~!&|-]{1,400}$")  # no ; ` $ { } # newline: one plain call
THEME_TOKEN = re.compile(
    r"\s*(?:(?P<string>\"[^\"]*\"|'[^']*')|(?P<number>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
    r"|(?P<name>[A-Za-z_][A-Za-z0-9_.]*(?:::[A-Za-z_][A-Za-z0-9_.]*)?)|(?P<punct>[(),=+-]))")
GGPLOT2_THEMES = {"theme_grey", "theme_gray", "theme_bw", "theme_linedraw", "theme_light", "theme_dark",
                  "theme_minimal", "theme_classic", "theme_void", "theme_test"}
THEME_HELPERS = re.compile(r"theme|element_[a-z_]+|unit|margin|rel|c")
THEME_CONSTANTS = {"TRUE", "FALSE", "NULL", "NA", "Inf", "True", "False", "None"}


def safe_theme_call(call, lang):
    """The packages a `theme_set(...)` call names with `::` when the call is only a chain of theme functions
    with literal arguments, else None. An allow-list: the outer call is theme_set; every other call is a
    ggplot2 theme, `pkg::theme_*`, `theme`, `element_*`, `unit`, `margin`, `rel` or `c` (Python: `theme_*`,
    `theme`, `element_*`, `plotnine.` ones); arguments are strings, numbers, TRUE/FALSE/NULL/NA, names before
    `=`, and `+`. So `get("system")(...)` and `do.call(...)` are refused, not only `system(`."""
    if not CALL_CHARS.match(call) or not call.startswith("theme_set(") or not call.endswith(")"):
        return None
    packages, pos, prev = [], 0, None
    while pos < len(call):
        match = THEME_TOKEN.match(call, pos)
        if not match or match.end() == pos:
            return None if call[pos:].strip() else packages
        pos, kind = match.end(), match.lastgroup
        text = match.group(kind)
        following = call[pos:].lstrip()[:1]
        if kind == "name":
            package, _, func = text.rpartition("::") if "::" in text else ("", "", text)
            if following == "(":
                if lang == "R":
                    ok = (func == "theme_set" and not package and prev is None) or (
                        func.startswith("theme_") if package else func in GGPLOT2_THEMES) or (
                        not package and THEME_HELPERS.fullmatch(func))
                else:
                    head, dot, tail = text.rpartition(".")
                    ok = (text == "theme_set" and prev is None) or (
                        (not dot or head == "plotnine") and re.fullmatch(r"theme(_[a-z0-9_]+)?|element_[a-z_]+", tail))
                if not ok or "." in package:
                    return None
                if package and package not in packages:
                    packages.append(package)
            elif not (following == "=" or text in THEME_CONSTANTS):
                return None
        prev = text
    return packages


def lucid_coder_root():
    """lucid-coder's plugin folder, or None. MX_LUCID_CODER_ROOT (tests only) names it directly, "" for none;
    otherwise installed_plugins.json lists it: the user-scope entry first, then the newest."""
    override = os.environ.get("MX_LUCID_CODER_ROOT")
    if override is not None:
        return override or None
    config = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    try:
        with open(os.path.join(config, "plugins", "installed_plugins.json"), encoding="utf-8") as handle:
            plugins = json.load(handle)["plugins"]
        entries = [e for key, found in plugins.items() if key.split("@")[0] == "lucid-coder" for e in found]
        entries.sort(key=lambda e: (e.get("scope") == "user", str(e.get("lastUpdated", ""))), reverse=True)
        return next((e["installPath"] for e in entries if os.path.isfile(
            os.path.join(e["installPath"], "scripts", "rules.js"))), None)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def active_rules():
    """(rules, why not): lucid-coder's active learned rules through its own CLI, read only.
    Never raises: node missing, a timeout, an error exit or malformed JSON each give ([], reason)."""
    root = lucid_coder_root()
    if not root or not os.path.isfile(os.path.join(root, "scripts", "rules.js")):
        return [], "lucid-coder is not installed"
    node = shutil.which("node")
    if not node:
        return [], "node is not on PATH"
    env = dict(os.environ)  # rules.js reads its store from the data folder the lucid-coder hooks left a pointer to
    env.pop("CLAUDE_PLUGIN_DATA", None)  # this plugin's own data folder is not lucid-coder's
    pointer = os.path.join(env.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"), ".lucid-coder-data")
    try:
        with open(pointer, encoding="utf-8") as handle:
            pointed = handle.read().strip()
        if pointed:
            env["CLAUDE_PLUGIN_DATA"] = pointed
    except OSError:
        pass
    seconds = float(os.environ.get("MX_RULES_SECONDS") or RULES_SECONDS)  # the override is for tests
    try:
        done = subprocess.run([node, os.path.join(root, "scripts", "rules.js"), "list", "--status", "active", "--json"],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                              encoding="utf-8", errors="replace", timeout=seconds, env=env)
    except subprocess.TimeoutExpired:
        return [], "reading the rules took more than {:g} s".format(seconds)
    except (OSError, subprocess.SubprocessError):
        return [], "rules.js could not run"
    if done.returncode != 0:
        return [], "rules.js exited {}".format(done.returncode)
    try:
        rules = json.loads(done.stdout)
    except ValueError:
        return [], "rules.js printed no JSON"
    if not isinstance(rules, list):
        return [], "rules.js printed no list"
    return [r for r in rules if isinstance(r, dict)], None


def theme_call(text):
    """The first theme_set(...) call in a rule's text, parentheses balanced and quotes skipped; None when
    the text has none or never closes it."""
    found = re.search(r"\btheme_set\(", text or "")
    if not found:
        return None
    depth, quote, i = 0, None, found.end() - 1
    while i < len(text):
        char = text[i]
        if quote:
            if char == "\\":
                i += 1
            elif char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[found.start():i + 1]
        i += 1
    return None


def language_tag(lang):
    return "R" if lang == "R" else "py"


def learned_theme(rules, lang):
    """(rule id, theme_set call) of the newest active fig.theme rule scoped to this language ("r" or "py")
    whose text holds a plain theme_set(...) call; None otherwise."""
    language = "r" if lang == "R" else "python"
    found = []
    for rule in rules:
        scope = rule.get("scope") if isinstance(rule.get("scope"), dict) else {}
        call = theme_call(rule.get("statement") if isinstance(rule.get("statement"), str) else "")
        if (rule.get("topic") == "fig.theme" and rule.get("status", "active") == "active"
                and scope.get("kind") == "language" and scope.get("language") == language
                and isinstance(rule.get("id"), str) and call
                and safe_theme_call(call, language_tag(lang)) is not None):
            found.append((rule["id"], call))
    return max(found) if found else None


def theme_text(template, lang, rules, why):
    """(theme file text, note) for code/theme.R (lang "R") or code/theme.py ("py")."""
    name = "code/theme." + lang
    language = "R" if lang == "R" else "Python"
    learned = learned_theme(rules, lang)
    if lang == "R":
        # A learned call names its own packages (`pkg::`); the template already attaches ggplot2.
        packages = [p for p in safe_theme_call(learned[1], "R") if p != "ggplot2"] if learned else ["ggpubr"]
        fallback = "theme_set(ggpubr::theme_pubr(base_size = 8))"
        values = {"THEME_NEEDS": " and ".join(["ggplot2"] + packages),
                  "THEME_LIBRARIES": "\n".join("  library({})".format(p) for p in packages),
                  "THEME_CALL": learned[1] if learned else fallback}
        used = "theme_pubr(base_size = 8)"
    else:
        fallback = 'theme_set(theme_classic(base_size=8) + theme(legend_position="top", plot_caption=element_text(ha="left")))'
        call = learned[1] if learned else fallback
        modules = sorted(set(re.findall(r"(?<![\w.])([A-Za-z_]\w*)\.\w+\(", call)))
        names = sorted(set(re.findall(r"(?<![\w.])([A-Za-z_]\w*)\(", call)) - set(modules) | {"theme_set"})
        values = {"THEME_NEEDS": "plotnine", "THEME_CALL": call,
                  "THEME_IMPORTS": "\n".join(["import " + m for m in modules]
                                             + ["from plotnine import " + ", ".join(names)])}
        used = "plotnine theme_classic(base_size=8)"
    if learned:
        values["THEME_SOURCE"] = ("From learned rule {} (lucid-coder, topic fig.theme); "
                                  "change it with /lucid-coder:learn.".format(learned[0]))
        note = "theme from learned rule {} in {}.".format(learned[0], name)
    else:
        reason = "no active fig.theme rule for {}{}".format(language, "; " + why if why else "")
        values["THEME_SOURCE"] = "The shipped fallback ({}).".format(reason)
        note = "{} uses the shipped {} fallback ({}).".format(name, used, reason)
    return ap.fill(template, values), note


def step_format(args, root):
    """(format, where it came from): --format, else step_format in gate.json, else (None, None)."""
    if args.format:
        return args.format, "--format"
    if root is None:
        return None, None
    try:
        with open(os.path.join(root, STATE_DIR, "gate.json"), encoding="utf-8") as handle:
            value = json.load(handle).get("step_format")
    except OSError:
        return None, None
    except (ValueError, AttributeError):
        print("note: {}/gate.json does not parse; its step_format was ignored.".format(STATE_DIR))
        return None, None
    if value is None:
        return None, None
    if value not in FORMATS:
        raise Refusal('"step_format" in {}/gate.json must be one of {}; got {!r}'.format(
            STATE_DIR, ", ".join(FORMATS), value))
    return value, "step_format in {}/gate.json".format(STATE_DIR)


def parse_panels(text):
    panels, seen = [], set()
    for name in [part.strip() for part in text.split(",") if part.strip()]:
        match = PANEL.match(name)
        if not match:
            raise Refusal("panel {!r} must look like Fig1a.R or Fig1a.py".format(name))
        if match.group(1) in seen:
            raise Refusal("panel {} is named twice".format(match.group(1)))
        seen.add(match.group(1))
        panels.append({"id": match.group(1), "kind": match.group(2), "file": "plot_" + name,
                       "path": "code/plot_" + name})
    if not panels:
        raise Refusal("--panels is empty")
    return panels


WRAPPER = re.compile(r"^(\d{2})_([A-Za-z0-9][A-Za-z0-9_-]*):([a-z0-9][a-z0-9-]*)$")


def parse_wrappers(values, steps):
    """--wrapper=NN_name:skill-name, repeatable: a code/NN_name.sh stub that calls a pipeline skill's script."""
    wrappers = []
    for value in values or []:
        match = WRAPPER.match(value)
        if not match:
            raise Refusal("--wrapper {!r} must look like NN_name:skill-name (e.g. 04_de:pseudobulk-de)".format(value))
        stem = "{}_{}".format(match.group(1), match.group(2))
        if any(stem == w["stem"] or match.group(1) == w["num"] for w in wrappers) or any(
                match.group(1) == s["num"] or stem == s["stem"] for s in steps):
            raise Refusal("wrapper {} reuses the number or name of another step or wrapper".format(stem))
        wrappers.append({"file": stem + ".sh", "path": "code/" + stem + ".sh", "num": match.group(1), "stem": stem,
                         "skill": match.group(3), "dir": "outputs/" + stem})
    return wrappers


def wrapper_text(template, wrapper, name):
    """The wrapper stub; names the skill's own scripts when lucid-coder's folder holds that skill."""
    root = lucid_coder_root()
    skill_dir = os.path.join(root, "skills", wrapper["skill"]) if root else None
    scripts = sorted(os.listdir(os.path.join(skill_dir, "scripts"))) if skill_dir and os.path.isdir(
        os.path.join(skill_dir, "scripts")) else []
    return ap.fill(template, {
        "FILE": wrapper["file"], "NUM": wrapper["num"], "NAME": name, "SKILL": wrapper["skill"],
        "PATH": wrapper["path"], "DIR": wrapper["dir"],
        "SCRIPT_HINT": "# Scripts in the skill: " + ", ".join(scripts[:8]) if scripts else
        "# Name the script and its arguments below; the skill's SKILL.md lists them."})


PANELS_DIR = "outputs/panels"  # manuscript panels have their own folder, outside every numbered step


def panel_dir(steps):
    """The folder panels write into: outputs/panels, whatever the steps are."""
    return PANELS_DIR


def existing_panel_dir(dest):
    """The same folder for a folder that already has steps."""
    return PANELS_DIR


def manuscript_files(panels, panel_dir, name, dest_rel, root, templates):
    """Plot stubs, the figure map and the manuscript-audit contract, every path repository-relative."""
    current = "{}/{}".format(dest_rel, panel_dir)  # the folder the panels write into
    files, rows, figures = {}, [], []
    for panel in panels:
        script = dest_rel + "/" + panel["path"]
        source = "{}/source_data/{}.tsv".format(current, panel["id"])
        output = "{}/figures/{}.pdf".format(current, panel["id"])
        files[panel["path"]] = ap.fill(ap.read(os.path.join(templates, "plot_panel." + panel["kind"])), {
            "FILE": panel["file"], "PANEL": panel["id"], "NAME": name, "PATH": script, "DEST": dest_rel})
        rows.append("\t".join([panel["id"], script, source, output, "[claim]", "draft"]))
        figures.append({"id": panel["id"], "script": script, "source_data": source,
                        "required_columns": ["label", "y"], "outputs": [output]})
    files["config/figure_map.tsv"] = "\n".join(["figure\tscript\tsource_data\toutput\tclaim\tstatus"] + rows) + "\n"
    contract = {"schema": "mycelium-extra.manuscript_checks.v1", "figure_map": dest_rel + "/config/figure_map.tsv",
                "figures": figures}
    if os.path.isfile(os.path.join(root, "data", "DATA_MANIFEST.md")):
        contract["data_manifest"] = "data/DATA_MANIFEST.md"
    files["config/manuscript_checks.json"] = json.dumps(contract, indent=2) + "\n"
    return files


def checked(path, text):
    """Refuse a file with an unfilled placeholder or a Python stub that does not compile."""
    if "@@" in text:
        raise Refusal("unresolved template placeholder in " + path)
    if path.endswith(".py"):
        compile(text, path, "exec")


def manuscript_root(dest):
    root = ap.living_root(dest)
    if root is None:
        raise Refusal("--panels needs a git or Mycelium repository: the contract names repository-relative paths")
    if root == dest:
        raise Refusal("{} is the repository root".format(dest))
    return root


def figure_map_ids(path):
    return {line.split("\t")[0] for line in ap.read(path, "strict").splitlines()[1:]}


def contract_ids(path):
    try:
        return {figure["id"] for figure in json.loads(ap.read(path, "strict"))["figures"]}
    except (ValueError, KeyError, TypeError):
        return set()


def add_panels(args, dest):
    """Retrofit a non-empty folder: write each missing manuscript file, keep every one that exists."""
    root = manuscript_root(dest)
    dest_rel = display(dest, root).replace(os.sep, "/")
    files = manuscript_files(parse_panels(args.panels), existing_panel_dir(dest), os.path.basename(dest), dest_rel,
                             root, args.templates)
    for folder in ("code", "config"):
        if os.path.islink(os.path.join(dest, folder)):
            raise Refusal("{}/{} is a symlink; nothing was changed".format(dest_rel, folder))
    for path, text in files.items():
        checked(path, text)
    for panel in parse_panels(args.panels):
        other = os.path.join(dest, "code", "plot_{}.{}".format(panel["id"], "py" if panel["kind"] == "R" else "R"))
        if os.path.lexists(other):
            raise Refusal("{} exists, so panel {} cannot also be a {} script; nothing was changed".format(
                display(other, root), panel["id"], panel["kind"]))
    missing = [path for path in sorted(files) if not os.path.lexists(os.path.join(dest, path))]
    print("{} {}/ (manuscript files only; existing files are kept)".format(
        "would add to" if args.dry_run else "added to", dest_rel))
    for path in sorted(files):
        print("  {} {}".format(("would add" if args.dry_run else "added") if path in missing else "kept", path))
    for path, known in (("config/figure_map.tsv", figure_map_ids), ("config/manuscript_checks.json", contract_ids)):
        if path not in missing:
            for panel in parse_panels(args.panels):
                if panel["id"] not in known(os.path.join(dest, path)):
                    print("WARNING: {} not in kept {}".format(panel["id"], path))
    if args.dry_run:
        return 0
    for path in missing:
        os.makedirs(os.path.dirname(os.path.join(dest, path)), exist_ok=True)
        with open(os.path.join(dest, path), "x", encoding="utf-8") as handle:  # "x": never overwrite
            handle.write(files[path])
    return 0


def plan_links(paths, kind, dest, root):
    links, names = [], set()
    for raw in paths or []:
        if not os.path.exists(raw):
            raise Refusal("--{} target does not exist: {}".format(kind, raw))
        target = canonical(raw)
        name = os.path.basename(target)
        if name in names:
            raise Refusal("two --{} targets are both named {}".format(kind, name))
        names.add(name)
        link_dir = os.path.join(dest, kind)
        value = (os.path.relpath(target, link_dir) if inside(target, root) and inside(dest, root)
                 else target)
        links.append({"path": os.path.join(link_dir, name), "rel": kind + "/" + name,
                      "target": target, "value": value})
    return links


def replace_line(text, prefix, lines):
    """Swap the first line starting with prefix for lines; keep the template if lines is empty."""
    if not lines:
        return text
    out, done = [], False
    for line in text.split("\n"):
        if not done and line.startswith(prefix):
            out.extend(lines)
            done = True
        else:
            out.append(line)
    return "\n".join(out)


def stub_values(step, name, data_links):
    first = step["input"] is None
    if first:
        source = ", ".join(link["rel"] for link in data_links) or "data/ (link the inputs there)"
        notebook_input = data_links[0]["rel"] if data_links else "data/"
    else:
        source = notebook_input = step["input"]
    usage = step["output"] if first else "{} {}".format(step["input"], step["output"])
    if step["show"]:  # the Snakefile passes the input and the step folder; the script derives every output path
        usage = step["dir"] if first else "{} {}".format(step["input"], step["dir"])
    if step["kind"] == "R":
        code = ("output_path <- args[[1]]" if first
                else "input_path <- args[[1]]\noutput_path <- args[[2]]")
        if step["show"]:
            code = "step_dir <- args[[1]]" if first else "input_path <- args[[1]]\nstep_dir <- args[[2]]"
    else:
        code = ("(output_path,) = sys.argv[1:]" if first
                else "input_path, output_path = sys.argv[1:]")
        if step["show"]:
            code = "(step_dir,) = sys.argv[1:]" if first else "input_path, step_dir = sys.argv[1:]"
    return {"FILE": step["file"], "PATH": step["path"], "NUM": step["num"], "NAME": name,
            "INPUT": notebook_input if step["kind"] in ("ipynb", "qmd", "marimo") else source,
            "INPUT_PY": "Path({})".format(json.dumps(notebook_input)) if first
            else "OUTPUTS / {} / {}".format(json.dumps(step["in_stem"]), json.dumps(step["rel_in"])),
            "INPUT_R": json.dumps(notebook_input) if first
            else "file.path(OUTPUTS, {}, {})".format(json.dumps(step["in_stem"]), json.dumps(step["rel_in"])),
            "OUTPUT_PY": "STEP / {}".format(json.dumps(step["rel_out"])),
            "OUTPUT_R": "file.path(STEP, {})".format(json.dumps(step["rel_out"])),
            "STEM": step["stem"], "DIR": step["dir"],
            "OUTPUT": step["output"], "USAGE": usage, "NARGS": "1" if first else "2",
            "ARGS_CODE": code}


def notebook(template, values):
    book = json.loads(template)
    for cell in book["cells"]:
        cell["source"] = [ap.fill(line, values) for line in cell["source"]]
    return json.dumps(book, indent=1) + "\n"


def rule(step, data_links):
    out = step["dir"]  # outputs/<stem>: this step's own folder, overwritten on a rerun
    lines = ["rule {}:".format(step["rule"]), "    input:"]
    if step["input"]:
        lines.append('        prev="{}",'.format(step["input"]))
    elif data_links:
        lines.append("        data=[{}],".format(", ".join(json.dumps(l["rel"]) for l in data_links)))
    key = "notebook" if step["kind"] in ("ipynb", "marimo") else "script"
    lines.append('        {}="{}",'.format(key, step["path"]))
    lines += ["    output:"] + ['        "{}/{}",{}'.format(out, o, "  # TODO: name the real outputs" if i == 0 else "")
                               for i, o in enumerate(step["outs"])]
    if step["executed"]:
        lines.append('        "{}/{}",'.format(out, step["executed"]))
    if step["html"]:
        lines.append('        "{}",'.format(step["html"]))
    lines += ["    threads: 1",
              "    log:", '        "{}/logs/{}.log",'.format(out, step["stem"]),
              "    benchmark:", '        "{}/logs/{}.benchmark.tsv"'.format(out, step["stem"]),
              "    shell:"]
    prev = " {input.prev:q}" if step["input"] else ""
    where = "STEP_DIR={} OUTPUTS=outputs ".format(out)  # notebooks and qmd pages find their folders here
    if step["kind"] == "ipynb":
        command = (where + "{{JUPYTER:q}} nbconvert --to notebook --execute {{input.notebook:q}} "
                   "--output-dir {} --output {} > {{log:q}} 2>&1".format(out, step["file"]))
    elif step["kind"] == "marimo":  # a marimo notebook is a Python file: run it headless as a script
        command = where + "{PYTHON:q} -u {input.notebook:q} > {log:q} 2>&1"
    elif step["kind"] == "qmd":  # --output-dir mirrors the source path (code/), so move the page up; embed-resources leaves no other file
        command = (where + "{{QUARTO:q}} render {{input.script:q}} --output-dir {0} > {{log:q}} 2>&1 && "
                   "mv {0}/code/{1}.html {2} && rmdir {0}/code".format(out, step["stem"], step["html"]))
    else:  # a figure step gets its step folder and derives its outputs; any other script gets its one output
        tool = "{RSCRIPT:q}" if step["kind"] == "R" else "{PYTHON:q} -u"
        command = tool + " {input.script:q}" + prev + (" " + out if step["show"] else " {output:q}") + " > {log:q} 2>&1"
    lines.append('        THREADS + "{}"'.format(command))
    return "\n".join(lines) + "\n"


def doc_text(template, name, dest_rel, steps, data_links, code_links, root):
    text = re.sub(r"<!-- NAMING:.*?-->\s*", "", template, count=1, flags=re.S)
    text = text.replace("# [Analysis Name]", "# " + name, 1)
    text = text.replace("analysis/[analysis-name]", dest_rel).replace("[analysis-name]", name)
    text = replace_line(text, "- `[dataset-name]`", [
        "- `{}` → `{}`: [how this analysis uses it]".format(l["rel"], display(l["target"], root))
        for l in data_links])
    text = replace_line(text, "- `[algorithm-name]`", [
        "- `{}` → `{}`: [what it provides]".format(l["rel"], display(l["target"], root))
        for l in code_links])
    text = replace_line(text, "| `outputs/[filename]`", [
        "| `{}/{}` | [description] (step {}) |".format(s["dir"], out, s["num"])
        for s in steps for out in s["outs"]]
        + ["| `outputs/numbers.json` | Reportable values, written by `register_value` |"])
    if "<!-- Update as work progresses" in text:
        text = replace_line(text, "<!-- Update as work progresses", [FINDINGS_HINT])
    else:
        text = text.replace("## Key Findings\n", "## Key Findings\n\n" + FINDINGS_HINT + "\n", 1)
    section = "\n".join(
        ["## Steps", "",
         "Run in number order; `bash run.sh` runs them all through the `Snakefile`. Each step writes its own folder, "
         "`outputs/<step>/`, and a rerun overwrites it; `logs/CHANGES.md` records what changed.",
         "Plan: [plans/PLAN.md](plans/PLAN.md). Status and log: [plans/TRACKER.md](plans/TRACKER.md).", "",
         "Note for the agent: scripts live in `code/`, not in a `scripts/` folder. Each script writes only "
         "`outputs/<its stem>/`, never loose files next to `outputs/.layout`.", "",
         "| Step | File | Does | Output |", "|---|---|---|---|"]
        + ["| {} | `{}` | [what it does] | `{}` |".format(s["num"], s["path"], s["output"])
           for s in steps]) + "\n"
    if "\n## Reproducibility" in text:
        return text.replace("\n## Reproducibility", "\n" + section + "\n## Reproducibility", 1)
    return text.rstrip("\n") + "\n\n" + section


def report_text(template, name, doc_name, dest_rel, steps, data_links):
    """The Quarto report: a mermaid chain of the steps, one Methods and one Results tab per step."""
    nodes = []
    for step in steps:
        nodes.append('s{0}["{1}"] --> o{0}[("{2}")]'.format(step["num"], step["path"], step["output"]))
    lines = ["flowchart LR"]
    if data_links:
        lines.append("    " + " & ".join('d{}[("{}")]'.format(i, l["rel"]) for i, l in enumerate(data_links))
                     + " --> " + nodes[0])
    else:
        lines.append("    " + nodes[0])
    for before, node in zip(steps, nodes[1:]):
        lines.append("    o{} --> {}".format(before["num"], node))
    methods, results = [], []
    for step in steps:
        title = "### {} {}".format(step["num"], step["stem"][3:].replace("_", " "))
        methods.append("\n".join([
            title, "",
            "[What this step does, in two sentences.] Script: [`{0}`](../{0}). Output: `{1}`."
            .format(step["path"], step["output"]), "",
            '```{{.{} filename="{}"}}'.format(step["lang"], step["path"]),
            "# [the 5-15 lines that do the work, with their line range]", "```", ""]))
        figure = "{}/figures/{}_[what-it-shows].png".format(step["dir"], step["num"])
        results.append("\n".join([
            title, "",
            "**Question.** [What this tab answers, as one question.]", "",
            "**Approach.** [The data, the model or test, the multiplicity family, in one or two sentences.]", "",
            "**Conclusion.** [The answer with its size and what it does not show.]", "",
            "- [Conclusion] ([figure](../{0}), panel A). [agent-derived: `{0}`]".format(figure), "",
            "![Figure N. [caption]. `{0}`](../{0})".format(figure), "",
            "Inspected `{}`: [groups, n, axes, interval type; any defect].".format(figure), ""]))
    return ap.fill(template, {"NAME": name, "DOC": doc_name, "DEST": dest_rel.replace(os.sep, "/"),
                           "MERMAID": "\n".join(lines), "METHODS": "\n".join(methods),
                           "RESULTS": "\n".join(results)})


def manifest_entry(root, basename):
    """The DATA_MANIFEST.md entry that mentions `basename`: its nearest heading, else "listed"; "not listed"
    when the manifest is missing or does not mention it."""
    try:
        lines = ap.read(os.path.join(root, "data", "DATA_MANIFEST.md")).splitlines()
    except (OSError, TypeError):
        return "not listed"
    heading = ""
    for line in lines:
        if line.startswith("#"):
            heading = line.lstrip("#").strip().strip("`")
        if basename in line:
            return heading or "listed"
    return "not listed"


def source_rows(data_links, root):
    """One data/SOURCES.md row per --data link; the plan column stays empty until a plan names the file."""
    return ["| `{}` | `{}` | {} | |".format(os.path.basename(l["target"]), display(l["target"], root),
                                          manifest_entry(root, os.path.basename(l["target"])))
            for l in data_links]


def report_rows(name, has_report):
    """reports/README.md rows: what the scaffold wrote there, with no run yet."""
    rows = []
    if has_report:
        rows += ["| `{}.qmd` | the record | | analysis-report |".format(name),
                 "| `{}.html` | its render | | quarto render |".format(name)]
    rows.append("| `report.scss`, `report-dark.scss` | theme, DESIGN.md tokens | — | you |")
    return rows


def find_doc_template(option, root, templates):
    if option:
        if not os.path.isfile(option):
            raise Refusal("--doc-template not found: {}".format(option))
        return option, option
    if root:
        try:
            plugin = ap.read(os.path.join(root, ".mycelium", "plugin-root")).strip()
        except OSError:
            plugin = ""
        candidate = os.path.join(plugin, MYCELIUM_TEMPLATE) if plugin else ""
        if candidate and os.path.isfile(candidate):
            return candidate, "Mycelium's template at " + candidate
    return (os.path.join(templates, "analysis-readme.md"),
            "the bundled copy of Mycelium 0.7.2's template")


def ignored(root, probes):
    """Map each probe path that git ignores to the rule that ignores it."""
    rels = {os.path.relpath(path, root): shown for path, shown in probes if inside(path, root)}
    if not rels:
        return {}
    result = git(root, "check-ignore", "-v", "--no-index", *sorted(rels))
    if result is None or result.returncode not in (0, 1):
        return {}
    found = {}
    for line in result.stdout.splitlines():
        rule_text, _, rel = line.partition("\t")
        if rel in rels:
            found[rels[rel]] = rule_text
    return found


# ---------------------------------------------------------------- --migrate: run-folder analysis to step folders

OLD = ".pre-0.27"  # suffix of an original that --apply keeps
NN = re.compile(r"^(\d{2}[a-z]?)_")  # the step number of a script, folder or file name
RULE_HEAD = re.compile(r"^rule\s+(\w+)\s*:")
SECTION = re.compile(r"^ {4}(\w+):")
RUN_BLOCK = re.compile(r"^RUN\s*=\s*config\.get\(\s*[\"']run[\"']", re.M)
SCRIPT_KEY = re.compile(r"^\s+(script|notebook)\s*=\s*[\"']code/([^\"']+)[\"']")
SCRIPT_EXT = re.compile(r"\.(marimo\.py|R|py|qmd|ipynb)$")
TOKEN = re.compile(r"\{(OUT|BASE)(?::q)?\}((?:/[^\s\"'>]*)?)")
STRING = re.compile(r"(?<![\w])(?P<f>f?)(?P<q>\"[^\"\n]*\"|'[^'\n]*')|(?P<comment>#.*$)")
RENDER = re.compile(r"\brender\s+\{input\.\w+(?::q)?\}")  # the quarto call of a qmd step, whatever the input is called
STEP_FILE = re.compile(r"""["'/](\d{2}[a-z]?)_[\w.-]*?\.(?:rds|tsv|csv|parquet|h5ad|txt|json|RData|rda|qs|xlsx|loom|mtx|h5|png|pdf|html)\b""")
LEFTOVER = re.compile(r"\b(OUT|BASE|RUN|_BASE_RUN)\b")
HTML_PAGE = re.compile(r"^[\w./-]*?/code/([\w.-]+)\.html$")
CODE_FILES = (".R", ".r", ".py", ".qmd", ".Rmd", ".rmd", ".ipynb", ".sh")
READS = (("dirname", re.compile(r"dirname\(")), ("base_dir", re.compile(r"\b[Bb][Aa][Ss][Ee]_[Dd][Ii][Rr]\b")),
         ("run_dir", re.compile(r"\b[Rr][Uu][Nn]_[Dd][Ii][Rr]\b")), ("file.path(run", re.compile(r"file\.path\(\s*run\b")),
         ("TP_BASE", re.compile(r"\bTP_BASE\b")), ("old run folder", re.compile(r"outputs/run_|\brun_\d{8}_")))
LAYOUT_TEXT = "layout: steps\nversion: 1\n"
CHANGES_HEAD = ("# Change log\n\nOne entry per run.sh run: code files changed since the previous run, and output folders "
                "rewritten. Runs that overlap in time may list the same folders.\n")


def split_rules(text):
    """Cut a Snakefile into ["text", lines, None] and ["rule", lines, name] parts. A rule runs until the next line at
    column 0; its trailing blank lines go to the gap after it."""
    parts, in_rule = [], False
    for line in text.split("\n"):
        head = RULE_HEAD.match(line)
        if head:
            parts.append(["rule", [line], head.group(1)])
            in_rule = True
        elif in_rule and (not line.strip() or line[0] in " \t"):
            parts[-1][1].append(line)
        else:
            in_rule = False
            if not parts or parts[-1][0] != "text":
                parts.append(["text", [], None])
            parts[-1][1].append(line)
    out = []
    for part in parts:
        blanks = 0
        if part[0] == "rule":
            while len(part[1]) > 1 and not part[1][-1].strip():
                part[1].pop()
                blanks += 1
        out.append(part)
        if blanks:
            out.append(["text", [""] * blanks, None])
    return out


def rule_script(lines):
    """(stem, kind) of the rule's script= or notebook= input under code/, else (None, None)."""
    for line in lines:
        match = SCRIPT_KEY.match(line)
        if match:
            ext = SCRIPT_EXT.search(match.group(2))
            if ext:
                return match.group(2)[:ext.start()], ext.group(1)
    return None, None


def flag(line, note):
    """The line with a '# MIGRATE: check' comment, or the note added to the one it has."""
    return line + ("; " if "# MIGRATE: check:" in line else "  # MIGRATE: check: ") + note


def code_end(line):
    """The line without its trailing # comment."""
    for match in STRING.finditer(line):
        if match.group("comment"):
            return line[:match.start()]
    return line


def path_key(rel):
    """A declared path with its wildcard names blanked, so {batch} in one rule matches {b} in another."""
    return re.sub(r"\{+\w+\}+", "{}", rel.strip("/"))


def map_path(which, rel, section, own, producers, directory=False):
    """(new path, reason) for {OUT}/rel or {BASE}/rel. `own` is the stem of the rule when the path is one of its
    own output, log or benchmark paths. A directory() output named like the step keeps its folder, because the step
    folder also holds the other outputs and the log, and Snakemake clears a directory output before the job.
    The reason is None when the path mapped cleanly."""
    segs = [s for s in rel.split("/") if s]
    stem = own
    if stem is None and path_key(rel) in producers.get("paths", {}):  # a rule declares this very file
        stem = producers["paths"][path_key(rel)]
    if stem is None:
        prefix = next((NN.match(s).group(1) for s in segs if NN.match(s)), None)
        found = producers.get(prefix, []) if prefix else []
        if len(found) == 1:
            stem = found[0]
        else:
            return "outputs/" + "/".join(segs), "no single rule outputs a file with this step number; check where it lives"
    here = NN.match(stem).group(1) if NN.match(stem) else None
    if segs and segs[0] != "logs" and here and NN.match(segs[0]) and NN.match(segs[0]).group(1) == here and "." not in segs[0] \
            and not (directory and len(segs) == 1):
        segs = segs[1:]  # the step's own results folder (01b_scar) is the step folder now
    return "/".join(["outputs", stem] + segs), None


def rewrite_literal(match, ctx):
    """Rewrite one string literal of a rule line. Returns the new literal text."""
    text, quote = match.group("q"), match.group("q")[0]
    body, is_f = text[1:-1], bool(match.group("f"))
    stem, kind = ctx["stem"], ctx["kind"]
    page = HTML_PAGE.match(body)
    if page and page.group(1) in ctx["qmd"]:  # a qmd step's page: outputs/<stem>/<stem>.html
        name = page.group(1)
        ctx["changed"] = True
        ctx["page"] = True
        return "{0}{1}outputs/{2}/{2}.html{1}".format("f" if is_f else "", quote, name)
    new = body
    if stem and "RUN_DIR=" in new:  # the folders a notebook or qmd page finds its input and output in
        new, count = re.subn(r"RUN_DIR=\{OUT(?::q)?\}", "STEP_DIR=outputs/{0} OUTPUTS=outputs".format(stem), new)
        ctx["changed"] = ctx["changed"] or bool(count)
    if kind == "qmd" and "--output-dir" not in new and RENDER.search(new):
        out = "outputs/" + stem
        exact = new.endswith("render {input.script:q} > {log:q} 2>&1")  # the scaffold's own command
        if "STEP_DIR=" not in new:
            new, count = re.subn(r"\{QUARTO(?::q)?\}", lambda m: "STEP_DIR={0} OUTPUTS=outputs {1}".format(out, m.group(0)),
                                 new, count=1)
            if not count:
                ctx["notes"].append("the qmd needs STEP_DIR={} OUTPUTS=outputs".format(out))
        call = RENDER.search(new)
        new = new[:call.end()] + " --output-dir " + out + new[call.end():]
        new = "{0} && mv {1}/code/{2}.html {1}/{2}.html && rmdir {1}/code".format(new.rstrip(), out, stem)
        if not exact:
            ctx["notes"].append("the render command had another form; check --output-dir and the moved page")
        ctx["changed"] = True
    if kind == "qmd" and "--output-dir" in new:
        ctx["rendered"] = True

    def token(found):
        which, rel = found.group(1), found.group(2)
        ctx["changed"] = True
        if not rel:  # a bare run folder
            if which == "OUT" and stem:
                ctx["notes"].append("the OUT run folder alone is now this step's folder; check the script that gets it")
                return "outputs/" + stem
            ctx["notes"].append("the " + which + " run folder alone is now outputs/; the script that gets it joins step folders itself")
            return "outputs"
        clean = rel[1:].replace("{{", "{").replace("}}", "}") if is_f else rel[1:]
        own = stem if which == "OUT" and ctx["section"] in ("output", "log", "benchmark") else None
        path, why = map_path(which, rel, ctx["section"], own, ctx["producers"], ctx["directory"])
        if why:
            ctx["notes"].append(why)
        elif own and ctx["section"] in ("log", "benchmark") and stem in ctx["shared"]:
            ctx["notes"].append("another rule runs this script and gets the same {}; give each rule its own file".format(
                ctx["section"]))
        elif own and ctx["section"] == "output" and ctx["pairs"] is not None:
            ctx["pairs"].append((clean, path.replace("{{", "{").replace("}}", "}") if is_f else path))
        return path

    new = TOKEN.sub(token, new)
    if is_f and new != body and "{" not in new.replace("{{", "").replace("}}", ""):  # no f-string expression is left: a plain string
        new, is_f = new.replace("{{", "{").replace("}}", "}"), False
    return "{0}{1}{2}{1}".format("f" if is_f else "", quote, new)


def migrate_snakefile(text, name, dest_rel, templates):
    """The Snakefile in the step layout and a report: (new text, info). info has rules (name, stem, kind),
    pairs (stem -> [(old path under the run, new path)]), folders (old results folder names that differ from a stem)."""
    parts = split_rules(text)
    rules = []
    for part in parts:
        if part[0] == "rule":
            stem, kind = rule_script(part[1])
            rules.append({"name": part[2], "stem": stem, "kind": kind})
    producers, qmd = {"paths": {}}, set()
    for part in parts:  # which rule declares which output file, to tell two rules of the same step number apart
        if part[0] != "rule":
            continue
        stem, section = rule_script(part[1])[0], None
        for line in part[1]:
            section = SECTION.match(line).group(1) if SECTION.match(line) else section
            for literal in STRING.finditer(line):
                for found in (TOKEN.finditer(literal.group(0)) if section == "output" and stem and not literal.group("comment") else ()):
                    if found.group(1) == "OUT" and found.group(2):
                        producers["paths"].setdefault(path_key(found.group(2)), stem)
    for item in rules:
        if item["stem"] and NN.match(item["stem"]):
            producers.setdefault(NN.match(item["stem"]).group(1), []).append(item["stem"])
        if item["kind"] == "qmd":
            qmd.add(item["stem"])
    seen_stems = [r["stem"] for r in rules if r["stem"]]
    shared = {stem for stem in seen_stems if seen_stems.count(stem) > 1}  # two rules run one script
    pairs, out_lines, rewritten, folders = {}, [], 0, set()
    for part in parts:
        if part[0] == "text":
            out_lines.extend(part[1])
            continue
        info = next(r for r in rules if r["name"] == part[2])
        ctx = {"stem": info["stem"], "kind": info["kind"], "qmd": qmd, "producers": producers, "section": None,
               "shared": shared, "rendered": False, "directory": False, "pairs": pairs.setdefault(info["stem"], []) if info["stem"] else None}
        changed_rule, page_at = False, None
        for line in part[1]:
            head = SECTION.match(line)
            if head:
                ctx["section"] = head.group(1)
            ctx["notes"], ctx["changed"], ctx["page"] = [], False, False

            def rewrite(m, line=line):
                if m.group("comment"):
                    return m.group(0)
                ctx["directory"] = re.search(r"directory\(\s*$", line[:m.start()]) is not None
                return rewrite_literal(m, ctx)

            new = STRING.sub(rewrite, line)
            if ctx["notes"]:
                new = flag(new, "; ".join(dict.fromkeys(ctx["notes"])))
            changed_rule = changed_rule or ctx["changed"]
            if ctx["page"]:
                page_at = len(out_lines)
            out_lines.append(new)
        if info["kind"] == "qmd" and page_at is not None and not ctx["rendered"]:  # the page moved but the command did not
            out_lines[page_at] = flag(out_lines[page_at], "no render command was rewritten for this page; add "
                                      "--output-dir outputs/{0} and move the page to outputs/{0}/{0}.html".format(info["stem"]))
        rewritten += changed_rule
        for old, _ in (ctx["pairs"] or []):
            first = old.split("/")[0]
            if info["stem"] and NN.match(first) and "." not in first and first != info["stem"]:
                folders.add((first, info["stem"]))
    body = "\n".join(out_lines)
    run = re.search(r"^RUN\s*=.*\n(?:.+\n)*", body, re.M) if RUN_BLOCK.search(body) else None
    if run is None:
        raise Refusal("the Snakefile has no RUN = config.get(\"run\") block; it is not a run-folder analysis")
    body = body[:run.start()] + body[run.end():].lstrip("\n")
    head = re.match(r"\A\s*\"\"\".*?\"\"\"[ \t]*\n", body, re.S)
    if head:
        body = body[head.end():].lstrip("\n")
    docstring = re.match(r"\"\"\".*?\"\"\"\n", ap.read(os.path.join(templates, "Snakefile")), re.S).group(0)
    docstring = ap.fill(docstring, {"NAME": name, "DEST": dest_rel, "ENV_NOTE": "kept from the previous Snakefile"})
    if not re.search(r"\bos\.", re.sub(r"^import os\n", "", body, flags=re.M)):
        body = re.sub(r"^import os\n\n?", "", body, count=1, flags=re.M)
    lines = (docstring + "\n" + body).split("\n")
    for index, line in enumerate(lines):  # anything still naming the old variables is for the user to fix
        if LEFTOVER.search(code_end(line)) and "still names OUT" not in line and index > docstring.count("\n"):
            lines[index] = flag(line, "still names OUT, BASE or RUN")
    new = "\n".join(lines)
    return new.rstrip("\n") + "\n", {"rules": rules, "rewritten": rewritten, "pairs": pairs, "folders": sorted(folders)}


def scan_code(dest, folders):
    """[(path, line number, text, pattern)] for every cross-step read in code/: the places the user checks by hand."""
    hits = []
    names = [first for first, _ in folders]
    for here, dirs, files in os.walk(os.path.join(dest, "code")):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__" and not d.startswith("."))
        for file in sorted(files):
            path = os.path.join(here, file)
            if not file.endswith(CODE_FILES) or os.path.islink(path):
                continue
            try:
                lines = ap.read(path).splitlines()
            except OSError:
                continue
            own = NN.match(file).group(1) if NN.match(file) else None
            for number, line in enumerate(lines, 1):
                for label, pattern in READS:
                    if pattern.search(line):
                        hits.append((os.path.relpath(path, dest), number, line.strip(), label))
                        break
                else:
                    other = next((m.group(1) for m in STEP_FILE.finditer(line) if m.group(1) != own), None)
                    if other:  # a file named for another step: it is read from that step's folder now
                        hits.append((os.path.relpath(path, dest), number, line.strip(), "file of step " + other))
                        continue
                    for folder in names:
                        if re.search(r"(?<![\w-])" + re.escape(folder) + r"(?![\w-])", line):
                            hits.append((os.path.relpath(path, dest), number, line.strip(), folder + "/"))
                            break
    return hits


def short(text, width=96):
    return text if len(text) <= width else text[:width - 3] + "..."


def gitignore_notes(dest, root, folders, stems):
    """Lines for MIGRATE.md about the .gitignore: what hides the new step folders, what names an old folder."""
    notes = []
    path = os.path.join(dest, ".gitignore")
    patterns = []
    if os.path.isfile(path):
        patterns = [l.strip() for l in ap.read(path).splitlines() if l.strip() and not l.lstrip().startswith("#")]
    for old, stem in folders:
        for pattern in patterns:
            if re.search(r"(?<![\w-])" + re.escape(old) + r"(?![\w-])", pattern):
                notes.append("`{}` names the old folder `{}`; the step folder is `outputs/{}/`, so add `/outputs/{}/`"
                             .format(pattern, old, stem, stem))
    probes = [(os.path.join(dest, "outputs", s, "probe.txt"), "outputs/{}/".format(s)) for s in stems if s]
    probes.append((os.path.join(dest, "logs", "CHANGES.md"), "logs/CHANGES.md"))
    for shown, rule_text in sorted((root and ignored(root, probes) or {}).items()):
        notes.append("git ignores `{}` ({}); it stays out of git unless you un-ignore it".format(shown, rule_text.split(":", 2)[-1]))
    return notes


def migrate_report(name, dest, root, info, new_text, folders_notes, hashes_missing, quarto_note):
    stems = [r for r in info["rules"] if r["stem"]]
    lines = ["# Migrating {} to step folders".format(name), "",
             "Written by `new-analysis --migrate`. It edited nothing in place: the originals are untouched until you run it "
             "again with `--apply`, and it never edits `code/` or deletes a run folder. Read `Snakefile.new` (diff printed by "
             "the tool), fix each `# MIGRATE: check` line, then apply.", ""]
    lines += ["## Rules rewritten", "", "{} of {} rules changed. A rule's folder is `outputs/<script stem>/`.".format(
        info["rewritten"], len(info["rules"])), "", "| Rule | Step folder |", "|---|---|"]
    lines += ["| `{}` | `outputs/{}/` |".format(r["name"], r["stem"]) for r in stems]
    skipped = [r["name"] for r in info["rules"] if not r["stem"]]
    if skipped:
        lines += ["", "No script input, so no step folder: " + ", ".join("`{}`".format(n) for n in skipped) + "."]
    checks = [(i + 1, l) for i, l in enumerate(new_text.split("\n")) if "# MIGRATE: check" in l]
    lines += ["", "## Paths to check", ""]
    if checks:
        lines += ["- `Snakefile.new:{}` `{}` ({})".format(n, short(l.split("#")[0].strip(), 80), l.split("MIGRATE: check:")[-1].strip())
                  for n, l in checks]
    else:
        lines.append("None: every `{OUT}` and `{BASE}` path mapped to a step folder.")
    if info["folders"]:
        lines += ["", "Results folders renamed to the step folder (the script stem): "
                  + ", ".join("`{}` to `{}`".format(old, stem) for old, stem in info["folders"]) + "."]
    hits = scan_code(dest, info["folders"])
    lines += ["", "## Reads in code/ to check by hand", "",
              "These scripts reach another step through a shared folder. `code/` is not edited. Each script now gets its own "
              "step folder (`STEP_DIR`, or `dirname(output_path)`) and reads other steps from `outputs/<step>/`.", ""]
    lines += (["- [ ] `{}:{}` `{}` ({})".format(p, n, short(t), pat) for p, n, t, pat in hits]
              or ["No hits."])
    lines += ["", "## .gitignore", ""]
    lines += ["- " + n for n in folders_notes] or ["No pattern in `.gitignore` hides or names a step folder."]
    lines += ["", "`.gitignore` is not edited.", "", "## Mixed layout", "",
              "Once step folders exist, `outputs/` holds them and the old `run_*` folders side by side. The resolver lists the "
              "step folders first and the run folders after. A downstream analysis that points at an old run folder keeps "
              "working, because it uses that path directly. Seed a step folder with `--seed step=run` (copy only) when a "
              "reader needs the files at the new path.", "", "## First run", ""]
    lines.append("Comments in the Snakefile that mention OUT, BASE or a run folder are kept as written; reword them.")
    lines.append("`logs/.code-hashes.tsv` is absent, so the first `run.sh` entry lists every file in `code/` as new."
                 if hashes_missing else "`logs/.code-hashes.tsv` exists; the first entry compares against it.")
    lines.append("`run.sh` takes no slug now and writes no `RUN.txt`: `bash run.sh`.")
    if quarto_note:
        lines.append(quarto_note)
    return "\n".join(lines) + "\n"


def quarto_text(dest, templates):
    """(new _quarto.yml or None, a note on what the old one set that the template drops)."""
    old = os.path.join(dest, "_quarto.yml")
    has_qmd = any(f.endswith(".qmd") for _, _, files in os.walk(os.path.join(dest, "code")) for f in files)
    if not os.path.isfile(old) and not has_qmd:
        return None, ""
    note = ""
    if os.path.isfile(old):
        text = ap.read(old)
        site = re.search(r"^\s*output-dir:\s*(\S+)", text, re.M)
        if re.search(r"^\s*type:\s*website", text, re.M) or site:
            note = "`_quarto.yml.new` is the current template: qmd pages go to `outputs/<step>/<step>.html`, not {}.".format(
                "`{}`".format(site.group(1)) if site else "a website folder")
    return ap.read(os.path.join(templates, "_quarto.yml")), note


@contextlib.contextmanager
def scaffold_lock(dest):
    """The scaffold's flock: an empty .<name>.scaffold.lock in the parent folder."""
    lock = os.path.join(os.path.dirname(dest), "." + os.path.basename(dest) + ".scaffold.lock")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def write_new(path, text, mode=None):
    """Write text to path through a temp file and a rename; mode sets the file mode."""
    folder = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(prefix=".migrate-", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(tmp, mode if mode is not None else 0o666 & ~umask)
        os.rename(tmp, path)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)


def parse_seed(text, rules):
    """{stem: run folder name} from step=run,step=run; a step is a stem, a rule name or a step number."""
    seeds = {}
    for item in [part.strip() for part in text.split(",") if part.strip()]:
        step, equals, run = item.partition("=")
        if not equals or not step or not run or "/" in run or run in (".", ".."):
            raise Refusal("--seed takes step=run pairs, e.g. 01_valid-tags=run_20261111_baseline; got {!r}".format(item))
        found = [r["stem"] for r in rules if r["stem"] and step in (r["stem"], r["name"], NN.match(r["stem"]).group(1) if NN.match(r["stem"]) else None)]
        if len(found) != 1:
            raise Refusal("--seed step {!r} matches {} rules with a script; use the script stem".format(step, len(found)))
        if found[0] in seeds:
            raise Refusal("--seed names step {} twice".format(found[0]))
        seeds[found[0]] = run
    if not seeds:
        raise Refusal("--seed is empty")
    return seeds


def seed_plan(dest, seeds, pairs):
    """[(stem, run, [(source, target)], [declared paths with no file in the run], skipped existing)] without copying."""
    plan = []
    for stem, run in seeds.items():
        base = os.path.join(dest, "outputs", run)
        if os.path.islink(base) or not os.path.isdir(base):
            raise Refusal("outputs/{} is not a run folder; nothing was changed".format(run))
        have = []
        for here, dirs, files in os.walk(base):
            dirs.sort()
            have += [os.path.relpath(os.path.join(here, f), base).replace(os.sep, "/") for f in sorted(files)
                     if not os.path.islink(os.path.join(here, f))]
        copies, missing, seen = [], [], set()
        for old, new in pairs.get(stem, []):
            names, regex = set(), "^"
            for index, piece in enumerate(re.split(r"\{(\w+)\}", old)):  # a {wildcard} matches one path part
                if index % 2:
                    regex += "(?P={})".format(piece) if piece in names else "(?P<{}>[^/]+)".format(piece)
                    names.add(piece)
                else:
                    regex += re.escape(piece)
            regex += "$"
            hit = False
            for rel in have:
                found = re.match(regex, rel)
                if found:
                    hit = True
                    target = new
                    for key, value in found.groupdict().items():
                        target = target.replace("{" + key + "}", value)
                    if target not in seen:
                        seen.add(target)
                        copies.append((os.path.join(base, rel), os.path.join(dest, target)))
            if not hit:
                missing.append(old)
        plan.append((stem, run, copies, missing))
    return plan


def seed_copy(plan, dest, dry_run):
    """Copy what is missing; never overwrite, never move. Returns the printed lines and the seeded folders."""
    out, seeded = [], []
    for stem, run, copies, missing in plan:
        made = kept = 0
        for source, target in copies:
            if os.path.lexists(target):
                kept += 1
                continue
            made += 1
            if not dry_run:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(source, "rb") as src, open(target, "xb") as dst:
                    shutil.copyfileobj(src, dst)
                shutil.copystat(source, target)
        out.append("  {} outputs/{}/ from outputs/{}/: {} file(s), {} already there".format(
            "would seed" if dry_run else "seeded", stem, run, made, kept))
        for old in missing:
            out.append("    no file in the run for declared output {}".format(old))
        if made:
            seeded.append((stem, run, made, kept))
    return out, seeded


def log_migration(dest, seeded):
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    path = os.path.join(dest, "logs", "CHANGES.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    entry = ["", "## {} migrated ok".format(stamp), "code changed: none", "outputs rewritten:"]
    entry += ["- outputs/{}/ (seeded: copied {} file(s) from outputs/{}/, run folder unchanged)".format(s, n, r) for s, r, n, _ in seeded]
    with open(path, "a", encoding="utf-8") as handle:
        if handle.tell() == 0:
            handle.write(CHANGES_HEAD)
        handle.write("\n".join(entry) + "\n")


def migrate(args, dest):
    """Move a run-folder analysis to step folders. Writes only new files unless --apply; never edits code/ or a run folder."""
    for flag in ("steps", "format", "data", "code", "doc_template", "panels"):
        if getattr(args, flag):
            raise Refusal("--migrate takes --dest, --seed, --apply and --dry-run only; got --{}".format(flag.replace("_", "-")))
    if not args.migrate:
        raise Refusal("--apply and --seed go with --migrate")
    root = ap.living_root(dest) if os.path.isdir(dest) else None
    dest_rel = display(dest, root).replace(os.sep, "/")
    name = os.path.basename(dest)
    if not os.path.isdir(dest) or os.path.islink(dest):
        raise Refusal("{} is not an existing analysis folder; nothing was changed".format(dest_rel))
    for item in ("code", "outputs", "Snakefile"):
        if os.path.islink(os.path.join(dest, item)):
            raise Refusal("{}/{} is a symlink; nothing was changed".format(dest_rel, item))
    snakefile = os.path.join(dest, "Snakefile")
    if not os.path.isfile(snakefile):
        raise Refusal("{} has no Snakefile; nothing to migrate".format(dest_rel))
    pre = os.path.join(dest, "Snakefile" + OLD)
    marker = os.path.join(dest, "outputs", ".layout")
    again = os.path.isfile(pre)  # an applied migration: --seed may copy more steps
    if again and not args.seed:
        raise Refusal("{} was migrated already ({} exists); use --seed step=run to copy more steps".format(dest_rel, "Snakefile" + OLD))
    if os.path.lexists(marker) and not again:
        raise Refusal("{} is already in the step-folder layout (outputs/.layout exists); nothing was changed".format(dest_rel))
    if args.seed and not (args.apply or again or args.dry_run):
        raise Refusal("--seed goes with --apply: it copies into the step folders of the new Snakefile")
    templates = args.templates
    source_text = ap.read(pre if again else snakefile, "strict")
    new_text, info = migrate_snakefile(source_text, name, dest_rel, templates)
    seeds = parse_seed(args.seed, info["rules"]) if args.seed else {}
    plan = seed_plan(dest, seeds, info["pairs"]) if seeds else []
    verb = "would write" if args.dry_run else "wrote"
    if again:  # only the seed step is left to do
        print("{} was migrated already; seeding only".format(dest_rel))
        return run_seed(args, dest, plan)

    files = {"Snakefile": new_text,
             "run.sh": ap.fill(ap.read(os.path.join(templates, "run.sh")), {"NAME": name}),
             "run.sbatch": ap.fill(ap.read(os.path.join(templates, "run.sbatch")), {"NAME": name})}
    quarto, quarto_note = quarto_text(dest, templates)
    if quarto:
        files["_quarto.yml"] = quarto
    stems = [r["stem"] for r in info["rules"]]
    notes = gitignore_notes(dest, root, info["folders"], stems)
    hashes_missing = not os.path.isfile(os.path.join(dest, "logs", ".code-hashes.tsv"))
    report = migrate_report(name, dest, root, info, new_text, notes, hashes_missing, quarto_note)
    if args.apply:  # a .new file the user read and perhaps edited is what gets installed, so it is what the diff shows
        for n in files:
            fresh, original = os.path.join(dest, n + ".new"), os.path.join(dest, n)
            if os.path.isfile(fresh):
                if os.path.isfile(original) and os.stat(original).st_mtime > os.stat(fresh).st_mtime:
                    raise Refusal("{0} changed after {0}.new was written; delete {0}.new and run --migrate again. "
                                  "Nothing was changed".format(n))
                files[n] = ap.read(fresh, "strict")
        new_text = files["Snakefile"]
    elif not args.dry_run:  # a rerun never overwrites a .new file that differs: it may hold the user's fixes
        written = [(n + ".new", text) for n, text in files.items()] + [("MIGRATE.md", report)]
        differ = [shown for shown, text in written
                  if os.path.isfile(os.path.join(dest, shown)) and ap.read(os.path.join(dest, shown), "strict") != text]
        if differ:
            raise Refusal("{} differs from a fresh migration (your edits, or the originals changed); nothing was changed. "
                          "Delete {} to write {} again, or run --migrate --apply to install what you edited".format(
                              ", ".join(differ), "it" if len(differ) == 1 else "them", "it" if len(differ) == 1 else "them"))
    print("migrate {}/ (run folders to step folders; originals stay until --apply)".format(dest_rel))
    flagged = sum(1 for l in new_text.split("\n") if "# MIGRATE: check" in l)
    print("  {} of {} rules rewritten; {} line(s) marked '# MIGRATE: check'".format(info["rewritten"], len(info["rules"]), flagged))
    for line in difflib.unified_diff(source_text.splitlines(), new_text.splitlines(), "Snakefile", "Snakefile.new", lineterm=""):
        print(line)
    held = [n + OLD for n in files if os.path.lexists(os.path.join(dest, n + OLD))]
    if args.apply and held:
        raise Refusal("{} exists already; nothing was changed".format(", ".join(held)))
    if not args.dry_run:
        with scaffold_lock(dest):
            if args.apply:
                install(dest, files)
            else:
                for n, text in files.items():
                    write_new(os.path.join(dest, n + ".new"), text, 0o755 if n == "run.sh" else None)
            if not (args.apply and os.path.lexists(os.path.join(dest, "MIGRATE.md"))):  # keep the report you read
                write_new(os.path.join(dest, "MIGRATE.md"), report)
    if args.apply:
        print("  {} {} (originals kept as *{})".format("would install" if args.dry_run else "installed", ", ".join(files), OLD))
    else:
        for n in files:
            print("  {} {}.new".format(verb, n))
    print("  {} MIGRATE.md".format(verb))
    for line in notes:
        print("note: .gitignore: " + line)
    if args.seed:
        run_seed(args, dest, plan)
    elif args.apply:
        print("next: bash run.sh to build the step folders, or --migrate --seed step=run,... to copy files from a run folder.")
    else:
        print("next: read the diff and MIGRATE.md, fix each '# MIGRATE: check', then run again with --apply.")
    return 0


def install(dest, files):
    """Rename each original to *.pre-0.27 and put the text in its place (the caller passes a user-edited *.new file's
    text). Undo on failure. The *.new files go only after every file is installed, so a failure keeps them."""
    done = []
    try:
        for n, text in files.items():
            path = os.path.join(dest, n)
            if os.path.lexists(path):
                os.rename(path, path + OLD)
                done.append((path, path + OLD))
            write_new(path, text, 0o755 if n == "run.sh" else None)
    except BaseException:
        for path, kept in reversed(done):
            if os.path.lexists(path):
                os.unlink(path)
            os.rename(kept, path)
        raise
    for n in files:
        with contextlib.suppress(OSError):
            os.unlink(os.path.join(dest, n + ".new"))


def run_seed(args, dest, plan):
    """Copy the declared outputs, write outputs/.layout, log the migration."""
    marker = os.path.join(dest, "outputs", ".layout")
    if args.dry_run:
        print("\n".join(seed_copy(plan, dest, True)[0]))
        print("  would write outputs/.layout")
        return 0
    with scaffold_lock(dest):
        lines, seeded = seed_copy(plan, dest, False)
        print("\n".join(lines))
        if not os.path.lexists(marker):
            os.makedirs(os.path.dirname(marker), exist_ok=True)
            write_new(marker, LAYOUT_TEXT)
            print("  wrote outputs/.layout")
        if seeded:
            log_migration(dest, seeded)
            print("  added a 'migrated' entry to logs/CHANGES.md")
    return 0


def main(argv):
    parser = argparse.ArgumentParser(prog="new_analysis")
    parser.add_argument("--dest", required=True, help="folder to create, e.g. analysis/<name>")
    parser.add_argument("--steps", help="comma-separated NN_name.{R,py,ipynb,qmd,marimo.py}; a name with no extension "
                        "takes --format")
    parser.add_argument("--format", choices=FORMATS, help="step format (default: step_format in "
                        ".mycelium-extra/gate.json); alone, it sets the default steps' extension")
    parser.add_argument("--lang", choices=sorted(LANGS), default="r", help="language of qmd steps")
    parser.add_argument("--data", action="append", help="file or folder to link into data/")
    parser.add_argument("--code", action="append", help="file or folder to link into code/")
    parser.add_argument("--doc-template", help="analysis doc template (default: Mycelium's)")
    here = globals().get("__file__")
    default_templates = (os.path.join(os.path.dirname(os.path.abspath(here)), "..", "templates")
                         if here and os.path.isfile(here) else None)
    parser.add_argument("--templates", default=default_templates, help="this skill's templates/")
    parser.add_argument("--panels", help="comma-separated manuscript panels, e.g. Fig1a.R,Fig1b.py")
    parser.add_argument("--wrapper", action="append", help="NN_name:skill-name, repeatable: a code/NN_name.sh stub that "
                        "calls that pipeline skill's script (the gate ignores scripts outside the repository)")
    parser.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    parser.add_argument("--migrate", action="store_true", help="move a run-folder analysis (--dest, existing) to step folders")
    parser.add_argument("--apply", action="store_true", help="with --migrate: install the .new files, keep the originals as *.pre-0.27")
    parser.add_argument("--seed", help="with --migrate and --apply: step=run,step=run; copy each step's declared outputs out of outputs/<run>/")
    args = parser.parse_args(argv)
    if not args.templates or not os.path.isdir(args.templates):
        parser.error("--templates=<skill-dir>/templates is required when run from stdin")
    load_paths(args.templates)

    try:
        return scaffold(args)
    except (Refusal, OSError) as refusal:
        print("refused: {}".format(refusal))
        return 1


def scaffold(args):
    dest = canonical(args.dest)
    if args.migrate or args.apply or args.seed:
        if args.wrapper:
            raise Refusal("--wrapper applies to a new scaffold, not to --migrate")
        return migrate(args, dest)
    if os.path.islink(dest):
        raise Refusal("destination is a symlink; nothing was changed")
    if os.path.exists(dest) and not os.path.isdir(dest):
        raise Refusal("{} exists and is not a folder".format(args.dest))
    if os.path.isdir(dest) and os.listdir(dest):
        if args.panels:
            if args.wrapper:
                raise Refusal("--wrapper applies to a new scaffold, not to adding panels")
            return add_panels(args, dest)
        raise Refusal("{} exists and is not empty; nothing was changed".format(args.dest))
    root = manuscript_root(dest) if args.panels else ap.living_root(dest)
    if root == dest:
        raise Refusal("{} is the repository root".format(args.dest))
    mycelium = root is not None and os.path.isdir(os.path.join(root, ".living"))
    name = os.path.basename(dest)
    dest_rel = display(dest, root)
    fmt, fmt_source = step_format(args, root)
    steps = parse_steps(args.steps or (",".join(n + "." + EXT.get(fmt, fmt) for n in DEFAULT_NAMES) if fmt else DEFAULT_STEPS),
                        fmt, args.lang)
    qmd = any(s["kind"] == "qmd" for s in steps)
    data_links = plan_links(args.data, "data", dest, root)
    code_links = plan_links(args.code, "code", dest, root)
    doc_name = name.upper().replace("-", "_") + ".md" if mycelium else "README.md"
    template_path, template_note = find_doc_template(args.doc_template, root, args.templates)
    templates = args.templates
    today = datetime.date.today().isoformat()

    files = {}
    for step in steps:
        values = stub_values(step, name, data_links)
        source = ap.read(os.path.join(templates, step["stub"]))
        files[step["path"]] = notebook(source, values) if step["kind"] == "ipynb" else ap.fill(source, values)
    tools, env_used, env_note = interpreters(root)
    files["Snakefile"] = ap.fill(ap.read(os.path.join(templates, "Snakefile")), {
        "NAME": json.dumps(name)[1:-1], "DEST": json.dumps(dest_rel)[1:-1],
        "RSCRIPT": json.dumps(tools["rscript"]), "PYTHON": json.dumps(tools["python"]),
        "JUPYTER": json.dumps(tools["jupyter"]),
        "ENV_NOTE": "defaults from " + ENV_FILE if env_used else "defaults are the names on PATH",
        "LAST_OUTPUTS": "\n".join(['        "{}/{}",'.format(steps[-1]["dir"], out) for out in steps[-1]["outs"]]
                                  + (['        "{}",'.format(steps[-1]["html"])] if steps[-1]["html"] else [])),
        "RULES": "\n\n".join(rule(step, data_links) for step in steps).rstrip("\n")})
    files["logs/.gitkeep"] = files["outputs/.gitkeep"] = ""  # git drops empty folders; SLURM needs logs/ after a clone
    files["outputs/.layout"] = "layout: steps\nversion: 1\n"  # the explicit marker ap.runs() reads
    rules, rules_why = active_rules()  # learned fig.theme rules; fails open to the shipped theme
    theme_notes = []
    for theme in CODE_THEMES:  # every figure script sources the one theme
        files["code/" + theme], note = theme_text(ap.read(os.path.join(templates, theme)), theme.split(".")[1],
                                                  rules, rules_why)
        theme_notes.append(note)
    wrappers = parse_wrappers(args.wrapper, steps)
    for wrapper in wrappers:
        files[wrapper["path"]] = wrapper_text(ap.read(os.path.join(templates, "wrapper.sh")), wrapper, name)
    files["data/SOURCES.md"] = ap.fill(ap.read(os.path.join(templates, "SOURCES.md")), {
        "SOURCE_ROWS": "\n".join(source_rows(data_links, root))})
    files["run.sh"] = ap.fill(ap.read(os.path.join(templates, "run.sh")), {"NAME": name})
    files["run.sbatch"] = ap.fill(ap.read(os.path.join(templates, "run.sbatch")), {"NAME": name})
    files[doc_name] = doc_text(ap.read(template_path), name, dest_rel, steps, data_links,
                               code_links, root)
    if qmd:  # each qmd step renders its page into its own outputs/<stem>/ folder
        files["_quarto.yml"] = ap.read(os.path.join(templates, "_quarto.yml"))
    report = "reports/" + name + ".qmd"
    if not all(s["kind"] == "qmd" for s in steps):
        files[report] = report_text(ap.read(os.path.join(templates, "report.qmd")), name, doc_name, dest_rel,
                                    steps, data_links)
    for theme in THEMES:  # report.qmd and _quarto.yml both name these (DESIGN.md tokens)
        files["reports/" + theme] = ap.read(os.path.join(templates, theme))
    files["reports/README.md"] = ap.fill(ap.read(os.path.join(templates, "reports-README.md")), {
        "REPORT_ROWS": "\n".join(report_rows(name, report in files))})
    if args.panels:
        files.update(manuscript_files(parse_panels(args.panels), panel_dir(steps), name, dest_rel.replace(os.sep, "/"), root, templates))
    folders = DIRS + (["config"] if args.panels else [])
    inputs = ", ".join(display(l["target"], root) for l in data_links) or (
        "[repository paths of the sample table, config, or raw-data folder; or none]")
    plan_rows = ["| S{} | `{}/{}` | [choice] | [repo: / user / inherited: / default:] | [check] |".format(
        s["num"], dest_rel, s["path"]) for s in steps]
    plan_rows += ["| S{} | `{}/{}` | runs the {} skill script | [repo: / user / inherited: / default:] | [check] |".format(
        w["num"], dest_rel, w["path"], w["skill"]) for w in wrappers]
    files["plans/PLAN.md"] = ap.fill(ap.read(os.path.join(templates, "PLAN.md")), {
        "NAME": name, "INPUTS": inputs, "PLAN_ROWS": "\n".join(plan_rows)})
    ids = ["S" + s["num"] for s in steps]
    tracker_rows = ["| {} | `{}` | todo | {} | [how to check it worked] |".format(ident, s["path"], before or "\u2014")
                    for ident, before, s in zip(ids, [None] + ids, steps)]
    tracker_rows += ["| S{} | `{}` | todo | \u2014 | [how to check it worked] |".format(w["num"], w["path"]) for w in wrappers]
    files["plans/TRACKER.md"] = ap.fill(ap.read(os.path.join(templates, "TRACKER.md")), {
        "NAME": name, "DOC": doc_name, "DATE": today, "TRACKER_ROWS": "\n".join(tracker_rows)})

    probes = [(os.path.join(dest, path), path) for path in sorted(files) if not path.endswith(".gitkeep")]
    probes += [(os.path.join(dest, d, "placeholder"), d + "/") for d in folders]
    hidden = ignored(root, probes) if root else {}

    verb = "would create" if args.dry_run else "created"
    if not args.dry_run:
        parent = os.path.dirname(dest)
        os.makedirs(parent, exist_ok=True)
        lock = os.path.join(parent, "." + name + ".scaffold.lock")
        fd = os.open(lock, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            stage = tempfile.mkdtemp(prefix="." + name + ".stage-", dir=parent)
            try:
                for folder in folders:
                    os.mkdir(os.path.join(stage, folder))
                for path, text in files.items():
                    checked(path, text)
                    if path.endswith(".marimo.py"):
                        compile(text, path, "exec")
                    if path.endswith(".ipynb"):
                        book = json.loads(text)
                        for cell in book["cells"]:
                            if cell["cell_type"] == "code":
                                compile("".join(cell["source"]), path, "exec")
                    with open(os.path.join(stage, path), "x", encoding="utf-8", errors="surrogateescape") as handle:
                        handle.write(text)
                        handle.flush()
                        os.fsync(handle.fileno())
                os.chmod(os.path.join(stage, "run.sh"), 0o755)
                for wrapper in wrappers:
                    os.chmod(os.path.join(stage, wrapper["path"]), 0o755)
                umask = os.umask(0)
                os.umask(umask)
                os.chmod(stage, 0o777 & ~umask)  # mkdtemp makes it 0700; a lab folder follows the umask
                for link in data_links + code_links:
                    os.symlink(link["value"], os.path.join(stage, link["rel"]))
                if os.path.lexists(dest):
                    if os.path.islink(dest) or not os.path.isdir(dest) or os.listdir(dest):
                        raise Refusal("destination changed or is not empty; nothing was changed")
                os.rename(stage, dest)  # Atomic replacement also accepts an existing empty folder.
            finally:
                if os.path.exists(stage):
                    shutil.rmtree(stage)
        finally:
            os.close(fd)

    print("{} {}/ (doc {} from {})".format(verb, dest_rel, doc_name, template_note))
    for path in [s["path"] for s in steps] + [w["path"] for w in wrappers] + ["Snakefile", "run.sh", "run.sbatch", doc_name,
                                              "plans/PLAN.md", "plans/TRACKER.md", "reports/README.md", "data/SOURCES.md"] + [
                                                  p for p in ("_quarto.yml", report) if p in files] + [
                                                  "reports/" + t for t in THEMES] + ["code/" + t for t in CODE_THEMES] + sorted(
                                                  p for p in files if p.startswith(("config/", "code/plot_"))) + [
                                                  d + "/" for d in folders]:
        print("  " + path)
    for link in data_links + code_links:
        print("  {} -> {}".format(link["rel"], link["value"]))
    print("note: " + env_note + ".")
    for note in theme_notes:
        print("note: " + note)
    for wrapper in wrappers:
        print("note: {0} calls the {1} skill and is not in the Snakefile; run it with `bash {0}`, or add a rule that "
              "does. Set CLAUDE_PLUGIN_ROOT to the plugin that ships the skill.".format(wrapper["path"], wrapper["skill"]))
    if fmt:
        print("note: default steps are .{} ({}).".format(fmt, fmt_source))
    for step in (s for s in steps if s["kind"] == "marimo"):
        print("note: {0} runs headless as a Python script; `marimo edit {0}` opens it, and `marimo export html {0} "
              "-o {2}` renders a page analysis-report can link (it executes the notebook: a gated run).".format(step["path"], step["stem"], step["html"] or "outputs/{}/{}.html".format(step["stem"], step["stem"])))
    if qmd:
        print("note: qmd steps are rendered by quarto into outputs/<stem>/ ({} engine); the Snakefile needs quarto "
              "on PATH, or --config quarto=/path/to/quarto.".format("knitr" if args.lang == "r" else "jupyter"))
    for shown in sorted(hidden):
        if shown in UNTRACKED_OK:
            print("note: git ignores {}/{} ({}); its contents stay out of git.".format(
                dest_rel, shown, hidden[shown]))
        else:
            print("WARNING: git ignores {}/{} ({}); it would never be committed. Pick another "
                  "location or ask before changing the ignore rule.".format(
                      dest_rel, shown, hidden[shown]))
    if mycelium:
        if not inside(dest, os.path.join(root, "analysis")):
            print("note: outside analysis/; Mycelium's analyze and validate_structure find it only "
                  "through an analysis/ANALYSIS_MANIFEST.md pointer.")
        if not MYCELIUM_NAME.match(name):
            print("note: Mycelium names analyses in lowercase-with-hyphens (e.g. dose-response-v2).")
        for link in data_links:
            if not inside(link["target"], os.path.join(root, "data")):
                print("note: {} is not under data/; register it with /mycelium:ingest so it has a "
                      "data/DATA_MANIFEST.md entry.".format(display(link["target"], root)))
        print("suggested analysis/ANALYSIS_MANIFEST.md entry, for /mycelium:analyze to add:")
        print("\n".join("  " + line for line in [
            "### " + name, "```yaml", "name: " + name, "status: draft", "created: " + today,
            "last_updated: " + today,
            "datasets: [{}]".format(", ".join(os.path.basename(l["target"]) for l in data_links)),
            "algorithms: [{}]".format(", ".join(os.path.basename(l["target"]) for l in code_links)),
            "parent_analysis: null", "key_findings: []", "report: null", "tags: []", "```"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
