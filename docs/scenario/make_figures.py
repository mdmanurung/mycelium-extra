"""Regenerate the docs figures from one real replay of the simulated vaccine scenario.

    python3 docs/scenario/make_figures.py [OUTDIR]

Default output: docs/figures/scenario/*.svg and docs/scenario/facts.json. With OUTDIR, all six
files go there (the test uses this). Standard library only, Python 3.9 or later.

The replay uses tests/e2e/harness.py, which runs the real hooks on a temp copy of
tests/fixtures/mycelium-project: the plan (tests/e2e/plans/baseline_plan.md) is shown, one run is
denied, the plan is approved, the three steps run, and `verify report` runs. R is always hidden, so
step 3 is the harness's stand-in (it copies tests/e2e/expected/summary.tsv) and the figures are the
same on every machine. Output is deterministic: no clock times, fixed float formats, sorted loops.
"""

import importlib.util
import json
import math
import os
import re
import sys
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "tests", "e2e"))
import harness  # noqa: E402

FIG_DIR = os.path.join(REPO, "docs", "figures", "scenario")
FACTS = os.path.join(HERE, "facts.json")

VACCINE, PLACEBO, HIGHLIGHT, GAP, PASS, INFO = "#0072B2", "#E69F00", "#D55E00", "#CC79A7", "#009E73", "#56B4E9"
INK, MUTED, GRID = "#1a1a1a", "#595959", "#d9d9d9"
FONT = "system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
CONTRAST_NULLS = ["ACTB", "GAPDH", "CD3E", "LYZ"]  # null genes drawn next to the 8 IFN genes
W, H = 640, 360


# ---------------------------------------------------------------- the replay

def read_tsv(path):
    with open(path, encoding="utf-8") as handle:
        lines = [l.rstrip("\n") for l in handle if l.strip() and not l.startswith("#")]
    header = lines[0].split("\t")
    return [dict(zip(header, l.split("\t"))) for l in lines[1:]]


