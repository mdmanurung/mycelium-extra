"""Regenerate docs/example.md: one real session on the fixture project (docs/design/c1-fixture-project.md).

    MX_E2E_SCILINTR=/path/to/scilintr MX_E2E_RSCRIPT=/path/to/Rscript python3 tests/e2e/make_example.py [OUT]

Every output block is what the hooks and verify printed in this run. The plan is hand-written
(tests/e2e/plans/baseline_plan.md): the model writes the brief in a real session, which no script can
generate. Mycelium's lineage manifest is written by the harness, as in the chain test. Needs the real
Python scilintr and an Rscript whose R has scilintr, so the lint lines are the real linter's.
"""

import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness

OUT = os.path.join(harness.REPO, "docs", "example.md")
PROMPT = ("/mycelium-extra:grill Test whether the day 28 minus day 0 change in gene expression differs between "
          "the vaccine and placebo arms of the vaccine cohort. Reference is placebo.")
HEAD = """# A worked example

[Back to the usage tiers](usage.md)

One session on the fixture project (`tests/fixtures/mycelium-project`): plan, approve, run, verify. Every output block below is what the hooks and `verify` printed in a real run on {date}, at version {version}. The two exceptions are the plan, which is written by hand because the model writes it in a real session (the file is `tests/e2e/plans/baseline_plan.md`), and Mycelium's lineage manifest, which the test harness writes where Mycelium's own hook would. Regenerate with `python3 tests/e2e/make_example.py` (see the top of that file for the tools it needs) when an output format changes.

"""


def block(text, language="text"):
    return "```{}\n{}\n```\n\n".format(language, text.strip("\n"))


def real_tools():
    scilintr, rscript = os.environ.get("MX_E2E_SCILINTR"), os.environ.get("MX_E2E_RSCRIPT")
    if not (scilintr and os.path.isfile(scilintr) and rscript and os.path.isfile(rscript)):
        sys.exit("set MX_E2E_SCILINTR and MX_E2E_RSCRIPT to a working scilintr and Rscript")
    return scilintr, rscript


def main(out_path):
    scilintr, rscript = real_tools()
    os.environ["PATH"] = os.path.dirname(rscript) + os.pathsep + os.environ.get("PATH", "")
    p = harness.Project.fresh(r=True)
    try:
        p.write_fakes(rscript=rscript)  # sacct stays a stand-in: the example runs no Slurm job
        with open(os.path.join(p.bin, "scilintr"), "w") as handle:
            handle.write('#!/bin/sh\nexec {} "$@"\n'.format(harness.sh_quote(scilintr)))
        os.chmod(os.path.join(p.bin, "scilintr"), 0o755)
        with open(p.path(".mycelium-extra", "tools.json"), "w") as handle:  # what `init --tools` records
            json.dump({"scilintr": os.path.join(p.bin, "scilintr"), "rscript": os.path.join(p.bin, "Rscript-lint")}, handle)
        first = harness.SCRIPTS[0]
        text = harness.plan_text()
        refused = p.agent_bash("python3 " + first)
        if not refused.denied:
            sys.exit("the gate allowed a run before approval")
        digest, card, reply = p.approve(text)
        results = [p.run_step(s) for s in harness.SCRIPTS]
        if any(r.code != 0 or r.denied for r in results):
            sys.exit("a planned step failed:\n" + "\n".join(p.log))
        p.space_outputs([(harness.out_of(s), r.receipts[0]) for s, r in zip(harness.SCRIPTS, results)])
        p.lineage()
        code, report, err = p.verify("report", digest)
        if code != 0:
            sys.exit("verify report failed: {}{}".format(report, err))
        receipt = results[0].receipts[0]
        scrub = lambda s: s.replace(p.root, "<project>").replace(p.tmp, "<tmp>")
        version = re.search(r'"version": "([^"]+)"', open(os.path.join(harness.REPO, ".claude-plugin",
                                                                      "plugin.json")).read()).group(1)
        doc = HEAD.format(date=datetime.date.today().isoformat(), version=version)
        doc += "## 1. Ask\n\nYou describe the question to grill. It searches the repository's records, asks what only " \
               "you can decide, and ends with a brief.\n\n" + block(PROMPT)
        doc += "## 2. The brief\n\nThe plan table is what the gate reads. Only the Step column grants a run; its " \
               "paths and commands are the whole grant.\n\n" + block(text, "markdown")
        doc += "## 3. Before approval, a run is denied\n\nThe agent tries step 1 straight away.\n\n" + \
               block("$ " + refused.command + "\n\n" + scrub(refused.reason))
        doc += "## 4. The approval card\n\nWhen the reply ends with `Plan status: READY`, the Stop hook shows this " \
               "card. You check the science on it, then type the last line.\n\n" + block(scrub(card)) + \
               "Step 3's `lint` bullet shows one open scilintr finding. The card is for your eyes and never blocks; " \
               "`verify` will, below.\n\n"
        doc += "## 5. Approval\n\n" + block("> approve plan {}\n\n{}".format(digest, scrub(reply["systemMessage"])))
        doc += "## 6. The gated runs and their receipts\n\nThe three steps run with no hook speaking. Each leaves a " \
               "receipt (here the first, trimmed to its main fields).\n\n"
        script = receipt.get("script") or {}
        shown = [("command", receipt.get("command")), ("plans", receipt.get("plans")),
                 ("script", script.get("path")), ("script sha256", (script.get("sha256") or "")[:12]),
                 ("script git", script.get("git")), ("exit", receipt.get("exit")),
                 ("exit source", receipt.get("exit_source"))]
        doc += block("\n".join("{}: {}".format(k, json.dumps(v)) for k, v in shown if v not in (None, "")))
        doc += "## 7. Verify\n\n`verify report` checks what ran against the approved plan and prints the result.\n\n"
        doc += block(scrub(report), "markdown")
        doc += ("`Verify status: DOES_NOT_CONFORM` is the point of the exercise. Every planned script ran under the "
                "approved plan and the inputs are unchanged, but scilintr found a magic threshold (`padj < 0.05`) "
                "in the R code, and `verify` blocks on a finding that is neither fixed nor waived. Name the "
                "constant, or waive it with `ANALYSIS_OK[R002]: <what is done, why it is valid, where it is "
                "checked>`; that edits a pinned script, so present the plan again, approve it, and re-run. "
                "`verify write <hash>` then records the plan, receipts and report under `provenance/`.\n")
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write(doc)
        print("wrote " + out_path)
    finally:
        p.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else OUT)
