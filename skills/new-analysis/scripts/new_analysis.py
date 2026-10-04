"""Scaffold a new analysis folder that plugs into Mycelium.

Run from stdin so Mycelium's hooks stay closed, with every option in --flag=value form
(the approval gate reads a bare analysis/... argument as a script to run):
    python3 - --dest=analysis/<name> [--steps=01_a.R,02_b.py,03_c.ipynb]
              [--data=PATH ...] [--code=PATH ...] [--doc-template=PATH]
              --templates=<skill-dir>/templates [--dry-run] < new_analysis.py

Creates <dest>/ with numbered step stubs at its root, a Snakefile that runs them in
order, run.sh, the analysis doc (Mycelium's analysis-readme template: <NAME>.md in a
Mycelium repository, README.md elsewhere), PLAN.md, TRACKER.md, and data/ code/ outputs/
logs/ reports/. data/ and code/ hold symlinks. Refuses a non-empty <dest>, never
overwrites, and writes nothing outside <dest>. Stdlib-only; runs on Python 3.6+.
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys

STEP = re.compile(r"^(\d{2})_([A-Za-z0-9][A-Za-z0-9_-]*)\.(R|py|ipynb)$")
DEFAULT_STEPS = "01_prepare_data.R,02_train_model.py,03_explore_model.ipynb"
DIRS = ["data", "code", "outputs", "logs", "reports"]
UNTRACKED_OK = {"outputs/", "logs/"}  # often ignored on purpose (large or regenerable files)
OUTPUT_EXT = {"R": ".rds", "py": ".parquet"}
MYCELIUM_TEMPLATE = os.path.join("skills", "core", "templates", "analysis-readme.md")
MYCELIUM_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FINDINGS_HINT = ("<!-- One bullet per result: the claim, the outputs/ file behind it, and its "
                 ".living/findings ID once crystallized. -->")


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


def find_root(dest):
    """The git toplevel above dest, else the nearest ancestor with .living/, else None."""
    start = dest
    while not os.path.isdir(start):
        start = os.path.dirname(start)
    result = git(start, "rev-parse", "--show-toplevel")
    if result is not None and result.returncode == 0 and result.stdout.strip():
        return os.path.realpath(result.stdout.strip())
    path = start
    while True:
        if os.path.isdir(os.path.join(path, ".living")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def display(path, root):
    return os.path.relpath(path, root) if inside(path, root) else path


def parse_steps(text):
    steps, previous = [], -1
    for name in [part.strip() for part in text.split(",") if part.strip()]:
        match = STEP.match(name)
        if not match:
            raise Refusal("step {!r} must look like NN_name.R, NN_name.py, or NN_name.ipynb"
                          .format(name))
        number = int(match.group(1))
        if number <= previous:
            raise Refusal("step numbers must increase: {} comes after {:02d}".format(name, previous))
        previous = number
        stem, kind = name.rsplit(".", 1)
        output = ("logs/" + name) if kind == "ipynb" else ("outputs/" + stem + OUTPUT_EXT[kind])
        steps.append({"file": name, "num": match.group(1), "stem": stem, "kind": kind,
                      "rule": "step" + re.sub(r"\W", "_", stem), "output": output})
    if not steps:
        raise Refusal("--steps is empty")
    for before, step in zip([None] + steps, steps):
        step["input"] = before["output"] if before else None
    return steps


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


def fill(text, values):
    for key, value in values.items():
        text = text.replace("@@" + key + "@@", value)
    return text


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


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
    if step["kind"] == "R":
        code = ("output_path <- args[[1]]" if first
                else "input_path <- args[[1]]\noutput_path <- args[[2]]")
    else:
        code = ("(output_path,) = sys.argv[1:]" if first
                else "input_path, output_path = sys.argv[1:]")
    return {"FILE": step["file"], "NUM": step["num"], "NAME": name,
            "INPUT": notebook_input if step["kind"] == "ipynb" else source,
            "OUTPUT": step["output"], "USAGE": usage, "NARGS": "1" if first else "2",
            "ARGS_CODE": code}


def notebook(template, values):
    book = json.loads(template)
    for cell in book["cells"]:
        cell["source"] = [fill(line, values) for line in cell["source"]]
    return json.dumps(book, indent=1) + "\n"


def rule(step, data_links):
    lines = ["rule {}:".format(step["rule"]), "    input:"]
    if step["input"]:
        lines.append('        prev="{}",'.format(step["input"]))
    elif data_links:
        lines.append("        data=[{}],".format(", ".join('"{}"'.format(l["rel"]) for l in data_links)))
    key = "notebook" if step["kind"] == "ipynb" else "script"
    lines.append('        {}="{}",'.format(key, step["file"]))
    todo = "" if step["kind"] == "ipynb" else "  # TODO: name the real outputs"
    lines += ["    output:", '        "{}",{}'.format(step["output"], todo),
              "    threads: 1",
              "    log:", '        "logs/{}.log",'.format(step["stem"]),
              "    benchmark:", '        "logs/{}.benchmark.tsv"'.format(step["stem"]),
              "    shell:"]
    prev = " {input.prev:q}" if step["input"] else ""
    if step["kind"] == "ipynb":
        command = ("{{JUPYTER:q}} nbconvert --to notebook --execute {{input.notebook:q}} "
                   "--output-dir logs --output {} > {{log:q}} 2>&1".format(step["file"]))
    elif step["kind"] == "R":
        command = "{RSCRIPT:q} {input.script:q}" + prev + " {output:q} > {log:q} 2>&1"
    else:
        command = "{PYTHON:q} -u {input.script:q}" + prev + " {output:q} > {log:q} 2>&1"
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
        "| `{}` | [description] (step {}) |".format(s["output"], s["num"])
        for s in steps if s["output"].startswith("outputs/")]
        + ["| `outputs/numbers.json` | Reportable values, written by `register_value` |"])
    if "<!-- Update as work progresses" in text:
        text = replace_line(text, "<!-- Update as work progresses", [FINDINGS_HINT])
    else:
        text = text.replace("## Key Findings\n", "## Key Findings\n\n" + FINDINGS_HINT + "\n", 1)
    section = "\n".join(
        ["## Steps", "",
         "Run in number order; `bash run.sh` runs them all through the `Snakefile`.",
         "Plan: [PLAN.md](PLAN.md). Status and log: [TRACKER.md](TRACKER.md).", "",
         "| Step | File | Does | Output |", "|---|---|---|---|"]
        + ["| {} | `{}` | [what it does] | `{}` |".format(s["num"], s["file"], s["output"])
           for s in steps]) + "\n"
    if "\n## Reproducibility" in text:
        return text.replace("\n## Reproducibility", "\n" + section + "\n## Reproducibility", 1)
    return text.rstrip("\n") + "\n\n" + section


def find_doc_template(option, root, templates):
    if option:
        if not os.path.isfile(option):
            raise Refusal("--doc-template not found: {}".format(option))
        return option, option
    if root:
        try:
            plugin = read(os.path.join(root, ".mycelium", "plugin-root")).strip()
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


def main(argv):
    parser = argparse.ArgumentParser(prog="new_analysis")
    parser.add_argument("--dest", required=True, help="folder to create, e.g. analysis/<name>")
    parser.add_argument("--steps", default=DEFAULT_STEPS, help="comma-separated NN_name.{R,py,ipynb}")
    parser.add_argument("--data", action="append", help="file or folder to link into data/")
    parser.add_argument("--code", action="append", help="file or folder to link into code/")
    parser.add_argument("--doc-template", help="analysis doc template (default: Mycelium's)")
    here = globals().get("__file__")
    default_templates = (os.path.join(os.path.dirname(os.path.abspath(here)), "..", "templates")
                         if here and os.path.isfile(here) else None)
    parser.add_argument("--templates", default=default_templates, help="this skill's templates/")
    parser.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    args = parser.parse_args(argv)
    if not args.templates or not os.path.isdir(args.templates):
        parser.error("--templates=<skill-dir>/templates is required when run from stdin")

    try:
        return scaffold(args)
    except Refusal as refusal:
        print("refused: {}".format(refusal))
        return 1


def scaffold(args):
    dest = os.path.realpath(os.path.abspath(args.dest))
    if os.path.exists(dest) and not os.path.isdir(dest):
        raise Refusal("{} exists and is not a folder".format(args.dest))
    if os.path.isdir(dest) and os.listdir(dest):
        raise Refusal("{} exists and is not empty; nothing was changed".format(args.dest))
    root = find_root(dest)
    if root == dest:
        raise Refusal("{} is the repository root".format(args.dest))
    mycelium = root is not None and os.path.isdir(os.path.join(root, ".living"))
    name = os.path.basename(dest)
    dest_rel = display(dest, root)
    steps = parse_steps(args.steps)
    data_links = plan_links(args.data, "data", dest, root)
    code_links = plan_links(args.code, "code", dest, root)
    doc_name = name.upper().replace("-", "_") + ".md" if mycelium else "README.md"
    template_path, template_note = find_doc_template(args.doc_template, root, args.templates)
    templates = args.templates
    today = datetime.date.today().isoformat()

    files = {}
    for step in steps:
        values = stub_values(step, name, data_links)
        source = read(os.path.join(templates, "stub." + step["kind"]))
        files[step["file"]] = notebook(source, values) if step["kind"] == "ipynb" else fill(source, values)
    files["Snakefile"] = fill(read(os.path.join(templates, "Snakefile")), {
        "NAME": name, "DEST": dest_rel, "LAST_OUTPUT": steps[-1]["output"],
        "RULES": "\n\n".join(rule(step, data_links) for step in steps).rstrip("\n")})
    files["run.sh"] = fill(read(os.path.join(templates, "run.sh")), {"NAME": name})
    files[doc_name] = doc_text(read(template_path), name, dest_rel, steps, data_links,
                               code_links, root)
    inputs = ", ".join(display(l["target"], root) for l in data_links) or (
        "[repository paths of the sample table, config, or raw-data folder; or none]")
    files["PLAN.md"] = fill(read(os.path.join(templates, "PLAN.md")), {
        "NAME": name, "INPUTS": inputs, "PLAN_ROWS": "\n".join(
            "| S{} | `{}/{}` | [choice] | [repo: / user / default:] | [check] |".format(
                s["num"], dest_rel, s["file"]) for s in steps)})
    ids = ["S" + s["num"] for s in steps]
    files["TRACKER.md"] = fill(read(os.path.join(templates, "TRACKER.md")), {
        "NAME": name, "DOC": doc_name, "DATE": today, "TRACKER_ROWS": "\n".join(
            "| {} | `{}` | todo | {} | [how to check it worked] |".format(
                ident, s["file"], before or "—")
            for ident, before, s in zip(ids, [None] + ids, steps))})

    probes = [(os.path.join(dest, path), path) for path in sorted(files)]
    probes += [(os.path.join(dest, d, "placeholder"), d + "/") for d in DIRS]
    hidden = ignored(root, probes) if root else {}

    verb = "would create" if args.dry_run else "created"
    if not args.dry_run:
        os.makedirs(dest, exist_ok=True)
        for folder in DIRS:
            os.mkdir(os.path.join(dest, folder))
        for path, text in files.items():
            with open(os.path.join(dest, path), "x", encoding="utf-8", errors="surrogateescape") as handle:
                handle.write(text)
        os.chmod(os.path.join(dest, "run.sh"), 0o755)
        for link in data_links + code_links:
            os.symlink(link["value"], link["path"])

    print("{} {}/ (doc {} from {})".format(verb, dest_rel, doc_name, template_note))
    for path in [s["file"] for s in steps] + ["Snakefile", "run.sh", doc_name, "PLAN.md",
                                               "TRACKER.md"] + [d + "/" for d in DIRS]:
        print("  " + path)
    for link in data_links + code_links:
        print("  {} -> {}".format(link["rel"], link["value"]))
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
