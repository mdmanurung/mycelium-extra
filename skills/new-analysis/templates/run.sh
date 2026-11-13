#!/usr/bin/env bash
# Reproduce @@NAME@@: run the Snakefile; each step writes its own folder outputs/<step>/ (a rerun overwrites it).
# Usage: bash run.sh [snakemake options]   e.g. bash run.sh -n   (dry run, logs nothing)
#        SNAKEMAKE="conda run -n snakemake snakemake" CORES=8 bash run.sh
# Each real run adds one entry to logs/CHANGES.md: which code/ files changed since the last run and
# which outputs/ step folders were rewritten. logs/.code-hashes.tsv holds the state it compares with.
# Layout: docs/concepts/analysis-layout.md in the mycelium-extra plugin.
set -euo pipefail
cd "$(dirname "$0")"

for arg in "$@"; do  # a dry run (-n, -pn, -nr) or a mode that runs nothing (--dag, --summary, --lint) logs nothing
  if [[ $arg =~ ^-[pnrkqFfTa]*n[pnrkqFfTa]*$ ]]; then exec ${SNAKEMAKE:-snakemake} --cores "${CORES:-4}" "$@"; fi
  case "$arg" in --dry-run | --dryrun | --dag | --rulegraph | --filegraph | --d3dag | --summary | --detailed-summary | --list | --list-* | --lint | --unlock | --version | -h | --help) exec ${SNAKEMAKE:-snakemake} --cores "${CORES:-4}" "$@" ;; esac
done

mkdir -p logs
stamp=$(mktemp logs/.run-stamp.XXXXXX)  # one stamp per run, so runs with disjoint targets do not share it
touch -d '1 second ago' "$stamp" 2> /dev/null || touch "$stamp"  # a little early, so a fast step still counts as newer

if command -v sha256sum > /dev/null 2>&1; then num_hasher="sha256sum"; else num_hasher="shasum -a 256"; fi
numbers_before=$($num_hasher outputs/numbers.json 2> /dev/null | cut -d ' ' -f 1 || true)  # Mycelium's register_value rewrites this one file in place

if ${SNAKEMAKE:-snakemake} --cores "${CORES:-4}" "$@"; then code=0; else code=$?; fi
set +e  # from here a logging problem must not replace Snakemake's exit status
numbers_after=$($num_hasher outputs/numbers.json 2> /dev/null | cut -d ' ' -f 1 || true)

exec 9> logs/.run.lock  # one writer at a time for the hashes and the log; held until this script exits
if command -v flock > /dev/null 2>&1; then flock -w 120 9 || true; fi
if command -v sha256sum > /dev/null 2>&1; then hasher="sha256sum"; else hasher="shasum -a 256"; fi
hashes=logs/.code-hashes.tsv
now=$(mktemp)
if [ -d code ]; then
  find code -type f ! -path '*/__pycache__/*' ! -path '*/.*' | LC_ALL=C sort | while IFS= read -r f; do
    printf '%s\t%s\n' "$($hasher "$f" | cut -d ' ' -f 1)" "$f"
  done > "$now"
fi

hash=nogit
git_ok=false
if git rev-parse --short HEAD > /dev/null 2>&1; then
  git_ok=true
  hash=$(git rev-parse --short HEAD)
  [ -z "$(git status --porcelain -uno -- . 2> /dev/null; git status --porcelain -- code 2> /dev/null)" ] || hash="$hash dirty"  # tracked edits anywhere here, or any change (untracked included) in code/
fi
[ "$code" -eq 0 ] && status=ok || status=failed

changed=""
while IFS=$'\t' read -r h f; do
  old=$(awk -F '\t' -v p="$f" '$2 == p { print $1; exit }' "$hashes" 2> /dev/null || true)
  [ "$old" = "$h" ] && continue
  if [ -n "$old" ]; then line="- $f: changed"; else line="- $f: new"; fi
  if [ -n "$old" ] && $git_ok && git ls-files --error-unmatch -- "$f" > /dev/null 2>&1; then
    stat=$(git diff --stat HEAD -- "$f" 2> /dev/null | head -n 1 || true)
    [ -z "$stat" ] || line="$line ($(echo "$stat" | sed 's/^ *//'))"
  fi
  changed="${changed}${line}"$'\n'
done < "$now"
if [ -f "$hashes" ]; then
  while IFS=$'\t' read -r h f; do
    awk -F '\t' -v p="$f" '$2 == p { found = 1 } END { exit !found }' "$now" || changed="${changed}- $f: removed"$'\n'
  done < "$hashes"
fi

rewritten=""
if [ -d outputs ]; then  # step folders (NN_name, NNx_name) and the panels folder; other folders are not steps
  rewritten=$(find outputs -mindepth 2 -type f -newer "$stamp" 2> /dev/null | cut -d / -f 2 | LC_ALL=C sort -u |
    grep -E '^([0-9]{2}[a-z]?_.+|panels)$' | sed 's|^|- outputs/|; s|$|/|' || true)
fi
[ "$numbers_before" = "$numbers_after" ] || rewritten="${rewritten:+$rewritten$'\n'}- outputs/numbers.json: numbers.json changed"  # it sits in outputs/, not in a step folder

log=logs/CHANGES.md
[ -f "$log" ] || printf '# Change log\n\nOne entry per run.sh run: code files changed since the previous run, and output folders rewritten. Runs that overlap in time may list the same folders.\n' > "$log"
{
  printf '\n## %s %s %s\n' "$(date '+%Y-%m-%d %H:%M')" "$hash" "$status"
  if [ -n "$changed" ]; then printf 'code changed:\n%s' "$changed"; else printf 'code changed: none\n'; fi
  if [ -n "$rewritten" ]; then printf 'outputs rewritten:\n%s\n' "$rewritten"; else printf 'outputs rewritten: none\n'; fi
} >> "$log"

if [ "$code" -eq 0 ]; then mv "$now" "$hashes"; else rm -f "$now"; fi  # a failed run keeps the old hashes, so the next run still lists these edits
rm -f "$stamp"
exit "$code"
