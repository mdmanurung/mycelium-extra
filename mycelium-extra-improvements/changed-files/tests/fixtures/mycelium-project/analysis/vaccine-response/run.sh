#!/usr/bin/env bash
# Run the vaccine-response steps in order. From anywhere: bash analysis/vaccine-response/run.sh
set -euo pipefail
cd "$(dirname "$0")"
python3 scripts/01_select_samples.py
python3 scripts/02_paired_test.py
Rscript scripts/03_summary.R
