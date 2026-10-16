"""Editable AI drafts and append-only, explicitly reviewed diary saves. Python 3.6+."""

import hashlib
import json
import os
import subprocess
import sys

import capacity


def draft(root, host, sid):
    directory = capacity.session_dir(root, host, sid)
    path = os.path.join(directory, "journal.md")
    with capacity.locked(path + ".lock"):
        if os.path.exists(path):
            return path  # Never overwrite the user's edits or an unreviewed draft.
        text = "# Research diary — AI draft, pending human review\n\n"
        text += "Revise this entry in your own words. `journal save` confirms your review.\n\n"
        text += capacity.summary(root, host, sid)
        text += "\n## My interpretation\n\n<Edit your interpretation here.>\n"
        capacity.atomic(path, text)
        capacity.write(os.path.join(directory, "draft.json"), {
            "initial_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "saved": []})
    return path


def save(root, host, sid, reviewed=False):
    if not reviewed:
        raise ValueError("unreviewed AI drafts remain pending; review then run journal save")
    directory = capacity.session_dir(root, host, sid)
    draft_path = os.path.join(directory, "journal.md")
    with capacity.locked(draft_path + ".lock"):
        with open(draft_path, encoding="utf-8") as handle:
            text = handle.read()
        if not text.strip():
            raise ValueError("diary entry is empty")
        meta_path = os.path.join(directory, "draft.json")
        meta = capacity.read(meta_path, {"saved": []}) if not os.path.exists(meta_path) else capacity.read(meta_path)
        if (not isinstance(meta, dict) or not isinstance(meta.get("saved"), list)
                or not all(isinstance(v, str) for v in meta["saved"])):
            raise ValueError("diary metadata is malformed; preserve draft and metadata for recovery")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        entry = "{}:{}:{}".format(host, sid, digest)
        marker = "<!-- journal:{} -->".format(entry)
        body = "\n## Research diary (human reviewed; AI draft origin)\n\n" + marker + "\n\n"
        # Links in the draft are relative to its checkpoint folder; retain absolute artifact pointers in the log.
        body += "Draft and supporting handoffs: `{}`\n\n".format(draft_path) + text + "\n"
        if os.path.isdir(os.path.join(root, ".living")):
            config = capacity.read(os.path.join(root, capacity.STATE, "capacity.json"), {})
            helper, runtime = config.get("registry_helper"), config.get("mycelium_python")
            if not helper or not runtime:
                raise ValueError("Mycelium diary needs registry_helper and mycelium_python in capacity.json; draft retained")
            p = subprocess.run([runtime, os.path.join(os.path.dirname(__file__), "journal_mycelium.py"),
                                root, sid, helper, draft_path, marker],
                               input=body.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               timeout=8)
            if p.returncode:
                raise ValueError("Mycelium diary save failed; retry safely: " + p.stderr.decode("utf-8", "replace"))
            target = p.stdout.decode("utf-8", "replace").strip()
        else:
            log_dir = os.path.join(root, capacity.STATE, "session-log")
            target = os.path.join(log_dir, host + "-" + capacity.safe_id(sid) + ".md")
            registry = os.path.join(log_dir, "LOG_REGISTRY.md")
            with capacity.locked(registry + ".lock"):
                old = ""
                if os.path.exists(target):
                    with open(target, encoding="utf-8") as handle:
                        old = handle.read()
                if marker not in old:
                    capacity.atomic(target, old + body)
                lines = "# Local session log\n\n| Session | Log |\n|---|---|\n"
                if os.path.exists(registry):
                    with open(registry, encoding="utf-8") as handle:
                        lines = handle.read()
                row = "| {}:{} | [{}]({}) |\n".format(host, sid, sid, os.path.basename(target))
                if row not in lines:
                    capacity.atomic(registry, lines + row)
        if digest not in meta["saved"]:
            meta["saved"].append(digest)
        meta["last_log"] = target
        capacity.write(meta_path, meta)
    return "Saved human-reviewed diary to " + target

