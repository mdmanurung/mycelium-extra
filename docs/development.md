# Development

[Back to README](../README.md)

Mycelium Extra sits between a plan and its execution. A small change to command
recognition or a hook payload can change which runs are allowed, so development
starts with the behavior you intend to change and the checks that demonstrate
it. The shared gate should keep the same meaning in Claude Code, Codex, and OpenCode.

## Testing a change

Run the affected skill's tests and the gate tests first:

```bash
python3 skills/<skill>/tests/test_<name>.py
python3 hooks/tests/test_gate.py
```

For the OpenCode adapter (`opencode/index.js`), run `python3 hooks/tests/test_opencode_gate.py` and
`node --test opencode/tests/gate.test.js` (CI uses Node 22; `package.json` has no `test` script). The
adapter spawns `hooks/py.sh`, so the Node tests need Python 3.9 or later on `PATH` or in
`MYCELIUM_EXTRA_PYTHON`, and their spawn cases skip without it.

Then run `python3 tests/test_end_to_end.py` on the fixture project (about two
minutes) and `python3 tests/test_fixture_data.py`. The ablations in
`python3 tests/e2e/ablate.py` remove individual guards to check that the defect
cases actually depend on them. See the [fixture design](design/c1-fixture-project.md).

Two more files under `tests/` cover the edges of the checks. `tests/test_contract_compatibility.py`
runs a fixed corpus of small tables through Extra's data-contract checker and, when a Mycelium
checkout is available, through Mycelium's `skills/core/scripts/data_contract_check.py`; set
`MYCELIUM_UPSTREAM` to that checkout (the default is a local path, so on CI only the local half runs).
Each case must give the same pass, gap, or block outcome in both, and the test never writes into the
checkout. `tests/test_eval_score.py` tests the scorer and leakage rules of the evaluation scaffold in
`tests/eval/`, using synthetic adjudications only; it checks the scorer, not the product.
`hooks/tests/test_gate_diff.py` checks that the gate-comparison oracle rejects a missing, new, or
changed difference.

`docs/example.md` is generated: with a real `scilintr` and an `Rscript` whose R has it, run
`MX_E2E_SCILINTR=<path> MX_E2E_RSCRIPT=<path> python3 tests/e2e/make_example.py` when an output format
changes (the gate it runs needs Python 3.9 or later: on RHEL 8, use `python3.11`). `python3 tests/test_example.py` checks that what it quotes still exists in the code.

`python3 tests/test_versions.py` checks that the four manifests (the Claude Code and Codex plugin manifests, the marketplace entry, and `opencode/package.json`) and the newest `CHANGELOG.md` heading name the same version, and `python3 tests/check_links.py $(git ls-files '*.md')` that every relative link and anchor resolves.

CI (`.github/workflows/ci.yml`) runs on every push to `main`, every pull request, and manual dispatch. It has three jobs.

**`tests`** runs in three official, non-slim Python images (the slim images have no `git`, so the git tests would skip instead of fail), with `fail-fast` off:

| Image | `LC_ALL` |
|---|---|
| `python:3.9-bookworm` | `C` (as on a bare HPC shell; PEP 538 switches Python to UTF-8 there, as it does for users) |
| `python:3.12-bookworm` | `C.UTF-8` |
| `python:3.14-bookworm` | `C.UTF-8` |

Each leg then runs, in order: every `hooks/tests/test_*.py`, `skills/*/tests/test_*.py`, and `tests/test_*.py` file with `python3` (a failure is reported and the loop goes on, then the step fails); `python3 tests/e2e/ablate.py`; and `tests/check_links.py` over the tracked Markdown files Files outside those patterns, such as `tests/integration_workflows.py`, are not run by CI. The Sphinx build is a separate workflow, `docs.yml`.

**`gate-diff`** runs on pull requests and on demand (`gh workflow run CI`, or the Actions button), in `python:3.14-bookworm` with full history. It compares the working tree's gate against the **fixed** base `267d9e244d1f50abef2d024c9632c50df1911823` (the 0.10.2 release), not the pull request's base commit. The pin must name the same commit as `hooks/tests/gate_diff_expected.json`; `tests/test_ci_pins.py` fails if the two drift apart:

```bash
python3 hooks/tests/gate_diff.py --base 267d9e244d1f50abef2d024c9632c50df1911823 --expect hooks/tests/gate_diff_expected.json
python3 hooks/tests/gate_diff.py --self-check
```

