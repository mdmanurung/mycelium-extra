# Manuscript-audit: approved-plan `verify` scenario, simulated and native (Claude Code)

Record of 2026-10-26 on branch `feature/manuscript-reproducibility`. It follows the [integration ledger](2026-10-26-manuscript-reproducibility-integration.md). This note qualifies one path from start to finish: a researcher-approved plan pins the manuscript checker and its contract, the gate records the runs, and `verify` grades the bound check.

**Status: native runs NOT performed.** The **Expected** column, the runbook and the grading rules below were written and committed before any native run (the [E4](e4-real-use.md) convention). **Simulated** results come from a host simulator, not a model or a Claude Code process. **Native observed** and **Verdict** stay empty until returned bundles are graded.

## What is under test

`tests/e2e/manuscript_scenario.py` builds a fresh git project for each scenario. The gate is turned on with `init` defaults (`gated_paths` `analysis/**`, `nbs/**`). All data are synthetic. Under `analysis/paper/` the project has:

- `data/counts.tsv` and its manifest `data/README.md`;
- the producer `scripts/01_make_source.py`, which writes `outputs/freq.tsv` and `figures/source_data/Fig1a.tsv`;
- the figure script `scripts/plot_fig1.py`, which the contract names but no scenario runs;
- the contract `config/manuscript_checks.json`;
- a byte copy of the checker at `tests/manuscript_audit.py`.

Because the checker is copied in, the binding's `test_paths` are pinned inside the project. The sample binding in `tests/fixtures/manuscript-project/APPROVED_PLAN_SNIPPET.md` names the plugin's own path, which exists only inside this repository.

The plan is the same in every scenario. Row 1 runs the producer. Row 2 runs the checker. Its single binding is:

```text
M-FIG-001  plan_row 2, required, defined_by researcher-approved
  test_paths    analysis/paper/tests/manuscript_audit.py, analysis/paper/config/manuscript_checks.json
  invocation    python3 analysis/paper/tests/manuscript_audit.py --root analysis/paper
                  --config config/manuscript_checks.json --result-json outputs/manuscript_audit.json
  evidence_path analysis/paper/outputs/manuscript_audit.json
```

Nothing in the gate, hooks, approval or `verify` was changed for this work.

## Scenarios, expectations and results

| Scenario | Setup | Expected (pre-registered) | Simulated (observed) | Native observed | Verdict |
|---|---|---|---|---|---|
| S1 pass | correct producer; rows 1 and 2 run | `M-FIG-001` passed; status `CONFORMS`, or `CONFORMS_WITH_GAPS` only if every gap is unrelated to validation (for example scilintr is not installed) | passed; `CONFORMS` (faked scilintr reports clean) | not run | - |
| S2 fail | producer omits `fraction` from the Figure 1a source data; rows 1 and 2 run | checker exits 2; failed, naming `fraction`; `DOES_NOT_CONFORM` | checker exit 2 via `PostToolUseFailure`; failed: "Missing declared plotting columns: fraction"; `DOES_NOT_CONFORM` | not run | - |
| S3 not run | correct producer; row 1 only | not run ("no matched run"); not `CONFORMS`; a finding says "not established" | not run; `CONFORMS_WITH_GAPS`; "not established" present | not run | - |
| S4 changed (simulated only) | contract edited after approval, before the check | `changed`, or a gate denial of the check for the changed pin | gate denied the check ("analysis/paper/config/manuscript_checks.json changed"); `changed`; `DOES_NOT_CONFORM` | n/a | - |
| S5 unattributable (simulated only) | check passes, then its evidence is rewritten outside any attempt, after verify's 5 s tolerance | `unattributable` | unattributable ("modified after the attempt"); `CONFORMS_WITH_GAPS` | n/a | - |
| S5b control (simulated only) | check fails (S2 data), then a pass is written over its evidence at once | not pre-registered (see below) | failed (the recorded exit 2 decides); `DOES_NOT_CONFORM` | n/a | - |

The simulated column comes from `tests/test_manuscript_verify_e2e.py`, which is discovered by CI. That test sends the real `hooks/gate_run.py` the event shapes Claude Code sends (`tests/e2e/harness.py`). The producer and checker really run between their `PreToolUse` and `PostToolUse` or `PostToolUseFailure` events, and the real `verify` produces both the report and `--json`. Every simulated outcome matched its expectation.

### Disclosures from the simulated pass

- **S5 was redesigned after a probe.** The first S5 setup was "the check fails, then a pass is forged over its evidence". That gave `failed`, not `unattributable`, because Claude Code records the exit code and the recorded exit 2 decides. That case is kept as control S5b. S5 now rewrites the evidence of a passing check, which is how verify's unattributable rule is meant to be exercised. This change was made before the oracle and this note were committed. It is listed here because the original plan table described S5 only loosely.
- **A rewrite within 5 s is not caught.** In a probe, the evidence of a passing check was rewritten straight after the attempt. `verify` attributed it to the attempt and graded it passed. `verify` allows 5 s of clock skew between a hook and the filesystem (`TOLERANCE` in `skills/verify/scripts/verify.py`). With Claude Code the recorded exit code still blocks a forged pass over a failed check (S5b). A host that records no exit status (Codex records `unknown`) gets no such protection. That case was not tested. This is a property of `verify` and was not changed here.
- **An unattributable result is a gap, not a block.** S5 ends `CONFORMS_WITH_GAPS`: verify counts such a check as not established, not as failed.

