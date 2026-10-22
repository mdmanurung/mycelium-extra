# Adversarial audit, 2026-10-21

**Verdict: the contracts do not all hold.** Independent probes expose nine
distinct defects. Existing passing tests do not cover these cases. This is an
audit of local behavior, not a native-host or scientific qualification.

Audited source: `ec58e1ee8ebef011a364b9461fab6de0b25b5dd1`, plugin 0.15.0.
Production source was unchanged. The two pre-existing untracked handoff artifacts
were preserved. All mutations used disposable synthetic projects, including the
overwrite and symlink reproductions. No scheduler, reviewer, external model,
network citation resolution, commit, push, or publication was invoked.

## Observed results

| Check | Result |
|---|---|
| Existing Python suite | 39 programs; 1,330 passed, 26 skipped, 0 failed |
| New standard-library probes | 137 cases; 119 passed, 18 violations; identical decisions on Python 3.12 and 3.14/C |
| New optional H5AD probes | 3 cases on Python 3.11; 1 passed, 2 violations |
| Distinct defects | 9, from the 20 violating observations above |
| Python function inventory | Entry or body execution observed for all 676 functions in 22 production modules |
| Separate H5AD suite | 101 passed, no skips; exercises the 20 reader-dependent baseline skips |
| OpenCode adapter suite | 22 passed; 2 additional timeout/closed-input assertions passed |
| Guard checks | 17/17 ablations detect a removed guard; self-comparison 173/173 identical |
| Pinned differential oracle | 116/173 identical; all 57 expected intentional differences accepted |
| JavaScript execution inventory | Adapter 47/49 V8 entries observed; rendered viewer/journal 91/110 observed |

Function execution is not exhaustive edge-case coverage. The 21 remaining V8
entries, including anonymous callbacks and the journal's `outcomes` helper, have
no recorded call in these probes. Prose-only agent behavior is unverified.
Twenty supplemental helper assertions cover empty text, rendering controls,
nested roots, booleans, numeric bounds, and large integers; they found no new
defect.

- [Receipt and per-module coverage](2026-10-21-adversarial-audit/receipt.json)
- [Every Python function](2026-10-21-adversarial-audit/function-coverage.tsv)
- [JavaScript entries and gaps](2026-10-21-adversarial-audit/javascript-functions.tsv)
- [All new standard-library observations](2026-10-21-adversarial-audit/adversarial.json)
- [Optional H5AD observations](2026-10-21-adversarial-audit/h5ad-adversarial.json)
- [Baseline receipts and skips](2026-10-21-adversarial-audit/baseline.json)
- [Production source hashes](2026-10-21-adversarial-audit/source-sha256.json)

## Reproduce

From the repository root, with an available supported interpreter:

```bash
MYCELIUM_EXTRA_PYTHON=/usr/bin/python3.12 python3.12 tests/adversarial_audit.py --output /tmp/mx-adversarial.json
```

Exit 1 means a probe found a contract violation; the JSON retains each expected
and observed result. This audit runner deliberately sits outside the CI
`test_*.py` glob: it reports current defects rather than blessing them as expected
failures. It uses only the standard library and creates its own temporary inputs.

The results directory beside this report contains the final observations,
baseline test receipts, source identities, and a function inventory. Counts and
coverage are recorded there so that a later run can be compared without treating
this dated observation as current qualification.

## Findings

### 1. P1: the data checker can overwrite the data it just checked

`skills/data-contract-check/scripts/data_contract_check.py:1184` accepts
`--result-json` equal to the contract path or the input table path. Both probes
exit 0 and replace the original input with a result document. The check is
advertised as read-only, and the successful exit conceals the loss.

Smallest repair: reject a result destination that resolves to any contract,
table, or reference input before publishing the result. Preserve the original
bytes on every rejected invocation. `method_fidelity.py` already rejects its two
input paths; the contract checker needs the corresponding complete input set.

### 2. P1: shell spellings hide an unapproved analysis run

`hooks/gate.py:427` and `hooks/gate.py:642` do not recognize these equivalent
execution forms:

```bash
python $'analys\151s/x.py'
python $'\x61nalysis/x.py'
ionice -c 3 python analysis/x.py
setsid python analysis/x.py
```

With a real gated temporary project, no approval, and `on_error: deny`, the pre
hook emits no denial for all four. The plain spelling is denied. The ANSI-C
quote cases are shell byte escapes, not unknown variable expansions.
All four forms also executed the same harmless print-only script under Bash,
using a temporary `python` alias to the available Python 3.12 interpreter.

Smallest repair: decode supported ANSI-C path literals, deny unsupported dynamic
spellings conservatively, and extend the existing wrapper recognition for these
two launchers. Keep benign command-as-data controls. This remains a cooperative
shell reader: these fixes cannot establish a general shell sandbox.

### 3. P1: pending-write preparation follows a state-directory symlink

`hooks/confirm_write.py:31` uses a direct `open()` under
`.mycelium-extra/write-pending/`. If that directory links outside project state,
preparation succeeds and writes its pending JSON there. This bypasses the
symlink refusal already used by the shared state writer.

Smallest repair: use the existing guarded state publication path and reject a
symlinked state directory before creating anything. The probe's outside target
is another temporary directory; no real external state was written.

### 4. P2: portable evidence can retain an environment secret in a filename

`hooks/evidence.py:25` scrubs finding text, but the output `path()` only checks
relative-path syntax. A recorded environment value `synthetic-sensitive` remains
in `analysis/synthetic-sensitive.tsv` in the exported evidence. All three
synthetic variants reproduce the same defect. The projection nevertheless lists
environment values among the withheld categories.

Smallest repair: apply the existing sensitive-value policy to projected path
fields, withholding a path when sanitizing it would make it a false coordinate.
Audit other allowlisted string fields against the same policy. No genuine secret
was used in these tests.

### 5. P2: malformed CSV can supply a verified numeric claim

`skills/verify/scripts/verify.py:1599` uses a lenient CSV reader and does not
reject extra fields. Both `x,0.05,unexpected` under a two-column header and an
unterminated quote return a usable cell. The end-to-end `check_claims()` probe
labels the unterminated-quote value **verified**, rather than unavailable.

Smallest repair: require strict CSV parsing and a consistent row shape before
using a cell or row count. Preserve the existing ambiguity checks for duplicate
headers and duplicate row labels. The data-contract reader already rejects these
malformed shapes.

### 6. P2: invalid validation IDs crash the declaration reader

`hooks/validation.py:137` records an error for a non-string check ID but then
unconditionally adds it to a set. `id: []` and `id: {}` raise `TypeError` instead
of returning `(None, errors)`. The launcher may convert the crash into a gate
error according to `on_error`; this is not successful declaration validation.

Smallest repair: add only a valid string ID to the duplicate-ID set. Test both
the reader's structured errors and the user-visible hook response.

### 7. P2: non-finite consent timestamps pass the newer-than-packet check

`skills/plan-review/scripts/review_packet.py:237` accepts JSON `NaN` and
`Infinity` as numeric timestamps. Neither is rejected by the `<= created`
comparison, so both consent records pass. Boolean and negative controls are
refused. A future *finite* timestamp was removed from the defect set because the
documented contract requires newer-than-preparation, not an upper clock bound.

Smallest repair: require a finite, non-boolean timestamp before the ordering
check. This finding concerns malformed cooperative consent state; it does not
claim that an attacker who can already forge consent files gains a new sandbox
escape.

### 8. P3: a refused atomic state write still creates an outside directory

`hooks/stateio.py:29` calls `makedirs()` before checking for a symlink. For a
linked state parent and a new nested destination, it raises the expected
`ValueError` but leaves the nested directory in the linked outside location.
File contents remain protected in this reproduction.

Smallest repair: check existing ancestors before creating directories, retaining
the final target check before publication. This deterministic side effect is
separate from untested concurrent symlink-swap races.

### 9. P2: malformed H5AD categorical codes crash instead of becoming gaps

`skills/data-contract-check/scripts/data_contract_check.py:212` indexes categories
without validating the codes' type. An H5AD with float codes `[0.5]` or string
codes `["x"]` raises `TypeError`; the CLI exits 1 with a traceback. Both should
be unreadable-column gaps (exit 3), not unhandled exceptions. A matched valid
control with integer codes `[0]` passes, and the existing 101-test H5AD suite
passes in the same environment.