def load_step2(project):
    """The fixture's own step 2 module, for its size_factors (not rerun here)."""
    path = project.path(harness.SCRIPTS[1])
    spec = importlib.util.spec_from_file_location("step2", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def replay():
    """Drive the real hooks and read back their state files. Returns plain data."""
    p = harness.Project.fresh(r=False)
    try:
        text = harness.plan_text()
        # plan shown (Stop hook), then a run before approval, then the approval prompt
        shown = p.hook("stop", {"last_assistant_message": text, "stop_hook_active": False,
                                "hook_event_name": "Stop"})
        denied = p.agent_bash("python3 " + harness.SCRIPTS[0])
        if not denied.denied:
            raise SystemExit("the gate allowed a run before approval")
        digest = re.search(r"approve plan ([0-9a-f]{8})", shown["systemMessage"]).group(1)
        reply = p.hook("prompt", {"prompt": "approve plan " + digest, "hook_event_name": "UserPromptSubmit"})
        results = [p.run_step(s) for s in harness.SCRIPTS]
        if any(r.denied or r.code != 0 for r in results):
            raise SystemExit("a planned step failed:\n" + "\n".join(p.log))
        p.space_outputs([(harness.out_of(s), r.receipts[0]) for s, r in zip(harness.SCRIPTS, results)])
        p.lineage()
        code, report, err = p.verify("report", digest)
        if code != 0:
            raise SystemExit("verify report failed: {}{}".format(report, err))

        with open(p.path(".mycelium-extra", "pending", p.session + ".json"), encoding="utf-8") as handle:
            card_full = json.load(handle)[0]["card"]["full"]

        meta = read_tsv(p.path("data", "processed", "vaccine-cohort", "sample_metadata.tsv"))
        used = read_tsv(p.path(harness.OUTPUTS[0]))
        de = read_tsv(p.path(harness.OUTPUTS[1]))
        summary = read_tsv(p.path(harness.OUTPUTS[2]))
        counts = {r["gene"]: r for r in read_tsv(p.path("data", "processed", "vaccine-cohort", "counts.tsv"))}
        step2 = load_step2(p)
        samples = [r["sample_id"] for r in used]
        sf = step2.size_factors({g: {s: int(row[s]) for s in samples} for g, row in counts.items()},
                                samples, sorted(counts))
        by_donor = {}
        for r in used:
            by_donor.setdefault(r["donor"], {})[r["visit"]] = r["sample_id"]
        arm = {r["donor"]: r["arm"] for r in used}
        change = {}  # gene -> donor -> day28 - day0 in log2(normalised + 1), as step 2 computes it
        for g, row in counts.items():
            change[g] = {d: math.log2(int(row[v["day28"]]) / sf[v["day28"]] + 1)
                         - math.log2(int(row[v["day0"]]) / sf[v["day0"]] + 1)
                         for d, v in by_donor.items()}
        return {
            "digest": digest, "plan": text, "shown": shown["systemMessage"], "approve_reply": reply["systemMessage"],
            "denied": denied, "results": results, "report": report, "card_full": card_full,
            "meta": meta, "used": used, "de": de, "summary": summary, "change": change, "arm": arm,
            "approvals": p.read_jsonl("approvals.jsonl"), "denies": p.read_jsonl("denies.jsonl"),
            "receipts": p.receipts(), "scrub": (p.root, p.tmp),
        }
    finally:
        p.close()


# ---------------------------------------------------------------- facts

def parse_report(report, card_full):
    """Verify's verdict, step statuses and gap lines, read from the real report and card."""
    verdict = re.findall(r"^Verify status: (\w+)", report, re.M)[-1]
    sections = dict(re.findall(r"^## (.+?)\n(.*?)(?=^## |\Z)", report, re.M | re.S))
    steps = re.findall(r"^\| `([^`]+)` \| (ran \(exit (\d+)[^)]*\)|[^|]+?) \|", sections["Planned scripts"], re.M)
    ran = re.search(r"^Ran as planned\s+(\w+): (.+?)\s*$", report, re.M)
    numbers = re.search(r"^Numbers match\s+(\w+): (.+?)\s*$", report, re.M)
    prose = re.search(r"(\d+) Validation cells are prose", report)
    inputs = re.findall(r"^\| `([^`]+)` \| sha256 (\w+) \| sha256 (\w+) \|", sections["Pinned inputs"], re.M)
    lint = {}  # script basename -> its lint line on the approval card
    for name, line in re.findall(r"\d (\d\d_\S+?)\*?\n(?:[^\n]*\n)*?\s+- lint: ([^\n]*)", card_full):
        lint[name] = line
    return {"verdict": verdict, "steps": steps, "ran": ran.groups(), "numbers": numbers.groups(),
            "prose_cells": int(prose.group(1)) if prose else 0, "inputs": inputs, "lint": lint,
            "qualified": "**qualified**" in report}


def build_facts(d, rep):
    de = d["de"]
    truth = harness.expected("truth.json")
    hits = [r["gene"] for r in de if float(r["padj"]) < 0.05]
    if sorted(hits) != sorted(truth["true_genes"]):
        raise SystemExit("top hits {} differ from the truth genes {}".format(sorted(hits), sorted(truth["true_genes"])))
    arms = {"vaccine": sorted(k for k, v in d["arm"].items() if v == "vaccine"),
            "placebo": sorted(k for k, v in d["arm"].items() if v == "placebo")}
    ifn = truth["true_genes"]
    mean = lambda xs: sum(xs) / len(xs)
    ifn_change = {a: mean([d["change"][g][x] for g in ifn for x in arms[a]]) for a in arms}
    hit_rows = {r["gene"]: r for r in de}
    kept = sorted(r["sample_id"] for r in d["used"])
    excluded = sorted(r["sample_id"] for r in d["meta"] if r["sample_id"] not in kept)
    deny = d["denies"][0]
    first_line = lambda s: s.strip().splitlines()[0]
    events = timeline(d, rep)
    return {
        "libraries_in": len(d["meta"]), "libraries_kept": len(kept), "libraries_excluded": excluded,
        "donors": 12, "arms": arms, "genes_tested": len(de), "truth_genes": truth["true_genes"],
        "top_hits": hits, "top_hits_equal_truth": True, "n_hits_padj_below_0_05": len(hits),
        "hit_p": float(hit_rows[hits[0]]["p"]), "hit_padj": float(hit_rows[hits[0]]["padj"]),
        "p_floor_denominator": math.comb(12, 6) // 2,
        "hit_log2fc": {g: float(hit_rows[g]["log2fc"]) for g in sorted(hits)},
        "median_log2fc_hits": float(d["summary"][0]["median_log2fc_hits"]),
        "null_p_min": min(float(r["p"]) for r in de if r["gene"] not in hits),
        "null_padj_min": min(float(r["padj"]) for r in de if r["gene"] not in hits),
        "ifn_mean_change_log2": {a: round(v, 2) for a, v in sorted(ifn_change.items())},
        "step_stdout": {s.split("/")[-1]: r.stdout.strip() for s, r in zip(harness.SCRIPTS, d["results"])},
        "denied": {"command": d["denied"].command, "reason_first_line": first_line(deny["reason"])},
        "plan": {"hash": d["digest"], "steps": len(harness.SCRIPTS), "scripts": [s.split("/")[-1] for s in harness.SCRIPTS]},
        "approval": {"hash": d["digest"], "rows": d["approvals"][0]["plan_rows"],
                     "inputs_pinned": len(rep["inputs"])},
        "receipts": [{"ordinal": i + 1, "command": r["command"], "exit": r["exit_status"]}
                     for i, r in enumerate(d["receipts"])],
        "verify": {"status": rep["verdict"], "qualified": rep["qualified"],
                   "ran_as_planned": rep["ran"][1], "numbers_match": rep["numbers"][1],
                   "prose_validation_cells": rep["prose_cells"],
                   "lint_not_checked": sorted(k for k, v in rep["lint"].items() if v.startswith("not checked")),
                   "gap_lines": [g[1] for g in verify_rows(rep) if g[2] == "gap"]},
        "r_available_in_replay": False,
        "r_note": "Rscript is hidden in the replay; step 3 is the harness stand-in that copies expected/summary.tsv.",
        "timeline": [{"ordinal": i + 1, "kind": e[0], "detail": e[1]} for i, e in enumerate(events)],
    }


def timeline(d, rep):
    """(kind, detail) per session event, in the order the state files record them."""
    approval, deny = d["approvals"][0], d["denies"][0]
    short = lambda c: c.split("/")[-1]
    rows = [(approval["shown_ts"], "plan shown", "{}, {} steps, READY".format(d["digest"], approval["plan_rows"])),
            (deny["ts"], "run denied", "{}: no active approved plan covers this run".format(short(d["denied"].command))),
            (approval["approved_ts"], "plan approved", "approve plan {}; 3 scripts and {} inputs pinned".format(
                d["digest"], len(rep["inputs"])))]
    rows += [(r["ts"], "run receipt", "{}, exit {}".format(short(r["command"]), r["exit_status"])) for r in d["receipts"]]
    rows.sort(key=lambda r: r[0])
    out = [(k, t) for _, k, t in rows]
    out.append(("verify", "{}: {}; {}; {} gaps listed".format(
        rep["verdict"], rep["ran"][1], rep["numbers"][1], sum(1 for r in verify_rows(rep) if r[2] == "gap"))))
    return out


def verify_rows(rep):
    """(what, detail, status) per verify row; status is passed, gap or failed."""
    rows = []
    for i, (script, state, code) in enumerate(rep["steps"]):
        name = script.split("/")[-1]
        status = "passed" if state.startswith("ran") and code == "0" else ("failed" if state.startswith("ran") else "gap")
        detail = "ran, exit {}".format(code) if state.startswith("ran") else state.strip()
        if name.endswith(".R"):
            detail += " (stand-in: no Rscript here)"  # the replay always hides R
        rows.append(("Step {}  {}".format(i + 1, name), detail, status))
    rows.append(("Inputs unchanged", "{} pinned files, same sha256".format(len(rep["inputs"])),
                 "passed" if all(a[1] == a[2] for a in rep["inputs"]) else "failed"))
    rows.append(("Claimed numbers", rep["numbers"][1], "passed" if rep["numbers"][0] == "yes" else "failed"))
    if rep["prose_cells"]:
        rows.append(("Validation cells", "{} are prose: nothing checks them".format(rep["prose_cells"]), "gap"))
    for name, line in sorted(rep["lint"].items()):
        if line.startswith("not checked"):
            rows.append(("Lint  " + name, "not checked: Rscript not found", "gap"))
    return rows


# ---------------------------------------------------------------- svg helpers

def n(x):
    s = "%.1f" % x
    return "0.0" if s == "-0.0" else s


def attrs(**kw):
    return "".join(' {}="{}"'.format(k.replace("_", "-"), v) for k, v in kw.items() if v is not None)


class Canvas(object):
    def __init__(self):
        self.parts = []

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, size=12, anchor="start", fill=INK, weight=None, rotate=None):
        tf = ' transform="rotate({} {} {})"'.format(rotate, n(x), n(y)) if rotate is not None else ""
        self.add('<text x="{}" y="{}" font-size="{}"{}{}>{}</text>'.format(
            n(x), n(y), size, attrs(text_anchor=anchor if anchor != "start" else None, fill=fill if fill != INK else None,
                                     font_weight=weight), tf, escape(s)))

    def rect(self, x, y, w, h, fill="none", stroke=None, rx=0, dash=None, sw=1):
        self.add('<rect x="{}" y="{}" width="{}" height="{}" fill="{}"{}/>'.format(
            n(x), n(y), n(w), n(h), fill, attrs(stroke=stroke, stroke_width=sw if stroke else None, rx=rx or None,
                                                stroke_dasharray=dash)))

    def line(self, x1, y1, x2, y2, stroke=GRID, sw=1, dash=None):
        self.add('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="{}" stroke-width="{}"{}/>'.format(
            n(x1), n(y1), n(x2), n(y2), stroke, sw, attrs(stroke_dasharray=dash)))

    def circle(self, x, y, r, fill, stroke="#ffffff", sw=0.8):
        self.add('<circle cx="{}" cy="{}" r="{}" fill="{}" stroke="{}" stroke-width="{}"/>'.format(
            n(x), n(y), n(r), fill, stroke, sw))

    def title(self, s, sub=None):
        self.text(20, 26, s, 14, weight="bold")
        if sub:
            self.text(20, 44, sub, 12, fill=MUTED)

    def render(self, title, desc):
        return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
                'aria-labelledby="t d" font-family="{f}">\n<title id="t">{t}</title>\n<desc id="d">{d}</desc>\n'
                '<rect x="0.5" y="0.5" width="{w1}" height="{h1}" rx="8" fill="#ffffff" stroke="#c8c8c8"/>\n{body}\n</svg>\n'
                ).format(w=W, h=H, w1=W - 1, h1=H - 1, f=FONT, t=escape(title), d=escape(desc), body="\n".join(self.parts))


