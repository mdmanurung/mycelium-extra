"""Build a disposable scratch project for one manuscript-audit `verify` scenario.

    python3 tests/e2e/manuscript_scenario.py --scenario S1 --dest /tmp/mx-ms-S1 [--init]

Stdlib only, Python 3.6 grammar. Synthetic data only. The project is a fresh git repository with:

- `analysis/paper/data/counts.tsv`, a synthetic count table, and `data/README.md`, its manifest;
- `analysis/paper/scripts/01_make_source.py`, a deterministic producer that writes
  `outputs/freq.tsv` and `figures/source_data/Fig1a.tsv` (in S2 it omits the `fraction` column
  from the figure source data, a declared plotting column);
- `analysis/paper/scripts/plot_fig1.py`, the figure script the contract names (never run here);
- `analysis/paper/config/manuscript_checks.json`, the contract the researcher approves;
- `analysis/paper/tests/manuscript_audit.py`, a byte copy of skills/manuscript-audit's checker, so the
  binding's `test_paths` are pinned inside the repository;
- `PLAN.md`, the plan the agent presents verbatim: row 1 the producer, row 2 the checker, and the
  `M-FIG-001` validation binding; and `PROMPTS.md`, the turns of the native runbook.

With --init the gate is turned on with skills/init's defaults (gated_paths analysis/** nbs/**) and
committed. Without it the native runbook asks the host to run init, as a researcher would.

Scenarios (docs/design/2026-10-26-manuscript-native-verify.md): S1 pass, S2 fail, S3 not run (only
row 1 is run), S4 changed (the contract is edited after approval; simulated only), S5 unattributable
(the check passes, then its evidence file is rewritten outside any attempt; simulated only). The
project differs only in S2; the other scenarios differ in what is run.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
CHECKER = os.path.join(REPO, "skills", "manuscript-audit", "scripts", "manuscript_audit.py")
INIT = os.path.join(REPO, "skills", "init", "scripts", "gate_init.py")

SCENARIOS = ("S1", "S2", "S3", "S4", "S5")
NATIVE = ("S1", "S2", "S3")  # the scenarios run on a real host; S4 and S5 are simulated only
BASE = "analysis/paper"
PRODUCER = BASE + "/scripts/01_make_source.py"
PLOT = BASE + "/scripts/plot_fig1.py"
CONTRACT = BASE + "/config/manuscript_checks.json"
CHECK_COPY = BASE + "/tests/manuscript_audit.py"
EVIDENCE = BASE + "/outputs/manuscript_audit.json"
FREQ = BASE + "/outputs/freq.tsv"
FIG = BASE + "/figures/source_data/Fig1a.tsv"
COUNTS = BASE + "/data/counts.tsv"
MANIFEST = BASE + "/data/README.md"
PRODUCER_CMD = "python3 " + PRODUCER
CHECK_ARGV = ["python3", CHECK_COPY, "--root", BASE, "--config", "config/manuscript_checks.json",
              "--result-json", "outputs/manuscript_audit.json"]
CHECK_CMD = " ".join(CHECK_ARGV)
BINDING_ID = "M-FIG-001"

COUNTS_TSV = ("sample_id\tcondition\tcell_type\tcell_count\ttotal_count\n"
              "S1\tA\tT\t25\t100\n"
              "S2\tB\tT\t50\t100\n"
              "S3\tA\tT\t75\t100\n")

MANIFEST_MD = ("# Data manifest (synthetic)\n\n"
               "`counts.tsv`: synthetic cell counts for three samples, written by\n"
               "tests/e2e/manuscript_scenario.py. No patient or donor data.\n")

PRODUCER_PY = '''"""Make the Figure 1a source data and the frequency table from data/counts.tsv (synthetic)."""
import csv
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OMIT_FRACTION_IN_FIGURE = {omit}  # S2 sets this: the figure source data then lacks a plotted column

with open(os.path.join(HERE, "data", "counts.tsv")) as handle:
    rows = list(csv.DictReader(handle, delimiter="\\t"))

for row in rows:
    row["fraction"] = repr(int(row["cell_count"]) / int(row["total_count"]))

os.makedirs(os.path.join(HERE, "outputs"), exist_ok=True)
os.makedirs(os.path.join(HERE, "figures", "source_data"), exist_ok=True)
with open(os.path.join(HERE, "outputs", "freq.tsv"), "w") as handle:
    handle.write("sample_id\\tcell_type\\tcell_count\\ttotal_count\\tfraction\\n")
    for row in rows:
        handle.write("\\t".join(row[k] for k in ("sample_id", "cell_type", "cell_count", "total_count", "fraction")) + "\\n")
figure = ["sample_id", "condition"] + ([] if OMIT_FRACTION_IN_FIGURE else ["fraction"])
with open(os.path.join(HERE, "figures", "source_data", "Fig1a.tsv"), "w") as handle:
    handle.write("\\t".join(figure) + "\\n")
    for row in rows:
        handle.write("\\t".join(row[k] for k in figure) + "\\n")
print("wrote outputs/freq.tsv and figures/source_data/Fig1a.tsv ({{}} rows)".format(len(rows)))
'''

PLOT_PY = '''"""Figure 1a: fraction per sample_id, grouped by condition (synthetic). Not run by the scenarios."""
import csv
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(HERE, "figures", "source_data", "Fig1a.tsv")) as handle:
    for row in csv.DictReader(handle, delimiter="\\t"):
        print(row["condition"], row["sample_id"], row["fraction"])
'''

CONTRACT_JSON = {
    "schema": "mycelium-extra.manuscript_checks.v1",
    "data_manifest": "data/README.md",
    "figures": [{"id": "Fig1a", "script": "scripts/plot_fig1.py", "source_data": "figures/source_data/Fig1a.tsv",
                 "required_columns": ["sample_id", "condition", "fraction"], "outputs": []}],
    "tables": [{"id": "freq", "file": "outputs/freq.tsv", "key_columns": ["sample_id", "cell_type"],
                "nonnegative_integer_columns": ["cell_count", "total_count"],
                "finite_numeric_columns": ["fraction"],
                "ratio_invariant": {"numerator": "cell_count", "denominator": "total_count", "fraction": "fraction"}}],
}


def binding():
    return {"id": BINDING_ID, "plan_row": "2", "required": True, "defined_by": "researcher-approved",
            "test_paths": [CHECK_COPY, CONTRACT], "invocation": CHECK_ARGV, "evidence_path": EVIDENCE}


def plan_text():
    """The plan the agent presents verbatim (identical in every scenario, so the approval is comparable)."""
    block = "<!-- validation-bindings {} -->".format(json.dumps({"version": 1, "checks": [binding()]}))
    return "\n".join([
        "**Objective.** Regenerate the Figure 1a source data and the cell-type frequency table from the synthetic "
        "counts, then check them against the researcher-approved manuscript contract `{}` (declared plotting "
        "columns sample_id, condition, fraction; key sample_id + cell_type unique; fraction = cell_count / "
        "total_count).".format(CONTRACT),
        "",
        "Inputs: {} {}".format(COUNTS, CONTRACT),
        "Outputs: {} {} {}".format(FREQ, FIG, EVIDENCE),
        "",
        "| # | Step | Choice | Source | Validation |",
        "|---|---|---|---|---|",
        "| 1 | run `{}` | fraction = cell_count / total_count, no filtering | user | writes freq.tsv and "
        "Fig1a.tsv, 3 rows each |".format(PRODUCER_CMD),
        "| 2 | run `{}` | contract as approved; read-only | user | `{}`: exit 0 and status pass |".format(
            CHECK_CMD, BINDING_ID),
        "",
        block,
        "",
        "Plan status: READY",
        "",
    ])


def prompts(scenario):
    """The host turns of the native runbook for `scenario` (S1-S3)."""
    run = ("Run exactly these commands from the repository root, one Bash call each, in this order, and nothing "
           "else. Do not edit, create or delete any file. Stop after the last one and report its exit code.\n\n")
    if scenario == "S3":
        steps = "1. `{}`\n".format(PRODUCER_CMD)
    else:
        steps = "1. `{}`\n2. `{}`\n".format(PRODUCER_CMD, CHECK_CMD)
    return "\n".join([
        "# Native runbook prompts for scenario {}".format(scenario),
        "",
        "Turn 1 (present the plan; the Stop hook then prints the plan card and `approve plan <hash>`):",
        "",
        "```text",
        "Present the plan in PLAN.md verbatim as your whole reply, including the HTML comment, with no tool "
        "calls and no other text.",
        "```",
        "",
        "Turn 2 (the researcher, after reading the card and the contract): type exactly `approve plan <hash>` "
        "with the hash the card printed.",
        "",
        "Turn 3:",
        "",
        "```text",
        run + steps.rstrip(),
        "```",
        "",
    ])


def write(root, rel, text, mtime=None):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def write_project(root, scenario):
    """Write the scenario's files under `root` (which may exist); files are dated an hour back, so the
    scripts and contract predate the plan as they would in a real project."""
    if scenario not in SCENARIOS:
        raise ValueError("unknown scenario {!r}; one of {}".format(scenario, ", ".join(SCENARIOS)))
    old = time.time() - 3600
    write(root, COUNTS, COUNTS_TSV, old)
    write(root, MANIFEST, MANIFEST_MD, old)
    write(root, PRODUCER, PRODUCER_PY.format(omit="True" if scenario == "S2" else "False"), old)
    write(root, PLOT, PLOT_PY, old)
    write(root, CONTRACT, json.dumps(CONTRACT_JSON, indent=2) + "\n", old)
    os.makedirs(os.path.dirname(os.path.join(root, CHECK_COPY)), exist_ok=True)
    shutil.copyfile(CHECKER, os.path.join(root, CHECK_COPY))
    os.utime(os.path.join(root, CHECK_COPY), (old, old))
    write(root, "PLAN.md", plan_text(), old)
    if scenario in NATIVE:
        write(root, "PROMPTS.md", prompts(scenario), old)
    write(root, ".gitignore", "__pycache__/\n", old)
    return root


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def manifest(root):
    """{relative path: sha256} of the generated files, for the grader to confirm the bundle's project."""
    out = {}
    for rel in (COUNTS, MANIFEST, PRODUCER, PLOT, CONTRACT, CHECK_COPY, "PLAN.md"):
        out[rel] = sha256(os.path.join(root, rel))
    return out


