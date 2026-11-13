#!/usr/bin/env python3
"""Run the whole test suite in parallel, longest shard first.

Run: python3.12 tests/run_suite.py [--stage S] [--only PATTERN] [-j N] [--list]

It finds the same files as CI (.github/workflows/ci.yml), runs each file as its own
shard, and splits the two slowest files (hooks/tests/test_gate.py and
skills/verify/tests/test_verify.py) into one shard per TestCase class. Shards run
side by side. Stage `unit` is the test files; the other stages are the ablations,
the adversarial audit, the link check and the gate diff against the pinned base.
Each shard prints one line with its seconds. Failed shards print the tail of their
output, then one summary line. Exit code 0 means every shard passed, 1 means not.

Wall times per shard go to tests/.suite_timings.json (ignored by git) and order the
next run. Under a Python older than 3.9 it starts itself again under a newer one.
"""

import sys

MIN_PYTHON = (3, 9)
PYTHON_CANDIDATES = ("python3.12", "python3.11", "python3.13", "python3.14", "python3.10", "python3.9")


def relaunch_under_newer_python():
    import os
    import shutil
    import subprocess

    for name in PYTHON_CANDIDATES:
        path = shutil.which(name)
        if not path:
            continue
        probe = subprocess.call([path, "-c", "import sys; sys.exit(sys.version_info < %r)" % (MIN_PYTHON,)])
        if probe == 0:
            os.execv(path, [path] + sys.argv)
    sys.stderr.write(
        "run_suite.py needs Python %d.%d or newer, and none of %s is on PATH.\n"
        % (MIN_PYTHON + (", ".join(PYTHON_CANDIDATES),))
    )
    sys.exit(1)


if sys.version_info < MIN_PYTHON:
    relaunch_under_newer_python()

import argparse  # noqa: E402
import ast  # noqa: E402
import concurrent.futures  # noqa: E402
import fnmatch  # noqa: E402
import glob  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402
import signal  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# CI's discovery globs, in CI's order.
TEST_GLOBS = ("hooks/tests/test_*.py", "skills/*/tests/test_*.py", "tests/test_*.py")
# Files that split into one shard per TestCase class (each runs `python FILE ClassName`).
SPLIT_FILES = ("hooks/tests/test_gate.py", "skills/verify/tests/test_verify.py")
GATE_DIFF_BASE = "267d9e244d1f50abef2d024c9632c50df1911823"
STAGES = ("unit", "ablate", "audit", "links", "gate-diff")
TAIL_LINES = 40
UNKNOWN_SECONDS = 30.0  # estimate for a shard never timed: start it early
TIMINGS = os.path.join("tests", ".suite_timings.json")


def test_files(root):
    found = []
    for pattern in TEST_GLOBS:
        found += sorted(glob.glob(os.path.join(root, pattern)))
    return [os.path.relpath(path, root).replace(os.sep, "/") for path in found]


def test_classes(path):
    """Names of the classes in a file that derive from unittest.TestCase and hold tests."""
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), path)
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}

    def base_names(node):
        for base in node.bases:
            if isinstance(base, ast.Attribute):
                yield base.attr
            elif isinstance(base, ast.Name):
                yield base.id

    def is_testcase(name, seen=()):
        if name == "TestCase":
            return True
        if name not in classes or name in seen:
            return False
        return any(is_testcase(base, seen + (name,)) for base in base_names(classes[name]))

    def has_tests(name, seen=()):
        if name not in classes or name in seen:
            return False
        own = any(
            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test")
            for item in classes[name].body
        )
        return own or any(has_tests(base, seen + (name,)) for base in base_names(classes[name]))

    return [name for name in classes if is_testcase(name) and has_tests(name)]


def unit_shards(root, python):
    shards = []
    for rel in test_files(root):
        if rel in SPLIT_FILES:
            names = test_classes(os.path.join(root, rel))
            if names:
                shards += [(rel + "::" + name, [python, rel, name]) for name in names]
                continue
        shards.append((rel, [python, rel]))
    return shards


