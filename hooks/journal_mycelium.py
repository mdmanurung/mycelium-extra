"""Use the installed Mycelium updater's locks and row format for diary preservation.

Executed with Mycelium's Python (3.11+); this adapter's own syntax stays 3.6 compatible.
"""

import datetime
import importlib.util
import os
from pathlib import Path
import sys


def main(root, sid, helper, draft_path, marker, body):
    sys.path.insert(0, os.path.dirname(helper))
    spec = importlib.util.spec_from_file_location("mycelium_registry", helper)
    updater = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(updater)
    log_dir = Path(root) / ".living" / "log"
    registry = log_dir / "LOG_REGISTRY.md"
    if not registry.is_file():
        raise ValueError("existing Mycelium LOG_REGISTRY.md is required")
    # Resolve the exact session row under the same lock as Mycelium's Stop updater.
    with updater.durable_path_lock(registry):
        lines = registry.read_text(encoding="utf-8").splitlines(keepends=True)
        index, cells = None, None
        for i, line in enumerate(lines):
            row = updater._row_cells(line)
            if row and row[1] == sid:
                index, cells = i, row
                break
        if cells is None:
            # Host IDs are recovery pointers; Mycelium may own a different log session ID.
            # Never guess or attach diary text to another active session.
            raise ValueError("no exact session row in LOG_REGISTRY; finalize this session first or configure its matching ID")
        import re
        link = re.search(r"\]\(([^)]+)\)", cells[10])
        if not link:
            raise ValueError("session registry row has no log link")
        target = Path(os.path.abspath(str(log_dir / link.group(1))))
        if target.parent != log_dir or not target.is_file():
            raise ValueError("session log must be an existing file inside .living/log")
        with updater.durable_path_lock(target):
            old = target.read_text(encoding="utf-8")
            if marker not in old:
                updater.atomic_write_text(target, old + body)
        # Keep all lifecycle and authored fields; only add the diary tag.
        if "journal" not in cells[9].split(", "):
            cells[9] = ", ".join(filter(None, (cells[9], "journal")))
        lines[index] = updater._render_cells(cells)
        updater.atomic_write_text(registry, "".join(lines))
    print(str(target))


if __name__ == "__main__":
    try:
        main(*sys.argv[1:], body=sys.stdin.buffer.read().decode("utf-8"))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