def scale(d0, d1, r0, r1):
    return lambda v: r0 + (v - d0) * (r1 - r0) / float(d1 - d0)


def legend_dot(c, x, y, color, label):
    c.circle(x, y, 4.5, color)
    c.text(x + 10, y + 4, label, 12)
    return x + 10 + 6.6 * len(label) + 18


# ---------------------------------------------------------------- figures

def fig_samples(d, facts):
    c = Canvas()
    c.title("Samples: 25 libraries in, 24 kept", "Each cell is one library, coloured by arm. Source: sample_metadata.tsv, step 1.")
    donors = sorted(d["arm"])
    x0, cw, ch = 82, 41, 40
    ytop = {"day0": 98, "day28": 98 + ch + 4, "rerun": 98 + 2 * (ch + 4)}
    used = set(r["sample_id"] for r in d["used"])
    for arm, color in (("vaccine", VACCINE), ("placebo", PLACEBO)):
        idx = [i for i, k in enumerate(donors) if d["arm"][k] == arm]
        xs, xe = x0 + idx[0] * cw, x0 + (idx[-1] + 1) * cw - 3
        c.line(xs, 70, xe, 70, color, 3)
        c.text((xs + xe) / 2, 63, "{} ({} donors)".format(arm, len(idx)), 12, "middle")
    for key, label in (("day0", "day 0"), ("day28", "day 28"), ("rerun", "day 28 rerun")):
        c.text(x0 - 8, ytop[key] + ch / 2 + 4, label, 12, "end")
    for i, k in enumerate(donors):
        c.text(x0 + i * cw + (cw - 3) / 2, 90, k, 12, "middle")
    for r in d["meta"]:
        i = donors.index(r["donor"])
        key = "rerun" if r["sample_id"].endswith("_rerun") else r["visit"]
        x, y = x0 + i * cw, ytop[key]
        color = VACCINE if r["arm"] == "vaccine" else PLACEBO
        if r["sample_id"] in used:
            c.rect(x, y, cw - 3, ch, color, rx=3)
        else:
            c.rect(x + 1, y + 1, cw - 5, ch - 2, "#ffffff", color, 3, "4 3", 2)
            c.line(x + 5, y + 5, x + cw - 8, y + ch - 5, HIGHLIGHT, 2)
            c.line(x + cw - 8, y + 5, x + 5, y + ch - 5, HIGHLIGHT, 2)
    ex = facts["libraries_excluded"][0]
    c.text(x0, 250, "Excluded by 01_select_samples.py: {} (preferred_acquisition = FALSE).".format(ex), 12)
    c.text(x0, 268, "The rerun repeats D03's day 28 library; keeping both would count D03 twice.", 12, fill=MUTED)
    c.rect(x0, 292, 14, 14, VACCINE, rx=2); c.text(x0 + 20, 304, "vaccine", 12)
    c.rect(x0 + 90, 292, 14, 14, PLACEBO, rx=2); c.text(x0 + 110, 304, "placebo", 12)
    c.rect(x0 + 190, 292, 14, 14, "#ffffff", VACCINE, 2, "3 2", 1.5)
    c.line(x0 + 193, 295, x0 + 201, 303, HIGHLIGHT, 1.5); c.line(x0 + 201, 295, x0 + 193, 303, HIGHLIGHT, 1.5)
    c.text(x0 + 210, 304, "excluded library", 12)
    c.text(x0, 332, "{} libraries in, {} out: 12 donors x 2 visits.".format(facts["libraries_in"], facts["libraries_kept"]), 12, fill=MUTED)
    return c.render("Samples used in the vaccine scenario",
                    "Grid of 12 donors by day 0 and day 28 libraries coloured by arm (6 vaccine, 6 placebo). The rerun library "
                    "{} is drawn dashed with a cross: step 1 excluded it, so 24 of 25 libraries were kept.".format(
                        facts["libraries_excluded"][0]))