## Native runbook (Claude Code, on the researcher's machine)

The native run needs a logged-in Claude Code and spends the researcher's quota: 3 short turns per scenario, 9 in total. No credentials or host configuration go into the bundle. The run follows the [H1](h1-native-host-lint.md) setup: `claude -p --plugin-dir <checkout> --include-hook-events`.

```sh
git -C <checkout> checkout feature/manuscript-reproducibility   # clean tree, the commit under test
sh <checkout>/tests/e2e/run_manuscript_native.sh S1 /tmp/mx-native
sh <checkout>/tests/e2e/run_manuscript_native.sh S2 /tmp/mx-native
sh <checkout>/tests/e2e/run_manuscript_native.sh S3 /tmp/mx-native
# return /tmp/mx-native/S1.tar.gz S2.tar.gz S3.tar.gz
```

For each scenario, `tests/e2e/run_manuscript_native.sh` does the following:

1. It records `claude --version`, the plugin commit and tree status, `claude plugin validate .`, `python3 --version` and whether scilintr is installed.
2. It generates the project and runs `init`.
3. **Turn 1.** The agent repeats the plan verbatim. The plan text is in the prompt, and Bash, Write and Edit are disallowed. The Stop hook prints the plan card.
4. The script shows the card and the contract. The researcher reads both and types `approve plan <hash>`. Any other input aborts the run and produces no bundle.
5. **Turn 2.** The researcher's own line is sent as the user prompt (`--resume <session>`), again with no tools.
6. **Turn 3.** The agent runs exactly the plan's rows; S3 runs row 1 only. Only those two commands are allowed, and Write and Edit are disallowed.
7. `verify report <hash>` and `--json` run from the shell, as `skills/verify/SKILL.md` documents. This is read-only.
8. The project (without `.git`) and the host records go into one tarball.

If the agent runs anything outside the plan's rows, or the gate denies a command, that is recorded as observed. The run is not retried silently.

## Grading rules

The grader is `python3 tests/e2e/grade_manuscript_native.py S1.tar.gz S2.tar.gz S3.tar.gz --json grades.json`. A bundle is `native-verified` only if all of the following checks pass:

| Check | Rule |
|---|---|
| scenario | `SCENARIO.json` names S1, S2 or S3 and matches the bundle folder |
| project | the plan, contract, checker copy, producer, figure script and data are byte-identical to what the generator writes at this checkout |
| host | `claude --version` is a Claude Code line and not a simulated one |
| approval | the approval record's binding equals the generated `M-FIG-001`, and its `session_id` is the session in the stream-json log |
| dispatch | every gate receipt of the run carries a host `tool_use_id` that turn 3 shows as a Bash `tool_use` with the same command. Each is matched to a gate launch, with the exit status from a Claude Code event (`event` for `PostToolUse`, `error` for `PostToolUseFailure`). If the stream carries hook events, turn 2 must show `UserPromptSubmit`, and turn 3 must show `PreToolUse` and `PostToolUse`/`PostToolUseFailure` tied to the checker. A stream with no hook events is reported as such. |
| adherence | turn 3's Bash commands are exactly the planned rows, in order |
| outcome | `verify --json` for the approved hash gives the Expected outcome and status above; the Markdown and JSON statuses agree |

The verdicts are `native-verified`, `not-native` (host, approval or dispatch failed), `deviated` (project or adherence failed) and `outcome-mismatch`.

The grader checks that the host's log agrees with the gate's own records. **It cannot prove a bundle came from a real session.** That rests on who ran it.

`tests/test_manuscript_native_grader.py` runs the runbook against a `claude` shim that is labelled simulated. The shim dispatches the real gate through `hooks/py.sh` as `hooks/hooks.json` does. The tests confirm three things: the runbook shows the card and contract before asking, the grader calls every shim bundle `not-native` with only the host check failing, and tampered bundles (an edited contract, an edited verify outcome, a receipt with no call id) fail the matching check.

## What a native pass would and would not show

If all three bundles grade `native-verified`, then on that Claude Code version the following holds. A researcher's typed approval froze the checker and contract. The host dispatched the gate for the producer and the checker. `verify` reported the bound manuscript check as passed, failed or not run, as each run warranted.

It would not show that the contract declares the right columns, that the figure is correct, that the science is valid, or that a published paper reproduces. It would not cover Codex or OpenCode, or the `changed` and `unattributable` outcomes on a native host; those two are simulated only.
