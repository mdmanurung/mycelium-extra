#!/bin/bash
#SBATCH --partition=short
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
#SBATCH --output=slurm-%A_%a.out
#SBATCH --error=slurm-%A_%a.err
#SBATCH --array=0-1
set -eu
printf 'array=%s task=%s\n' "$SLURM_ARRAY_JOB_ID" "$SLURM_ARRAY_TASK_ID"
