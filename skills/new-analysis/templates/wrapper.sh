#!/usr/bin/env bash
# @@FILE@@: step @@NUM@@ of @@NAME@@, a wrapper around the @@SKILL@@ skill.
# Purpose: [One sentence: what the skill script computes in this analysis.]
# Run:     bash @@PATH@@   (from the analysis folder; add a Snakefile rule that calls it to run it with the steps)
# Inputs:  [each file the skill script reads, with the script that produced it, or [gap]]
# Outputs: @@DIR@@/ [each file the skill script writes; nothing outside this folder]
# Why:     the approval gate ignores a script that lives outside the repository (mycelium-extra#5),
#          so the plan's Step column names this file and the skill script runs from inside it.
set -euo pipefail
cd "$(dirname "$0")/.."

# Parameters -------------------------------------------------------------------
# CLAUDE_PLUGIN_ROOT is the folder of the plugin that ships the skill.
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:?set CLAUDE_PLUGIN_ROOT to the plugin folder that holds skills/@@SKILL@@}"
SKILL_DIR="$PLUGIN_ROOT/skills/@@SKILL@@"
OUT=@@DIR@@ # this step's folder; a rerun overwrites it

# Run the skill script ---------------------------------------------------------
@@SCRIPT_HINT@@
mkdir -p "$OUT/logs"
echo "@@FILE@@ is not written yet: call a script under $SKILL_DIR/scripts/ with its arguments," >&2
echo "writing only into $OUT/" >&2
exit 1
