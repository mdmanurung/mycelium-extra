"""The planted-defect catalog (docs/design/c1-fixture-project.md, section 8).

Each defect applies one mutation to a fresh baseline project and drives the chain to the check
that should catch it. `run(project)` returns an outcome dict, and the test compares it with
`expect`: every key except `messages` must be equal, and every string in `messages` must appear
in outcome["text"]. A known miss expects what a chain that reports success produces, plus the
evidence that its results are wrong.

Stdlib only, Python 3.6 grammar.
"""

import base64
import json
import os
import re
import time

import harness

A = harness.ANALYSIS
METADATA = "data/processed/vaccine-cohort/sample_metadata.tsv"
COUNTS = "data/processed/vaccine-cohort/counts.tsv"
PAIRED = A + "/scripts/02_paired_test.py"
CONFORMS = "Verify status: CONFORMS"
DENY = "deny"


# Tasks whose fixtures C1 leaves for them to add (design section 8.6).
LATER = ["D1", "D2", "D4", "C3", "D6", "E1", "E4", "E5", "D10", "D11", "D12"]


class Defect(object):
    def __init__(self, id, layer, caught_by, covers, run, expect, known_miss=False, xfail_task=None):
        self.id, self.layer, self.caught_by, self.covers = id, layer, caught_by, covers
        self.run, self.expect, self.known_miss, self.xfail_task = run, expect, known_miss, xfail_task


DEFECTS = []


def defect(id, layer, caught_by, covers, expect, known_miss=False, xfail_task=None):
    def register(run):
        DEFECTS.append(Defect(id, layer, caught_by, covers, run, expect, known_miss, xfail_task))
        return run
    return register


# ---------------------------------------------------------------- helpers

def edit_rows(change):
    """A text edit for a TSV: change(header, rows) edits the list of row lists in place."""
    def apply(text):
        lines = text.rstrip("\n").split("\n")
        header, rows = lines[0].split("\t"), [line.split("\t") for line in lines[1:]]
        change(header, rows)
        return "\n".join(["\t".join(header)] + ["\t".join(row) for row in rows]) + "\n"
    return apply


def set_cells(match, column, value):
    """Set `column` to `value` in every metadata row for which match(row dict) holds."""
    def change(header, rows):
        for row in rows:
            if match(dict(zip(header, row))):
                row[header.index(column)] = value
    return edit_rows(change)


def drop_rows(match):
    def change(header, rows):
        rows[:] = [row for row in rows if not match(dict(zip(header, row)))]
    return edit_rows(change)


def contract(change=None):
    """The baseline contract, after change(contract dict)."""
    data = json.loads(harness.contract_text())
    if change:
        change(data)
    return json.dumps(data, indent=1)


def check(p, text=None):
    code, out, err = p.data_contract(text or contract())
    return {"code": code, "text": out + err}


def gate(result):
    decision = DENY if result.denied else "silent" if result.pre is None else "notice"
    return {"decision": decision, "text": result.reason or json.dumps(result.pre)}


def results(p):
    """The hit list of de_results.tsv, compared with the simulated truth."""
    truth = harness.expected("truth.json")
    with open(p.path(A, "outputs", "de_results.tsv"), encoding="utf-8") as handle:
        rows = [line.rstrip("\n").split("\t") for line in handle][1:]
    hits = sorted(gene for gene, _, _, padj in rows if float(padj) < 0.05)
    signs = {"+" if float(fc) > 0 else "-" for gene, fc, _, padj in rows if float(padj) < 0.05}
    return {"hits": hits, "hits_are_truth": hits == sorted(truth["true_genes"]),
            "hit_sign": "".join(sorted(signs))}


def whole_chain(p):
    """Commit the mutation, check the contract, run the plan, and verify: the known-miss path."""
    p.commit("mutation")
    code, out, err = p.data_contract(contract())
    digest = p.run_plan()[0]
    vcode, report, verr = p.verify("report", digest)
    outcome = {"contract": code, "status": harness.status_line(report), "text": out + err + report + verr}
    outcome.update(results(p))
    return outcome


def replace(old, new):
    return lambda text: text.replace(old, new)


# ---------------------------------------------------------------- 8.1 data layer

