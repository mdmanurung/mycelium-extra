#!/usr/bin/env python3
"""Offline read-only stdlib consumer: read_evidence.py PROVENANCE_DIR HASH."""
import hashlib
import json
from pathlib import Path
import re
import sys


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(folder, plan):
    if not re.fullmatch(r"[0-9a-f]{8}", plan):
        raise ValueError("invalid plan hash")
    folder = Path(folder)
    pending = folder / ".transactions" / "pending.json"
    completion = folder / ("complete-" + plan + ".json")
    if pending.exists():
        raise ValueError("interrupted publication; no recovery attempted")
    before = completion.read_bytes()
    marker = json.loads(before)
    required = {p + "-" + plan + "." + ext for p, ext in
                (("plan", "md"), ("receipts", "jsonl"), ("outputs", "tsv"), ("lint", "txt"),
                 ("verify", "md"), ("evidence", "json"))}
    if marker["hash"] != plan or not required.issubset(marker["sha256"]):
        raise ValueError("missing bundle members or wrong plan")
    members = {}
    for name, expected in marker["sha256"].items():
        if not isinstance(name, str) or name.startswith(".") or Path(name).name != name or "\\" in name:
            raise ValueError("unsafe member name")
        path = folder / name
        if path.is_symlink():
            raise ValueError("symlinked member")
        raw = path.read_bytes()
        if sha(raw) != expected:
            raise ValueError("member checksum mismatch: " + name)
        members[name] = raw
    if marker["index_row"] not in (folder / "PROVENANCE.md").read_text(encoding="utf-8").splitlines():
        raise ValueError("index does not commit this generation")
    value = json.loads(members["evidence-" + plan + ".json"])
    semantic = {k: v for k, v in value.items() if k not in
                ("generated_at", "snapshot_digest", "producer", "references")}
    canonical = json.dumps(semantic, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
    if (value["schema"] != "mycelium-extra.evidence-handoff.v1" or value["plan_hash"] != plan
            or sha(canonical) != value["snapshot_digest"]):
        raise ValueError("invalid handoff schema or semantic identity")
    if pending.exists() or completion.read_bytes() != before:
        raise ValueError("publication changed while reading; retry")
    return value


if __name__ == "__main__":
    try:
        value = read(*sys.argv[1:])
        print(json.dumps({"conformity": value["conformity"], "qualification": value["qualification"],
                          "snapshot_digest": value["snapshot_digest"]}, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as error:
        sys.exit("evidence: " + str(error))