def fig_paired(d, facts):
    c = Canvas()
    genes = facts["truth_genes"] + CONTRAST_NULLS
    c.title("Day 28 minus day 0 change, one dot per donor",
            "Vaccine (6 donors) against placebo (6 donors); 8 IFN genes, 4 null genes.")
    vals = [d["change"][g][k] for g in genes for k in d["arm"]]
    lo, hi = math.floor(min(vals)), math.ceil(max(vals))
    px0, px1, py0, py1 = 58, 626, 76, 262
    y = scale(lo, hi, py1, py0)
    for t in range(lo, hi + 1):
        c.line(px0, y(t), px1, y(t), "#8c8c8c" if t == 0 else GRID, 1.2 if t == 0 else 1)
        c.text(px0 - 6, y(t) + 4, str(t), 12, "end")
    c.text(16, (py0 + py1) / 2, "log2 change (day 28 minus day 0)", 12, "middle", rotate=-90)
    col = (px1 - px0) / float(len(genes))
    arms = {"vaccine": (VACCINE, -1), "placebo": (PLACEBO, 1)}
    for gi, g in enumerate(genes):
        cx = px0 + (gi + 0.5) * col
        for arm, (color, side) in arms.items():
            donors = sorted(k for k in d["arm"] if d["arm"][k] == arm)
            ax = cx + side * 10
            for j, k in enumerate(donors):
                c.circle(ax + (j - 2.5) * 3.2, y(d["change"][g][k]), 3.0, color)
            m = sum(d["change"][g][k] for k in donors) / len(donors)
            c.line(ax - 10, y(m), ax + 10, y(m), INK, 1.6)
        c.text(cx + 3, py1 + 14, g, 12, "end", HIGHLIGHT if gi < 8 else INK, rotate=-40)
    sep = px0 + 8 * col
    c.line(sep, py0, sep, py1, "#8c8c8c", 1, "4 3")
    c.text((px0 + sep) / 2, py0 - 6, "IFN genes (4-fold up in vaccine)", 12, "middle", HIGHLIGHT)
    c.text((sep + px1) / 2, py0 - 6, "null genes", 12, "middle", MUTED)
    c.text((px0 + px1) / 2, 342, "gene", 12, "middle", MUTED)
    x = legend_dot(c, 60, 342, VACCINE, "vaccine")
    x = legend_dot(c, x, 342, PLACEBO, "placebo")
    c.line(x - 6, 342, x + 8, 342, INK, 1.6)
    c.text(x + 14, 346, "arm mean", 12)
    v, p = facts["ifn_mean_change_log2"]["vaccine"], facts["ifn_mean_change_log2"]["placebo"]
    return c.render("Paired change per donor, vaccine versus placebo",
                    "For 8 interferon genes the day 28 minus day 0 log2 change is about {:.1f} in the vaccine arm and "
                    "{:.1f} in placebo; for 4 null genes both arms centre on 0. One dot per donor, bars mark arm means."
                    .format(v, p))


