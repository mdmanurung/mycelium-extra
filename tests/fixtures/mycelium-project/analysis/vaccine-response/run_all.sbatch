#!/bin/bash
#SBATCH --job-name=vaccine-response
#SBATCH --time=00:10:00
#SBATCH --mem=1G
#SBATCH --cpus-per-task=1
#SBATCH --output=logs/slurm-%j.out
# Submit from the project root: sbatch analysis/vaccine-response/run_all.sbatch
set -euo pipefail
python3 analysis/vaccine-response/scripts/01_select_samples.py
python3 analysis/vaccine-response/scripts/02_paired_test.py
Rscript analysis/vaccine-response/scripts/03_summary.R
