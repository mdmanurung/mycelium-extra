"""Experiment tree for the iterate skill: an append-only event log and the questions it answers.

Run: <skill-dir>/../../hooks/mxpy - [--analysis DIR] <command> [options] < <skill-dir>/scripts/tree.py
The log is <analysis>/plans/tree.jsonl, one JSON event per line: add, plan, run, answer, repair, stop,
evaluator, arena.
Nothing edits or deletes a line; every view is a replay. A node added after a stop ends the stop. Stdlib only, Python 3.9+.

Commands
  plan [--run-cmd C] [--readout R] [--repair-cap N] [--stop-after N] [--stop-rule TEXT]
        sets or changes plan rows on the root, after the user confirms them (each change is a logged event)
  add SLUG [--parent P] [--question T] [--kind candidate|baseline|sanity]   a node, branch exp/SLUG.
        The root also takes the plan rows:
        [--run-cmd C] [--readout R] [--repair-cap N] [--stop-after N] [--stop-rule TEXT]
        and, for method mode: [--mode method] [--floor N] [--card PATH] [--rubric TEXT]
  run SLUG (--receipt N | --exit CODE) [--commit SHA] [--run-id ID] [--readout-value V] [--log PATH]
  answer SLUG --outcome better|same|worse --summary T [--figure PATH ...]   freezes the node
  repair SLUG [--note T]                 a failed run is repaired in place, up to the cap
  stop --reason user|blocker|rule [--note T]
  status [--json]   summary   frozen   stop-check
Method mode (root added with --mode method)
  freeze-evaluator [--file PATH ...] [--refreeze --note T]   SHA-256 of the benchmark card and each file
  check-evaluator                        exit 0 every hashed file matches, 3 one changed or is gone, 2 no tree
  arena SLUG SLUG ... --winner SLUG [--note T]   sibling candidates judged on the rubric fixed before their runs
A method tree stops at the iteration floor, counted in answered candidates; a baseline and a sanity node
(add --kind) must have run first, and the evaluator must be frozen before any run.

Exit codes. stop-check: 0 stop rule met or a stop recorded, 3 not yet, 2 no tree or an unreadable one.
Other commands: 0 done, 1 usage or bad input, 3 refused (a frozen node, the repair cap, a missing plan row).
The run command, repair cap and stop rule come from the user's approved plan rows. They have no
defaults here: when one is missing, the command says so and exits 3, and the agent asks the user.
"""

import argparse
import contextlib
import hashlib
import json
import os
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True
TREE = os.path.join("plans", "tree.jsonl")
RECEIPTS = os.path.join(".mycelium-extra", "receipts.jsonl")
SLUG = re.compile(r"^[a-z0-9]([a-z0-9._-]*[a-z0-9_-])?$")
EVENTS = ("add", "run", "answer", "repair", "stop", "plan", "evaluator", "arena")
PLAN_KEYS = ("run_cmd", "readout", "repair_cap", "stop_after", "stop_rule", "mode", "floor", "card", "rubric")
METHOD_KEYS = ("floor", "card", "rubric")
RESEARCH_KEYS = ("stop_after", "stop_rule")
MODES = ("research", "method")
KINDS = ("candidate", "baseline", "sanity")
STATUSES = ("ok", "failed", "unknown")
REQUIRED = {"add": ("node",), "run": ("node",), "answer": ("node", "outcome"), "repair": ("node",),
            "evaluator": ("hashes",), "arena": ("nodes", "winner")}
TEXT_KEYS = ("node", "parent", "branch", "question", "run_cmd", "readout", "stop_rule", "note", "summary", "outcome",
             "reason", "commit", "run_id", "readout_value", "log", "mode", "card", "rubric", "kind", "winner",
             "seen_status", "receipt_exit_status")
INT_KEYS = ("repair_cap", "stop_after", "receipt", "exit", "floor")
OUTCOMES = ("better", "same", "worse")
REASONS = ("user", "blocker", "rule")
NO_FIGURE = "unsupported: no inspected figure"
ASK = "Ask the user for this plan row; it is an impactful choice and has no default."


class TreeError(Exception):
    """The log cannot be read as a tree."""


def valid_slug(slug):
    """A slug that also makes a valid git branch name `exp/<slug>` (no `..`, no `.lock` ending)."""
    return bool(SLUG.match(slug)) and ".." not in slug and not slug.endswith(".lock")


def well_formed(event):
    """True when every field the replay reads is present where it is required and has the type it expects."""
    if any(event.get(key) is None for key in REQUIRED.get(event.get("ev"), ())):
        return False
    if any(event.get(key) is not None and not isinstance(event[key], str) for key in TEXT_KEYS):
        return False
    if any(event.get(key) is not None and (isinstance(event[key], bool) or not isinstance(event[key], int))
           for key in INT_KEYS):
        return False
    for key in ("figures", "nodes", "folders"):
        value = event.get(key)
        if value is not None and not (isinstance(value, list) and all(isinstance(item, str) for item in value)):
            return False
    hashes = event.get("hashes")
    return hashes is None or (isinstance(hashes, dict) and all(
        isinstance(k, str) and isinstance(v, str) for k, v in hashes.items()))


