#!/usr/bin/env bash
# Reproduce trim-hto into its own run folder: outputs/run_<YYYYMMDD>_<slug>/ with a RUN.txt, steps in number order.
# Usage: bash run.sh <slug> [snakemake options]   e.g. bash run.sh baseline -n   (dry run)
#        SNAKEMAKE="conda run -n snakemake snakemake" CORES=8 bash run.sh baseline
# A run folder is never overwritten. The same slug on the same day resumes a run whose RUN.txt says
# status: running or failed; any other status is refused with a _vNN slug to use instead.
# Layout: docs/concepts/analysis-layout.md in the mycelium-extra plugin.
set -euo pipefail
cd "$(dirname "$0")"

slug="${1:?usage: bash run.sh <slug> [snakemake options]}"
shift
case "$slug" in "" | *[!A-Za-z0-9_-]*) echo "refused: slug must use only A-Z a-z 0-9 _ -" >&2; exit 1 ;; esac
run="run_$(date +%Y%m%d)_${slug}"
dir="outputs/${run}"

for arg in "$@"; do  # a dry run plans the jobs and leaves no run folder behind
  case "$arg" in -n | --dry-run | --dryrun | -np) exec ${SNAKEMAKE:-snakemake} --cores "${CORES:-4}" --config run="$run" "$@" ;; esac
done

if [ -d "$dir" ]; then
  if [ ! -f "$dir/RUN.txt" ]; then
    echo "refused: $dir has no RUN.txt; add one (run, kind, status) or pick another slug" >&2
    exit 1
  fi
  status=$(sed -n 's/^status:[[:space:]]*\([a-z]*\).*/\1/p' "$dir/RUN.txt" | head -n 1)
  case "$status" in
    running | failed) echo "resuming $dir (status: $status)" ;;
    *)
      base="${run%_v[0-9][0-9]}"
      n=2
      while [ -e "outputs/${base}_v$(printf '%02d' "$n")" ]; do n=$((n + 1)); done
      echo "refused: $dir has status '${status:-none}' and a run is never overwritten; use: bash run.sh ${base#run_*_}_v$(printf '%02d' "$n")" >&2
      exit 1
      ;;
  esac
else
  mkdir -p "$dir"
  why=$(awk '/^## Objective/ { f = 1; next } f && /^#/ { exit } f && NF && !/^<!--/ { print; exit }' plans/PLAN.md 2>/dev/null || true)
  case "$why" in "" | "["*) why="[fill in]" ;; esac
  plan=""
  approvals=$(git rev-parse --show-toplevel 2>/dev/null || pwd)/.mycelium-extra/approvals
  newest=$(ls -t "$approvals"/*.json 2>/dev/null | head -n 1 || true)
  if [ -n "$newest" ]; then
    plan=$(grep -o '"hash": *"[^"]*"' "$newest" | head -n 1 | sed 's/.*"\([^"]*\)"$/\1/' || true)
  fi
  cat > "$dir/RUN.txt" << RUNTXT
# run
run: ${run}
kind: analysis            # analysis | figures | scratch
status: running           # running | done | current | side | superseded | failed | scratch

# origin
why: ${why}
plan: ${plan}
labeled: $(date +%Y-%m-%d) by run.sh

# links
superseded_by:
notes:
RUNTXT
fi

set_status() {  # edit the status word only; keep an inline comment where it was
  pad=$(printf '%-18s' "$1")
  sed -e "s/^status:[[:space:]]*[a-z]*[[:space:]]*#/status: ${pad}#/" \
    -e "/^status:[[:space:]]*[a-z]*[[:space:]]*\$/s/^status:.*/status: $1/" "$dir/RUN.txt" > "$dir/RUN.txt.tmp" \
    && mv "$dir/RUN.txt.tmp" "$dir/RUN.txt"
}
set_status running

if ${SNAKEMAKE:-snakemake} --cores "${CORES:-4}" --config run="$run" "$@"; then
  set_status done
else
  code=$?
  set_status failed
  exit "$code"
fi
