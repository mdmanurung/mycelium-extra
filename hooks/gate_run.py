"""Hook entry point: load the gate only in a repository that turned it on.

Most repositories never run init, yet every prompt, tool call, and turn end runs this hook,
and loading gate.py is most of its cost. This reads the event, looks for
.mycelium-extra/gate.json the way gate.find_root does, and imports the gate only when the
file is there, or when the event cannot be read, so gate.py reports it as it always has.
"""

import json
import os
import sys

sys.dont_write_bytecode = True  # leave no __pycache__ in the plugin folder
STATE_DIR = ".mycelium-extra"


def find_root(cwd):  # gate.find_root, copied so the gate need not load; a test checks they agree
    path = os.path.abspath(cwd or ".")
    while True:
        if os.path.isfile(os.path.join(path, STATE_DIR, "gate.json")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def main(argv):
    host = None
    if len(argv) == 4 and argv[1:3] == ["--host", "codex"]:
        host = "codex"
        argv = [argv[0], argv[3]]
    text = sys.stdin.buffer.read().decode("utf-8", "replace")  # Claude Code sends UTF-8, whatever the locale
    try:
        event = json.loads(text)
        if len(argv) == 2 and find_root(event.get("cwd") or os.getcwd()) is None:
            return 0
        if host:
            event["host"] = host
            text = json.dumps(event)
    except Exception:
        pass  # an unreadable event: gate.py fails open and says so
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import gate
    return gate.main(argv, text)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
