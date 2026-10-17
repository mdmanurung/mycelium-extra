"""Atomic writes, a short file lock, and a quiet git call for the gate's state files."""

import contextlib
import json
import os
import subprocess
import tempfile
import time


def atomic(path, text):
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    if os.path.realpath(parent) != os.path.abspath(parent) or os.path.islink(path):
        raise ValueError("refusing a symlinked state target")
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        directory_fd = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write(path, value):
    atomic(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


@contextlib.contextmanager
def locked(path):
    import fcntl
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.realpath(path) != os.path.abspath(path):
        raise ValueError("refusing a symlinked lock")
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        deadline = time.monotonic() + 2
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ValueError("checkpoint lock busy; retry")
                time.sleep(0.02)
        yield
    finally:
        os.close(fd)


def command(cwd, argv):
    try:
        p = subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=2, encoding="utf-8", errors="replace")
        return p.stdout.strip() if p.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None