The first command fails unless every difference from that base matches `hooks/tests/gate_diff_expected.json` exactly (the old and new exit status, output, and state for each case), the base, fuzz count, seed, and case count match, and no case differs that is not listed. The second compares the current source with itself and requires no differences. Because the base is fixed, the listed differences are expected on every pull request, and any other change in a decision turns the check red until the oracle is updated and reviewed.

The comparison skips `denies.jsonl` (the deny log records no decision), so a new line there is never a difference.

**`opencode-plugin`** runs `node --test opencode/tests/gate.test.js` on Node 22 (`actions/setup-node`). The runner's `python3` is recorded in `MYCELIUM_EXTRA_PYTHON` by the test, so the gate runs even where the default `python3` is too old.

Before changing `hooks/gate.py`, also run `python3 hooks/tests/gate_diff.py`: with no options it compares the committed gate (`HEAD`) with the working tree and must report every case identical, except the decisions you meant to change. To reproduce the CI result locally, run the two commands above.

### Changing the gate's behaviour on purpose

An intended gate behaviour change needs a named regression test that fails before the change and passes after it, and a reviewed, case-specific rationale for each oracle entry it changes. Never regenerate `gate_diff_expected.json` blindly to turn a red comparison green: the file is the record of which decisions changed and why, and the comparison matches observed output only. It does not read the `rationale` text, so reviewing that each entry still describes its own case is a human step.

## Python compatibility and versions

The plugin needs Python 3.9 or later. Hooks and skill commands run through `hooks/py.sh`, which uses `MYCELIUM_EXTRA_PYTHON` if set, else `python3` when it is 3.9 or later (hooks skip this probe), else the newest `python3.N` on `PATH`; on RHEL 8, bare `python3` is 3.6. `hooks/gate_run.py` up to its version check stays parseable by Python 3.6, so an old interpreter is not a SyntaxError: a hook registration from before 0.9.76 (`python3 gate_run.py`, which a directory marketplace keeps until the plugin is updated) first hands the event to `py.sh --hook` once (guarded by `MYCELIUM_EXTRA_REEXEC`), and only if that also lands on an old Python is it reported through `on_error`; `hooks/tests/test_py_launcher.py` runs it under `/usr/bin/python3.6` when that exists.

