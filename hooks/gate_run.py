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
EVENT = {}


def find_root(cwd):  # gate.find_root, copied so the gate need not load; a test checks they agree
    path = os.path.abspath(cwd or ".")
    while True:
        if os.path.isfile(os.path.join(path, STATE_DIR, "gate.json")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def identity(event, host=None):
    """Who and which call an error belongs to, as far as the event can be decoded; None for what it cannot."""
    event = event if isinstance(event, dict) else {}
    found = {"host": host or event.get("host"), "session_id": event.get("session_id") or event.get("thread_id"),
             "call_id": event.get("tool_use_id") or event.get("tool_call_id") or event.get("call_id")}
    return dict((key, value if isinstance(value, (str, int)) and not isinstance(value, bool) else None)
                for key, value in found.items())


def error_output(name, error, cwd, event=None, host=None):
    """The hook's reply when the gate itself broke. It fails open unless gate.json sets
    "on_error": "deny", which blocks every tool call the gate could not check. It reads gate.json on
    its own, so it works when gate.py cannot even be imported; an unreadable file cannot opt in. The error is
    logged with the event, decision, host, session and call id when the event could be decoded."""
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
    try:  # best-effort record; a failed write never changes the decision and leaves no record at all
        line = json.dumps(dict(identity(event, host), ts=int(time.time()), event=name, error=str(error),
                               decision="deny" if policy == "deny" and name == "tool" else "allow")) + "\n"
        with open(os.path.join(root, STATE_DIR, "gate-errors.jsonl"), "a", encoding="utf-8") as log:
            log.write(line)
    except Exception:
        if root:
            note += " The error could not be recorded in gate-errors.jsonl."
    message = "mycelium-extra gate error ({}): {}; the gate did not run.".format(name, error)
    if policy == "deny" and name == "tool":
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                "permissionDecisionReason": message.replace("the gate did not run.",
                "blocked because gate.json sets on_error to deny. Do not work around this block; "
                "the user can fix the gate or set on_error to allow.") + note}}
    return {"systemMessage": message + note}


def opencode_event(event):
    """Normalize one OpenCode V2 plugin payload into the gate's hook vocabulary.

    The plugin sends OpenCode's own tool names (`shell`, `edit`, `write`, `patch`) and inputs;
    the gate handles Bash, Edit, Write and apply_patch. A failed post event becomes
    PostToolUseFailure with the error's message and metadata, so no exit status is read from a
    path it does not describe. Like the rest of this file, it stays parseable by Python 3.6.
    """
    data = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    name = event.get("tool_name", "")
    if name == "shell":
        event["tool_name"] = "Bash"
        command = data.get("command", data.get("cmd", ""))
        if isinstance(command, list):  # a list argv, quoted like the Codex path
            import shlex
            command = " ".join(shlex.quote(word) for word in command)
        event["tool_input"] = dict(data, command=command)
        if data.get("background") is True:
            event["tool_input"]["run_in_background"] = True
    elif name in ("edit", "write"):
        event["tool_name"] = "Write" if name == "write" else "Edit"
        event["tool_input"] = dict(data, file_path=data.get("path", data.get("file_path", "")))
    elif name == "patch":
        event["tool_name"] = "apply_patch"
        event["tool_input"] = dict(data, command=data.get("patchText", data.get("patch", "")))
    if event.get("hook_event_name") == "PostToolUse" and event.get("status") == "error":
        event["hook_event_name"] = "PostToolUseFailure"
        error = event.get("error")
        if isinstance(error, dict):
            metadata = error.get("metadata")
            event["tool_response"] = metadata if isinstance(metadata, dict) else {}
            event["error"] = error.get("message") if isinstance(error.get("message"), str) else ""
        elif error is not None:
            event["error"] = str(error)
    event.pop("status", None)
    return event


