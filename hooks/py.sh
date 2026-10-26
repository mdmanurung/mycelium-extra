#!/bin/sh
# Run mycelium-extra's Python, which needs 3.9 or later: $MYCELIUM_EXTRA_PYTHON if set (used as is), else
# python3 when it is new enough (an activated env keeps its packages), else the newest python3.N on PATH.
# --hook skips the python3 probe (a versioned name implies its version) and falls back to python3 whatever
# it is: gate_run.py then reports an old one through gate.json's on_error.
hook=
if [ "${1:-}" = --hook ]; then hook=1; shift; fi
py=${MYCELIUM_EXTRA_PYTHON:-}
if [ -z "$py" ] && [ -z "$hook" ] &&
   python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' </dev/null >/dev/null 2>&1; then
  py=python3
fi
if [ -z "$py" ]; then
  for name in python3.14 python3.13 python3.12 python3.11 python3.10 python3.9; do
    if command -v "$name" >/dev/null 2>&1; then py=$name; break; fi
  done
fi
if [ -z "$py" ]; then
  if [ -z "$hook" ]; then
    echo "mycelium-extra needs Python 3.9 or later, found $(python3 -V 2>&1 </dev/null); set MYCELIUM_EXTRA_PYTHON to one" >&2
    exit 1
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    # No interpreter at all. A bare exec would exit 127 with no JSON, which every host reads as "no
    # decision" and allows; say it in the hook's own protocol, and deny a tool call when gate.json
    # asks for on_error: deny (an unreadable gate.json cannot opt in, as in gate_run.py).
    note="mycelium-extra: no Python interpreter was found (set MYCELIUM_EXTRA_PYTHON), so this call was not checked by the gate."
    cfg=${CLAUDE_PROJECT_DIR:-.}/.mycelium-extra/gate.json
    for last; do :; done  # the hook's event is its last argument (`... gate_run.py [--host H] tool`)
    if [ "${last:-}" = tool ] && [ -f "$cfg" ] &&
       grep -Eq '"on_error"[[:space:]]*:[[:space:]]*"deny"' "$cfg" 2>/dev/null; then
      printf '{"systemMessage":"%s","hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s Do not work around this block; the user can fix the gate or set on_error to allow."}}\n' "$note" "$note"
    else
      printf '{"systemMessage":"%s"}\n' "$note"
    fi
    exit 0
  fi
  py=python3
fi
exec "$py" "$@"