@defect("DC-01", "data", "data-contract-check", ["Invented columns or levels"],
        {"code": 2, "messages": ["required columns are absent", "missing: seq_batch"]})
def dc01(p):
    def change(c):
        c["checks"][0]["columns"] = ["seq_batch" if x == "run_id" else x for x in c["checks"][0]["columns"]]
        c["checks"][4]["batch"] = "seq_batch"
    return check(p, contract(change))


@defect("DC-02", "data", "data-contract-check", ["Invented columns or levels", "Reversed contrast"],
        {"code": 2, "messages": ["required levels of 'arm' are absent after filtering"]})
def dc02(p):
    p.edit(METADATA, set_cells(lambda r: r["arm"] == "vaccine", "arm", "Vaccine"))
    return check(p)


@defect("DC-03", "data", "data-contract-check", ["Silent row loss"],
        {"code": 2, "messages": ["row count differs from the plan", "expected: 24", "observed: 22",
                                 "groups with fewer distinct donor than required", "observed: placebo=5"]})
def dc03(p):
    p.edit(METADATA, drop_rows(lambda r: r["donor"] == "D09"))
    return check(p)


@defect("DC-04", "data", "data-contract-check", ["Join duplication", "Unit of replication"],
        {"code": 2, "messages": ["a unit appears more than once in the same arm x visit cell"]})
def dc04(p):
    p.edit(METADATA, set_cells(lambda r: r["sample_id"] == "D03_day28_rerun", "preferred_acquisition", "TRUE"))
    return check(p)


@defect("DC-05", "data", "data-contract-check", ["Unit of replication"],
        {"code": 2, "messages": ["units are missing a level of 'visit'", "D11 lacks day28"]})
def dc05(p):
    p.edit(METADATA, drop_rows(lambda r: r["sample_id"] == "D11_day28"))

    def change(c):
        c["checks"][1]["rows"] = 23
    return check(p, contract(change))


@defect("DC-06", "data", "data-contract-check", ["Batch versus biology"],
        {"code": 2, "messages": ["'arm' is fully nested in 'run_id'"]})
def dc06(p):
    placebo = {"D07": "R2", "D08": "R2", "D09": "R2", "D10": "R3", "D11": "R3", "D12": "R3"}

    def change(header, rows):
        for row in rows:
            r = dict(zip(header, row))
            row[header.index("run_id")] = "R1" if r["arm"] == "vaccine" else placebo[r["donor"]]
    p.edit(METADATA, edit_rows(change))
    return check(p)


@defect("DC-07", "data", "data-contract-check", ["Cohort and exclusions"],
        {"code": 2, "messages": ["'run_id' has missing values", "rows have a missing value"]})
def dc07(p):
    p.edit(METADATA, set_cells(lambda r: r["sample_id"] == "D05_day0", "run_id", "NA"))
    return check(p)


@defect("DC-08", "data", "none", ["Reversed contrast"], known_miss=True,
        expect={"contract": 0, "status": CONFORMS, "hits_are_truth": True, "hit_sign": "-"})
def dc08(p):
    p.edit(PAIRED, replace("observed = sum(diff[:n_v]) / n_v - sum(diff[n_v:]) / n_p",
                           "observed = sum(diff[n_v:]) / n_p - sum(diff[:n_v]) / n_v"))
    return whole_chain(p)


@defect("DC-09", "data", "none", ["Sample label swap"], known_miss=True,
        expect={"contract": 0, "status": CONFORMS, "hits_are_truth": False})
def dc09(p):
    # Column i of the counts matrix is taken to be the i-th sample of samples_used.tsv.
    p.edit(PAIRED, replace("column = {name: i for i, name in enumerate(count_header)}",
                           "column = {name: i + 1 for i, name in enumerate(r[0] for r in rows)}"))
    return whole_chain(p)


@defect("DC-10", "data", "none", ["Gene symbol corruption"], known_miss=True,
        expect={"contract": 0, "status": CONFORMS, "hits_are_truth": True, "date_symbols": 2})
def dc10(p):
    p.edit(COUNTS, lambda text: text.replace("\nMARCHF1\t", "\n1-Mar\t").replace("\nSEPTIN7\t", "\n7-Sep\t"))
    outcome = whole_chain(p)
    with open(p.path(A, "outputs", "de_results.tsv"), encoding="utf-8") as handle:
        outcome["date_symbols"] = sum(line.split("\t")[0] in ("1-Mar", "7-Sep") for line in handle)
    return outcome


