#!/usr/bin/env bash
#SBATCH --job-name=trim-hto
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=logs/slurm-%x-%j.out
# Submit from this folder: sbatch run.sbatch <slug>   (runs the Snakefile through run.sh; the slug names the run, extra args go to snakemake)
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?submit with sbatch from the analysis folder}"
CORES="${SLURM_CPUS_PER_TASK:-4}" bash run.sh "$@"
