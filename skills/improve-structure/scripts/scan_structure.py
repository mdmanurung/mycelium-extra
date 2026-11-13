"""Scan one analysis folder, or a folder of analyses, for structural friction. Read-only, stdlib only.

Run: sh <skill-dir>/../../hooks/py.sh - PATH [--json] [--dup-lines 8] [--long-script 300] [--long-pipe 15] < <skill-dir>/scripts/scan_structure.py

PATH is an analysis folder (it has code/) or a folder holding analyses (each with code/). The scan
reads code/, the Snakefile, plans/, logs/CHANGES.md and git history. It writes nothing.
Output: a text summary, or with --json the same findings as JSON. Exit 0 always, 2 for a bad PATH.
A finding is a place to look, never a verdict: the user decides what to change.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

CODE_EXT = (".R", ".r", ".py", ".qmd", ".Rmd", ".rmd", ".ipynb")
SCRIPT_EXT = (".R", ".r", ".py")
DOC_EXT = (".qmd", ".Rmd", ".rmd", ".ipynb")
STEP = re.compile(r"^(\d{2}[a-z]?)_")
STEP_FILE = re.compile(r"""["'/](\d{2}[a-z]?)_[\w.-]*?\.(?:rds|tsv|csv|parquet|h5ad|txt|json|RData|rda|qs|xlsx|loom|mtx|h5|png|pdf|html)\b""")
OUT_STEP = re.compile(r"outputs/(\d{2}[a-z]?_[\w-]+)")
ABS_OUT = re.compile(r"""["'](?:/|~/)[^"']*outputs/(\d{2}[a-z]?_[\w-]+)""")
STEP_LITERAL = re.compile(r"""["'/](\d{2}[a-z]?)_[\w-]""")
STRING = re.compile(r"""("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')""")
# `dirname(output...)` is the step's own folder, so it is not a shared-folder token.
SHARED = (("dirname", re.compile(r"dirname\(\s*(?!output)")),
          ("base_dir", re.compile(r"\b[Bb][Aa][Ss][Ee]_[Dd][Ii][Rr]\b")),
          ("run_dir", re.compile(r"\b[Rr][Uu][Nn]_[Dd][Ii][Rr]\b")),
          ("file.path(run", re.compile(r"file\.path\(\s*run\b")),
          ("TP_BASE", re.compile(r"\bTP_BASE\b")),
          ("old run folder", re.compile(r"outputs/run_|\brun_\d{8}_")))
IMPORT = re.compile(r"^(library|require|suppressPackageStartupMessages|import |from \S+ import|source\()")
PIPE_END = re.compile(r"(\|>|%>%)\s*$")
HEAVY = re.compile(
    r"\b(lmFit|glmFit|glmQLFit|voomWithQualityWeights|voom|calcNormFactors|DESeq|dream|FindMarkers|FindClusters|"
    r"RunUMAP|RunPCA|NormalizeData|FindNeighbors|IntegrateData|runUMAP|runPCA|buildSNNGraph|glmmTMB|lmer|glmer|"
    r"rank_genes_groups|sc\.pp\.neighbors|sc\.tl\.umap|sc\.tl\.leiden|sc\.pp\.pca|sc\.pp\.normalize_total|"
    r"sc\.pp\.highly_variable_genes|\.fit|model\.train|scvi\.model|mixedlm|smf\.ols|smf\.glm)\s*\(")
WRITE = re.compile(r"\b(saveRDS|write_h5ad|write_tsv|write_csv|write_parquet|to_parquet|to_csv|write\.table|write\.csv)\s*\(")
READ_CALL = re.compile(r"\b(readRDS|read_tsv|read_csv|read_parquet|read_delim|fread|read\.table|read\.csv|load|scan|"
                       r"read_h5ad|sc\.read\w*|ad\.read\w*|anndata\.read\w*|pd\.read_\w+|open)\s*\(")
UPPER_ASSIGN = re.compile(r"^\s*[A-Z][A-Z0-9_]{2,}\s*(<-|=)(?!=)")
COMPARE_NUM = re.compile(r"(<=|>=|<|>)\s*-?\d*\.\d+")
KEYWORD_NUM = re.compile(
    r"\b(resolution|n_neighbors|min_cells|min_genes|min_counts|n_pcs|npcs|nfeatures|n_top_genes|perplexity|"
    r"threshold|cutoff|min_dist|lfc|fdr|k\.param|n\.neighbors|min\.cells|min\.features)\s*=\s*-?\d")