@defect("DC-11", "data", "none", ["Normalization and transformation"], known_miss=True,
        expect={"contract": 0, "status": CONFORMS, "hits_are_truth": False, "cpm_false_positives": True})
def dc11(p):
    p.edit(PAIRED, replace("    sf = size_factors(counts, samples, genes)\n",
                           "    sf = {s: sum(counts[g][s] for g in genes) / 1e6 for s in samples}\n"))
    outcome = whole_chain(p)
    expected = harness.expected("truth.json")["selection"]["total_count_cpm"]["false_positive_genes"]
    outcome["cpm_false_positives"] = len(expected) >= 3 and set(expected) <= set(outcome["hits"])
    return outcome


# ---------------------------------------------------------------- 8.2 gate layer

@defect("G-01", "gate", "approval gate", ["Silent scope growth"],
        {"decision": DENY, "messages": ["blocked because no active approved plan covers this run",
                                        "04_extra_plot.py"]})
def g01(p):
    p.approve(harness.plan_text())
    return gate(p.agent_bash("python3 " + A + "/scripts/04_extra_plot.py"))


@defect("G-02", "gate", "approval gate", ["Input and matrix state"],
        {"decision": DENY, "names_plan": True, "messages": ["changed after the plan was written", METADATA]})
def g02(p):
    digest = p.approve(harness.plan_text())[0]
    p.edit(METADATA, lambda text: text + "D13_day0\tD13\tplacebo\tday0\tR1\tL1\tTRUE\t8.0\n")
    outcome = gate(p.run_step(harness.SCRIPTS[0]))
    outcome["names_plan"] = "inputs pinned by plan {} changed".format(digest) in outcome["text"]
    return outcome


@defect("G-03", "gate", "approval gate", ["Explore results reported"],
        {"decision": DENY, "messages": ["the exploratory-run prefix works only after the user"]})
def g03(p):
    p.approve(harness.plan_text())
    return gate(p.agent_bash("MYCELIUM_EXTRA_EXPLORE=1 python3 " + A + "/scripts/04_extra_plot.py"))


@defect("G-04", "gate", "approval gate", ["tool: gate state"],
        {"decision": DENY, "messages": ["appears to modify .mycelium-extra/"]})
def g04(p):
    return gate(p.agent_bash("echo '{}' > .mycelium-extra/approvals/x.json"))


@defect("G-05", "gate", "approval gate", ["tool: approval"], {"offered": False})
def g05(p):
    text = "\n".join(line for line in harness.plan_text().splitlines() if not line.startswith("Plan status:"))
    notice = p.hook(p.events.get("Stop", "stop"), {"last_assistant_message": text, "stop_hook_active": False})
    message = (notice or {}).get("systemMessage", "")
    return {"offered": "approve plan" in message, "text": message}


@defect("G-06", "gate", "approval gate", ["Silent scope growth"],
        {"decision": DENY, "messages": ["no active approved plan covers this run", "sbatch"]})
def g06(p):
    p.approve(harness.plan_text())
    return gate(p.agent_bash("sbatch " + A + "/run.sh", effect=lambda _: "Submitted batch job 4242"))


@defect("G-07", "gate", "approval gate", ["tool: approval expiry"],
        {"decision": DENY, "messages": ["no active approved plan covers this run",
                                        "Active approved plans (last 24 h): none."]})
def g07(p):
    digest = p.approve(harness.plan_text())[0]
    path = p.path(".mycelium-extra", "approvals", digest + ".json")
    record = p.approval(digest)
    record["approved_at"] -= 25 * 3600
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(record, handle)
    return gate(p.run_step(harness.SCRIPTS[0]))


# ---------------------------------------------------------------- 8.3 verify layer

GAPS = "Verify status: CONFORMS_WITH_GAPS"
BLOCKED = "Verify status: DOES_NOT_CONFORM"
DE = A + "/outputs/de_results.tsv"
SUMMARY = A + "/outputs/summary.tsv"
EXTRA = A + "/scripts/04_extra_plot.py"
EXPLORE = "MYCELIUM_EXTRA_EXPLORE=1 "