def run(argv):
    host = None
    if len(argv) == 4 and argv[1] == "--host" and argv[2] in ("codex", "opencode"):
        host = EVENT["host"] = argv[2]
        argv = [argv[0], argv[3]]
    text = sys.stdin.buffer.read().decode("utf-8", "replace")  # Claude Code sends UTF-8, whatever the locale
    EVENT["text"] = text
    try:
        event = json.loads(text)
        if host:
            event["host"] = host
            text = json.dumps(event)
    except Exception:
        pass  # an unreadable event: gate.py fails open and says so
    # Everything up to here stays parseable by Python 3.6, so an old interpreter is reported, not a SyntaxError.
    if sys.version_info < (3, 9):
        try:
            cwd = json.loads(text).get("cwd")
        except Exception:
            cwd = None
        if find_root(cwd or os.getcwd()) is None:
            return 0
        raise RuntimeError("mycelium-extra needs Python 3.9 or later, but the hook ran {} {}; install python3.9 "
                           "or later, or set MYCELIUM_EXTRA_PYTHON".format(sys.executable, sys.version.split()[0]))
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    # Host payload decoding belongs at the launcher boundary.
    try:
        decoded = json.loads(text)
        if isinstance(decoded, dict):
            if host == "codex":
                decoded.setdefault("session_id", decoded.get("thread_id"))
                import re
                tool_name = re.split(r"__|[./]", decoded.get("tool_name", ""))[-1]
                if tool_name:
                    decoded["tool_name"] = tool_name
                if tool_name in ("exec_command", "shell_command", "shell"):
                    data = decoded.get("tool_input") or {}
                    command = data.get("cmd", data.get("command", ""))
                    if isinstance(command, list):
                        import shlex
                        command = " ".join(shlex.quote(word) for word in command)
                    decoded["tool_name"] = "Bash"
                    decoded["tool_input"] = dict(data, command=command)
            if host == "opencode":
                decoded = opencode_event(decoded)
            text = json.dumps(decoded)
    except (ValueError, TypeError, AttributeError):
        pass
    # Capacity is independent of plan approval; closeout must run before gate hints.
    import capacity
    try:
        event = json.loads(text)
        event.setdefault("hook_event_name", {"prompt": "UserPromptSubmit", "tool": "PreToolUse",
                         "post": "PostToolUse", "stop": "Stop"}.get(argv[-1], argv[-1]))
        handled, notice = capacity.handle(event)
        if handled:
            if notice:
                print(json.dumps(notice))
            return 0
    except Exception as error:
        # Capacity opted in: unreadable state never turns a missing quota into permission.
        decoded = locals().get("event")
        decoded = decoded if isinstance(decoded, dict) else {}
        root = capacity.project(decoded.get("cwd") or os.getcwd())
        config = capacity.read(os.path.join(root, STATE_DIR, "capacity.json")) if root else None
        if root and not (isinstance(config, dict) and config.get("enabled") is False):
            name = decoded.get("hook_event_name", argv[-1])
            reason = "Capacity unavailable: {}; save notes and stop.".format(error)
            try:
                capacity.write(os.path.join(root, STATE_DIR, "capacity-errors", "{}-{}.json".format(int(time.time() * 1000000), os.getpid())),
                               {"event": name, "gap": reason})
            except Exception:
                pass
            if name == "SessionStart":
                return 0  # Startup is silent; the next tool still fails closed.
            notice = (capacity.deny(reason) if name == "PreToolUse" else
                      {"continue": False, "stopReason": reason, "systemMessage": reason})
            print(json.dumps(notice))
            return 0
        notice = None
    try:
        if len(argv) == 2 and find_root(event.get("cwd") or os.getcwd()) is None:
            if notice:
                print(json.dumps(notice))
            return 0
    except Exception:
        pass
    if len(argv) == 2 and argv[1] not in ("prompt", "tool", "post", "stop"):
        return 0
    import gate
    if notice:
        # Wind-down context and approval denial must coexist in a single JSON response.
        import io
        saved = sys.stdout
        output = io.StringIO()
        try:
            sys.stdout = output
            result = gate.main(argv, text)
        finally:
            sys.stdout = saved
        payload = json.loads(output.getvalue()) if output.getvalue().strip() else {}
        extra = notice.get("hookSpecificOutput", {})
        specific = payload.setdefault("hookSpecificOutput", {})
        for key, value in extra.items():
            if key == "additionalContext" and specific.get(key):
                specific[key] += "\n" + value
            else:
                specific[key] = value
        print(json.dumps(payload))
        return result
    return gate.main(argv, text)


def main(argv):
    try:
        return run(argv)
    except Exception as error:  # the gate would not load: still honour on_error
        try:
            event = json.loads(EVENT.get("text", ""))
            cwd = event.get("cwd")
        except Exception:
            event, cwd = None, None
        print(json.dumps(error_output(argv[-1], error, cwd or os.getcwd(), event, EVENT.get("host"))))
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