SEED_NUM = re.compile(r"(set\.seed\(\s*\d+|\b(random_state|seed|rng_seed)\s*=\s*\d+|np\.random\.seed\(\s*\d+)")
PLOT = re.compile(r"\b(ggplot|ggsave|plot_grid|plotnine|plt\.subplots|plt\.figure|sc\.pl\.|sns\.)")
THEME_REF = re.compile(r"(source\([^)]*theme|here\([^)]*theme|from theme import|import theme\b|run_path\([^)]*theme|"
                       r"exec\([^)]*theme)")
THEME_INLINE = re.compile(r"\b(theme_set|theme_pubr|theme_prism|theme_bw|theme_classic|theme_minimal|"
                          r"plt\.rcParams|rcParams\.update|plt\.style\.use|sns\.set_theme|sns\.set_style)\b")
HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")
PLACEHOLDER = {"", "-", "--", "—", "–", "none", "n/a", "na", "tbd", "todo"}


def read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def code_lines(path):
    """[(line number, text)] of the code in a file. Scripts: every line. qmd/Rmd: chunk bodies. ipynb: code cells."""
    text = read(path)
    if path.endswith(".ipynb"):
        try:
            cells = json.loads(text).get("cells", [])
        except ValueError:
            return []
        out, number = [], 0
        for cell in cells:
            source = cell.get("source", [])
            lines = source.splitlines() if isinstance(source, str) else [s.rstrip("\n") for s in source]
            for line in lines:
                number += 1
                if cell.get("cell_type") == "code":
                    out.append((number, line))
        return out
    lines = text.splitlines()
    if path.endswith((".qmd", ".Rmd", ".rmd")):
        out, inside = [], False
        for number, line in enumerate(lines, 1):
            if re.match(r"^\s*```\s*\{", line):
                inside = True
            elif re.match(r"^\s*```\s*$", line) and inside:
                inside = False
            elif inside and not line.lstrip().startswith("#|"):
                out.append((number, line))
        return out
    return list(enumerate(lines, 1))


def is_comment(line):
    return line.lstrip().startswith("#")


def code_files(code_dir):
    return [n for n in sorted(os.listdir(code_dir))
            if n.endswith(CODE_EXT) and os.path.isfile(os.path.join(code_dir, n)) and not os.path.islink(os.path.join(code_dir, n))]


def stem_of(name):
    return name.rsplit(".", 1)[0]


def find_analyses(path):
    if os.path.isdir(os.path.join(path, "code")):
        return [path]
    found = []
    for here, dirs, _ in os.walk(path):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in ("outputs", "data", "node_modules", "__pycache__"))
        if "code" in dirs and here != path:
            found.append(here)
            dirs[:] = []
    return found


def finding(kind, files, lines=None, detail="", **extra):
    item = {"kind": kind, "files": files, "lines": lines or [], "detail": detail}
    item.update(extra)
    return item


# ---- detectors --------------------------------------------------------------------------------

def cross_step_reads(code_dir, files):
    """Shared-folder reads, absolute paths into another step's folder, and fan-in.

    A shared-folder token (base_dir, run_dir, dirname(input)) counts only on a line that reads a file
    or names another step ("01_valid-tags.rds", "01b_scar"). The same tokens also build a step's own
    output paths, and those lines are not reads. Fan-in counts only steps that have a script here.
    """
    out = []
    known = {STEP.match(n).group(1) for n in files if STEP.match(n)}
    for name in files:
        if name.startswith("theme."):
            continue
        own = STEP.match(name).group(1) if STEP.match(name) else None
        stem = stem_of(name)
        others, shared, absolute = set(), [], []
        for number, line in code_lines(os.path.join(code_dir, name)):
            if is_comment(line):
                continue
            reads_other = READ_CALL.search(line) or any(
                m.group(1) != own for m in STEP_LITERAL.finditer(line)
            )
            for label, pattern in SHARED:
                if pattern.search(line) and (reads_other or label == "old run folder"):
                    shared.append((number, label))
                    break
            for match in ABS_OUT.finditer(line):
                if match.group(1) != stem:
                    absolute.append(number)
            for match in OUT_STEP.finditer(line):
                number_of = STEP.match(match.group(1)).group(1)
                if match.group(1) != stem and number_of != own:
                    others.add(number_of)
            for match in STEP_FILE.finditer(line):
                if match.group(1) != own:
                    others.add(match.group(1))
        if shared:
            out.append(finding("shared_folder_read", [name], [n for n, _ in shared[:10]],
                               "reads another step's file through a shared folder ({}); name the producing step's file in one explicit path"
                               .format(", ".join(sorted({label for _, label in shared})))))
        if absolute:
            out.append(finding("absolute_step_path", [name], absolute[:10],
                               "absolute path into another step's outputs folder; it breaks on another machine"))
        others &= known
        if len(others) > 2:
            out.append(finding("fan_in", [name], [], "reads {} other steps ({}); a step with this many inputs hides its seams"
                               .format(len(others), ", ".join(sorted(others))), steps=sorted(others)))
    return out