def plan(rows=None, outputs=None, change=None):
    """The baseline plan with its table rows replaced by `rows`, its Outputs: line replaced by
    `outputs` ("" drops the line), and then change(text)."""
    lines = []
    for line in harness.plan_text().splitlines():
        if rows is not None and line[:4] in ("| 1 ", "| 2 ", "| 3 "):
            if line.startswith("| 1 "):
                lines.extend(rows)
            continue
        if outputs is not None and line.startswith("Outputs:"):
            if outputs:
                lines.append("Outputs: " + outputs)
            continue
        lines.append(line)
    text = "\n".join(lines) + "\n"
    return change(text) if change else text


def row(n, command, choice="as the script states", source="repo: analysis/vaccine-response/VACCINE_RESPONSE.md",
        validation="exit 0"):
    return "| {} | run `{}` | {} | {} | {} |".format(n, command, choice, source, validation)


def report(p, digest):
    code, out, err = p.verify("report", digest)
    return {"code": code, "status": harness.status_line(out), "text": out + err}


def baseline(p, text=None, scripts=harness.SCRIPTS):
    digest = p.run_plan(text, scripts)[0]
    return digest, report(p, digest)


def row_status(text, path):
    found = [line for line in text.splitlines() if line.startswith("| `{}` |".format(path))]
    return found[0].split("|")[2].strip() if found else None


def stale_mtime(p, rel, epoch):
    os.utime(p.path(rel), (epoch, epoch))


@defect("V-01", "verify", "verify", ["Swallowed errors"],
        {"status": BLOCKED, "messages": ["`{}` failed (exit 1)".format(PAIRED), "Output `{}` does not exist".format(DE)]})
def v01(p):
    p.edit(PAIRED, replace("def main():\n", "def main():\n    raise SystemExit('counts unreadable')\n"))
    p.commit("02 fails")
    return baseline(p)[1]


def crash_after(rows):
    """02 writes the header and `rows` gene rows of de_results.tsv, then dies; rows=0: before writing."""
    def change(text):
        if not rows:
            return text.replace("def main():\n", "def main():\n    raise SystemExit('worker lost')\n")
        text = text.replace("    padj = bh(pvalues, genes)\n",
                            "    padj = bh(pvalues, genes)\n    genes = genes[:{}]\n".format(rows))
        return text.replace("    print(\"{} libraries", "    raise SystemExit('worker lost')\n    print(\"{} libraries")
    return change


def swallowed(p, rows, scripts):
    p.edit(PAIRED, crash_after(rows))
    p.commit("02 dies")
    digest = p.approve(harness.plan_text())[0]
    results = []
    for script in scripts:
        results.append(p.agent_bash("python3 {} || true".format(PAIRED)) if script == PAIRED else p.run_step(script))
    p.space_outputs([(harness.out_of(s), r.receipts[0]) for s, r in zip(scripts, results)
                     if r.receipts and os.path.isfile(p.path(harness.out_of(s)))])
    p.lineage()
    outcome = report(p, digest)
    outcome["row"] = row_status(outcome["text"], PAIRED)
    return outcome


@defect("V-02a", "verify", "verify", ["Swallowed errors"],
        {"status": GAPS, "row": "ran (exit 0 from hook event)", "messages": ["Output `{}` does not exist".format(DE)]})
def v02a(p):
    return swallowed(p, 0, harness.SCRIPTS[:2])


@defect("V-02b", "verify", "none", ["Swallowed errors"], known_miss=True,
        expect={"status": CONFORMS, "de_rows": 10})
def v02b(p):
    outcome = swallowed(p, 10, harness.SCRIPTS)
    with open(p.path(DE), encoding="utf-8") as handle:
        outcome["de_rows"] = len(handle.readlines()) - 1
    return outcome


@defect("V-03", "verify", "verify", ["Stale evidence as current"],
        {"status": BLOCKED, "messages": ["`{}` was edited after its run".format(PAIRED)]})
def v03(p):
    digest = p.run_plan()[0]
    p.edit(PAIRED, lambda text: text + "# tidied\n")
    return report(p, digest)


@defect("V-04", "verify", "verify", ["Stale evidence as current"],
        {"status": BLOCKED, "messages": ["Output `{}` was written".format(SUMMARY), "before the plan was approved",
                                         "`{}`: no run under this plan was recorded".format(harness.SCRIPTS[2])]})
