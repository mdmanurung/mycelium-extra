"""Experiment tree for the iterate skill: an append-only event log and the questions it answers.

Run: <skill-dir>/../../hooks/mxpy - [--analysis DIR] <command> [options] < <skill-dir>/scripts/tree.py
The log is <analysis>/plans/tree.jsonl, one JSON event per line: add, plan, run, answer, repair, stop.
Nothing edits or deletes a line; every view is a replay. A node added after a stop ends the stop. Stdlib only, Python 3.9+.

Commands
  plan [--run-cmd C] [--readout R] [--repair-cap N] [--stop-after N] [--stop-rule TEXT]
        sets or changes plan rows on the root, after the user confirms them (each change is a logged event)
  add SLUG [--parent P] [--question T]   a node, branch exp/SLUG. The root also takes the plan rows:
        [--run-cmd C] [--readout R] [--repair-cap N] [--stop-after N] [--stop-rule TEXT]
  run SLUG (--receipt N | --exit CODE) [--commit SHA] [--run-id ID] [--readout-value V] [--log PATH]
  answer SLUG --outcome better|same|worse --summary T [--figure PATH ...]   freezes the node
  repair SLUG [--note T]                 a failed run is repaired in place, up to the cap
  stop --reason user|blocker|rule [--note T]
  status [--json]   summary   frozen   stop-check

Exit codes. stop-check: 0 stop rule met or a stop recorded, 3 not yet, 2 no tree or an unreadable one.
Other commands: 0 done, 1 usage or bad input, 3 refused (a frozen node, the repair cap, a missing plan row).
The run command, repair cap and stop rule come from the user's approved plan rows. They have no
defaults here: when one is missing, the command says so and exits 3, and the agent asks the user.
"""

import argparse
import contextlib
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
EVENTS = ("add", "run", "answer", "repair", "stop", "plan")
PLAN_KEYS = ("run_cmd", "readout", "repair_cap", "stop_after", "stop_rule")
TEXT_KEYS = ("node", "parent", "branch", "question", "run_cmd", "readout", "stop_rule", "note", "summary", "outcome",
             "reason", "commit", "run_id", "readout_value", "log")
INT_KEYS = ("repair_cap", "stop_after", "receipt", "exit")
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
    """True when every field the replay reads has the type it expects."""
    if any(event.get(key) is not None and not isinstance(event[key], str) for key in TEXT_KEYS):
        return False
    if any(event.get(key) is not None and (isinstance(event[key], bool) or not isinstance(event[key], int))
           for key in INT_KEYS):
        return False
    figures = event.get("figures")
    return figures is None or (isinstance(figures, list) and all(isinstance(item, str) for item in figures))


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
    path = os.path.abspath(start)
    while True:
        candidate = os.path.join(path, RECEIPTS)
        if os.path.isfile(candidate):
            return candidate
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
    """ok, failed or unknown for one run event: the cited receipt's exit status, else the stated exit code."""
    code = event.get("exit")
    if event.get("receipt") is not None:
        record = receipt_line(analysis, event["receipt"])
        code = record.get("exit_status") if record else None
    if isinstance(code, bool) or not isinstance(code, int):
        return "unknown"
    return "ok" if code == 0 else "failed"


