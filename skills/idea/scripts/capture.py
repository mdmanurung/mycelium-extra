"""Capture ideas exclusively; registry errors leave an idempotent recovery record.

Run from stdin with --plugin-root, --root, --helper, --python and --text-file.
Use --recover instead of --text-file to retry pending captures, never plain-edit a registry.
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile


HEADER = ("# Todo registry\n\n| Item | Priority | Status | Category | Date | Author | File |\n"
          "|---|---|---|---|---|---|---|\n")


def cell(text):
    return text.replace("|", "&#124;").replace("\r", " ").replace("\n", " ")


def publish(todo, note, runtime, helper, write):
    with open(note, encoding="utf-8") as handle:
        record = json.load(handle)
    name = record["file"]
    if not re.fullmatch(r"[a-z0-9-]+\.md", name):
        raise ValueError("invalid capture recovery filename")
    text = record["text"]
    path = os.path.join(todo, name)
    if not os.path.lexists(path):
        reserve(todo, path, text)
    with open(path, encoding="utf-8") as handle:
        if os.path.islink(path) or handle.read() != text:
            raise ValueError("idea changed; recovery retained for review: " + note)
    registry = os.path.join(todo, "TODO_REGISTRY.md")
    if os.path.islink(registry):
        raise ValueError("symlinked registry refused; recovery retained: " + note)
    if not os.path.lexists(registry):
        reserve(todo, registry, HEADER)
    result = subprocess.run([runtime, helper, registry, record["key"], record["row"], "--key-column", "7"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    if result.returncode:
        raise ValueError("registry publication failed; idea and recovery record retained: " + note)
    record["published"] = True
    write(note, record)
    return name


def reserve(todo, path, text):
    fd, stage = tempfile.mkstemp(prefix=".idea-text-", dir=todo)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(stage, path)  # Exclusive publication of a complete file.
    finally:
        os.unlink(stage)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin-root", required=True)
    parser.add_argument("--root", default=os.getcwd())
    parser.add_argument("--helper", required=True)
    parser.add_argument("--python", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text-file")
    source.add_argument("--recover", action="store_true")
    parser.add_argument("--context", default="")
    args = parser.parse_args(argv)
    sys.path.insert(0, os.path.join(args.plugin_root, "hooks"))
    from stateio import atomic, locked, write, command
    todo = os.path.join(os.path.realpath(args.root), "todo")
    try:
        if os.path.realpath(todo) != todo:
            raise ValueError("symlinked todo directory refused")
        os.makedirs(todo, exist_ok=True)
        with locked(os.path.join(todo, ".capture.lock")):
            if args.recover:
                notes = []
                for name in sorted(os.listdir(todo)):
                    if name.startswith(".capture-") and name.endswith(".json"):
                        path = os.path.join(todo, name)
                        with open(path, encoding="utf-8") as handle:
                            record = json.load(handle)
                        if not record.get("published"):
                            notes.append(path)
            else:
                with open(args.text_file, encoding="utf-8") as handle:
                    idea = handle.read()
                if not idea.strip():
                    raise ValueError("idea text is empty")
                title = " ".join(idea.split()[:8])
                slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "idea"
                reserved = set()
                for pending in os.listdir(todo):
                    if pending.startswith(".capture-") and pending.endswith(".json"):
                        with open(os.path.join(todo, pending), encoding="utf-8") as handle:
                            reserved.add(json.load(handle)["file"])
                name, counter = slug + ".md", 2
                while name in reserved or os.path.lexists(os.path.join(todo, name)):
                    name = "{}-{}.md".format(slug, counter)
                    counter += 1
                date = datetime.date.today().isoformat()
                author = command(args.root, ["git", "config", "user.name"]) or "unknown"
                context = args.context or (command(args.root, ["git", "branch", "--show-current"]) or "unknown branch")
                key = "[{}]({})".format(name, name)
                row = "| {} | idea | open | idea | {} | {} | {} |".format(cell(title), date, cell(author), key)
                text = ("# {}\n\n| Field | Value |\n|---|---|\n| **Date** | {} |\n| **Author** | {} |\n"
                        "| **Priority** | idea |\n| **Status** | open |\n| **Category** | idea |\n\n"
                        "## Description\n\n{}\n\n## Notes\n\n{}\n").format(title, date, cell(author), idea, context)
                # Record before publication so an interrupted capture retains the exact user text.
                fd, note = tempfile.mkstemp(prefix=".capture-", suffix=".json", dir=todo)
                os.close(fd)
                write(note, {"file": name, "text": text, "key": key, "row": row, "published": False})
                notes = [note]
            for note in notes:
                print("Parked: todo/" + publish(todo, note, args.python, args.helper, write))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        print("capture: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
