"""Project-owned checks for the declared-check variants of DC-08 to DC-11 (roadmap C08).

Each text below is a file the researcher approves together with the plan: defects.py writes it into the
disposable project, commits it, and the plan's validation binding pins it. Every one imports the project's
real step 02 (analysis/vaccine-response/scripts/02_paired_test.py), points its input and output constants at a
temporary folder and calls its main(), so a defect planted inside main() (the contrast's sign, the join of
counts to metadata, the size factors) is exercised, not a copy of the computation or a label. Nothing is
written into the project except the evidence file named on the plan's Outputs: line.

The tiny dataset has a known answer. Four donors (V1, V2 vaccine; P1, P2 placebo) have a day 0 and a day 28 library;
five genes never change, UP rises from 100 to 400 in the vaccine arm only and DOWN falls from 100 to 25 there. With
median-of-ratios size factors every size factor is 1 (the median ratio is that of an unchanged gene), so
log2fc(UP) = log2(401/101), log2fc(DOWN) = log2(26/101), and every unchanged gene is 0. Total-count scaling instead
moves the unchanged genes by about -0.4, which is the composition effect the planned normalization avoids.

Stdlib only, Python 3.6 grammar (the harness runs these under its own interpreter).
"""

PRELUDE = '''"""Declared check @NAME@ (approved with the plan): the real step 02 on a tiny known-answer dataset."""
import contextlib
import importlib.util
import io
import json
import math
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
STEP = os.path.join(HERE, "..", "scripts", "02_paired_test.py")
EVIDENCE = os.path.join(HERE, "..", "outputs", "@NAME@_check.json")
DONORS = [("V1", "vaccine"), ("V2", "vaccine"), ("P1", "placebo"), ("P2", "placebo")]
LIBRARIES = [(d + "_" + v, d, arm, v) for d, arm in DONORS for v in ("day0", "day28")]
FLAT = [100] * 8
COUNTS = {"C%d" % i: FLAT for i in range(1, 6)}
COUNTS["UP"] = [100, 400, 100, 800, 100, 120, 100, 90]
COUNTS["DOWN"] = [100, 25, 100, 50, 100, 110, 100, 95]


def finish(ok, message):
    with open(EVIDENCE, "w") as handle:
        json.dump({"status": "passed" if ok else "failed", "message": message}, handle)
    print(message)
    sys.exit(0 if ok else 1)


def analyse(order):
    """log2fc by gene from the real step 02, the metadata rows (samples_used.tsv) in `order`."""
    with tempfile.TemporaryDirectory() as work:
        samples, counts, out = [os.path.join(work, n) for n in ("samples_used.tsv", "counts.tsv", "de.tsv")]
        with open(samples, "w") as handle:
            handle.write("sample_id\\tdonor\\tarm\\tvisit\\n")
            for sample, donor, arm, visit in order:
                handle.write("\\t".join((sample, donor, arm, visit)) + "\\n")
        with open(counts, "w") as handle:  # the matrix keeps one column order whatever the metadata's
            handle.write("gene\\t" + "\\t".join(l[0] for l in LIBRARIES) + "\\n")
            for gene in sorted(COUNTS):
                handle.write(gene + "\\t" + "\\t".join(str(n) for n in COUNTS[gene]) + "\\n")
        spec = importlib.util.spec_from_file_location("step02", STEP)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.SAMPLES, module.COUNTS, module.OUT = samples, counts, out
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                module.main()
        except Exception as error:
            finish(False, "step 02 raised {}: {} on the known-answer dataset".format(type(error).__name__, error))
        with open(out) as handle:
            return dict((r[0], float(r[1])) for r in (l.rstrip("\\n").split("\\t") for l in handle.readlines()[1:]))
'''

CONTRAST_DIRECTION = PRELUDE.replace("@NAME@", "contrast_direction") + '''

fc = analyse(LIBRARIES)
finish(fc["UP"] > 0 > fc["DOWN"], "contrast direction: UP (higher in vaccine at day 28) has log2fc {:+.2f} and DOWN "
       "{:+.2f}; positive must mean higher in vaccine than placebo".format(fc["UP"], fc["DOWN"]))
'''

NORMALIZATION = PRELUDE.replace("@NAME@", "normalization") + '''

fc = analyse(LIBRARIES)
worst = max(abs(fc[g]) for g in fc if g.startswith("C"))
finish(worst < 0.05, "normalization: unchanged genes reach |log2fc| {:.2f}, expected 0 under median-of-ratios size "
                     "factors".format(worst))
'''

SHUFFLE = PRELUDE.replace("@NAME@", "shuffle") + '''

keyed, shuffled = analyse(LIBRARIES), analyse(LIBRARIES[1:] + LIBRARIES[:1])
moved = sorted(g for g in keyed if abs(keyed[g] - shuffled[g]) > 1e-9)
finish(not moved, "shuffle invariance: reordering the metadata rows changed log2fc of {} of {} genes ({})".format(
    len(moved), len(keyed), ", ".join(moved[:3]) or "none"))
'''

# The contract checks run through data_contract_check.py; this is the command the plan names for each.
CONTRACT_RUNNER = """import subprocess
import sys

sys.exit(subprocess.call([sys.executable, {checker!r}, "--contract", {contract!r}, "--root", ".",
                          "--result-json", {evidence!r}], stdout=subprocess.DEVNULL))
"""