def replay(events, analysis="."):
    """The tree the events describe: {"root": id|None, "plan": {...}, "nodes": {id: node}, "stops": [...]}.

    The log is append-only, so the replay enforces what the commands check: a second `add` of a slug, and any
    run, repair or answer on a frozen node, are ignored. A stop ends the loop until a node is added after it.
    """
    nodes, stops, root, plan, answers = {}, [], None, {}, []
    for event in events:
        kind, slug = event["ev"], event.get("node")
        if kind == "add":
            if slug in nodes:
                continue
            nodes[slug] = {"id": slug, "branch": event.get("branch") or "exp/" + slug, "parent": event.get("parent"),
                           "question": event.get("question") or "", "runs": [], "repairs": 0, "answer": None,
                           "state": "new"}
            stops = []
            if event.get("parent") is None and root is None:
                root = slug
                plan = {key: event.get(key) for key in PLAN_KEYS}
        elif kind == "plan":
            if root is not None:
                plan.update({key: event[key] for key in PLAN_KEYS if event.get(key) is not None})
        elif kind == "stop":
            stops.append(event)
        elif slug in nodes and nodes[slug]["state"] != "frozen":
            node = nodes[slug]
            if kind == "run":
                node["runs"].append(dict(event, status=run_status(analysis, event)))
                node["state"] = "ran" if node["runs"][-1]["status"] == "ok" else "failed"
            elif kind == "repair":
                node["repairs"] += 1
                node["state"] = "repairing"
            elif kind == "answer":
                node["answer"] = event
                node["state"] = "frozen"
                answers.append(event)
    return {"root": root, "plan": plan, "nodes": nodes, "stops": stops, "answers": answers}


def load(analysis):
    try:
        return replay(read_events(tree_path(analysis)), analysis)
    except (TypeError, KeyError, AttributeError, ValueError) as problem:
        raise TreeError("{} holds an event the replay cannot read ({})".format(tree_path(analysis), problem))


def frozen_branches(tree):
    return [node["branch"] for node in tree["nodes"].values() if node["state"] == "frozen"]


def missing_rows(plan):
    """Names of the four impactful plan rows the root does not hold yet (the stop rule needs its count and its words)."""
    rows = (("run command", plan.get("run_cmd")), ("readout", plan.get("readout")),
            ("repair cap", plan.get("repair_cap")),
            ("stop rule", plan.get("stop_after") if plan.get("stop_rule") else None))
    return [name for name, value in rows if value in (None, "")]


def stop_check(tree):
    """(code, message): 0 when a stop is recorded or the stop rule is met, 3 otherwise."""
    if tree["stops"]:
        last = tree["stops"][-1]
        return 0, "stopped: reason {}{}".format(last.get("reason"), " (" + last["note"] + ")" if last.get("note") else "")
    if tree["root"] is None:
        return 3, "the tree has no root node; add one with the run command, readout, repair cap and stop rule. " + ASK
    plan = tree["plan"]
    limit = plan.get("stop_after")
    missing = missing_rows(plan)
    if missing:
        return 3, "the root node has no {}. {}".format(", ".join(missing), ASK)
    streak = 0
    for answer in reversed(tree["answers"]):
        if answer.get("outcome") == "better":
            break
        streak += 1
    if streak >= limit:
        return 0, "stop rule met: the last {} answered nodes were not better".format(streak)
    open_nodes = [n["id"] for n in tree["nodes"].values() if n["state"] != "frozen"]
    return 3, "stop rule not met: {} of {} answered nodes in a row were not better; open nodes: {}".format(
        streak, limit, ", ".join(open_nodes) or "none")


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
    """A message when the repair cap is below 0 (0 means no repairs) or the stop-after count is below 1."""
    for key, floor in (("repair_cap", 0), ("stop_after", 1)):
        if event.get(key) is not None and event[key] < floor:
            return "--{} must be {} or more".format(key.replace("_", "-"), floor)
    return ""