def tree_path(analysis):
    return os.path.join(analysis, TREE)


def read_events(path):
    """Events in file order. A line that is not a JSON object raises TreeError: a gap is not a pass."""
    events = []
    with open(path, encoding="utf-8") as handle:
        lines = handle.readlines()
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            event = None
        if event is None and number == len(lines) and not line.endswith("\n"):
            break  # a writer was killed mid-line: the unfinished last line is not an event yet
        if not isinstance(event, dict) or event.get("ev") not in EVENTS or not well_formed(event):
            raise TreeError("{} line {} is not a tree event".format(path, number))
        events.append(event)
    return events


def find_receipts(start):
    """The repository's receipts.jsonl: the nearest one at or above `start`, never above the repository root (the
    first folder with a `.git` or a `.mycelium-extra`), so another project's receipts are never read."""
    path = os.path.abspath(start)
    while True:
        candidate = os.path.join(path, RECEIPTS)
        if os.path.isfile(candidate):
            return candidate
        if any(os.path.exists(os.path.join(path, marker)) for marker in (".git", ".mycelium-extra")):
            return None
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def receipt_line(analysis, number):
    """The receipt record at 1-based line `number` of the repository's receipts.jsonl, or None."""
    path = find_receipts(analysis)
    if not path:
        return None
    with open(path, encoding="utf-8") as handle:
        for index, line in enumerate(handle, 1):
            if index == number:
                try:
                    record = json.loads(line)
                except ValueError:
                    return None
                return record if isinstance(record, dict) else None
    return None


def run_status(analysis, event):
    """ok, failed or unknown for one run event.

    A run recorded by this version carries the status tree.py saw when it ran (`seen_status`), so a replay on a
    clone with no receipts file gives the same answer. An older event is read from its cited receipt, else from
    its stated exit code. A receipt that is missing or has no integer exit status is unknown, not failed.
    """
    if event.get("seen_status") in STATUSES:
        return event["seen_status"]
    code = event.get("exit")
    if event.get("receipt") is not None:
        record = receipt_line(analysis, event["receipt"])
        code = record.get("exit_status") if record else None
    if isinstance(code, bool) or not isinstance(code, int):
        return "unknown"
    return "ok" if code == 0 else "failed"


def replay(events, analysis="."):
    """The tree the events describe: {"root": id|None, "plan": {...}, "nodes": {id: node}, "stops": [...], ...}.

    The log is append-only, so the replay enforces what the commands check: a second `add` of a slug, and any
    run, repair or answer on a frozen node, are ignored. A stop ends the loop until a node is added after it.
    Method mode adds the latest `evaluator` event, the `arena` events, the sequence number of the event that set
    the rubric, and, per answer, `counted`: a candidate answered after a baseline and a sanity node had run.
    """
    nodes, stops, root, plan, answers = {}, [], None, {}, []
    evaluator, arenas, rubric_seq, ready = None, [], None, {"baseline": False, "sanity": False}
    for seq, event in enumerate(events):
        kind, slug = event["ev"], event.get("node")
        if kind == "add":
            if slug in nodes:
                continue
            nodes[slug] = {"id": slug, "branch": event.get("branch") or "exp/" + slug, "parent": event.get("parent"),
                           "kind": event.get("kind") or "candidate", "question": event.get("question") or "",
                           "runs": [], "repairs": 0, "answer": None, "state": "new"}
            stops = []
            if event.get("parent") is None and root is None:
                root = slug
                plan = {key: event.get(key) for key in PLAN_KEYS}
                rubric_seq = seq if event.get("rubric") else None
        elif kind == "plan":
            if root is not None:
                plan.update({key: event[key] for key in PLAN_KEYS if event.get(key) is not None})
                if event.get("rubric") is not None:
                    rubric_seq = seq
        elif kind == "stop":
            stops.append(event)
        elif kind == "evaluator":
            evaluator = event
        elif kind == "arena":
            arenas.append(event)
        elif slug in nodes and nodes[slug]["state"] != "frozen":
            node = nodes[slug]
            if kind == "run":
                node["runs"].append(dict(event, status=run_status(analysis, event), seq=seq))
                node["state"] = {"ok": "ran", "failed": "failed"}.get(node["runs"][-1]["status"], "unknown")
                if node["state"] == "ran" and node["kind"] in ready:
                    ready[node["kind"]] = True
            elif kind == "repair":
                node["repairs"] += 1
                node["state"] = "repairing"
            elif kind == "answer":
                node["answer"] = event
                node["state"] = "frozen"
                method = plan.get("mode") == "method"
                counted = not method or (node["kind"] == "candidate" and all(ready.values()))
                answers.append(dict(event, counted=counted))
    return {"root": root, "plan": plan, "nodes": nodes, "stops": stops, "answers": answers, "evaluator": evaluator,
            "arenas": arenas, "rubric_seq": rubric_seq, "ready": ready}


