"""Bind a plan-review packet to the exact bytes the user consented to send (roadmap C11).

    sh <plugin>/hooks/py.sh <plugin>/skills/plan-review/scripts/review_packet.py prepare --packet <file> [--attach <repo-relative file> ...] [--root <project root>]
    sh <plugin>/hooks/py.sh <plugin>/skills/plan-review/scripts/review_packet.py preview --digest <hex, at least 12>
    sh <plugin>/hooks/py.sh <plugin>/skills/plan-review/scripts/review_packet.py verify --digest <hex, at least 12>

`prepare` runs the pre-send scan (`presend_check.py`) and refuses what it says not to send. It then writes, under
`<root>/.mycelium-extra/review-packets/<digest>/`, `packet.txt` (the packet's bytes), `workspace/<path>` (a copy
of each explicitly selected attachment) and `manifest.json` (the packet's and each attachment's size and SHA-256,
the scan counts and the time). The DIGEST is the SHA-256 of the manifest's bytes, so it covers the packet hash.

`preview` prints the digest, the attachment list and the exact line the user must type: `send packet <digest12>`.

`verify` runs immediately before the documented send route. It recomputes the packet and attachment hashes and
refuses (exit 3) on any difference, on any file in the folder that the manifest does not list, on an attachment
edited since `prepare`, and unless a consent record for exactly this digest exists and is newer than the packet.
It then prints the single list of files to send: `packet.txt` and the `workspace/` files, nothing else.

A consent record is `<root>/.mycelium-extra/review-consent/<digest>.json` with `schema`
"mycelium-extra.review-consent.v1", `digest`, `session_id`, `ts` (epoch seconds) and `prompt` (the user's literal
prompt, `send packet <12 or more hex of the digest>`). The approval gate writes it after it observes that prompt.
THIS SCRIPT NEVER WRITES ONE: a consent an agent could write by assertion would prove nothing.

This is a cooperative mechanism, not a sandbox. It does not send anything, and it cannot stop an agent with
unrestricted shell access from sending other bytes or writing a consent record itself. It shows that the files
named by `verify` are the ones the user approved. Exit 0: ok. 1: could not run. 3: refused, do not send.
Run it by path (it loads `presend_check.py` from its own folder), not from stdin. Standard library only; Python 3.9+.
"""

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import presend_check  # noqa: E402

SCHEMA = "mycelium-extra.review-packet.v1"
CONSENT_SCHEMA = "mycelium-extra.review-consent.v1"
STATE = ".mycelium-extra"
MIN_PREFIX = 12
MAX_ATTACHMENT = 1000000
# Code and documents only. A table, an archive or an unknown type is not an attachment.
ALLOWED_EXT = (".py", ".r", ".rmd", ".qmd", ".md", ".txt", ".sh", ".smk", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".tex")
BLOCKED_DIRS = ("data", ".git", ".mycelium-extra", ".ssh")


class Refuse(Exception):
    """Do not send: the message says why, and never carries a flagged value."""


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def write_ro(path, raw):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(raw)
    os.chmod(path, 0o444)


def find_root(start):
    """The nearest directory with .mycelium-extra/gate.json (as the gate finds it), else `start`."""
    path = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(path, STATE, "gate.json")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return os.path.abspath(start)
        path = parent


def packets_dir(root):
    return os.path.join(root, STATE, "review-packets")


def attachment_path(root, given):
    """(path relative to root with /, bytes) for one explicitly selected attachment, or Refuse."""
    path = given if os.path.isabs(given) else os.path.join(root, given)
    real = os.path.realpath(path)
    rel = os.path.relpath(real, os.path.realpath(root)).replace(os.sep, "/")
    if rel.startswith("../") or rel == "..":
        raise Refuse("attachment {!r} is outside the project root".format(given))
    if not os.path.isfile(real):
        raise Refuse("attachment {!r} is not a regular file".format(given))
    if rel.split("/")[0] in BLOCKED_DIRS or any(p in BLOCKED_DIRS for p in rel.split("/")[:-1]):
        raise Refuse("attachment {!r} is under a directory that is never attached ({})".format(
            given, ", ".join(BLOCKED_DIRS)))
    if not rel.lower().endswith(ALLOWED_EXT) or os.path.basename(rel).lower().startswith(".env"):
        raise Refuse("attachment {!r} is not a code or document type ({})".format(given, " ".join(ALLOWED_EXT)))
    raw = read_bytes(real)
    if len(raw) > MAX_ATTACHMENT:
        raise Refuse("attachment {!r} is over {} bytes".format(given, MAX_ATTACHMENT))
    return rel, raw


