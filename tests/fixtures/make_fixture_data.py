"""Deterministic generator for the C1 fixture project's simulated data.

Run from anywhere:

    python3 tests/fixtures/make_fixture_data.py [--seed N]   # write the files
    python3 tests/fixtures/make_fixture_data.py --check      # compare, write nothing

It simulates a paired vaccine cohort (12 donors x day0/day28, 60 genes, 8 true
interferon-response genes up 4-fold in the vaccine arm at day 28), refuses a seed
that fails the selection criteria, runs 01_select_samples.py and 02_paired_test.py
on a temporary copy of the project, and writes:

    mycelium-project/data/processed/vaccine-cohort/sample_metadata.tsv
    mycelium-project/data/processed/vaccine-cohort/counts.tsv
    mycelium-project/analysis/vaccine-response/VACCINE_RESPONSE.md (Key Findings block)
    ../e2e/expected/truth.json, baseline.json, summary.tsv

Seed criteria (docs/design/c1-fixture-project.md, section 4):
  - exactly the 8 true genes at padj < 0.05 under median-of-ratios;
  - at least 3 false positives under total-count CPM.

The simulation reproduces c1_feasibility_probe.py draw for draw, so seed N here
gives the probe's seed N result. stdlib only, Python 3.6 grammar.
"""

import argparse
import difflib
import hashlib
import itertools
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.join(HERE, "mycelium-project")
EXPECTED = os.path.normpath(os.path.join(HERE, "..", "e2e", "expected"))
ANALYSIS = os.path.join("analysis", "vaccine-response")
METADATA = os.path.join("data", "processed", "vaccine-cohort", "sample_metadata.tsv")
COUNTS = os.path.join("data", "processed", "vaccine-cohort", "counts.tsv")
DOC = os.path.join(ANALYSIS, "VACCINE_RESPONSE.md")
DEFAULT_SEED = 0
VISITS = ("day0", "day28")
N_DONORS = 12
TRUE_GENES = ["IFI27", "IFI44L", "ISG15", "MX1", "RSAD2", "SIGLEC1", "IFIT1", "OAS1"]
NULL_GENES = [
    "ACTB", "GAPDH", "B2M", "PPIA", "RPLP0", "TBP", "HPRT1", "PGK1", "YWHAZ", "UBC",
    "SDHA", "GUSB", "HMBS", "TFRC", "ALAS1", "POLR2A", "EEF1A1", "RPL13A", "MARCHF1", "SEPTIN7",
    "CD3E", "CD4", "CD8A", "CD19", "MS4A1", "CD14", "FCGR3A", "NCAM1", "ITGAM", "PTPRC",
    "IL7R", "CCR7", "SELL", "LEF1", "TCF7", "GZMB", "PRF1", "NKG7", "GNLY", "KLRD1",
    "LYZ", "S100A8", "S100A9", "CST3", "FCER1A", "HLA-DRA", "CD74", "JUN", "FOS", "DUSP1",
    "MALAT1", "NEAT1",
]
GENES = TRUE_GENES + NULL_GENES
RERUN = "D03_day28_rerun"
START = "<!-- key-findings:start (written by tests/fixtures/make_fixture_data.py) -->"
END = "<!-- key-findings:end -->"


class SeedRefused(Exception):
    pass


# --- simulation (draw order identical to c1_feasibility_probe.py) -----------------

def simulate(seed, n_genes=60, n_true=8):
    rng = random.Random(seed)
    donors = ["D%02d" % i for i in range(1, N_DONORS + 1)]
    arm = {d: "vaccine" if i < 6 else "placebo" for i, d in enumerate(donors)}
    genes = ["G%03d" % i for i in range(n_genes)]
    true = set(genes[:n_true])
    base = {g: rng.uniform(math.log(50), math.log(2000)) for g in genes}
    lib = {(d, v): rng.uniform(0.7, 1.3) for d in donors for v in VISITS}
    donor = {(g, d): rng.gauss(0, 0.4) for g in genes for d in donors}
    counts = {}
    for g in genes:
        for d in donors:
            for v in VISITS:
                up = g in true and v == "day28" and arm[d] == "vaccine"
                mu = base[g] + donor[g, d] + (math.log(4) if up else 0.0)
                counts[g, d, v] = max(0, int(round(math.exp(mu + rng.gauss(0, 0.25)) * lib[d, v])))
    # Draws below come after the probe's, so they never change its result.
    rerun = {g: max(0, int(round(counts[g, "D03", "day28"] * 1.6 * math.exp(rng.gauss(0, 0.1)))))
             for g in genes}
    rin = {(d, v): rng.uniform(6.5, 9.5) for d in donors for v in VISITS}
    rin[RERUN] = rng.uniform(6.5, 9.5)
    return {"donors": donors, "arm": arm, "genes": genes, "true": true, "counts": counts,
            "rerun": rerun, "rin": rin}