def load(analysis):
    try:
        return replay(read_events(tree_path(analysis)), analysis)
    except (TypeError, KeyError, AttributeError, ValueError) as problem:
        raise TreeError("{} holds an event the replay cannot read ({})".format(tree_path(analysis), problem))


def frozen_branches(tree):
    return [node["branch"] for node in tree["nodes"].values() if node["state"] == "frozen"]


def is_method(plan):
    return plan.get("mode") == "method"


def missing_rows(plan):
    """Names of the impactful plan rows the root does not hold yet.

    Research mode needs the run command, readout, repair cap and stop rule. The rule is the user's words
    (`--stop-rule`); a count (`--stop-after`) is optional, and without one tree.py cannot judge the rule. Method mode swaps the stop rule for the iteration floor and the benchmark card.
    """
    rows = [("run command", plan.get("run_cmd")), ("readout", plan.get("readout")),
            ("repair cap", plan.get("repair_cap"))]
    if is_method(plan):
        rows += [("iteration floor", plan.get("floor")), ("benchmark card", plan.get("card"))]
    else:
        rows.append(("stop rule", plan.get("stop_rule")))
    return [name for name, value in rows if value in (None, "")]


def stop_check(tree, ignore_stops=False):
    """(code, message): 0 when a stop is recorded or the stop rule (research) or floor (method) is met, 3 otherwise.

    `ignore_stops` judges the rule or floor alone, as if no stop had been recorded.
    """
    if tree["stops"] and not ignore_stops:
        last = tree["stops"][-1]
        return 0, "stopped: reason {}{}".format(last.get("reason"), " (" + last["note"] + ")" if last.get("note") else "")
    if tree["root"] is None:
        return 3, "the tree has no root node; add one with the run command, readout, repair cap and stop rule. " + ASK
    plan = tree["plan"]
    missing = missing_rows(plan)
    if missing:
        return 3, "the root node has no {}. {}".format(", ".join(missing), ASK)
    open_nodes = [n["id"] for n in tree["nodes"].values() if n["state"] != "frozen"]
    if is_method(plan):
        return method_stop_check(tree, plan, open_nodes)
    limit = plan.get("stop_after")
    if limit is None:
        return 3, ("the stop rule is in words only ({}), so tree.py cannot judge it. Ask the user whether it is "
                   "met; run `stop --reason rule` only after the user says so. Open nodes: {}").format(
            plan["stop_rule"], ", ".join(open_nodes) or "none")
    streak = 0
    for answer in reversed(tree["answers"]):
        if answer.get("outcome") == "better":
            break
        streak += 1
    if streak >= limit:
        return 0, "stop rule met: the last {} answered nodes were not better".format(streak)
    return 3, "stop rule not met: {} of {} answered nodes in a row were not better; open nodes: {}".format(
        streak, limit, ", ".join(open_nodes) or "none")


def method_stop_check(tree, plan, open_nodes):
    """Method mode: the floor counts answered candidates that came after a frozen evaluator, a baseline and a sanity run."""
    if tree["evaluator"] is None:
        return 3, "the evaluator is not frozen. Run freeze-evaluator before any node runs."
    absent = [name for name, done in tree["ready"].items() if not done]
    if absent:
        unknown = [n["id"] for n in tree["nodes"].values() if n["state"] == "unknown" and n["kind"] in absent]
        return 3, "no {} node has run yet. Add one (add --kind ...) and run it before candidates count.{}".format(
            " or ".join(absent), " {} ran with an unknown exit status (the receipt has no integer exit status, or "
            "is not on this machine); that counts as neither ok nor failed.".format(", ".join(unknown))
            if unknown else "")
    done = sum(1 for answer in tree["answers"] if answer["counted"])
    if done >= plan["floor"]:
        return 0, "iteration floor met: {} of {} candidates answered".format(done, plan["floor"])
    return 3, "iteration floor not met: {} of {} candidates answered; open nodes: {}".format(
        done, plan["floor"], ", ".join(open_nodes) or "none")


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evaluator_files(tree, analysis):
    """{absolute path: recorded hash} for the files the latest evaluator freeze hashed."""
    event = tree.get("evaluator")
    if not event:
        return {}
    base = os.path.abspath(analysis)
    return {os.path.normpath(os.path.join(base, rel)): digest for rel, digest in (event.get("hashes") or {}).items()}


