"""Read an analysis folder and write the Quarto report skeleton for it.

Run from stdin so the gate reads no script path, with every option as --flag=value:
    <plugin>/hooks/mxpy - --dest=analysis/<name> --templates=<plugin>/skills/new-analysis/templates
              [--overwrite] [--dry-run] < analysis_report.py
    <plugin>/hooks/mxpy - --dest=... --templates=... --outputs-row [--date=YYYY-MM-DD] < analysis_report.py

Finds the analysis doc (<NAME>.md or README.md), the numbered steps (NN_*.R|py|ipynb|qmd|marimo.py at the root
or in code/), every Snakefile and *.smk and the rules and scripts it runs, the current run through
hooks/analysis_paths.py (a steps layout: outputs/<stem>/ per script, figures and source_data gathered over the step folders and paired by stem, qmd pages at outputs/<stem>/<stem>.html; run_<date> folders with a RUN.txt label and a flat outputs/ still work), the PNG figures, *REPORT*.md files and numbers.json. Writes
reports/<name>.qmd from new-analysis's report.qmd template: a mermaid chain per Snakefile (rules in
file order; a folder with no Snakefile chains the steps by number), one Methods tab per step and one
Results tab per step that has figures or a report. Prints the inventory for the agent to fill from.
Refuses to overwrite an existing report unless --overwrite. Stdlib-only; Python 3.9+.
"""

import argparse
import datetime
import fnmatch
import glob
import json
import os
import re
import shutil
import subprocess
import sys

# Snakefile, Snakefile.<name> (not a backup copy) and <name>.smk.
SNAKEFILE = re.compile(r"Snakefile(\.(?!(?:bak|orig|old)$)\w+)?|.+\.smk")

THEMES = ("report.scss", "report-dark.scss")  # Quarto theme from DESIGN.md; report.qmd names both
STEP = re.compile(r"^(\d{2})_([A-Za-z0-9][A-Za-z0-9_-]*)\.(R|py|ipynb|qmd|marimo\.py)$")
LANG = {"R": "r", "py": "python", "ipynb": "python", "marimo.py": "python", "qmd": "r"}  # ponytail: a qmd step in a mixed folder is quoted as r; sniff its chunk if python qmd steps mix in


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


def find_steps(dest):
    steps = []
    for folder in ("", "code"):
        base = os.path.join(dest, folder)
        if not os.path.isdir(base):
            continue
        for entry in sorted(os.listdir(base)):
            match = STEP.match(entry)
            if match and os.path.isfile(os.path.join(base, entry)):
                steps.append({"num": match.group(1), "stem": "{}_{}".format(match.group(1), match.group(2)), "kind": match.group(3),
                              "path": (folder + "/" if folder else "") + entry})
    return sorted(steps, key=lambda s: (s["num"], s["path"]))


def parse_snakefile(path, step_files):
    """Rules in file order, each with the step script its shell line names."""
    text = ap.read(path)
    rules = []
    heads = list(re.finditer(r"^rule\s+(\w+)\s*:", text, re.M))
    for k, head in enumerate(heads):
        name = head.group(1)
        block = text[head.start():heads[k + 1].start() if k + 1 < len(heads) else len(text)]
        if name == "all":
            continue
        shell = block.split("shell:", 1)[1] if "shell:" in block else ""
        inputs = {os.path.basename(v) for v in re.findall(r'\b(?:script|notebook)\s*=\s*"([^"]+)"', block)}
        scripts = [f for f in step_files if f in inputs or re.search(r"(?<!\w)" + re.escape(f) + r"(?![\w.])", shell)]
        rules.append({"rule": name, "scripts": scripts})
    return {"file": os.path.basename(path), "rules": rules}


