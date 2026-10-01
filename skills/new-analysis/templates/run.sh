#!/usr/bin/env bash
# Reproduce every output of @@NAME@@: runs the Snakefile, steps in number order.
# Usage: bash run.sh [snakemake options]   e.g. bash run.sh -n   (dry run)
#        SNAKEMAKE="conda run -n snakemake snakemake" CORES=8 bash run.sh
set -euo pipefail
cd "$(dirname "$0")"
${SNAKEMAKE:-snakemake} --cores "${CORES:-4}" "$@"