def prepare(root, packet_file, attachments, consent_unread_inputs=False):
    raw = read_bytes(packet_file)
    scan = presend_check.analyse(raw, root)
    out = ["Pre-send scan of the packet: sha256 {}.".format(scan["packet_sha256"]),
           presend_check.render(scan["flags"], scan["unread"], scan["redactions_listed"]).rstrip()]
    # The user may consent to a stated input coverage gap (SKILL.md), but not to undisclosed flags or a
    # malformed redactions block: those still refuse.
    gap_only = bool(scan["unread"]) and not scan["flags"] and scan["redactions_valid"]
    if scan["exit"] in (1, 3) and not (consent_unread_inputs and gap_only):
        raise Refuse("\n".join(out + ["The scan says do not send; fix the packet, then prepare again."
                                      + ("" if not scan["unread"] or scan["flags"] or not scan["redactions_valid"]
                                         else " To send with the input coverage gap the user accepted, pass "
                                              "--consent-unread-inputs.")]))
    files = {}
    for given in attachments:
        rel, data = attachment_path(root, given)
        files[rel] = data
    flagged = []
    for rel in sorted(files):
        for number, kind, masked, _ in presend_check.check(files[rel].decode("utf-8", "replace"))[0]:
            flagged.append("- attachment {} line {}: {} `{}`".format(rel, number, kind, masked))
    manifest = {"schema": SCHEMA, "created": int(time.time()),
                "packet": {"name": "packet.txt", "size": len(raw), "sha256": sha256_bytes(raw)},
                "attachments": [{"path": rel, "size": len(files[rel]), "sha256": sha256_bytes(files[rel])}
                                for rel in sorted(files)],
                "scan": {"packet_exit": scan["exit"], "packet_flags": len(scan["flags"]),
                         "attachment_flags": len(flagged), "inputs_unread": len(scan["unread"]),
                         "consented_unread_inputs": bool(consent_unread_inputs and gap_only)}}
    mbytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("ascii")
    digest = sha256_bytes(mbytes)
    base = packets_dir(root)
    os.makedirs(base, exist_ok=True)
    final = os.path.join(base, digest)
    tmp = tempfile.mkdtemp(prefix=".tmp-", dir=base)
    try:
        write_ro(os.path.join(tmp, "packet.txt"), raw)
        for rel, data in files.items():
            write_ro(os.path.join(tmp, "workspace", rel), data)
        write_ro(os.path.join(tmp, "manifest.json"), mbytes)
        if os.path.isdir(final):
            raise Refuse("this exact packet was already prepared: digest {}".format(digest))
        os.rename(tmp, final)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    out += flagged[:30]
    out.append("digest: {}".format(digest))
    out.append("Prepared {} file(s). Next: preview --digest {}".format(1 + len(files), digest[:MIN_PREFIX]))
    return "\n".join(out) + "\n"


def resolve(root, prefix):
    prefix = prefix.lower()
    if not re.fullmatch(r"[0-9a-f]{%d,64}" % MIN_PREFIX, prefix):
        raise Refuse("--digest needs at least {} hex characters".format(MIN_PREFIX))
    base = packets_dir(root)
    names = [n for n in (os.listdir(base) if os.path.isdir(base) else []) if re.fullmatch(r"[0-9a-f]{64}", n)
             and n.startswith(prefix)]
    if len(names) != 1:
        raise Refuse("{} prepared packet(s) match {}".format(len(names), prefix))
    return names[0], os.path.join(base, names[0])


def load(folder, digest):
    """(manifest, problems) for a prepared folder; problems are reasons to refuse, never values."""
    try:
        mbytes = read_bytes(os.path.join(folder, "manifest.json"))
        manifest = json.loads(mbytes.decode("ascii"))
        listed = [a["path"] for a in manifest["attachments"]]
        assert manifest["schema"] == SCHEMA and isinstance(manifest["created"], int)
        assert isinstance(manifest["packet"]["sha256"], str) and all(isinstance(p, str) for p in listed)
        assert all(not p.startswith("/") and ".." not in p.split("/") for p in listed)
    except (OSError, ValueError, KeyError, TypeError, AssertionError):
        raise Refuse("manifest.json is missing or malformed")
    if sha256_bytes(mbytes) != digest:
        raise Refuse("manifest.json bytes do not hash to the digest")
    problems = []
    expected = {"manifest.json", "packet.txt"} | {"workspace/" + p for p in listed}
    actual = set()
    for here, dirs, names in os.walk(folder):
        for name in dirs + names:
            full = os.path.join(here, name)
            rel = os.path.relpath(full, folder).replace(os.sep, "/")
            if os.path.islink(full):
                problems.append("unexpected symlink: " + rel)
            elif os.path.isfile(full):
                actual.add(rel)
    problems += ["unexpected file: " + p for p in sorted(actual - expected)]
    problems += ["missing file: " + p for p in sorted(expected - actual)]
    packet = os.path.join(folder, "packet.txt")
    if "packet.txt" in actual and sha256_bytes(read_bytes(packet)) != manifest["packet"]["sha256"]:
        problems.append("packet.txt changed (hash differs from the manifest)")
    return manifest, problems