Smallest repair: validate categorical-code type and bounds before indexing and
raise the existing `TableGap` for malformed encodings. Preserve standard missing
code handling. Reproduce with an existing environment containing h5py and numpy:

```bash
python tests/adversarial_audit.py --h5ad-only --output /tmp/mx-adversarial-h5ad.json
```

If the optional reader is absent, this mode writes an explicit gap and exits 3.
The three H5AD probes were run with Python 3.11; they are separate from the 137
standard-library probes compared on Python 3.12 and 3.14/C. Together they give
140 cases, 120 passes, and 20 violating observations across the nine findings.

## Coverage of all 13 skills

“Held” below means the observed cases held, never all possible inputs. The JSON
and baseline receipts give the complete executed case lists.

| Skill | Adversarial cases and evidence | Assessment |
|---|---|---|
| data-contract-check | Empty/malformed/invalid UTF-8 tables, duplicate keys, missing values, vacuous filters, invalid numeric settings, input overwrites; malformed categorical H5AD probes and H5AD suite | Input preservation and malformed categorical handling fail; ordinary validation controls hold |
| decision-status | Fenced fake decisions and extraction suite | Tested parser controls hold; interpreting contested decisions remains agent behavior |
| focus | Traversal, session-name collisions, documented `list` command and focus suite | Tested controls hold; focus does not confer approval |
| grill | Reference contracts, planted-defect end-to-end suite, scientific convention tests | Static and fixture coverage; live questioning, routing, and hostile-text compliance are unverified |
| handoff | Reviewed pending-plan preservation, concurrent pending plans, existing-file replacement, and secret-omission instructions | Instruction review only; no native agent replay or actual handoff overwrite |
| harden | Reviewed failed-current-code, non-failing reproduction, and confirmation scenarios | Instructions require stopping without a false structural claim; actual agent compliance unverified |
| idea | Cell escaping; capture suite covers collisions, recovery, helper failure and changed files | Tested capture cases hold |
| idea-triage | Reviewed duplicate titles, missing files, unknown scores, `park all`, and helper-failure instructions | Instruction review only; actual ranking and write restraint unverified |
| init | No-write dry run, CLI parser, configuration/init suite | Tested controls hold |
| new-analysis | Empty/repeated/reordered/traversal/unsupported steps, mixed-step dependency chain and scaffold suite | Tested controls hold, subject to recorded optional-tool skips |
| plan-review | Redaction syntax, recognizable identifiers/secrets, malformed consent timestamps, packet hash/consent suite | Non-finite consent timestamps fail; local packet controls otherwise hold in tested cases |
| track-changes | Path and note traversal, malformed history, secret scrubbing, HTML injection, journal/viewer suites | Tested controls hold; shared evidence-path redaction remains finding 4 |
| verify | Ambiguous/malformed claims, fidelity duplicate keys, exact commands, verifier suite | Malformed-table claim validation fails; other executed controls hold |

## Hooks and functions

The inventory covers every Python function definition, including local helpers
and methods, in the eight hook modules, thirteen skill helper modules, and the
example consumer. It records observed execution or an explicit coverage gap for
each function. Line/branch coverage and function-entry observations are evidence
of execution, not proof that every edge case of that function was tested.

The shell launcher has its own test suite. Claude, Codex, and OpenCode event
normalization, approval lifecycle, receipt handling, guarded provenance recovery,
and the offline HTML viewers have local fixture tests. The OpenCode adapter's
JavaScript tests were run directly, with a deliberately failing tiny Node test as
a check that failures are observable. Browser behavior beyond the simulated DOM,
real host dispatch, scheduler execution, live citations, paid reviews, and full
agent compliance with Markdown skills were not tested.

Known documentation limits were kept separate from new defects: unknown secrets
can evade pattern scans; allowed text attachments can contain sensitive tables;
the shell reader is heuristic; scientific validity is outside verify's status;
and a missing optional tool is a gap or skip, not a passing check.