def fig_volcano(d, facts):
    c = Canvas()
    de = d["de"]
    c.title("Volcano: vaccine minus placebo change per gene", "60 genes; exact permutation test, 6 against 6 donors.")
    xs = [float(r["log2fc"]) for r in de]
    ys = [-math.log10(float(r["p"])) for r in de]
    xlo, xhi = math.floor(min(xs) * 2) / 2.0, math.ceil(max(xs) * 2) / 2.0
    yhi = 4.0
    px0, px1, py0, py1 = 62, 618, 56, 288
    X, Y = scale(xlo, xhi, px0, px1), scale(0, yhi, py1, py0)
    t = xlo
    while t <= xhi + 1e-9:
        c.line(X(t), py0, X(t), py1, GRID); c.text(X(t), py1 + 16, "%.1f" % t, 12, "middle"); t += 0.5
    for t in range(0, 5):
        c.line(px0, Y(t), px1, Y(t), GRID); c.text(px0 - 6, Y(t) + 4, str(t), 12, "end")
    c.line(X(0), py0, X(0), py1, "#8c8c8c", 1.2)
    c.text(16, (py0 + py1) / 2, "-log10 p", 12, "middle", rotate=-90)
    c.text((px0 + px1) / 2, 322, "log2 change difference, vaccine minus placebo (log2 units)", 12, "middle", MUTED)
    hits = set(facts["top_hits"])
    for r, x, y in zip(de, xs, ys):
        if r["gene"] not in hits:
            c.circle(X(x), Y(y), 3.5, "#8c8c8c")
    top = sorted(((float(r["log2fc"]), r["gene"], -math.log10(float(r["p"]))) for r in de if r["gene"] in hits))
    mid = sum(X(x) for x, _, _ in top) / len(top)
    for i, (x, g, y) in enumerate(top):
        c.circle(X(x), Y(y), 4.8, HIGHLIGHT)
        lx = mid + (i - (len(top) - 1) / 2.0) * 16
        c.line(X(x), Y(y) - 6, lx, Y(y) - 24, HIGHLIGHT, 1)
        c.text(lx + 4, Y(y) - 28, g, 12, fill=HIGHLIGHT, rotate=-90)
    c.text(px1 - 4, py1 - 10, "all 8: p = {:.4f}, padj = {:.3f}".format(facts["hit_p"], facts["hit_padj"]), 12, "end")
    c.text(px1 - 4, py1 - 26, "p floor is 1/{} (exact test)".format(facts["p_floor_denominator"]), 12, "end", MUTED)
    c.circle(66, 340, 4.8, HIGHLIGHT); c.text(76, 344, "truth gene, found at padj < 0.05", 12)
    c.circle(300, 340, 3.5, "#8c8c8c"); c.text(310, 344, "other genes (52)", 12)
    return c.render("Volcano plot of the paired test",
                    "Effect (log2 change difference) against -log10 p for 60 genes. The 8 interferon truth genes sit at "
                    "p = {:.4f} (padj {:.3f}) with effects from {:.1f} to {:.1f}; the other 52 genes are not significant."
                    .format(facts["hit_p"], facts["hit_padj"], top[0][0], top[-1][0]))


