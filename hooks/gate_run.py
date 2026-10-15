"""Hook entry point: load the gate only in a repository that turned it on.

Most repositories never run init, yet every prompt, tool call, and turn end runs this hook,
and loading gate.py is most of its cost. This reads the event, looks for
.mycelium-extra/gate.json the way gate.find_root does, and imports the gate only when the
file is there, or when the event cannot be read, so gate.py reports it as it always has.
"""

import json
import os
import sys
import time

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


def error_output(name, error, cwd):
    """The hook's reply when the gate itself broke. It fails open unless gate.json sets
    "on_error": "deny", which blocks every tool call the gate could not check. It reads gate.json on
    its own, so it works when gate.py cannot even be imported; an unreadable file cannot opt in."""
    note, policy = "", "allow"
    root = None
    try:
        root = find_root(cwd)
        with open(os.path.join(root, STATE_DIR, "gate.json"), encoding="utf-8") as config:
            value = json.load(config).get("on_error", "allow")
        if value in ("allow", "deny"):
            policy = value
        else:
            note = ' "on_error" in gate.json must be "allow" or "deny"; allowing.'
    except Exception:
        note = " gate.json is unreadable, so it cannot say what to do on an error; allowing." if root else ""
    try:  # best-effort record; a failed write never changes the decision
        with open(os.path.join(root, STATE_DIR, "gate-errors.jsonl"), "a", encoding="utf-8") as log:
            log.write(json.dumps({"ts": int(time.time()), "event": name, "error": str(error),
                                  "decision": "deny" if policy == "deny" and name == "tool" else "allow"}) + "\n")
    except Exception:
        pass
    message = "mycelium-extra gate error ({}): {}; the gate did not run.".format(name, error)
    if policy == "deny" and name == "tool":
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                "permissionDecisionReason": message.replace("the gate did not run.",
                "blocked because gate.json sets on_error to deny. Do not work around this block; "
                "the user can fix the gate or set on_error to allow.")}}
    return {"systemMessage": message + note}


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
    try:
        import gate
        return gate.main(argv, text)
    except Exception as error:  # the gate would not load: still honour on_error
        try:
            cwd = json.loads(text).get("cwd")
        except Exception:
            cwd = None
        print(json.dumps(error_output(argv[-1], error, cwd or os.getcwd())))
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
