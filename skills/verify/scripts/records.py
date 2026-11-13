"""Verify's provenance records: the saved bundle, the PROVENANCE.md index, the Outputs row and the readers of them.

Moved out of verify.py unchanged. verify.py runs from stdin as well as a module, so this file cannot import it:
`bind` hands it the names it uses (the gate, `render`, `when`, ...) from verify's globals before each call.
Stdlib-only.
"""

import json
import os
import re
import sys
import time

gate = PLUGIN_ROOT = when = waiver_note = render = read_text = _paths = LINT_LINE = QUALIFICATION_LINE = None
_BOUND = ("gate", "PLUGIN_ROOT", "when", "waiver_note", "render", "read_text", "_paths", "LINT_LINE",
          "QUALIFICATION_LINE")


def bind(names):
    """Take the helpers verify.py owns; called by verify.py before every use, so a later gate is picked up."""
    globals().update({name: names[name] for name in _BOUND})


def recorded_qualification(folder, digest):
    """`qualified` or `not qualified` from the saved report, `not recorded` for a bundle written before it."""
    found = QUALIFICATION_LINE.search(read_text(os.path.join(folder, "verify-{}.md".format(digest))))
    return found.group(1) if found else "not recorded"


def _write_bundle(root, result, folder):
    if result.get("plan_intact") is False:
        sys.exit("verify: plan {} does not hash to its approval record, so it is not saved as the frozen plan as "
                 "approved. Restore the approval record, then write again.".format(result["hash"]))
    if not os.path.isdir(os.path.join(root, result["analysis_dir"])):
        sys.exit("verify: analysis folder {} does not exist.".format(result["analysis_dir"]))
    os.makedirs(folder, exist_ok=True)
    digest = result["hash"]
    stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime())
    paths = {"plan": "plan-{}.md".format(digest), "receipts": "receipts-{}.jsonl".format(digest),
             "outputs": "outputs-{}.tsv".format(digest), "report": "verify-{}.md".format(digest),
             "lint": "lint-{}.txt".format(digest)}
    if result.get("validation_binding"):  # the frozen binding, each check's outcome and the raw evidence's identity
        paths["validation"] = "validation-{}.json".format(digest)
        with open(os.path.join(folder, paths["validation"]), "w", encoding="utf-8") as handle:
            json.dump({"schema": "mycelium-extra.validation-record.v1", "hash": digest,
                       "instance": (result.get("instance") or {}).get("selected"),
                       "binding": result["validation_binding"], "results": result["validation"]},
                      handle, indent=1, sort_keys=True)
            handle.write("\n")
    if any(env["packages"] for env in result.get("envs") or []):
        paths["env"] = "env-{}.txt".format(digest)
        with open(os.path.join(folder, paths["env"]), "w", encoding="utf-8", errors="surrogateescape") as handle:
            handle.write("# Conda envs of plan {}'s runs, read {} from each env's conda-meta (the format of "
                         "`conda list --explicit --md5`).\n# One block per env: copy a block from `@EXPLICIT` "
                         "into its own file for `conda create -n <name> --file <file>`.\n".format(digest, stamp))
            for env in (e for e in result["envs"] if e["packages"]):
                handle.write("\n# env: {}\n# prefix: {}\n# from: {}\n{}@EXPLICIT\n{}\n".format(
                    env["env"], env["prefix"], env["source"],
                    "# changed after the run: this is the env as it was when verify read it\n"
                    if env["changed_after_run"] else "", "\n".join(env["packages"])))
    if any(env.get("pip") for env in result.get("envs") or []):
        paths["pip"] = "pip-{}.txt".format(digest)
        with open(os.path.join(folder, paths["pip"]), "w", encoding="utf-8", errors="surrogateescape") as handle:
            handle.write("# Pip packages of plan {}'s runs, read {} from each conda env's site-packages: the "
                         "Python packages conda did not install.\n# Usable as: pip install -r {}. A commented-out package came "
                         "from a local path or archive: install it from there.\n".format(
                             digest, stamp, paths["pip"]))
            for env in (e for e in result["envs"] if e.get("pip")):
                handle.write("\n# env: {}\n# prefix: {}\n# from: {}\n{}{}\n".format(
                    env["env"], env["prefix"], env["source"],
                    "# changed after the run: this is the env as it was when verify read it\n"
                    if env["pip_changed_after_run"] else "", "\n".join(env["pip"])))
    if result.get("rule_envs"):
        paths["rule_envs"] = "rule-envs-{}.json".format(digest)
        with open(os.path.join(folder, paths["rule_envs"]), "w", encoding="utf-8") as handle:
            json.dump({"schema": "mycelium-extra.rule-envs.v1", "hash": digest,
                       "note": "Read from `.snakemake/conda/`; the layout was checked against one real run (Snakemake 9.27.0 with conda 24.9.2 (one real run, 2026-10-20)), "
                               "other versions are not validated.", "envs": result["rule_envs"]},
                      handle, indent=1, sort_keys=True)
            handle.write("\n")
    with open(os.path.join(folder, paths["plan"]), "w", encoding="utf-8", errors="surrogateescape") as handle:
        handle.write("# Approved plan {}\n\nApproved {} in session {}. Frozen copy of the plan "
                     "the mycelium-extra gate approved; do not edit it. Revise the analysis's own plan "
                     "instead.\n\n---\n\n{}\n".format(digest, when(result["approved_at"]),
                                                      result["session_id"], result["plan"].rstrip()))
    with open(os.path.join(folder, paths["receipts"]), "w", encoding="utf-8", errors="surrogateescape") as handle:
        for receipt in result["receipts"]:
            handle.write(json.dumps(receipt, sort_keys=True) + "\n")
    with open(os.path.join(folder, paths["outputs"]), "w", encoding="utf-8", errors="surrogateescape") as handle:
        # The first six columns are the older format (stale reads only the first three); a table without
        # the last four is a legacy bundle: its producers were chosen by timing, with no grade.
        handle.write("path\twritten\tsize\tsha256\tfingerprint\twritten_by\tproducer_attempt\tevidence_method"
                     "\tstrength\tapproval_instance\n")
        for row in result["outputs"]:
            record = row["record"]
            handle.write("\t".join(str(v) for v in [
                row["path"], time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(row["written"])),
                record.get("size", ""), record.get("sha256", ""), gate.method(record),
                row["by"] + (" via " + row["rule"] if row["rule"] else ""),
                row["producer_attempt"] or "", row["evidence_method"], row["strength"],
                (result.get("instance") or {}).get("selected") or "legacy"]) + "\n")
    with open(os.path.join(folder, paths["lint"]), "w", encoding="utf-8", errors="surrogateescape") as handle:
        lint = result["lint"]
        handle.write("\n\n".join(lint["output"]) or "scilintr did not run.")
        handle.write("\n\n# ANALYSIS_OK waivers ({})\n".format(len(lint["waivers"])))
        handle.writelines("{}:{}: {}\n".format(*w) for w in lint["waivers"])
        handle.write("\n# Waived findings ({})\n".format(len(lint.get("waived", []))))
        handle.writelines("{}:{} [{}] <- {}\n".format(w[0], w[1], w[2], waiver_note(w).replace("`", ""))
                          for w in lint.get("waived", []))
        handle.write("\n# Approved thresholds ({})\n".format(len(lint.get("approved", []))))
        handle.writelines("{}:{} [{}]\n".format(f[0], f[1], f[3]) for f in lint.get("approved", []))
    with open(os.path.join(folder, paths["report"]), "w", encoding="utf-8", errors="surrogateescape") as handle:
        handle.write("Written {} by mycelium-extra verify.\n\n".format(stamp))
        handle.write(render(result, all_outputs=True, saved=True))
    import evidence
    try:
        with open(os.path.join(PLUGIN_ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as handle:
            version = json.load(handle)["version"]
    except (OSError, ValueError, KeyError, TypeError):
        version = "unknown"
    handoff = evidence.project(result, version, references=dict(paths))
    paths["evidence"] = "evidence-{}.json".format(digest)
    with open(os.path.join(folder, paths["evidence"]), "w", encoding="utf-8") as handle:
        json.dump(handoff, handle, indent=2, sort_keys=True)
        handle.write("\n")
    index = os.path.join(folder, "PROVENANCE.md")
    row = "| {} | {} | {} | {} | [plan]({}) - [receipts]({}) - [outputs]({}) - [lint]({}) - [report]({}){} |".format(
        digest, when(result["approved_at"]), stamp, result["status"], paths["plan"], paths["receipts"],
        paths["outputs"], paths["lint"], paths["report"],
        (" - [validation]({})".format(paths["validation"]) if "validation" in paths else "") +
        (" - [conda env]({})".format(paths["env"]) if "env" in paths else "") +
        (" - [pip]({})".format(paths["pip"]) if "pip" in paths else "") +
        (" - [rule envs (layout checked against one real run: Snakemake 9.27.0, conda 24.9.2)]({})".format(paths["rule_envs"]) if "rule_envs" in paths else ""))
    if os.path.isfile(index):
        with open(index, encoding="utf-8") as handle:
            lines = [line.rstrip("\n") for line in handle if not line.startswith("| {} |".format(digest))]
    else:
        lines = ["# Provenance", "",
                 "One row per approved plan checked for this analysis by mycelium-extra verify. Each plan's "
                 "frozen text, its run receipts, and the check sit beside this file.", "",
                 "| Plan | Approved | Verified | Status | Files |", "|---|---|---|---|---|"]
    lines.append(row)
    with open(index, "w", encoding="utf-8", errors="surrogateescape") as handle:
        handle.write("\n".join(lines) + "\n")
    return ["PROVENANCE.md"] + list(paths.values())


def write(root, result):
    if not os.path.isdir(os.path.join(root, result["analysis_dir"])):
        sys.exit("verify: analysis folder {} does not exist.".format(result["analysis_dir"]))
    import provenance
    folder = os.path.join(root, result["analysis_dir"], "provenance")
    names = provenance.publish(folder, result["hash"], lambda stage: _write_bundle(root, result, stage))
    return [os.path.join(os.path.relpath(folder, root), name) for name in names]


def target_row(result):
    return "provenance/verify-{}.md in the Outputs table".format(result["hash"])


def index_outputs(root, result):
    """Put one row for this plan's verify record in the `## Outputs` table of the analysis doc, replacing an
    earlier row for the same file. Returns the note to print when nothing was added, else None."""
    folder = os.path.join(root, result["analysis_dir"])
    doc = _paths().find_doc(folder)
    if not doc:
        return "no analysis doc in {}, so no Outputs row was added.".format(result["analysis_dir"])
    target = "provenance/verify-{}.md".format(result["hash"])
    row = "| {} | verify {} ({}) |".format(target, result["status"], time.strftime("%Y-%m-%d", time.localtime()))
    lines = read_text(doc).splitlines()
    start = next((i for i, line in enumerate(lines) if re.match(r"^##\s+Outputs\s*$", line)), None)
    first = last = None
    for i in range(start + 1 if start is not None else len(lines), len(lines)):
        if lines[i].startswith("#"):
            break
        if lines[i].lstrip().startswith("|"):
            first = i if first is None else first
            last = i
        elif first is not None:
            break
    if first is None or last - first < 1:
        return "{} has no `## Outputs` table, so no Outputs row was added.".format(os.path.basename(doc))
    old = re.compile(r"^\|\s*`?{}`?\s*\|".format(re.escape(target)))
    kept = [line for i, line in enumerate(lines) if not (first + 2 <= i <= last and old.match(line))]
    kept.insert(last + 1 - (len(lines) - len(kept)), row)
    with open(doc, "w", encoding="utf-8", errors="surrogateescape") as handle:
        handle.write("\n".join(kept) + "\n")
    return None


def provenance_receipts(root):
    """Include interrupted first saves, using Git's inventory without scanning data trees."""
    listed = gate.git(root, "ls-files", "-co", "--exclude-standard", "--",
                      "*provenance/receipts-*.jsonl", "*provenance/complete-*.json",
                      "*provenance/.transactions/pending.json")
    ignored = gate.git(root, "ls-files", "-o", "-i", "--exclude-standard", "--",
                       "*provenance/receipts-*.jsonl", "*provenance/complete-*.json",
                       "*provenance/.transactions/pending.json")
    if listed is not None:
        # an analysis folder a repository ignores still holds provenance it wrote: list ignored files too
        paths = set(line for line in listed.splitlines() if line)
        paths |= set(line for line in (ignored or "").splitlines() if line)
    else:
        paths = set()
        for folder, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            if os.path.basename(folder) == "provenance":
                paths.update(os.path.relpath(os.path.join(folder, f), root) for f in files)
                if os.path.isfile(os.path.join(folder, ".transactions", "pending.json")):
                    paths.add(os.path.relpath(os.path.join(folder, ".transactions", "pending.json"), root))
    found = set()
    for rel in paths:
        name, folder = os.path.basename(rel), os.path.dirname(rel)
        if re.fullmatch(r"receipts-[0-9a-f]{8}\.jsonl", name):
            found.add(rel)
        elif re.fullmatch(r"complete-[0-9a-f]{8}\.json", name):
            found.add(os.path.join(folder, "receipts-" + name[9:-5] + ".jsonl"))
        elif name == "pending.json" and os.path.basename(folder) == ".transactions":
            pending = gate.read_json(os.path.join(root, rel), {})
            if isinstance(pending, dict) and isinstance(pending.get("members"), dict):
                found.update(os.path.join(os.path.dirname(folder), f) for f in pending["members"]
                             if re.fullmatch(r"receipts-[0-9a-f]{8}\.jsonl", f))
    return sorted(found)


def recorded_lint(folder, digest):
    text = read_text(os.path.join(folder, "lint-{}.txt".format(digest)))
    if not text:
        return "not recorded"
    approved = re.search(r"^# Approved thresholds \((\d+)\)$", text, re.M)
    approved = int(approved.group(1)) if approved else 0
    text = text.split("# ANALYSIS_OK waivers")[0]
    found = max(sum(1 for line in text.splitlines() if LINT_LINE.match(line)) - approved, 0)
    # A missing, timed-out or unreadable linter leaves no finding in the lint file; the report names it.
    gaps = sorted(set(re.findall(r"scilintr \((\w+)\) not checked",
                                 read_text(os.path.join(folder, "verify-{}.md".format(digest))))))
    states = (["{} finding(s)".format(found)] if found else []) + (
        ["{} approved threshold(s)".format(approved)] if approved else []) + (
        ["gap: {} not checked".format(", ".join(gaps))] if gaps else [])
    if states:
        return "; ".join(states)
    return "clean" if text.startswith("$ ") else "not run"


def recorded_verify(folder, digest):
    """(approved, verify status) from the analysis's PROVENANCE.md row for the plan."""
    for line in read_text(os.path.join(folder, "PROVENANCE.md")).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[0] == digest:
            return cells[1], cells[3]
    return "?", "verified"