def normalised(code_dir, name):
    """[(line number, normalised text)] without blanks, comments and import lines."""
    out = []
    for number, line in code_lines(os.path.join(code_dir, name)):
        text = re.sub(r"\s+", " ", line.strip())
        if not text or text.startswith("#") or IMPORT.match(text) or text in ("}", ")", "})", "]", "{", "("):
            continue
        out.append((number, text))
    return out


def duplicated_blocks(code_dir, files, size):
    """Runs of `size` or more identical normalised lines in 2 or more files."""
    seqs = {n: normalised(code_dir, n) for n in files}
    windows = {}
    for name, seq in seqs.items():
        for i in range(len(seq) - size + 1):
            key = hashlib.sha1("\n".join(t for _, t in seq[i:i + size]).encode()).hexdigest()
            windows.setdefault(key, []).append((name, i))
    pairs = {}
    for places in windows.values():
        for a in range(len(places)):
            for b in range(a + 1, len(places)):
                (na, ia), (nb, ib) = places[a], places[b]
                if na != nb:
                    pairs.setdefault((na, nb), set()).add((ia, ib))
    out = []
    for (na, nb), starts in sorted(pairs.items()):
        runs = []
        for ia, ib in sorted(starts):
            if runs and ia == runs[-1][1] + 1 and ib == runs[-1][3] + 1:
                runs[-1][1], runs[-1][3] = ia, ib
            else:
                runs.append([ia, ia, ib, ib])
        for first_a, last_a, first_b, _ in runs:
            length = last_a - first_a + size
            la, lb = seqs[na][first_a][0], seqs[nb][first_b][0]
            out.append(finding("duplicated_block", [na, nb], [la, lb],
                               "{} identical lines in both scripts (from line {} and line {}); a shared function or step would "
                               "hold them once, if the lab rule of 3+ calls or 2+ scripts is met".format(length, la, lb),
                               length=length))
    return out


def long_scripts(code_dir, files, long_script, long_pipe):
    out = []
    for name in files:
        lines = code_lines(os.path.join(code_dir, name))
        if name.endswith(SCRIPT_EXT) and len(lines) > long_script:
            out.append(finding("long_script", [name], [], "{} lines; the script likely does more than one step".format(len(lines)),
                               count=len(lines)))
        best, best_start, run, start, previous = 0, 0, 0, 0, ""
        for number, line in lines:
            text = line.strip()
            if not text or is_comment(text):
                continue
            if PIPE_END.search(previous) or (text.startswith(".") and run):
                run += 1
            else:
                run, start = 1, number
            if run > best:
                best, best_start = run, start
            previous = text
        if best > long_pipe:
            out.append(finding("long_pipe", [name], [best_start], "a chain of {} lines; split it into named steps".format(best),
                               count=best))
    return out


def heavy_documents(code_dir, files):
    out = []
    for name in files:
        if not name.endswith(DOC_EXT):
            continue
        heavy, writes, lines = set(), set(), []
        for number, line in code_lines(os.path.join(code_dir, name)):
            if is_comment(line):
                continue
            for match in HEAVY.finditer(line):
                heavy.add(match.group(1))
                lines.append(number)
            for match in WRITE.finditer(line):
                writes.add(match.group(1))
                lines.append(number)
        if len(heavy) >= 2 or (heavy and writes):
            out.append(finding("heavy_notebook", [name], sorted(set(lines))[:10],
                               "a notebook or qmd page computes ({}); scripts compute and notebooks show"
                               .format(", ".join(sorted(heavy | writes)))))
    return out