def v04(p):
    harness.copy_summary(p)
    stale_mtime(p, SUMMARY, time.time() - 3600)
    return baseline(p, scripts=harness.SCRIPTS[:2])[1]


TOP = A + "/outputs/top_genes.tsv"


@defect("V-05", "verify", "verify", ["Number transcription"],
        {"status": GAPS, "messages": ["Output `{}`".format(TOP), "is not tied to any recorded run"]})
def v05(p):
    text = plan(change=lambda t: t.replace("outputs/summary.tsv\n", "outputs/summary.tsv " + TOP + "\n"))
    digest = p.run_plan(text)[0]
    inline = p.agent_bash("python3 -c \"open('{}', 'w').write('gene\\nIFI27\\n')\"".format(TOP))
    if inline.denied:
        return gate(inline)
    stale_mtime(p, TOP, p.receipts()[-1]["ts"] + 2 * harness.TOLERANCE)
    return report(p, digest)


@defect("V-06", "verify", "verify", ["Input and matrix state"],
        {"status": BLOCKED, "messages": ["Input `{}` changed since the approval".format(COUNTS)]})
def v06(p):
    digest = p.run_plan()[0]
    p.edit(COUNTS, lambda text: text.replace("\t", "\t1", 1))
    return report(p, digest)


@defect("V-07", "verify", "verify", ["tool: verify"],
        {"status": GAPS, "messages": ["`{}`: no run under this plan was recorded".format(harness.SCRIPTS[2])]})
def v07(p):
    return baseline(p, scripts=harness.SCRIPTS[:2])[1]


def allow_explore(p):
    p.hook(p.events.get("UserPromptSubmit", "prompt"), {"prompt": "allow explore"})


@defect("V-08", "verify", "verify", ["Explore results reported"],
        {"status": GAPS, "messages": ["Explore run in the analysis folder", "04_extra_plot"]})
def v08(p):
    digest = p.run_plan()[0]
    allow_explore(p)
    p.agent_bash(EXPLORE + "python3 " + EXTRA)
    return report(p, digest)


@defect("V-09", "verify", "verify", ["Explore results reported"],
        {"status": GAPS, "messages": ["Output `{}` was likely written by".format(DE), "explore"]})
def v09(p):
    digest = p.run_plan()[0]
    allow_explore(p)
    result = p.agent_bash(EXPLORE + "python3 " + PAIRED)
    p.space_outputs([(DE, result.receipts[0])])
    return report(p, digest)


@defect("V-10", "verify", "verify", ["Retry until significant"],
        {"status": GAPS, "messages": ["Mycelium's lineage saw `/tmp/scratch/refit.py`"]})
def v10(p):
    digest = p.run_plan()[0]
    p.lineage(p.runs + [(time.time(), "python3 /tmp/scratch/refit.py", "/tmp/scratch/refit.py")])
    return report(p, digest)


@defect("V-11", "verify", "verify", ["tool: verify"],
        {"status": GAPS, "messages": ["was untracked when it ran"]})
def v11(p):
    copy = PAIRED.replace("02_paired", "02b_paired")
    with open(p.path(PAIRED), encoding="utf-8") as src, open(p.path(copy), "w", encoding="utf-8") as dst:
        dst.write(src.read())
    text = plan(change=lambda t: t.replace("02_paired_test.py", "02b_paired_test.py"))
    return baseline(p, text, [harness.SCRIPTS[0], copy, harness.SCRIPTS[2]])[1]


SBATCH = "sbatch " + A + "/run_all.sbatch"


def sbatch_effect(p):
    for script in harness.SCRIPTS:
        if script.endswith(".R"):
            harness.copy_summary(p)
        else:
            p.shell("python3 " + script)
    return "Submitted batch job 4242\n"


@defect("V-12", "verify", "verify", ["tool: verify"],
        {"status": BLOCKED, "messages": ["Slurm job 4242 ended FAILED"]})
def v12(p):
    digest = p.approve(plan([row(1, SBATCH)]))[0]
    p.agent_bash(SBATCH, effect=sbatch_effect)
    now = time.time()
    p.write_fakes(sacct="4242|FAILED|1:0|{}|{}".format(time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now - 60)),
                                                        time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now))))
    return report(p, digest)


