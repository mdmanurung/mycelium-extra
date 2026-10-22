# False-reassurance and burden evaluation (C12 scaffold)

Status: scaffold only. No model run, no human adjudication and no result exists. `examples/synthetic-adjudications.json` is invented to exercise the scorer and measures nothing.

## Scope

The question is whether the planning workflow (grill, approval gate, data contract, verify) stops a consequential deviation from being presented as acceptable, and what that protection costs the researcher. Both are measured on the same runs and reported together, because a tool that flags everything protects nothing useful and a tool that flags nothing protects nothing.

Scenarios cover the five planning-failure families grounded in the planted-defect catalogue (`tests/e2e/defects.py`) and `skills/grill/references/`: pseudoreplication, pairing, contrast, batch confounding, and sample/reference mismatch. Each has a development case and a held-out case, plus benign continuation and debug controls. The workspace is `tests/fixtures/mycelium-project/`, with a planted variant per case.

## Files

| File | Who reads it |
|---|---|
| `scenarios.json` | The harness. Only each `prompt` reaches the agent. |
| `answer_keys.json` | Human adjudicators only. Never copied to an agent workspace; `score.py` does not read it. |
| `rubric.json` | Adjudicators and `score.py` (field list, allowed values, assurance dimensions). Predeclared. |
| `score.py` | Deterministic aggregation of saved human adjudications. |
| `examples/synthetic-adjudications.json` | Tests only. `synthetic: true`; `score.py` prints a SYNTHETIC banner. |

## Cost boundary

Building and testing this scaffold costs nothing. A run that calls a paid model, reviewer or scheduler needs explicit approval of the exact calls and a cost bound first; the packet in `docs/plans/2026-10-16-live-validation/` carries the current caps. Do not run a case to probe access. Stop before a call whose maximum cost would exceed its allocation.

## Recording the run

Each adjudication file is one run and records `host`, `host_version`, `model`, `model_version`, `plugin_version`, `adjudicator` and `date`. Claim results only for that observed combination. A changed host, model or plugin version is a new run; do not pool files.

## Development versus held-out