def cmd_plan(args):
    tree, code = need_tree(args)
    if code:
        return code
    if tree["root"] is None:
        return fail("the tree has no root node yet; use add SLUG with the plan rows", 3)
    event = {"ev": "plan", "run_cmd": args.run_cmd, "readout": args.readout, "repair_cap": args.repair_cap,
             "stop_after": args.stop_after, "stop_rule": args.stop_rule}
    if all(event[key] is None for key in PLAN_KEYS):
        return fail("give at least one of --run-cmd --readout --repair-cap --stop-after --stop-rule")
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
    tree = tree or {"root": None, "nodes": {}}
    if not valid_slug(args.slug):
        return fail("slug must make a git branch name exp/SLUG: lowercase letters, digits, '.', '_' or '-', "
                    "starting and ending with a letter, digit, '_' or '-', no '..', not ending in '.lock': " + args.slug)
    if args.slug in tree["nodes"]:
        return fail("node exists: " + args.slug)
    event = {"ev": "add", "node": args.slug, "branch": "exp/" + args.slug, "question": args.question or ""}
    plan_args = {"run_cmd": args.run_cmd, "readout": args.readout, "repair_cap": args.repair_cap,
                 "stop_after": args.stop_after, "stop_rule": args.stop_rule}
    if args.parent is None:
        if tree["root"] is not None:
            return fail("the tree has a root already ({}); give --parent".format(tree["root"]))
        event.update(plan_args)
        event["parent"] = None
    else:
        if args.parent not in tree["nodes"]:
            return fail("unknown parent: " + args.parent)
        if any(value is not None for value in plan_args.values()):
            return fail("only the root holds the run command, readout, repair cap and stop rule; children inherit them")
        event["parent"] = args.parent
    bad = bad_numbers(event)
    if bad:
        return fail(bad)
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
    event = {"ev": "run", "node": args.slug, "commit": args.commit or git_head(args.analysis),
             "run_id": args.run_id, "receipt": args.receipt, "exit": args.exit,
             "readout_value": args.readout_value, "log": args.log}
    if args.receipt is not None and receipt_line(args.analysis, args.receipt) is None:
        return fail("receipt line {} not found in {}".format(args.receipt, find_receipts(args.analysis) or RECEIPTS))
    append(args.analysis, event)
    status = run_status(args.analysis, event)
    print("run recorded for {}: {}".format(args.slug, status))
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
    if not node["runs"] or node["runs"][-1]["status"] != "ok":
        return fail("node {} has no successful run. A failed run answers nothing: repair it, then run again.".format(
            args.slug), 3)
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
    if not node["runs"] or node["runs"][-1]["status"] == "ok":
        return fail("node {} has no failed run to repair".format(args.slug), 3)
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
    append(args.analysis, {"ev": "stop", "reason": args.reason, "note": args.note or ""})
    print("stop recorded: " + args.reason)
    return 0


def node_line(node):
    last = node["runs"][-1] if node["runs"] else {}
    parts = [node["id"], "[" + node["state"] + "]", "branch " + node["branch"]]
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
        out = {"root": tree["root"], "plan": tree["plan"], "stop": {"met": stop_code == 0, "message": stop_message},
               "nodes": list(tree["nodes"].values())}
        print(json.dumps(out, indent=1, sort_keys=True))
        return 0
    plan = tree["plan"]
    print("run command: {}; readout: {}; repair cap: {}; stop after: {}".format(
        plan.get("run_cmd") or "not set", plan.get("readout") or "not set",
        plan.get("repair_cap", "not set") if plan.get("repair_cap") is not None else "not set",
        plan.get("stop_after") if plan.get("stop_after") is not None else "not set"))
    if plan.get("stop_rule"):
        print("stop rule: " + plan["stop_rule"])
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
                       ("--stop-rule", str)):
        plan.add_argument(flag, type=kind)
    for name in ("summary", "frozen", "stop-check"):
        sub.add_parser(name)
    return top


COMMANDS = {"plan": cmd_plan, "add": cmd_add, "run": cmd_run, "answer": cmd_answer, "repair": cmd_repair, "stop": cmd_stop,
            "status": cmd_status, "summary": cmd_summary, "frozen": cmd_frozen, "stop-check": cmd_stop_check}


def main(argv=None):
    try:
        args = parser().parse_args(argv)
    except SystemExit as stop:
        return 1 if stop.code else 0
    if args.command in ("add", "plan", "run", "answer", "repair", "stop"):
        if args.command == "add":
            os.makedirs(os.path.dirname(tree_path(args.analysis)), exist_ok=True)
        with locked(args.analysis):
            return COMMANDS[args.command](args)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
