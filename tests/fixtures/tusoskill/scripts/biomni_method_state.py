"""Stub of a method-state helper for the loop guard's bridge tests. It reads state/state.json and nothing else.

  stop-check --root R                          exit 0 when iteration >= max_iterations or state/blocker.json exists,
                                               else exit 3, printing one JSON object with a self_audit_line
  record-blocker --root R --kind K --detail D  writes state/blocker.json

Written for this repository's tests. It is not a copy of any real helper.
"""

import argparse
import json
import os
import sys


def main():
    top = argparse.ArgumentParser()
    sub = top.add_subparsers(dest="command", required=True)
    for name in ("stop-check", "record-blocker"):
        item = sub.add_parser(name)
        item.add_argument("--root", required=True)
        if name == "record-blocker":
            item.add_argument("--kind", required=True, choices=("benchmark", "data", "infra", "user"))
            item.add_argument("--detail", required=True)
    args = top.parse_args()
    state_dir = os.path.join(args.root, "state")
    blocker = os.path.join(state_dir, "blocker.json")
    if args.command == "record-blocker":
        with open(blocker, "w") as handle:
            json.dump({"kind": args.kind, "detail": args.detail}, handle)
        return 0
    with open(os.path.join(state_dir, "state.json")) as handle:
        state = json.load(handle)
    done = state["iteration"] >= state["max_iterations"] or os.path.isfile(blocker)
    print(json.dumps({"self_audit_line": "STOP-GATE: iteration={}/{}; may_finalize={}".format(
        state["iteration"], state["max_iterations"], "yes" if done else "no")}))
    return 0 if done else 3


if __name__ == "__main__":
    sys.exit(main())
