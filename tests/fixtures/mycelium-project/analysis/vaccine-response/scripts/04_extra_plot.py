"""Exploratory volcano data, not part of the approved plan.

Writes analysis/vaccine-response/outputs/volcano.tsv (-log10 p against log2FC).
"""

import math
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
DE = os.path.join(ROOT, "analysis", "vaccine-response", "outputs", "de_results.tsv")
OUT = os.path.join(ROOT, "analysis", "vaccine-response", "outputs", "volcano.tsv")


def main():
    with open(DE) as handle:
        rows = [line.rstrip("\n").split("\t") for line in handle][1:]
    with open(OUT, "w") as handle:
        handle.write("gene\tlog2fc\tneg_log10_p\n")
        for gene, log2fc, p, _ in rows:
            handle.write("{}\t{}\t{:.3f}\n".format(gene, log2fc, -math.log10(float(p))))


if __name__ == "__main__":
    main()
