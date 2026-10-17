# Development

[Back to README](../README.md)

Mycelium Extra sits between a plan and its execution. A small change to command
recognition or a hook payload can change which runs are allowed, so development
starts with the behavior you intend to change and the checks that demonstrate
it. The shared gate should keep the same meaning in Claude Code and Codex.

## Testing a change

Run the affected skill's tests and the gate tests first:

```bash
python3 skills/<skill>/tests/test_<name>.py
python3 hooks/tests/test_gate.py
```

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
changes. `python3 tests/test_example.py` checks that what it quotes still exists in the code.

`python3 tests/test_versions.py` checks that the three manifests and the newest `CHANGELOG.md` heading name the same version, and `python3 tests/check_links.py $(git ls-files '*.md')` that every relative link and anchor resolves.

CI (`.github/workflows/ci.yml`) runs on every push to `main`, every pull request, and manual dispatch. It has two jobs.

**`tests`** runs in three official, non-slim Python images (the slim images have no `git`, so the git tests would skip instead of fail), with `fail-fast` off:

| Image | `LC_ALL` |
|---|---|
| `python:3.9-bookworm` | `C` (as on a bare HPC shell; PEP 538 switches Python to UTF-8 there, as it does for users) |
| `python:3.12-bookworm` | `C.UTF-8` |
| `python:3.14-bookworm` | `C.UTF-8` |

Each leg then runs, in order: every `hooks/tests/test_*.py`, `skills/*/tests/test_*.py`, and `tests/test_*.py` file with `python3` (a failure is reported and the loop goes on, then the step fails); `python3 tests/e2e/ablate.py`; and `tests/check_links.py` over the tracked Markdown files (leaving out the historical `mycelium-extra-improvements/` snapshot folder). Files outside those patterns, such as `tests/integration_workflows.py`, are not run by CI. The Sphinx build is a separate workflow, `docs.yml`.

**`gate-diff`** runs only on pull requests, in `python:3.14-bookworm` with full history. It compares the working tree's gate against the **fixed** base `384e6394b71cdae6ab983f0b10fa8d4f5e65c900`, not the pull request's base commit:

```bash
python3 hooks/tests/gate_diff.py --base 384e6394b71cdae6ab983f0b10fa8d4f5e65c900 --expect hooks/tests/gate_diff_expected.json
python3 hooks/tests/gate_diff.py --self-check
```

The first command fails unless every difference from that base matches `hooks/tests/gate_diff_expected.json` exactly (the old and new exit status, output, and state for each case), the base, fuzz count, seed, and case count match, and no case differs that is not listed. The second compares the current source with itself and requires no differences. Because the base is fixed, the listed differences are expected on every pull request, and any other change in a decision turns the check red until the oracle is updated and reviewed.

Before changing `hooks/gate.py`, also run `python3 hooks/tests/gate_diff.py`: with no options it compares the committed gate (`HEAD`) with the working tree and must report every case identical, except the decisions you meant to change. To reproduce the CI result locally, run the two commands above.

### Changing the gate's behaviour on purpose

An intended gate behaviour change needs a named regression test that fails before the change and passes after it, and a reviewed, case-specific rationale for each oracle entry it changes. Never regenerate `gate_diff_expected.json` blindly to turn a red comparison green: the file is the record of which decisions changed and why, and the comparison matches observed output only. It does not read the `rationale` text, so reviewing that each entry still describes its own case is a human step.

## Python compatibility and versions

The plugin needs Python 3.9 or later. Hooks and skill commands run through `hooks/py.sh`, which uses `MYCELIUM_EXTRA_PYTHON` if set, else `python3` when it is 3.9 or later (hooks skip this probe), else the newest `python3.N` on `PATH`; on RHEL 8, bare `python3` is 3.6. `hooks/gate_run.py` up to its version check stays parseable by Python 3.6, so an old interpreter is reported through `on_error` instead of failing with a SyntaxError; `hooks/tests/test_py_launcher.py` runs it under `/usr/bin/python3.6` when that exists.

Bump `version` in `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, and `.claude-plugin/marketplace.json` together, so `claude plugin update` picks up the change. The same commit adds a [CHANGELOG.md](../CHANGELOG.md) entry for the new version.

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