def mermaid(snakefiles, steps):
    lines = ["flowchart LR"]
    if not any(s["rules"] for s in snakefiles):
        nodes = ['s{0}["{1}"]'.format(s["num"], s["path"]) for s in steps]
        lines.append("    " + " --> ".join(nodes) if nodes else "    none[no numbered steps found]")
        return "\n".join(lines)
    for k, snake in enumerate(snakefiles):
        if not snake["rules"]:
            continue
        lines.append('    subgraph w{}["{}"]'.format(k, snake["file"]))
        nodes = []
        for j, rule in enumerate(snake["rules"]):
            text = rule["rule"] + (": " + ", ".join(rule["scripts"]) if rule["scripts"] else "")
            nodes.append('r{}_{}["{}"]'.format(k, j, text))
        lines.append("        " + " --> ".join(nodes))
        lines.append("    end")
    return "\n".join(lines)


def run_label(run):
    """The run's label: `run:` of RUN.txt, else the folder name; "flat layout" for old analyses;
    "outputs/ (steps)" plus the date of the last logs/CHANGES.md entry for a steps layout."""
    if run is None:
        return None
    if run["layout"] == "steps":
        change = ap.last_change(os.path.dirname(run["path"]))
        return "outputs/ (steps)" + (", last change " + change[3:13] if change else "")
    if run["layout"] == "flat":
        return "flat layout"
    return (run["run_txt"] or {}).get("run") or run["name"]


def scan_outputs(dest):
    base = os.path.join(dest, "outputs")
    found = {"runs": [], "current": None, "run": None, "layout": "none", "figures": [], "reports": [], "numbers": [],
             "source_data_missing": [], "pages": []}
    if not os.path.isdir(base):
        return found
    rel = lambda path: os.path.relpath(path, dest).replace(os.sep, "/")
    listed = ap.runs(dest, "outputs")
    found["runs"] = [r["name"] for r in listed if r["layout"] == "run"] if listed and listed[0]["layout"] in ("run", "steps") else [
        e for e in sorted(os.listdir(base)) if os.path.isdir(os.path.join(base, e)) and not os.path.islink(os.path.join(base, e))]
    run, reason = ap.current_run(dest, "outputs")
    found["layout"] = "flat" if reason == "flat layout" else run["layout"] if run else "none"
    if reason == "outside repository":
        found["current_gap"] = "outputs/current points outside the repository ({}); it is not used.".format(
            os.readlink(os.path.join(base, "current")))
    if run and run["layout"] == "run":
        found["current"], found["run"] = run["name"], run_label(run)
    elif run:
        found["run"] = run_label(run)
    if run and run["layout"] == "steps":
        steps = ap.step_dirs(run)
        found["runs"] = steps
        found["pages"] = [rel(os.path.join(base, e, e + ".html")) for e in steps
                          if os.path.isfile(os.path.join(base, e, e + ".html"))]
    if run and (run["layout"] == "steps" or (run["layout"] == "run" and os.path.isdir(os.path.join(run["path"], "figures")))):
        # A steps or run folder: figures pair with source_data and tables by stem (contract rule 3).
        pngs = [f for f in ap.figures(run) if f.endswith(".png")]
        found["figures"] = [rel(f) for f in pngs]
        have = {ap.stem(f) for f in ap.source_data(run)}
        found["source_data_missing"] = sorted({ap.stem(f): rel(f) for f in sorted(ap.figures(run), key=lambda f: f.endswith(".png"))
                                               if ap.stem(f) not in have}.values())  # PNG last, so it wins a shared stem
        found["tables"] = [rel(t) for t in ap.tables(run)]
        found["reports"] = [rel(os.path.join(h, f)) for h, _, fs in os.walk(run["path"]) for f in sorted(fs)
                            if "REPORT" in f and f.endswith(".md")]
        number = ap.numbers(dest, run)
        found["numbers"] = [rel(number)] if number else []
        return found
    for folder, dirs, files in os.walk(base):  # flat layout, or a run folder with no figures/: walk what is there
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(folder, d)) and d not in ("cache", "logs")]
        for file in sorted(files):
            path = rel(os.path.join(folder, file))
            if file.endswith(".png"):
                found["figures"].append(path)
            elif "REPORT" in file and file.endswith(".md"):
                found["reports"].append(path)
            elif file == "numbers.json":
                found["numbers"].append(path)
    return found