def missing_rules(folder, files):
    scripts = [n for n in files if STEP.match(n)]
    snake = os.path.join(folder, "Snakefile")
    if not os.path.isfile(snake):
        return [finding("no_snakefile", [], [], "no Snakefile; the run order lives in the file names only")] if scripts else []
    text = read(snake)
    return [finding("no_rule", [n], [], "no Snakefile rule names this script, so a pipeline run skips it")
            for n in scripts if n not in text]


def validation_rows(folder):
    """[(row text, Validation cell)] from markdown tables with a Validation column in plans/ and the analysis doc."""
    paths = []
    plans = os.path.join(folder, "plans")
    if os.path.isdir(plans):
        paths += [os.path.join(plans, f) for f in sorted(os.listdir(plans)) if f.endswith(".md")]
    for name in ("README.md", os.path.basename(folder).upper().replace("-", "_") + ".md"):
        if os.path.isfile(os.path.join(folder, name)):
            paths.append(os.path.join(folder, name))
    rows = []
    for path in paths:
        index = None
        for line in read(path).splitlines():
            if not line.lstrip().startswith("|"):
                index = None
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if index is None:
                index = next((i for i, c in enumerate(cells) if c.lower().startswith("validation")), None)
            elif index < len(cells) and not re.match(r"^:?-{2,}:?$", cells[0]):
                rows.append((line, cells[index]))
    return rows


def unchecked_steps(folder, files):
    rows = validation_rows(folder)
    out = []
    for name in files:
        if not STEP.match(name):
            continue
        stem = stem_of(name)
        has = any((name in row or stem in row) and cell.strip().lower() not in PLACEHOLDER for row, cell in rows)
        if not has:
            wanted = ("check_" + stem, "test_" + stem, "check_" + stem[3:], "test_" + stem[3:])
            for check_dir in ("tests", "checks", "code"):
                path = os.path.join(folder, check_dir)
                if os.path.isdir(path) and any(f.startswith(wanted) for f in os.listdir(path)):
                    has = True
        if not has:
            out.append(finding("no_check", [name], [], "no plan row with a Validation cell and no check file for this step"))
    return out


def midscript_parameters(code_dir, files):
    out = []
    for name in files:
        if not name.endswith(SCRIPT_EXT):
            continue
        lines = code_lines(os.path.join(code_dir, name))
        top_end = next((n for n, l in lines if not is_comment(l) and READ_CALL.search(l)), 40)
        hits, knobs = [], []
        depth = 0
        for number, line in lines:
            depth_before = depth
            bare = STRING.sub('""', line.split("#", 1)[0])
            depth += sum(bare.count(c) for c in "([{") - sum(bare.count(c) for c in ")]}")
            if number <= top_end or is_comment(line):
                continue
            if depth_before > 0:
                continue  # a named argument or dict entry inside a call, not a new assignment
            if UPPER_ASSIGN.match(line):
                knobs.append(number)
            elif COMPARE_NUM.search(line) or KEYWORD_NUM.search(line) or SEED_NUM.search(line):
                hits.append(number)
        if len(hits) >= 2:
            out.append(finding("midscript_parameter", [name], hits[:10],
                               "{} hard-coded values (thresholds, counts, seeds) after the first data read; knobs belong at the "
                               "top with a reason beside each".format(len(hits)), count=len(hits)))
        if knobs:
            out.append(finding("knob_not_at_top", [name], knobs[:10], "UPPER_SNAKE value set after the first data read"))
    return out


