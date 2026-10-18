"""Focus: which analysis one host session says it is working on. Advisory state only: it grants no run,
extends no approval and pins nothing. One small file per host session, written only by the user's typed
`focus` command (gate.py on_prompt), never by a CLI the agent could call.

    focus analysis/X [plan <hash>]   focus switch analysis/X [plan <hash>]   focus status   focus end

`python3 hooks/focus.py list [--repo DIR]` lists the analyses a focus can name (read-only).
"""

import os
import re
import sys
import time
import uuid

SCHEMA = "mycelium-extra.focus.v1"
VERB = re.compile(r"^\s*focus\s+(status|end|(?:(switch)\s+)?(analysis/\S+)(?:\s+plan\s+([0-9a-f]{8}))?)\s*[.!]?\s*$",
                  re.IGNORECASE)
PATH_OK = re.compile(r"analysis(?:/[A-Za-z0-9][A-Za-z0-9._-]*)+")
OBJECTIVE = re.compile(r"^[\s>*_`-]*objective[\s*_`]*[.:]\s*(\S.*)$", re.IGNORECASE)
OBJECTIVE_HEADING = re.compile(r"^#+\s*objective\b", re.IGNORECASE)


class FocusError(Exception):
    """A focus command that was refused; the message says why and what to type instead."""


def _state_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)


def session_name(session_id):
    """The state file's name for a host session; a missing or placeholder id is refused, never shared."""
    if not isinstance(session_id, str) or not session_id.strip() or session_id.strip() == "unknown":
        raise FocusError("mycelium-extra: no focus change: this host sent no session id, and a focus belongs to "
                         "one session.")
    return re.sub(r"[^A-Za-z0-9_-]", "_", session_id)


def record_path(root, session_id):
    return os.path.join(root, ".mycelium-extra", "focus", session_name(session_id) + ".json")


def read(root, session_id):
    """The session's record, or None when it has none. A record that is malformed, belongs to another session
    id, or has two open episodes is an error: nothing repairs it silently."""
    import json
    path = record_path(root, session_id)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError):
        record = None
    episodes = record.get("episodes") if isinstance(record, dict) else None
    ok = (isinstance(record, dict) and record.get("schema") == SCHEMA and record.get("session_id") == session_id
          and isinstance(episodes, list)
          and all(isinstance(e, dict) and isinstance(e.get("analysis_path"), str)
                  and isinstance(e.get("focus_id"), str) and isinstance(e.get("started_at"), (int, float))
                  for e in episodes))
    if not ok:
        raise FocusError("mycelium-extra: the focus record {} is malformed or belongs to another session. Move it "
                         "aside; nothing was changed.".format(os.path.relpath(path, root)))
    if sum(1 for e in episodes if e.get("ended_at") is None) > 1:
        raise FocusError("mycelium-extra: the focus record {} has more than one open episode. Move it aside; "
                         "nothing was changed.".format(os.path.relpath(path, root)))
    return record


def open_episode(record):
    return next((e for e in (record or {}).get("episodes", []) if e.get("ended_at") is None), None)


def resolve_target(root, name):
    """The repository-relative path of an existing analysis folder, or FocusError: no `..`, no escape by a
    symlink, nothing in the state folder, and the exact folder rather than a guess."""
    rel = name.strip().rstrip("/")
    if not PATH_OK.fullmatch(rel) or ".." in rel.split("/"):
        raise FocusError("mycelium-extra: no focus: `{}` is not an analysis path. Type `focus analysis/<folder>` "
                         "with a folder that exists (letters, digits, . _ -).".format(name[:80]))
    real_root = os.path.realpath(root)
    real = os.path.realpath(os.path.join(root, rel))
    if not (real == real_root or real.startswith(real_root + os.sep)) or real.startswith(
            os.path.join(real_root, ".mycelium-extra") + os.sep):
        raise FocusError("mycelium-extra: no focus: `{}` resolves outside the project.".format(rel))
    if not os.path.isdir(real):
        found = analyses(root)
        raise FocusError("mycelium-extra: no focus: `{}` is not a folder. Type the exact path{}.".format(
            rel, "; there are: " + ", ".join(found[:8]) + (" …" if len(found) > 8 else "") if found
            else " (no folder under analysis/ yet; create one with the new-analysis skill)"))
    return rel


