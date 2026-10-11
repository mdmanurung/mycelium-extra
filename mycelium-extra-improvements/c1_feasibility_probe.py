"""Feasibility probe for the C1 fixture's simulated data (not the fixture generator).

Question: can a stdlib-only paired design give a clean, known ground truth that an
exact permutation test plus BH recovers, and does total-count CPM break it?

Design: 12 donors (6 vaccine, 6 placebo) x 2 visits; 60 genes, the first 8 up
4-fold (log2FC 2) at day 28 in the vaccine arm only. Test: per-donor day28 - day0
difference of log2 normalised counts, vaccine mean minus placebo mean, exact
two-sided permutation over the C(12,6) = 924 arm labellings, BH at 0.05.

Run: python3 c1_feasibility_probe.py
"""

import itertools
import math
import random

VISITS = ("day0", "day28")


def simulate(seed, n_genes=60, n_true=8):
    rng = random.Random(seed)
    donors = ["D%02d" % i for i in range(1, 13)]
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
    return donors, genes, true, counts


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


def hits(seed, method):
    donors, genes, true, counts = simulate(seed)
    sf = size_factors(counts, donors, genes, method)
    combos = list(itertools.combinations(range(12), 6))
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
    found = {g for g in genes if adjusted[g] < 0.05}
    return len(found & true), len(found - true)


if __name__ == "__main__":
    clean = 0
    for seed in range(30):
        mor, cpm = hits(seed, "median-of-ratios"), hits(seed, "cpm")
        clean += mor == (8, 0)
        print("seed {:2d}  median-of-ratios TP/FP {}  total-count CPM TP/FP {}".format(seed, mor, cpm))
    print("seeds where median-of-ratios recovers exactly the 8 true genes: {}/30".format(clean))
