#!/bin/bash
#SBATCH --account=pawsey0115
#SBATCH --partition=copy
#SBATCH --time=24:00:00
#SBATCH --job-name=truth-2024
#SBATCH --output=/scratch/pawsey0115/hwang4/work_projects/weather-benchmark/data/logs/truth-%j.out
#SBATCH --error=/scratch/pawsey0115/hwang4/work_projects/weather-benchmark/data/logs/truth-%j.err

set -euo pipefail
umask 027

# The `copy` partition has internet egress, which the CDS API needs.
# Submit a 1-month pilot first, then the full year:
#   sbatch scripts/download_truth.sbatch                              # full year, all datasets
#   sbatch --export=ARGS="--months 01" scripts/download_truth.sbatch  # 1-month pilot

ROOT=/scratch/pawsey0115/hwang4/work_projects/weather-benchmark

source /software/projects/pawsey0115/hwang4/miniforge3/bin/activate /software/projects/pawsey0115/hwang4/conda_envs/aurora

python "$ROOT/scripts/download_truth.py" --year 2024 --outdir "$ROOT/data/truth" ${ARGS:-}