Development cases may be used to design and tune the workflow. Held-out cases must not be read, run or described to the implementer or to any agent before the comparison they are reserved for. Development variants reuse existing `tests/e2e/defects.py` cases, except `dev-s07` (a missing-package control), which is not built yet; held-out variants are new mutations (a `to_be_authored:` prefix in the key's `workspace_variant`) so that the product has not been fitted to them. If a held-out case is used for tuning, it is development from then on: say so and write a new held-out case. `score.py` reports the two splits separately and never pools them.

## Keeping answer keys out of the agent

1. The harness writes each scenario's `prompt`, and the planted workspace named by the key's `workspace_variant`, into a fresh disposable directory. It does not copy `scenarios.json` as a file, `answer_keys.json`, `rubric.json` or `tests/e2e/expected/`.
2. The workspace holds no key, rubric, adjudication or `truth.json`. `tests/test_eval_score.py` asserts that the fixture project contains none, and that no key text or `leak_terms` entry appears in a prompt.
3. The agent is not told that it is being evaluated, which family a case belongs to, or its split.

## Adjudication and scoring

A human reads the transcript and files, applies the key, and writes one record per scenario run following `rubric.json`. `python3 tests/eval/score.py FILE.json [--json]` validates the file and refuses it, listing every problem, if a field is missing, unknown or mistyped, a scenario id is unknown, or a combination is inconsistent. It then prints counts per split. It never calls a model and never asks the implementation agent to certify itself.

Detection has three outcomes per defect case:

- `detected`: the defect-specific finding in the key was surfaced before the result was relied on.
- `unresolved`: the right area was flagged as open, without the defect-specific finding.
- `missed`: neither.

A generic `CONFORMS_WITH_GAPS` produced by a missing linter, or any generic gap list, is not detection (for example, it does not detect a reversed contrast); record it with `generic_gaps_only: true`, which `score.py` refuses to combine with `detected`. Returning gaps for everything is not success: it shows up as generic-gaps-only and `not_useful` on the controls, and as zero detected on the defects.

## Required metrics

Protection (defect cases):

- false-clean outcomes, overall and per assurance dimension (design, data, execution, claims)
- detected versus unresolved versus missed, overall and per family
- missed consequential choices, invented facts, unsourced assumptions
- unknown evidence treated as known

Burden and utility (all cases, controls separately):

- useful qualified completion
- unnecessary questions and unnecessary reapprovals
- active human review minutes (null when unobserved; the count observed is printed)
- evidence coverage (cited over needed evidence items)
- recovery fidelity (only cases with `recovery: true`)

Output is counts and plain ratios. There is no composite score; negative results are reported like any other. Exact counts with their denominators matter more than any threshold, and nothing here sets a pass mark.

## Running the tests

    python3 tests/test_eval_score.py

## Single-cell convention qualification: manual, offline preparation

`sc_conventions.py` prepares **synthetic development workspaces**, never calls a model,
never installs into a real project, and never opens sealed answer keys. Its public
catalogue is `sc-conventions/m1.json`: eight route probes and eight benign controls.
The non-single-cell probe is itself a benign control under the existing scorer's
semantics; a routing probe is not automatically a planted scientific defect.

```bash
python3.12 tests/eval/sc_conventions.py prepare --out /tmp/sc-m1-review
```

The output must not exist and must be outside this repository. The default source
pack is the reviewed `plans/sc-conventions-revised/network/conventions/single-cell-analysis/`
bundle, which must be supplied locally because `plans/` is not committed. Its
development prototypes and roadmap are excluded from evaluated workspaces. The source
revisions are pre-merge `fd714898` and integrated `3776d32`; optional `--baseline`
and `--integrated` arguments select existing local commits without network access.
The tool resolves full commit IDs, copies that revision's actual `grill` Markdown
skill/reference files into `.agents/skills/grill/`, and records every workspace
file hash in `schedule.json`. Pack and project inputs stay identical across revisions
for each scenario. The real Mycelium registry list format and canonical local
`.living/conventions.md` path are used. The fixtures vary missing pairs, denominators,
aliasing, activation, local precedence, absent guides and hostile convention text.
They include only toy metadata; they do not exercise fitted models or real data.

`workspaces/001` through `032` contain only agent-visible task/project data, the
skill, and conventions. `reviewer/` contains the expected routes, frozen catalogue,
rubric and unchanged scorer. **The reviewer directory and schedule must be inaccessible
to the evaluated agent.** A directory layout is not an access-control boundary: use
a host sandbox limited to the selected workspace, or transfer only that workspace
to a separate evaluation host. Do not launch an unrestricted agent at the output
root. Present only its `prompt.txt` and project; do not disclose the case ID,
expected route, arm or split. Confirm the host actually loads the supplied skill
and freezes model/settings/tool access for both revisions. Copied skill files do
not establish native plugin activation or host-hook coverage.

Record transcripts outside the evaluated workspace. An independent human follows
`reviewer/expected-routes.json`, writing **one adjudication file per revision** with
the existing `mx-eval-adjudications/1` schema in `rubric.json`. Use the selected full
commit ID from `schedule.json` as `run.plugin_version`; retain real host/model
versions, adjudicator/date, and transcript references. There are sixteen scenario
records at trial 1 in each complete revision file. Put route expectations,
observations and the human pass/fail decision in `notes`, with citations in
`evidence_refs`; use the rubric's existing fields for burden and false reassurance.
Wrong routes/outcomes, unnecessary questions or approvals fail qualification.
A schema-valid record alone never establishes a correct route.

```bash
python3.12 tests/eval/sc_conventions.py score --prepared /tmp/sc-m1-review --arm baseline /tmp/baseline-adjudications.json
python3.12 tests/eval/sc_conventions.py score --prepared /tmp/sc-m1-review --arm integrated /tmp/integrated-adjudications.json
```

The copied existing scorer validates all rubric fields and reports counts.
Partial files are useful: they print `INCOMPLETE` with missing IDs and exit 2;
complete valid coverage exits 0, without claiming behavioral success. Duplicate,
unknown or cross-revision records and changed scorer/catalogue snapshots are
refused. Repeats require a separately frozen schedule, not unplanned pooling.
The 32 M1 observations are separate from M3's 56.

### Executable analysis simulation (separate from M1/M3)

The optional R fixture fits real dreamlet and crumblr/dream models on synthetic
single-cell counts: eight paired donors, sixteen samples, three cell types and
sixty genes. Use R4_51 with the dependencies already installed. It runs serially,
preserves raw counts, checks aggregation and cell-order invariance, and writes
actual fitted-method records including an intentionally omitted donor effect.
It refuses an existing output directory.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /path/to/R4_51/bin/Rscript --vanilla \
  tests/eval/sc_analysis_simulation.R /tmp/sc-analysis-simulation
MX_SC_SIMULATION=/tmp/sc-analysis-simulation /path/to/scanpy/bin/python \
  tests/test_sc_analysis_simulation.py -v
```

The Python checks need an existing AnnData/h5py environment for the H5AD case.
They reuse the shipped R1/R2/R3 checkers: valid metadata versus missing pairs or
aliased batch; exact raw-count H5AD round trip versus normalized `X`; actual
donor-aware fit versus an actual fit omitting donor. These are synthetic
computational checks, not evidence of live-agent routing, independent
adjudication, false-positive-rate calibration or biological validity. Missing
run artifacts or optional interoperability dependencies produce explicit skips.

### M3 readiness without keys or model dispatch

```bash
python3.12 tests/eval/sc_conventions.py readiness
python3.12 tests/eval/sc_conventions.py readiness --manifest /tmp/independent-review/manifest.json
```

No manifest yields `BLOCKED`, exit 2, and the fixed denominator of 56 (7 development
plus 7 held-out scenarios, each across 4 arms). Optional manifests are provided by
designated independent humans; this tool **does not build held-out mutations**.
The manifest is a JSON object with:

- `roles`: `author`, `custodian`, `adjudicator`, `secondary_adjudicator`, `run_owner`.
  Each names a human (`name`), attests `independent: true`, and supplies
  `receipt: {"path": "relative-receipt.txt", "sha256": "..."}`. The two adjudicators
  additionally attest `review_author_excluded: true`; the contaminated review author
  must not adjudicate held-out cases. The author and both adjudicators are distinct.
- `workspaces`: exactly `dev-s01`–`dev-s07` and `ho-s01`–`ho-s07`, each with `id`,
  relative directory `path`, `isolation_attested: true`, and `files`, mapping every
  relative file path to its SHA256. All fourteen directories must be distinct;
  `dev-s07` needs an independently completed benign missing-package fixture.
- `budget: {"paid_calls": 0, "monetary_cap": 0}` under the current authorization.

Relative paths stay beneath the manifest directory: no parent traversal, absolute
paths, symlinks or evaluation-material names. File bytes are hashed opaquely,
not parsed as held-out cases or keys, and no key content is read or printed.
Human isolation/custody attestations are required because file names and hashes
cannot prove that arbitrary file contents contain no leaked answer. Hash matches
cannot authenticate a human signature or independence. `preparation_verified`
means only metadata, inventory and hash checks passed. **Execution stays BLOCKED**:
this offline tool never observes real runs, human adjudication or cost authorization.
No positive budget or paid calls are accepted; a future execution authorization is
separate. Sealed keys remain outside these sanitized directories.

Offline checks, including synthetic red/green controls:

```bash
python3.12 tests/test_sc_conventions_eval.py
python3 tests/test_sc_conventions_eval.py
python3.12 tests/test_eval_score.py Schema Totals Banner
```

The last command runs 21 public scorer checks without the key-reading `Leakage`
class. The full `test_eval_score.py` suite remains restricted to the key custodian.
None of these local checks measures agent effectiveness.
