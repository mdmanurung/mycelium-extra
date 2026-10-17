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
  py=python3
fi
exec "$py" "$@"
