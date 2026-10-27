"""Read an analysis folder and write the Quarto report skeleton for it.

Run from stdin so the gate reads no script path, with every option as --flag=value:
    sh <plugin>/hooks/py.sh - --dest=analysis/<name> --templates=<plugin>/skills/new-analysis/templates
              [--overwrite] [--dry-run] < analysis_report.py

Finds the analysis doc (<NAME>.md or README.md), the numbered steps (NN_*.R|py|ipynb at the root
or in code/), every Snakefile* and the rules and scripts it runs, the dated runs under outputs/
(and where outputs/current points), the PNG figures, *REPORT*.md files and numbers.json. Writes
reports/<name>.qmd from new-analysis's report.qmd template: a mermaid chain per Snakefile (rules in
file order; a folder with no Snakefile chains the steps by number), one Methods tab per step and one
Results tab per step that has figures or a report. Prints the inventory for the agent to fill from.
Refuses to overwrite an existing report unless --overwrite. Stdlib-only; Python 3.9+.
"""

import argparse
import json
import os
import re
import subprocess
import sys

STEP = re.compile(r"^(\d{2})_([A-Za-z0-9][A-Za-z0-9_-]*)\.(R|py|ipynb)$")
LANG = {"R": "r", "py": "python", "ipynb": "python"}


def read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def fill(text, values):
    for key, value in values.items():
        text = text.replace("@@" + key + "@@", value)
    return text


def repo_root(dest):
    try:
        out = subprocess.run(["git", "-C", dest, "rev-parse", "--show-toplevel"], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, encoding="utf-8")
        if out.returncode == 0 and out.stdout.strip():
            return os.path.realpath(out.stdout.strip())
    except OSError:
        pass
    return None


def find_doc(dest, name):
    for candidate in (name.upper().replace("-", "_") + ".md", "README.md"):
        if os.path.isfile(os.path.join(dest, candidate)):
            return candidate
    return None


def find_steps(dest):
    steps = []
    for folder in ("", "code"):
        base = os.path.join(dest, folder)
        if not os.path.isdir(base):
            continue
        for entry in sorted(os.listdir(base)):
            match = STEP.match(entry)
            if match and os.path.isfile(os.path.join(base, entry)):
                steps.append({"num": match.group(1), "stem": entry.rsplit(".", 1)[0], "kind": match.group(3),
                              "path": (folder + "/" if folder else "") + entry})
    return sorted(steps, key=lambda s: (s["num"], s["path"]))


def parse_snakefile(path, step_files):
    """Rules in file order, each with the step script its shell line names, plus the RUN folder."""
    text = read(path)
    run = re.search(r'^RUN\s*=\s*"([^"]+)"', text, re.M)
    rules = []
    heads = list(re.finditer(r"^rule\s+(\w+)\s*:", text, re.M))
    for k, head in enumerate(heads):
        name = head.group(1)
        block = text[head.start():heads[k + 1].start() if k + 1 < len(heads) else len(text)]
        if name == "all":
            continue
        scripts = [f for f in step_files if re.search(r"(?<!\w)" + re.escape(f) + r"(?![\w.])",
                                                      block.split("shell:", 1)[1] if "shell:" in block else "")]
        rules.append({"rule": name, "scripts": scripts})
    return {"file": os.path.basename(path), "run": run.group(1) if run else None, "rules": rules}


def mermaid(snakefiles, steps):
    lines = ["flowchart LR"]
    if not any(s["rules"] for s in snakefiles):
        nodes = ['s{0}["{1}"]'.format(s["num"], s["path"]) for s in steps]
        lines.append("    " + " --> ".join(nodes) if nodes else "    none[no numbered steps found]")
        return "\n".join(lines)
    for k, snake in enumerate(snakefiles):
        if not snake["rules"]:
            continue
        label = snake["file"] + (" → " + snake["run"] if snake["run"] else "")
        lines.append('    subgraph w{}["{}"]'.format(k, label))
        nodes = []
        for j, rule in enumerate(snake["rules"]):
            text = rule["rule"] + (": " + ", ".join(rule["scripts"]) if rule["scripts"] else "")
            nodes.append('r{}_{}["{}"]'.format(k, j, text))
        lines.append("        " + " --> ".join(nodes))
        lines.append("    end")
    return "\n".join(lines)


def scan_outputs(dest):
    base = os.path.join(dest, "outputs")
    found = {"runs": [], "current": None, "figures": [], "reports": [], "numbers": []}
    if not os.path.isdir(base):
        return found
    current = os.path.join(base, "current")
    if os.path.islink(current):
        found["current"] = os.readlink(current)
    for entry in sorted(os.listdir(base)):
        if os.path.isdir(os.path.join(base, entry)) and not os.path.islink(os.path.join(base, entry)):
            found["runs"].append(entry)
    for folder, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(folder, d)) and d not in ("cache", "logs")]
        for file in sorted(files):
            rel = os.path.relpath(os.path.join(folder, file), dest).replace(os.sep, "/")
            if file.endswith(".png"):
                found["figures"].append(rel)
            elif "REPORT" in file and file.endswith(".md"):
                found["reports"].append(rel)
            elif file == "numbers.json":
                found["numbers"].append(rel)
    return found


