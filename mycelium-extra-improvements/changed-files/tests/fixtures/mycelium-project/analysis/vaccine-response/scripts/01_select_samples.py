"""Step 1: keep the preferred acquisition of each library (decision 2026-04-01).

Reads data/processed/vaccine-cohort/sample_metadata.tsv and writes
analysis/vaccine-response/outputs/samples_used.tsv. SIMULATED data.
"""

import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
METADATA = os.path.join(ROOT, "data", "processed", "vaccine-cohort", "sample_metadata.tsv")
OUT = os.path.join(ROOT, "analysis", "vaccine-response", "outputs", "samples_used.tsv")


def main():
    with open(METADATA) as handle:
        lines = [line.rstrip("\n") for line in handle if line.strip() and not line.startswith("#")]
    header = lines[0].split("\t")
    rows = [dict(zip(header, line.split("\t"))) for line in lines[1:]]
    kept = [row for row in rows if row["preferred_acquisition"] == "TRUE"]
    print("samples in: {}, out: {} (dropped: {})".format(
        len(rows), len(kept), ", ".join(row["sample_id"] for row in rows if row not in kept) or "none"))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as handle:
        handle.write("\t".join(header) + "\n")
        for row in kept:
            handle.write("\t".join(row[column] for column in header) + "\n")


if __name__ == "__main__":
    main()