def methods_tab(step):
    title = "### {} {}".format(step["num"], step["stem"][3:].replace("_", " "))
    return "\n".join([title, "",
                      "[What this step does, in two sentences.] Script: [`{0}`](../{0}).".format(step["path"]), "",
                      '```{{.{} filename="{}"}}'.format(LANG[step["kind"]], step["path"]),
                      "# [the 5-15 lines that do the work, with their line range]", "```", ""])


def results_tab(step, figures, reports, missing=()):
    title = "### {} {}".format(step["num"], step["stem"][3:].replace("_", " "))
    lines = [title, "",
             "**Question.** [What this tab answers, as one question.]", "",
             "**Approach.** [The data, the model or test, the multiplicity family, in one or two sentences.]", "",
             "**Conclusion.** [The answer with its size and what it does not show.]", ""]
    for n, fig in enumerate(figures, 1):
        lines += ["- [Conclusion] ([figure](../{0})). [agent-derived: `{0}`]".format(fig), "",
                  "![Figure {1}. [caption]. `{0}`](../{0})".format(fig, n), "",
                  "Inspected `{}`: [groups, n, axes, interval type; any defect].".format(fig), ""]
        if fig in missing:
            lines += ["source data missing: {}".format(fig), ""]
    for rep in reports:
        lines += ["- [Conclusion from the run report]. [agent-derived: `{}`]".format(rep), ""]
    if not figures and not reports:
        lines += ["- [Conclusion] ([figure](../outputs/{}_[what-it-shows].png)). "
                  "[agent-derived: `outputs/{}_[what-it-shows].png`]".format(step["num"], step["num"]), ""]
    return "\n".join(lines)