SNAKEMAKE = "snakemake -s " + A + "/Snakefile --cores 1"
RULES = [("step01_select_samples", "scripts/01_select_samples.py", "outputs/samples_used.tsv"),
         ("step02_paired_test", "scripts/02_paired_test.py", "outputs/de_results.tsv"),
         ("step03_summary", "scripts/03_summary.R", "outputs/summary.tsv")]


def snakemake_effect(incomplete):
    def effect(p):
        for rule, script, output in RULES:
            start = time.time()
            if script.endswith(".R"):
                harness.copy_summary(p)
                shell = "Rscript {} > logs/03_summary.log 2>&1".format(script)
            else:
                p.shell("python3 {}/{}".format(A, script))
                shell = "python -u {} > logs/{}.log 2>&1".format(script, rule)
            p.snakemake_record(output, rule, [script], shell, incomplete=rule == incomplete, start=start,
                               workdir=A)
        return ""
    return effect


@defect("V-13", "verify", "verify", ["tool: verify"],
        {"status": BLOCKED, "messages": ["Snakemake marks rule `step02_paired_test` incomplete"]})
def v13(p):
    # The steps stay in the plan table: verify checks a rule's record for the planned step that ran
    # inside the wrapper, not for the Snakefile, which has its own direct receipt.
    digest = p.approve(plan(change=lambda t: t.replace("\n\nPlan status", "\n" + row(
        4, SNAKEMAKE, source="repo: " + A + "/Snakefile") + "\n\nPlan status")))[0]
    p.agent_bash(SNAKEMAKE, effect=snakemake_effect("step02_paired_test"))
    return report(p, digest)


@defect("V-14", "verify", "verify", ["tool: verify"],
        {"status": BLOCKED, "messages": ["1 scilintr finding(s) remain in Python code"]})
def v14(p):
    p.write_fakes(scilintr="{}:60:5: [silent-coercion] int() on a count column\n".format(PAIRED), scilintr_code=1)
    return baseline(p)[1]


@defect("V-15", "verify", "verify", ["tool: verify"],
        {"status": GAPS, "messages": ["scilintr (Python) not checked", "not found"]})
def v15(p):
    os.remove(os.path.join(p.bin, "scilintr"))
    return baseline(p)[1]


@defect("V-16", "verify", "verify", ["Outputs and reporting"],
        {"status": GAPS, "messages": ["The plan has no `Outputs:` line"]})
def v16(p):
    return baseline(p, plan(outputs=""))[1]


@defect("V-17", "verify", "verify", ["Version-specific behaviour"],
        {"status": GAPS, "messages": ["Conda env `vaccine-de`", "was not found"]})
def v17(p):
    digest = p.approve(harness.plan_text())[0]
    results = []
    for script in harness.SCRIPTS:
        tool = "Rscript" if script.endswith(".R") else "python3"
        effect = (lambda q, s=script: harness.copy_summary(q) if s.endswith(".R") else q.shell("python3 " + s)[1])
        results.append(p.agent_bash("conda run -n vaccine-de {} {}".format(tool, script), effect=effect))
    p.space_outputs([(harness.out_of(s), r.receipts[0]) for s, r in zip(harness.SCRIPTS, results) if r.receipts])
    p.lineage()
    return report(p, digest)


VOLCANO_PLAN = """**Objective.** Volcano data for the vaccine-response results.

Inputs: analysis/vaccine-response/outputs/de_results.tsv
Outputs: analysis/vaccine-response/outputs/volcano.tsv

| # | Step | Choice | Source | Validation |
|---|---|---|---|---|
| 1 | run `analysis/vaccine-response/scripts/04_extra_plot.py` | -log10 p against log2FC | user | one row per gene |

Plan status: READY
"""


@defect("V-18", "verify", "verify", ["Silent scope growth"],
        {"status": GAPS, "messages": ["`{}` ran since the approval but is not in the plan table".format(EXTRA),
                                      "Run under another plan"]})
def v18(p):
    digest = p.run_plan()[0]
    p.approve(VOLCANO_PLAN)
    p.agent_bash("python3 " + EXTRA)
    return report(p, digest)