def link_files(root):
    out = subprocess.run(
        ["git", "ls-files", "*.md", ":!:mycelium-extra-improvements/**"],
        cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if out.returncode != 0:
        return []
    return [line for line in out.stdout.decode("utf-8", "replace").splitlines() if line]


def stage_shards(stage, root, python, scratch):
    """Shards of one stage as (name, argv); a stage whose script is missing gives none."""
    def present(rel):
        return os.path.exists(os.path.join(root, rel))

    if stage == "unit":
        return unit_shards(root, python)
    if stage == "ablate" and present("tests/e2e/ablate.py"):
        return [("ablate", [python, "tests/e2e/ablate.py"])]
    if stage == "audit" and present("tests/adversarial_audit.py"):
        return [("audit", [python, "tests/adversarial_audit.py", "--output", os.path.join(scratch, "adversarial.json")])]
    if stage == "links" and present("tests/check_links.py"):
        files = link_files(root)
        return [("links", [python, "tests/check_links.py"] + files)] if files else []
    if stage == "gate-diff" and present("hooks/tests/gate_diff.py"):
        expect = "hooks/tests/gate_diff_expected.json"
        return [
            ("gate-diff", [python, "hooks/tests/gate_diff.py", "--base", GATE_DIFF_BASE, "--expect", expect]),
            ("gate-diff-self-check", [python, "hooks/tests/gate_diff.py", "--self-check"]),
        ]
    return []


def read_timings(root):
    try:
        with open(os.path.join(root, TIMINGS), encoding="utf-8") as handle:
            data = json.load(handle)
        return {key: float(value) for key, value in data.items()}
    except (OSError, ValueError, AttributeError, TypeError):
        return {}


def write_timings(root, seen):
    path = os.path.join(root, TIMINGS)
    merged = read_timings(root)
    merged.update(seen)
    try:
        with open(path + ".tmp", "w", encoding="utf-8") as handle:
            json.dump(merged, handle, indent=1, sort_keys=True)
            handle.write("\n")
        os.replace(path + ".tmp", path)
    except OSError:
        pass


def run_shard(name, argv, root, timeout):
    start = time.time()
    # Own process group, so a timeout can kill the grandchildren too.
    proc = subprocess.Popen(
        argv, cwd=root, env=dict(os.environ), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True,
    )
    try:
        stdout, _ = proc.communicate(timeout=timeout)
        code, output = proc.returncode, stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            proc.kill()
        stdout, _ = proc.communicate()
        code = -1
        output = (stdout or b"").decode("utf-8", "replace") + "\nTIMEOUT after %ds\n" % timeout
    return {"name": name, "code": code, "seconds": time.time() - start, "output": output}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the test suite in parallel.")
    parser.add_argument("--stage", choices=STAGES + ("all",), default="all")
    parser.add_argument("--only", action="append", default=[], metavar="PATTERN",
                        help="keep shards whose name contains PATTERN (or matches it as a glob); repeatable")
    parser.add_argument("--list", action="store_true", help="print the shards and stop")
    parser.add_argument("-j", "--jobs", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--timeout", type=int, default=1800, help="seconds per shard")
    parser.add_argument("--root", default=REPO, help="repo root (the tests use a temporary one)")
    args = parser.parse_args(argv)
    root = os.path.abspath(args.root)

    scratch = tempfile.mkdtemp(prefix="run_suite_")
    try:
        stages = STAGES if args.stage == "all" else (args.stage,)
        shards = []
        for stage in stages:
            shards += stage_shards(stage, root, sys.executable, scratch)
        if args.only:
            shards = [
                shard for shard in shards
                if any(pat in shard[0] or fnmatch.fnmatch(shard[0], pat) for pat in args.only)
            ]
        if not shards:
            print("No shards match.")
            return 1

        timings = read_timings(root)
        shards.sort(key=lambda shard: -timings.get(shard[0], UNKNOWN_SECONDS))
        if args.list:
            for name, _ in shards:
                known = timings.get(name)
                print("%-8s %s" % ("%.1fs" % known if known is not None else "-", name))
            print("%d shards" % len(shards))
            return 0

        start = time.time()
        results = []
        jobs = max(1, args.jobs)
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = [pool.submit(run_shard, name, cmd, root, args.timeout) for name, cmd in shards]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                results.append(result)
                print("%-4s %7.1fs  %s" % ("ok" if result["code"] == 0 else "FAIL", result["seconds"], result["name"]))
                sys.stdout.flush()

        failed = sorted((r for r in results if r["code"] != 0), key=lambda r: r["name"])
        for result in failed:
            tail = result["output"].rstrip("\n").splitlines()[-TAIL_LINES:]
            print("\n--- %s (exit %s), last %d lines ---" % (result["name"], result["code"], len(tail)))
            print("\n".join(tail))
        write_timings(root, {r["name"]: round(r["seconds"], 2) for r in results if r["code"] == 0})  # a crash is not a real duration
        print("\n%d shards, %d passed, %d failed, %.1fs wall (-j %d)" % (
            len(results), len(results) - len(failed), len(failed), time.time() - start, jobs))
        return 1 if failed else 0
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
