"""Recoverable publication of verify bundles; public filenames stay unchanged."""

import hashlib
import json
import os
import re
import tempfile

from capacity import atomic, locked


def sha(path):
    if os.path.islink(path):
        raise ValueError("symlinked provenance member: " + path)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def record(path, value):
    atomic(path, json.dumps(value, sort_keys=True, indent=2) + "\n")


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def copy(source, target):
    with open(source, encoding="utf-8", errors="surrogateescape") as handle:
        atomic(target, handle.read())


def bundle_state(folder, digest):
    """Read under the publication lock. A marker is evidence, never permission."""
    if os.path.exists(os.path.join(folder, ".transactions", "pending.json")):
        return "interrupted"
    path = os.path.join(folder, "complete-{}.json".format(digest))
    if not os.path.exists(path):
        return "legacy"
    try:
        value = load(path)
        members = value["sha256"]
        required = {"{}-{}.{}".format(prefix, digest, ext) for prefix, ext in
                    (("plan", "md"), ("receipts", "jsonl"), ("outputs", "tsv"),
                     ("verify", "md"), ("lint", "txt"))}
        if (value["hash"] != digest or not required.issubset(members)
                or not all(os.path.basename(p) == p and sha(os.path.join(folder, p)) == h
                           and isinstance(h, str) for p, h in members.items())):
            return "interrupted"
        with open(os.path.join(folder, "PROVENANCE.md"), encoding="utf-8") as handle:
            return "complete" if value["index_row"] in handle.read().splitlines() else "interrupted"
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return "interrupted"


def recover(folder):
    """Called with the analysis lock held. Keep all staged and previous evidence."""
    pending = os.path.join(folder, ".transactions", "pending.json")
    if not os.path.exists(pending):
        return
    try:
        tx = load(pending)
        name, members = tx["transaction"], tx["members"]
        if (not isinstance(name, str) or not re.fullmatch(r"txn-[A-Za-z0-9_-]+", name)
                or not isinstance(members, dict) or "PROVENANCE.md" not in members):
            raise ValueError("invalid transaction")
        directory = os.path.join(folder, ".transactions", name)
        for path, hashes in members.items():
            if (os.path.basename(path) != path or path.startswith(".")
                    or not isinstance(hashes, dict) or not isinstance(hashes.get("new"), str)):
                raise ValueError("invalid transaction member")
            for version in ("old", "new"):
                if sha(os.path.join(directory, version, path)) != hashes.get(version):
                    raise ValueError("damaged staged/previous member")
        current = {p: sha(os.path.join(folder, p)) for p in members}
        if not all(current[p] == h["new"] for p, h in members.items()):
            if any(current[p] not in (h.get("old"), h["new"]) for p, h in members.items()):
                raise ValueError("ambiguous external change")
            for path in sorted(members, key=lambda p: p == "PROVENANCE.md"):
                target = os.path.join(folder, path)
                if members[path].get("old") is None:
                    if os.path.exists(target):
                        os.unlink(target)
                else:
                    copy(os.path.join(directory, "old", path), target)
            if any(sha(os.path.join(folder, p)) != h.get("old") for p, h in members.items()):
                raise ValueError("rollback did not match")
        record(os.path.join(directory, "recovered.json"), {"outcome":
               "finalized" if all(current[p] == h["new"] for p, h in members.items()) else "restored"})
        os.unlink(pending)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        raise ValueError("provenance recovery gap; retain transaction evidence: " + str(error))


def publish(folder, digest, build, fault=lambda stage: None):
    """Stage, back up, mark pending, publish members/completion, then the index."""
    if not re.fullmatch(r"[0-9a-f]{8}", digest):
        raise ValueError("invalid provenance plan hash")
    os.makedirs(folder, exist_ok=True)
    with locked(os.path.join(folder, ".publish.lock")):
        recover(folder)
        if bundle_state(folder, digest) == "interrupted":
            raise ValueError("provenance recovery gap; existing completion does not match; retain evidence")
        transactions = os.path.join(folder, ".transactions")
        os.makedirs(transactions, exist_ok=True)
        directory = tempfile.mkdtemp(prefix="txn-", dir=transactions)
        new, old = [os.path.join(directory, v) for v in ("new", "old")]
        os.mkdir(new)
        os.mkdir(old)
        index = os.path.join(folder, "PROVENANCE.md")
        if os.path.exists(index):
            copy(index, os.path.join(new, "PROVENANCE.md"))
        names = build(new)
        hashes = {p: sha(os.path.join(new, p)) for p in names if p != "PROVENANCE.md"}
        with open(os.path.join(new, "PROVENANCE.md"), encoding="utf-8") as handle:
            row = next(line for line in handle if line.startswith("| {} |".format(digest))).rstrip("\n")
        completion = "complete-{}.json".format(digest)
        record(os.path.join(new, completion), {"hash": digest, "sha256": hashes, "index_row": row})
        names = sorted(set(names + [completion]), key=lambda p: p == "PROVENANCE.md")
        members = {}
        for path in names:
            target = os.path.join(folder, path)
            before = sha(target)
            if before is not None:
                copy(target, os.path.join(old, path))
            # fsync all staged files before publishing the pending record.
            copy(os.path.join(new, path), os.path.join(new, path))
            members[path] = {"old": before, "new": sha(os.path.join(new, path))}
        fault("staged")
        tx = {"transaction": os.path.basename(directory), "members": members}
        record(os.path.join(directory, "transaction.json"), tx)
        pending = os.path.join(transactions, "pending.json")
        record(pending, tx)
        fault("pending")
        for path in names:
            copy(os.path.join(new, path), os.path.join(folder, path))
            fault(path)
        record(os.path.join(directory, "published.json"), {"hash": digest})
        os.unlink(pending)
        fault("done")
        return names