@defect("V-19", "verify", "verify", ["Unstated defaults"],
        {"status": CONFORMS, "messages": ["Default without a usable reason (advisory)"]})
def v19(p):
    return baseline(p, plan(change=lambda t: t.replace("default: matches step 2", "default: standard")))[1]


@defect("V-20", "verify", "none", ["Stale evidence as current"], known_miss=True,
        expect={"status": CONFORMS, "credited_to": "python3 " + harness.SCRIPTS[0]})
def v20(p):
    # 02 finished within TOLERANCE of 01's receipt (as on a fast machine), so verify credits
    # de_results.tsv to the earliest receipt that could have written it: run 01, under the same plan.
    digest = p.approve(harness.plan_text())[0]
    first, _, last = [p.run_step(script) for script in harness.SCRIPTS]
    stale_mtime(p, DE, first.receipts[0]["ts"] + 1)
    p.space_outputs([(SUMMARY, last.receipts[0])])
    p.lineage()
    outcome = report(p, digest)
    found = [line for line in outcome["text"].splitlines() if line.startswith("| `{}` |".format(DE))]
    outcome["credited_to"] = found[0].split("`")[3] if found else None
    return outcome


# ---------------------------------------------------------------- 8.4 sweeps and memory

def verified(p):
    """The baseline plan run, verified, its provenance written and committed, as in the chain."""
    digest = p.run_plan()[0]
    p.fill_ledger(digest)
    code, out, err = p.verify("write", digest, "--analysis-dir", A)
    if harness.status_line(out) != CONFORMS:
        raise harness.HarnessError("verify write did not conform:\n" + out + err)
    p.commit("provenance for plan " + digest)
    return digest


def sweep(p, *args):
    code, out, err = p.verify(*args)
    return {"code": code, "text": out + err}


@defect("S-01", "sweep", "verify", ["Stale evidence as current"],
        {"code": 0, "scripts": 1, "ledger": True,
         "messages": ["1 of 1 verified plans stale", "script `{}` edited since it ran".format(PAIRED)]})
def s01(p):
    verified(p)
    p.edit(PAIRED, lambda text: text + "# tidied\n")
    outcome = sweep(p, "stale")
    outcome["scripts"] = sum(line.startswith("- script ") for line in outcome["text"].splitlines())
    found = re.search(r"findings: `rg -n '([^']+)' \.living/findings/`", outcome["text"])
    with open(p.path(".living", "findings", "vaccine-response.md"), encoding="utf-8") as handle:
        ledger = [line for line in handle if line.startswith("| 2026-")]  # F-001's Evidence Ledger row
    outcome["ledger"] = bool(found and ledger and re.search(found.group(1), ledger[0]))
    return outcome


@defect("S-02", "sweep", "verify", ["Outputs and reporting"], {"code": 0, "manifest": "not listed"})
def s02(p):
    verified(p)
    p.edit("analysis/ANALYSIS_MANIFEST.md", lambda text: text.split("### vaccine-response")[0])
    outcome = sweep(p, "status", "--json")
    rows = json.loads(outcome["text"]) if outcome["code"] == 0 else []
    outcome["manifest"] = rows[0]["manifest"] if len(rows) == 1 else rows
    return outcome


@defect("S-03", "sweep", "verify", ["Stale evidence as current"],
        {"code": 0, "messages": ["1 of 1 verified plans stale", "summary.tsv", "deleted"]})
def s03(p):
    verified(p)
    os.remove(p.path(SUMMARY))
    return sweep(p, "stale")


@defect("M-01", "memory", "decision-status", ["Redoing settled work"],
        {"code": 0, "dates": ["2026-03-02", "2026-05-10", "2026-07-15"], "names_current": False,
         "messages": ["Raw fields only: no status is inferred", "status: confirmed", "status: held"]})
def m01(p):
    code, out, err = p.stdin_skill("decision-status", "decision_threads.py", "--living-dir .living --term normalisation")
    dates = [d for d in ("2026-03-02", "2026-04-01", "2026-04-20", "2026-05-10", "2026-07-15") if d in out]
    return {"code": code, "text": out + err, "dates": dates, "names_current": "current" in out.lower()}