def evaluator_drift(tree, analysis, hasher=file_hash):
    """[(path, why)] for each hashed file that is changed or missing, each file added under a frozen folder, and
    the plan's benchmark card when the freeze does not cover it (the card was changed after the freeze).
    `hasher(path)` gives a file's hash; one that returns None (the loop guard, out of time or with a cached hash)
    leaves that file unchecked, so it is not listed."""
    drift = []
    known = set(evaluator_files(tree, analysis))
    base = os.path.abspath(analysis)
    for path, digest in sorted(evaluator_files(tree, analysis).items()):
        if not os.path.isfile(path):
            drift.append((path, "missing"))
        else:
            now = hasher(path)
            if now is not None and now != digest:
                drift.append((path, "changed"))
    card = (tree.get("plan") or {}).get("card")
    if card and tree.get("evaluator"):
        card_path = os.path.normpath(os.path.join(base, card))
        if not any(path == card_path or path.startswith(card_path + os.sep) for path in known):
            drift.append((card_path, "not frozen"))
    for folder in (tree.get("evaluator") or {}).get("folders") or []:
        for member in folder_members(os.path.join(base, folder)):
            if os.path.normpath(member) not in known:
                drift.append((os.path.normpath(member), "added"))
    return sorted(drift)


def find_trees(root):
    """Paths of tree.jsonl files within three levels of `root`, without walking into data or hidden folders."""
    found = []
    skip = {"data", "node_modules", "renv", "venv", "env"}
    base = os.path.abspath(root)
    for depth in range(3):
        level = [base]
        for _ in range(depth):
            level = [os.path.join(p, d) for p in level for d in _folders(p) if d not in skip]
        for folder in level:
            candidate = os.path.join(folder, TREE)
            if os.path.isfile(candidate):
                found.append(candidate)
    return found


def _folders(path):
    try:
        return sorted(name for name in os.listdir(path)
                      if not name.startswith(".") and os.path.isdir(os.path.join(path, name)))
    except OSError:
        return []


def analysis_of(tree_file):
    return os.path.dirname(os.path.dirname(tree_file))


def append(analysis, event):
    """Add one line. An unfinished last line (a writer killed mid-write) is dropped first; it was never an event."""
    path = tree_path(analysis)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    event = dict(event, ts=int(time.time()))
    line = json.dumps(event, sort_keys=True) + "\n"
    if os.path.isfile(path):
        with open(path, "rb+") as handle:
            data = handle.read()
            if data and not data.endswith(b"\n"):
                cut = data.rfind(b"\n") + 1
                try:
                    json.loads(data[cut:].decode("utf-8"))
                    handle.write(b"\n")
                except ValueError:
                    handle.truncate(cut)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line)