def methods_tab(step):
    title = "### {} {}".format(step["num"], step["stem"][3:].replace("_", " "))
    return "\n".join([title, "",
                      "[What this step does, in two sentences.] Script: [`{0}`](../{0}).".format(step["path"]), "",
                      '```{{.{} filename="{}"}}'.format(LANG[step["kind"]], step["path"]),
                      "# [the 5-15 lines that do the work, with their line range]", "```", ""])


def results_tab(step, figures, reports):
    title = "### {} {}".format(step["num"], step["stem"][3:].replace("_", " "))
    lines = [title, "",
             "**Question.** [What this tab answers, as one question.]", "",
             "**Approach.** [The data, the model or test, the multiplicity family, in one or two sentences.]", "",
             "**Conclusion.** [The answer with its size and what it does not show.]", ""]
    for n, fig in enumerate(figures, 1):
        lines += ["- [Conclusion] ([figure](../{0})). [agent-derived: `{0}`]".format(fig), "",
                  "![Figure {1}. [caption]. `{0}`](../{0})".format(fig, n), "",
                  "Inspected `{}`: [groups, n, axes, interval type; any defect].".format(fig), ""]
    for rep in reports:
        lines += ["- [Conclusion from the run report]. [agent-derived: `{}`]".format(rep), ""]
    if not figures and not reports:
        lines += ["- [Conclusion] ([figure](../outputs/{}_[what-it-shows].png)). "
                  "[agent-derived: `outputs/{}_[what-it-shows].png`]".format(step["num"], step["num"]), ""]
    return "\n".join(lines)


def main(argv):
    parser = argparse.ArgumentParser(prog="analysis_report")
    parser.add_argument("--dest", required=True, help="the analysis folder")
    parser.add_argument("--templates", required=True, help="new-analysis's templates/ (holds report.qmd)")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing reports/<name>.qmd")
    parser.add_argument("--dry-run", action="store_true", help="print the inventory, write nothing")
    args = parser.parse_args(argv)

    dest = os.path.realpath(args.dest)
    if not os.path.isdir(dest):
        print("refused: {} is not a folder".format(args.dest))
        return 1
    template = os.path.join(args.templates, "report.qmd")
    if not os.path.isfile(template):
        print("refused: no report.qmd under " + args.templates)
        return 1
    name = os.path.basename(dest)
    root = repo_root(dest)
    dest_rel = os.path.relpath(dest, root).replace(os.sep, "/") if root else name
    doc = find_doc(dest, name)
    steps = find_steps(dest)
    step_files = sorted({os.path.basename(s["path"]) for s in steps})  # a shell line names the file, with or without code/
    snakefiles = [parse_snakefile(os.path.join(dest, f), step_files)
                  for f in sorted(os.listdir(dest)) if f.startswith("Snakefile")]
    outputs = scan_outputs(dest)
    by_step = lambda items, num: [i for i in items if os.path.basename(i).startswith(num + "_")]

    inventory = {"name": name, "folder": dest_rel, "doc": doc, "steps": [s["path"] for s in steps],
                 "snakefiles": snakefiles, "outputs": outputs}
    print(json.dumps(inventory, indent=2))
    if doc is None:
        print("note: no <NAME>.md or README.md; the Overview has nothing to copy the Purpose from.")
    if not steps:
        print("note: no NN_*.R|py|ipynb steps at the root or in code/; Methods has no tabs.")

    report = os.path.join(dest, "reports", name + ".qmd")
    report_rel = "reports/" + name + ".qmd"
    if os.path.exists(report) and not args.overwrite:
        print("kept: {}/{} exists; pass --overwrite to replace it".format(dest_rel, report_rel))
        return 0
    results = [results_tab(s, by_step(outputs["figures"], s["num"]), by_step(outputs["reports"], s["num"]))
               for s in steps if by_step(outputs["figures"], s["num"]) or by_step(outputs["reports"], s["num"])] or [
        results_tab(s, [], []) for s in steps]
    text = fill(read(template), {
        "NAME": name, "DOC": doc or "README.md", "DEST": dest_rel, "MERMAID": mermaid(snakefiles, steps),
        "METHODS": "\n".join(methods_tab(s) for s in steps), "RESULTS": "\n".join(results)})
    if "@@" in text:
        print("refused: unresolved placeholder in the template")
        return 1
    if args.dry_run:
        print("would write {}/{}".format(dest_rel, report_rel))
        return 0
    os.makedirs(os.path.dirname(report), exist_ok=True)
    with open(report, "w", encoding="utf-8") as handle:
        handle.write(text)
    print("wrote {}/{}".format(dest_rel, report_rel))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