CHIP = {"passed": PASS, "gap": GAP, "failed": HIGHLIGHT}


def fig_verify(d, facts, rep):
    c = Canvas()
    c.title("Verify outcome: {}".format(rep["verdict"]), "Read from `verify report {}` after the replay.".format(d["digest"]))
    rows = verify_rows(rep)
    y0, rh = 62, 31
    for i, (what, detail, status) in enumerate(rows):
        y = y0 + i * rh
        c.line(20, y + rh - 4, 620, y + rh - 4, "#eeeeee")
        c.text(20, y + 16, what, 12, weight="bold")
        c.rect(238, y + 2, 62, 20, CHIP[status], rx=10)
        c.text(269, y + 16, status, 12, "middle", "#ffffff" if status != "gap" else INK)
        c.text(312, y + 16, detail, 12)
    yy = y0 + len(rows) * rh + 12
    x = 20
    for label, color in (("passed", PASS), ("gap: not checked, not failed", GAP), ("failed", HIGHLIGHT)):
        c.rect(x, yy, 12, 12, color, rx=3); c.text(x + 18, yy + 11, label, 12); x += 18 + 6.3 * len(label) + 24
    c.text(20, yy + 36, "A gap means no check existed, not that a check failed.", 12, fill=MUTED)
    gaps = [r for r in rows if r[2] == "gap"]
    return c.render("Verify outcome for the approved plan",
                    "Verdict {} with {} rows: {} passed, {} gaps and {} failed. Gaps are the prose validation cells and "
                    "the R lint that was not run.".format(rep["verdict"], len(rows), sum(r[2] == "passed" for r in rows),
                                                          len(gaps), sum(r[2] == "failed" for r in rows)))