def plot_style(code_dir, files):
    out, plotting, palettes = [], [], {}
    theme_file = any(os.path.isfile(os.path.join(code_dir, f)) for f in ("theme.R", "theme.py"))
    for name in files:
        if name.startswith("theme.") or not name.endswith(SCRIPT_EXT + (".qmd", ".Rmd", ".rmd")):
            continue
        lines = code_lines(os.path.join(code_dir, name))
        code = [l for _, l in lines if not is_comment(l)]
        if any(PLOT.search(l) for l in code):
            plotting.append((name, any(THEME_REF.search(l) for l in code),
                             [n for n, l in lines if THEME_INLINE.search(l) and not is_comment(l)]))
        for number, line in lines:
            if not is_comment(line) and len(set(HEX.findall(line))) >= 3:
                palettes.setdefault(name, number)
    for name, uses_theme, inline in plotting:
        if not uses_theme and (theme_file or len(plotting) >= 2):
            out.append(finding("plot_without_theme", [name], inline[:5],
                               "plots without sourcing the shared theme file" if theme_file else
                               "plots with its own theme; {} scripts plot and none shares a theme file".format(len(plotting))))
    if len(palettes) >= 2:
        out.append(finding("palette_repeated", sorted(palettes), [palettes[n] for n in sorted(palettes)],
                           "hex colour lists written out in {} scripts; keep one palette in the theme file".format(len(palettes))))
    return out


def edit_counts(folder):
    """{code file: {"changes_md": n, "git": n}} from logs/CHANGES.md and git history."""
    counts = {}
    log = os.path.join(folder, "logs", "CHANGES.md")
    if os.path.isfile(log):
        for line in read(log).splitlines():
            match = re.match(r"^\s*-\s+`?code/([^\s`(]+)", line)
            if match:
                counts.setdefault(match.group(1), {"changes_md": 0, "git": 0})["changes_md"] += 1
    try:
        prefix = subprocess.run(["git", "-C", folder, "rev-parse", "--show-prefix"], capture_output=True, text=True, timeout=30)
        history = subprocess.run(["git", "-C", folder, "log", "--name-only", "--format=", "--", "code"],
                                 capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return counts
    if prefix.returncode == 0 and history.returncode == 0:
        start = prefix.stdout.strip() + "code/"
        for line in history.stdout.splitlines():
            if line.startswith(start):
                counts.setdefault(line[len(start):], {"changes_md": 0, "git": 0})["git"] += 1
    return counts


def hot_spots(folder, top):
    ranked = sorted(edit_counts(folder).items(), key=lambda kv: (-(kv[1]["changes_md"] + kv[1]["git"]), kv[0]))
    return [{"file": "code/" + k, "git_commits": v["git"], "changes_md_entries": v["changes_md"]}
            for k, v in ranked[:top] if v["git"] + v["changes_md"] >= 2]


def scan(folder, args):
    code_dir = os.path.join(folder, "code")
    files = code_files(code_dir)
    findings = []
    findings += cross_step_reads(code_dir, files)
    findings += duplicated_blocks(code_dir, files, args.dup_lines)
    findings += long_scripts(code_dir, files, args.long_script, args.long_pipe)
    findings += heavy_documents(code_dir, files)
    findings += missing_rules(folder, files)
    findings += unchecked_steps(folder, files)
    findings += midscript_parameters(code_dir, files)
    findings += plot_style(code_dir, files)
    return {"path": folder, "files": files, "hot_spots": hot_spots(folder, 5), "findings": findings}


def summary(result):
    lines = []
    for item in result["analyses"]:
        lines.append("{}  ({} code files, {} findings)".format(item["path"], len(item["files"]), len(item["findings"])))
        if item["hot_spots"]:
            lines.append("  Edited most: " + "; ".join("{} ({} commits, {} log entries)".format(
                h["file"], h["git_commits"], h["changes_md_entries"]) for h in item["hot_spots"]))
        for f in item["findings"]:
            where = ", ".join(f["files"]) or "(analysis)"
            at = " line " + ",".join(str(n) for n in f["lines"]) if f["lines"] else ""
            lines.append("  {}: {}{}: {}".format(f["kind"], where, at, f["detail"]))
        if not item["findings"]:
            lines.append("  No findings.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("path")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dup-lines", type=int, default=8)
    parser.add_argument("--long-script", type=int, default=300)
    parser.add_argument("--long-pipe", type=int, default=15)
    args = parser.parse_args()
    if not os.path.isdir(args.path):
        print("not a folder: " + args.path, file=sys.stderr)
        return 2
    folders = find_analyses(os.path.abspath(args.path))
    if not folders:
        print("no analysis found under {} (no folder with code/)".format(args.path), file=sys.stderr)
        return 2
    result = {"root": os.path.abspath(args.path), "analyses": [scan(f, args) for f in folders]}
    print(json.dumps(result, indent=2) if args.json else summary(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
