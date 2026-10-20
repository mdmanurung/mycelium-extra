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
    ("A-3", "gate", "    if (stale or capped) and not blocked:\n", "    if False:\n", "G-02"),
    ("A-4", "verify", "return value if value.is_finite() else None", "return value", "V-31"),
    ("A-5", "verify", 'report.add("block", "{} failed: {}".format(who, one["reason"]))',
     '(lambda *a: None)("block", "{} failed: {}".format(who, one["reason"]))', "V-02c"),
    ("A-6", "gate", '"pins_checked": (launch_match == "matched" and bool(records) and not explore',
     '"pins_checked": (bool(records) and not explore', "F-02"),
    ("A-7", "gate", 'cells = lambda row: tuple(comparison_text(cell) for cell in row["cells"])',
     'cells = lambda row: tuple(clean(cell) for cell in row["cells"])', "F-03"),
    ("A-8", "verify", 'report.add("gap", "{}: {} not checked: resolving citations needs',
     '(lambda *a: None)("gap", "{}: {} not checked: resolving citations needs', "V-33"),
    # consent guards: protected-state writes (A-9..A-11), exact APPROVE matching (A-12, A-13), session scoping
    # (A-14), the explore grant (A-15), on_error (A-16), and the unresolved-operand rule (A-17)
    ("A-9", "gate", '    if writes_state(command, root, event.get("cwd") or root):\n', "    if False:\n", "G-04"),
    ("A-10", "gate", "    if head in SHELLS and any(SHELL_C.match(t) for t in args):\n", "    if False:\n", "G-09"),
    ("A-11", "gate", '    if head == "git":\n        return git_wipes_state(args, ancestor)\n',
     '    if False:\n        return git_wipes_state(args, ancestor)\n', "G-10"),
    ("A-12", "gate", 'APPROVE = re.compile(r"^\\s*approve(?:', 'APPROVE = re.compile(r".*approve(?:', "G-11"),
    ("A-13", "gate", '(\\d{1,4}))?)?\\s*[.!]?\\s*$", re.IGNORECASE)', '(\\d{1,4}))?)?\\s*[.!]?.*$", re.IGNORECASE)',
     "G-11"),
    ("A-14", "gate", '(session_id is None or bool(session_id) and record.get("session_id") == session_id)',
     "True", "G-12"),
    ("A-15", "gate", '        if explore:\n            return deny("mycelium-extra gate: the exploratory-run prefix',
     '        if False:\n            return deny("mycelium-extra gate: the exploratory-run prefix', "G-03"),
    ("A-16", "gate_run", "            policy = value\n", '            policy = "allow"\n', "G-13"),
    ("A-17", "gate", '            if (rel is None and (first or SCRIPT_EXT.search(value)) and re.search(r"[$`]", value)\n',
     '            if (False and (first or SCRIPT_EXT.search(value)) and re.search(r"[$`]", value)\n', "G-14"),
]


def case_passes(defect_id):
    test = test_end_to_end.Defects("test_" + defect_id.replace("-", "_"))
    with open(os.devnull, "w", encoding="utf-8") as quiet:
        return unittest.TextTestRunner(stream=quiet, verbosity=0).run(test).wasSuccessful()


def patched(tmp, target, old, new):
    """A patched copy: verify.py alone (it runs as stdin source), or the whole hooks/ folder (gate.py or gate_run.py)."""
    if target == "verify":
        source, path = harness.VERIFY, os.path.join(tmp, "verify.py")
        shutil.copyfile(source, path)
        entry = path
    else:
        shutil.copytree(os.path.dirname(harness.GATE_RUN), os.path.join(tmp, "hooks"))
        path = os.path.join(tmp, "hooks", "gate_run.py" if target == "gate_run" else "gate.py")
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