def git(root, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="Scenario", GIT_AUTHOR_EMAIL="scenario@example.org",
               GIT_COMMITTER_NAME="Scenario", GIT_COMMITTER_EMAIL="scenario@example.org")
    subprocess.check_call(("git",) + args, cwd=root, env=env, stdout=subprocess.DEVNULL)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="manuscript_scenario")
    parser.add_argument("--scenario", required=True, choices=SCENARIOS)
    parser.add_argument("--dest", required=True, help="a new directory for the scratch project")
    parser.add_argument("--init", action="store_true", help="turn the gate on with skills/init's defaults")
    args = parser.parse_args(argv)
    dest = os.path.abspath(args.dest)
    if os.path.exists(dest) and os.listdir(dest):
        parser.exit(1, "refusing to write into non-empty {}\n".format(dest))
    write_project(dest, args.scenario)
    write(dest, "SCENARIO.json", json.dumps({"scenario": args.scenario, "files": manifest(dest),
                                             "plan_sha256": sha256(os.path.join(dest, "PLAN.md")),
                                             "producer_cmd": PRODUCER_CMD, "check_cmd": CHECK_CMD,
                                             "binding_id": BINDING_ID, "evidence_path": EVIDENCE},
                                            indent=2, sort_keys=True) + "\n")
    git(dest, "init", "-q")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "manuscript scenario {} (synthetic)".format(args.scenario))
    if args.init:
        subprocess.check_call([sys.executable, INIT, "--root", dest])
        git(dest, "add", "-A")
        git(dest, "commit", "-q", "-m", "mycelium-extra init")
    print(dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