# ---------------------------------------------------------------- 8.5 known bugs, now fixed
# Each was a bug at 3a11123. E2 and E3 fixed them, so they are plain asserts: an expectedFailure
# that passed would report the suite as FAILED.

@defect("KB-01", "gate", "approval gate", ["tool: gate state"], {"decision": "silent"})
def kb01(p):
    return gate(p.agent_bash("python3 -c \"import os; open('notes.txt','w').write(os.path.join('x', '.mycelium-extra'))\""))


@defect("KB-02", "gate", "approval gate", ["tool: gate state"], {"decision": "silent"})
def kb02(p):
    with open(p.path("notes.md"), "w", encoding="utf-8") as handle:
        handle.write("The gate state lives in one place.\n")
    return gate(p.agent_bash("sed -i 's/gate state/the `.mycelium-extra` folder/' notes.md"))


@defect("KB-03", "gate", "approval gate", ["tool: gate state"], {"decision": "silent"})
def kb03(p):
    # Python 3.6 cannot parse `:=`, so the gate falls back to its any-mention rule; 3.8+ parses it.
    command = ("python3 - <<'EOF'\nif (name := 'notes.txt'):\n"
               "    open(name, 'w').write('see .mycelium-extra')\nEOF")
    pre = p.pre_bash(command)
    return {"decision": DENY if p.denied(pre) else "silent" if pre is None else "notice", "text": json.dumps(pre)}


@defect("KB-04", "verify", "verify", ["tool: verify"],
        {"status": GAPS, "row": "ran (exit status unknown)",
         "messages": ["but the tool response carried no exit status, so the run is not counted as a success"]})
def kb04(p):
    digest = p.approve(harness.plan_text())[0]
    results = [p.agent_bash("python3 " + s, response="bare" if s == PAIRED else "claude") if s != harness.SCRIPTS[2]
               else p.run_step(s) for s in harness.SCRIPTS]
    p.space_outputs([(harness.out_of(s), r.receipts[0]) for s, r in zip(harness.SCRIPTS, results)])
    p.lineage()
    outcome = report(p, digest)
    outcome["row"] = row_status(outcome["text"], PAIRED)
    return outcome


WRAP = "sbatch --chdir={} --wrap 'python3 scripts/01_select_samples.py'".format(A)


@defect("KB-05", "verify", "verify", ["tool: verify"],
        {"decision": "silent", "script": harness.SCRIPTS[0], "row": "job 4242 COMPLETED"})
def kb05(p):
    digest = p.approve(plan([row(1, WRAP, choice="runs `{}`".format(harness.SCRIPTS[0]))],
                            outputs=harness.OUTPUTS[0]))[0]
    result = p.agent_bash(WRAP, effect=lambda q: q.shell("python3 " + harness.SCRIPTS[0])[1] + "Submitted batch job 4242\n")
    outcome = gate(result)
    outcome["script"] = ((result.receipts or [{}])[0].get("paths") or [None])[0]
    outcome["row"] = row_status(report(p, digest)["text"], harness.SCRIPTS[0])
    return outcome


@defect("KB-06", "verify", "verify", ["tool: verify"],
        {"row": "no receipt", "messages": ["`{}`: no run under this plan was recorded".format(harness.SCRIPTS[2])]})
def kb06(p):
    # A report rule lists 03_summary.R as an input (for dependency tracking) but runs only R Markdown.
    def effect(q):
        snakemake_effect(None)(q)
        os.remove(q.path(A, ".snakemake", "metadata", base64_name(RULES[2][2])))
        q.snakemake_record("reports/report.html", "report", ["scripts/03_summary.R", "reports/report.Rmd"],
                           "Rscript -e \"rmarkdown::render('reports/report.Rmd')\"", workdir=A)
        return ""
    digest = p.approve(plan(change=lambda t: t.replace("\n\nPlan status", "\n" + row(
        4, SNAKEMAKE, source="repo: " + A + "/Snakefile") + "\n\nPlan status")))[0]
    p.agent_bash(SNAKEMAKE, effect=effect)
    outcome = report(p, digest)
    outcome["row"] = row_status(outcome["text"], harness.SCRIPTS[2])
    return outcome


def base64_name(output):
    return base64.b64encode(output.encode("utf-8")).decode("ascii")


def by_id(id):
    return [d for d in DEFECTS if d.id == id][0]