@contextlib.contextmanager
def locked(analysis):
    """Hold an exclusive lock on the log while a command checks the tree and appends, so two calls cannot both pass."""
    try:
        import fcntl
        handle = open(tree_path(analysis) + ".lock", "a")
    except (ImportError, OSError):
        yield
        return
    with handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def git_head(analysis):
    try:
        out = subprocess.run(["git", "-C", analysis, "rev-parse", "--short", "HEAD"], capture_output=True,
                             text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def fail(message, code=1):
    print(message)
    return code


def need_tree(args):
    if not os.path.isfile(tree_path(args.analysis)):
        return None, fail("no tree: {} does not exist. Start one with: add SLUG --run-cmd ... "
                          "(the run command, repair cap and stop rule are the user's plan rows).".format(
                              tree_path(args.analysis)), 2)
    try:
        return load(args.analysis), 0
    except (TreeError, OSError) as problem:
        return None, fail("tree unreadable: {}".format(problem), 2)


def bad_numbers(event):
    """A message when the repair cap is below 0 (0 means no repairs) or the stop-after or floor count is below 1."""
    for key, floor in (("repair_cap", 0), ("stop_after", 1), ("floor", 1)):
        if event.get(key) is not None and event[key] < floor:
            return "--{} must be {} or more".format(key.replace("_", "-"), floor)
    return ""


def wrong_mode_rows(plan, event):
    """A message when `event` sets a row the plan's mode does not use: floor, card and rubric are method rows;
    the stop count and stop rule are research rows."""
    method = is_method(plan) or event.get("mode") == "method"
    unused = RESEARCH_KEYS if method else METHOD_KEYS
    given = [key for key in unused if event.get(key) is not None]
    if not given:
        return ""
    if method:
        return "{} apply to research mode; a method tree stops at its iteration floor".format(
            ", ".join("--" + key.replace("_", "-") for key in given))
    return "{} are for method mode (root added with --mode method)".format(
        ", ".join("--" + key.replace("_", "-") for key in given))


def cmd_plan(args):
    tree, code = need_tree(args)
    if code:
        return code
    if tree["root"] is None:
        return fail("the tree has no root node yet; use add SLUG with the plan rows", 3)
    event = dict({"ev": "plan"}, **{key: getattr(args, key) for key in PLAN_KEYS if key != "mode"})
    if all(event[key] is None for key in PLAN_KEYS if key != "mode"):
        return fail("give at least one of --run-cmd --readout --repair-cap --stop-after --stop-rule "
                    "--floor --card --rubric")
    wrong = wrong_mode_rows(tree["plan"], event)
    if wrong:
        return fail(wrong)
    bad = bad_numbers(event)
    if bad:
        return fail(bad)
    append(args.analysis, event)
    missing = missing_rows(replay(read_events(tree_path(args.analysis)), args.analysis)["plan"])
    print("plan rows set on {}{}".format(tree["root"], "; still missing: " + ", ".join(missing) if missing else ""))
    return 0


def cmd_add(args):
    tree, code = (None, 0)
    if os.path.isfile(tree_path(args.analysis)):
        tree, code = need_tree(args)
        if code:
            return code
    tree = tree or {"root": None, "nodes": {}, "plan": {}}
    if not valid_slug(args.slug):
        return fail("slug must make a git branch name exp/SLUG: lowercase letters, digits, '.', '_' or '-', "
                    "starting and ending with a letter, digit, '_' or '-', no '..', not ending in '.lock': " + args.slug)
    if args.slug in tree["nodes"]:
        return fail("node exists: " + args.slug)
    event = {"ev": "add", "node": args.slug, "branch": "exp/" + args.slug, "question": args.question or ""}
    plan_args = {key: getattr(args, key) for key in PLAN_KEYS}
    if args.kind != "candidate":
        event["kind"] = args.kind
    if args.parent is None:
        if tree["root"] is not None:
            return fail("the tree has a root already ({}); give --parent".format(tree["root"]))
        event.update(plan_args)
        event["parent"] = None
        event["mode"] = args.mode or "research"
        wrong = wrong_mode_rows({"mode": event["mode"]}, event)
        if wrong:
            return fail(wrong)
    else:
        if args.mode is not None:
            return fail("only the root holds the mode; children inherit it")
        if args.parent not in tree["nodes"]:
            return fail("unknown parent: " + args.parent)
        if args.kind != "candidate" and not is_method(tree["plan"]):
            return fail("--kind {} is for method mode (root added with --mode method)".format(args.kind))
        if any(value is not None for value in plan_args.values()):
            return fail("only the root holds the plan rows (run command, readout, repair cap, stop rule or "
                        "floor, card, rubric); children inherit them")
        event["parent"] = args.parent
    bad = bad_numbers(event)
    if bad:
        return fail(bad)
    if args.parent is None and args.kind != "candidate" and event["mode"] != "method":
        return fail("--kind {} is for method mode (add --mode method)".format(args.kind))
    append(args.analysis, event)
    note = ""
    if args.parent is None:
        missing = missing_rows(event)
        note = "; missing plan rows: {}. {} Set them later with the plan command.".format(
            ", ".join(missing), ASK) if missing else ""
    print("added {} (branch exp/{}){}".format(args.slug, args.slug, note))
    return 0


def get_node(args, tree):
    node = tree["nodes"].get(args.slug)
    if node is None:
        print("unknown node: " + args.slug)
    return node


def method_refusal(args, tree):
    """In method mode a run or an answer needs a frozen evaluator that still matches its hashes."""
    if not is_method(tree["plan"]):
        return ""
    if tree["evaluator"] is None:
        return "the evaluator is not frozen. Run freeze-evaluator (benchmark card and protected files) first."
    drift = evaluator_drift(tree, args.analysis)
    if drift:
        return "the evaluator changed since it was frozen: {}. Restore it, or ask the user and re-freeze.".format(
            ", ".join("{} ({})".format(os.path.relpath(path, args.analysis), why) for path, why in drift))
    return ""


def cmd_run(args):
    tree, code = need_tree(args)
    if code:
        return code
    node = get_node(args, tree)
    if node is None:
        return 1
    if node["state"] == "frozen":
        return fail("node {} is frozen: a run answered it. Add a child node instead.".format(args.slug), 3)
    if args.receipt is None and args.exit is None:
        return fail("give --receipt N (a line of .mycelium-extra/receipts.jsonl) or --exit CODE")
    blocked = method_refusal(args, tree)
    if blocked:
        return fail(blocked, 3)
    event = {"ev": "run", "node": args.slug, "commit": args.commit or git_head(args.analysis),
             "run_id": args.run_id, "receipt": args.receipt, "exit": args.exit,
             "readout_value": args.readout_value, "log": args.log}
    if args.receipt is not None and receipt_line(args.analysis, args.receipt) is None:
        return fail("receipt line {} not found in {}".format(args.receipt, find_receipts(args.analysis) or RECEIPTS))
    status = run_status(args.analysis, event)
    event["seen_status"] = status
    if args.receipt is not None:
        event["receipt_exit_status"] = str(receipt_line(args.analysis, args.receipt).get("exit_status"))
    append(args.analysis, event)
    print("run recorded for {}: {}".format(args.slug, status))
    if status == "unknown":
        print("The exit status is unknown (a receipt with no integer exit status, as for a background or compound "
              "command). The run counts as neither ok nor failed. Ask the user how it ended.")
    return 0


def cmd_answer(args):
    tree, code = need_tree(args)
    if code:
        return code
    node = get_node(args, tree)
    if node is None:
        return 1
    if node["state"] == "frozen":
        return fail("node {} is already answered and frozen".format(args.slug), 3)
    if node["runs"] and node["runs"][-1]["status"] == "unknown":
        return fail("node {} has a run with an unknown exit status. Ask the user how it ended; if it succeeded, "
                    "record that with `run {} --exit 0`.".format(args.slug, args.slug), 3)
    if not node["runs"] or node["runs"][-1]["status"] != "ok":
        return fail("node {} has no successful run. A failed run answers nothing: repair it, then run again.".format(
            args.slug), 3)
    blocked = method_refusal(args, tree)
    if blocked:
        return fail(blocked, 3)
    if is_method(tree["plan"]) and node["kind"] == "candidate" and not all(tree["ready"].values()):
        return fail("no {} node has run yet. A candidate counts only after a baseline and a sanity node ran.".format(
            " or ".join(name for name, done in tree["ready"].items() if not done)), 3)
    append(args.analysis, {"ev": "answer", "node": args.slug, "outcome": args.outcome, "summary": args.summary,
                           "figures": args.figure or []})
    print("answered {} ({}); branch exp/{} is frozen".format(args.slug, args.outcome, args.slug))
    return 0


def cmd_repair(args):
    tree, code = need_tree(args)
    if code:
        return code
    node = get_node(args, tree)
    if node is None:
        return 1
    if node["state"] == "frozen":
        return fail("node {} is frozen; add a child node instead".format(args.slug), 3)
    if not node["runs"] or node["runs"][-1]["status"] != "failed":
        return fail("node {} has no failed run to repair{}".format(
            args.slug, " (its last run has an unknown exit status; ask the user how it ended)"
            if node["runs"] and node["runs"][-1]["status"] == "unknown" else ""), 3)
    if node["state"] == "repairing":
        return fail("node {} was repaired and has not run since. Run it again before the next repair.".format(
            args.slug), 3)
    cap = tree["plan"].get("repair_cap")
    if not isinstance(cap, int):
        return fail("no repair cap is recorded on the root node. " + ASK, 3)
    if node["repairs"] >= cap:
        return fail("node {} has used its {} repairs. Ask the user: raise the cap (the plan command), drop the node, "
                    "or stop.".format(args.slug, cap), 3)
    append(args.analysis, {"ev": "repair", "node": args.slug, "note": args.note or ""})
    print("repair {} of {} recorded for {}".format(node["repairs"] + 1, cap, args.slug))
    return 0


def cmd_stop(args):
    tree, code = need_tree(args)
    if code:
        return code
    if args.reason == "rule" and is_method(tree["plan"]):
        floor_code, floor_message = stop_check(tree, ignore_stops=True)
        if floor_code != 0:
            return fail("the iteration floor is not met, so the stop rule has not fired: " + floor_message, 3)
    append(args.analysis, {"ev": "stop", "reason": args.reason, "note": args.note or ""})
    print("stop recorded: " + args.reason)
    return 0


def folder_members(path):
    """Every file under a folder, following links to subfolders and leaving out __pycache__ and .pyc files that
    Python rewrites by itself."""
    members, seen = [], set()
    for top, dirs, files in os.walk(path, followlinks=True):
        if os.path.realpath(top) in seen:  # a link back into a folder already walked
            dirs[:] = []
            continue
        seen.add(os.path.realpath(top))
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        members += [os.path.join(top, f) for f in files if not f.endswith(".pyc")]
    return members


def expand_files(analysis, names):
    """[(relative path, absolute path)] for each named file; a folder gives every file under it. None on a bad name."""
    found = {}
    for name in names:
        path = os.path.normpath(os.path.join(analysis, name))
        if os.path.isdir(path):
            members = folder_members(path)
        elif os.path.isfile(path):
            members = [path]
        else:
            return None, name
        for member in members:
            if not os.path.isfile(member):  # a dangling link: its content cannot be hashed
                return None, os.path.relpath(member, analysis).replace(os.sep, "/")
            found[os.path.relpath(member, analysis).replace(os.sep, "/")] = member
    return found, None


def cmd_freeze_evaluator(args):
    tree, code = need_tree(args)
    if code:
        return code
    if not is_method(tree["plan"]):
        return fail("freeze-evaluator is for method mode (root added with --mode method)", 3)
    card = tree["plan"].get("card")
    if not card:
        return fail("the root has no benchmark card. " + ASK, 3)
    if tree["evaluator"] is not None and not args.refreeze:
        return fail("the evaluator is frozen already. Ask the user; to change it, give --refreeze and --note "
                    "(the change is logged).", 3)
    if args.refreeze and not args.note:
        return fail("--refreeze needs --note: say what changed and that the user agreed")
    carried, gone = [], []
    if args.refreeze and tree["evaluator"] is not None:
        # a refreeze keeps what the first freeze protected; --file adds to it
        old_folders = tree["evaluator"].get("folders") or []
        carried = old_folders + [rel for rel in tree["evaluator"]["hashes"]
                                 if not any(rel.startswith(folder + "/") for folder in old_folders)]
        gone = [name for name in carried if not os.path.lexists(os.path.join(args.analysis, name))]
        carried = [name for name in carried if name not in gone]
    names = [card] + carried + (args.file or [])
    files, bad = expand_files(args.analysis, names)
    if files is None:
        return fail("not a readable file or folder: " + bad)
    base = os.path.abspath(args.analysis)
    folders = sorted({os.path.relpath(os.path.join(base, n), base).replace(os.sep, "/")
                      for n in names if os.path.isdir(os.path.join(base, n))})
    note = args.note or ""
    if gone:
        note += " (no longer present, dropped: {})".format(", ".join(gone))
    event = {"ev": "evaluator", "hashes": {rel: file_hash(path) for rel, path in sorted(files.items())},
             "folders": folders, "note": note}
    append(args.analysis, event)
    print("evaluator frozen: {} file(s) hashed (SHA-256), card {}{}".format(
        len(files), card, "; dropped, no longer present: " + ", ".join(gone) if gone else ""))
    return 0


def cmd_check_evaluator(args):
    tree, code = need_tree(args)
    if code:
        return code
    if tree["evaluator"] is None:
        print("the evaluator is not frozen")
        return 3
    drift = evaluator_drift(tree, args.analysis)
    if drift:
        print("evaluator changed: " + ", ".join("{} ({})".format(os.path.relpath(p, args.analysis), why)
                                                for p, why in drift))
        return 3
    print("evaluator unchanged: {} file(s) match".format(len(tree["evaluator"]["hashes"])))
    return 0


def cmd_arena(args):
    tree, code = need_tree(args)
    if code:
        return code
    if not is_method(tree["plan"]):
        return fail("arena is for method mode (root added with --mode method)", 3)
    if not tree["plan"].get("rubric") or tree["rubric_seq"] is None:
        return fail("no rubric is recorded on the root. Fix it before the runs. " + ASK, 3)
    names = list(dict.fromkeys(args.slugs))
    if len(names) < 2 or args.winner not in names:
        return fail("give two or more sibling nodes and a --winner among them")
    unknown = [name for name in names if name not in tree["nodes"]]
    if unknown:
        return fail("unknown node: " + ", ".join(unknown))
    nodes = [tree["nodes"][name] for name in names]
    if len({node["parent"] for node in nodes}) != 1 or any(node["kind"] != "candidate" for node in nodes):
        return fail("an arena compares sibling candidates (one parent, kind candidate)", 3)
    early = [node["id"] for node in nodes if any(run["seq"] < tree["rubric_seq"] for run in node["runs"])]
    if early:
        return fail("the rubric was set after the runs of {}. A rubric fixed after the runs judges nothing."
                    .format(", ".join(early)), 3)
    append(args.analysis, {"ev": "arena", "nodes": names, "winner": args.winner, "note": args.note or ""})
    print("arena recorded: {} won over {}".format(args.winner, ", ".join(n for n in names if n != args.winner)))
    return 0


def node_line(node):
    last = node["runs"][-1] if node["runs"] else {}
    parts = [node["id"], "[" + node["state"] + "]", "branch " + node["branch"]]
    if node.get("kind", "candidate") != "candidate":
        parts.append(node["kind"])
    if last.get("readout_value"):
        parts.append("readout " + str(last["readout_value"]))
    if last.get("log"):
        parts.append("log " + str(last["log"]))
    if node["repairs"]:
        parts.append("repairs {}".format(node["repairs"]))
    if node["answer"]:
        figs = node["answer"].get("figures") or []
        parts.append("{}: {}".format(node["answer"]["outcome"], node["answer"].get("summary", "")))
        parts.append("figure " + (", ".join(figs) if figs else NO_FIGURE))
    return "; ".join(parts)


def cmd_status(args):
    tree, code = need_tree(args)
    if code:
        return code
    stop_code, stop_message = stop_check(tree)
    if args.json:
        out = {"root": tree["root"], "plan": tree["plan"], "evaluator": tree["evaluator"], "arenas": tree["arenas"], "stop": {"met": stop_code == 0, "message": stop_message},
               "nodes": list(tree["nodes"].values())}
        print(json.dumps(out, indent=1, sort_keys=True))
        return 0
    plan = tree["plan"]
    unset = lambda key: plan[key] if plan.get(key) is not None else "not set"  # noqa: E731
    print("run command: {}; readout: {}; repair cap: {}; {}".format(
        plan.get("run_cmd") or "not set", plan.get("readout") or "not set", unset("repair_cap"),
        "mode method; iteration floor: {}; benchmark card: {}; evaluator: {}; rubric: {}".format(
            unset("floor"), unset("card"),
            "{} file(s) hashed".format(len(tree["evaluator"]["hashes"])) if tree["evaluator"] else "not frozen",
            plan.get("rubric") or "not set") if is_method(plan) else "stop after: {}".format(
                unset("stop_after") if plan.get("stop_after") is not None or not plan.get("stop_rule")
                else "no count (the rule is in words)")))
    if plan.get("stop_rule"):
        print("stop rule: " + plan["stop_rule"])
    for arena in tree["arenas"]:
        print("arena: {} won over {}".format(arena["winner"], ", ".join(n for n in arena["nodes"] if n != arena["winner"])))
    for node in tree["nodes"].values():
        print(("  " if node["parent"] else "") + node_line(node) + ("" if not node["parent"] else "; parent " + node["parent"]))
    print(stop_message)
    return 0


def cmd_summary(args):
    tree, code = need_tree(args)
    if code:
        return code
    for node in tree["nodes"].values():
        print(node_line(node))
    print(stop_check(tree)[1])
    return 0


def cmd_frozen(args):
    tree, code = need_tree(args)
    if code:
        return code
    for branch in frozen_branches(tree):
        print(branch)
    return 0


def cmd_stop_check(args):
    tree, code = need_tree(args)
    if code:
        return code
    stop_code, message = stop_check(tree)
    print(message)
    return stop_code


def parser():
    top = argparse.ArgumentParser(prog="tree.py", description=__doc__.split("\n")[0])
    top.add_argument("--analysis", default=".", help="analysis folder holding plans/tree.jsonl (default: .)")
    sub = top.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add")
    add.add_argument("slug")
    add.add_argument("--parent")
    add.add_argument("--question")
    add.add_argument("--run-cmd")
    add.add_argument("--readout")
    add.add_argument("--repair-cap", type=int)
    add.add_argument("--stop-after", type=int)
    add.add_argument("--stop-rule")
    add.add_argument("--mode", choices=MODES)
    add.add_argument("--floor", type=int)
    add.add_argument("--card")
    add.add_argument("--rubric")
    add.add_argument("--kind", choices=KINDS, default="candidate")
    run = sub.add_parser("run")
    run.add_argument("slug")
    run.add_argument("--receipt", type=int)
    run.add_argument("--exit", type=int)
    run.add_argument("--commit")
    run.add_argument("--run-id")
    run.add_argument("--readout-value")
    run.add_argument("--log")
    answer = sub.add_parser("answer")
    answer.add_argument("slug")
    answer.add_argument("--outcome", required=True, choices=OUTCOMES)
    answer.add_argument("--summary", required=True)
    answer.add_argument("--figure", action="append")
    repair = sub.add_parser("repair")
    repair.add_argument("slug")
    repair.add_argument("--note")
    stop = sub.add_parser("stop")
    stop.add_argument("--reason", required=True, choices=REASONS)
    stop.add_argument("--note")
    status = sub.add_parser("status")
    status.add_argument("--json", action="store_true")
    plan = sub.add_parser("plan")
    for flag, kind in (("--run-cmd", str), ("--readout", str), ("--repair-cap", int), ("--stop-after", int),
                       ("--stop-rule", str), ("--floor", int), ("--card", str), ("--rubric", str)):
        plan.add_argument(flag, type=kind)
    plan.set_defaults(mode=None)
    freeze = sub.add_parser("freeze-evaluator")
    freeze.add_argument("--file", action="append")
    freeze.add_argument("--refreeze", action="store_true")
    freeze.add_argument("--note")
    arena = sub.add_parser("arena")
    arena.add_argument("slugs", nargs="+", metavar="SLUG")
    arena.add_argument("--winner", required=True)
    arena.add_argument("--note")
    sub.add_parser("check-evaluator")
    for name in ("summary", "frozen", "stop-check"):
        sub.add_parser(name)
    return top


COMMANDS = {"plan": cmd_plan, "add": cmd_add, "run": cmd_run, "answer": cmd_answer, "repair": cmd_repair, "stop": cmd_stop,
            "status": cmd_status, "summary": cmd_summary, "frozen": cmd_frozen, "stop-check": cmd_stop_check,
            "freeze-evaluator": cmd_freeze_evaluator, "check-evaluator": cmd_check_evaluator, "arena": cmd_arena}


def main(argv=None):
    try:
        args = parser().parse_args(argv)
    except SystemExit as stop:
        return 1 if stop.code else 0
    if args.command in ("add", "plan", "run", "answer", "repair", "stop", "freeze-evaluator", "arena"):
        if args.command == "add":
            os.makedirs(os.path.dirname(tree_path(args.analysis)), exist_ok=True)
        with locked(args.analysis):
            return COMMANDS[args.command](args)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
