"""Handoff-resume chain: write HANDOFF.md, arm a marker, restart, read the handoff in the new session.

Claude cannot restart its own session, so the chain is three links that hooks keep in order:
  request  the skill starts (a PostToolUse hook records the session that ran it); the Stop hook blocks the end of the turn until HANDOFF.md is fresh and armed
  arm      the skill checks HANDOFF.md and writes .mycelium-extra/resume.json
  resume   the first prompt in a DIFFERENT session adds "read HANDOFF.md" to its context, once

State is one small file; it is separate from the approval gate and works without gate.json.
Usage: resume_run.py request|arm|cancel|status    (the skill calls these)
       resume_run.py --hook stop|prompt|post          (hooks.json calls these; event JSON on stdin)
"""

import hashlib
import json
import os
import subprocess
import sys
import time

sys.dont_write_bytecode = True
STATE = os.path.join(".mycelium-extra", "resume.json")
FRESH_SECONDS = 15 * 60  # HANDOFF.md must be written this recently to arm
REQUEST_TTL = 3600  # a request never armed stops holding Stop after an hour
MAX_AGE = 48 * 3600  # an armed marker older than this is ignored
HANDOFF = "HANDOFF.md"


def project_root(cwd):
    try:
        out = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"], capture_output=True,
                             text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return os.path.abspath(cwd)


def find_marker_root(cwd):
    path = os.path.abspath(cwd or ".")
    while True:
        if os.path.isfile(os.path.join(path, STATE)):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def load(root):
    try:
        with open(os.path.join(root, STATE), encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def save(root, data):
    path = os.path.join(root, STATE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1)
    os.replace(tmp, path)


def drop(root):
    try:
        os.remove(os.path.join(root, STATE))
    except OSError:
        pass


def digest(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def handoff_problem(root, since):
    """Why HANDOFF.md cannot be armed, or None. `since` is the request time (0 when unknown)."""
    path = os.path.join(root, HANDOFF)
    if not os.path.isfile(path):
        return "HANDOFF.md does not exist at " + root
    age = time.time() - os.path.getmtime(path)
    if os.path.getmtime(path) < since or age > FRESH_SECONDS:
        return "HANDOFF.md was not written in this handoff (older than the request or 15 minutes)"
    text = open(path, encoding="utf-8", errors="replace").read()
    if "## Next action" not in text:
        return "HANDOFF.md has no '## Next action' section"
    return None


def command(argv):
    root = project_root(os.getcwd())
    mode = argv[0] if argv else "status"
    state = load(root)
    if mode == "request":
        save(root, {"state": "requested", "requested": time.time()})
        print("handoff-resume requested; write HANDOFF.md, then run: arm")
        return 0
    if mode == "arm":
        problem = handoff_problem(root, (state or {}).get("requested", 0))
        if problem:
            print("not armed: " + problem)
            return 1
        text = open(os.path.join(root, HANDOFF), encoding="utf-8", errors="replace").read()
        save(root, {"state": "armed", "armed": time.time(), "sha256": digest(os.path.join(root, HANDOFF)),
                    "owner": (state or {}).get("owner"), "pending": "## Pending plan" in text})
        print("armed. Type /clear (or open a new session in this folder), then send any message.")
        return 0
    if mode == "cancel":
        drop(root)
        print("cancelled")
        return 0
    print(json.dumps(state) if state else "no marker")
    return 0


def read_event():
    try:
        event = json.load(sys.stdin)
        return event if isinstance(event, dict) else {}
    except (OSError, ValueError):
        return {}


def post_hook(event):
    """After the skill's own `resume_run.py request`, record which session ran it: only that session is held by Stop."""
    command_text = (event.get("tool_input") or {}).get("command") or ""
    if "resume_run.py" not in command_text or " request" not in command_text or not event.get("session_id"):
        return {}
    root = find_marker_root(event.get("cwd"))
    state = load(root) if root else None
    if state and state.get("state") == "requested":
        state["owner"] = event["session_id"]
        save(root, state)
    return {}


def stop_hook(event):
    root = find_marker_root(event.get("cwd"))
    state = load(root) if root else None
    sid = event.get("session_id")
    if not state or not sid:
        return {}
    if state.get("state") == "requested":
        if state.get("owner") != sid or event.get("stop_hook_active"):  # only the requesting session; one block per turn
            return {}
        if time.time() - state.get("requested", 0) > REQUEST_TTL:
            drop(root)
            return {}
        problem = handoff_problem(root, state.get("requested", 0))
        step = "write HANDOFF.md as the handoff skill says, then run arm" if problem else "run: arm"
        return {"decision": "block", "reason": "handoff-resume is not finished: " + (problem or "HANDOFF.md is "
                "ready but not armed") + ". Next: " + step + " (resume_run.py arm), then tell the user to type /clear."}
    if state.get("state") == "armed":
        if state.get("delivered_to") == sid:  # the new session finished its first turn: the resume is done
            drop(root)
            return {}
        if state.get("owner") == sid and not state.get("told"):
            state["told"] = True
            save(root, state)
            return {"systemMessage": "handoff-resume armed. Type /clear, then send any message; the new session "
                    "will read HANDOFF.md first."}
    return {}


def prompt_hook(event):
    root = find_marker_root(event.get("cwd"))
    state = load(root) if root else None
    sid = event.get("session_id")
    if not state or state.get("state") != "armed" or not state.get("owner") or not sid:
        return {}  # no owner or no session id: do nothing rather than guess
    if sid == state["owner"] or state.get("delivered_to"):
        return {}  # the arming session, or the resume was already delivered once
    if time.time() - state.get("armed", 0) > MAX_AGE or not os.path.isfile(os.path.join(root, HANDOFF)):
        drop(root)
        return {}
    note = ""
    if digest(os.path.join(root, HANDOFF)) != state.get("sha256"):
        note = " HANDOFF.md changed after it was armed; say so in one line."
    if state.get("pending"):
        action = ("Read HANDOFF.md. It holds a pending plan: print it as its Pending plan section says, unchanged, "
                  "and wait for the user to approve the hash the gate card shows.")
    else:
        action = "Read HANDOFF.md, run its Check first, then do its Next action."
    state["delivered_to"] = sid  # the marker goes when this session ends a turn, so a blocked prompt is not lost
    save(root, state)
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext":
            "handoff-resume: this session continues the previous one. Before anything else: " + action + note
            + " If the user's message is a different explicit task, do that task and offer the handoff after."}}


def main():
    args = sys.argv[1:]
    if args and args[0] == "--hook":
        event = read_event()
        try:
            out = {"stop": stop_hook, "prompt": prompt_hook, "post": post_hook}.get(args[1] if len(args) > 1 else "", lambda e: {})(event)
        except Exception:  # a hook must never break the session
            out = {}
        if out:
            print(json.dumps(out))
        return 0
    return command(args)


if __name__ == "__main__":
    sys.exit(main())