def fig_timeline(d, facts, rep):
    c = Canvas()
    events = timeline(d, rep)
    c.title("One session, in order", "Events read from the gate's state files; numbers are the order, not clock times.")
    color = {"plan shown": INFO, "run denied": HIGHLIGHT, "plan approved": PASS, "run receipt": PASS, "verify": VACCINE}
    y0, rh = 72, 36
    c.line(36, y0, 36, y0 + (len(events) - 1) * rh, "#8c8c8c", 2)
    for i, (kind, detail) in enumerate(events):
        y = y0 + i * rh
        c.circle(36, y, 11, color[kind], "#ffffff", 2)
        c.text(36, y + 4, str(i + 1), 12, "middle", "#ffffff" if kind != "plan shown" else INK, weight="bold")
        c.text(62, y - 1, kind, 12, weight="bold")
        c.text(62, y + 14, detail, 12, fill=MUTED)
    return c.render("Session timeline of the scenario",
                    "{} events in order: the plan is shown, a run is denied before approval, the plan is approved, three "
                    "runs leave receipts, and verify reports {}.".format(len(events), rep["verdict"]))


# ---------------------------------------------------------------- main

def main(outdir=None):
    d = replay()
    rep = parse_report(d["report"], d["card_full"])
    facts = build_facts(d, rep)
    svgs = {"samples.svg": fig_samples(d, facts), "paired-change.svg": fig_paired(d, facts),
            "volcano.svg": fig_volcano(d, facts), "verify-outcome.svg": fig_verify(d, facts, rep),
            "session-timeline.svg": fig_timeline(d, facts, rep)}
    fig_dir, facts_path = (outdir, os.path.join(outdir, "facts.json")) if outdir else (FIG_DIR, FACTS)
    os.makedirs(fig_dir, exist_ok=True)
    for name, text in sorted(svgs.items()):
        with open(os.path.join(fig_dir, name), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    with open(facts_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(facts, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print("wrote {} figures and {}".format(len(svgs), facts_path))


if __name__ == "__main__":
    try:
        main(sys.argv[1] if len(sys.argv) > 1 else None)
    except harness.HarnessError as error:
        sys.exit("replay failed: {}".format(error))