def analyses(root):
    """The folders directly under analysis/ (a focus can also name a nested one), sorted."""
    folder = os.path.join(root, "analysis")
    try:
        return sorted("analysis/" + n for n in os.listdir(folder)
                      if os.path.isdir(os.path.join(folder, n)) and not n.startswith("."))
    except OSError:
        return []


def objective_of(root, rel):
    """(objective line, doc path) from the analysis doc (`<NAME>.md` as new-analysis names it, else README.md),
    or (None, doc path or None) when the doc has none. The first `Objective:` line, or the line under an
    `## Objective` heading; never a guess from other prose."""
    name = os.path.basename(rel)
    for doc in (name.upper().replace("-", "_") + ".md", "README.md"):
        path = os.path.join(root, rel, doc)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                lines = [handle.readline() for _ in range(300)]
        except OSError:
            continue
        for i, line in enumerate(lines):
            found = OBJECTIVE.match(line)
            if found:
                return _one_line(found.group(1)), rel + "/" + doc
            if OBJECTIVE_HEADING.match(line):
                for later in lines[i + 1:i + 6]:
                    if later.strip() and not later.lstrip().startswith("#"):
                        return _one_line(later), rel + "/" + doc
        return None, rel + "/" + doc
    return None, None


def _one_line(text, limit=160):
    text = re.sub(r"[\x00-\x1f\x7f]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" *_`>")
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def plan_touches(gate, root, record, rel):
    """Whether an approved plan's table names a path inside `rel` (the only link this module recognises between
    a plan and an analysis folder; it never picks a plan because it is the newest)."""
    paths = gate.plan_paths_in(root, gate.plan_table(record.get("plan") or "", every_cell=True))
    return any(p == rel or p.startswith(rel + "/") for p in paths)


def _locked(root, session_id):
    _state_dir()
    import stateio
    try:
        return stateio.locked(os.path.join(root, ".mycelium-extra", "locks", "focus-" + session_name(session_id) + ".lock"))
    except (OSError, ValueError) as error:  # a focus change never goes ahead unlocked
        raise FocusError("mycelium-extra: no focus change: could not lock the focus record ({}).".format(error))


def _save(root, session_id, record):
    _state_dir()
    import json
    import stateio
    path = record_path(root, session_id)
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    try:
        stateio.atomic(path, json.dumps(record, indent=1) + "\n")
        os.chmod(path, 0o600)
    except (OSError, ValueError) as error:
        raise FocusError("mycelium-extra: no focus change: could not write the focus record ({}).".format(error))


def change(gate, root, event, command):
    """Apply one typed focus command (`start`, `switch`, `end`) for the event's session; the message to show.
    Raises FocusError with nothing changed."""
    session_id = event.get("session_id")
    session_name(session_id)  # refused before any file is touched
    kind, name, plan_hash = command
    rel = resolve_target(root, name) if name else None
    if plan_hash:
        approval = os.path.join(root, ".mycelium-extra", "approvals", plan_hash + ".json")
        record = gate.read_approval(approval) if os.path.isfile(approval) else None
        if record is None:
            raise FocusError("mycelium-extra: no focus: no approved plan {}. Leave out `plan {}`, or approve the "
                             "plan first.".format(plan_hash, plan_hash))
        if not plan_touches(gate, root, record, rel):
            raise FocusError("mycelium-extra: no focus: plan {} names no path inside {}. Nothing is guessed; "
                             "leave out `plan {}` or pick the plan that names this folder.".format(plan_hash, rel, plan_hash))
    now = time.time()
    with _locked(root, session_id):
        record = read(root, session_id) or {"schema": SCHEMA, "host": event.get("host") or "claude-code",
                                           "session_id": session_id, "episodes": []}
        current = open_episode(record)
        if kind == "end":
            if not current:
                raise FocusError("mycelium-extra: no focus is active in this session.")
            current["ended_at"] = now
            _save(root, session_id, record)
            return "mycelium-extra: focus on {} ended. The analysis is not complete or reportable; this only "\
                   "closes the focus.".format(current["analysis_path"])
        if current and kind == "start":
            raise FocusError("mycelium-extra: focus is already on {}. Type `focus switch {}` to change it, or "
                             "`focus end`.".format(current["analysis_path"], rel))
        if current:
            current["ended_at"] = now
        objective, doc = objective_of(root, rel)
        transcript = event.get("transcript_path")
        record["episodes"].append({
            "focus_id": uuid.uuid4().hex[:12], "analysis_path": rel, "started_at": now, "ended_at": None,
            "original_plan_hash": plan_hash, "plan_selection": "explicit" if plan_hash else None,
            "objective_source": doc, "transcript_path": transcript if isinstance(transcript, str) else None})
        _save(root, session_id, record)
    return "mycelium-extra: focus {} on {}{}. This is advisory: it grants no run and changes no approval. " \
           "`focus status` shows it.".format("switched" if current else "started", rel,
                                            " (was {})".format(current["analysis_path"]) if current else "")


def context_line(root, session_id):
    """The one advisory line for the agent while a focus is open, else None. Never raises: a prompt is not
    blocked by a bad record (`focus status` reports it)."""
    try:
        episode = open_episode(read(root, session_id))
    except (FocusError, OSError):
        return None
    if not episode:
        return None
    return ("mycelium-extra focus: {}{}. Stay on this analysis unless the user directs otherwise; before a "
            "consequential scope expansion or a new analysis, say why and propose `focus switch`. Advisory only: "
            "this grants no permission and never overrides the user's message.".format(
                episode["analysis_path"], " (goal source: {})".format(episode["objective_source"])
                if episode.get("objective_source") else ""))


def status(gate, root, config, event):
    """The `focus status` card (rows aligned like the freeze card), for the user."""
    session_id = event.get("session_id")
    try:
        record = read(root, session_id)
    except FocusError as error:
        return str(error)
    current = open_episode(record)
    if not current:
        past = (record or {}).get("episodes") or []
        return ("mycelium-extra · focus none{}\nNext       focus analysis/<folder>{}".format(
            " (last: {})".format(past[-1]["analysis_path"]) if past else "",
            "   (folders: {})".format(", ".join(analyses(root)[:6])) if analyses(root) else ""))
    rel = current["analysis_path"]
    lines = ["mycelium-extra · focus {} · since {}".format(
        rel, time.strftime("%m-%d %H:%M", time.localtime(current["started_at"])))]
    objective, doc = objective_of(root, rel)
    lines.append("Objective  {}".format("{} ({})".format(objective, doc) if objective else
                                        "not stated in {}".format(doc) if doc else "no analysis doc found"))
    original = current.get("original_plan_hash")
    approvals = gate.all_approvals(root)
    touching = [r for r in approvals or [] if plan_touches(gate, root, r, rel)]
    lines.append("Plan       original {}  ·  newest approved naming this folder: {}".format(
        original + " (selected)" if original else "not selected",
        touching[0]["hash"] if touching else ("none" if approvals is not None else "not checked (scan timed out)")))
    active = gate.active_approvals(root, config, session_id)
    elsewhere = gate.active_approvals(root, config)
    if active is None or elsewhere is None:
        runs = "not checked (scan timed out)"
    elif any(plan_touches(gate, root, r, rel) for r in active):
        runs = "an approval naming this folder is active in this session (focus did not grant it)"
    elif any(plan_touches(gate, root, r, rel) for r in elsewhere):
        runs = "not authorized in this session (an active approval belongs to another session)"
    elif touching:
        runs = "not authorized: the approval naming this folder has expired"
    else:
        runs = "not authorized: no approved plan names this folder"
    lines.append("Runs       " + runs)
    lines.append("Next       /mycelium-extra:track-changes {}   ·   focus switch|end".format(rel))
    return "\n".join(lines)


def main(argv):
    if len(argv) >= 2 and argv[1] == "list":
        root = os.getcwd()
        if "--repo" in argv:
            root = argv[argv.index("--repo") + 1]
        found = analyses(root)
        print("\n".join(found) if found else "no folders under analysis/")
        return 0
    print("usage: focus.py list [--repo DIR]   (focus itself is changed only by typing `focus ...`)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
