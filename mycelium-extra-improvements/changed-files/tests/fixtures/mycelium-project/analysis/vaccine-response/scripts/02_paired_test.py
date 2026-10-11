"""Step 2: paired day 28 minus day 0 change, vaccine versus placebo.

Joins counts to samples_used.tsv by sample_id, computes median-of-ratios size
factors, takes each donor's day28 - day0 difference of log2(normalised + 1),
tests vaccine mean minus placebo mean (reference: placebo) with an exact
two-sided permutation over all arm labellings, and applies BH.
Writes analysis/vaccine-response/outputs/de_results.tsv. SIMULATED data.
"""

import itertools
import math
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
COUNTS = os.path.join(ROOT, "data", "processed", "vaccine-cohort", "counts.tsv")
SAMPLES = os.path.join(ROOT, "analysis", "vaccine-response", "outputs", "samples_used.tsv")
OUT = os.path.join(ROOT, "analysis", "vaccine-response", "outputs", "de_results.tsv")


def read_tsv(path):
    with open(path) as handle:
        lines = [line.rstrip("\n") for line in handle if line.strip() and not line.startswith("#")]
    header = lines[0].split("\t")
    return header, [line.split("\t") for line in lines[1:]]


def size_factors(counts, samples, genes):
    usable = [g for g in genes if all(counts[g][s] > 0 for s in samples)]
    geo = {g: sum(math.log(counts[g][s]) for s in samples) / len(samples) for g in usable}
    factors = {}
    for s in samples:
        ratios = sorted(math.log(counts[g][s]) - geo[g] for g in usable)
        factors[s] = math.exp(ratios[len(ratios) // 2])
    return factors


def bh(pvalues, genes):
    order = sorted(genes, key=lambda g: pvalues[g])
    adjusted, running = {}, 1.0
    for rank in range(len(genes), 0, -1):
        g = order[rank - 1]
        running = min(running, pvalues[g] * len(genes) / rank)
        adjusted[g] = running
    return adjusted


def main():
    header, rows = read_tsv(SAMPLES)
    meta = [dict(zip(header, row)) for row in rows]
    by_donor = {}
    for row in meta:
        by_donor.setdefault(row["donor"], {})[row["visit"]] = row["sample_id"]
    arm = {row["donor"]: row["arm"] for row in meta}
    vaccine = sorted(d for d in by_donor if arm[d] == "vaccine")
    placebo = sorted(d for d in by_donor if arm[d] == "placebo")
    donors = vaccine + placebo
    samples = [by_donor[d][v] for d in donors for v in ("day0", "day28")]

    count_header, count_rows = read_tsv(COUNTS)
    column = {name: i for i, name in enumerate(count_header)}
    genes = [row[0] for row in count_rows]
    counts = {row[0]: {s: int(row[column[s]]) for s in samples} for row in count_rows}

    sf = size_factors(counts, samples, genes)
    n_v = len(vaccine)
    combos = list(itertools.combinations(range(len(donors)), n_v))
    log2fc, pvalues = {}, {}
    for g in genes:
        diff = []
        for d in donors:
            day0, day28 = by_donor[d]["day0"], by_donor[d]["day28"]
            diff.append(math.log2(counts[g][day28] / sf[day28] + 1) - math.log2(counts[g][day0] / sf[day0] + 1))
        total = sum(diff)
        n_p = len(donors) - n_v
        observed = sum(diff[:n_v]) / n_v - sum(diff[n_v:]) / n_p
        null = [abs(sum(diff[i] for i in c) / n_v - (total - sum(diff[i] for i in c)) / n_p) for c in combos]
        log2fc[g] = observed
        pvalues[g] = sum(s >= abs(observed) - 1e-12 for s in null) / len(null)
    padj = bh(pvalues, genes)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as handle:
        handle.write("gene\tlog2fc\tp\tpadj\n")
        for g in genes:
            handle.write("{}\t{:.4f}\t{:.6f}\t{:.6f}\n".format(g, log2fc[g], pvalues[g], padj[g]))
    print("{} libraries, {} donors ({} vaccine, {} placebo), {} genes, {} at padj < 0.05".format(
        len(samples), len(donors), n_v, len(placebo), len(genes), sum(padj[g] < 0.05 for g in genes)))


if __name__ == "__main__":
    main()
