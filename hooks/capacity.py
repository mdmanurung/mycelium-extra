"""Opt-in account allowance guard and durable recovery records. Python 3.6+."""

import argparse
import contextlib
import datetime
import glob
import hashlib
import json
import math
import os
import re
import select
import shlex
import subprocess
import sys
import tempfile
import time

STATE = ".mycelium-extra"
SCRIPT = os.path.realpath(__file__)
MAX_AGE = 300
FIELDS = ("assignment", "ownership", "completed", "tests", "decisions", "blockers",
          "running", "next_action", "pending_plan")


def read(path, default=None):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("a native session/agent ID is required")
    return value


def atomic(path, text):
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    if os.path.realpath(parent) != os.path.abspath(parent) or os.path.islink(path):
        raise ValueError("refusing a symlinked state target")
    fd, tmp = tempfile.mkstemp(prefix=".capacity-", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write(path, value):
    atomic(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


@contextlib.contextmanager
def locked(path):
    import fcntl
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.realpath(path) != os.path.abspath(path):
        raise ValueError("refusing a symlinked lock")
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        deadline = time.monotonic() + 2
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ValueError("checkpoint lock busy; retry")
                time.sleep(0.02)
        yield
    finally:
        os.close(fd)


def command(cwd, argv):
    try:
        p = subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=2, encoding="utf-8", errors="replace")
        return p.stdout.strip() if p.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def project(cwd):
    path = os.path.abspath(cwd)
    while True:
        if os.path.isfile(os.path.join(path, STATE, "capacity.json")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    common = command(cwd, ["git", "rev-parse", "--git-common-dir"])
    if common:
        root = os.path.dirname(os.path.abspath(os.path.join(cwd, common)))
        if os.path.isfile(os.path.join(root, STATE, "capacity.json")):
            return root
    return None


def session_dir(root, host, sid):
    if host not in ("claude", "codex"):
        raise ValueError("unknown host")
    return os.path.join(root, STATE, "handoffs", host, safe_id(sid))


def timestamp(value):
    # Native rollouts use UTC ISO timestamps; never use file mtime as quota time.
    return datetime.datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=datetime.timezone.utc).timestamp()


def normalize(raw, host, observed, source):
    keys = (("five_hour", "seven_day", "used_percentage", "resets_at") if host == "claude"
            else ("primary", "secondary", "used_percent", "resets_at"))
    windows = {}
    for name in keys[:2]:
        item = raw.get(name)
        if not isinstance(item, dict):
            windows[name] = None
            continue
        windows[name] = {"used": item.get(keys[2]), "reset": item.get(keys[3])}
    return {"observed": observed, "source": source, "windows": windows}


def assess(usage, now=None):
    now = time.time() if now is None else now
    valid, complete = [], True
    if not isinstance(usage, dict):
        return "unavailable", "no native allowance reading"
    observed = usage.get("observed")
    if (isinstance(observed, bool) or not isinstance(observed, (int, float))
            or not math.isfinite(observed) or not 0 <= now - observed <= MAX_AGE):
        return "unavailable", "allowance reading is stale or malformed"
    windows = usage.get("windows")
    if not isinstance(windows, dict) or len(windows) != 2:
        return "unavailable", "both allowance windows are required"
    for item in windows.values():
        if not isinstance(item, dict):
            complete = False
            continue
        used, reset = item.get("used"), item.get("reset")
        if (isinstance(used, bool) or not isinstance(used, (int, float))
                or not math.isfinite(used) or not 0 <= used <= 100
                or isinstance(reset, bool) or not isinstance(reset, (int, float))
                or not math.isfinite(reset) or reset <= now):
            complete = False
        else:
            valid.append(used)
    peak = max(valid) if valid else None
    if peak is not None and peak >= 90:
        return "closeout", "allowance usage reached {}%".format(peak)
    if not complete:
        return "unavailable", "an allowance window is missing, malformed, or reset"
    return ("wind_down" if peak >= 80 else "normal"), "allowance usage {}%".format(peak)


def codex_rollout(sid, path=None):
    if not path:
        home = os.environ.get("CODEX_HOME", os.path.expanduser("~/.codex"))
        matches = glob.glob(os.path.join(home, "sessions", "*", "*", "*", "rollout-*" + safe_id(sid) + ".jsonl"))
        if len(matches) != 1:
            return None
        path = matches[0]
    latest, identity = None, None
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            try:
                event = json.loads(line)
            except ValueError:
                # A partially written last line is not a new reading.
                continue
            payload = event.get("payload", {})
            if event.get("type") == "session_meta":
                identity = payload.get("id")
            if event.get("type") == "event_msg" and payload.get("type") == "token_count":
                raw = payload.get("rate_limits")
                if raw is not None:
                    latest = normalize(raw, "codex", timestamp(event["timestamp"]), path)
    return latest if identity == sid else None


def codex_refresh():
    """Only connect to an existing server. Never start a daemon or model request."""
    p = subprocess.Popen(["codex", "app-server", "proxy"], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        def send(value):
            p.stdin.write((json.dumps(value) + "\n").encode("utf-8"))
            p.stdin.flush()
        send({"id": 1, "method": "initialize", "params": {
            "clientInfo": {"name": "mycelium-capacity", "version": "0.1"}}})
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if not select.select([p.stdout], [], [], max(0, deadline - time.monotonic()))[0]:
                break
            line = p.stdout.readline()
            if not line:
                break
            value = json.loads(line.decode("utf-8"))
            if value.get("id") == 1 and "result" in value:
                send({"method": "initialized"})
                send({"id": 2, "method": "account/rateLimits/read"})
            if value.get("id") == 2:
                raw = value.get("result", {}).get("rateLimits")
                if not isinstance(raw, dict):
                    return None
                snake = {}
                for name in ("primary", "secondary"):
                    item = raw.get(name)
                    snake[name] = ({"used_percent": item.get("usedPercent"),
                                    "resets_at": item.get("resetsAt")} if isinstance(item, dict) else None)
                return normalize(snake, "codex", time.time(), "account/rateLimits/read")
    finally:
        p.terminate()
        try:
            p.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            p.kill()
            p.communicate()
    return None


def usage(root, host, sid, transcript=None, refresh=False):
    directory = session_dir(root, host, sid)
    path = os.path.join(directory, "usage.json")
    result = read(path)
    if host == "codex":
        try:
            native = codex_rollout(sid, transcript)
            if native is not None:
                result = native
        except (OSError, ValueError, TypeError, AttributeError, KeyError):
            result = None
        if refresh:
            try:
                result = codex_refresh() or result
            except (OSError, ValueError, BrokenPipeError):
                pass
        if result is not None:
            write(path, result)
    return result


def mode(root, host, sid, transcript=None, resume=False):
    current = usage(root, host, sid, transcript, refresh=resume)
    level, reason = assess(current)
    path = os.path.join(root, STATE, "capacity", host + ".json")
    with locked(path + ".lock"):
        state = read(path, {})
        if resume:
            if level != "normal":
                raise ValueError("resume requires both fresh allowance windows below 80%: " + reason)
            state = {"paused": False, "resumed": time.time(), "session": sid}
        elif level in ("closeout", "unavailable"):
            state.update(paused=True, reason=reason, session=sid)
        write(path, state)
    if state.get("paused"):
        return "paused", state.get("reason", reason)
    return level, reason


def checkout(cwd, ownership=()):
    files = {}
    for rel in ownership:
        path = os.path.realpath(os.path.join(cwd, rel))
        if os.path.commonpath([path, os.path.realpath(cwd)]) != os.path.realpath(cwd):
            raise ValueError("ownership paths must stay inside the checkout")
        try:
            with open(path, "rb") as handle:
                files[rel] = hashlib.sha256(handle.read()).hexdigest()
        except OSError:
            files[rel] = None
    return {"cwd": os.path.abspath(cwd), "head": command(cwd, ["git", "rev-parse", "HEAD"]),
            "branch": command(cwd, ["git", "branch", "--show-current"]),
            "status": command(cwd, ["git", "status", "--short"]), "files": files}


def checkpoint(root, host, sid, agent, cwd, record=None, final=False):
    directory = session_dir(root, host, sid)
    agent = safe_id(agent)
    path = os.path.join(directory, agent + ".json")
    with locked(path + ".lock"):
        previous = read(path, {})
        if record is not None:
            if not isinstance(record, dict) or set(record) - set(FIELDS):
                raise ValueError("checkpoint accepts only the documented record fields")
            previous.update(record)
        for key in FIELDS:
            previous.setdefault(key, [] if key in ("ownership", "running") else "unconfirmed")
        if not isinstance(previous["ownership"], list) or not all(isinstance(p, str) for p in previous["ownership"]):
            raise ValueError("ownership must be a list of relative file paths")
        if not isinstance(previous["running"], list):
            raise ValueError("running must be a list of job records")
        previous.update(host=host, session=sid, agent=agent, updated=time.time(),
                        final_status="recorded" if final else "unconfirmed",
                        checkout=checkout(cwd, previous["ownership"]))
        write(path, previous)
        text = "# {} checkpoint\n\nFinal status: {}\nCheckout: {}\n\n".format(
            agent, previous["final_status"], previous["checkout"]["cwd"])
        for key in FIELDS:
            value = previous[key]
            text += "## {}\n\n{}\n\n".format(key.replace("_", " "),
                value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))
        atomic(os.path.join(directory, agent + ".md"), text)
    return path


def records(directory):
    return [read(path) for path in sorted(glob.glob(os.path.join(directory, "*.json")))
            if os.path.basename(path) not in ("usage.json", "draft.json", "recovery.json")
            and isinstance(read(path), dict) and "agent" in read(path)]


def summary(root, host, sid):
    directory = session_dir(root, host, sid)
    text = "# Coordinator summary\n\nRecorded evidence; unconfirmed is not completed.\n\n"
    for record in records(directory):
        text += "## [{}]({}.md) — {}\n\n".format(record["agent"], record["agent"], record["final_status"])
        for key in ("completed", "tests", "blockers", "running", "next_action"):
            text += "- {}: {}\n".format(key, record[key])
        text += "\n"
    text += "[Editable AI diary draft](journal.md)\n"
    atomic(os.path.join(directory, "SUMMARY.md"), text)
    return text


def recovery(root, host, source):
    result = []
    for record in records(session_dir(root, host, source)):
        previous = record["checkout"]
        cwd = previous["cwd"]
        current = checkout(cwd, record["ownership"]) if os.path.isdir(cwd) else None
        jobs = []
        for job in record["running"]:
            state = "unresolved; do not relaunch"
            if isinstance(job, dict) and job.get("kind") == "pid" and isinstance(job.get("id"), int) and job["id"] > 0:
                try:
                    os.kill(job["id"], 0)
                    state = "process exists; identity unconfirmed; do not relaunch"
                except ProcessLookupError:
                    state = "process absent; inspect output before retry"
                except PermissionError:
                    pass
            elif isinstance(job, dict) and job.get("kind") == "slurm" and re.fullmatch(r"[0-9]+", str(job.get("id", ""))):
                status = command(cwd, ["squeue", "--noheader", "--jobs", str(job["id"]), "--format=%i %T"])
                if status is not None:
                    state = status or "not in queue; inspect accounting and outputs before retry"
            jobs.append({"job": job, "status": state})
        result.append({"agent": record["agent"], "final_status": record["final_status"],
                       "completed": record["completed"], "next_action": record["next_action"],
                       "checkout_changed": current != previous, "current_checkout": current, "jobs": jobs,
                       "handoff": os.path.join(session_dir(root, host, source), record["agent"] + ".md")})
    return result


def setup(root, host):
    config_path = os.path.join(root, STATE, "capacity.json")
    with locked(config_path + ".lock"):
        config = read(config_path, {})
        config["enabled"] = True
        if host == "claude":
            settings_path = os.path.join(root, ".claude", "settings.local.json")
            settings = read(settings_path, {})
            if not isinstance(settings, dict):
                raise ValueError("invalid Claude project settings")
            old = settings.get("statusLine")
            bridge = "python3 {} statusline --root {}".format(shlex.quote(SCRIPT), shlex.quote(root))
            if not isinstance(old, dict) or old.get("command") != bridge:
                # Preserve effective project/local/user status-line output, including its formatting.
                if old is None:
                    for path in (os.path.join(root, ".claude", "settings.json"),
                                 os.path.expanduser("~/.claude/settings.json")):
                        candidate = read(path, {})
                        if "statusLine" in candidate:
                            old = candidate["statusLine"]
                            break
                if old is not None and (not isinstance(old, dict) or old.get("type") != "command"):
                    raise ValueError("cannot bridge a non-command status line")
                config["status_line"] = old
                settings["statusLine"] = dict(old or {}, type="command", command=bridge)
                write(settings_path, settings)
        write(config_path, config)
    return "Capacity enabled; approval settings unchanged. Missing usage pauses new work."


def statusline(root, raw_text):
    config = read(os.path.join(root, STATE, "capacity.json"), {})
    try:
        event = json.loads(raw_text)
        sid = safe_id(event["session_id"])
        write(os.path.join(session_dir(root, "claude", sid), "usage.json"),
              normalize(event.get("rate_limits", {}), "claude", time.time(), "Claude status line"))
    except (ValueError, KeyError, TypeError, AttributeError, OSError):
        pass
    old = config.get("status_line") or {}
    if old.get("command"):
        # The existing status line is a user-configured shell command, not model input.
        p = subprocess.run(old["command"], shell=True, input=raw_text.encode("utf-8"), timeout=5)
        return p.returncode
    return 0


def context(event, message):
    name = event.get("hook_event_name", "UserPromptSubmit")
    return {"hookSpecificOutput": {"hookEventName": name, "additionalContext": message}}


def deny(message):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": message}}


def owned_note(root, host, sid, agent, value):
    directory = session_dir(root, host, sid)
    targets = [os.path.join(directory, agent + ".input.json")]
    if agent == "coordinator":
        targets.append(os.path.join(directory, "journal.md"))
    return isinstance(value, str) and os.path.realpath(value) == os.path.abspath(value) and value in targets


def note_tool(event, root, host, sid, agent):
    name = event.get("tool_name", "").split("__")[-1]
    data = event.get("tool_input", {})
    if name in ("Read", "read_file"):
        path = data.get("file_path", data.get("path", ""))
        return os.path.realpath(path).startswith(session_dir(root, host, sid) + os.sep)
    if name in ("Write", "Edit"):
        return owned_note(root, host, sid, agent, data.get("file_path"))
    if name in ("interrupt_agent", "list_agents", "wait_agent"):
        return True
    if name != "Bash":
        return False
    try:
        tokens = shlex.split(data.get("command", ""))
        # No shell syntax: even a quoted note cannot introduce execution beside this command.
        if len(tokens) < 3 or tokens[0] not in ("python3", sys.executable) or tokens[1] != SCRIPT:
            return False
        args = parser().parse_args(tokens[2:])
        if args.action not in ("status", "checkpoint", "draft"):
            return False
        if args.root != root or args.host != host or args.session != sid or args.agent != agent:
            return False
        return args.action != "checkpoint" or owned_note(root, host, sid, agent, args.record)
    except (ValueError, SystemExit):
        return False


def handle(event):
    """Return (handled, payload). Never emit allow or override approval grants."""
    root = project(event.get("cwd") or os.getcwd())
    if root is None:
        return False, None
    host = event.get("host", "claude")
    sid = safe_id(event.get("session_id"))
    agent = safe_id(event.get("agent_id") or "coordinator")
    name = event.get("hook_event_name", "")
    prompt = event.get("prompt", "").strip()
    directory = session_dir(root, host, sid)
    if name == "UserPromptSubmit" and prompt in ("capacity setup", "capacity status", "journal save"):
        if agent != "coordinator":
            raise ValueError("only the user/coordinator can issue recovery commands")
        if prompt == "capacity setup":
            message = setup(root, host)
        elif prompt == "journal save":
            import journal
            message = journal.save(root, host, sid, reviewed=True)
        else:
            message = "{}: {}".format(*mode(root, host, sid, event.get("transcript_path")))
        return True, {"decision": "block", "reason": message, "systemMessage": message}
    match = re.fullmatch(r"capacity resume(?: ([A-Za-z0-9_-]+))?", prompt)
    if name == "UserPromptSubmit" and match:
        source = match.group(1) or sid
        evidence = recovery(root, host, source)
        mode(root, host, sid, event.get("transcript_path"), resume=True)
        write(os.path.join(directory, "recovery.json"), evidence)
        return True, context(event, "Explicit resume. Read these records before work; retain completed tasks, "
            "inspect existing jobs, and recheck approval validity. No jobs were launched.\n" + json.dumps(evidence))
    level, reason = mode(root, host, sid, event.get("transcript_path"))
    message = "Capacity {}: {}. ".format(level, reason)
    if level == "wind_down":
        message += "Finish the current bounded unit, save a checkpoint, assign no new tasks or agents."
    elif level == "paused":
        message += "Only handoff, summary, diary preservation and shutdown coordination; save notes then stop. "
        message += "Resume only on an explicit user capacity resume with fresh data below 80%."
    message += " Checkpoint directory: {}. Worker {} owns only {}.input.json; "
    message = message.format(directory, agent, agent)
    message += "save completed work units through capacity.py checkpoint; preserve pending plans verbatim."
    if name in ("SubagentStart", "SessionStart"):
        checkpoint(root, host, sid, agent, event.get("cwd") or root)
        return True, context(event, message)
    if name in ("Stop", "SubagentStop", "PreCompact", "SessionEnd"):
        record = {"completed": event["last_assistant_message"]} if event.get("last_assistant_message") else None
        checkpoint(root, host, sid, agent, event.get("cwd") or root, record,
                   final=name in ("Stop", "SubagentStop"))
        summary(root, host, sid)
        if agent == "coordinator":
            import journal
            journal.draft(root, host, sid)
        if level == "paused" and name in ("Stop", "SubagentStop"):
            return True, {"continue": False, "stopReason": message, "systemMessage": message}
        if name not in ("Stop",):
            return True, context(event, message) if name == "PreCompact" else None
    if name == "PreToolUse":
        tool = event.get("tool_name", "").split("__")[-1]
        assignment = tool in ("Agent", "Task", "TaskCreate", "TaskUpdate", "SendMessage", "spawn_agent",
                              "followup_task", "send_message", "TeamCreate")
        if level != "normal" and assignment:
            return True, deny(message)
        if level == "paused" and not note_tool(event, root, host, sid, agent):
            return True, deny(message)
        if level != "normal":
            return False, context(event, message)
    if name == "UserPromptSubmit" and level == "paused":
        # Permit one closeout turn; ordinary execution remains denied by PreToolUse.
        return True, context(event, message)
    return False, context(event, message) if level == "wind_down" else None


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("setup", "status", "resume", "checkpoint", "draft", "save", "statusline"))
    p.add_argument("--root", default=os.getcwd())
    p.add_argument("--host", choices=("claude", "codex"), default="codex")
    p.add_argument("--session", default=os.environ.get("CODEX_THREAD_ID"))
    p.add_argument("--agent", default="coordinator")
    p.add_argument("--source-session")
    p.add_argument("--record")
    p.add_argument("--reviewed", action="store_true")
    return p


def main():
    args = parser().parse_args()
    root = project(args.root) or command(args.root, ["git", "rev-parse", "--show-toplevel"]) or os.path.abspath(args.root)
    try:
        if args.action == "statusline":
            return statusline(root, sys.stdin.buffer.read().decode("utf-8", "replace"))
        if args.action == "setup":
            print(setup(root, args.host))
            return 0
        sid = safe_id(args.session)
        if args.action == "status":
            print("{}: {}".format(*mode(root, args.host, sid)))
        elif args.action == "resume":
            evidence = recovery(root, args.host, args.source_session or sid)
            mode(root, args.host, sid, resume=True)
            write(os.path.join(session_dir(root, args.host, sid), "recovery.json"), evidence)
            print(json.dumps(evidence, indent=2))
        elif args.action == "checkpoint":
            if not args.record:
                raise ValueError("checkpoint requires --record with an owned JSON record")
            print(checkpoint(root, args.host, sid, args.agent, args.root, read(args.record)))
            summary(root, args.host, sid)
        else:
            import journal
            print(journal.draft(root, args.host, sid) if args.action == "draft" else
                  journal.save(root, args.host, sid, args.reviewed))
        return 0
    except (ValueError, OSError) as error:
        print("capacity: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
