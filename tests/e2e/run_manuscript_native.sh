#!/bin/sh
# Native Claude Code run of one manuscript-audit verify scenario (S1, S2 or S3), on YOUR machine.
# docs/design/2026-10-26-manuscript-native-verify.md is the protocol; its Expected column was
# committed before any native run.
#
#   sh tests/e2e/run_manuscript_native.sh S1 /tmp/mx-native     # then S2, S3
#
# Needs: claude (Claude Code) logged in, git, python3. Writes only under WORK/<scenario>/ and
# WORK/<scenario>.tar.gz. Synthetic data only; no credentials or host config are copied into the
# bundle. Three host turns:
#   1. the agent presents PLAN.md verbatim (no tools); the Stop hook prints the plan card;
#   2. YOU read the card and the contract, then type `approve plan <hash>` yourself;
#   3. the agent runs exactly the plan's rows (S3: row 1 only), with only those commands allowed.
# Then verify runs from the shell (read-only) and everything is packed into one tarball.
set -eu

SCENARIO=${1:?usage: run_manuscript_native.sh S1|S2|S3 WORK_DIR}
WORK=${2:?usage: run_manuscript_native.sh S1|S2|S3 WORK_DIR}
case "$SCENARIO" in S1|S2|S3) ;; *) echo "native scenarios are S1, S2, S3 (S4 and S5 are simulated only)" >&2; exit 1 ;; esac
PLUGIN=$(cd "$(dirname "$0")/../.." && pwd)
PROJ="$WORK/$SCENARIO/project"
HOST="$WORK/$SCENARIO/host"
if [ -e "$WORK/$SCENARIO" ]; then echo "refusing to reuse $WORK/$SCENARIO; pick a new WORK_DIR" >&2; exit 1; fi
mkdir -p "$HOST"

# Record the host and the plugin under test.
claude --version > "$HOST/claude_version.txt" 2>&1
git -C "$PLUGIN" rev-parse HEAD > "$HOST/plugin_commit.txt"
git -C "$PLUGIN" status --porcelain > "$HOST/plugin_status.txt"
(cd "$PLUGIN" && claude plugin validate .) > "$HOST/plugin_validate.txt" 2>&1 || echo "plugin validate exited $?" >> "$HOST/plugin_validate.txt"
python3 --version > "$HOST/python_version.txt" 2>&1
(command -v scilintr || echo "scilintr: not on PATH") > "$HOST/scilintr.txt" 2>&1

# The scratch project, gated with init's defaults.
python3 "$PLUGIN/tests/e2e/manuscript_scenario.py" --scenario "$SCENARIO" --dest "$PROJ" --init > "$HOST/generate.txt" 2>&1
cd "$PROJ"

COMMON="--plugin-dir $PLUGIN --output-format stream-json --verbose --include-hook-events"
NO_TOOLS="Bash Write Edit MultiEdit NotebookEdit"

# Turn 1: present the plan verbatim (the plan text is in the prompt, so no tool is needed).
PROMPT1="Reply with exactly the text between the BEGIN and END lines below, verbatim, as your whole reply. No tool calls, no other text.
BEGIN
$(cat PLAN.md)
END"
# shellcheck disable=SC2086
claude -p "$PROMPT1" $COMMON --disallowedTools $NO_TOOLS > "$HOST/turn1.jsonl"
SID=$(python3 -c 'import json,sys
for l in open(sys.argv[1]):
    try: e=json.loads(l)
    except ValueError: continue
    if e.get("session_id"): print(e["session_id"]); break' "$HOST/turn1.jsonl")
echo "$SID" > "$HOST/session_id.txt"

echo
echo "================ plan card (from the Stop hook) ================"
python3 -c 'import json,sys
seen=set()
for l in open(sys.argv[1]):
    try: e=json.loads(l)
    except ValueError: continue
    def walk(x):
        if isinstance(x, dict):
            for v in x.values(): walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
        elif isinstance(x, str) and "approve plan " in x and x not in seen:
            seen.add(x); print(x)
    walk(e)
if not seen: print("(no card found in turn1.jsonl; look for the Stop hook systemMessage there)")' "$HOST/turn1.jsonl"
echo "================ contract you are approving ================"
cat analysis/paper/config/manuscript_checks.json
echo "================================================================"
echo "Read the card and the contract. If you approve, type the approval line exactly"
echo "(for example: approve plan 1a2b3c4d). Anything else aborts."
printf '> '
read -r APPROVAL
case "$APPROVAL" in "approve plan "*) ;; *) echo "not approved; stopping" >&2; exit 1 ;; esac

# Turn 2: the researcher's own approval line, sent as the user prompt.
# shellcheck disable=SC2086
claude -p "$APPROVAL" --resume "$SID" $COMMON --disallowedTools $NO_TOOLS > "$HOST/turn2.jsonl"

# Turn 3: run exactly the plan's rows; only these commands are allowed.
PRODUCER="python3 analysis/paper/scripts/01_make_source.py"
CHECK="python3 analysis/paper/tests/manuscript_audit.py --root analysis/paper --config config/manuscript_checks.json --result-json outputs/manuscript_audit.json"
if [ "$SCENARIO" = S3 ]; then
  STEPS="1. \`$PRODUCER\`"
else
  STEPS="1. \`$PRODUCER\`
2. \`$CHECK\`"
fi
PROMPT3="Run exactly these commands from the repository root, one Bash call each, in this order, and nothing else. Do not edit, create or delete any file. Stop after the last one and report its exit code.
$STEPS"
# shellcheck disable=SC2086
claude -p "$PROMPT3" --resume "$SID" $COMMON \
  --allowedTools "Bash($PRODUCER)" "Bash(python3 analysis/paper/tests/manuscript_audit.py:*)" \
  --disallowedTools Write Edit MultiEdit NotebookEdit > "$HOST/turn3.jsonl" || echo "turn 3 exited $?" >> "$HOST/notes.txt"

# verify, from the shell (read-only), as skills/verify documents it.
HASH=$(printf '%s' "$APPROVAL" | sed 's/^approve plan //')
sh "$PLUGIN/hooks/py.sh" - --plugin-root "$PLUGIN" report "$HASH" < "$PLUGIN/skills/verify/scripts/verify.py" > "$HOST/verify_report.md" 2> "$HOST/verify_report.err" || true
sh "$PLUGIN/hooks/py.sh" - --plugin-root "$PLUGIN" report "$HASH" --json < "$PLUGIN/skills/verify/scripts/verify.py" > "$HOST/verify_report.json" 2> "$HOST/verify_report_json.err" || true

# One bundle: the project (without .git) and the host records.
cd "$WORK"
tar --exclude="$SCENARIO/project/.git" -czf "$SCENARIO.tar.gz" "$SCENARIO"
echo
echo "bundle: $WORK/$SCENARIO.tar.gz"
tail -1 "$HOST/verify_report.md" || true
