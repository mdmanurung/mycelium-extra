"""The planted-defect catalog (docs/design/c1-fixture-project.md, section 8).

Each defect applies one mutation to a fresh baseline project and drives the chain to the check
that should catch it. `run(project)` returns an outcome dict, and the test compares it with
`expect`: every key except `messages` must be equal, and every string in `messages` must appear
in outcome["text"]. A known miss expects what a chain that reports success produces, plus the
evidence that its results are wrong.

Stdlib only, Python 3.6 grammar.
"""

import json
import time

import harness

A = harness.ANALYSIS
METADATA = "data/processed/vaccine-cohort/sample_metadata.tsv"
COUNTS = "data/processed/vaccine-cohort/counts.tsv"
PAIRED = A + "/scripts/02_paired_test.py"
CONFORMS = "Verify status: CONFORMS"
DENY = "deny"


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


def by_id(id):
    return [d for d in DEFECTS if d.id == id][0]
