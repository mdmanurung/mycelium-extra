"""Guard ablations (docs/design/c1-fixture-project.md, section 10).

Each ablation disables one guard in a patched copy of verify or the gate, outside the repository,
and runs the defect case that depends on that guard. The case must pass against the real source
and fail against the patched one; otherwise the case does not test the guard it names.

Run: python3 tests/e2e/ablate.py [A-1 ...]     exit 0 when every ablation bites.
"""

import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import harness  # noqa: E402
import test_end_to_end  # noqa: E402

# (id, "verify" or "gate", exact source text, its replacement, the case that must then fail)
ABLATIONS = [
    ("A-1", "verify", 'report.add("block", "`{}` was edited after its run',
     '(lambda *a: None)("block", "`{}` was edited after its run', "V-03"),
    ("A-2", "verify", 'report.add("block", "Input `{}` changed since the approval',
     '(lambda *a: None)("block", "Input `{}` changed since the approval', "V-06"),
    ("A-3", "gate", "    if stale and not blocked:\n", "    if False:\n", "G-02"),
]


def case_passes(defect_id):
    test = test_end_to_end.Defects("test_" + defect_id.replace("-", "_"))
    with open(os.devnull, "w") as quiet:
        return unittest.TextTestRunner(stream=quiet, verbosity=0).run(test).wasSuccessful()


def patched(tmp, target, old, new):
    """A patched copy: verify.py alone (it runs as stdin source), or the whole hooks/ folder."""
    if target == "verify":
        source, path = harness.VERIFY, os.path.join(tmp, "verify.py")
        shutil.copyfile(source, path)
        entry = path
    else:
        shutil.copytree(os.path.dirname(harness.GATE_RUN), os.path.join(tmp, "hooks"))
        path = os.path.join(tmp, "hooks", "gate.py")
        entry = os.path.join(tmp, "hooks", os.path.basename(harness.GATE_RUN))
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    if text.count(old) != 1:
        raise SystemExit("ablate: the guard text is in {} {} times, not once: {!r}".format(
            path, text.count(old), old))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text.replace(old, new))
    return entry


def ablate(ablation):
    id, target, old, new, defect_id = ablation
    if not case_passes(defect_id):
        return "{}: {} fails against the real source, so the ablation proves nothing".format(id, defect_id)
    tmp = tempfile.mkdtemp(prefix="mx-ablate-")
    saved = harness.GATE_RUN, harness.VERIFY
    try:
        entry = patched(tmp, target, old, new)
        if target == "verify":
            harness.VERIFY = entry
        else:
            harness.GATE_RUN = entry
        if case_passes(defect_id):
            return "{}: {} still passes with the guard removed from {}".format(id, defect_id, target)
    finally:
        harness.GATE_RUN, harness.VERIFY = saved
        shutil.rmtree(tmp, ignore_errors=True)
    return None


def main(argv):
    chosen = [a for a in ABLATIONS if not argv or a[0] in argv]
    failures = []
    for ablation in chosen:
        problem = ablate(ablation)
        print("FAIL " + problem if problem else "ok   {}: {} fails without its guard in {}".format(
            ablation[0], ablation[4], ablation[1]))
        if problem:
            failures.append(problem)
    print("{} of {} ablations bite.".format(len(chosen) - len(failures), len(chosen)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