def outputs_row(dest, name, run, date):
    """Write the render into the analysis doc's `## Outputs` table (one row per path, replaced on a rerun) and
    the run cell of reports/README.md. Returns the lines to print."""
    path = "reports/{}.html".format(name)
    row = "| {} | Quarto report (rendered {}, run {}) |".format(path, date, run)
    doc = ap.find_doc(dest)
    if doc is None:
        return ["refused: no <NAME>.md or README.md to hold the Outputs table"]
    lines = ap.read(doc).split("\n")
    mine = re.compile(r"^\|\s*`?{}`?\s*\|".format(re.escape(path)))
    head = next((i for i, l in enumerate(lines) if re.match(r"^##\s+Outputs\s*$", l)), None)
    if head is None:
        lines += ["", "## Outputs", "", "| File | Description |", "|------|-------------|", row]
    else:
        end = next((i for i in range(head + 1, len(lines)) if lines[i].startswith("#")), len(lines))
        table = [i for i in range(head + 1, end) if lines[i].startswith("|")]
        hit = [i for i in table if mine.match(lines[i])]
        if hit:
            lines[hit[0]] = row
            for i in reversed(hit[1:]):
                del lines[i]
        elif table:
            lines.insert(table[-1] + 1, row)
        else:
            lines[head + 1:head + 1] = ["", "| File | Description |", "|------|-------------|", row]
    with open(doc, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    out = ["wrote the Outputs row for {} in {}".format(path, os.path.basename(doc))]
    readme = os.path.join(dest, "reports", "README.md")
    if os.path.isfile(readme):
        text = ap.read(readme).split("\n")
        for i, line in enumerate(text):
            cells = line.split("|")
            if len(cells) >= 5 and cells[1].strip() in ("`{}.qmd`".format(name), "`{}.html`".format(name)):
                cells[3] = " `{}` ".format(run)
                if cells[1].strip().endswith(".html`"):
                    cells[2] = " its render, {} ".format(date)
                text[i] = "|".join(cells)
        with open(readme, "w", encoding="utf-8") as handle:
            handle.write("\n".join(text))
        out.append("updated the run cell in reports/README.md")
    return out


def lucid_coder_root():
    """The installed lucid-coder root, or None. MX_LUCID_CODER_ROOT is for tests only; otherwise the user-scope
    (then any) install in installed_plugins.json, else the newest folder in the plugin cache."""
    forced = os.environ.get("MX_LUCID_CODER_ROOT")
    if forced:
        return forced if os.path.isfile(os.path.join(forced, "scripts", "rules.js")) else None
    base = os.path.expanduser("~/.claude")
    try:
        with open(os.path.join(base, "plugins", "installed_plugins.json"), encoding="utf-8") as handle:
            installs = [i for k, v in (json.load(handle).get("plugins") or {}).items()
                        if k.split("@")[0] == "lucid-coder" for i in v if isinstance(i, dict)]
        for item in sorted(installs, key=lambda i: i.get("scope") != "user"):
            path = item.get("installPath")
            if path and os.path.isfile(os.path.join(path, "scripts", "rules.js")):
                return path
    except (OSError, ValueError, AttributeError, TypeError):
        pass
    found = sorted(glob.glob(os.path.join(base, "plugins", "cache", "lucid-coder", "lucid-coder", "*", "scripts", "rules.js")))
    return os.path.dirname(os.path.dirname(found[-1])) if found else None


def learned_rules(steps, cwd):
    """Active lucid-coder learned rules that apply to this analysis (global; a language the steps are written in;
    a file-glob that matches a step), as `id topic` strings. Read only, through lucid-coder's own CLI; any failure gives []."""
    plugin, node = lucid_coder_root(), shutil.which("node")
    if not plugin or not node:
        return []
    try:
        done = subprocess.run([node, os.path.join(plugin, "scripts", "rules.js"), "list", "--status", "active", "--json"],
                              cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10, universal_newlines=True)
        rules = json.loads(done.stdout) if done.returncode == 0 else []
    except (OSError, ValueError, subprocess.SubprocessError):
        return []
    langs = {LANG[s["kind"]] for s in steps}
    paths = [s["path"] for s in steps] + ["reports/x.qmd"]
    found = []
    for rule in rules if isinstance(rules, list) else []:
        scope = rule.get("scope") if isinstance(rule, dict) and isinstance(rule.get("scope"), dict) else {}
        if not isinstance(rule, dict) or rule.get("status") != "active" or not rule.get("id"):
            continue
        if scope.get("kind") == "global" or (scope.get("kind") == "language" and scope.get("language") in langs) or (
                scope.get("kind") == "file-glob" and scope.get("glob") and any(
                    fnmatch.fnmatch(p, scope["glob"]) or fnmatch.fnmatch(os.path.basename(p), scope["glob"]) for p in paths)):
            found.append("{} {}".format(rule["id"], rule.get("topic", "")).strip())
    return found


def main(argv):
    parser = argparse.ArgumentParser(prog="analysis_report")
    parser.add_argument("--dest", required=True, help="the analysis folder")
    parser.add_argument("--templates", required=True, help="new-analysis's templates/ (holds report.qmd)")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing reports/<name>.qmd")
    parser.add_argument("--outputs-row", action="store_true",
                        help="after a render: add reports/<name>.html to the doc's Outputs table, update reports/README.md")
    parser.add_argument("--date", help="render date for --outputs-row (default today)")
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
    load_paths(args.templates)
    if args.outputs_row:
        run, _ = ap.current_run(dest, "outputs")
        for line in outputs_row(dest, name, run_label(run) or "none", args.date or datetime.date.today().isoformat()):
            print(line)
        return 0
    root = ap.git_toplevel(dest)
    dest_rel = os.path.relpath(dest, root).replace(os.sep, "/") if root else name
    doc = os.path.basename(ap.find_doc(dest) or "") or None
    steps = find_steps(dest)
    step_files = sorted({os.path.basename(s["path"]) for s in steps})  # a shell line names the file, with or without code/
    snakefiles = [parse_snakefile(os.path.join(dest, f), step_files)
                  for f in sorted(os.listdir(dest))
                  if SNAKEFILE.fullmatch(f) and os.path.isfile(os.path.join(dest, f))]
    outputs = scan_outputs(dest)
    by_step = lambda items, num: [i for i in items if os.path.basename(i).startswith(num + "_")]

    inventory = {"name": name, "folder": dest_rel, "doc": doc, "steps": [s["path"] for s in steps],
                 "snakefiles": snakefiles, "outputs": outputs}
    print(json.dumps(inventory, indent=2))
    if "current_gap" in outputs:
        print("gap: " + outputs["current_gap"])
    rules = learned_rules(steps, dest)
    if rules:
        print("info: lucid-coder learned rules that apply ({}): {}. Follow them in the report text and figures; "
              "`/lucid-coder:rules` shows each one. They are reported here, not enforced.".format(len(rules), "; ".join(rules)))
    if doc is None:
        print("note: no <NAME>.md or README.md; the Overview has nothing to copy the Purpose from.")
    if not steps:
        print("note: no NN_*.R|py|ipynb|qmd|marimo.py steps at the root or in code/; Methods has no tabs.")
    if steps and all(s["kind"] == "qmd" for s in steps):
        print("note: every step is a qmd that carries its own Methods and Results prose and renders to "
              "outputs/<stem>/<stem>.html; no reports/{}.qmd written.".format(name))
        return 0

    report = os.path.join(dest, "reports", name + ".qmd")
    report_rel = "reports/" + name + ".qmd"
    if os.path.exists(report) and not args.overwrite:
        print("kept: {}/{} exists; pass --overwrite to replace it".format(dest_rel, report_rel))
        return 0
    missing = outputs["source_data_missing"]
    results = [results_tab(s, by_step(outputs["figures"], s["num"]), by_step(outputs["reports"], s["num"]), missing)
               for s in steps if by_step(outputs["figures"], s["num"]) or by_step(outputs["reports"], s["num"])] or [
        results_tab(s, [], []) for s in steps]
    text = ap.fill(ap.read(template), {
        "NAME": name, "DOC": doc or "README.md", "DEST": dest_rel, "MERMAID": mermaid(snakefiles, steps),
        "METHODS": "\n".join(methods_tab(s) for s in steps), "RESULTS": "\n".join(results)})
    if missing:  # contract rule 3: a figure with no source_data/ table is an open item
        text = text.replace("## Open items\n\n", "## Open items\n\n" + "".join(
            "- source data missing: {}\n".format(f) for f in missing), 1)
    if "@@" in text:
        print("refused: unresolved placeholder in the template")
        return 1
    # The template's theme files sit beside the report; an existing copy is the user's and is kept.
    themes = [t for t in THEMES if os.path.isfile(os.path.join(args.templates, t))
              and not os.path.exists(os.path.join(dest, "reports", t))]
    if args.dry_run:
        print("would write {}/{}".format(dest_rel, report_rel))
        for theme in themes:
            print("would write {}/reports/{}".format(dest_rel, theme))
        return 0
    os.makedirs(os.path.dirname(report), exist_ok=True)
    with open(report, "w", encoding="utf-8") as handle:
        handle.write(text)
    print("wrote {}/{}".format(dest_rel, report_rel))
    for theme in themes:
        with open(os.path.join(dest, "reports", theme), "w", encoding="utf-8") as handle:
            handle.write(ap.read(os.path.join(args.templates, theme)))
        print("wrote {}/reports/{}".format(dest_rel, theme))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
