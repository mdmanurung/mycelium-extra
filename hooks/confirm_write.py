"""Prepare a pending write for the gate's `confirm_writes` setting (gate.json).

    sh <plugin>/hooks/py.sh <plugin>/hooks/confirm_write.py prepare --kind KIND --target PATH [--target PATH ...] [--root DIR]

KIND is verify-write, harden, decision-status or idea-triage. Each --target is a repository path the write will
touch (for verify-write, the analysis folder). Writes `.mycelium-extra/write-pending/<id>.json` and prints the
line the user types as a prompt of its own. The gate, not this script, records the consent
(`write-consent/<id>.json`); until it does, the gate denies the write. Cooperative, like `send packet`.
"""
import argparse
import hashlib
import json
import os
import sys
import time

KINDS = ("verify-write", "harden", "decision-status", "idea-triage")


def find_root(start):
    path = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(path, ".mycelium-extra", "gate.json")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def prepare(root, kind, targets):
    rels = []
    for target in targets:
        rel = os.path.relpath(os.path.realpath(os.path.join(root, target)), os.path.realpath(root)).replace(os.sep, "/")
        if rel == ".." or rel.startswith("../"):
            raise SystemExit("confirm_write: {} is outside the project root".format(target))
        rels.append(rel.rstrip("/"))
    now = time.time()
    ident = hashlib.sha256(json.dumps([kind, rels, now]).encode("utf-8")).hexdigest()[:8]
    path = os.path.join(root, ".mycelium-extra", "write-pending", ident + ".json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"schema": "mycelium-extra.write-pending.v1", "id": ident, "kind": kind, "targets": rels, "ts": now}, handle)
    return ident


def main(argv):
    parser = argparse.ArgumentParser(prog="confirm_write")
    parser.add_argument("action", choices=["prepare"])
    parser.add_argument("--kind", required=True, choices=KINDS)
    parser.add_argument("--target", action="append", required=True)
    parser.add_argument("--root", default=None)
    args = parser.parse_args(argv)
    root = args.root or find_root(os.getcwd())
    if not root:
        print("confirm_write: no .mycelium-extra/gate.json found; the gate is not enabled here, so nothing to confirm")
        return 0
    ident = prepare(root, args.kind, args.target)
    print("pending {} write to: {}".format(args.kind, ", ".join(args.target)))
    print("Ask the user to type exactly: confirm write {}".format(ident))
    print("The gate denies this write until they do (valid 1 hour).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