def size_factors(counts, donors, genes, method):
    samples = [(d, v) for d in donors for v in VISITS]
    if method == "cpm":
        return {s: sum(counts[g, s[0], s[1]] for g in genes) / 1e6 for s in samples}
    usable = [g for g in genes if all(counts[g, d, v] > 0 for d, v in samples)]
    geo = {g: sum(math.log(counts[g, d, v]) for d, v in samples) / len(samples) for g in usable}
    factors = {}
    for d, v in samples:
        ratios = sorted(math.log(counts[g, d, v]) - geo[g] for g in usable)
        factors[d, v] = math.exp(ratios[len(ratios) // 2])
    return factors


def found(sim, method):
    donors, genes, counts = sim["donors"], sim["genes"], sim["counts"]
    sf = size_factors(counts, donors, genes, method)
    combos = list(itertools.combinations(range(N_DONORS), 6))
    pvalues = {}
    for g in genes:
        diff = [math.log2(counts[g, d, "day28"] / sf[d, "day28"] + 1)
                - math.log2(counts[g, d, "day0"] / sf[d, "day0"] + 1) for d in donors]
        total = sum(diff)
        observed = abs(sum(diff[:6]) / 6 - sum(diff[6:]) / 6)
        null = [abs(sum(diff[i] for i in c) / 6 - (total - sum(diff[i] for i in c)) / 6) for c in combos]
        pvalues[g] = sum(s >= observed - 1e-12 for s in null) / len(null)
    order = sorted(genes, key=lambda g: pvalues[g])
    adjusted, running = {}, 1.0
    for rank in range(len(genes), 0, -1):
        g = order[rank - 1]
        running = min(running, pvalues[g] * len(genes) / rank)
        adjusted[g] = running
    return set(g for g in genes if adjusted[g] < 0.05)


def symbol(sim, g):
    return GENES[sim["genes"].index(g)]


def select(seed):
    """Return the simulation and its criteria record, or raise SeedRefused."""
    sim = simulate(seed)
    mor, cpm = found(sim, "median-of-ratios"), found(sim, "cpm")
    record = {
        "median_of_ratios": {"true_positives": len(mor & sim["true"]), "false_positives": len(mor - sim["true"])},
        "total_count_cpm": {"true_positives": len(cpm & sim["true"]), "false_positives": len(cpm - sim["true"]),
                            "false_positive_genes": sorted(symbol(sim, g) for g in cpm - sim["true"])},
    }
    if mor != sim["true"]:
        raise SeedRefused("seed {}: median-of-ratios finds {} true and {} false positive(s); need exactly the 8 "
                          "true genes".format(seed, len(mor & sim["true"]), len(mor - sim["true"])))
    if len(cpm - sim["true"]) < 3:
        raise SeedRefused("seed {}: total-count CPM gives {} false positive(s); need at least 3".format(
            seed, len(cpm - sim["true"])))
    return sim, record


# --- rendering --------------------------------------------------------------------

def run_of(donor_index):
    # D01-02 and D07-08 in R1, D03-04 and D09-10 in R2, D05-06 and D11-12 in R3: both arms per run.
    return "R%d" % (donor_index % 6 // 2 + 1)


def render_tables(sim):
    donors, arm = sim["donors"], sim["arm"]
    header = ["sample_id", "donor", "arm", "visit", "run_id", "lane", "preferred_acquisition", "rin"]
    rows = []
    for i, d in enumerate(donors):
        for j, v in enumerate(VISITS):
            sid = "{}_{}".format(d, v)
            rows.append([sid, d, arm[d], v, run_of(i), "L%d" % ((i + j) % 2 + 1), "TRUE",
                         "%.1f" % sim["rin"][d, v]])
            if sid == "D03_day28":
                rows.append([RERUN, d, arm[d], v, run_of(i), "L2", "FALSE", "%.1f" % sim["rin"][RERUN]])
    metadata = "\t".join(header) + "\n" + "".join("\t".join(r) + "\n" for r in rows)

    # Columns in an order different from the metadata, so a positional join is wrong (DC-09).
    columns = sorted([r[0] for r in rows], key=lambda s: (s.split("_")[1], s), reverse=True)
    lines = ["\t".join(["gene"] + columns)]
    for g in sim["genes"]:
        values = []
        for sid in columns:
            if sid == RERUN:
                values.append(sim["rerun"][g])
            else:
                d, v = sid.split("_")
                values.append(sim["counts"][g, d, v])
        lines.append("\t".join([symbol(sim, g)] + [str(x) for x in values]))
    return metadata, "\n".join(lines) + "\n"


def run_scripts(metadata, counts):
    """Run 01 and 02 on a temporary copy of the project; return their outputs."""
    tmp = tempfile.mkdtemp(prefix="mx-fixture-")
    try:
        copy = os.path.join(tmp, "project")
        shutil.copytree(PROJECT, copy)
        for rel, text in ((METADATA, metadata), (COUNTS, counts)):
            path = os.path.join(copy, rel)
            if not os.path.isdir(os.path.dirname(path)):
                os.makedirs(os.path.dirname(path))
            with open(path, "w") as handle:
                handle.write(text)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        for script in ("01_select_samples.py", "02_paired_test.py"):
            subprocess.check_call([sys.executable, os.path.join(copy, ANALYSIS, "scripts", script)],
                                  cwd=copy, env=env, stdout=subprocess.DEVNULL)
        out = {}
        for name in ("samples_used.tsv", "de_results.tsv"):
            with open(os.path.join(copy, ANALYSIS, "outputs", name)) as handle:
                out[name] = handle.read()
        return out
    finally:
        shutil.rmtree(tmp)


def parse_de(text):
    rows = [line.split("\t") for line in text.strip().split("\n")[1:]]
    return [(r[0], float(r[1]), float(r[2]), float(r[3])) for r in rows]


def summarise(de):
    """Python twin of 03_summary.R (R's median, then sprintf("%.4f"))."""
    hits = sorted(r[1] for r in de if r[3] < 0.05)
    n = len(hits)
    median = hits[n // 2] if n % 2 else (hits[n // 2 - 1] + hits[n // 2]) / 2
    return "n_tested\tn_hits\tmedian_log2fc_hits\n{}\t{}\t{:.4f}\n".format(len(de), n, median)


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def claims_block(de, summary_row):
    """D1's checked record: one line per number a cell or a row count holds, naming that cell."""
    hits = [r for r in de if r[3] < 0.05]
    low, high = min(hits, key=lambda r: r[1]), max(hits, key=lambda r: r[1])
    floor = min(de, key=lambda r: (r[2], r[0]))
    top = max(hits, key=lambda r: (r[3], r[0]))
    return [
        "{} | outputs/summary.tsv n_hits".format(len(hits)),
        "{} | outputs/summary.tsv n_tested".format(len(de)),
        "{} | outputs/summary.tsv median_log2fc_hits".format(summary_row["median_log2fc_hits"]),
        "{:.4f} | outputs/de_results.tsv log2fc {}".format(low[1], low[0]),
        "{:.4f} | outputs/de_results.tsv log2fc {}".format(high[1], high[0]),
        "{:.6f} | outputs/de_results.tsv p {}".format(floor[2], floor[0]),
        "{:.6f} | outputs/de_results.tsv padj {}".format(top[3], top[0]),
        "24 | outputs/samples_used.tsv rows",
    ]


def key_findings(de, summary_row):
    hits = [r for r in de if r[3] < 0.05]
    return "\n".join([
        START,
        "- {} of {} genes are at padj < 0.05 (BH), all with positive log2FC (a larger day 28 minus day 0 "
        "change in vaccine than in placebo) [agent-derived: `outputs/summary.tsv`].".format(len(hits), len(de)),
        "- Hits: {} [agent-derived: `outputs/de_results.tsv`].".format(", ".join(sorted(r[0] for r in hits))),
        "- Median log2FC of the hits: {}; range {:.4f} to {:.4f} [agent-derived: `outputs/summary.tsv`].".format(
            summary_row["median_log2fc_hits"], min(r[1] for r in hits), max(r[1] for r in hits)),
        "- Smallest p: {:.6f} (the permutation floor, 2 of 924 labellings); largest padj among the hits: "
        "{:.6f} [agent-derived: `outputs/de_results.tsv`].".format(min(r[2] for r in de), max(r[3] for r in hits)),
        "- 24 libraries from 12 donors (6 vaccine, 6 placebo) after removing {} [agent-derived: `outputs/samples_used.tsv`].".format(RERUN),
        "",
        "<!-- claims",
    ] + claims_block(de, summary_row) + [
        "-->",
        END,
    ])


def fill_doc(text, block):
    if START not in text or END not in text:
        raise SystemExit("{}: Key Findings markers are missing".format(DOC))
    head, rest = text.split(START, 1)
    return head + block + rest.split(END, 1)[1]


def build(seed):
    """Return {path: content} for every generated file."""
    sim, record = select(seed)
    metadata, counts = render_tables(sim)
    out = run_scripts(metadata, counts)
    de = parse_de(out["de_results.tsv"])
    hits = sorted(r[0] for r in de if r[3] < 0.05)
    if hits != sorted(TRUE_GENES):
        raise SeedRefused("seed {}: 02_paired_test.py finds {}, the generator's own analysis finds the 8 true "
                          "genes; the two implementations disagree".format(seed, hits))
    summary = summarise(de)
    names, values = [line.split("\t") for line in summary.strip().split("\n")]
    summary_row = dict(zip(names, values))
    truth = {
        "note": "Simulated ground truth. Kept outside the project so no analysis step can read it.",
        "seed": seed,
        "design": {"donors": N_DONORS, "arms": {"vaccine": sim["donors"][:6], "placebo": sim["donors"][6:]},
                   "visits": list(VISITS), "genes": len(GENES), "true_log2fc": 2.0,
                   "donor_sd_log": 0.4, "residual_sd_log": 0.25, "library_size_factor": [0.7, 1.3],
                   "excluded_library": RERUN},
        "true_genes": TRUE_GENES,
        "null_genes": NULL_GENES,
        "selection": record,
    }
    baseline = {
        "seed": seed,
        "outputs": {
            "samples_used.tsv": {"rows": out["samples_used.tsv"].count("\n") - 1,
                                 "sha256": sha256(out["samples_used.tsv"])},
            "de_results.tsv": {"rows": len(de), "sha256": sha256(out["de_results.tsv"]), "hits": hits},
            "summary.tsv": {"rows": 1, "sha256": sha256(summary), "values": summary_row},
        },
    }
    with open(os.path.join(PROJECT, DOC)) as handle:
        doc = fill_doc(handle.read(), key_findings(de, summary_row))
    return {
        os.path.join(PROJECT, METADATA): metadata,
        os.path.join(PROJECT, COUNTS): counts,
        os.path.join(PROJECT, DOC): doc,
        os.path.join(EXPECTED, "truth.json"): json.dumps(truth, indent=2, sort_keys=True) + "\n",
        os.path.join(EXPECTED, "baseline.json"): json.dumps(baseline, indent=2, sort_keys=True) + "\n",
        os.path.join(EXPECTED, "summary.tsv"): summary,
        os.path.join(EXPECTED, "claims.json"): json.dumps(
            {"doc": DOC, "verified": claims_block(de, summary_row),
             "not_claims": ["28", "0", "0.05", "2", "924", "12", "6", "6"]}, indent=2) + "\n",
    }


def check(files):
    """Return one description per generated file that differs from the committed copy."""
    problems = []
    for path in sorted(files):
        rel = os.path.relpath(path, HERE)
        if not os.path.exists(path):
            problems.append("missing: " + rel)
            continue
        with open(path) as handle:
            committed = handle.read()
        if committed != files[path]:
            diff = difflib.unified_diff(committed.splitlines(), files[path].splitlines(),
                                        "committed/" + rel, "regenerated/" + rel, n=0, lineterm="")
            problems.append("differs: {}\n{}".format(rel, "\n".join(list(diff)[:12])))
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate or check the C1 fixture's simulated data.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--check", action="store_true", help="regenerate in memory and compare; write nothing")
    args = parser.parse_args(argv)
    try:
        files = build(args.seed)
    except SeedRefused as exc:
        print("refused: {}".format(exc))
        return 2
    if args.check:
        problems = check(files)
        for problem in problems:
            print(problem)
        if problems:
            print("fixture check: {} file(s) differ; rerun make_fixture_data.py".format(len(problems)))
            return 1
        print("fixture check: {} file(s) match seed {}".format(len(files), args.seed))
        return 0
    for path in sorted(files):
        if not os.path.isdir(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        with open(path, "w") as handle:
            handle.write(files[path])
        print("wrote " + os.path.relpath(path, HERE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