def attachment_problems(root, folder, manifest):
    problems = []
    for a in manifest["attachments"]:
        snap = os.path.join(folder, "workspace", a["path"])
        if os.path.isfile(snap) and sha256_bytes(read_bytes(snap)) != a["sha256"]:
            problems.append("attachment changed (snapshot hash differs): " + a["path"])
        try:
            if sha256_bytes(read_bytes(os.path.join(root, a["path"]))) != a["sha256"]:
                problems.append("attachment changed since prepare (source hash differs): " + a["path"])
        except OSError:
            problems.append("attachment source missing since prepare: " + a["path"])
    return problems


def preview(root, prefix):
    digest, folder = resolve(root, prefix)
    manifest, problems = load(folder, digest)
    out = ["digest: {}".format(digest), "packet: packet.txt, {} bytes, sha256 {}".format(
        manifest["packet"]["size"], manifest["packet"]["sha256"])]
    out += ["attachment: {} ({} bytes, sha256 {}...)".format(a["path"], a["size"], a["sha256"][:12])
            for a in manifest["attachments"]] or ["attachments: none"]
    scan = manifest.get("scan", {})
    out.append("pre-send flags: {} in the packet, {} in attachments; {} input(s) not checked".format(
        scan.get("packet_flags"), scan.get("attachment_flags"), scan.get("inputs_unread")))
    problems += attachment_problems(root, folder, manifest)
    if problems:
        raise Refuse("\n".join(out + ["REFUSED, the folder no longer matches what was prepared:"] +
                               ["- " + p for p in problems]))
    out.append("To approve exactly these bytes, the user types:  send packet {}".format(digest[:MIN_PREFIX]))
    out.append("Typing it is recorded by the approval gate, not by this script.")
    return "\n".join(out) + "\n"


def check_consent(root, digest, manifest):
    path = os.path.join(root, STATE, "review-consent", digest + ".json")
    if not os.path.isfile(path):
        raise Refuse("no consent record for digest {}: the user has not typed `send packet {}`".format(
            digest[:MIN_PREFIX], digest[:MIN_PREFIX]))
    try:
        rec = json.loads(read_bytes(path).decode("utf-8"))
        ok = (rec["schema"] == CONSENT_SCHEMA and rec["digest"] == digest and
              isinstance(rec["session_id"], str) and rec["session_id"] and
              isinstance(rec["ts"], (int, float)) and not isinstance(rec["ts"], bool))
        typed = re.fullmatch(r"send packet ([0-9a-f]{%d,64})" % MIN_PREFIX, rec["prompt"].strip().lower())
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise Refuse("consent record is malformed")
    if not ok:
        raise Refuse("consent record is for another digest or malformed")
    if not typed or not digest.startswith(typed.group(1)):
        raise Refuse("consent prompt does not name this digest")
    if rec["ts"] <= manifest["created"]:
        raise Refuse("consent was recorded at or before the packet was prepared")


def verify(root, prefix):
    digest, folder = resolve(root, prefix)
    manifest, problems = load(folder, digest)
    problems += attachment_problems(root, folder, manifest)
    if problems:
        raise Refuse("\n".join(["REFUSED, do not send:"] + ["- " + p for p in problems]))
    check_consent(root, digest, manifest)
    files = [os.path.join(folder, "packet.txt")] + [os.path.join(folder, "workspace", a["path"])
                                                     for a in manifest["attachments"]]
    return "\n".join(["Verified digest {}: bytes match and the user's consent is recorded.".format(digest),
                      "Send exactly these files and nothing else:"] + files +
                     ["This script sent nothing; it is a cooperative check, not a sandbox."]) + "\n"


def main(argv):
    parser = argparse.ArgumentParser(prog="review_packet")
    parser.add_argument("command", choices=("prepare", "preview", "verify"))
    parser.add_argument("--packet", help="prepare: the packet file")
    parser.add_argument("--attach", action="append", default=[], help="prepare: a code or document file (repeatable)")
    parser.add_argument("--consent-unread-inputs", action="store_true",
                        help="prepare: the user accepted the stated input coverage gap")
    parser.add_argument("--digest", help="preview, verify: the digest or its first 12+ hex characters")
    parser.add_argument("--root", default=None, help="project root (default: nearest with .mycelium-extra/gate.json)")
    args = parser.parse_args(argv)
    root = os.path.abspath(args.root) if args.root else find_root(os.getcwd())
    try:
        if args.command == "prepare":
            if not args.packet:
                parser.error("prepare needs --packet")
            sys.stdout.write(prepare(root, args.packet, args.attach, args.consent_unread_inputs))
        else:
            if not args.digest:
                parser.error(args.command + " needs --digest")
            sys.stdout.write((preview if args.command == "preview" else verify)(root, args.digest))
    except Refuse as why:
        sys.stdout.write("review_packet: {}\n".format(why))
        return 3
    except (OSError, IOError) as error:
        sys.stderr.write("review_packet: {}\n".format(error))
        return 1
    return 0


if __name__ == "__main__":
    if sys.stdout.encoding.lower().replace("-", "") != "utf8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, sys.stdout.encoding, "backslashreplace")
    sys.exit(main(sys.argv[1:]))