Bump `version` in `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and `opencode/package.json` together, so `claude plugin update` picks up the change and every host reports the same version. The same commit adds a [CHANGELOG.md](../CHANGELOG.md) entry for the new version.

## Cross-host checks

Passing a Python test does not show that a host loaded the plugin or dispatched
its hooks. Check both layers: the shared behavior in the test suite, and the
installed plugin in a real host session.

`python3 hooks/tests/test_codex_gate.py` checks the Codex entrypoint's approval
flow, receipts, missing exit status, and state protection for patches and moves.
`hooks/hooks.json` is Claude's configuration; the Codex manifest points to
`hooks/codex.json`. Keep host decoding at the launcher boundary and reuse the
shared gate. Codex shell tools expose `Bash` and `tool_input.command` to hooks.
Do not assume a Codex post event means exit 0.

Validate Claude's marketplace and plugin separately:

```bash
claude plugin validate .
claude plugin validate .claude-plugin/plugin.json
```

For Codex, install the checkout in a disposable `CODEX_HOME`, check the cached
files against the source, and test discovery. Real host tests need trusted,
enabled hooks; invoking the Python launcher alone does not prove dispatch.

OpenCode V2 loads the adapter from `opencode/` as a plugin directory; on 2.0.32
a `plugins` entry naming a `.js` file draws a `configured plugin path must be a
directory` warning, so ship and test the directory form. `node --test
opencode/tests/gate.test.js` checks payload mapping, handler wiring, the event
envelope (`data.sessionID`, `data.text`), location filtering, the
`/mycelium-extra:<skill>` commands, and the spawn contract against the real
`gate_run.py`; `hooks/tests/test_opencode_gate.py`
checks the launcher's mapping, approvals, receipts, and state protection; CI
runs the first as the `opencode-plugin` job. The 2.0.32 server event stream is
service-wide — a plugin instance receives every location's session events — so
the adapter filters to its own location, and a test covers that. A passing
suite does not show the plugin loaded or dispatched: install it in a disposable
location, confirm it appears in the host's plugin list, and run the denied-run
→ card → approval → receipt journey before claiming OpenCode support.

### Validated on 2026-10-06

Version 0.9.43 was checked with Claude Code 2.1.291 and Codex CLI 0.160.0.
Both live hosts denied an unapproved fixture run, registered a plan through
Stop, accepted its hash through UserPromptSubmit in the same session, allowed
the approved run, and wrote a receipt. Claude's receipt recorded exit 0;
Codex's recorded `unknown`, matching its missing hook exit metadata. A failed
Codex run also left an `unknown` receipt rather than a success claim.

Codex discovered nine skills and four hooks without hook configuration errors;
62 installed hook and skill files matched the source. All 14 test files passed
on Python 3.6.8; the Python 3.12.14 suite and corrected heading checks passed
as well. Optional-tool cases retained their skips. Gate comparison was 160/160
identical and all three ablations caught their missing guards. The Sphinx build
had no warnings; Markdown links and generated HTML paths had no broken targets.
These checks validate the local candidate, not a published installation or a
GitHub Pages deployment.

### Validated on 2026-10-17 (OpenCode V2 2.0.32)

The OpenCode adapter was qualified with OpenCode 2.0.32 and
`opencode-go/deepseek-v4-pro` in a disposable repository. The plugin loaded from
a `plugins` entry naming the `opencode/` directory, and the skills loaded from
the `skills` entry. An unapproved `python analysis/x.py` was denied and the
model quoted the gate's reason word for word. The plan pinned at the turn's
`session.execution.succeeded` event — 2.0.32 delivers no `session.idle` — the
approval card arrived as a synthetic message, a `approve plan c260d4cc` user
prompt registered the approval (a quote-wrapped `"approve plan c260d4cc"` was
refused with "nothing approved"), and the approved `python3 analysis/x.py` ran
and wrote a receipt with `host: opencode`, the plan credited, and
`launch_match: matched`. A `write` into `.mycelium-extra/` was denied and left
no file. The first attempt recorded `exit_status: unknown` for both a failed run
(`python` missing) and the successful run; a review pass then found the code in
the shell result's `metadata.exit` (mirrored in `output.exit`), a launcher
mapping gap rather than a host gap, and the adapter maps it to `exit_code`.
Re-running recorded `exit_status: 127` and `exit_status: 0`, both
`exit_source: response`. The plugin's `/mycelium-extra:<skill>` commands
registered and listed, the same names Claude Code uses, and invoking
`/mycelium-extra:verify status` submitted the skill-loading prompt for that
skill. The shell tool reports the outcome `completed` even for
a nonzero exit, so no status is ever inferred from that word. Notices delivered
as synthetic messages persist in the transcript and
are visible to the model as well as the user, and the model may proceed to run
an approved plan immediately after the approval. The `plan-review` OpenCode
route (Codex CLI for the engineering review, Biomni MCP for the biomedical one)
is implemented but was not exercised here: both legs send material off the
machine and need the user's consent, so qualifying them is the user's call.
`python3.12
hooks/tests/test_opencode_gate.py` (8 tests), `node --test
opencode/tests/gate.test.js` (11 tests), the 421-test gate suite, `gate_diff`
168/168, and the 103-test end-to-end suite passed. These checks validate the
local candidate, not a published installation.

## Usage measurement (the ~2026-10-31 review)

The opt-in features shipped between 0.11.0 and 0.13.2 were released on the
understanding that they would be reviewed after a measurement window: the
`card_coverage` row, the coverage exceptions, the decision trace, the correction
lookup and the evidence assistance. (`card_coverage` was turned on by default on 2026-10-19, before the review, at the user's request; the new `focus_notices` is off by default.) The last two landed in 0.13.2, so they have
the shortest exposure before the ~2026-10-31 review and a low reading for them
says more about the calendar than about the feature. Nothing in the gate records a "feature was
used" event, and none of the state files is written for this purpose, so the
measurement is assembled read-only from what the gate already keeps. Run it
against each live project that has a `.mycelium-extra/` folder; the two in use
are `/exports/para-lipg-hpc/mdmanurung/bmv_pilot_cytof_integration` and
`/exports/para-lipg-hpc/mdmanurung/scale`.

There is no pre-0.11.0 baseline in either project. Take a reading now and again
at the review: a before/after over a window you define is worth more than the
absolute numbers, which only say how busy a project was.

```bash
P=/exports/para-lipg-hpc/mdmanurung/bmv_pilot_cytof_integration   # then the same for .../scale
cd "$P"

# Approvals per day, and the latency between a plan being shown and approved.
# approvals.jsonl holds one line per approval: shown_ts, approved_ts, latency_s,
# plan_chars and plan_rows — how big the plan was is part of the cost of approving one.
jq -r '.approved_ts | strftime("%Y-%m-%d")' .mycelium-extra/approvals.jsonl 2>/dev/null | sort | uniq -c
jq -s '{n: length, median_latency_s: (map(.latency_s // 0) | sort | .[length/2 | floor]),
        mean_plan_rows: (map(.plan_rows) | if length > 0 then add / length else 0 end)}' .mycelium-extra/approvals.jsonl 2>/dev/null

# A second, independent approval count: one frozen plan per approval.
ls .mycelium-extra/approvals/ 2>/dev/null | wc -l

# Denials the gate made, and why. The file only exists once a denial has happened.
{ wc -l < .mycelium-extra/denies.jsonl; } 2>/dev/null || echo "no denial recorded yet"
jq -r .reason .mycelium-extra/denies.jsonl 2>/dev/null | sort | uniq -c | sort -rn

# Re-pins and freezes per plan (one line per re-pin), and plans frozen without one.
wc -l .mycelium-extra/repins/*.jsonl 2>/dev/null || echo "no re-pin recorded yet"
ls .mycelium-extra/approvals/ 2>/dev/null | wc -l

# A gate that could not decide. Anything here is a gate bug or a host problem, not a denial.
{ wc -l < .mycelium-extra/gate-errors.jsonl; } 2>/dev/null || echo "no gate errors"
jq -r '.reason // .error // "?"' .mycelium-extra/gate-errors.jsonl 2>/dev/null | sort | uniq -c | sort -rn

# Read-only work: explore grants, and the runs a launch hook recorded.
ls .mycelium-extra/explore-grants 2>/dev/null | wc -l
ls .mycelium-extra/launches 2>/dev/null | wc -l

# Reportable work that was verified. `verify` itself leaves no record — it is read-only
# by design — so the only trace of verification is the provenance folder `verify write`
# creates. Keep the depth bounded: a full-tree find is slow on a large project.
find . -maxdepth 6 -type d -name provenance -newermt 2026-07-01 2>/dev/null | wc -l
```

Two things this cannot measure, and should not be read as measuring. **`verify`
runs are not recorded anywhere.** Every `verify` subcommand except `write` is
read-only, so a project that reads the report daily and a project that never
opens it look identical in the state files; the `provenance/` count above is a
lower bound on `verify write` only. **`card_coverage` use is not recorded
either**: it changes what is printed, not what is stored, so the row's effect
has to be judged from the transcript that asked for it and from whether a
coverage exception was approved, which shows up as a `plan_rows`/`plan_chars`
change and, for the placement question, as a `denies.jsonl` reason.

A first reading on 2026-10-19, as a baseline (both projects predate 0.11.0's
last release, so this is a starting point, not a before):

| Project | `approvals.jsonl` | `approvals/` | `receipts.jsonl` | `launches` | `denies.jsonl` | `repins/` | `gate-errors.jsonl` | `explore-grants` | `provenance/` |
|---|---|---|---|---|---|---|---|---|---|
| `bmv_pilot_cytof_integration` | 1 | 99 | 379 | 0 | absent | 0 | 21 | 3 | 42 |
| `scale` | absent | 45 | 196 | 0 | absent | 0 | absent | 0 | 3 |

The `bmv` approvals log has one line because it was added in 0.11.0; the 99 files
in `approvals/` are the real approval count, which is why the folder is counted
separately. `scale` has no `approvals.jsonl` at all, so its summary line reports
`n: 0` and a null median rather than failing — worth knowing before reading a
zero as "no approvals". The 21 gate errors are 20 hosts where the hook ran a
Python older than 3.9 and 1 `No module named 'gate'` — the reason strings are
specific enough to triage, which is the point of keeping them.

## Documentation website

The website and repository use the same Markdown pages. You can improve a
guide without maintaining a second copy, and Sphinx checks the links when it
builds the site.

Use Python 3.12 for the website tooling.

```bash
python3.12 -m venv /tmp/mycelium-extra-docs
/tmp/mycelium-extra-docs/bin/python -m pip install -r docs/requirements.txt
/tmp/mycelium-extra-docs/bin/python -m sphinx -b html -W --keep-going -c docs . docs/_build/html
/tmp/mycelium-extra-docs/bin/python -m http.server 8000 --directory docs/_build/html
```

Open `http://localhost:8000/`. The build treats warnings as errors and checks
internal document links. The configuration uses an explicit list of user guides
and the run-plan reference. Developer instructions, roadmap, changelog, design notes, and the
repository README are excluded from the website and its search index.
Generated HTML is ignored by Git.

The Documentation workflow builds every pull request and publishes pushes to
`main`. In GitHub repository **Settings → Pages**, choose **GitHub Actions**
as the source before the first deployment. The published URL will be
`https://mdmanurung.github.io/mycelium-extra/`. A local build does not publish it.
See [Sphinx's deployment guide](https://www.sphinx-doc.org/en/master/tutorial/deploying.html).
